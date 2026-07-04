"""
doc_parser.py — Extractor de documentos de Drive para Gradus.

Fase 3 de las specs: descarga cada documento del inventario, llama a la API
de Anthropic para extraer datos estructurados, y guarda los resultados en la
tabla extracciones_crudas de catalogo.db.

NO toca tablas del catálogo final — solo extracciones_crudas.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "catalogo.db"

PROMPT_VERSION = "v1_piloto"
MODEL_ID = "claude-sonnet-4-6"
MAX_TOKENS_OUTPUT = 20000
TEMPERATURE = 0
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 5

# Precios claude-sonnet-4-6 (USD por token)
PRICE_INPUT_PER_TOKEN  = 3.0  / 1_000_000
PRICE_OUTPUT_PER_TOKEN = 15.0 / 1_000_000

# ---------------------------------------------------------------------------
# Prompt de extracción (no modificar — aprobado por María)
# ---------------------------------------------------------------------------

PROMPT_EXTRACCION = """\
Eres un extractor de datos de documentos de investigación universitaria de la consultora Gradus \
(college counseling para estudiantes de Latinoamérica). Tu única tarea es leer el documento que \
se te da y extraer información estructurada siguiendo el esquema JSON especificado más abajo.

## Reglas absolutas

1. Solo extraés lo que está literalmente en el documento. No completes campos con información que \
sepas del mundo. No infieras costos, fechas, requisitos o cualquier otro dato que no esté escrito \
en el documento. Si el documento no lo dice, el campo va como null.

2. Cuando hay ambigüedad o duda, marcalo con baja confianza. En vez de "valor": "X" usa \
{"valor": "X", "confianza": "baja"}. La confianza puede ser "alta", "media" o "baja".

3. Nunca inventes universidades o programas. Si una universidad solo se menciona de pasada sin \
información sustantiva, no la incluyas. Solo incluí universidades que tengan al menos una mención \
de programa, requisito, costo, o pathway.

4. Preservá el texto original del documento cuando sea posible. Si el documento dice \
"£28,000/año aprox", el costo_anual_local debe decir "£28,000/año aprox", no "28000 GBP". \
El campo costo_anual_estimado_usd sí puede ser tu conversión numérica aproximada.

5. No traduzcas nombres propios. "University of Manchester" se queda en inglés. \
"Universidad Carlos III" se queda en español.

## Estructura del documento esperada

Los documentos de Gradus suelen tener:
- Un header con datos del estudiante (nombre, intereses, países, promedio, nacionalidad, idiomas).
- Bloques agrupados por país (UK, USA, España, Países Bajos, etc.), y dentro de cada país, \
una o más universidades con sus programas, requisitos, costos, pathways.

## Esquema JSON que debés devolver

Devolvé únicamente el JSON, sin texto antes ni después, sin bloques de código markdown:

{
  "estudiante": {
    "nombre": "string o null",
    "nacionalidades": ["array de strings, ej. ['Colombiana', 'Española']"] ,
    "residencia_actual": "string o null",
    "anio_grado": "número o null",
    "nivel_buscado": "'pregrado' | 'maestría' | 'foundation' | null",
    "areas_interes": ["array de strings"] ,
    "paises_interes": ["array de strings"] ,
    "promedio": "string tal como aparece en el doc (ej. '3.88 W / 3.7 U', 'IB 38', 'A*AA')" ,
    "sistema_calificacion": "string (ej. 'GPA_USA', 'IB', 'A-levels', 'Promedio_LATAM') o null",
    "examenes_estandarizados": "objeto JSON con scores tal como aparecen, ej. {'SAT': 1210, 'IELTS': 7.5, 'Duolingo': null} o null",
    "idiomas": ["array de strings con niveles, ej. ['Español nativo', 'Inglés C1']"] ,
    "presupuesto_anual_usd": "número o null",
    "acepta_pathway": "true | false | null",
    "notas_estudiante": "string o null"
  },
  "universidades": [
    {
      "nombre": "string",
      "pais": "string",
      "ciudad": "string o null",
      "ranking_grupo": "string (ej. 'Russell Group', 'G5', 'Ivy League') o null",
      "publica_privada": "'pública' | 'privada' | null",
      "pagina_oficial": "string (URL) o null",
      "notas_universidad": "string o null",
      "programas": [
        {
          "nombre": "string (ej. 'Aerospace Engineering BEng')",
          "nivel": "'pregrado' | 'maestría' | 'foundation' | 'pathway' | 'year_one'",
          "area": "string (ej. 'Ingeniería Aeroespacial')",
          "duracion_anos": "número o null",
          "idioma_instruccion": "string o null",
          "modalidad": "'presencial' | 'híbrido' | 'online' | null",
          "entradas_anuales": ["array de meses, ej. ['septiembre']"] ,
          "requisitos": [
            {
              "sistema": "string (ej. 'A-levels', 'IB', 'GPA_USA', 'SAT', 'IELTS')",
              "requisito": "string (ej. 'A*AA', '38 puntos', '1300 SAT')",
              "notas": "string o null"
            }
          ],
          "costos": [
            {
              "tipo_estudiante": "'internacional' | 'home_uk_irl' | 'ue' | 'in_state_usa' | 'out_of_state_usa' | 'local' | 'no_especificado'",
              "costo_anual_local": "string tal como aparece en el doc (ej. '£28,000/año')",
              "costo_anual_estimado_usd": "número (tu conversión aproximada) o null",
              "moneda": "'GBP' | 'EUR' | 'USD' | etc. o null",
              "ano_referencia": "número o null",
              "incluye": "string (ej. 'Solo matrícula') o null"
            }
          ],
          "pathways_mencionados": [
            {
              "provider": "string (ej. 'INTO', 'Kaplan', 'Study Group', 'Shorelight', 'OnCampus', 'Navitas')",
              "nombre_pathway": "string o null",
              "ubicacion_campus": "'dentro_campus' | 'fuera_campus' | 'edificio_aparte' | null",
              "duracion_anos": "número o null",
              "costo_anual_local": "string o null",
              "notas": "string o null"
            }
          ],
          "notas_programa": "string o null"
        }
      ]
    }
  ],
  "metadata_extraccion": {
    "secciones_no_extraidas": ["lista de secciones del documento que viste pero no extrajiste"],
    "ambiguedades": ["lista de cosas que te generaron duda al extraer"]
  }
}

## Regla especial sobre el tipo_estudiante en costos

El documento puede no aclarar a qué tipo de estudiante aplica un costo. Reglas:
- Si el documento aclara explícitamente "internacional", "EU rate", "in-state", "home UK": usá ese tipo.
- Si no aclara: usá "tipo_estudiante": "no_especificado". NUNCA asumas "internacional" por defecto.
- Si hay múltiples costos para la misma universidad (ej. un costo home y un costo internacional), \
creá múltiples entradas en el array.

## Regla especial sobre pathways

Si el documento menciona un pathway pero no aclara universidad asociada, igual incluí el pathway \
dentro de la universidad bajo cuya sección apareció. Si el pathway no está asociado a ninguna \
universidad específica, no lo incluyas.

## Si el documento es ambiguo, vacío o no es una investigación

Si después de leer el documento no podés identificar al menos una universidad con información \
sustantiva, devolvé:

{
  "estudiante": {...lo que pudiste extraer...},
  "universidades": [],
  "metadata_extraccion": {
    "secciones_no_extraidas": [],
    "ambiguedades": ["No se identificaron universidades con información sustantiva. \
Posible falso positivo del inventario."]
  }
}

## Documento a extraer

"""

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS extracciones_crudas (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_drive_id   TEXT    NOT NULL,
            documento_nombre     TEXT    NOT NULL,
            fecha_extraccion     DATETIME DEFAULT CURRENT_TIMESTAMP,
            prompt_version       TEXT    NOT NULL,
            modelo_usado         TEXT    NOT NULL,
            json_extraido        TEXT,
            tokens_input         INTEGER,
            tokens_output        INTEGER,
            costo_usd_estimado   REAL,
            estado               TEXT    NOT NULL,
            error_mensaje        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_extracciones_drive_id
            ON extracciones_crudas(documento_drive_id);
    """)
    conn.commit()


def _save_row(
    conn: sqlite3.Connection,
    drive_id: str,
    nombre: str,
    json_text: Optional[str],
    tok_in: Optional[int],
    tok_out: Optional[int],
    costo: Optional[float],
    estado: str,
    error_msg: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO extracciones_crudas
            (documento_drive_id, documento_nombre, prompt_version, modelo_usado,
             json_extraido, tokens_input, tokens_output, costo_usd_estimado,
             estado, error_mensaje)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (drive_id, nombre, PROMPT_VERSION, MODEL_ID,
         json_text, tok_in, tok_out, costo, estado, error_msg),
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Google Drive helpers
# ---------------------------------------------------------------------------

def download_doc(service, file_id: str) -> Optional[str]:
    """Descarga un Google Doc como texto plano. Devuelve None si falla."""
    req = service.files().export_media(fileId=file_id, mimeType="text/plain")
    content = req.execute()
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return content or None


def list_folder_docs(service, folder_id: str) -> list[dict]:
    """Devuelve todos los Google Docs dentro de una carpeta (no recursivo)."""
    q = (
        f"'{folder_id}' in parents"
        " and mimeType='application/vnd.google-apps.document'"
        " and trashed=false"
    )
    result = service.files().list(
        q=q,
        fields="files(id, name, mimeType)",
        pageSize=50,
    ).execute()
    return result.get("files", [])

# ---------------------------------------------------------------------------
# Llamada a la API de Anthropic con retry
# ---------------------------------------------------------------------------

def _call_api(client, content: str):
    """Llama a Anthropic con el prompt completo. Reintenta hasta MAX_RETRIES veces."""
    prompt = PROMPT_EXTRACCION + content
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS_OUTPUT,
                temperature=TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
    raise last_exc

# ---------------------------------------------------------------------------
# Extracción de un único documento
# ---------------------------------------------------------------------------

def extract_one(
    service,
    client,
    drive_id: str,
    nombre: str,
    conn: sqlite3.Connection,
) -> dict:
    """
    Descarga, extrae y guarda un documento.
    Devuelve un dict con: estado, tokens_input, tokens_output, costo_usd, parsed.
    """
    # 1. Descargar contenido
    try:
        content = download_doc(service, drive_id)
    except Exception as exc:
        _save_row(conn, drive_id, nombre, None, None, None, None, "error_api", str(exc))
        return {"estado": "error_api", "error": str(exc)}

    if not content or len(content.strip()) < 100:
        _save_row(conn, drive_id, nombre, None, None, None, None,
                  "documento_vacio", "Contenido vacío o demasiado corto")
        return {"estado": "documento_vacio"}

    # 2. Llamar a la API
    try:
        response = _call_api(client, content)
    except Exception as exc:
        _save_row(conn, drive_id, nombre, None, None, None, None, "error_api", str(exc))
        return {"estado": "error_api", "error": str(exc)}

    raw_text  = response.content[0].text
    tok_in    = response.usage.input_tokens
    tok_out   = response.usage.output_tokens
    costo     = tok_in * PRICE_INPUT_PER_TOKEN + tok_out * PRICE_OUTPUT_PER_TOKEN

    # 3. Limpiar wrapper markdown si el modelo lo agregó (```json ... ```)
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = clean_text.split("\n", 1)[-1]   # quita la línea ```json
        if clean_text.endswith("```"):
            clean_text = clean_text[: clean_text.rfind("```")].rstrip()

    # 4. Validar JSON
    try:
        parsed = json.loads(clean_text)
        raw_text = clean_text          # guardamos el texto limpio
        estado, error_msg = "exitoso", None
    except json.JSONDecodeError as exc:
        parsed, estado, error_msg = None, "json_invalido", str(exc)

    _save_row(conn, drive_id, nombre, raw_text, tok_in, tok_out, costo, estado, error_msg)

    return {
        "estado":        estado,
        "tokens_input":  tok_in,
        "tokens_output": tok_out,
        "costo_usd":     costo,
        "parsed":        parsed,
    }

# ---------------------------------------------------------------------------
# Estimación de tamaño (sin llamar a la API)
# ---------------------------------------------------------------------------

def estimate_size(service, drive_id: str, nombre: str) -> dict:
    """Descarga el doc y devuelve caracteres y tokens aprox (4 chars ≈ 1 token)."""
    try:
        content = download_doc(service, drive_id)
        if not content:
            return {"nombre": nombre, "chars": 0, "tokens_aprox": 0, "error": "vacío"}
        chars = len(content)
        prompt_tokens = len(PROMPT_EXTRACCION) // 4
        doc_tokens    = chars // 4
        tok_in        = prompt_tokens + doc_tokens
        tok_out_est   = 3000          # estimación conservadora de output
        costo_est     = tok_in * PRICE_INPUT_PER_TOKEN + tok_out_est * PRICE_OUTPUT_PER_TOKEN
        return {
            "nombre":      nombre,
            "chars":       chars,
            "tokens_aprox": tok_in,
            "costo_est_usd": costo_est,
        }
    except Exception as exc:
        return {"nombre": nombre, "chars": 0, "tokens_aprox": 0, "error": str(exc)}

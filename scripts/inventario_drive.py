"""
Inventario de Google Drive — Gradus App, sección 5.1 de las specs.

Identifica y lista documentos candidatos a ser investigaciones de estudiantes.
NO extrae contenido todavía — solo cataloga cuáles documentos hay que procesar.

Criterios de inclusión (en orden de prioridad):
  1. Keyword en nombre de archivo: variantes de "investigaci", "aplicaci" al exterior
  2. Ubicación en carpeta de "investigación" o "estudiantes"
  3. Keyword en cuerpo del documento (búsqueda fullText via Drive API)
  4. Nombre de persona en el título (patrón 1-4 palabras capitalizadas)
  5. Validación LLM para casos ambiguos del criterio 4

Exclusiones: facturas, contratos, plantillas, templates, docs < 200 palabras.

Salida: data/inventario.json
"""

from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.extraction.drive_client import get_drive_service

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

INVENTARIO_PATH = Path(__file__).parent.parent / "data" / "inventario.json"

# Variantes de "investigación" / "aplicación al exterior"
KEYWORDS_NOMBRE = ["investigaci", "aplicacion", "aplicación", "universidades"]

# Palabras clave para cuerpos de documentos (fullText Drive API)
KEYWORDS_CUERPO = ["investigacion", "investigación"]

# Patrones de exclusión en el nombre del archivo
PATRONES_EXCLUSION = [
    "factura", "contrato firmado", "plantilla", "template",
    "borrador vacío", "borrador vacio", "borrador vací",
    "recibo", "pago", "invoice",
]

# Tokens que descalifican un nombre como "nombre de persona"
TOKENS_ADMIN = {
    "borrador", "draft", "v1", "v2", "v3", "checklist", "plantilla",
    "template", "final", "copia", "backup", "resumen", "guia", "guía",
    "formato", "modelo", "instructivo", "proceso", "lista", "doc",
    "formulario", "reporte", "informe",
}

# Nombres y apellidos latinoamericanos comunes
NOMBRES_LATAM = {
    # Nombres femeninos
    "maria", "andrea", "luciana", "valentina", "sofia", "camila", "isabella",
    "daniela", "gabriela", "laura", "natalia", "alejandra", "fernanda",
    "carolina", "ana", "paula", "sara", "jessica", "paola", "claudia",
    "diana", "monica", "patricia", "angelica", "veronica", "isabela",
    "victoria", "mariana", "juliana", "catalina", "lina", "manuela",
    "salome", "lorena", "adriana", "silvana", "tatiana", "viviana",
    # Nombres masculinos
    "jose", "juan", "alejandro", "santiago", "mateo", "emilio", "rafael",
    "antonio", "roberto", "francisco", "jorge", "alberto", "ricardo",
    "manuel", "gabriel", "diego", "miguel", "andres", "federico",
    "nicolas", "ignacio", "sebastian", "carlos", "luis", "daniel",
    "david", "pablo", "ivan", "mario", "sergio", "oscar", "rodrigo",
    "javier", "hernan", "julian", "fabian", "hernan", "mauricio",
    # Apellidos comunes latinoamericanos
    "gonzalez", "rodriguez", "martinez", "garcia", "lopez", "hernandez",
    "perez", "silva", "torres", "flores", "rivera", "jimenez", "romero",
    "moreno", "sanchez", "ruiz", "castro", "ramos", "vargas", "gomez",
    "gutierrez", "diaz", "ramirez", "cruz", "herrera", "medina",
    "suarez", "reyes", "ortega", "morales", "delgado", "vega", "molina",
    "mendoza", "munoz", "rojas", "navarro", "guerrero", "blanco",
    "castillo", "lara", "aguilar", "cabrera", "espinosa", "campos",
    "contreras", "acosta", "miranda", "alvarado", "arias", "mejia",
    "cardona", "pena", "ospina", "montoya", "londono", "velasquez",
    "posada", "salazar", "botero", "castano", "giraldo", "zapata",
    "arango", "restrepo", "ochoa", "cano", "valencia", "hurtado",
    "zuluaga", "patino", "jaramillo", "orozco", "fuentes", "trujillo",
    "paredes", "figueroa", "serrano", "sandoval", "montes", "bermudez",
    "camacho", "calderon", "pacheco", "lozano", "escobar", "franco",
    "sierra", "gallego", "velez", "caruso", "valcarcel", "coquelet",
    "cataño", "catano",
}

# Palabras de carpetas que indican contenido de estudiantes
KEYWORDS_CARPETA_ESTUDIANTE = [
    "investigaci", "estudiante", "aplicacion", "universidades",
]

# Límite de llamadas LLM para no exceder costos/cuotas
MAX_LLM_CALLS = 40

MIME_GDOC = "application/vnd.google-apps.document"
MIME_FOLDER = "application/vnd.google-apps.folder"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def norm(s: str) -> str:
    """Quita acentos y convierte a minúsculas: 'Martínez' → 'martinez'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def contiene_keyword(texto: str, keywords: List[str]) -> bool:
    t = norm(texto)
    return any(k in t for k in keywords)


def es_excluido(nombre: str) -> Tuple[bool, str]:
    """Retorna (True, motivo) si el archivo debe descartarse por nombre."""
    n = norm(nombre)
    for patron in PATRONES_EXCLUSION:
        if patron in n:
            return True, f"nombre contiene '{patron}'"
    return False, ""


def es_nombre_persona(nombre: str) -> Tuple[bool, bool]:
    """
    Evalúa si el nombre del archivo parece ser un nombre de estudiante.

    Retorna (es_candidato, es_ambiguo):
      - es_candidato: True si cumple el patrón
      - es_ambiguo: True si necesita validación LLM (nombre de 1 sola palabra)
    """
    stem = Path(nombre).stem.strip()
    # Limpiar guiones y comas comunes en nombres de carpetas/archivos
    stem = stem.replace(" - ", " ").replace(",", " ").strip()
    tokens = [t for t in stem.split() if t]

    # Entre 1 y 4 palabras
    if not (1 <= len(tokens) <= 4):
        return False, False

    # Todas las palabras deben ser alfabéticas (incluye acentos/tildes)
    if not all(t.replace("-", "").replace("'", "").isalpha() for t in tokens):
        return False, False

    # Al menos la primera palabra debe empezar con mayúscula
    if not tokens[0][0].isupper():
        return False, False

    # No debe contener tokens administrativos
    tokens_norm = {norm(t) for t in tokens}
    if tokens_norm & TOKENS_ADMIN:
        return False, False

    # Al menos una palabra en la lista de nombres conocidos
    if tokens_norm & NOMBRES_LATAM:
        ambiguo = len(tokens) == 1
        return True, ambiguo

    # Dos o más palabras capitalizadas sin tokens admin → candidato (ambiguo)
    if len(tokens) >= 2 and all(t[0].isupper() for t in tokens):
        return True, True  # podría ser un nombre extranjero → LLM valida

    return False, False


# ---------------------------------------------------------------------------
# Acceso a Drive con caché
# ---------------------------------------------------------------------------

_folder_cache: Dict[str, str] = {}


def get_folder_nombre(service, folder_id: str) -> str:
    """Obtiene el nombre de una carpeta con caché local."""
    if folder_id in _folder_cache:
        return _folder_cache[folder_id]
    try:
        result = service.files().get(fileId=folder_id, fields="name").execute()
        nombre = result.get("name", folder_id)
    except Exception:
        nombre = folder_id
    _folder_cache[folder_id] = nombre
    return nombre


def get_ruta(service, parents: List[str]) -> str:
    """Construye la ruta del archivo (carpeta inmediata padre)."""
    if not parents:
        return "Mi Drive (raíz)"
    return get_folder_nombre(service, parents[0])


def listar_paginado(service, query: str,
                    fields: str = "files(id,name,mimeType,modifiedTime,parents)") -> List[dict]:
    """Lista todos los archivos que coinciden con la query, manejando paginación."""
    archivos = []
    page_token = None
    while True:
        params: dict = {
            "pageSize": 1000,
            "fields": f"nextPageToken, {fields}",
            "q": query,
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            params["pageToken"] = page_token
        result = service.files().list(**params).execute()
        archivos.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return archivos


def build_entry(service, archivo: dict, motivo: str, confianza: str) -> dict:
    return {
        "drive_id": archivo["id"],
        "nombre": archivo.get("name", ""),
        "mime_type": archivo.get("mimeType", ""),
        "fecha_modificacion": archivo.get("modifiedTime", "")[:10],
        "ruta": get_ruta(service, archivo.get("parents", [])),
        "motivo_inclusion": motivo,
        "confianza": confianza,
    }


# ---------------------------------------------------------------------------
# Validación LLM
# ---------------------------------------------------------------------------

def validar_con_llm(service, anthropic_client, archivo: dict,
                    llm_calls_count: List[int]) -> Tuple[Optional[bool], str]:
    """
    Lee las primeras 1000 palabras del documento y pregunta al LLM.
    Retorna (es_investigacion, motivo).
    """
    if not anthropic_client:
        return None, "sin_clave_api"

    if llm_calls_count[0] >= MAX_LLM_CALLS:
        return None, "limite_llm_alcanzado"

    if archivo.get("mimeType") != MIME_GDOC:
        return None, "no_es_gdoc"

    try:
        request = service.files().export_media(fileId=archivo["id"], mimeType="text/plain")
        contenido = request.execute()
        if isinstance(contenido, bytes):
            contenido = contenido.decode("utf-8", errors="replace")

        palabras = contenido.split()
        if len(palabras) < 200:
            return False, f"menos_de_200_palabras ({len(palabras)} palabras)"

        primeras_1000 = " ".join(palabras[:1000])
        llm_calls_count[0] += 1

        respuesta = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f"Archivo: '{archivo.get('name', '')}'\n\n"
                    f"Primeras palabras:\n{primeras_1000}\n\n"
                    "¿Este documento es una investigación de universidades o guía "
                    "de admisión para un estudiante específico? "
                    "Responde SOLO: SI o NO, y una razón brevísima (máximo 15 palabras)."
                ),
            }],
        )

        texto = respuesta.content[0].text.strip()
        es_si = norm(texto[:3]).startswith("si") or norm(texto[:2]) == "si"
        return es_si, texto

    except Exception as e:
        return None, f"error: {str(e)[:60]}"


# ---------------------------------------------------------------------------
# Script principal
# ---------------------------------------------------------------------------

def run_inventario(service, anthropic_client=None) -> Tuple[List[dict], dict]:
    """
    Ejecuta el inventario completo.
    Retorna (lista_inventario, estadisticas).
    """
    candidatos: Dict[str, dict] = {}  # drive_id → entry
    excluidos: List[dict] = []
    llm_calls_count = [0]  # lista mutable para pasar por referencia

    stats = {
        "keyword_nombre": 0,
        "keyword_cuerpo": 0,
        "carpeta_investigacion": 0,
        "nombre_persona_claro": 0,
        "nombre_persona_llm": 0,
        "nombre_persona_sin_validar": 0,
        "excluidos_nombre": 0,
        "excluidos_llm": 0,
        "excluidos_pocas_palabras": 0,
    }

    # ── PASO 1: Keyword en nombre de archivo ─────────────────────────────

    print("\n── Paso 1/5: Buscando por palabra clave en nombre del archivo...")
    # Construir query Drive para múltiples keywords
    keyword_queries = " or ".join(
        f"name contains '{kw}'" for kw in ["investigaci", "aplicacion"]
    )
    archivos_kw_nombre = listar_paginado(
        service,
        f"({keyword_queries}) and trashed = false",
    )
    print(f"   → {len(archivos_kw_nombre)} archivos encontrados")

    for a in archivos_kw_nombre:
        nombre = a.get("name", "")
        excluido, motivo_exc = es_excluido(nombre)
        if excluido:
            excluidos.append({"nombre": nombre, "motivo": motivo_exc, "paso": 1})
            stats["excluidos_nombre"] += 1
            continue
        if a["id"] not in candidatos:
            candidatos[a["id"]] = build_entry(service, a, "match_palabra_clave_nombre", "alta")
            stats["keyword_nombre"] += 1

    # ── PASO 2: Carpetas de investigación / estudiantes ───────────────────

    print("\n── Paso 2/5: Buscando en carpetas de investigación y estudiantes...")
    carpeta_queries = " or ".join(
        f"name contains '{kw}'" for kw in ["investigaci", "estudiante", "aplicacion"]
    )
    carpetas_inv = listar_paginado(
        service,
        f"mimeType = '{MIME_FOLDER}' and ({carpeta_queries}) and trashed = false",
        fields="files(id,name)",
    )
    print(f"   → {len(carpetas_inv)} carpetas encontradas: "
          f"{', '.join(repr(c['name']) for c in carpetas_inv[:8])}"
          f"{'...' if len(carpetas_inv) > 8 else ''}")

    for carpeta in carpetas_inv:
        docs_en_carpeta = listar_paginado(
            service,
            f"'{carpeta['id']}' in parents and "
            f"mimeType = '{MIME_GDOC}' and trashed = false",
        )
        for a in docs_en_carpeta:
            if a["id"] in candidatos:
                continue
            nombre = a.get("name", "")
            excluido, motivo_exc = es_excluido(nombre)
            if excluido:
                excluidos.append({"nombre": nombre, "motivo": motivo_exc, "paso": 2})
                stats["excluidos_nombre"] += 1
                continue
            # Si además tiene keyword en nombre, subir confianza
            if contiene_keyword(nombre, KEYWORDS_NOMBRE):
                motivo, conf = "match_palabra_clave_nombre", "alta"
                stats["keyword_nombre"] += 1
            else:
                motivo, conf = "carpeta_investigacion", "media"
                stats["carpeta_investigacion"] += 1
            candidatos[a["id"]] = build_entry(service, a, motivo, conf)

    # ── PASO 3: Keyword en cuerpo del documento (fullText Drive API) ──────

    print("\n── Paso 3/5: Buscando por palabra clave en cuerpo de documentos...")
    archivos_cuerpo = listar_paginado(
        service,
        f"fullText contains 'investigacion' and "
        f"mimeType = '{MIME_GDOC}' and trashed = false",
    )
    print(f"   → {len(archivos_cuerpo)} documentos encontrados")
    nuevos_cuerpo = 0
    for a in archivos_cuerpo:
        if a["id"] in candidatos:
            continue
        nombre = a.get("name", "")
        excluido, motivo_exc = es_excluido(nombre)
        if excluido:
            excluidos.append({"nombre": nombre, "motivo": motivo_exc, "paso": 3})
            stats["excluidos_nombre"] += 1
            continue
        candidatos[a["id"]] = build_entry(service, a, "match_palabra_clave_cuerpo", "media")
        stats["keyword_cuerpo"] += 1
        nuevos_cuerpo += 1
    print(f"   → {nuevos_cuerpo} nuevos (no capturados en pasos anteriores)")

    # ── PASO 4: Patrón de nombre de persona en todos los Google Docs ──────

    print("\n── Paso 4/5: Analizando nombres de archivos (patrón de estudiante)...")
    todos_gdocs = listar_paginado(
        service,
        f"mimeType = '{MIME_GDOC}' and trashed = false",
    )
    print(f"   → {len(todos_gdocs)} Google Docs en total en el Drive")

    candidatos_ambiguos: List[dict] = []

    for a in todos_gdocs:
        if a["id"] in candidatos:
            continue

        nombre = a.get("name", "")
        excluido, motivo_exc = es_excluido(nombre)
        if excluido:
            # Solo registramos si además pasaba el filtro de nombre
            es_persona, _ = es_nombre_persona(nombre)
            if es_persona:
                excluidos.append({"nombre": nombre, "motivo": motivo_exc, "paso": 4})
                stats["excluidos_nombre"] += 1
            continue

        es_persona, es_ambiguo = es_nombre_persona(nombre)
        if not es_persona:
            continue

        if es_ambiguo:
            candidatos_ambiguos.append(a)
        else:
            candidatos[a["id"]] = build_entry(service, a, "nombre_persona", "media")
            stats["nombre_persona_claro"] += 1

    print(f"   → {stats['nombre_persona_claro']} incluidos por nombre claro de persona")
    print(f"   → {len(candidatos_ambiguos)} candidatos ambiguos para validación LLM")

    # ── PASO 5: Validación LLM para candidatos ambiguos ───────────────────

    n_ambiguos = len(candidatos_ambiguos)

    if n_ambiguos == 0:
        print("\n── Paso 5/5: Sin candidatos ambiguos — validación LLM omitida.")

    elif not anthropic_client:
        print(f"\n── Paso 5/5: Validación LLM — OMITIDA")
        print(f"   ANTHROPIC_API_KEY no disponible.")
        print(f"   → {n_ambiguos} archivos incluidos con confianza 'baja' para revisión manual.")
        for a in candidatos_ambiguos:
            candidatos[a["id"]] = build_entry(service, a, "nombre_persona", "baja")
            stats["nombre_persona_sin_validar"] += 1

    else:
        a_validar = candidatos_ambiguos[:MAX_LLM_CALLS]
        a_sin_validar = candidatos_ambiguos[MAX_LLM_CALLS:]

        print(f"\n── Paso 5/5: Validando {len(a_validar)} candidatos con LLM "
              f"(Claude Haiku)...")

        for i, a in enumerate(a_validar, 1):
            nombre = a.get("name", "")
            print(f"   [{i:2d}/{len(a_validar)}] '{nombre}' ... ", end="", flush=True)
            es_inv, motivo_llm = validar_con_llm(
                service, anthropic_client, a, llm_calls_count
            )

            if es_inv is True:
                print(f"✓  → investigación ({motivo_llm[:50]})")
                candidatos[a["id"]] = build_entry(
                    service, a, "nombre_persona_validado_llm", "media"
                )
                stats["nombre_persona_llm"] += 1
            elif es_inv is False:
                print(f"✗  → excluido ({motivo_llm[:50]})")
                excluidos.append({"nombre": nombre, "motivo": f"LLM: {motivo_llm[:80]}", "paso": 5})
                if "pocas_palabras" in motivo_llm or "200" in motivo_llm:
                    stats["excluidos_pocas_palabras"] += 1
                else:
                    stats["excluidos_llm"] += 1
            else:
                print(f"⚠  → no validado ({motivo_llm}), incluido con confianza baja")
                candidatos[a["id"]] = build_entry(service, a, "nombre_persona", "baja")
                stats["nombre_persona_sin_validar"] += 1

            time.sleep(0.3)  # respetar rate limit de la API

        if a_sin_validar:
            print(f"   ⚠  {len(a_sin_validar)} archivos exceden el límite de LLM "
                  f"({MAX_LLM_CALLS}) — incluidos con confianza 'baja'")
            for a in a_sin_validar:
                candidatos[a["id"]] = build_entry(service, a, "nombre_persona", "baja")
                stats["nombre_persona_sin_validar"] += 1

    stats["total_incluidos"] = len(candidatos)
    stats["total_excluidos"] = len(excluidos)
    stats["llm_calls"] = llm_calls_count[0]

    return list(candidatos.values()), excluidos, stats


# ---------------------------------------------------------------------------
# Salida y resumen
# ---------------------------------------------------------------------------

def imprimir_resumen(inventario: List[dict], excluidos: List[dict], stats: dict) -> None:
    total = stats["total_incluidos"]

    print("\n" + "=" * 65)
    print("  RESUMEN DEL INVENTARIO — Gradus App")
    print("=" * 65)
    print(f"\n  Total de documentos en inventario : {total}")
    print()
    print("  Por motivo de inclusión:")
    print(f"    Palabra clave en nombre          : {stats['keyword_nombre']}")
    print(f"    En carpeta investigación/estud.  : {stats['carpeta_investigacion']}")
    print(f"    Palabra clave en cuerpo          : {stats['keyword_cuerpo']}")
    print(f"    Nombre de persona (claro)        : {stats['nombre_persona_claro']}")
    print(f"    Nombre de persona (LLM validado) : {stats['nombre_persona_llm']}")
    print(f"    Nombre de persona (sin validar)  : {stats['nombre_persona_sin_validar']}")
    print()
    print(f"  Documentos excluidos              : {stats['total_excluidos']}")
    print(f"    Por nombre (factura/plantilla)   : {stats['excluidos_nombre']}")
    print(f"    Por LLM (no es investigación)    : {stats['excluidos_llm']}")
    print(f"    Por menos de 200 palabras        : {stats['excluidos_pocas_palabras']}")
    if stats["llm_calls"]:
        print(f"  Llamadas LLM utilizadas           : {stats['llm_calls']}")
    print()

    # Por confianza
    alta = sum(1 for d in inventario if d["confianza"] == "alta")
    media = sum(1 for d in inventario if d["confianza"] == "media")
    baja = sum(1 for d in inventario if d["confianza"] == "baja")
    print(f"  Por confianza: alta={alta}  media={media}  baja={baja}")
    print()

    # Primeros 30
    limite = min(30, total)
    print(f"  Primeros {limite} documentos del inventario:")
    print(f"  {'#':<4} {'Confianza':<8} {'Motivo':<35} {'Nombre'}")
    print("  " + "-" * 85)
    for i, doc in enumerate(inventario[:limite], 1):
        motivo_corto = doc["motivo_inclusion"].replace("match_", "").replace("_", " ")
        nombre_corto = doc["nombre"][:45] + ("…" if len(doc["nombre"]) > 45 else "")
        print(f"  {i:<4} {doc['confianza']:<8} {motivo_corto:<35} {nombre_corto}")

    if total > 30:
        print(f"\n  ... y {total - 30} documentos más.")
        print(f"  Ver el inventario completo en: data/inventario.json")

    print()
    if inventario and any(d["confianza"] == "baja" for d in inventario):
        n_baja = sum(1 for d in inventario if d["confianza"] == "baja")
        print(f"  ⚠  Hay {n_baja} documento(s) con confianza 'baja' que conviene")
        print(f"     revisar manualmente en inventario.json antes de extraer.")
    print("=" * 65)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Genera el inventario de documentos de Drive")
    parser.add_argument(
        "--con-llm", action="store_true",
        help="Activar validación LLM para nombres ambiguos (requiere ANTHROPIC_API_KEY)"
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  INVENTARIO DE GOOGLE DRIVE — Gradus App")
    print("=" * 65)
    print()

    # Conectar a Drive
    print("Conectando con Google Drive...")
    service = get_drive_service()
    print("✓ Conectado")

    # Conectar a Anthropic si hay clave disponible y se solicitó
    anthropic_client = None
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if args.con_llm:
        if api_key:
            import anthropic
            anthropic_client = anthropic.Anthropic(api_key=api_key)
            print(f"✓ Validación LLM habilitada (límite: {MAX_LLM_CALLS} llamadas)")
        else:
            print("⚠  --con-llm solicitado pero ANTHROPIC_API_KEY no está definida.")
            print("   Continúa sin LLM. Los candidatos ambiguos quedarán con confianza baja.")
    else:
        print("ℹ  Validación LLM desactivada. "
              "Usar --con-llm para activarla (requiere ANTHROPIC_API_KEY).")

    print()

    # Ejecutar inventario
    t0 = time.time()
    inventario, excluidos, stats = run_inventario(service, anthropic_client)
    elapsed = time.time() - t0

    # Guardar JSON
    INVENTARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INVENTARIO_PATH, "w", encoding="utf-8") as f:
        json.dump(inventario, f, ensure_ascii=False, indent=2)

    print(f"\n✓ inventario.json guardado en: {INVENTARIO_PATH}")
    print(f"  Tiempo total: {elapsed:.1f} segundos")

    # Imprimir resumen
    imprimir_resumen(inventario, excluidos, stats)


if __name__ == "__main__":
    main()

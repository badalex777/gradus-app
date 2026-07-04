"""
fix_lucas.py — Extrae el documento de Lucas Mejía partiéndolo en 3 partes.
Combina los 3 JSON resultantes en un único registro en extracciones_crudas.
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import anthropic
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ─── Constantes ──────────────────────────────────────────────────────────────
LUCAS_DRIVE_ID = "1UW5pQoyBi2PlmGy7AnrUBWx8j7m_0XXU73xgnbCLy9Y"
LUCAS_NOMBRE   = "Lucas Mejía"
DB_PATH        = PROJECT_ROOT / "data" / "catalogo.db"
TOKEN_PATH     = PROJECT_ROOT / "token.json"
MODEL_ID       = "claude-sonnet-4-6"
MAX_TOKENS     = 16000
TEMPERATURE    = 0
PROMPT_VERSION = "v1_piloto"

PRICE_IN  = 3.0  / 1_000_000
PRICE_OUT = 15.0 / 1_000_000

# ─── Prompt (idéntico al de doc_parser.py) ───────────────────────────────────
from app.extraction.doc_parser import PROMPT_EXTRACCION

# ─── Google Drive ─────────────────────────────────────────────────────────────
def build_drive_service():
    creds = Credentials.from_authorized_user_file(
        str(TOKEN_PATH),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)

def download_doc(service, file_id: str) -> str:
    req = service.files().export_media(fileId=file_id, mimeType="text/plain")
    content = req.execute()
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return content or ""

# ─── API call ─────────────────────────────────────────────────────────────────
def call_api(client, part_text: str, part_label: str):
    note = (
        f"\n\n[NOTA: Este es el {part_label} del documento, "
        "que fue dividido por su longitud. Extraé solo lo que aparece en esta parte. "
        "Incluí todas las universidades que veas, aunque no estén completas.]\n\n"
    )
    prompt = PROMPT_EXTRACCION + note + part_text
    print(f"  → Enviando {part_label} ({len(part_text):,} chars)...")
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp
        except Exception as exc:
            print(f"    Error intento {attempt+1}: {exc}")
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError(f"Falló {part_label} después de 3 intentos")

def parse_response(resp):
    """Limpia markdown y parsea JSON. Devuelve (parsed, clean_text)."""
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].rstrip()
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as e:
        return None, raw

# ─── Combinación de 3 JSONs ───────────────────────────────────────────────────
def merge_parts(parts: list[dict]) -> dict:
    """Une los 3 resultados en un único objeto JSON."""
    merged = {
        "estudiante": None,
        "universidades": [],
        "metadata_extraccion": {
            "secciones_no_extraidas": [],
            "ambiguedades": [],
        },
    }

    for i, p in enumerate(parts):
        if p is None:
            continue
        # Tomar datos del estudiante del primer parte que los tenga
        if merged["estudiante"] is None and p.get("estudiante"):
            merged["estudiante"] = p["estudiante"]

        # Acumular universidades, evitar duplicados por nombre
        nombres_existentes = {u["nombre"] for u in merged["universidades"]}
        for uni in p.get("universidades", []):
            if uni["nombre"] not in nombres_existentes:
                merged["universidades"].append(uni)
                nombres_existentes.add(uni["nombre"])
            else:
                # Misma universidad en otra parte — fusionar programas
                target = next(u for u in merged["universidades"] if u["nombre"] == uni["nombre"])
                prog_nombres = {pr["nombre"] for pr in target.get("programas", [])}
                for prog in uni.get("programas", []):
                    if prog["nombre"] not in prog_nombres:
                        target.setdefault("programas", []).append(prog)
                        prog_nombres.add(prog["nombre"])

        # Metadatos
        meta = p.get("metadata_extraccion", {})
        merged["metadata_extraccion"]["secciones_no_extraidas"].extend(
            meta.get("secciones_no_extraidas", [])
        )
        merged["metadata_extraccion"]["ambiguedades"].extend(
            meta.get("ambiguedades", [])
        )

    return merged

# ─── SQLite ───────────────────────────────────────────────────────────────────
def save_to_db(
    drive_id, nombre, json_text, tok_in, tok_out, costo, estado, error_msg
):
    conn = sqlite3.connect(DB_PATH)
    # Borrar filas previas fallidas de Lucas
    conn.execute(
        "DELETE FROM extracciones_crudas WHERE documento_drive_id = ? AND estado != 'exitoso'",
        (drive_id,),
    )
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
    conn.close()

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        print("❌ ANTHROPIC_API_KEY no configurada")
        sys.exit(1)

    print("Conectando a Google Drive...")
    service = build_drive_service()

    print("Descargando documento de Lucas Mejía...")
    content = download_doc(service, LUCAS_DRIVE_ID)
    lines   = content.splitlines()
    total   = len(lines)
    print(f"  Total: {total} líneas, {len(content):,} chars")

    # Dividir en 3 partes iguales
    cut1 = total // 3
    cut2 = 2 * total // 3
    parts_text = [
        "\n".join(lines[:cut1]),
        "\n".join(lines[cut1:cut2]),
        "\n".join(lines[cut2:]),
    ]
    labels = ["Parte 1 de 3", "Parte 2 de 3", "Parte 3 de 3"]

    print(f"Dividido en: {len(parts_text[0]):,} | {len(parts_text[1]):,} | {len(parts_text[2]):,} chars")

    client = anthropic.Anthropic(api_key=api_key)

    results   = []  # (parsed_dict, raw_text, tok_in, tok_out)
    total_in  = 0
    total_out = 0

    for i, (part, label) in enumerate(zip(parts_text, labels)):
        print(f"\n[{label}]")
        resp = call_api(client, part, label)
        parsed, clean = parse_response(resp)
        tok_in  = resp.usage.input_tokens
        tok_out = resp.usage.output_tokens
        total_in  += tok_in
        total_out += tok_out
        status = "✅ JSON válido" if parsed is not None else "❌ JSON inválido"
        print(f"  {status} | in={tok_in:,} out={tok_out:,}")
        results.append((parsed, clean, tok_in, tok_out))

    # Verificar que al menos algunas partes son válidas
    parsed_parts = [r[0] for r in results]
    n_ok = sum(1 for p in parsed_parts if p is not None)
    print(f"\n{n_ok}/3 partes con JSON válido")

    if n_ok == 0:
        costo = total_in * PRICE_IN + total_out * PRICE_OUT
        save_to_db(LUCAS_DRIVE_ID, LUCAS_NOMBRE, None, total_in, total_out,
                   costo, "json_invalido", "Las 3 partes fallaron")
        print("❌ Todas las partes fallaron. Guardado como json_invalido.")
        sys.exit(1)

    # Combinar
    merged = merge_parts(parsed_parts)
    merged_text = json.dumps(merged, ensure_ascii=False, indent=2)
    costo = total_in * PRICE_IN + total_out * PRICE_OUT

    # Guardar
    save_to_db(LUCAS_DRIVE_ID, LUCAS_NOMBRE, merged_text,
               total_in, total_out, costo, "exitoso", None)

    n_unis = len(merged.get("universidades", []))
    print(f"\n✅ Lucas Mejía guardado como EXITOSO")
    print(f"   Universidades extraídas: {n_unis}")
    print(f"   Tokens  entrada: {total_in:,}")
    print(f"   Tokens  salida:  {total_out:,}")
    print(f"   Costo estimado:  ${costo:.4f} USD")

if __name__ == "__main__":
    main()

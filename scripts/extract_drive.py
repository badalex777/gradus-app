"""
extract_drive.py — Corrida completa de extracción para Gradus.

Lee data/inventario.json, saltea los documentos ya exitosos en extracciones_crudas,
muestra un resumen con costo estimado, pide confirmación, y procesa uno a uno.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import anthropic
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.extraction.doc_parser import create_table, get_connection, extract_one

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

INVENTARIO_PATH = PROJECT_ROOT / "data" / "inventario.json"
TOKEN_PATH      = PROJECT_ROOT / "token.json"
SCOPES          = ["https://www.googleapis.com/auth/drive.readonly"]

FALLBACK_COSTO_POR_DOC = 0.18   # USD — si no hay pilotos en la DB

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_drive_service():
    creds = Credentials.from_authorized_user_file(
        str(TOKEN_PATH), scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def get_already_done(conn) -> set[str]:
    """Devuelve el conjunto de drive_ids ya exitosos en la DB."""
    rows = conn.execute(
        "SELECT documento_drive_id FROM extracciones_crudas WHERE estado = 'exitoso'"
    ).fetchall()
    return {row[0] for row in rows}


def estimate_avg_cost(conn) -> float:
    """
    Promedio de costo de los pilotos exitosos, excluyendo Lucas Mejía porque
    ese se procesó con un método especial de 3 partes y no es representativo.
    """
    rows = conn.execute(
        """
        SELECT costo_usd_estimado
        FROM extracciones_crudas
        WHERE estado = 'exitoso'
          AND documento_nombre != 'Lucas Mejía'
          AND costo_usd_estimado IS NOT NULL
        """
    ).fetchall()
    if not rows:
        return FALLBACK_COSTO_POR_DOC
    return sum(r[0] for r in rows) / len(rows)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Verificar API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        print("❌  ANTHROPIC_API_KEY no configurada. Revisá el archivo .env")
        sys.exit(1)

    # 2. Cargar inventario
    if not INVENTARIO_PATH.exists():
        print(f"❌  No se encontró {INVENTARIO_PATH}")
        sys.exit(1)

    with open(INVENTARIO_PATH, encoding="utf-8") as f:
        inventario = json.load(f)

    # 3. Conectar a la DB y asegurar la tabla
    conn = get_connection()
    create_table(conn)

    # 4. Determinar qué saltear y qué procesar
    ya_exitosos_ids = get_already_done(conn)

    a_saltear  = [doc for doc in inventario if doc["drive_id"] in ya_exitosos_ids]
    a_procesar = [doc for doc in inventario if doc["drive_id"] not in ya_exitosos_ids]

    # 5. Estimación de costo
    costo_promedio  = estimate_avg_cost(conn)
    costo_estimado  = costo_promedio * len(a_procesar)

    # 6. Resumen previo
    print()
    print("=" * 62)
    print("  GRADUS — Corrida completa de extracción")
    print("=" * 62)
    print(f"  Documentos en inventario:      {len(inventario):>4}")
    print(f"  Ya exitosos (se saltean):      {len(a_saltear):>4}")
    print(f"  A procesar ahora:              {len(a_procesar):>4}")
    print(f"  Costo promedio por doc:        ${costo_promedio:.4f} USD")
    print(f"  Costo total estimado:          ${costo_estimado:.2f} USD")
    print("=" * 62)

    if not a_procesar:
        print("\n✅  Todos los documentos ya están procesados. Nada que hacer.")
        conn.close()
        return

    print("\n  Documentos a saltear (ya exitosos):")
    for doc in a_saltear:
        print(f"    ✓  {doc['nombre']}")

    print(f"\n  Primeros documentos a procesar:")
    for doc in a_procesar[:5]:
        print(f"    →  {doc['nombre']}")
    if len(a_procesar) > 5:
        print(f"    ... y {len(a_procesar) - 5} más")

    print()
    print("  Escribí 'yes' para confirmar y arrancar (cualquier otra cosa cancela):")
    try:
        respuesta = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        respuesta = ""

    if respuesta != "yes":
        print("\nCancelado. No se llamó a la API.")
        conn.close()
        sys.exit(0)

    # 7. Conectar a Drive y Anthropic
    print("\nConectando a Google Drive...")
    service = build_drive_service()
    client  = anthropic.Anthropic(api_key=api_key)
    print("Conexiones listas. Arrancando extracción...\n")

    # 8. Procesar uno a uno
    exitosos: list[str] = []
    fallidos: list[dict] = []
    costo_real = 0.0
    total = len(a_procesar)

    for i, doc in enumerate(a_procesar, 1):
        drive_id = doc["drive_id"]
        nombre   = doc["nombre"]
        print(f"[{i}/{total}]  {nombre}")

        result = extract_one(service, client, drive_id, nombre, conn)
        estado = result.get("estado")

        if estado == "exitoso":
            costo = result.get("costo_usd", 0.0)
            costo_real += costo
            exitosos.append(nombre)
            print(
                f"  ✅  exitoso | "
                f"in={result.get('tokens_input', 0):,}  "
                f"out={result.get('tokens_output', 0):,}  "
                f"${costo:.4f}"
            )
        else:
            error = result.get("error", "")
            fallidos.append({"nombre": nombre, "estado": estado, "error": error})
            print(f"  ❌  {estado}  —  {error[:80]}")

    # 9. Resumen final
    print()
    print("=" * 62)
    print("  RESUMEN FINAL")
    print("=" * 62)
    print(f"  Procesados:    {total}")
    print(f"  ✅  Exitosos:  {len(exitosos)}")
    print(f"  ❌  Fallidos:  {len(fallidos)}")
    print(f"  Costo real:    ${costo_real:.4f} USD")

    if fallidos:
        print("\n  Documentos que fallaron:")
        for f in fallidos:
            print(f"    ❌  {f['nombre']}  ({f['estado']})")
            if f["error"]:
                print(f"        {f['error'][:100]}")

    print("=" * 62)
    conn.close()


if __name__ == "__main__":
    main()

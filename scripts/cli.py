"""Punto de entrada del comando `gradus` en la terminal."""

import sys
from scripts.init_db import init_db


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: gradus <comando>")
        print("Comandos disponibles:")
        print("  init   — Crea la base de datos con el esquema completo y los datos semilla")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init_db()
    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)

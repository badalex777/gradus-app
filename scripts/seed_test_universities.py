"""
Inserta universidades mínimas de prueba y vincula las reglas de excepción
que tenían centro_especifico a su universidad_id real.

Se puede correr varias veces sin problema (INSERT OR IGNORE + UPDATE solo si NULL).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "catalogo.db"


def seed_test_universities(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ── 1. Universidades de prueba ─────────────────────────────────────────

    # University of Manchester — necesaria para vincular la excepción INTO Manchester
    cur.execute("""
        INSERT OR IGNORE INTO universidades
            (nombre, pais, ciudad, ranking_grupo, publica_privada, fuente_inicial)
        VALUES
            ('University of Manchester', 'UK', 'Manchester',
             'Russell Group', 'pública', 'seed_prueba')
    """)

    # University of Alabama at Birmingham — ejemplo de universidad vía Shorelight USA
    cur.execute("""
        INSERT OR IGNORE INTO universidades
            (nombre, pais, ciudad, publica_privada, fuente_inicial)
        VALUES
            ('University of Alabama at Birmingham', 'USA', 'Birmingham',
             'pública', 'seed_prueba')
    """)

    # ── 2. Vincular reglas de centro_especifico a universidad_id ──────────
    # La excepción "INTO Manchester" se cargó con centro_especifico y universidad_id=NULL.
    # Ahora que University of Manchester existe, la vinculamos por su ID.
    cur.execute("""
        UPDATE reglas_elegibilidad
        SET universidad_id = (
            SELECT id FROM universidades
            WHERE nombre = 'University of Manchester' AND pais = 'UK'
        )
        WHERE centro_especifico = 'INTO Manchester'
          AND universidad_id IS NULL
    """)

    n_vinculadas = cur.rowcount
    conn.commit()

    # Verificar
    cur.execute("SELECT COUNT(*) FROM universidades WHERE fuente_inicial='seed_prueba'")
    n_unis = cur.fetchone()[0]

    cur.execute("""
        SELECT r.id, r.centro_especifico, r.universidad_id, u.nombre
        FROM reglas_elegibilidad r
        LEFT JOIN universidades u ON u.id = r.universidad_id
        WHERE r.centro_especifico = 'INTO Manchester'
    """)
    row = cur.fetchone()

    print(f"✓ Universidades de prueba insertadas: {n_unis}")
    if row:
        print(f"✓ Regla INTO Manchester vinculada → universidad_id={row[2]} ({row[3]})")
    else:
        print("⚠ No se encontró la regla INTO Manchester")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        seed_test_universities(conn)
    finally:
        conn.close()

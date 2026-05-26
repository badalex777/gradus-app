"""
Test completo del motor de elegibilidad — cubre los casos de las secciones
4.6.bis y 7.1 de las specs.

Casos:
  1. Doble nacionalidad colombiana/estadounidense, residencia Colombia,
     Shorelight USA → bloqueado (el pasaporte USA gana sobre el colombiano).
  2. Pasaporte USA, residencia USA, INTO Manchester UK
     → permitido + comisión (la excepción específica de Manchester gana
       sobre la regla general INTO UK).
  3. Colombiano sin pasaporte USA, residencia Colombia, Shorelight USA
     → permitido + comisión (default permisivo, sin reglas que apliquen).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Agrega la raíz del proyecto al path para poder importar el servicio
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.eligibility import evaluar_elegibilidad, ElegibilidadResultado
from scripts.seed_test_universities import seed_test_universities

DB_PATH = Path(__file__).parent.parent / "data" / "catalogo.db"


# ---------------------------------------------------------------------------
# Helpers de consulta
# ---------------------------------------------------------------------------

def get_provider_id(cur: sqlite3.Cursor, nombre: str) -> int:
    cur.execute("SELECT id FROM pathway_providers WHERE nombre = ?", (nombre,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Provider no encontrado: '{nombre}'")
    return row[0]


def get_universidad(cur: sqlite3.Cursor, nombre: str, pais: str) -> tuple:
    """Devuelve (id, pais) de la universidad."""
    cur.execute(
        "SELECT id, pais FROM universidades WHERE nombre = ? AND pais = ?",
        (nombre, pais)
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Universidad no encontrada: '{nombre}' en '{pais}'")
    return row[0], row[1]


# ---------------------------------------------------------------------------
# Definición de los casos de prueba
# ---------------------------------------------------------------------------

CASOS = [
    {
        "numero": 1,
        "descripcion": (
            "Doble nacionalidad colombiana/estadounidense, residencia Colombia, "
            "vía Shorelight → USA"
        ),
        "contexto": (
            "Shorelight bloquea totalmente a quienes tienen pasaporte USA. "
            "Aunque el estudiante también sea colombiano, la restricción aplica igual. "
            "La doble nacionalidad NO evade la restricción."
        ),
        "nacionalidades": ["Colombia", "USA"],
        "residencia": "Colombia",
        "provider_nombre": "Shorelight",
        "universidad_nombre": "University of Alabama at Birmingham",
        "universidad_pais": "USA",
        "esperado_aplica": False,
        "esperado_comision": False,
        "esperada_identidad_restrictiva": "USA",
    },
    {
        "numero": 2,
        "descripcion": (
            "Pasaporte USA, residencia USA, INTO → University of Manchester, UK"
        ),
        "contexto": (
            "INTO tiene una regla general UK que dice 'aplica pero sin comisión'. "
            "Sin embargo, Manchester tiene una excepción específica que sí permite comisión. "
            "La excepción (Nivel 1) gana sobre la regla general (Nivel 2)."
        ),
        "nacionalidades": ["USA"],
        "residencia": "USA",
        "provider_nombre": "INTO",
        "universidad_nombre": "University of Manchester",
        "universidad_pais": "UK",
        "esperado_aplica": True,
        "esperado_comision": True,
        "esperada_identidad_restrictiva": "USA",
    },
    {
        "numero": 3,
        "descripcion": (
            "Solo pasaporte colombiano, residencia Colombia, "
            "vía Shorelight → USA"
        ),
        "contexto": (
            "Las reglas de Shorelight solo bloquean a quienes tienen pasaporte USA. "
            "Un colombiano sin ningún vínculo con USA no tiene restricciones: "
            "aplica el default permisivo."
        ),
        "nacionalidades": ["Colombia"],
        "residencia": "Colombia",
        "provider_nombre": "Shorelight",
        "universidad_nombre": "University of Alabama at Birmingham",
        "universidad_pais": "USA",
        "esperado_aplica": True,
        "esperado_comision": True,
        "esperada_identidad_restrictiva": None,  # default, sin restricción
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests() -> bool:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Preparar datos de prueba (idempotente)
    print("Preparando datos de prueba...")
    seed_test_universities(conn)
    print()

    print("=" * 65)
    print("  PRUEBAS DEL MOTOR DE ELEGIBILIDAD — Gradus App")
    print("=" * 65)

    todos_ok = True

    for caso in CASOS:
        print(f"\n── Caso {caso['numero']}: {caso['descripcion']}")
        print(f"   Contexto: {caso['contexto']}")

        # Obtener IDs de la BD
        provider_id = get_provider_id(cur, caso["provider_nombre"])
        universidad_id, pais_destino = get_universidad(
            cur, caso["universidad_nombre"], caso["universidad_pais"]
        )

        # Ejecutar el motor
        resultado: ElegibilidadResultado = evaluar_elegibilidad(
            conn=conn,
            nacionalidades=caso["nacionalidades"],
            residencia=caso["residencia"],
            universidad_id=universidad_id,
            pais_destino=pais_destino,
            provider_id=provider_id,
        )

        # Verificar
        aplica_ok = resultado.puede_aplicar == caso["esperado_aplica"]
        comision_ok = resultado.recibe_comision == caso["esperado_comision"]
        caso_ok = aplica_ok and comision_ok
        todos_ok = todos_ok and caso_ok

        # Mostrar resultado
        simbolo_aplica = "✓" if aplica_ok else "✗"
        simbolo_comision = "✓" if comision_ok else "✗"

        print(f"\n   Estudiante: nac={caso['nacionalidades']}, residencia={caso['residencia']}")
        print(f"   Destino:    {caso['universidad_nombre']} ({pais_destino}) vía {caso['provider_nombre']}")
        print()
        print(f"   puede_aplicar    : {'SÍ' if resultado.puede_aplicar else 'NO'}  {simbolo_aplica}")
        print(f"   recibe_comision  : {'SÍ' if resultado.recibe_comision else 'NO'}  {simbolo_comision}")
        print(f"   nivel aplicado   : {resultado.nivel_especificidad}")
        print(f"   identidad que disparó la restricción: "
              f"{resultado.identidad_que_dispara or 'ninguna (default)'}")
        print(f"   mensaje para UI  : {resultado.regla_aplicada}")

        # Desglose por identidad — lo que la UI usaría para el "expandir detalle"
        print(f"\n   Desglose por identidad evaluada:")
        for det in resultado.detalle_por_identidad:
            marca = " ← RESTRICCIÓN" if det.es_la_mas_restrictiva else ""
            aplica_str = "SÍ aplica" if det.puede_aplicar else "NO aplica"
            comision_str = "con comisión" if det.recibe_comision else "sin comisión"
            print(f"     · '{det.identidad}': {aplica_str}, {comision_str}"
                  f" [{det.nivel_especificidad}]{marca}")

        print(f"\n   → {'✅ CORRECTO' if caso_ok else '❌ INCORRECTO'}")

        if not aplica_ok:
            esperado = "SÍ" if caso["esperado_aplica"] else "NO"
            print(f"     ERROR: puede_aplicar debería ser {esperado}")
        if not comision_ok:
            esperado = "SÍ" if caso["esperado_comision"] else "NO"
            print(f"     ERROR: recibe_comision debería ser {esperado}")

    print("\n" + "=" * 65)
    if todos_ok:
        print("  RESULTADO GLOBAL: ✅ TODAS LAS PRUEBAS PASARON")
    else:
        print("  RESULTADO GLOBAL: ❌ HAY PRUEBAS FALLIDAS")
    print("=" * 65)

    conn.close()
    return todos_ok


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)

"""
Script de prueba — verifica los dos casos del criterio de éxito Fase 1:

  Caso 1: Pasaporte USA → INTO Manchester (UK)  →  puede_aplicar=SÍ, recibe_comision=SÍ
  Caso 2: Pasaporte USA → INTO Liverpool (UK)   →  puede_aplicar=SÍ, recibe_comision=NO
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "catalogo.db"


def buscar_regla(cur, provider_id: int, centro: Optional[str],
                 nacionalidad: str, pais_destino: str):
    """
    Devuelve la regla más específica para la combinación dada.
    Niveles de especificidad (de mayor a menor):
      Nivel 1 — regla con centro_especifico igual al solicitado
      Nivel 2 — regla general del provider en ese país (centro_especifico IS NULL)
      Nivel 3 — regla global del provider sin importar destino
    """

    # Nivel 1: regla específica por centro
    if centro:
        cur.execute("""
            SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion
            FROM reglas_elegibilidad
            WHERE pathway_provider_id = ?
              AND centro_especifico = ?
              AND nacionalidad_o_residencia = ?
              AND pais_destino = ?
        """, (provider_id, centro, nacionalidad, pais_destino))
        row = cur.fetchone()
        if row:
            return row, "nivel_1_centro_especifico"

    # Nivel 2: regla general del provider en ese país
    cur.execute("""
        SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion
        FROM reglas_elegibilidad
        WHERE pathway_provider_id = ?
          AND centro_especifico IS NULL
          AND universidad_id IS NULL
          AND nacionalidad_o_residencia = ?
          AND pais_destino = ?
    """, (provider_id, nacionalidad, pais_destino))
    row = cur.fetchone()
    if row:
        return row, "nivel_2_general_pais"

    # Nivel 3: regla global del provider (sin importar destino)
    cur.execute("""
        SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion
        FROM reglas_elegibilidad
        WHERE pathway_provider_id = ?
          AND centro_especifico IS NULL
          AND universidad_id IS NULL
          AND nacionalidad_o_residencia = ?
          AND pais_destino IS NULL
    """, (provider_id, nacionalidad))
    row = cur.fetchone()
    if row:
        return row, "nivel_3_global_provider"

    return None, "sin_regla"


def evaluar(cur, provider_nombre: str, centro: str | None,
            nacionalidades: list[str], pais_destino: str) -> dict:
    """
    Evalúa elegibilidad para todas las nacionalidades del estudiante
    y aplica la regla más restrictiva.
    """
    cur.execute("SELECT id FROM pathway_providers WHERE nombre = ?", (provider_nombre,))
    prov = cur.fetchone()
    if not prov:
        raise ValueError(f"Provider no encontrado: {provider_nombre}")
    provider_id = prov[0]

    resultados = []
    for nac in nacionalidades:
        regla, nivel = buscar_regla(cur, provider_id, centro, nac, pais_destino)
        if regla:
            resultados.append({
                "nacionalidad": nac,
                "puede_aplicar": bool(regla[0]),
                "recibe_comision": bool(regla[1]),
                "notas": regla[2],
                "nivel": nivel,
            })

    if not resultados:
        return {
            "puede_aplicar": True,
            "recibe_comision": True,
            "regla": "default (sin reglas conocidas)",
            "nacionalidad_restrictiva": None,
        }

    # La regla más restrictiva manda:
    # NO aplica (2) > SÍ aplica sin comisión (1) > SÍ aplica con comisión (0)
    def nivel_restriccion(r):
        if not r["puede_aplicar"]:
            return 2
        if not r["recibe_comision"]:
            return 1
        return 0

    mas_restrictivo = max(resultados, key=nivel_restriccion)

    return {
        "puede_aplicar": mas_restrictivo["puede_aplicar"],
        "recibe_comision": mas_restrictivo["recibe_comision"],
        "regla": mas_restrictivo["notas"],
        "nivel_especificidad": mas_restrictivo["nivel"],
        "nacionalidad_restrictiva": mas_restrictivo["nacionalidad"],
    }


def run_tests():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=" * 60)
    print("  PRUEBA DE ELEGIBILIDAD — Gradus App  ")
    print("=" * 60)

    casos = [
        {
            "descripcion": "Estudiante con pasaporte USA → INTO Manchester (UK)",
            "provider": "INTO",
            "centro": "INTO Manchester",
            "nacionalidades": ["USA"],
            "pais_destino": "UK",
            "esperado_aplica": True,
            "esperado_comision": True,
        },
        {
            "descripcion": "Estudiante con pasaporte USA → INTO Liverpool (UK)",
            "provider": "INTO",
            "centro": "INTO Liverpool",
            "nacionalidades": ["USA"],
            "pais_destino": "UK",
            "esperado_aplica": True,
            "esperado_comision": False,
        },
    ]

    todos_ok = True
    for i, caso in enumerate(casos, 1):
        resultado = evaluar(
            cur,
            provider_nombre=caso["provider"],
            centro=caso["centro"],
            nacionalidades=caso["nacionalidades"],
            pais_destino=caso["pais_destino"],
        )

        aplica_ok = resultado["puede_aplicar"] == caso["esperado_aplica"]
        comision_ok = resultado["recibe_comision"] == caso["esperado_comision"]
        caso_ok = aplica_ok and comision_ok
        todos_ok = todos_ok and caso_ok

        print(f"\nCaso {i}: {caso['descripcion']}")
        print(f"  puede_aplicar    : {'SÍ' if resultado['puede_aplicar'] else 'NO'}  "
              f"{'✓' if aplica_ok else '✗ (esperado: SÍ)' if caso['esperado_aplica'] else '✗ (esperado: NO)'}")
        print(f"  recibe_comision  : {'SÍ' if resultado['recibe_comision'] else 'NO'}  "
              f"{'✓' if comision_ok else '✗ (esperado: SÍ)' if caso['esperado_comision'] else '✗ (esperado: NO)'}")
        print(f"  regla aplicada   : {resultado.get('nivel_especificidad', 'default')}")
        print(f"  nota             : {resultado['regla']}")
        print(f"  resultado final  : {'✅ CORRECTO' if caso_ok else '❌ INCORRECTO'}")

    print("\n" + "=" * 60)
    print(f"  RESULTADO GLOBAL: {'✅ TODAS LAS PRUEBAS PASARON' if todos_ok else '❌ HAY PRUEBAS FALLIDAS'}")
    print("=" * 60)

    conn.close()
    return todos_ok


if __name__ == "__main__":
    run_tests()

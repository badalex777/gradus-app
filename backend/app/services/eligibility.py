"""
Motor de elegibilidad de Gradus.

Implementa la lógica de la sección 4.6.bis de las specs:
  - Se incluyen TODAS las nacionalidades del estudiante + su residencia.
  - Se busca la regla más específica en 3 niveles.
  - Gana la regla más restrictiva entre todas las identidades evaluadas.

Regla fundamental:
  Si un estudiante tiene pasaporte estadounidense, las restricciones
  aplican siempre, sin importar las demás nacionalidades.
  Tener doble (o triple) nacionalidad NO permite evadir una restricción.
  La regla más restrictiva manda.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class ElegibilidadResultado:
    puede_aplicar: bool
    recibe_comision: bool
    regla_aplicada: str           # descripción de la regla que se aplicó
    nivel_especificidad: str      # "nivel_1", "nivel_2", "nivel_3" o "default"
    identidad_que_dispara: Optional[str]  # qué nacionalidad/residencia disparó la regla


# ---------------------------------------------------------------------------
# Búsqueda de reglas — 3 niveles de especificidad
# ---------------------------------------------------------------------------

def _fila_a_dict(row: tuple) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {
        "puede_aplicar": bool(row[0]),
        "recibe_comision": bool(row[1]),
        "notas": row[2] or "",
        "es_excepcion": bool(row[3]),
        "id": row[4],
    }


def _buscar_nivel1(cur: sqlite3.Cursor,
                   provider_id: int,
                   universidad_id: int,
                   identidad: str,
                   pais_destino: str) -> Optional[Dict[str, Any]]:
    """Nivel 1: regla específica para esta universidad (universidad_id coincide)."""
    cur.execute("""
        SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion, id
        FROM reglas_elegibilidad
        WHERE pathway_provider_id = ?
          AND universidad_id = ?
          AND nacionalidad_o_residencia = ?
          AND (pais_destino = ? OR pais_destino IS NULL)
        ORDER BY
            CASE WHEN pais_destino IS NOT NULL THEN 0 ELSE 1 END
        LIMIT 1
    """, (provider_id, universidad_id, identidad, pais_destino))
    return _fila_a_dict(cur.fetchone())


def _buscar_nivel2(cur: sqlite3.Cursor,
                   provider_id: int,
                   identidad: str,
                   pais_destino: str) -> Optional[Dict[str, Any]]:
    """Nivel 2: regla general del provider para ese país (sin universidad específica)."""
    cur.execute("""
        SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion, id
        FROM reglas_elegibilidad
        WHERE pathway_provider_id = ?
          AND universidad_id IS NULL
          AND centro_especifico IS NULL
          AND nacionalidad_o_residencia = ?
          AND pais_destino = ?
        LIMIT 1
    """, (provider_id, identidad, pais_destino))
    return _fila_a_dict(cur.fetchone())


def _buscar_nivel3(cur: sqlite3.Cursor,
                   provider_id: int,
                   identidad: str) -> Optional[Dict[str, Any]]:
    """Nivel 3: regla global del provider sin importar país de destino."""
    cur.execute("""
        SELECT puede_aplicar, gradus_recibe_comision, notas, es_excepcion, id
        FROM reglas_elegibilidad
        WHERE pathway_provider_id = ?
          AND universidad_id IS NULL
          AND centro_especifico IS NULL
          AND nacionalidad_o_residencia = ?
          AND pais_destino IS NULL
        LIMIT 1
    """, (provider_id, identidad))
    return _fila_a_dict(cur.fetchone())


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def evaluar_elegibilidad(
    conn: sqlite3.Connection,
    nacionalidades: List[str],   # todas las nacionalidades del estudiante
    residencia: str,             # país de residencia actual
    universidad_id: int,         # ID de la universidad destino en la BD
    pais_destino: str,           # país de la universidad destino
    provider_id: int,            # ID del pathway provider a evaluar
) -> ElegibilidadResultado:
    """
    Evalúa si un estudiante puede aplicar a una universidad vía un provider,
    y si Gradus recibe comisión.

    CRÍTICO: no ignorar ninguna identidad. Tener doble nacionalidad NO
    permite evadir restricciones. La regla más restrictiva manda.
    """
    cur = conn.cursor()

    # Incluir TODAS las nacionalidades + residencia (sin duplicados)
    identidades = list(set(nacionalidades + [residencia]))

    resultados_por_identidad = []

    for identidad in identidades:
        regla = None
        nivel = None

        # Nivel 1: excepción específica para esta universidad
        regla = _buscar_nivel1(cur, provider_id, universidad_id, identidad, pais_destino)
        if regla:
            nivel = "nivel_1_universidad_especifica"

        # Nivel 2: regla general del provider para este país
        if not regla:
            regla = _buscar_nivel2(cur, provider_id, identidad, pais_destino)
            if regla:
                nivel = "nivel_2_general_pais"

        # Nivel 3: regla global del provider
        if not regla:
            regla = _buscar_nivel3(cur, provider_id, identidad)
            if regla:
                nivel = "nivel_3_global_provider"

        if regla:
            resultados_por_identidad.append({
                "identidad": identidad,
                "puede_aplicar": regla["puede_aplicar"],
                "recibe_comision": regla["recibe_comision"],
                "notas": regla["notas"],
                "nivel": nivel,
            })

    # Sin ninguna regla → default permisivo (no filtrar de más)
    if not resultados_por_identidad:
        return ElegibilidadResultado(
            puede_aplicar=True,
            recibe_comision=True,
            regla_aplicada="default (sin reglas conocidas para esta combinación)",
            nivel_especificidad="default",
            identidad_que_dispara=None,
        )

    # La regla más restrictiva manda.
    # Orden: NO aplica (2) > SÍ aplica sin comisión (1) > SÍ aplica con comisión (0)
    def _nivel_restriccion(r: dict) -> int:
        if not r["puede_aplicar"]:
            return 2
        if not r["recibe_comision"]:
            return 1
        return 0

    mas_restrictivo = max(resultados_por_identidad, key=_nivel_restriccion)

    return ElegibilidadResultado(
        puede_aplicar=mas_restrictivo["puede_aplicar"],
        recibe_comision=mas_restrictivo["recibe_comision"],
        regla_aplicada=mas_restrictivo["notas"],
        nivel_especificidad=mas_restrictivo["nivel"],
        identidad_que_dispara=mas_restrictivo["identidad"],
    )

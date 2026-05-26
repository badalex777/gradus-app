"""
Motor de elegibilidad de Gradus.

Implementa la lógica de la sección 4.6.bis de las specs:
  - Se incluyen TODAS las nacionalidades del estudiante + su residencia.
  - Se busca la regla más específica en 3 niveles.
  - Gana la regla más restrictiva entre todas las identidades evaluadas.
  - Todas las identidades evaluadas quedan expuestas en detalle_por_identidad
    para que la UI pueda mostrar el desglose completo (sección 7.1).

Regla fundamental:
  Si un estudiante tiene pasaporte estadounidense, las restricciones
  aplican siempre, sin importar las demás nacionalidades.
  Tener doble (o triple) nacionalidad NO permite evadir una restricción.
  La regla más restrictiva manda.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class DetalleIdentidad:
    """Resultado de la evaluación para una sola nacionalidad o residencia."""
    identidad: str                  # 'USA', 'Colombia', etc.
    puede_aplicar: bool
    recibe_comision: bool
    nota_regla: str                 # descripción de la regla encontrada
    nivel_especificidad: str        # 'nivel_1', 'nivel_2', 'nivel_3' o 'default'
    es_la_mas_restrictiva: bool     # True si esta identidad condujo al resultado final


@dataclass
class ElegibilidadResultado:
    """
    Resultado completo de la evaluación de elegibilidad.

    Para la UI:
      - puede_aplicar / recibe_comision: el veredicto final
      - regla_aplicada: mensaje explicativo listo para mostrar al usuario
      - identidad_que_dispara: qué nacionalidad/residencia causó la restricción
      - detalle_por_identidad: desglose por cada identidad evaluada
        → permite mostrar "con pasaporte colombiano habría podido aplicar con
          comisión; la restricción la dispara el pasaporte estadounidense"
    """
    puede_aplicar: bool
    recibe_comision: bool
    regla_aplicada: str
    nivel_especificidad: str
    identidad_que_dispara: Optional[str]
    detalle_por_identidad: List[DetalleIdentidad] = field(default_factory=list)


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
# Generación del mensaje explicativo (sección 7.1 — transparencia obligatoria)
# ---------------------------------------------------------------------------

def _generar_mensaje(
    identidad_restrictiva: str,
    puede_aplicar: bool,
    recibe_comision: bool,
    provider_nombre: str,
    todas_identidades: List[str],
    nota_regla: str,
) -> str:
    """
    Genera el mensaje que la UI mostrará al usuario sobre la regla aplicada.
    Sigue el espíritu de la sección 7.1: transparencia sobre qué se evaluó
    y qué identidad disparó la restricción.
    """
    lista_ids = ", ".join(f"'{i}'" for i in sorted(todas_identidades))
    multiples = len(todas_identidades) > 1

    if not puede_aplicar:
        base = (
            f"Bloqueado por pasaporte/residencia '{identidad_restrictiva}'. "
            f"Se evaluaron todas las identidades del estudiante ({lista_ids}). "
            f"La doble nacionalidad no permite evadir esta restricción de {provider_nombre}."
        )
        return base

    if not recibe_comision:
        base = (
            f"Aplicable vía {provider_nombre} pero sin comisión Gradus "
            f"(restricción activada por '{identidad_restrictiva}'). "
            f"Se evaluaron todas las identidades del estudiante ({lista_ids})."
        )
        return base

    # Permitido con comisión — incluir contexto si hay múltiples identidades
    if multiples:
        return (
            f"{nota_regla} "
            f"(Se evaluaron todas las identidades: {lista_ids}.)"
        )
    return nota_regla


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
    Evalúa si un estudiante puede aplicar a una universidad vía un provider
    y si Gradus recibe comisión.

    CRÍTICO: no ignorar ninguna identidad. Tener doble nacionalidad NO
    permite evadir restricciones. La regla más restrictiva manda.

    Todas las identidades evaluadas quedan expuestas en el resultado
    para que la UI pueda mostrar el desglose completo (sección 7.1).
    """
    cur = conn.cursor()

    # Nombre del provider — necesario para el mensaje explicativo
    cur.execute("SELECT nombre FROM pathway_providers WHERE id = ?", (provider_id,))
    row = cur.fetchone()
    provider_nombre = row[0] if row else str(provider_id)

    # Incluir TODAS las nacionalidades + residencia (sin duplicados)
    identidades = list(set(nacionalidades + [residencia]))

    # Evaluar cada identidad y construir el detalle completo
    detalles: List[Dict[str, Any]] = []

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
            detalles.append({
                "identidad": identidad,
                "puede_aplicar": regla["puede_aplicar"],
                "recibe_comision": regla["recibe_comision"],
                "nota_regla": regla["notas"],
                "nivel": nivel,
                "tiene_regla": True,
            })
        else:
            # Sin regla → default permisivo; se incluye igual para el desglose de la UI
            detalles.append({
                "identidad": identidad,
                "puede_aplicar": True,
                "recibe_comision": True,
                "nota_regla": (
                    f"Sin reglas específicas para '{identidad}' con {provider_nombre} "
                    f"en este destino — se aplica el default permisivo"
                ),
                "nivel": "default",
                "tiene_regla": False,
            })

    # Solo las identidades con regla explícita determinan el resultado final
    con_regla = [d for d in detalles if d["tiene_regla"]]

    # La regla más restrictiva manda.
    # Orden: NO aplica (2) > SÍ aplica sin comisión (1) > SÍ aplica con comisión (0)
    def _nivel_restriccion(d: dict) -> int:
        if not d["puede_aplicar"]:
            return 2
        if not d["recibe_comision"]:
            return 1
        return 0

    if con_regla:
        mas_restrictivo = max(con_regla, key=_nivel_restriccion)
    else:
        mas_restrictivo = None

    # Marcar cuál es la más restrictiva en el detalle completo
    for d in detalles:
        d["es_la_mas_restrictiva"] = (
            mas_restrictivo is not None and d["identidad"] == mas_restrictivo["identidad"]
            and d["tiene_regla"]
        )

    detalle_por_identidad = [
        DetalleIdentidad(
            identidad=d["identidad"],
            puede_aplicar=d["puede_aplicar"],
            recibe_comision=d["recibe_comision"],
            nota_regla=d["nota_regla"],
            nivel_especificidad=d["nivel"],
            es_la_mas_restrictiva=d["es_la_mas_restrictiva"],
        )
        for d in detalles
    ]

    # Sin ninguna regla explícita → default permisivo global
    if mas_restrictivo is None:
        return ElegibilidadResultado(
            puede_aplicar=True,
            recibe_comision=True,
            regla_aplicada=(
                f"Sin reglas conocidas para ninguna de las identidades del estudiante "
                f"con {provider_nombre} en este destino — default permisivo."
            ),
            nivel_especificidad="default",
            identidad_que_dispara=None,
            detalle_por_identidad=detalle_por_identidad,
        )

    mensaje = _generar_mensaje(
        identidad_restrictiva=mas_restrictivo["identidad"],
        puede_aplicar=mas_restrictivo["puede_aplicar"],
        recibe_comision=mas_restrictivo["recibe_comision"],
        provider_nombre=provider_nombre,
        todas_identidades=identidades,
        nota_regla=mas_restrictivo["nota_regla"],
    )

    return ElegibilidadResultado(
        puede_aplicar=mas_restrictivo["puede_aplicar"],
        recibe_comision=mas_restrictivo["recibe_comision"],
        regla_aplicada=mensaje,
        nivel_especificidad=mas_restrictivo["nivel"],
        identidad_que_dispara=mas_restrictivo["identidad"],
        detalle_por_identidad=detalle_por_identidad,
    )

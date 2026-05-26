"""
gradus init — crea la base de datos SQLite con el esquema completo y los datos semilla.
Las tablas se crean en el orden correcto para respetar las llaves foráneas.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "catalogo.db"

# --------------------------------------------------------------------------
# DDL — tablas en orden correcto (respetando dependencias FK)
# --------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 1. pathway_providers (sin dependencias)
CREATE TABLE IF NOT EXISTS pathway_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    tiene_convenio_gradus BOOLEAN DEFAULT 0,
    comision_porcentaje REAL,
    comision_se_descuenta_uk BOOLEAN DEFAULT 0,
    notas_convenio TEXT
);

-- 2. universidades (sin dependencias, necesaria antes de reglas_elegibilidad)
CREATE TABLE IF NOT EXISTS universidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    pais TEXT NOT NULL,
    ciudad TEXT,
    ciudad_tamano TEXT,
    proximidad_ciudad_grande TEXT,
    pagina_oficial TEXT,
    video_intro TEXT,
    ranking_grupo TEXT,
    publica_privada TEXT,
    notas_generales TEXT,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fuente_inicial TEXT,
    UNIQUE(nombre, pais)
);

-- 3. reglas_elegibilidad (depende de pathway_providers y universidades)
CREATE TABLE IF NOT EXISTS reglas_elegibilidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pathway_provider_id INTEGER NOT NULL,
    universidad_id INTEGER,
    centro_especifico TEXT,
    nacionalidad_o_residencia TEXT NOT NULL,
    pais_destino TEXT,
    puede_aplicar BOOLEAN NOT NULL,
    gradus_recibe_comision BOOLEAN NOT NULL,
    es_excepcion BOOLEAN DEFAULT 0,
    notas TEXT,
    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pathway_provider_id) REFERENCES pathway_providers(id),
    FOREIGN KEY (universidad_id) REFERENCES universidades(id)
);

CREATE INDEX IF NOT EXISTS idx_reglas_lookup ON reglas_elegibilidad(
    pathway_provider_id, nacionalidad_o_residencia, pais_destino, universidad_id
);

-- 4. programas (depende de universidades)
CREATE TABLE IF NOT EXISTS programas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universidad_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    nivel TEXT NOT NULL,
    area TEXT,
    areas_relacionadas TEXT,
    duracion_anos REAL,
    idioma_instruccion TEXT,
    modalidad TEXT DEFAULT 'presencial',
    tiene_placement_year BOOLEAN DEFAULT 0,
    tiene_study_abroad BOOLEAN DEFAULT 0,
    entradas_anuales TEXT,
    acceptance_rate REAL,
    notas TEXT,
    FOREIGN KEY (universidad_id) REFERENCES universidades(id)
);

CREATE INDEX IF NOT EXISTS idx_programas_area ON programas(area);
CREATE INDEX IF NOT EXISTS idx_programas_nivel ON programas(nivel);

-- 5. costos_programa (depende de programas)
CREATE TABLE IF NOT EXISTS costos_programa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    tipo_estudiante TEXT NOT NULL,
    costo_anual_local TEXT,
    costo_anual_estimado_usd INTEGER,
    moneda TEXT,
    ano_referencia INTEGER,
    incluye TEXT,
    notas TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id),
    UNIQUE (programa_id, tipo_estudiante, ano_referencia)
);

CREATE INDEX IF NOT EXISTS idx_costos_programa ON costos_programa(programa_id, tipo_estudiante);

-- 6. requisitos_admision (depende de programas)
CREATE TABLE IF NOT EXISTS requisitos_admision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    sistema TEXT NOT NULL,
    requisito TEXT NOT NULL,
    notas TEXT,
    examen_ingles_aceptado TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id)
);

-- 7. requisitos_usa_especificos (depende de programas)
CREATE TABLE IF NOT EXISTS requisitos_usa_especificos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    sat_es_requerido BOOLEAN DEFAULT 0,
    sat_es_opcional BOOLEAN DEFAULT 0,
    sat_recomendado_si_aporta TEXT,
    sat_recomendado_notas TEXT,
    act_aceptado BOOLEAN DEFAULT 1,
    requiere_css_profile BOOLEAN DEFAULT 0,
    css_profile_notas TEXT,
    application_platform TEXT,
    supplemental_essays BOOLEAN DEFAULT 0,
    notas TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id),
    UNIQUE (programa_id)
);

-- 8. pathways (depende de programas y pathway_providers)
CREATE TABLE IF NOT EXISTS pathways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    pathway_provider_id INTEGER NOT NULL,
    nombre_pathway TEXT,
    ubicacion_campus TEXT,
    duracion_anos REAL,
    costo_anual_estimado INTEGER,
    notas TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id),
    FOREIGN KEY (pathway_provider_id) REFERENCES pathway_providers(id)
);

CREATE INDEX IF NOT EXISTS idx_pathways_programa ON pathways(programa_id);

-- 9. convenios_universidad (depende de universidades y pathway_providers)
CREATE TABLE IF NOT EXISTS convenios_universidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universidad_id INTEGER NOT NULL,
    pathway_provider_id INTEGER,
    tipo TEXT NOT NULL,
    comision_porcentaje REAL,
    posibilidad_beca BOOLEAN DEFAULT 0,
    facilita_admision BOOLEAN DEFAULT 0,
    nacionalidades_excluidas TEXT,
    notas TEXT,
    estado TEXT DEFAULT 'activo',
    FOREIGN KEY (universidad_id) REFERENCES universidades(id),
    FOREIGN KEY (pathway_provider_id) REFERENCES pathway_providers(id)
);

CREATE INDEX IF NOT EXISTS idx_convenios_universidad ON convenios_universidad(universidad_id);

-- 10. estudiantes_historicos (depende de universidades)
CREATE TABLE IF NOT EXISTS estudiantes_historicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    nacionalidades TEXT,
    anio_grado INTEGER,
    nivel_buscado TEXT,
    areas_interes TEXT,
    paises_interes TEXT,
    promedio TEXT,
    examenes TEXT,
    presupuesto_anual_usd INTEGER,
    idiomas TEXT,
    documento_origen TEXT,
    fecha_investigacion DATE,
    universidades_recomendadas TEXT,
    universidad_final INTEGER,
    FOREIGN KEY (universidad_final) REFERENCES universidades(id)
);

-- 11. extracciones_log (sin dependencias externas)
CREATE TABLE IF NOT EXISTS extracciones_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_drive_id TEXT NOT NULL,
    documento_nombre TEXT,
    fecha_extraccion DATETIME DEFAULT CURRENT_TIMESTAMP,
    estado TEXT,
    universidades_extraidas INTEGER DEFAULT 0,
    programas_extraidos INTEGER DEFAULT 0,
    conflictos_detectados INTEGER DEFAULT 0,
    notas TEXT
);

-- 12. conflictos_pendientes (sin dependencias externas)
CREATE TABLE IF NOT EXISTS conflictos_pendientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    entidad_id INTEGER,
    campo TEXT,
    valores_propuestos TEXT NOT NULL,
    resolucion TEXT,
    fecha_resolucion DATETIME,
    estado TEXT DEFAULT 'pendiente'
);

-- Índice adicional en universidades
CREATE INDEX IF NOT EXISTS idx_universidades_pais ON universidades(pais);
"""

# --------------------------------------------------------------------------
# SEED — 15 pathway providers
# --------------------------------------------------------------------------

SEED_PROVIDERS_SQL = """
INSERT OR IGNORE INTO pathway_providers (nombre, tiene_convenio_gradus, comision_se_descuenta_uk) VALUES
    ('INTO',          1, 0),
    ('Kaplan',        1, 0),
    ('Study Group',   1, 0),
    ('Shorelight',    1, 0),
    ('OnCampus',      1, 0),
    ('Navitas',       1, 0),
    ('GUS',           1, 0),
    ('Adventus',      1, 0),
    ('QS',            1, 0),
    ('Trotamundos',   1, 0),
    ('Geebe',         1, 0),
    ('Key Education', 1, 0),
    ('IPERC',         1, 0),
    ('SI UK',         1, 0),
    ('Direct',        0, 0);
"""

# --------------------------------------------------------------------------
# SEED — reglas de elegibilidad para nacionalidad/residencia USA
# --------------------------------------------------------------------------

SEED_REGLAS_SQL = """
INSERT OR IGNORE INTO reglas_elegibilidad
    (pathway_provider_id, universidad_id, centro_especifico,
     nacionalidad_o_residencia, pais_destino,
     puede_aplicar, gradus_recibe_comision, es_excepcion, notas)
VALUES
    -- ── INTO ──────────────────────────────────────────────────────────────
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'),
     NULL, NULL, 'USA', 'USA', 1, 0, 0,
     'En USA puede aplicar pero sin comisión por restricción interna'),

    ((SELECT id FROM pathway_providers WHERE nombre='INTO'),
     NULL, NULL, 'USA', 'UK', 1, 0, 0,
     'Regla general UK: aplica pero sin comisión'),

    ((SELECT id FROM pathway_providers WHERE nombre='INTO'),
     NULL, 'INTO Choice Center London', 'USA', 'UK', 1, 1, 1,
     'Excepción: este centro sí permite comisión con pasaporte USA'),

    ((SELECT id FROM pathway_providers WHERE nombre='INTO'),
     NULL, 'INTO London (Salud)', 'USA', 'UK', 1, 1, 1,
     'Excepción: áreas de salud sí permiten comisión con pasaporte USA'),

    ((SELECT id FROM pathway_providers WHERE nombre='INTO'),
     NULL, 'INTO Manchester', 'USA', 'UK', 1, 1, 1,
     'Excepción: Manchester sí permite comisión con pasaporte USA'),

    -- ── Kaplan ────────────────────────────────────────────────────────────
    ((SELECT id FROM pathway_providers WHERE nombre='Kaplan'),
     NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo total en USA: aplicación directa a universidad sin Gradus'),

    ((SELECT id FROM pathway_providers WHERE nombre='Kaplan'),
     NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Sin restricción en UK'),

    -- ── Study Group ───────────────────────────────────────────────────────
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'),
     NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo general en USA salvo excepciones'),

    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'),
     NULL, 'Lipscomb', 'USA', 'USA', 1, 1, 1,
     'Excepción: Lipscomb sí permite con pasaporte USA + comisión'),

    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'),
     NULL, 'James Madison', 'USA', 'USA', 1, 1, 1,
     'Excepción: James Madison sí permite con pasaporte USA + comisión'),

    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'),
     NULL, 'Western Washington', 'USA', 'USA', 1, 1, 1,
     'Excepción: Western Washington sí permite con pasaporte USA + comisión'),

    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'),
     NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Foundation y DE en UK sin restricción'),

    -- ── Shorelight ────────────────────────────────────────────────────────
    ((SELECT id FROM pathway_providers WHERE nombre='Shorelight'),
     NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo total en USA: aplicación directa a universidad sin Gradus'),

    -- ── OnCampus ──────────────────────────────────────────────────────────
    ((SELECT id FROM pathway_providers WHERE nombre='OnCampus'),
     NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Sin restricción en UK');
"""


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_PROVIDERS_SQL)
        conn.executescript(SEED_REGLAS_SQL)
        conn.commit()
        print(f"✓ Base de datos creada en: {db_path}")

        # Verificación rápida
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pathway_providers")
        n_providers = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM reglas_elegibilidad")
        n_reglas = cur.fetchone()[0]
        print(f"✓ Pathway providers cargados: {n_providers}")
        print(f"✓ Reglas de elegibilidad cargadas: {n_reglas}")
        print("✓ gradus init completado exitosamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

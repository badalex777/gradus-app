# Gradus App — Especificaciones Técnicas

**Proyecto:** Aplicación interna de filtrado de universidades para Gradus
**Usuaria principal:** María Aristizábal (fundadora de Gradus)
**Estado:** Specs v2.0 — listo para implementación con Claude Code
**Última actualización:** Mayo 2026

---

## Changelog v2.0 (cambios respecto a v1.0)

Cambios importantes que modifican modelo de datos o lógica de negocio:

- **Costos por tipo de estudiante:** los costos salen de la tabla `programas` y viven en una tabla nueva `costos_programa` con segmentación (internacional, UE, home UK/IRL, in-state USA, out-of-state USA, local). Esto refleja que el mismo programa tiene costos muy distintos según nacionalidad/residencia.
- **Doble nacionalidad NO evade restricciones de providers:** corregida la lógica del motor de elegibilidad. Si un estudiante tiene pasaporte estadounidense, las restricciones aplican siempre, sin importar otras nacionalidades. La regla más restrictiva manda.
- **Requisitos USA específicos:** nueva tabla `requisitos_usa_especificos` con SAT opcional/recomendado, CSS Profile, plataforma de aplicación, ensayos suplementarios.
- **Inventario de Drive incluye documentos con nombres de personas:** además de match por palabra clave, se detectan documentos titulados con nombres latinoamericanos y se valida con LLM cuando hay duda.
- **Diplomas internacionales con autocompletado:** IB, Matura, Abitur, Baccalauréat además de APs.
- **Exportación principal en Word**, no CSV/JSON. Documento de resumen ejecutivo legible, re-exportable según filtros activos.
- **Pathways con fallback inteligente:** si en un país de interés no hay opciones directas, se muestran las vías pathway igual con badge claro, sin filtrarlas.
- **Modalidad presencial:** es preferencia configurable, no política dura.
- **Búsqueda web:** mantiene filtro original (anti-marketing, fuentes oficiales) sin meter umbrales de ranking. María hace la curaduría final de calidad.
- **Búsqueda web subida a "capability principal":** mencionada en visión y arquitectura, no solo en sección 8. Es parte central de cómo el catálogo crece orgánicamente.

---

## 1. Visión y contexto

Gradus es una empresa de college counseling que desde 2019 ha enviado a más de 100 estudiantes de Latinoamérica a universidades en Europa, Estados Unidos, Canadá y otros destinos. María, la fundadora, ha construido un acervo de conocimiento curado sobre universidades, programas, requisitos, pathways y convenios, almacenado principalmente en Google Drive como documentos de investigación organizados por estudiante.

El cuello de botella actual está en la **Fase 1 del proceso**: la investigación inicial donde, dado el perfil de un estudiante (carrera, países, presupuesto, notas, idiomas, nacionalidad), María identifica manualmente qué universidades y programas le sirven. Hoy esto implica revisar documentos de estudiantes anteriores con perfiles similares, consultar el catálogo mental de convenios, y reconstruir las opciones desde cero cada vez.

### Visión de la aplicación

Una herramienta interna que permita a María, partiendo del perfil de un estudiante nuevo, obtener en minutos:

1. **Resultados primarios:** una lista filtrada de universidades y programas del catálogo curado de Gradus que reflejen su conocimiento de los últimos años, con flags claros sobre convenios, comisiones, requisitos especiales y restricciones.

2. **Sugerencias complementarias desde búsqueda web:** universidades y programas adicionales que cumplan con los parámetros del estudiante pero que aún no estén en el catálogo de Gradus. María puede revisar estas sugerencias y, si le parecen pertinentes, validarlas y agregarlas al catálogo desde la misma app — sin tocar código. Esta capacidad es lo que permite que el catálogo de Gradus crezca de manera orgánica con cada investigación nueva.

**No es:** un portal genérico de búsqueda de universidades, ni un meta-buscador de pathway providers, ni una herramienta para estudiantes finales.

**Sí es:** un acelerador de la Fase 1 de investigación que combina el conocimiento histórico curado de Gradus con descubrimiento asistido de nuevas opciones desde la web, donde toda la curaduría final pasa por María.

### Principio rector del catálogo

El catálogo de la aplicación se construye desde los documentos de investigación históricos de Gradus, no desde fuentes externas. Esto es deliberado: lo que diferencia a Gradus es haber estudiado a fondo cada universidad para perfiles concretos. El documento de convenios sirve para enriquecer ese catálogo con flags comerciales, no como fuente primaria.

---

## 2. Principios de diseño

1. **El catálogo refleja el conocimiento curado, no un agregado externo.** Si una universidad no ha sido investigada por Gradus, no está en el catálogo (al menos no como recomendación validada).

2. **Las reglas de negocio son ciudadanas de primera clase.** Convenios, comisiones, exclusividades y restricciones por nacionalidad se modelan estructuralmente, no como notas en texto libre.

3. **Una sola usuaria, sin sistema de cuentas.** María. UX simple, directa, sin overhead de autenticación o permisos.

4. **Soft filters por defecto, hard filters cuando se justifica.** No descartar universidades por falta de datos; mostrarlas marcadas como "verificar".

5. **Catálogo vivo.** María debe poder agregar, editar y enriquecer universidades desde la app, sin tocar código ni base de datos directamente.

6. **Resultados exportables.** La app no genera la presentación final al estudiante, pero sí exporta los datos limpios para que María los lleve a Google Slides.

7. **Honestidad sobre la fuente de datos.** Cada universidad y campo debe poder rastrearse a su origen: documento de estudiante X, convenio Y, ingresada manualmente por María en fecha Z, o complementada con búsqueda web.

---

## 3. Arquitectura técnica

### Stack

- **Backend:** Python 3.11+ con FastAPI
- **Base de datos:** SQLite (un archivo local, ubicado en una carpeta sincronizada con Google Drive para portabilidad y backup automático)
- **Frontend:** React + Vite + TailwindCSS
- **Acceso a Google Drive:** Google Drive API (para fase de extracción) + MCP de Google Drive (para exploración asistida con Claude)
- **Búsqueda web complementaria:** API de búsqueda web (a definir: Tavily, Serper, o similar) — solo cuando se solicite explícitamente desde la app
- **Empaquetado:** la app se ejecuta localmente vía un comando de terminal o un script `.command` que María hace doble click

### Justificación del stack

- **Python + FastAPI** es ideal para el backend porque la fase de extracción de datos (parsear documentos, llamar APIs, procesar texto) es nativamente más fluida en Python, y FastAPI es ligero y moderno para servir el frontend.
- **SQLite** porque es un solo archivo, no requiere servidor, es portable, y maneja sin problema un catálogo de algunos miles de universidades y programas. Si en el futuro hay necesidad de migrar a Postgres, el SQL es transferible.
- **React + Vite + Tailwind** porque es el stack moderno estándar, con la ventaja de que Tailwind permite construir UIs limpias rápido sin diseñador.
- **Local-first** porque es el modo más seguro y simple: nada en la nube, nada que mantener, todo bajo control de María.

### Estructura del proyecto

```
gradus-app/
├── README.md
├── pyproject.toml                 # Dependencias Python
├── package.json                   # Dependencias frontend
├── data/
│   ├── catalogo.db                # Base de datos SQLite (sincronizada vía Drive)
│   └── backups/                   # Backups automáticos timestamped
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entrypoint
│   │   ├── models.py              # SQLAlchemy ORM
│   │   ├── schemas.py             # Pydantic schemas
│   │   ├── routers/               # Endpoints
│   │   ├── services/
│   │   │   ├── filter_engine.py   # Lógica del motor de filtros
│   │   │   ├── eligibility.py     # Reglas de elegibilidad por nacionalidad
│   │   │   └── web_search.py      # Búsqueda web complementaria
│   │   └── extraction/
│   │       ├── drive_client.py    # Conexión a Google Drive
│   │       ├── doc_parser.py      # Parser de documentos de investigación
│   │       └── consolidator.py    # Lógica de consolidación con asistencia
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
├── scripts/
│   ├── extract_drive.py           # Script de extracción inicial
│   ├── import_convenios.py        # Importar documento de convenios
│   └── backup_db.py               # Backup manual
└── docs/
    ├── ARCHITECTURE.md
    ├── EXTRACTION_GUIDE.md
    └── USER_MANUAL.md
```

---

## 4. Esquema de base de datos

Estas son las tablas principales. El esquema completo en SQL está al final de esta sección.

### 4.1 `universidades`

Tabla maestra. Una fila por universidad (no por programa).

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | "University of Manchester" |
| pais | TEXT | "Reino Unido" |
| ciudad | TEXT | "Manchester" |
| ciudad_tamano | TEXT | "pequeña" / "mediana" / "grande" — opcional |
| proximidad_ciudad_grande | TEXT | "Cerca de Londres (1h tren)" — texto libre, opcional |
| pagina_oficial | TEXT | URL |
| video_intro | TEXT | URL del video que María usa con estudiantes |
| ranking_grupo | TEXT | "Russell Group", "G5", "Ivy League", etc. — opcional |
| publica_privada | TEXT | "pública" / "privada" |
| notas_generales | TEXT | Texto libre para observaciones de María |
| fecha_creacion | DATETIME | |
| fecha_actualizacion | DATETIME | |
| fuente_inicial | TEXT | "doc_estudiante:luciana_olano" / "documento_convenios" / "manual" |

### 4.2 `programas`

Una fila por programa de una universidad. Una universidad tiene muchos programas. Los costos no viven aquí — viven en la tabla `costos_programa` (sección 4.2.bis) porque varían según el tipo de estudiante (internacional vs. local vs. UE vs. in-state USA, etc.).

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| universidad_id | INTEGER FK | |
| nombre | TEXT | "Aerospace Engineering (BEng) Hons" |
| nivel | TEXT | "pregrado" / "maestría" / "foundation" / "pathway" / "year_one" |
| area | TEXT | "Ingeniería Aeroespacial" — área de interés normalizada |
| areas_relacionadas | TEXT (JSON) | ["Ingeniería Mecánica", "Aeronáutica"] |
| duracion_anos | REAL | 3.0, 4.0, 4.5 |
| idioma_instruccion | TEXT | "inglés", "español", "inglés/español" |
| modalidad | TEXT | "presencial" (default), "híbrido", "online" |
| tiene_placement_year | BOOLEAN | |
| tiene_study_abroad | BOOLEAN | |
| entradas_anuales | TEXT (JSON) | ["septiembre", "enero"] |
| acceptance_rate | REAL | Para US sobre todo, 0.0 a 1.0 |
| notas | TEXT | |

### 4.2.bis `costos_programa`

Tabla de costos por programa, **una fila por tipo de estudiante**. Esta separación es crítica porque el mismo programa tiene costos muy distintos según la nacionalidad/residencia:

- **Reino Unido e Irlanda:** distinguen "home" (residente UK con 3+ años de impuestos) e "international" (todos los demás, incluyendo internacionales no graduados en UK). Gradus trabaja casi siempre con internacionales → para UK/Irlanda el default es international.
- **España, Italia, Francia, otros países UE:** un estudiante con pasaporte UE paga lo que pagan los europeos (mucho más bajo) solo por tener ese pasaporte, sin importar dónde resida. Esto se llama típicamente "EU rate".
- **Estados Unidos:** distinguen "in-state" (residente del estado de la universidad) y "out-of-state" (todos los demás, incluyendo internacionales). Para estudiantes internacionales, el costo siempre será out-of-state, salvo que el estudiante tenga green card y haya residido en el estado.
- **Otros países:** generalmente un solo costo internacional.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| programa_id | INTEGER FK | |
| tipo_estudiante | TEXT | Ver enum abajo |
| costo_anual_local | TEXT | "£28,000", "€2,500", "$45,000" — texto libre con moneda original |
| costo_anual_estimado_usd | INTEGER | Conversión aproximada para comparación |
| moneda | TEXT | "GBP", "EUR", "USD" |
| ano_referencia | INTEGER | Año al que corresponde el costo (los costos se desactualizan) |
| incluye | TEXT | "Solo matrícula" / "Matrícula + alojamiento" / etc. |
| notas | TEXT | |

**Enum `tipo_estudiante`:**
- `internacional` — default genérico, aplica a casi todos los casos de Gradus
- `home_uk_irl` — residente con 3+ años de impuestos en UK/Irlanda
- `ue` — estudiante con pasaporte UE en universidades europeas (España, Italia, Francia, etc.)
- `in_state_usa` — residente del estado de una universidad pública USA
- `out_of_state_usa` — no residente del estado, incluyendo internacionales en universidades públicas USA
- `local` — categoría genérica para otros países que distinguen local/internacional

**Lógica del motor para mostrar el costo correcto:**

Cuando se muestra un programa al estudiante, el motor evalúa:

1. País del programa + nacionalidades del estudiante → determina qué tipo aplica
2. Busca en `costos_programa` la fila con ese tipo
3. Si no la encuentra, hace fallback a `internacional`
4. Si tampoco existe, marca el programa como "costo no registrado"

Ejemplos:
- Programa en España + estudiante con pasaporte español → busca tipo `ue`, fallback a `internacional`
- Programa en UK + estudiante colombiano sin residencia UK → busca tipo `internacional`
- Programa en University of California + estudiante colombiano → busca `out_of_state_usa`, fallback a `internacional`

### 4.3 `requisitos_admision`

Requisitos de admisión por programa. Modelados estructuralmente para que el motor pueda filtrar por notas y exámenes.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| programa_id | INTEGER FK | |
| sistema | TEXT | "A-levels" / "IB" / "GPA_USA" / "Promedio_LATAM" / "AP" / "SAT" / "ACT" / "Matura" / "Abitur" / "Baccalaureat" |
| requisito | TEXT | "A*AA" / "38 puntos" / "GPA 3.5+" / "1300 SAT" |
| notas | TEXT | "A* en Matemáticas y Física" |
| examen_ingles_aceptado | TEXT (JSON) | ["IELTS 6.5", "TOEFL 90", "Duolingo 120"] — incluye Duolingo |

### 4.3.bis `requisitos_usa_especificos`

Tabla auxiliar para requisitos específicos de universidades en Estados Unidos. Una fila por programa USA.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| programa_id | INTEGER FK | |
| sat_es_requerido | BOOLEAN | true = obligatorio, false = opcional o no aplica |
| sat_es_opcional | BOOLEAN | true = test-optional (estudiante elige si lo aporta) |
| sat_recomendado_si_aporta | TEXT | "1400+", "1500+" — score recomendado cuando es test-optional pero la universidad es selectiva |
| sat_recomendado_notas | TEXT | "Universidad muy selectiva: aunque sea opcional, se recomienda aportar SAT alto" |
| act_aceptado | BOOLEAN | |
| requiere_css_profile | BOOLEAN | true = requiere llenar el CSS Profile (típico de privadas selectivas para ayuda financiera) |
| css_profile_notas | TEXT | Detalles relevantes |
| application_platform | TEXT | "Common App" / "Coalition" / "directa" |
| supplemental_essays | BOOLEAN | true si pide ensayos adicionales |
| notas | TEXT | |

**Sobre el CSS Profile:** es el formulario complementario al FAFSA que requieren muchas universidades privadas selectivas en USA para evaluar ayuda financiera, especialmente para estudiantes internacionales. Modelarlo permite que la app alerte a María cuando una universidad lo requiera, ya que tiene implicaciones para el flujo de aplicación y los plazos.

### 4.4 `pathways`

Opciones de pathway / foundation / year one disponibles para acceder a un programa.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| programa_id | INTEGER FK | (programa al que da acceso) |
| pathway_provider_id | INTEGER FK | |
| nombre_pathway | TEXT | "Foundation Engineering and Physical Sciences" |
| ubicacion_campus | TEXT | "dentro_campus" / "fuera_campus" / "edificio_aparte_acceso_universidad" |
| duracion_anos | REAL | |
| costo_anual_estimado | INTEGER | |
| notas | TEXT | |

### 4.5 `pathway_providers`

Catálogo de los pathway providers (INTO, Kaplan, Navitas, etc.) con sus reglas de elegibilidad.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | "INTO", "Kaplan", "Shorelight", "Study Group", "OnCampus", "Navitas", "GUS", "Adventus", "QS", "Trotamundos", "Geebe", "Key Education", "IPERC", "SI UK", "Direct" |
| tiene_convenio_gradus | BOOLEAN | |
| comision_porcentaje | REAL | Si está en convenio |
| comision_se_descuenta_uk | BOOLEAN | Default: false. En UK, Study Group/INTO/Kaplan toman comisión completa |
| notas_convenio | TEXT | "Pelear comisión 80%" |

### 4.6 `reglas_elegibilidad`

Tabla que modela las restricciones de pasaporte/residencia por provider, con granularidad a nivel de universidad/centro específico cuando aplica. **Ciudadana de primera clase.**

**Modelo conceptual:** las reglas operan por la combinación (provider × país destino × nacionalidad/residencia × universidad o centro específico). El campo `universidad_id` es opcional: cuando es NULL, la regla aplica a todas las universidades del provider en ese país. Cuando tiene valor, es una excepción específica para esa universidad/centro.

**Lógica de resolución:** la regla más específica gana sobre la regla general. Si hay conflicto entre dos reglas igualmente específicas, gana la más reciente por fecha.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| pathway_provider_id | INTEGER FK | |
| universidad_id | INTEGER FK NULLABLE | NULL = aplica a todas las universidades del provider en ese país. Con valor = regla específica para esa universidad/centro. |
| centro_especifico | TEXT NULLABLE | Texto descriptivo cuando el centro no es una universidad en sí (ej. "INTO Choice Center London", "INTO Manchester"). Se usa cuando aún no hay registro de universidad asociado. |
| nacionalidad_o_residencia | TEXT | "USA" |
| pais_destino | TEXT | "USA", "UK", etc. NULL = aplica a todos los destinos del provider |
| puede_aplicar | BOOLEAN | |
| gradus_recibe_comision | BOOLEAN | |
| es_excepcion | BOOLEAN | true cuando esta regla sobrescribe una regla general más amplia |
| notas | TEXT | "Aplicación directa a universidad" |

**Reglas iniciales conocidas (basadas en el documento de pasaporte americano de Gradus):**

*Reglas para nacionalidad/residencia USA:*

| Provider | Universidad/Centro | País destino | Aplica | Comisión | Tipo regla |
|---|---|---|---|---|---|
| INTO | (todos) | USA | SÍ | NO | General |
| INTO | (todos) | UK | SÍ | NO | General UK |
| INTO | Choice Center London | UK | SÍ | SÍ | Excepción |
| INTO | London (áreas Salud) | UK | SÍ | SÍ | Excepción |
| INTO | Manchester | UK | SÍ | SÍ | Excepción |
| Kaplan | (todos) | USA | NO | NO | General |
| Kaplan | (todos) | UK | SÍ | SÍ | General |
| Study Group | (todos) | USA | NO | NO | General |
| Study Group | Lipscomb | USA | SÍ | SÍ | Excepción |
| Study Group | James Madison | USA | SÍ | SÍ | Excepción |
| Study Group | Western Washington | USA | SÍ | SÍ | Excepción |
| Study Group | (todos) | UK | SÍ | SÍ | General UK |
| Shorelight | (todos) | USA | NO | NO | General |
| OnCampus | (todos) | UK | SÍ | SÍ | General |
| (resto) | (todos) | (cualquiera) | SÍ | SÍ | Default |

**Notas operativas:**

- El default para cualquier combinación no listada explícitamente es: aplica = SÍ, comisión = SÍ. Esto evita filtrar de más por reglas inexistentes.
- Solo se modelan reglas para nacionalidad/residencia USA por ahora. El sistema está diseñado para extender a otras nacionalidades sin cambios de esquema, agregando filas a la tabla.
- El sistema NO tiene reglas particulares modeladas para Canadá ni Australia como destino — Gradus aún no tiene experiencia profunda allí. Cuando se gane experiencia, se agregan filas.

### 4.6.bis Lógica de resolución de elegibilidad (referencia para implementación)

**Regla fundamental, crítica para no romper restricciones de providers:**

Si un estudiante tiene pasaporte estadounidense, las restricciones de pasaporte estadounidense aplican **siempre y de manera obligatoria, sin importar qué otra(s) nacionalidad(es) tenga**. Tener doble (o triple) nacionalidad NO permite "elegir" la nacionalidad más conveniente para evadir la restricción. Esto es una regla dura impuesta por los pathway providers (Shorelight, Kaplan, etc.) — no es una preferencia de Gradus, es la realidad operativa.

Implicación: la regla más restrictiva entre todas las nacionalidades del estudiante manda. Si una de las nacionalidades del estudiante bloquea o restringe una vía, esa vía se considera bloqueada o restringida, sin importar las otras nacionalidades que tenga.

Pseudocódigo del motor de elegibilidad:

```python
def evaluar_elegibilidad(estudiante, universidad, provider):
    """
    Retorna: {
        puede_aplicar: bool,
        recibe_comision: bool,
        regla_aplicada: str,
        nacionalidad_que_dispara_restriccion: str | None,
    }
    """
    # CRÍTICO: incluir TODAS las nacionalidades + residencia.
    # No se puede ignorar ninguna para "evadir" restricciones.
    nacionalidades_y_residencia = list(set(
        estudiante.nacionalidades + [estudiante.residencia_actual]
    ))

    pais_destino = universidad.pais
    resultados_por_nacionalidad = []

    for nac in nacionalidades_y_residencia:
        # Buscar la regla más específica que aplique (3 niveles de especificidad)

        # Nivel 1: regla específica para esta universidad/centro
        regla = buscar_regla(
            provider=provider,
            universidad_id=universidad.id,
            nacionalidad=nac,
            pais_destino=pais_destino
        )

        # Nivel 2: regla general del provider en ese país
        if not regla:
            regla = buscar_regla(
                provider=provider,
                universidad_id=None,
                nacionalidad=nac,
                pais_destino=pais_destino
            )

        # Nivel 3: regla del provider sin importar destino
        if not regla:
            regla = buscar_regla(
                provider=provider,
                universidad_id=None,
                nacionalidad=nac,
                pais_destino=None
            )

        if regla:
            resultados_por_nacionalidad.append((nac, regla))

    if not resultados_por_nacionalidad:
        # Sin reglas → default permisivo
        return {
            "puede_aplicar": True,
            "recibe_comision": True,
            "regla_aplicada": "default (sin reglas conocidas)",
            "nacionalidad_que_dispara_restriccion": None,
        }

    # REGLA MÁS RESTRICTIVA MANDA. No la más permisiva.
    # Orden de restricción: NO aplica > SÍ aplica sin comisión > SÍ aplica con comisión

    def nivel_restriccion(regla):
        if not regla.puede_aplicar:
            return 2  # más restrictivo
        if not regla.gradus_recibe_comision:
            return 1  # restrictivo medio
        return 0  # permisivo

    nac_mas_restrictiva, regla_mas_restrictiva = max(
        resultados_por_nacionalidad,
        key=lambda x: nivel_restriccion(x[1])
    )

    return {
        "puede_aplicar": regla_mas_restrictiva.puede_aplicar,
        "recibe_comision": regla_mas_restrictiva.gradus_recibe_comision,
        "regla_aplicada": regla_mas_restrictiva.id,
        "nacionalidad_que_dispara_restriccion": nac_mas_restrictiva,
    }
```

**Caso típico: estudiante con doble nacionalidad colombiana/estadounidense, residiendo en Colombia, considerando Shorelight USA.**
- Como nacionalidad colombiana → permitido + comisión.
- Como nacionalidad estadounidense → **bloqueado** (Shorelight USA bloquea con pasaporte USA).
- **Resultado: bloqueado.** La restricción de la nacionalidad estadounidense manda.
- Mensaje en la UI: "Bloqueado por pasaporte estadounidense del estudiante. La doble nacionalidad no permite evadir esta restricción de Shorelight."

**Caso típico: estudiante con pasaporte estadounidense, residiendo en USA, considerando INTO Manchester UK.**
- La residencia estadounidense activa la regla USA.
- INTO Manchester UK con pasaporte/residencia USA → SÍ aplica + SÍ comisión (excepción específica).
- **Resultado: permitido + comisión.** La excepción manda sobre la regla general porque es más específica (Nivel 1 vs. Nivel 2).

**Caso típico: estudiante colombiano sin pasaporte estadounidense, residiendo en Colombia, considerando Shorelight USA.**
- Solo nacionalidad colombiana, sin residencia USA.
- No hay reglas que restrinjan a colombianos en Shorelight.
- **Resultado: permitido + comisión** (default).

### 4.7 `convenios_universidad`

Una fila por convenio que tiene Gradus con una universidad, vía un provider o directo.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| universidad_id | INTEGER FK | |
| pathway_provider_id | INTEGER FK NULLABLE | NULL si es convenio directo con la universidad |
| tipo | TEXT | "directo" / "vía_pathway" / "study_abroad" / "solo_algunos_masters" |
| comision_porcentaje | REAL | |
| posibilidad_beca | BOOLEAN | |
| facilita_admision | BOOLEAN | |
| nacionalidades_excluidas | TEXT (JSON) | ["USA"] cuando aplica |
| notas | TEXT | "Solo aplica a maestrías de Business" |
| estado | TEXT | "activo" / "en_proceso" / "vencido" |

### 4.8 `estudiantes_historicos`

Cada estudiante para el cual se hizo investigación. Sirve para trazabilidad y para "estudiantes similares".

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | |
| nacionalidades | TEXT (JSON) | ["Colombiana", "Española"] |
| anio_grado | INTEGER | |
| nivel_buscado | TEXT | "pregrado" / "maestría" |
| areas_interes | TEXT (JSON) | ["Ingeniería Aeroespacial"] |
| paises_interes | TEXT (JSON) | ["Reino Unido", "USA", "España", "Países Bajos"] |
| promedio | TEXT | "3.88 W / 3.7 U" |
| examenes | TEXT (JSON) | {"SAT": 1210, "Duolingo": null, ...} |
| presupuesto_anual_usd | INTEGER | |
| idiomas | TEXT (JSON) | |
| documento_origen | TEXT | URL o ID del Google Doc |
| fecha_investigacion | DATE | |
| universidades_recomendadas | TEXT (JSON) | IDs de universidades |
| universidad_final | INTEGER FK NULLABLE | A dónde terminó yendo, si se sabe |

### 4.9 `extracciones_log`

Log de cada extracción de documento, para trazabilidad y reextracción.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| documento_drive_id | TEXT | |
| documento_nombre | TEXT | |
| fecha_extraccion | DATETIME | |
| estado | TEXT | "exitosa" / "parcial" / "con_conflictos" / "fallida" |
| universidades_extraidas | INTEGER | |
| programas_extraidos | INTEGER | |
| conflictos_detectados | INTEGER | |
| notas | TEXT | |

### 4.10 `conflictos_pendientes`

Conflictos de consolidación que María debe resolver.

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| tipo | TEXT | "campo_universidad" / "programa_duplicado" / "requisito_inconsistente" |
| entidad_id | INTEGER | |
| campo | TEXT | "duracion_anos" |
| valores_propuestos | TEXT (JSON) | [{"valor": 3, "fuentes": ["doc1", "doc5"]}, {"valor": 4, "fuentes": ["doc7"]}] |
| resolucion | TEXT NULLABLE | Valor elegido por María |
| fecha_resolucion | DATETIME NULLABLE | |
| estado | TEXT | "pendiente" / "resuelto" / "ignorado" |

---

## 5. Flujo de extracción de Google Drive

Esta es la fase más crítica del proyecto. El objetivo: convertir ~100 Google Docs de investigaciones por estudiante en un catálogo consolidado de universidades.

### 5.1 Inventario inicial

Claude Code, vía MCP de Google Drive, busca todos los documentos del Drive de María que cumplan al menos uno de los siguientes criterios. Los documentos pueden no incluir la palabra "investigación" en el título, así que el inventario es generoso por diseño y depende de María revisar la lista al final.

**Criterios de inclusión:**

1. **Match por palabra clave en nombre o cuerpo:**
   - Contienen "investigación" / "investigacion" / "INVESTIGACIÓN" / "INVESTIGACION" en el nombre del archivo
   - Contienen esas variantes en el cuerpo del documento
   - Están en carpetas con "estudiantes" / "estudiante" / "investigaciones" en el nombre de la carpeta
   - Coinciden con un patrón "NOMBRE - INVESTIGACION" en el título

2. **Match por nombre de persona en el título del documento.** Muchos documentos están nombrados simplemente con el nombre del estudiante (primer nombre, nombre + apellido, dos apellidos, o variaciones). Lógica de detección:
   - Tokenizar el nombre del archivo
   - Si el nombre del archivo es 1 a 4 palabras y todas empiezan con mayúscula y todas son alfabéticas (sin números, sin símbolos comunes de docs como "borrador", "v1", "draft", "checklist", "plantilla", "template")
   - Y al menos una palabra coincide con un nombre o apellido común latinoamericano (lista incorporada en el extractor: María, José, Juan, Andrea, Luciana, Alejandro, González, Rodríguez, Martínez, etc., extensible)
   - O el patrón coincide con "NOMBRE APELLIDO" típico (dos palabras capitalizadas sin tokens administrativos)
   - → se considera candidato a investigación de estudiante.

3. **Validación con LLM cuando hay duda.** Para los candidatos del paso 2, si el nombre del archivo es ambiguo (ej. "Sofia"), Claude Code abre el documento, lee las primeras 1000 palabras, y le pregunta a un LLM: "¿este documento parece ser una investigación universitaria para un estudiante específico, o es otro tipo de documento (factura, plantilla, notas administrativas, etc.)?". Solo se incluyen los confirmados.

4. **Exclusiones automáticas:**
   - Documentos con "factura", "contrato firmado", "plantilla", "template", "borrador vacío" en el título.
   - Documentos vacíos o con menos de 200 palabras de contenido.

**Salida:** `inventario.json` con `[{drive_id, nombre, fecha_modificacion, ruta, motivo_inclusion, confianza}, ...]`. Campo `motivo_inclusion` indica por cuál criterio entró (ej. "match_palabra_clave", "nombre_persona_validado_llm"). María revisa la lista, marca los que hay que excluir, y puede agregar manualmente documentos que no aparecieron pero que sabe que existen.

### 5.2 Extracción por documento

Para cada documento marcado como incluido:

1. **Descarga del contenido** vía Drive API.
2. **Detección de estructura.** El parser intenta identificar las secciones típicas: header del estudiante (nombre, intereses, países, promedio, idiomas, nacionalidad), y bloques por país con universidades.
3. **Extracción asistida con LLM.** Para cada documento, se hace una llamada a Claude con el prompt:

```
Eres un extractor de datos. Dado este documento de investigación universitaria
de Gradus, extrae estructuradamente la información del estudiante y todas las
universidades mencionadas con sus programas, requisitos, pathways, costos y notas.

Devuelve JSON estricto siguiendo este esquema: [esquema completo]

Si un campo no está en el documento, déjalo como null. No inventes información.
Si hay ambigüedad, marca el campo con un objeto {valor: X, confianza: "baja"}.
```

4. **Almacenamiento crudo.** Las extracciones se guardan en una tabla `extracciones_crudas` (no normalizada) antes de consolidar. Esto permite re-consolidar si se mejora la lógica.

### 5.3 Consolidación con asistencia

Después de extraer N documentos, se corre el consolidador:

1. **Agrupación por universidad.** Todas las menciones de "University of Manchester" se agrupan (con fuzzy matching para variaciones tipográficas).
2. **Resolución por mayoría con override.** Para cada campo de la universidad, si todas las menciones coinciden, se usa ese valor. Si difieren, se crea un registro en `conflictos_pendientes`.
3. **Interfaz de resolución.** En la app, una pantalla "Conflictos" muestra cada caso así:

```
University of Manchester — duración_anos
- 3 años (mencionado en 9 documentos: Luciana Olano 2024, Pedro X 2023, ...)
- 4 años (mencionado en 3 documentos: Ana Y 2022, ...)
[Elegir 3] [Elegir 4] [Otro: ___] [Posponer]
```

María va resolviendo los conflictos importantes. Los menores pueden quedar como "tomar el más reciente" automáticamente.

### 5.4 Cruce con convenios

Una vez consolidadas las universidades, se ejecuta `import_convenios.py` que parsea el documento de convenios y, para cada universidad mencionada, le agrega:

- Su pathway provider asociado
- Tipo de convenio (directo / vía pathway / study abroad / solo algunos másters)
- Notas comerciales (comisiones especiales, exclusividades, "en proceso")

Si una universidad aparece en convenios pero no en el catálogo extraído, se marca como "convenio sin investigación previa" y María decide si agregarla manualmente al catálogo.

### 5.5 Reporte de extracción

Al finalizar, se genera un reporte:

```
=== Reporte de Extracción Gradus ===
Documentos procesados: 87 / 87
Universidades únicas identificadas: 234
Universidades completas (>80% campos): 156
Universidades parciales: 78
Conflictos pendientes: 47
Convenios cruzados: 198 / 234 universidades del catálogo

Top 10 universidades con más menciones:
1. University of Manchester (14 documentos)
2. ...
```

---

## 6. Especificación de pantallas

### 6.1 Pantalla principal: "Nuevo estudiante"

Formulario con los siguientes campos, agrupados:

**Identificación**
- Nombre del estudiante
- Año de grado / año de inicio buscado
- Fecha de la investigación

**Nacionalidad y residencia (crítico para reglas de elegibilidad)**
- Nacionalidades (multi-select): Colombiana, Mexicana, Argentina, Española, Italiana, Estadounidense, Otra...
- País de residencia actual
- ⚠️ Si selecciona Estadounidense o residencia USA, la app muestra una alerta inline: "Este estudiante tiene restricciones especiales que se aplican automáticamente. Algunas universidades vía Shorelight (USA) y Kaplan (USA) se bloquean. Vía INTO (USA y UK general) se permite aplicar pero sin comisión. Excepciones específicas (INTO Manchester, INTO Choice Center London, INTO Salud London, Study Group Lipscomb/James Madison/Western Washington) sí permiten aplicar y dan comisión. Si tiene doble nacionalidad y reside fuera de USA, la app sugerirá usar la nacionalidad alternativa cuando convenga."

**Académico**
- Sistema de calificación principal (dropdown): Promedio LATAM, GPA USA, A-levels, IB, Matura suiza, Abitur alemán, Baccalauréat francés, otro
- Promedio / nota
- **Credenciales académicas detalladas** (sección expandible con autocompletado de cursos comunes y notas para cada sistema):
  - APs (cursos + scores)
  - IB (Higher Level + Standard Level + scores predicted/finales + Theory of Knowledge + Extended Essay)
  - Matura (materias + notas)
  - Abitur (materias + notas)
  - Baccalauréat (especialidad + notas)
  - El autocompletado se construye dinámicamente desde los documentos extraídos del Drive (los cursos que aparezcan en investigaciones pasadas se vuelven sugerencias) más una lista base inicial.
  - Si en el futuro María necesita agregar otros diplomas (Bagrut, Gaokao, ENEM, etc.), se agregan vía Claude Code o desde la pantalla de configuración.
- Exámenes estandarizados: SAT, ACT (con scores), exámenes oficiales del país
- Examen de inglés: tipo (IELTS, TOEFL, Duolingo, Cambridge) y score
- Idiomas con nivel

**Intereses académicos**
- Carrera / área de interés (con autocompletado desde el catálogo)
- Áreas alternativas que considera
- Nivel: pregrado / maestría

**Preferencias geográficas**
- Países de interés (multi-select)
- Tipo de ciudad: cualquiera / pequeña / mediana / grande
- Proximidad a ciudad grande importa: sí / no

**Presupuesto**
- Presupuesto anual estimado en USD
- Filtro estricto o flexible

**Otros**
- ¿Acepta hacer pathway/foundation si no cumple requisitos directos? sí / no
- Modalidad: presencial (default fijo según política Gradus)
- Notas adicionales del estudiante

[Botón: Buscar opciones]

### 6.2 Pantalla de resultados

Después de hacer match, muestra:

**Header con resumen del perfil**
"Buscando para: Luciana Olano | Aeroespacial pregrado | UK, USA, España, NL | Pasaporte: COL/ESP | Presupuesto: USD 50K"

**Resultados por país** (acordeones expandibles, países en orden de preferencia del estudiante)

Cada universidad como una tarjeta:

```
┌─────────────────────────────────────────────────────────┐
│ University of Manchester                  🟢 CONVENIO   │
│ Manchester, UK · Russell Group                          │
│                                                         │
│ Programas que matchean:                                 │
│  • Aerospace Engineering (BEng) — 3 años                │
│    Requisitos: A*AA. Estudiante con APs: ⚠ verificar    │
│    Costo: £28,000/año (~USD 36,000) ✅ dentro presupuesto│
│                                                         │
│  • Aerospace Engineering con Foundation integrado       │
│    Foundation: 1 año, integrado en universidad          │
│                                                         │
│ Pathways disponibles:                                   │
│  • INTO Manchester (fuera de campus)                    │
│    🟢 Convenio directo. ⚠ Pasaporte USA: sin comisión   │
│  • Foundation propia universidad (dentro campus)        │
│                                                         │
│ [Ver detalle] [Editar] [Agregar a selección]            │
└─────────────────────────────────────────────────────────┘
```

**Filtros laterales en vivo** (estilo showroom de jets):
- Slider de presupuesto
- Multi-select de pathway providers
- Toggle: solo convenios / solo con beca / solo Russell Group / etc.
- Toggle: incluir universidades sin info de costo
- Toggle: incluir universidades parciales (datos incompletos)

**Sección al final: "Sugerencias externas"** (opcional, requiere click)
Si María lo activa, la app hace búsqueda web complementaria para identificar universidades adicionales que cumplan el perfil pero no están en el catálogo. Estas aparecen claramente diferenciadas: fondo gris, badge "Sugerencia externa — no validada por Gradus".

**Acciones globales:**
- **Exportar resumen ejecutivo a Word.** Genera un documento `.docx` legible y editable con todas las universidades que actualmente cumplen los filtros aplicados. El documento es re-exportable: si María cambia filtros (ej. de "todos los países" a "solo España"), exportar de nuevo genera un nuevo documento con esas universidades. La exportación refleja siempre el estado actual de los filtros, no el estado inicial de la búsqueda.
- Guardar la búsqueda como "investigación" (para historial)

**Estructura del documento Word de resumen ejecutivo:**

El documento debe ser un resumen humano-legible, sin tecnicismos, listo para que María lo lea, edite, comparta o use como base de su propio material. La estructura propuesta:

```
RESUMEN DE INVESTIGACIÓN — [Nombre del estudiante]
Generado: [fecha y hora]

PERFIL DEL ESTUDIANTE
- Nombre: [...]
- Nacionalidades: [...]
- Residencia actual: [...]
- Promedio: [...]
- Sistema: [...]
- Exámenes: SAT [...], Inglés [...]
- Carrera de interés: [...]
- Países considerados: [...]
- Presupuesto anual: USD [...]
- Acepta pathways: [Sí / Solo si es necesario / No]

PARÁMETROS DE LA BÚSQUEDA APLICADOS
- Filtros activos en el momento de la exportación
- Total de universidades en los resultados: [N]
- Universidades con convenio Gradus: [N]
- Universidades sin convenio: [N]
- Universidades con restricción de elegibilidad aplicada: [N]

UNIVERSIDADES POR PAÍS

==================================================
REINO UNIDO (5 universidades)
==================================================

1. University of Manchester    [CONVENIO]
   Manchester, Reino Unido. Russell Group.

   Programas que matchean:
   • Aerospace Engineering (BEng) — 3 años
     Requisitos: A*AA con Matemáticas y Física
     Costo internacional: £28,000 / año (~USD 36,000)
     Idioma: inglés
     Examen aceptado: IELTS 6.5, TOEFL 90, Duolingo 120
     Entradas: septiembre

   • Aerospace Engineering con Foundation integrado — 4 años total

   Pathways disponibles:
   • INTO Manchester (fuera de campus). Excepción USA: aplicable con comisión.
   • Foundation propia universidad (dentro campus).

   Notas: [...]
   Página oficial: [...]
   Video: [...]

2. University of Bristol    [CONVENIO]
   ...

==================================================
ESPAÑA (3 universidades)
==================================================
...

ALERTAS DE ELEGIBILIDAD APLICADAS
[Si el estudiante tiene pasaporte estadounidense, una sección que liste qué universidades quedaron filtradas por esa razón y cuáles aparecieron como excepciones permitidas]

NOTAS DE LA BÚSQUEDA
[Espacio en blanco para que María agregue comentarios manuales después]
```

El documento se genera con la skill de docx (con estilos limpios, tipografía profesional, jerarquía clara de headings). María puede abrirlo en Word, modificarlo, y usarlo como insumo para construir sus Google Slides finales. **No genera CSV ni JSON desde la UI principal** — ese formato queda como opción avanzada solo en la pantalla de configuración para casos puntuales.

### 6.3 Pantalla "Catálogo" (gestión de universidades)

Lista buscable y filtrable de todas las universidades del catálogo. Permite:
- Ver detalle de cada universidad (todos sus programas, requisitos, pathways, convenios)
- Editar cualquier campo
- Agregar nueva universidad (formulario amplio)
- Agregar nuevo programa a una universidad existente
- Agregar nuevo convenio
- Marcar una universidad como "verificar" o "obsoleta"

### 6.4 Pantalla "Conflictos pendientes"

Lista de conflictos de consolidación pendientes de resolver, con interfaz de resolución rápida (descrita en sección 5.3).

### 6.5 Pantalla "Historial"

Lista de búsquedas pasadas (estudiantes investigados) con la posibilidad de:
- Ver el resultado original
- Re-ejecutar la búsqueda con el catálogo actual (para ver si hay nuevas opciones)
- Marcar a qué universidad terminó yendo el estudiante (alimentación del modelo a futuro)

### 6.6 Pantalla "Configuración"

- Path de la base de datos
- Conexión con Google Drive
- API keys (búsqueda web)
- Backups manuales
- Importar/exportar catálogo completo

---

## 7. Reglas de negocio críticas

### 7.1 Filtro automático por pasaporte/residencia

Cuando el estudiante tiene pasaporte estadounidense o reside en USA, la app aplica el motor de elegibilidad descrito en sección 4.6.bis a cada combinación (universidad × pathway provider) de los resultados.

**Comportamiento por caso:**

1. **Universidad bloqueada por todos sus providers disponibles** (todos los pathways retornan `puede_aplicar=False` y no hay vía directa)
   → se oculta por defecto, con un toggle "Mostrar bloqueadas (solo aplicación directa, sin comisión)" disponible.

2. **Universidad accesible vía algún provider con comisión** (al menos un pathway retorna `puede_aplicar=True, recibe_comision=True`)
   → se muestra normal. La app elige por defecto el provider que sí da comisión.

3. **Universidad accesible vía algún provider pero sin comisión** (todos los pathways disponibles retornan `recibe_comision=False`)
   → se muestra con badge amarillo "Sin comisión Gradus para este perfil".

4. **Casos de excepción específica** (ej. INTO Manchester con pasaporte USA, Study Group → Lipscomb con pasaporte USA)
   → la app destaca la excepción con badge verde "Excepción USA: vía permitida con comisión".

**Lógica de doble nacionalidad:**

Si el estudiante tiene doble nacionalidad (ej. colombiana/estadounidense) y reside fuera de USA:
- La app evalúa elegibilidad para ambas nacionalidades
- Si una nacionalidad permite aplicar con comisión y la otra no, recomienda usar la nacionalidad permisiva
- Muestra explícitamente: "Recomendación: aplicar con pasaporte colombiano. Razón: el estadounidense bloquea esta vía."
- El usuario puede ver ambas opciones expandiendo un detalle.

Si el estudiante reside en USA, las restricciones de residencia siempre aplican, sin importar las nacionalidades alternativas.

**Transparencia obligatoria en la UI:**

El usuario siempre debe ver qué reglas se están aplicando. En cada tarjeta de universidad afectada, un texto pequeño debajo indica: "Filtro de pasaporte USA aplicado: [link a explicación]". El link abre un modal explicando la regla específica que se está aplicando para ese caso.

### 7.2 Convenios y comisiones

Cada universidad puede tener uno o más convenios (vía distintos providers o directos). En los resultados:
- Convenio activo + comisión > 0% → badge verde "CONVENIO"
- Convenio en proceso → badge amarillo "EN PROCESO"
- Sin convenio → sin badge
- Convenio con comisión 0% (ej. CEU Abat Oliba Study Abroad) → badge gris "Sin comisión"

### 7.3 Soft filter de presupuesto

Si el estudiante tiene presupuesto definido y la universidad tiene costo registrado:
- Costo dentro del presupuesto → badge verde
- Costo entre 100-120% del presupuesto → badge amarillo "Ligeramente sobre presupuesto"
- Costo > 120% → no se muestra por defecto, toggle para incluirlas

Si la universidad no tiene costo registrado → badge gris "Costo no registrado", se muestra siempre. Esto evita perder opciones.

### 7.4 Pathways: preferencia con fallback inteligente

La preferencia "¿acepta hacer pathway/foundation?" del estudiante es un input importante pero no es un filtro binario duro. La realidad es que en muchos países, si el estudiante no cumple los requisitos de admisión directa y le interesa ese destino, hacer un pathway es la única vía. La app debe respetar esta realidad.

**Comportamiento del motor:**

1. **Estudiante prefiere entrada directa ("no quiere pathway"):**
   - Primer pase: la app busca y muestra solo programas de entrada directa cuyos requisitos el estudiante cumple.
   - Si en un país de su interés NO hay programas directos disponibles que cumplan sus requisitos:
     - La app muestra una sección al inicio de ese país: "⚠️ En [país] no hay opciones de entrada directa que cumplan tu perfil. Si te interesa este destino, considera estas opciones vía pathway:"
     - A continuación lista los programas accesibles vía pathway, con un badge claro "Solo accesible vía pathway".
   - El estudiante (con María) decide caso por caso si acepta el pathway en ese país, sin perder la visibilidad de la opción.

2. **Estudiante acepta pathway sin restricción:**
   - Se muestran tanto entradas directas como pathways.
   - Para cada universidad, si tiene múltiples vías de acceso, se ordenan: entrada directa > foundation integrado en universidad > pathway externo en campus > pathway externo fuera de campus.

3. **Estudiante explícitamente no acepta pathway bajo ninguna circunstancia:**
   - Hard filter: solo entradas directas cumplidas.
   - Se le advierte al final de los resultados: "[N] opciones quedaron excluidas en países de tu interés porque solo eran accesibles vía pathway. Cambiar la preferencia en el formulario para verlas."

Esto evita perder oportunidades por un filtro demasiado rígido y respeta la realidad del proceso de admisión internacional.

### 7.5 Modalidad presencial: preferencia histórica, no política dura

Históricamente, todos los estudiantes que ha atendido Gradus han buscado programas presenciales por razones obvias (experiencia, networking, vida estudiantil). Por eso el default del filtro de modalidad es "presencial".

Sin embargo, **esto es una preferencia configurable, no una política fija de Gradus**. Si en el futuro un estudiante busca específicamente híbrido u online, María puede cambiar el filtro y la app mostrará programas de esa modalidad si existen en el catálogo. La base de datos almacena la modalidad de cada programa correctamente, sin filtrar a nivel de query — el filtro vive en la UI, donde se puede ajustar.

### 7.6 Consideración del Duolingo

Cuando el estudiante tiene Duolingo como examen de inglés, cada programa debe indicar explícitamente si lo acepta. Si no se sabe, se marca con badge "Verificar Duolingo".

---

## 8. Búsqueda web complementaria

### Cuándo se usa

Por dos vías:

1. **Activación explícita** desde la pantalla de resultados, vía un botón "Buscar opciones adicionales en la web". María decide cuándo quiere ampliar la búsqueda más allá del catálogo curado.

2. **Activación automática** cuando los resultados primarios devuelven menos de un umbral mínimo (ej. menos de 5 universidades para un país de interés del estudiante). En ese caso, la app pregunta a María si quiere complementar con búsqueda web.

### Qué hace

Para cada combinación de país de interés × área de carrera × nivel del estudiante, hace consultas a la API de búsqueda web buscando universidades y programas adicionales. Aplica los siguientes filtros sobre los resultados:

- **Excluir universidades ya presentes en el catálogo de Gradus.** No tiene sentido sugerir lo que ya está.
- **Descartar contenido de marketing puro y agregadores de baja calidad** (sitios que solo agrupan rankings sin información sustantiva, comparadores comerciales, listicles de blogs sin autoridad).
- **Priorizar fuentes oficiales:** dominios de las universidades, ministerios de educación, agregadores académicos reconocidos del país (UCAS para UK, Studyportals, Hochschulkompass para Alemania, etc.).
- **Verificar mínimamente que la institución sea una universidad real con programa académico publicado**, no una academia online dudosa o instituciones sin acreditación visible.

**Importante: la app NO filtra por umbrales de ranking ni por listas predefinidas de universidades "buenas".** Hay universidades excelentes que no aparecen en rankings populares (instituciones especializadas, regionales con programas específicos sólidos, escuelas de arte/diseño que no se miden en rankings generalistas, etc.). Filtrar por ranking introduciría sesgo y haría perder buenas opciones. La curaduría de calidad la hace María revisando las sugerencias.

### Cómo se muestra

Las sugerencias externas aparecen en una sección separada y claramente diferenciada de los resultados del catálogo curado:

- Sección con header propio: "Sugerencias adicionales desde la web (no validadas por Gradus)"
- Cada tarjeta con fondo gris distintivo y badge "Sugerencia externa — pendiente de validación"
- Link directo a la fuente (página oficial de la universidad o programa)
- Resumen breve de la información encontrada: nombre, país, ciudad, programa, costo aproximado si está disponible, idioma, requisitos básicos
- Botón "Agregar al catálogo (revisar y validar)" que abre el formulario de nueva universidad pre-llenado con los datos que pudo extraer la búsqueda web. María revisa, completa, ajusta, y guarda.
- Botón "Descartar" para sugerencias que claramente no aplican.

**Nunca se mezclan sugerencias externas con resultados del catálogo curado.** La separación visual es estricta para que María sepa siempre qué es conocimiento curado de Gradus y qué es sugerencia por validar.

### Flujo de validación e incorporación al catálogo

Cuando María hace click en "Agregar al catálogo" sobre una sugerencia:

1. Se abre el formulario de nueva universidad / programa pre-llenado con todo lo que la búsqueda web pudo extraer.
2. Cada campo aparece con un icono indicando "fuente: web search — verificar" hasta que María lo confirma o lo edita.
3. María completa los campos faltantes (convenios si aplica, costos por tipo de estudiante, requisitos detallados, etc.).
4. Al guardar, la universidad pasa al catálogo curado y queda disponible para todas las búsquedas futuras.
5. Quedan registradas como `fuente_inicial = "web_search:[fecha]:[búsqueda]"` para trazabilidad.

Esto cumple la visión: la app no solo filtra el catálogo existente, sino que ayuda activamente a expandirlo de manera controlada y curada.

---

## 9. Plan de implementación por fases

### Fase 0 — Setup (1 día)
- Instalar Claude Code en Mac
- Crear proyecto, repositorio Git local
- Configurar acceso a Google Drive (OAuth)
- Crear esquema inicial de SQLite vacío
- **Criterio de éxito:** comando `gradus init` corre sin errores y crea base de datos vacía válida.

### Fase 1 — Importar convenios y reglas de elegibilidad (1 día)
- Parsear el documento de convenios PDF
- Parsear el documento de pasaporte americano
- Poblar tablas `pathway_providers`, `convenios_universidad`, `reglas_elegibilidad`
- Las excepciones específicas de Study Group USA (Lipscomb, James Madison, Western Washington) se cargan con `centro_especifico` ya que las universidades aún no están en la BD; cuando se carguen vía Fase 4-5, un script de reconciliación las vincula vía `universidad_id`
- **Criterio de éxito:** la base de datos tiene los providers, sus reglas de elegibilidad granulares para USA, y los convenios listados. Una query de prueba "estudiante con pasaporte USA, ¿puede aplicar a INTO Manchester con comisión?" retorna correctamente SÍ/SÍ. Una query "estudiante con pasaporte USA, ¿puede aplicar a INTO Liverpool con comisión?" retorna SÍ/NO.

### Fase 2 — Inventario de Drive (1 día)
- Conexión a Drive funcionando
- Búsqueda y listado de documentos candidatos
- Generación de `inventario.json`
- María revisa y aprueba el inventario
- **Criterio de éxito:** lista de ~100 documentos identificada, validada por María.

### Fase 3 — Extracción piloto (2-3 días)
- Implementar parser y extractor con LLM
- Procesar 5-10 documentos de prueba
- Validar la calidad de la extracción manualmente con María
- Iterar sobre el prompt de extracción hasta lograr calidad aceptable
- **Criterio de éxito:** 80%+ de los campos extraídos correctamente en los documentos de prueba.

### Fase 4 — Extracción masiva (1-2 días de procesamiento)
- Correr extractor sobre todos los documentos
- Generar reporte de extracción
- **Criterio de éxito:** todos los documentos procesados, datos crudos en BD.

### Fase 5 — Consolidación inicial (3-5 días, mucho trabajo de María)
- Implementar consolidador
- Implementar pantalla de resolución de conflictos
- María resuelve los conflictos importantes
- Cruce con convenios
- **Criterio de éxito:** catálogo consolidado con conflictos importantes resueltos. Reporte de calidad disponible.

### Fase 6 — App de filtros — MVP (5-7 días)
- Backend con endpoints principales
- Frontend con pantalla de nuevo estudiante y resultados
- Reglas de elegibilidad implementadas y testeadas
- **Criterio de éxito:** María puede ingresar un perfil de estudiante y ver resultados filtrados con flags de convenios y elegibilidad.

### Fase 7 — Gestión de catálogo (3-4 días)
- Pantallas de catálogo, edición, agregar universidad/programa/convenio
- **Criterio de éxito:** María puede mantener el catálogo sin tocar SQL.

### Fase 8 — Refinamientos (continuo)
- Búsqueda web complementaria
- Historial y "estudiantes similares"
- Exportación a Word (resumen ejecutivo) — feature core, debe estar listo en Fase 6 idealmente; refinamientos visuales después
- Exportación CSV/JSON solo desde configuración avanzada
- Backups automáticos
- Mejoras de UX según uso real

---

## 10. Setup en Mac — instrucciones paso a paso

(Estas instrucciones son para María, pensadas asumiendo cero experiencia con terminal.)

### 10.1 Prerequisitos

1. **Instalar Homebrew** (gestor de paquetes para Mac). Abrir Terminal (Cmd+Space, escribir "Terminal") y pegar:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. **Instalar Python, Node y Git:**
```
brew install python@3.11 node git
```

3. **Instalar Claude Code:**
```
npm install -g @anthropic-ai/claude-code
```

4. **Verificar:**
```
claude --version
```

### 10.2 Crear el proyecto

1. Crear carpeta del proyecto:
```
mkdir -p ~/Gradus/gradus-app
cd ~/Gradus/gradus-app
```

2. Iniciar Claude Code:
```
claude
```

3. Cuando arranque, pegarle el documento de specs (este archivo) y pedirle:
> "Lee estas specs completas y construye el proyecto Gradus App según el plan de implementación. Empieza por la Fase 0 (setup) y avísame cuando termines cada fase para que valide antes de seguir."

### 10.3 Conectar Google Drive

Claude Code te va a pedir credenciales de Google Cloud. Las instrucciones detalladas vendrán cuando llegue ese paso, pero a grandes rasgos:
1. Ir a console.cloud.google.com
2. Crear un proyecto "Gradus"
3. Habilitar Google Drive API
4. Crear credenciales OAuth (escritorio)
5. Descargar el JSON y ponerlo en la carpeta del proyecto

### 10.4 Correr la app día a día

Una vez instalada, María abre Terminal y escribe:
```
cd ~/Gradus/gradus-app
./run.sh
```

Esto abre la app en el navegador en `http://localhost:3000`. Para cerrar, Ctrl+C en Terminal.

Alternativamente, se puede crear un alias de doble click (un archivo `Gradus.command` en el escritorio que hace lo mismo).

---

## 11. Decisiones tomadas y justificaciones

| Decisión | Alternativa rechazada | Razón |
|---|---|---|
| Catálogo desde docs de estudiantes | Catálogo desde convenios | El conocimiento curado es el activo de Gradus, no la lista de convenios |
| SQLite local | Postgres en cloud | Simplicidad, portabilidad, cero costos operativos |
| Web app local | App nativa Mac | Modificable fácilmente, replicable a otros equipos |
| FastAPI Python | Node.js puro | Python es mejor para extracción/parsing de docs |
| React + Tailwind | HTML simple / framework más opinado | Balance entre velocidad de desarrollo y calidad de UI |
| Reglas de elegibilidad estructuradas | Notas en texto libre | Permite filtrado automático y evita errores |
| Soft filter de presupuesto | Hard filter | Evita perder opciones por data faltante |
| No genera Slides | Genera Slides | María prefiere control sobre la presentación final |
| Sin sistema de cuentas | Login multi-usuario | Solo María usa la app, simplicidad |
| Costos en tabla aparte por tipo de estudiante | Un solo campo de costo en programas | Múltiples tipos (UE, internacional, in-state) tienen costos muy distintos en el mismo programa |
| Exportación principal en Word | CSV/JSON desde la UI principal | María no es tech-savvy con CSV/JSON; prefiere documento legible |
| Doble nacionalidad NO permite evadir restricciones | Estudiante elige nacionalidad más conveniente | Restricción es impuesta por providers, no es opcional |
| Sin filtro de ranking en búsqueda web | Filtrar por top 1000 QS/THE | Universidades buenas no siempre aparecen en rankings; María cura |
| Pathway con fallback inteligente | Pathway como filtro binario | En algunos países es la única vía, no se debe perder la opción |
| Modalidad presencial como preferencia configurable | Modalidad presencial como política dura | Es histórico, no política rígida |

---

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Calidad de extracción baja | Fase piloto con 5-10 docs antes de procesar todo |
| Conflictos de consolidación inmanejables | UI de resolución rápida + opción de "tomar más reciente" automática |
| Cambios en estructura de docs futuros | Parser configurable, no asumir esquema rígido |
| Pérdida de la base de datos | Backups automáticos + DB sincronizada con Drive |
| María no puede mantener el catálogo | Pantallas de gestión amigables, sin tocar SQL |
| Reglas de elegibilidad incompletas (otros pasaportes) | Tabla de reglas extensible, se agregan según se descubran |

---

## 13. Apéndice A — Esquema SQL completo

```sql
-- Pathway providers
CREATE TABLE pathway_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    tiene_convenio_gradus BOOLEAN DEFAULT 0,
    comision_porcentaje REAL,
    comision_se_descuenta_uk BOOLEAN DEFAULT 0,
    notas_convenio TEXT
);

-- Reglas de elegibilidad por provider, con granularidad opcional a universidad/centro
CREATE TABLE reglas_elegibilidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pathway_provider_id INTEGER NOT NULL,
    universidad_id INTEGER,           -- NULL = aplica a todo el provider en ese país
    centro_especifico TEXT,           -- ej. "INTO Choice Center London"
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

-- Índice clave para resolución rápida de elegibilidad
CREATE INDEX idx_reglas_lookup ON reglas_elegibilidad(
    pathway_provider_id, nacionalidad_o_residencia, pais_destino, universidad_id
);

-- Universidades
CREATE TABLE universidades (
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

-- Programas
CREATE TABLE programas (
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

-- Costos por programa, segmentados por tipo de estudiante
CREATE TABLE costos_programa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    tipo_estudiante TEXT NOT NULL,  -- 'internacional', 'home_uk_irl', 'ue', 'in_state_usa', 'out_of_state_usa', 'local'
    costo_anual_local TEXT,          -- "£28,000", "€2,500", "$45,000"
    costo_anual_estimado_usd INTEGER,
    moneda TEXT,
    ano_referencia INTEGER,
    incluye TEXT,                    -- "Solo matrícula", "Matrícula + alojamiento", etc.
    notas TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id),
    UNIQUE (programa_id, tipo_estudiante, ano_referencia)
);

CREATE INDEX idx_costos_programa ON costos_programa(programa_id, tipo_estudiante);

-- Requisitos de admisión
CREATE TABLE requisitos_admision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    sistema TEXT NOT NULL,           -- 'A-levels', 'IB', 'GPA_USA', 'AP', 'SAT', 'Matura', 'Abitur', 'Baccalaureat', etc.
    requisito TEXT NOT NULL,
    notas TEXT,
    examen_ingles_aceptado TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id)
);

-- Requisitos específicos de USA (SAT opcional, CSS Profile, etc.)
CREATE TABLE requisitos_usa_especificos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programa_id INTEGER NOT NULL,
    sat_es_requerido BOOLEAN DEFAULT 0,
    sat_es_opcional BOOLEAN DEFAULT 0,
    sat_recomendado_si_aporta TEXT,    -- "1400+", "1500+"
    sat_recomendado_notas TEXT,
    act_aceptado BOOLEAN DEFAULT 1,
    requiere_css_profile BOOLEAN DEFAULT 0,
    css_profile_notas TEXT,
    application_platform TEXT,          -- 'Common App', 'Coalition', 'directa'
    supplemental_essays BOOLEAN DEFAULT 0,
    notas TEXT,
    FOREIGN KEY (programa_id) REFERENCES programas(id),
    UNIQUE (programa_id)
);

-- Pathways
CREATE TABLE pathways (
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

-- Convenios universidad
CREATE TABLE convenios_universidad (
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

-- Estudiantes históricos
CREATE TABLE estudiantes_historicos (
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

-- Logs de extracción
CREATE TABLE extracciones_log (
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

-- Conflictos pendientes
CREATE TABLE conflictos_pendientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    entidad_id INTEGER,
    campo TEXT,
    valores_propuestos TEXT NOT NULL,
    resolucion TEXT,
    fecha_resolucion DATETIME,
    estado TEXT DEFAULT 'pendiente'
);

-- Índices para rendimiento
CREATE INDEX idx_universidades_pais ON universidades(pais);
CREATE INDEX idx_programas_area ON programas(area);
CREATE INDEX idx_programas_nivel ON programas(nivel);
CREATE INDEX idx_convenios_universidad ON convenios_universidad(universidad_id);
CREATE INDEX idx_pathways_programa ON pathways(programa_id);
```

### Seed inicial — pathway providers conocidos

```sql
INSERT INTO pathway_providers (nombre, tiene_convenio_gradus, comision_se_descuenta_uk) VALUES
    ('INTO', 1, 0),
    ('Kaplan', 1, 0),
    ('Study Group', 1, 0),
    ('Shorelight', 1, 0),
    ('OnCampus', 1, 0),
    ('Navitas', 1, 0),
    ('GUS', 1, 0),
    ('Adventus', 1, 0),
    ('QS', 1, 0),
    ('Trotamundos', 1, 0),
    ('Geebe', 1, 0),
    ('Key Education', 1, 0),
    ('IPERC', 1, 0),
    ('SI UK', 1, 0),
    ('Direct', 0, 0);
```

### Seed inicial — reglas de elegibilidad para pasaporte/residencia USA

Las universidades referenciadas deben crearse antes (o se inserta la regla con `centro_especifico` y se asocia `universidad_id` después):

```sql
-- Reglas generales por provider
INSERT INTO reglas_elegibilidad
    (pathway_provider_id, universidad_id, centro_especifico, nacionalidad_o_residencia,
     pais_destino, puede_aplicar, gradus_recibe_comision, es_excepcion, notas)
VALUES
    -- INTO
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'), NULL, NULL, 'USA', 'USA', 1, 0, 0,
     'En USA, se puede aplicar pero no hay comisión por restricción interna'),
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'), NULL, NULL, 'USA', 'UK', 1, 0, 0,
     'Regla general UK: aplica pero sin comisión'),
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'), NULL, 'INTO Choice Center London', 'USA', 'UK', 1, 1, 1,
     'Excepción: este centro sí permite comisión con pasaporte USA'),
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'), NULL, 'INTO London (Salud)', 'USA', 'UK', 1, 1, 1,
     'Excepción: áreas de salud sí permiten comisión con pasaporte USA'),
    ((SELECT id FROM pathway_providers WHERE nombre='INTO'), NULL, 'INTO Manchester', 'USA', 'UK', 1, 1, 1,
     'Excepción: Manchester sí permite comisión con pasaporte USA'),

    -- Kaplan
    ((SELECT id FROM pathway_providers WHERE nombre='Kaplan'), NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo total en USA: aplicación directa a universidad sin Gradus'),
    ((SELECT id FROM pathway_providers WHERE nombre='Kaplan'), NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Sin restricción en UK'),

    -- Study Group
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'), NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo general en USA salvo excepciones'),
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'), NULL, 'Lipscomb', 'USA', 'USA', 1, 1, 1,
     'Excepción: Lipscomb sí permite con pasaporte USA + comisión'),
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'), NULL, 'James Madison', 'USA', 'USA', 1, 1, 1,
     'Excepción: James Madison sí permite con pasaporte USA + comisión'),
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'), NULL, 'Western Washington', 'USA', 'USA', 1, 1, 1,
     'Excepción: Western Washington sí permite con pasaporte USA + comisión'),
    ((SELECT id FROM pathway_providers WHERE nombre='Study Group'), NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Foundation y DE en UK sin restricción'),

    -- Shorelight
    ((SELECT id FROM pathway_providers WHERE nombre='Shorelight'), NULL, NULL, 'USA', 'USA', 0, 0, 0,
     'Bloqueo total en USA: aplicación directa a universidad sin Gradus'),

    -- OnCampus
    ((SELECT id FROM pathway_providers WHERE nombre='OnCampus'), NULL, NULL, 'USA', 'UK', 1, 1, 0,
     'Sin restricción en UK');
```

---

## 14. Apéndice B — Glosario

- **Pathway / Foundation / Year One:** programas de un año (típicamente) que sirven de puente entre el bachillerato del estudiante y la entrada directa a una carrera universitaria, cuando el estudiante no cumple los requisitos directos.
- **Pathway provider:** empresa especializada en operar pathways en convenio con universidades. Los principales son INTO, Kaplan, Navitas, Study Group, OnCampus, Shorelight, GUS.
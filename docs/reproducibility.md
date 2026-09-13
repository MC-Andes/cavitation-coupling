# Reproducibilidad y estado del proyecto

## Qué está implementado

- Paquete Python 3.11+ para leer/escribir el HDF5 v1.
- Validación de formas, finitud, tiempo y radios monótonos.
- Presión manométrica como promedio de anillos y fuerza integrada exacta.
- Reconstrucción axisimétrica en puntos superficiales 3-D.
- Interpolación temporal lineal sin extrapolación.
- Corrección global mínima L2 que conserva fuerza e impulso para depuración.
- Exportación HDF5 autocontenida para condiciones `POINT_LOAD` de Kratos.
- Promedio temporal exacto del interpolante lineal en cada paso explícito.
- `Process` Python que empareja condiciones por coordenada inicial y aplica N.
- Pruebas, cobertura ≥90 %, lint, tipos estrictos y build de documentación.

## Qué no está implementado ni se presenta como resultado

- Caso C de Basilisk y exportador paralelo.
- Matriz geométrica anillo–parche \(M_{ai}\) de producción.
- Caso geométrico completo `Grid.mdpa`/`Body.mdpa` ejecutado con Kratos.
- Casos FEniCSx, constitutivos gradados o resultados físicos.
- Condensación, eliminación de partículas, delaminación o acoplamiento two-way.

Esta distinción impide que el ejemplo sintético se confunda con datos de
cavitación. La primera corrida externa solo puede comenzar cuando los campos
`simulation_revision` del solver lock estén fijados.

## Entorno local

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,docs]"
ruff check .
ruff format --check .
mypy src
pytest
mkdocs build --strict
python examples/synthetic_mapping.py
python examples/kratos_load_table.py
cavitation-coupling results/synthetic-wall-loads.h5
cavitation-kratos-export \
  results/synthetic-wall-loads.h5 \
  results/kratos/synthetic-gaussian-pulse/surface-points.csv \
  results/kratos/synthetic-gaussian-pulse/cli-loads.v1.h5
```

En la auditoría local se usó Python 3.12.13. La CI repite pruebas en 3.11, 3.12 y
3.13. `pyproject.toml` es la única fuente de dependencias Python; no se mantiene
un `requirements.txt` divergente.

Kratos se mantiene en el extra opcional `kratos` porque los wheels oficiales
10.4.3 no cubren macOS ARM. El job `Kratos MPM 10.4.3 smoke` usa Linux x86-64,
importa MPMApplication y el proceso HDF5, y ejecuta las pruebas del adaptador.

## Procedencia de plantillas

El archivo `provenance/solvers.lock.yml` registra los commits auditados de:

- MC-Andes `standards`: `6fd9737`.
- `template-python-mech`: `9f3de3a`.
- `template-docs`: `378dc16`.

También registra las revisiones consultadas de los candidatos MPM y selecciona
Kratos 10.4.3. “Auditada” no significa “usada en simulación”; el commit ejecutado,
paquetes, compilador, hilos OpenMP y digest del contenedor se fijarán por campaña.

## Licencias

El paquete original de este repositorio es MIT. Kratos usa BSD-4-Clause y se
ejecuta como programa externo; su reconocimiento está en
`THIRD_PARTY_LICENSES.md`. Si se añade código C derivado de Basilisk, se conserva
su aviso y licencia compatible en ese subárbol; no se relicencia bajo MIT. Toda
dependencia y dato pasa una auditoría antes de release.

## Manifiesto de una corrida

Cada resultado publicable tendrá:

```text
case_id/
├── resolved-config.yaml
├── manifest.json
├── software-lock.yml
├── stdout.log
├── wall-loads.v1.h5
├── kratos-loads.v1.h5
├── metrics.json
└── sha256sums.txt
```

`manifest.json` registra fecha UTC, host, CPU/GPU, MPI ranks, threads, memoria,
tiempo, celdas/partículas, pasos y salida Git sucia/limpia. Los binarios HDF5
grandes se publican en un repositorio de datos con DOI y hashes; Git conserva
fixtures mínimos y scripts.

## Flujo MC-Andes

El trabajo está en `feat/mvp-cavitation-coupling`. La integración debe ocurrir
por Pull Request, con al menos una revisión y checks verdes. Se usan Conventional
Commits, Semantic Versioning y Keep a Changelog. Antes de `v0.1.0` en GitHub se
requieren además:

- repositorio/remoto definitivo y URL correcta en `CITATION.cff`;
- protección de `main` y checks requeridos;
- Pages, Dependabot, alertas y secret scanning;
- commit real de Basilisk/Kratos/FEniCSx para el MVP ejecutado;
- licencia de cualquier código externo incorporado;
- soporte/maintainers y DOI de datos, si existen.

## Soporte

El alcance soportado en v0.1 es el esquema HDF5 y el mapeo de presión normal. Las
API de solver externas permanecen experimentales hasta que sus pruebas de
integración entren en CI/HPC. Preguntas y cambios siguen las plantillas de issue;
vulnerabilidades se reportan de forma privada según `SECURITY.md`.

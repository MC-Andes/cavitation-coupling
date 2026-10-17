# Inicio rápido

Ejecuta primero el ejemplo sintético para comprobar el contrato de datos y el
mapeo. Esta ruta funciona con el paquete Python y no requiere los solvers
externos Basilisk, Kratos o FEniCSx.

## 1. Preparar el entorno

Necesitas Git y Python 3.11 o superior. Ejecuta los comandos desde la raíz del
repositorio:

```bash
git clone https://github.com/MC-Andes/cavitation-coupling.git
cd cavitation-coupling
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

En Windows con PowerShell, sustituye la activación por:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Generar y comprobar una carga

```bash
python examples/synthetic_mapping.py
cavitation-coupling results/synthetic-wall-loads.h5
```

El primer comando escribe `results/synthetic-wall-loads.h5` y muestra los
errores relativos de fuerza e impulso del mapeo. El segundo inspecciona
la historia HDF5. El ejemplo contiene 101 instantes y 40 anillos.

!!! note "Datos de verificación"
    El pulso es sintético. Sus amplitudes y tiempos se eligieron para comprobar
    el software; no son mediciones ni una corrida física de Basilisk.

## 3. Crear la tabla para Kratos

Después del paso anterior, ejecuta:

```bash
python examples/kratos_load_table.py
```

El ejemplo crea los puntos de la superficie y la tabla de fuerzas:

```text
results/kratos/synthetic-gaussian-pulse/
├── surface-points.csv
└── cavitation.kratos-loads.v1.h5
```

Para usar esos mismos puntos desde la herramienta de línea de comandos:

```bash
cavitation-kratos-export \
  results/synthetic-wall-loads.h5 \
  results/kratos/synthetic-gaussian-pulse/surface-points.csv \
  results/kratos/synthetic-gaussian-pulse/cli-loads.v1.h5
```

La tabla contiene fuerzas en **N**, listas para el adaptador; no construye ni
resuelve por sí sola un modelo MPM. Consulta la
[guía de integración con Kratos](https://github.com/MC-Andes/cavitation-coupling/blob/main/mpm/kratos/README.md)
para sus requisitos de plataforma y aplicación.

## 4. Abrir la carga en ParaView

```bash
cavitation-paraview-export \
  results/synthetic-wall-loads.h5 \
  results/paraview/synthetic-gaussian-pulse
```

Abre `wall-pressure.pvd` dentro del directorio generado para recorrer la presión
en el tiempo. `radial-time.vtr` muestra el mapa radial–temporal y
`force-history.vtp`, la historia de fuerza. La
[guía de ParaView](https://github.com/MC-Andes/cavitation-coupling/blob/main/visualization/paraview/README.md)
detalla la escena y sus variables.

## 5. Verificar el paquete o editar documentación

```bash
python -m pip install -e ".[dev,docs]"
ruff check .
ruff format --check .
mypy src
pytest
mkdocs build --strict
```

Para previsualizar la documentación mientras editas:

```bash
mkdocs serve
```

Conserva las salidas de los ejemplos en `results/`. Las versiones del software,
los supuestos y los requisitos de una corrida física se explican en
[reproducibilidad](reproducibility.md) y [estado del proyecto](project-status.md).

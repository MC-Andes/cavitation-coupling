# Cavitación · Basilisk–MPM

[![CI](https://github.com/MC-Andes/cavitation-coupling/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/MC-Andes/cavitation-coupling/actions/workflows/ci.yml)
[![Documentación](https://img.shields.io/badge/documentación-español-173f73)](https://mc-andes.github.io/cavitation-coupling/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](pyproject.toml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-173f73)](LICENSE)

**Transferencia conservativa de cargas de cavitación para estudiar la respuesta
de una pared con el Método de los Puntos Materiales.** Un proyecto de
[mecánica computacional de MC-Andes](https://mc-andes.github.io/).

[Documentación](https://mc-andes.github.io/cavitation-coupling/) ·
[Inicio rápido](docs/getting-started.md) ·
[Alcance publicado](docs/project-status.md) ·
[Contribuir](CONTRIBUTING.md) ·
[Citar](CITATION.cff)

## El problema

El colapso de una burbuja próxima a una superficie produce una carga transitoria.
Este proyecto conecta la presión axisimétrica de una pared rígida en Basilisk
con fuerzas superficiales para Kratos MPM. El primer caso de investigación es
una pared homogénea elástica; espesor, gradación y respuesta plástica son
extensiones que requieren sus propias verificaciones.

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/data-flow-mobile.svg">
  <img src="docs/assets/data-flow.svg" alt="Flujo unidireccional de presión, transferencia y respuesta estructural.">
</picture>

La deformación de la pared no regresa al fluido en este acoplamiento
unidireccional. FEniCSx se contempla como referencia estructural independiente.

## Qué ofrece esta versión pública

| Componente | Disponible en el repositorio |
| --- | --- |
| Contrato de cargas | HDF5 versionado con presión manométrica, anillos, tiempos, unidades y procedencia |
| Transferencia | Mapeo de cargas y comprobación de fuerza e impulso |
| Adaptador Kratos | Tabla HDF5 de fuerzas puntuales y proceso de aplicación de cargas |
| Visualización | Exportación VTK para presión, mapa radial–temporal e historia de fuerza |
| Verificación | Ejemplos sintéticos, pruebas automáticas y documentación técnica |

> **Investigación en desarrollo.** Los ejemplos incluidos verifican el flujo de
> software con datos sintéticos. Esta rama pública no contiene todavía un caso
> físico completo validado de cavitación ni predicciones de daño o erosión.
> Consulta el [alcance y las limitaciones](docs/project-status.md) antes de
> interpretar cualquier resultado.

## Inicio rápido

Requiere Python 3.11 o superior. Desde una terminal:

```bash
git clone https://github.com/MC-Andes/cavitation-coupling.git
cd cavitation-coupling
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/synthetic_mapping.py
cavitation-coupling results/synthetic-wall-loads.h5
```

En PowerShell, activa el entorno con `.venv\Scripts\Activate.ps1`.
El ejemplo genera una carga sintética y muestra los errores de fuerza e impulso;
no requiere instalar Basilisk ni Kratos. La
[guía de inicio](docs/getting-started.md) añade la tabla para Kratos y la
visualización en ParaView con rutas completas de entrada y salida.

## Guía de lectura

| Para… | Consulta |
| --- | --- |
| Entender el modelo | [Problema físico](docs/physics.md), [MPM](docs/mpm.md) y [transferencia](docs/coupling.md) |
| Identificar qué está publicado | [Estado y alcance](docs/project-status.md) |
| Reproducir y verificar | [Inicio rápido](docs/getting-started.md), [verificación](docs/verification.md) y [reproducibilidad](docs/reproducibility.md) |
| Integrar un solver | [Guía de Kratos](mpm/kratos/README.md) y [plan técnico de la pared](docs/framework-and-2d-roadmap.md) |
| Inspeccionar campos | [ParaView](visualization/paraview/README.md) |
| Participar | [Contribución](CONTRIBUTING.md) y [normas MC-Andes](https://github.com/MC-Andes/standards) |

## Organización del repositorio

```text
src/cavitation_coupling/  Contratos, mapeo y herramientas de línea de comandos
coupling/schemas/        Esquemas de intercambio de cargas
mpm/kratos/              Adaptador de cargas para Kratos MPM
examples/                Ejemplos sintéticos reproducibles
tests/                   Pruebas del paquete y del adaptador
docs/                    Documentación publicada con MkDocs
visualization/paraview/  Guías y escenas de visualización
provenance/              Versiones y referencias de software
```

## Convenciones y calidad

- Unidades SI; presión manométrica positiva en compresión.
- Presión radial como promedio por área anular; `POINT_LOAD` recibe **N**, no Pa.
- Interpolación temporal sin extrapolación automática.
- Conservación de fuerza e impulso comprobada por el mapeador.
- Resultados generados fuera del control de versiones.

Para desarrollar y verificar la documentación:

```bash
python -m pip install -e ".[dev,docs]"
ruff check .
ruff format --check .
mypy src
pytest
mkdocs build --strict
```

Los cambios se integran por Pull Request, con revisión y CI en verde según las
[normas de MC-Andes](https://github.com/MC-Andes/standards). Consulta
[CHANGELOG.md](CHANGELOG.md) para el historial y [SECURITY.md](SECURITY.md)
para reportar vulnerabilidades.

## Licencia y citación

El paquete publicado usa la [licencia MIT](LICENSE). Las dependencias conservan
sus licencias y reconocimientos en [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
Cita la versión utilizada mediante [CITATION.cff](CITATION.cff), además de los
solvers y datos primarios empleados.

# Acoplamiento Basilisk–MPM para cavitación

Estrategia reproducible y herramientas de acoplamiento *offline* para estudiar la
respuesta de recubrimientos con impedancia gradada ante el colapso de una burbuja
aislada. El producto mínimo viable (MVP) transfiere la presión manométrica
axisimétrica de una pared rígida en Basilisk a una superficie MPM elástica y
verifica conservación de fuerza e impulso.

> **Alcance de v0.1.0:** este repositorio contiene el diseño técnico, el contrato
> HDF5 y un mapeador conservativo probado con datos sintéticos. No contiene aún
> resultados físicos de Basilisk, Kratos ni FEniCSx; ninguna cifra sintética debe
> interpretarse como predicción de erosión.

## Flujo del MVP

```text
Basilisk axisimétrico
  └─ p_w(r,t), tau_w(r,t), metadatos
       └─ HDF5 versionado (presión manométrica, promedios anulares)
            └─ mapeo conservativo y reconstrucción r = sqrt(x² + y²)
                 ├─ Kratos MPMApplication: sólido elástico
                 └─ FEniCSx: referencia lineal independiente
                      └─ errores de fuerza, impulso y desplazamiento
```

La [estrategia técnica](docs/index.md) contiene formulación, parámetros
propuestos, selección de MPM, algoritmo de transferencia, V&V, diseño de
experimentos, costos, riesgos y plan de publicación.

El [estado autocontenido y plan de la pared MPM
2D](docs/framework-and-2d-roadmap.md) separa lo ya implementado de las siguientes
tareas, define el caso axisimétrico, las pruebas de fuerza/impulso/onda/energía y
la salida requerida en ParaView.

## Instalación y verificación

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,docs]"
ruff check .
ruff format --check .
mypy src
pytest
mkdocs build --strict
python examples/synthetic_mapping.py
cavitation-coupling results/synthetic-wall-loads.h5
cavitation-kratos-export \
  results/synthetic-wall-loads.h5 \
  surface-points.csv \
  cavitation.kratos-loads.v1.h5
cavitation-paraview-export \
  results/synthetic-wall-loads.h5 \
  results/paraview/synthetic-gaussian-pulse
```

Python 3.11 o superior es obligatorio. La cobertura mínima del paquete es 90 %.
Los resultados generados permanecen fuera del control de versiones.

La integración con Kratos usa dos archivos HDF5: el primero conserva el campo
canónico $p(r,t)$ como promedios anulares; el segundo contiene esa fuente y las
fuerzas puntuales ya integradas para las condiciones MPM. Consulta la
[guía Kratos](mpm/kratos/README.md) antes de construir el sólido: `POINT_LOAD`
recibe N, no Pa.

## Visualización

El exportador genera una animación de presión superficial, un mapa
radial–temporal y la historia de fuerza en formatos VTK XML. La guía de
[visualización en ParaView](visualization/paraview/README.md) explica cómo abrir
el bundle y regenerar el estado reproducible y su vista previa.

## Convenciones científicas

- Unidades SI en memoria y en disco.
- Presión transferida: `p_w - p_ref`, positiva en compresión.
- Los campos radiales son promedios por área sobre anillos, no máximos de celda.
- Sin extrapolación temporal ni filtrado automático de pulsos.
- Tolerancia de aceptación inicial del mapeo: 1 % para fuerza e impulso; las
  pruebas algebraicas del mapeador exigen precisión de máquina.
- Una simulación de daño por un solo colapso se reporta como daño incipiente o
  potencial de erosión, no como erosión acumulada cuantitativa.

## Organización y gobernanza

El proyecto sigue las [normas de MC-Andes](https://github.com/MC-Andes/standards)
y deriva de `template-python-mech` y `template-docs`. Las revisiones auditadas se
registran en [Reproducibilidad](docs/reproducibility.md). Todo cambio entra por
Pull Request desde una rama corta, con Conventional Commits, pruebas,
documentación y CI en verde.

## Licencia y citación

Código bajo licencia MIT. Consulte [CITATION.cff](CITATION.cff) y cite además los
solucionadores y datos primarios utilizados en cada publicación. Los avisos de
Kratos y otras dependencias externas están en
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

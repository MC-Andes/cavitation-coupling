# Adaptador Kratos MPMApplication

## Decisión de integración

Kratos MPMApplication 10.4.3 es el solver sólido seleccionado. Su proceso
Neumann de partículas genera condiciones móviles `MPMParticlePointLoadCondition`.
La implementación oficial no ofrece aún cargas distribuidas de línea o superficie
para esas condiciones: `POINT_LOAD` representa una **fuerza total en N** y
`MPC_AREA` vale 1 en la condición puntual. Por eso nunca se pasa presión en Pa
directamente a Kratos.

La ruta implementada es:

```text
Basilisk wall-loads HDF5: p̄(r,t) [Pa]
  → cavitation-kratos-export + superficie de cuadratura
  → Kratos load HDF5: p̄(r,t), áreas y POINT_LOAD(t) [N]
  → AxisymmetricHdf5PointLoadProcess
  → MPMParticlePointLoadCondition
```

## Archivos

- `axisymmetric_hdf5_point_load_process.py`: proceso cargable por Kratos.
- `ProjectParameters.load-process.json`: fragmento para `list_other_processes`.
- `../../coupling/schemas/kratos-point-loads-v1.yaml`: contrato derivado.

El archivo de superficie es CSV solo porque contiene una tabla geométrica
pequeña y auditable. Sus columnas exactas, todas en SI, son:

```text
condition_id,x_m,y_m,z_m,area_m2,nx,ny,nz
```

Debe existir una condición geométrica `Point3D` en el submodelpart de carga de
`case_Grid.mdpa` por cada fila. Cada condición genera exactamente un punto
material de carga. Las coordenadas se comparan de forma uno-a-uno; el orden y los
IDs que Kratos asigne a las condiciones MPM generadas no se usan como identidad.

## Generar una tabla de carga

```bash
python examples/synthetic_mapping.py
python examples/kratos_load_table.py

# Para una superficie real exportada por el preprocesador:
cavitation-kratos-export \
  case.wall-loads.v1.h5 \
  surface-points.csv \
  case.kratos-loads.v1.h5 \
  --wall-origin 0 0 0 \
  --wall-x-axis 1 0 0 \
  --wall-y-axis 0 1 0
```

El HDF5 derivado conserva la fuente `source/pressure_gauge` con dimensiones
`(Nt,Nr)` y guarda además `loads/point_force` con dimensiones `(Nt,Nc,3)`. La
escritura es atómica, los campos grandes usan gzip, shuffle y Fletcher-32, y el
lector rechaza archivos incompletos o versiones mayores desconocidas.

## Ejecutar con Kratos

Los wheels oficiales 10.4.3 se ejecutan en Linux x86-64, no en el host macOS ARM
actual. En un entorno Linux:

```bash
python -m pip install -e ".[kratos]"
export PYTHONPATH="$PWD/mpm/kratos:$PYTHONPATH"
python MainKratos.py ProjectParameters.json
```

Copia el objeto de `ProjectParameters.load-process.json` dentro de
`processes.list_other_processes`. El nombre `Background_Grid.CavitationLoad`
debe coincidir con el submodelpart que contiene únicamente los puntos de carga.

`time_sampling = step_average` integra exactamente el interpolante lineal de la
fuente sobre `[TIME-DELTA_TIME,TIME]`. Esto conserva impulso aun si un paso cruza
uno o varios tiempos almacenados. `linear` se reserva para depuración.

## Signo y conservación

Para normal exterior del sólido \(\mathbf n\), la fuerza aplicada es

\[
\mathbf f_a(t)=-p_a(t)A_a\mathbf n_a.
\]

Una presión manométrica positiva comprime el sólido. Las fuerzas ya incluyen
`area_m2`; no deben multiplicarse otra vez por `MPC_AREA` ni por \(2\pi r\). El
exportador registra fuerza fuente, fuerza aplicada, error de impulso y la
corrección del mapeo. El proceso puede escribir la fuerza realmente aplicada por
paso en `diagnostics_csv`.

## Alcance

Esta ruta utiliza puntos de cuadratura y una corrección global mínima para el
MVP. Conserva exactamente fuerza e impulso globales y tiene pruebas analíticas,
pero el operador anillo–parche por intersección geométrica sigue siendo la ruta
de producción para demostrar conservación local por anillo.

La carga se define en la superficie inicial y no sigue la normal deformada, en
coherencia con la pared rígida usada en Basilisk. La release MPM auditada admite
OpenMP, no MPI; el proceso no debe ejecutarse en varios rangos.

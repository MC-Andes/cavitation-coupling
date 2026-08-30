# Transferencia conservativa Basilisk–MPM

## Contrato HDF5 abierto

El archivo canónico se llama `{case_id}.wall-loads.v1.h5`, usa `float64`, SI,
compresión gzip, `shuffle` y checksum Fletcher-32. La especificación legible por
máquina está en `coupling/schemas/wall-loads-v1.yaml`.

```text
/
├── attrs
│   ├── schema_name, schema_version, case_id
│   ├── complete, units_system = SI
│   ├── coordinate_system = axisymmetric-rz
│   ├── pressure_convention = gauge-positive-in-compression
│   ├── temporal_interpolation = piecewise-linear
│   └── metadata_json
├── time                              (Nt)       [s]
├── coordinates/radial_edges          (Nr+1)     [m]
├── fields/pressure_gauge             (Nt,Nr)    [Pa]
├── fields/shear_radial               (Nt,Nr)    [Pa]
├── derived/impulse_pressure          (Nr)       [Pa s]
└── derived/force_normal              (Nt)       [N]
```

La versión actual es 1.1.0 y el lector sigue aceptando archivos 1.0 del mismo
major. La escritura es atómica y `complete` solo se activa tras cerrar todos los
datasets. `metadata_json` debe contener en producción: commits de Basilisk y del
exportador, compilador, comando, SHA-256 de configuración, \(R_0,H,\gamma\),
presión de referencia, niveles y \(\Delta_{min}\), cadencia temporal e ID del
estudio de convergencia. Se conservan el archivo de configuración original y su
hash. La versión 1.x puede añadir datasets opcionales; una versión mayor cambia
semántica y debe rechazarse hasta migración explícita.

Los centros radiales pueden derivarse de los bordes y sirven solo para dibujar.
Guardar únicamente muestras puntuales en centros impediría calcular exactamente
el área de cada anillo y no es aceptable. CSV se permite durante depuración, no
como intercambio final de campos.

## Contrato derivado para Kratos

Kratos no consume directamente presión radial. El comando
`cavitation-kratos-export` combina el HDF5 anterior con una tabla de cuadratura
de la superficie y escribe `{case_id}.kratos-loads.v1.h5`:

```text
/
├── source/time                         (Nt)       [s]
├── source/radial_edges                 (Nr+1)     [m]
├── source/pressure_gauge               (Nt,Nr)    [Pa]
├── conditions/ids                      (Nc)       [-]
├── conditions/coordinates_initial      (Nc,3)     [m]
├── conditions/tributary_area           (Nc)       [m²]
├── conditions/outward_normal           (Nc,3)     [-]
├── loads/pressure_gauge                 (Nt,Nc)    [Pa]
├── loads/point_force                    (Nt,Nc,3)  [N]
├── diagnostics/source_force             (Nt)       [N]
└── diagnostics/target_force             (Nt)       [N]
```

La especificación completa está en
`coupling/schemas/kratos-point-loads-v1.yaml`. El archivo es autocontenido:
conserva $p(r,t)$, pero Kratos recibe exclusivamente `loads/point_force`. La
escritura usa un temporal y renombrado atómico, marca `complete=true` al final y
protege los campos grandes con gzip, shuffle y Fletcher-32.

## Operador espacial de producción

Sea \(\chi_i(r)\) el indicador del anillo fuente \(i\), y \(N_a\) la función de
forma o ponderación del grado de libertad superficial \(a\). Se precomputa

\[
M_{ai}=\int_\Gamma N_a(\mathbf x)\chi_i(r)\,dA,
\qquad
A_i=\pi(r_{i+1}^2-r_i^2).
\]

Si la superficie cubre el disco y las funciones forman una partición de unidad,

\[
\sum_a M_{ai}=A_i.
\]

La fuerza normal es entonces

\[
\mathbf f_a^p(t)=-\mathbf n_a\sum_iM_{ai}\bar p_i(t).
\]

Para una superficie MPM por parches, \(M_{ai}\) se obtiene cortando cada triángulo
o rectángulo por los círculos \(r_i\) e integrando \(N_a\) en las intersecciones.
Una cuadratura adaptativa es válida si cada columna se renormaliza a su área
geométrica y el refinamiento de cuadratura demuestra convergencia local. La
simple evaluación `p(r_centroid)` no es el operador de producción.

Para el cortante axisimétrico,

\[
\mathbf e_r=\left(\frac{x-x_c}{r},\frac{y-y_c}{r},0\right),\qquad
\mathbf f_a^\tau=\sum_i\int_\Gamma
N_a\chi_i\bar\tau_i\mathbf e_r\,dA.
\]

En \(r=0\), \(\tau_r=0\) por simetría y se usa el límite vectorial nulo; no se
evalúa \(1/r\). En el MVP de pared deslizante, el término cortante es cero.

## Superficie, áreas y nodos

1. Marcar puntos materiales que tengan una cara expuesta en la superficie
   inicial; congelar su identidad, pero actualizar la normal solo si se activa
   geometría grande en una etapa posterior.
2. Construir caras/triángulos de frontera y áreas tributarias sin contar caras
   internas entre recubrimiento y sustrato.
3. Integrar primero tracción sobre la cara y crear una condición puntual de
   Kratos por cuadratura. `POINT_LOAD` ya es fuerza en N; no usar `MPC_AREA=1`
   como si fuera un área física ni multiplicar la fuerza una segunda vez.
4. Verificar \(\sum_a A_a=\pi R_{map}^2\) en el disco común.

Fuera de `radial_edges[-1]`, la carga manométrica es cero. Si la superficie MPM
no cubre todo \(R_{map}\), se recorta también la integral Basilisk al área común.
No se prolonga el último valor radial.

## Sincronización temporal que conserva impulso

La historia fuente se reconstruye linealmente por tramos:

\[
p(t)=(1-\theta)p_k+\theta p_{k+1},\qquad
\theta=\frac{t-t_k}{t_{k+1}-t_k}.
\]

No produce sobreoscilación. Fuera del intervalo temporal se lanza error, salvo
que el archivo certifique explícitamente estados inicial y final descargados.
Para pasos MPM que no coinciden con los knots, se calcula el promedio exacto del
interpolante en el paso,

\[
p^{n+1/2}=\frac{1}{\Delta t_s}
\int_{t_n}^{t_{n+1}}p_{lin}(t)\,dt,
\]

de modo que el incremento de momento use el impulso correcto. Se registra además
la fuerza que vio cada paso real del integrador MPM. Reducir \(\Delta t_s\) debe
converger en pico estructural y trabajo externo.

## Comprobaciones y tolerancias

La referencia normal positiva en compresión es

\[
F_B(t)=\sum_i\bar p_i(t)A_i,
\qquad F_M(t)=-\sum_a\mathbf f_a(t)\cdot\mathbf n.
\]

Se aceptan

\[
e_F=\frac{\max_t|F_M-F_B|}{\max_t|F_B|}<1\%,
\qquad
e_J=\frac{|\int F_Mdt-\int F_Bdt|}
{\max(|\int F_Bdt|,J_{scale})}<1\%.
\]

Entre 1 y 2 % se emite advertencia y se refina cuadratura/tiempo; más de 2 %
falla. Las pruebas analíticas exigen \(10^{-10}\)–\(10^{-12}\). Cuando la fuerza
cruza cero se usa una escala global, no un error relativo punto a punto. El
trabajo externo también se audita, pero no puede “conservarse” entre una pared
rígida de velocidad cero y un sólido móvil; es una magnitud de respuesta.

El paquete ofrece dos rutas. `ConservativePressureOperator` aplica una matriz
\(M_{ai}\) precomputada y rechaza columnas que no sumen al área exacta: es el
núcleo de producción. `map_axisymmetric_load` evalúa promedios anulares en puntos
de cuadratura y elimina el residuo global con la corrección uniforme de norma L2
mínima; conserva fuerza e impulso y sirve para depuración, pero no demuestra
conservación local por anillo.

## Pseudocódigo: extracción de Basilisk

```text
event wall_loads(t = next_output_time):
    create accumulators sum_p[Nr], sum_tau[Nr], area[Nr]
    for each active leaf face on wall:
        r_interval = radial extent of face
        p_load = face_pressure - p_ref
        tau = viscous traction on face
        for each intersected radial bin i:
            dA = axisymmetric overlap area
            sum_p[i] += p_load * dA
            sum_tau[i] += tau * dA
            area[i] += dA
    MPI_reduce all accumulators
    assert area approximately pi*(r_outer^2-r_inner^2)
    write time, sum_p/area, sum_tau/area to temporary HDF5
    append mesh, EOS and convergence metadata
on successful completion:
    integrate impulse by trapezoids
    compute force from annular areas
    validate schema and atomically rename final file
```

## Pseudocódigo: promediado y operador geométrico

```text
for each source annulus i:
    for each target surface element e intersecting annulus i:
        polygon = intersect(element e, disk(r[i+1]))
                  minus intersect(element e, disk(r[i]))
        for each local shape function N_a on e:
            M[a,i] += integrate(N_a, polygon)
    assert abs(sum_a M[a,i] - A[i]) / A[i] < geometry_tolerance
store sparse M, mesh hash, axis origin and normal convention
```

## Pseudocódigo: reconstrucción y fuerzas

```text
read and validate HDF5; reject unknown major version
assert M was built for current surface mesh and R_map
load Kratos point-force HDF5 and match initial coordinates one-to-one
for each Kratos explicit step [TIME-DELTA_TIME, TIME]:
    f_step = exact_time_average(piecewise_linear_point_force, tn, tn1)
    for each MPMParticlePointLoadCondition a:
        SetValuesOnIntegrationPoints(POINT_LOAD, f_step[a])
    record source force, applied force, source/applied impulse
    abort if mapping-only error exceeds 2 percent
```

## Pseudocódigo: caso completo

```text
case = validate_yaml(case_config)
record git commits, compiler, container digest and configuration SHA-256
run basilisk spherical verification if baseline is absent
run basilisk rigid-wall case with checkpoint/restart
extract + validate wall-load HDF5
build/load conservative surface operator
run elastic Kratos MPMApplication case and collect supported outputs
run equivalent FEniCSx case
compare force, impulse, displacement and stress norms
publish manifest with commands, hashes, timings and pass/fail criteria
only if all MVP gates pass: enable plasticity case
```

## Pruebas unitarias obligatorias

- Presión uniforme: \(F=p\pi R^2\).
- \(p=p_0(1-r^2/R^2)\): \(F=\pi p_0R^2/2\).
- Pulso triangular y rectangular en tiempos no alineados: impulso exacto.
- AMR: no contar simultáneamente padres e hijos.
- Eje: sin NaN, cortante radial nulo.
- Rotación azimutal de la malla: fuerza invariante.
- Exterior: cero sin extrapolación.
- Signo: presión positiva produce fuerza opuesta a la normal exterior.
- Superficie parcial: conservación sobre el dominio común.
- Round-trip HDF5, unidades, versión, checksums y metadatos de producción.

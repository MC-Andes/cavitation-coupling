# Implementación, estudio paramétrico y publicación

## Arquitectura modular

```text
project/
├── basilisk/
│   ├── cases/                 # entradas C: colapso esférico y pared rígida
│   ├── eos/                   # auditorías y tests de EOS; no forks ocultos
│   ├── postprocessing/        # extracción de interfaz, pared y energías
│   └── validation/            # RP/Keller–Miksis, pulso y convergencia
├── coupling/
│   ├── schemas/               # contrato HDF5 versionado
│   └── tests/                 # fixtures cruzados Basilisk/Kratos
├── src/cavitation_coupling/   # I/O, mapeo, conservación y CLI reutilizables
├── mpm/
│   ├── kratos/                # Process HDF5 y fragmentos ProjectParameters
│   ├── material_models/       # solo modelos nuevos y sus tests
│   ├── cases/                 # elástico, plástico y gradado
│   └── validation/            # onda 1-D, impulso, indentación y energías
├── experiments/               # metadatos y enlaces a datos, no binarios grandes
├── examples/                  # ejemplos sintéticos ejecutables
├── results/                   # ignorado; manifiestos publicables van a Zenodo
├── scripts/                   # lanzadores delgados, sin lógica científica oculta
├── docs/                      # formulación, decisiones, V&V y publicación
└── provenance/                # commits, toolchains y contenedores fijados
```

Cada caso se configura en YAML validado por JSON Schema. Entrada: geometría,
materiales, solver, tolerancias y semillas. Salida: directorio inmutable con
configuración resuelta, hashes, logs, HDF5, métricas y estado pass/fail. El
workflow nunca deduce un parámetro científico del nombre de un directorio.

## Etapas y puertas de aceptación

### A. Verificación de Basilisk

- Colapso esférico 1-D/2-D contra Rayleigh–Plesset y Keller–Miksis.
- Burbuja estática de Laplace y oscilación pequeña con tensión superficial.
- Propagación/reflexión/transmisión de un pulso acústico.
- Masa de cada fase, energía total y \(p_gV^\Gamma\).
- Niveles 12–16, CFL y tamaño de dominio.

**Puerta:** error de tiempo de colapso <2 %, tendencia asintótica de \(R(t)\),
balances explicados y sin reflexión de frontera en la ventana útil.

### B. Cavidad cerca de pared rígida

- \(\gamma=1.1,1.5,1.9\), forma, impacto, \(u_j,d_j\).
- Presión radial, FWHM, sensor equivalente, fuerza e impulso.
- Comparación morfológica/temporal con Dular y escalados de Supponen; presión con
  datos que realmente usen sensores de pared.

**Puerta:** chorro y tiempo convergentes; impulso cambia <2 % entre las dos mallas
más finas. El pico se reporta como función de sensor y malla.

### C. Verificación de MPM

- Barra/medio elástico 1-D: velocidad y reflexión de onda.
- Semiespacio o placa bajo presión analítica.
- Johnson–Cook uniaxial y pulso plástico antes de 3-D; J2 solo tras verificar
  compatibilidad con MPMApplication.
- Momento, energías nativas de Kratos y trabajo externo del adaptador.

**Puerta:** orden/tendencia esperados, error de onda <2 % en ROI y residuo de
energía <2 % antes del retorno de ondas por las fronteras.

### D. Acoplamiento offline (MVP publicable)

- Exportar HDF5, construir \(M_{ai}\), aplicar carga al sólido elástico.
- Fuerza e impulso del mapeo <1 %.
- Comparar Kratos MPM con FEniCSx en desplazamientos y tensiones filtradas a una
  resolución común.

**Puerta:** diferencias <5 % en desplazamiento máximo y energía elástica, y
convergencia de norma \(L_2\); las singularidades puntuales no se comparan.

### E. Recubrimiento elastoplástico gradado

- Sustrato, \(h_c\), perfiles Al–316L e igual masa areal.
- elasticidad → Johnson–Cook nativo → daño nuevo, una complejidad por vez.
- Interfaz perfectamente adherida primero; cohesiva solo con datos.

**Puerta:** cada nuevo modelo reproduce sus cupones/benchmarks y la respuesta
elástica previa en su límite.

### F. DOE y mapa de regímenes

Clasificar: elástico; plasticidad localizada; cráter residual; daño iniciado;
falla constitutiva. “Remoción” y “erosión acumulada” quedan fuera salvo validación
experimental explícita.

## Diseño de experimentos secuencial

No se cruza desde el inicio toda incertidumbre fluida con toda incertidumbre
material.

1. **Fluido:** 3 valores de \(\gamma\) × 3 de \(p_{g0}/p_\infty\), más réplicas
   numéricas de nivel/CFL en tres puntos: 15 casos físicos y 12–18 de convergencia.
2. **Elástico:** factorial pequeño \(h_c/R_0=\{0.06,0.15,0.30,0.61\}\), perfil
   homogéneo/creciente/decreciente y \(n=1\) donde aplica, para dos cargas: 20
   configuraciones tras eliminar duplicados.
3. **No lineal:** Latin hypercube máximo-proyección de 48–64 puntos en
   \(h_c/R_0,n,Z_{sup}/Z_l,\sigma_y,p_{g0},\gamma\) y parámetros de tasa. Se
   añaden 10 puntos de validación fuera del entrenamiento.
4. **Adaptación:** un proceso gaussiano o polynomial chaos identifica frontera
   entre regímenes; se agregan lotes de 8 puntos donde la entropía de clasificación
   sea mayor.
5. **Incertidumbre:** 200–1000 evaluaciones del surrogate para Sobol/intervalos;
   5–10 simulaciones directas confirman colas críticas.

Se bloquean previamente variables de proceso no identificables. El muestreo,
semilla y matriz exacta se versionan. Las comparaciones de igual masa y de igual
espesor son dos bloques distintos.

## Variables de salida y clasificación

| Fluido | Sólido |
| --- | --- |
| \(R(t)/R_0\), interfaz, \(t_c\) | desplazamiento máximo y residual |
| \(u_j,d_j\), tiempo de impacto | profundidad/radio de cráter geométrico |
| pico y FWHM por sensor | \(\bar\varepsilon_p\), tasa máxima |
| \(I(r),F_z(t),\int F_zdt\) | tensiones principales y triaxialidad |
| energía cinética/compresible | daño, volumen dañado y estado de interfaz |
| balances de masa/energía | energías elástica, plástica, viscosa y cinética |

- **Daño iniciado:** variable alcanza el umbral calibrado en volumen finito.
- **Craterización:** desplazamiento residual medible, aun sin daño.
- **Falla constitutiva:** el modelo pierde capacidad portante según su ley.
- **Remoción:** separación geométrica/másica demostrada, no mero `D=1`.
- **Erosión acumulada:** pérdida por población de impactos y evolución material;
  requiere múltiples colapsos y calibración.

## Costo computacional preliminar

Son rangos de planificación, no benchmarks. Se reemplazan por tiempos medidos en
la etapa A y se publican hardware, eficiencia y energía de cómputo.

| Etapa/caso | Recursos orientativos | Costo por caso | Almacenamiento útil |
| --- | --- | ---: | ---: |
| A: esférico/onda | 1–32 CPU, minutos–2 h | 1–50 core-h | <2 GB |
| B: axi nivel 14 | 64–256 CPU, 2–8 h | 128–2048 core-h | 5–30 GB |
| B: axi nivel 15/16 | 128–512 CPU, 8–48 h | 1000–25000 core-h | 20–150 GB |
| C/D: Kratos MPM elástico 100 µm | 1 nodo OpenMP; medir antes de escalar | por determinar con benchmark | 10–80 GB |
| D: FEniCSx lineal | 16–128 CPU, 0.5–4 h | 8–512 core-h | 2–20 GB |
| E: MPM 50 µm/no lineal | no estimado hasta validar constitutivo y escalado | por determinar | 50–500 GB |
| F: campaña | arreglos de 48–100 casos | \(10^5{-}10^6\) core-h | 2–20 TB crudos |

No se guardan dumps completos en cada paso. Se retienen checkpoints espaciados,
campos en ventanas de impacto, métricas reducidas y cargas HDF5; la política de
retención se define antes de enviar el barrido.

## Ejecución HPC reproducible

- Compilar Basilisk y ejecutar Kratos 10.4.3 en un contenedor Linux reproducible;
  fijar commit, paquetes, compilador y número de hilos OpenMP. MPMApplication no
  se presenta como ruta MPI soportada en la release auditada.
- Ejecutar una prueba corta en el nodo de login solo para configuración; usar
  Slurm job arrays por matriz de casos.
- Escribir checkpoints a scratch local, copiar atómicamente artefactos completos
  y verificar SHA-256.
- Reanudar por ID de caso; nunca sobrescribir una corrida completa.
- Reducir cargas y métricas dentro del job para evitar I/O masivo.
- Registrar tiempo de pared, core-h, memoria máxima, pasos, celdas/partículas y
  razón de fallas.
- Publicar scripts, configs y fixtures pequeños en Git; datos grandes con DOI y
  manifiesto de hashes.

## Estructura propuesta del artículo

1. **Introducción:** daño por un colapso, gradación de impedancia y vacío de
   acoplamiento reproducible.
2. **Pregunta e hipótesis:** alcance de pared rígida y gas de masa fija.
3. **Método fluido:** all-Mach VOF, EOS, dominio, AMR y extracción.
4. **Transferencia:** HDF5, operador \(M_{ai}\), conservación y sincronización.
5. **Método sólido:** Kratos MPMApplication, dominio, constitutivo y gradación.
6. **Verificación/validación:** solvers separados, mapping y FEniCSx.
7. **Diseño paramétrico e incertidumbre.**
8. **Resultados:** carga convergida, respuesta elástica, plasticidad y mapa de
   regímenes.
9. **Discusión:** mecanismos de onda, tasa, fabricabilidad y límites de
   acoplamiento.
10. **Conclusiones y datos/código disponibles.**

La primera versión puede terminar tras la respuesta elastoplástica sin daño si
la calibración no es defendible. Es preferible un resultado limitado y verificado
a una afirmación de erosión sin sustento.

## Figuras de publicación

1. Geometría, ejes, \(R_0,H,h_c,R_{map}\) y flujo de datos.
2. Auditoría EOS: \(p,e,c\) y estado inicial de ambas fases.
3. \(R(t)/R_0\) contra RP/Keller–Miksis y convergencia de \(t_c\).
4. Secuencia de interfaz/chorro cerca de pared con resolución AMR.
5. Mapa \(p_w(r,t)\), fuerza total y ventana del pulso.
6. Pico e impulso frente a nivel, CFL y diámetro de sensor.
7. Error de columnas de \(M\), fuerza e impulso del mapeo.
8. Benchmark de onda MPM y comparación MPM–FEM del MVP.
9. Perfiles \(\rho,E,\nu,Z,\sigma_y\) y masa areal de cada gradación.
10. Campos 3-D de desplazamiento, plasticidad y energía por perfil.
11. Diagrama de reflexión/transmisión y series en interfaces.
12. Mapa de regímenes con intervalos de incertidumbre y frontera del surrogate.

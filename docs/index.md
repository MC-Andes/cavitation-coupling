# Estrategia técnica y producto mínimo viable

## Resultado perseguido

El estudio cuantificará cómo el espesor y una gradación **materialmente
realizable** de impedancia modifican la transición elástica → plástica → daño
incipiente causada por un colapso individual. La primera publicación no afirmará
predecir erosión acumulada ni pérdida de masa sin calibración de falla y ensayos
de múltiples colapsos.

![Flujo de datos Basilisk a MPM](assets/data-flow.svg)

El acoplamiento es secuencial:

\[
\text{Basilisk}\longrightarrow
\{\bar p_w(r,t)-p_{\mathrm{ref}},\,\bar\tau_r(r,t),\,I(r)\}
\longrightarrow\text{MPM}.
\]

La barra superior denota promedio por área anular. La deformación del sólido no
regresa a Basilisk.

## MVP verificable

1. Reproducir en Basilisk el colapso esférico compresible y luego una cavidad
   gaseosa axisimétrica cerca de una pared rígida.
2. Exportar a HDF5 presión manométrica y tracción, conservando bordes de los
   anillos, unidades, resolución y procedencia.
3. Integrar la carga sobre condiciones puntuales de la superficie MPM, usando
   áreas anulares en el caso axisimétrico o áreas tributarias en 3-D, y exigir
   errores de fuerza e impulso menores a 1 %.
4. Resolver un recubrimiento y sustrato **linealmente elásticos** con Kratos
   Multiphysics MPMApplication 10.4.3.
5. Ejecutar el mismo sólido y carga en FEniCSx, con malla y dominio independientes,
   y comparar desplazamiento, tensión y energía antes de añadir plasticidad.

El paquete Python ya implementa el contrato HDF5, la tabla de fuerzas para
Kratos, el promedio temporal exacto por paso y una cuadratura globalmente
conservativa. Para producción se
precomputará la matriz de intersección anillo–parche descrita en
[Transferencia conservativa](coupling.md); la corrección mínima L2 incluida en
el helper actual es un verificador y una ruta de depuración, no sustituye el
estudio de convergencia local del operador.

## Hipótesis y simplificaciones

| Decisión | Consecuencia controlada |
| --- | --- |
| Una cavidad aislada | Elimina interacción entre burbujas, núcleos y nubes; no representa cavitación desarrollada. |
| Gas de masa fija, sin cambio de fase | El MVP no reproduce condensación de una burbuja de vapor. `p_{g0}` y la masa no condensable son incertidumbres. |
| Pared plana y rígida en CFD | La presión no responde al desplazamiento ni a la impedancia del recubrimiento. |
| Axisimetría en CFD | Excluye inestabilidades azimutales, rugosidad y chorros oblicuos; la carga alimenta el MVP MPM axisimétrico y una extensión 3-D. |
| Acoplamiento unidireccional | Es válido solo mientras movimiento, velocidad y escala temporal de la pared no alteren de forma apreciable el hueco o el impacto. |
| Un colapso | Permite hablar de deformación residual, daño incipiente o potencial de erosión; no de tasa de erosión. |

La pared inicialmente plana no implica que el sólido sea infinitamente rígido:
esa hipótesis solo pertenece a la etapa fluida. Su dominio de validez se audita
con los criterios de [Verificación y riesgos](verification.md#validez-del-acoplamiento-unidireccional).

## Preguntas falsables

- A masa areal fija, ¿un perfil creciente de impedancia reduce la amplitud de la
  onda reflejada en la superficie y la deformación plástica equivalente frente a
  un recubrimiento homogéneo?
- ¿Existe un espesor óptimo relativo a la duración del pulso,
  \(h_c/(c_L\tau_p)\), y no solo relativo a \(R_0\)?
- ¿Cambia el orden de desempeño cuando el tiempo de relajación hace
  \(De=\tau_{\mathrm{relax}}/t_R\) de orden uno?
- ¿Son robustas esas tendencias ante incertidumbre de alta tasa y ante el tamaño
  equivalente del sensor usado para definir el pulso?

## Cobertura de los entregables

| Entregable | Ubicación |
| --- | --- |
| Resumen, hipótesis y diagrama | esta página |
| Ecuaciones, fronteras y parámetros | [Problema físico y Basilisk](physics.md) |
| Selección del código y constitutivos | [Selección y modelo MPM](mpm.md) |
| Algoritmo, HDF5 y pseudocódigo | [Transferencia conservativa](coupling.md) |
| Etapas, DOE, costos, artículo y figuras | [Implementación y publicación](implementation.md) |
| Matriz V&V, convergencia, riesgos | [Verificación y riesgos](verification.md) |
| Versiones y ejecución | [Reproducibilidad](reproducibility.md) |
| DOI y enlaces verificables | [Referencias](references.md) |

## Visualización

`visualization/paraview/` convierte cualquier HDF5 v1 en una animación VTK de
presión, un mapa radial–tiempo y una historia de fuerza. El ejemplo sintético
incluye una escena reproducible para ParaView 6.1; los mismos artefactos se
generarán sin cambiar el esquema cuando existan resultados Basilisk.

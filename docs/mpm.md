# Selección del código y modelo MPM

## Decisión actual: Kratos Multiphysics MPMApplication

Por decisión del proyecto se sustituye Uintah por
[Kratos MPMApplication 10.4.3](https://github.com/KratosMultiphysics/Kratos/tree/v10.4.3/applications/MPMApplication).
La release auditada ofrece integración explícita, formulaciones axisimétricas y
3-D, condiciones de grid y de puntos materiales, salida VTK y leyes elásticas y
Johnson–Cook térmicas propias de la aplicación. Es BSD-4-Clause y se distribuye
como wheel Linux x86-64; el commit y los paquetes exactos están en
`provenance/solvers.lock.yml`.

La selección no convierte en capacidades verificadas todas las leyes presentes
en otras aplicaciones de Kratos. Maxwell, un J2 genérico y modelos de daño deben
probar compatibilidad con los elementos MPM, la actualización explícita y sus
variables internas antes de incorporarse. Tampoco se atribuyen a la release una
frontera absorbente MPM o eliminación de puntos por daño sin un benchmark.

## Condición de carga implementada

La API oficial distingue:

- cargas de punto, línea y superficie sobre el grid de fondo;
- condiciones de partícula móviles, cuya ruta Neumann implementada es
  `MPMParticlePointLoadCondition`.

El generador de condiciones indica que las cargas distribuidas de línea y
superficie sobre partículas todavía no están implementadas. Para una condición
puntual fija `MPC_AREA=1` y `POINT_LOAD` es una fuerza total, no una presión. El
adaptador implementado crea una cuadratura superficial de condiciones `Point3D`,
integra externamente $p(r,t)$ por sus áreas tributarias y actualiza cada
`POINT_LOAD` en N con un `Process` Python.

Estas semánticas se verificaron en el
[generador oficial de condiciones](https://github.com/KratosMultiphysics/Kratos/blob/v10.4.3/applications/MPMApplication/custom_utilities/material_point_generator_utility.cpp)
y en el
[proceso Neumann oficial](https://github.com/KratosMultiphysics/Kratos/blob/v10.4.3/applications/MPMApplication/python_scripts/apply_mpm_particle_neumann_condition_process.py).

Esta elección mantiene las cargas unidas a puntos materiales y evita depender
de una cara particular del grid. El proceso empareja por coordenadas iniciales,
no por orden o ID generado, y usa la superficie inicial: la fuerza es muerta, no
*follower*, coherente con la pared rígida de Basilisk.

## Axisimetría y 3-D

Kratos dispone de elementos, elasticidad y Johnson–Cook axisimétricos para MPM
explícito. Por ello el MVP elástico será axisimétrico 2-D: cada punto de la línea
superficial recibe un área anular $2\pi r\,dr$ ya incluida en su fuerza. No se
usa además la condición axisimétrica de grid, porque duplicaría el factor
$2\pi r$.

La extensión 3-D usa exactamente el mismo archivo y proceso, pero con parches
tributarios sobre el disco. Se requiere para defectos no axisimétricos, chorros
oblicuos y daño localizado. PQMPM no se considera disponible en axisimetría hasta
que un benchmark de la release seleccionada demuestre lo contrario.

## Formulación estructural

MPM resuelve, en la configuración actual,

\[
\rho_s\ddot{\mathbf u}=\nabla\cdot\boldsymbol\sigma+\rho_s\mathbf b,
\]

mediante transferencia partícula→grid, actualización explícita del momento y
grid→partícula. El trabajo externo discreto se calcula con la misma fuerza que
recibe el integrador:

\[
W_{ext}=\int\sum_a\mathbf f_a(t)\cdot\mathbf v_a(t)\,dt.
\]

Con un pulso extremadamente corto, el paso estable es

\[
\Delta t_s\le C_s\frac{\Delta x_s}
{\max(c_L+|\mathbf v|)},\qquad C_s=0.4\ \text{inicial},
\]

y además se exigen al menos 20 pasos por ancho a media altura del pulso. La carga
se interpola linealmente en los tiempos MPM; nunca se extrapola ni se ajusta con
splines.

## Dominio y discretización del MVP

| Elemento | Base | Convergencia/criterio |
| --- | ---: | --- |
| Radio del sólido axisimétrico | 10 mm | 8, 10 y 12 mm; la onda reflejada no debe llegar a la ROI en la ventana analizada. |
| Profundidad | 12 mm | 8, 12 y 16 mm; misma condición. |
| Recubrimiento | 0.50 mm | 0.10, 0.25, 0.50 y 1.00 mm en extensión. |
| Celda MPM | 100 µm | 200, 100 y 50 µm; mínimo 5 celdas en el recubrimiento cuando aplique. |
| Puntos/celda | 8 | 1, 8 y 27; registrar patrón inicial. |
| Paso estimado | 6–8 ns para \(c_{max}\sim5{-}6\) km/s | CFL y 20 pasos/FWHM; usa el \(c_L\) máximo local real. |
| Ventana estructural | 0–3 µs tras impacto | extender a 5 µs solo con fronteras verificadas. |

La cara superior fuera de \(R_{map}\) es libre. No se presupone una frontera
absorbente nativa en Kratos MPM: el MVP usa un dominio suficientemente grande y
termina la ventana de interés antes del retorno de la primera reflexión. Una
extensión podrá añadir dashpots solo después de calibrarlos con una onda 1-D. El
caso axisimétrico es la referencia primaria; la verificación 3-D completa se
activa para mecanismos que rompan esa simetría.

El primer gradado se aproxima por capas MPM con `Properties` distintas y nodos de
material coincidentes. Se aumenta el número de capas hasta que las magnitudes de
interés converjan; no se presupone que la release asigne una ley continua a cada
punto por profundidad. El desprendimiento requiere después una interfaz cohesiva
calibrada y no se simula convirtiendo sin más la unión en contacto con fricción.

## Escalera constitutiva

### Nivel 1: elasticidad

\[
\boldsymbol\sigma=\lambda\,\mathrm{tr}(\boldsymbol\varepsilon)\mathbf I
+2G\boldsymbol\varepsilon,
\quad G=\frac{E}{2(1+\nu)},\quad
K=\frac{E}{3(1-2\nu)}.
\]

El MVP usa aluminio homogéneo nominal
\(\rho=2700\ \mathrm{kg\,m^{-3}}\), \(E=68.9\ \mathrm{GPa}\),
\(\nu=0.33\), tanto en MPM como en FEniCSx. Estos números verifican transferencia;
no representan aún una capa cold-sprayed calibrada.

### Nivel 2: plasticidad dependiente de tasa

La primera ley no lineal candidata es `JohnsonCookThermalPlastic` de
MPMApplication explícito, solo si existen curvas del material **fabricado** a las
tasas y temperaturas relevantes. Un J2 genérico de otra aplicación Kratos no se
usará hasta verificar su compatibilidad con el elemento MPM:

\[
\sigma_y=(A+B\bar\varepsilon_p^n)
\left[1+C\ln\left(\frac{\dot{\bar\varepsilon}_p}{\dot\varepsilon_0}\right)\right]
(1-T^{*m}).
\]

Los parámetros necesarios son \(A,B,n,C,m,\dot\varepsilon_0\), calor específico,
fracción Taylor–Quinney y respuesta térmica. Si no se dispone de alta tasa, se
tratan como variables inciertas y no se usa el modelo para validar erosión.
Joshi et al. encontraron diferencias de deformación plástica de hasta 60 % al
ignorar la tasa en acero dúplex; esto justifica la etapa, no suministra parámetros
para otro material.

### Nivel 3: daño o viscoelasticidad

Para metal, un daño de energía regularizada o Johnson–Cook calibrado puede activar
iniciación, pero es desarrollo nuevo para esta integración y la eliminación de
puntos se pospone. El tamaño característico y la energía de fractura deben impedir
que la disipación tienda a cero con la malla. Se reportan por separado iniciación
de daño, falla constitutiva y remoción.

Para polímero, una futura rama requerirá implementar y verificar Maxwell
generalizado,

\[
G(t)=G_\infty+\sum_{k=1}^{N}G_k e^{-t/\tau_k},
\qquad G_k>0,\quad\tau_k>0,
\]

calibrado con DMA/relajación y datos de alta frecuencia. Viscoelasticidad,
plasticidad y daño solo se combinan a partir de una energía libre y un potencial
de disipación comunes o de un modelo publicado e implementado como unidad. La
suma informal de tres modelos independientes no es termodinámicamente admisible.

## Gradación de impedancia realizable

La impedancia longitudinal local es

\[
Z(z)=\rho(z)c_L(z),\qquad
c_L(z)=\sqrt{\frac{K(z)+4G(z)/3}{\rho(z)}}.
\]

La primera familia fabricable es Al–316L obtenible por deposición gradual/cold
spray. Los extremos nominales de *screening* son:

| Constituyente | \(\rho\) (kg m\(^{-3}\)) | \(E\) (GPa) | \(\nu\) | Nota |
| --- | ---: | ---: | ---: | --- |
| Al 6061 | 2700 | 68.9 | 0.33 | superficie de baja impedancia; propiedades reales cambian con cold spray. |
| 316L | 8000 | 193 | 0.30 | extremo compatible con sustrato; fluencia depende de proceso/tasa. |

No se interpola \(Z\) de forma abstracta. Con fracción de acero
\(v(z)=(z/h_c)^n\) para gradación creciente,

\[
\rho=(1-v)\rho_{Al}+v\rho_{SS},
\]

\[
K=\tfrac12\left[(1-v)K_{Al}+vK_{SS}+
\left(\frac{1-v}{K_{Al}}+\frac{v}{K_{SS}}\right)^{-1}\right],
\]

y análogamente para \(G\) (promedio Voigt–Reuss–Hill). Luego

\[
E=\frac{9KG}{3K+G},\qquad
\nu=\frac{3K-2G}{2(3K+G)}.
\]

Con constituyentes estables y \(0\le v\le1\), \(\rho,K,G,E>0\) y
\(-1<\nu<0.5\). La gradación decreciente usa
\(v=1-(z/h_c)^n\); debe advertirse que termina en un salto de impedancia con un
sustrato 316L. \(n=0.5,1,2,4\) produce perfiles comparables. Fluencia,
endurecimiento, porosidad y adhesión **no** se obtienen de Voigt–Reuss–Hill: se
miden en cupones por profundidad o se propagan como intervalos.

Se comparan:

- homogéneo con la misma masa areal \(m_A=\int_0^{h_c}\rho(z)dz\);
- creciente y decreciente con los mismos constituyentes;
- exponentes \(n\) y espesores \(h_c/R_0\);
- masa fija ajustando \(h_c=m_A/\bar\rho\), y espesor fijo en un bloque separado.

Esto evita confundir el efecto de impedancia con añadir simplemente más masa.

## Parámetros adimensionales

| Grupo | Interpretación |
| --- | --- |
| \(h_c/R_0\) | geometría recubrimiento–burbuja. |
| \(Z_{sup}/Z_l\), \(Z_{sub}/Z_{sup}\) | transmisión y reflexión. |
| \(p_{max}/\sigma_y\) | propensión instantánea a fluencia, no suficiente si el pulso es corto. |
| \(I_p/(\rho_sc_LR_0)\) | impulso **local de presión** adimensional; la expresión original es dimensionalmente correcta. |
| \(J_F/(\rho_sc_LR_0^3)\) | impulso de fuerza total adimensional. |
| \(De=\tau_{relax}/t_R\) | relajación respecto al colapso. |
| \(\Lambda=h_c/(c_L\tau_p)\) | espesor respecto a la distancia recorrida durante el pulso. |
| \(t_Rc_L/R_0\) | separación de escalas fluido–sólido. |

\(p_{max}/\sigma_y\) gobierna inicio de plasticidad; el impulso y \(\Lambda\)
controlan amplitud/deformación y reflexiones; \(De\) controla disipación
viscoelástica. Daño necesita además triaxialidad, tasa, energía y longitud
característica.

# Problema físico y modelo de fluido

## Geometría y escalas

Se usan coordenadas \((r,z)\), con pared en \(z=0\), eje de simetría en
\(r=0\) y centro inicial de la cavidad en \((0,H)\). El radio inicial es el
radio máximo experimental \(R_0\), la velocidad inicial es cero y
\(\gamma=H/R_0\). Para \(\gamma>1\) la esfera no corta la pared. La carga
axisimétrica se reconstruye en el sólido como

\[
p(x,y,t)=p\!\left(\sqrt{(x-x_c)^2+(y-y_c)^2},t\right).
\]

La escala de Rayleigh del caso base es

\[
U_R=\sqrt{\frac{p_\infty-p_{g0}}{\rho_l}},\qquad
t_R=0.915R_0\sqrt{\frac{\rho_l}{p_\infty-p_{g0}}}.
\]

Con los valores de la tabla inferior, \(U_R\simeq9.96\ \mathrm{m\,s^{-1}}\) y
\(t_R\simeq151.6\ \mu\mathrm{s}\), coherente con los \(147\ \mu\mathrm{s}\)
medidos para una burbuja de diámetro máximo cercano a 3.3 mm por Dular et al.

## Ecuaciones de Basilisk

El punto de partida es `compressible/two-phase.h`, el solver all-Mach de
Fuster y Popinet. Para cada fase \(k\), sin transferencia de masa,

\[
\partial_t(\alpha_k\rho_k)+
\nabla\!\cdot(\alpha_k\rho_k\mathbf u)=0,
\]

\[
\partial_t(\rho\mathbf u)+
\nabla\!\cdot(\rho\mathbf u\otimes\mathbf u)
=-\nabla p+\nabla\!\cdot\boldsymbol\tau+\mathbf f_\sigma,
\]

\[
\partial_t\{\alpha_k\rho_k(e_k+|\mathbf u|^2/2)\}
+\nabla\!\cdot\{\alpha_k\rho_k\mathbf u(e_k+|\mathbf u|^2/2)\}
=-\alpha_k\nabla\!\cdot(p\mathbf u)
+\alpha_k\nabla\!\cdot(\boldsymbol\tau\mathbf u),
\]

\[
\partial_t f+\mathbf u\cdot\nabla f=0,
\qquad \alpha_l=f,\quad\alpha_g=1-f.
\]

La interfaz se sigue con VOF y el salto capilar con
`compressible/tension.h`. La tensión newtoniana es

\[
\boldsymbol\tau=\mu(\nabla\mathbf u+\nabla\mathbf u^T)
+\lambda_v(\nabla\cdot\mathbf u)\mathbf I.
\]

La primera EOS será stiffened-gas, implementada mediante
`compressible/Mie-Gruneisen.h`,

\[
\rho e=\frac{p+\Gamma\Pi}{\Gamma-1},\qquad
c^2=\Gamma\frac{p+\Pi}{\rho}.
\]

Para el gas se toma \(\Pi_g=0\). Antes de adoptar NASG se probarán de forma
unitaria presión, energía y velocidad del sonido contra la EOS analítica: la
revisión actual de `NASG.h` incluye el covolumen \(b\) en una función de
compresibilidad, pero su función de velocidad del sonido requiere auditoría.
También se documentarán los términos viscosos que el propio solver marca como
incompletos. No se cambiará de EOS en mitad de la campaña sin una decisión
registrada.

La auditoría EOS es una puerta ejecutable, no una lista informal. Para cada fase
se verifican: unidades y presión absoluta; \(p_0,T_0,\rho_0\); \(e_0\) calculada
por la misma EOS; \(c_0\) por derivada termodinámica y por la función del código;
\(\Gamma,\Pi\); y, si se usa NASG, \(b,q,c_v\) y la referencia de energía. Se
comprueba \(1-b\rho>0\), positividad de \(c^2\), salto capilar inicial y masa de
gas. Cambiar \(q\) sin cambiar consistentemente la energía total es un fallo.

## Tres modelos que no deben confundirse

| Modelo | Masa de la cavidad | Física necesaria | Estado en este proyecto |
| --- | --- | --- | --- |
| Gas no condensable | fija | EOS de gas + compresibilidad líquida | **MVP**; cavidad gaseosa idealizada. |
| Vapor puro | cambia | transferencia de masa, calor latente y no equilibrio interfacial | no implementado. |
| Vapor + gas no condensable | vapor cambia; gas no | dos especies, difusión y transferencia de fase | extensión posterior, solo tras V&V separada. |

`thermal.h` añade conducción y acopla presión–temperatura, pero el método
publicado no modela transferencia de masa. Por ello, usar \(p_{g0}\) cercano a la
presión de vapor no convierte el MVP en una simulación de condensación.

## Caso base propuesto

Los valores marcados **E** proceden del experimento de Dular et al.; **I** de
IAPWS a 293.15 K y 0.1 MPa; **D** es una decisión de diseño que debe someterse a
sensibilidad.

| Magnitud | Valor base | Fuente/justificación |
| --- | ---: | --- |
| \(R_0\) | 1.65 mm | **E:** diámetro máximo hasta 3.3 mm. |
| \(\gamma\), \(H\) | 1.50; 2.475 mm | **D:** esfera separada; barrer 1.1, 1.5, 1.9. |
| \(T_0\) | 293.15 K | **D:** agua ambiente; coincide con propiedades IAPWS. |
| \(p_\infty\) | 101325 Pa absoluto | **D:** ambiente. |
| \(p_{g0}\) | 2339 Pa absoluto | **D:** caso efectivo de baja presión; barrer 0.02, 0.05 y 0.10 \(p_\infty\). |
| \(\rho_l\) | 998.207 kg m\(^{-3}\) | **I:** IAPWS-95. |
| \(c_l\) | 1482.35 m s\(^{-1}\) | **I:** IAPWS-95. |
| \(\mu_l\) | \(1.0016\times10^{-3}\) Pa s | **I:** IAPWS viscosity formulation. |
| \(\sigma\) | 0.07274 N m\(^{-1}\) | **I:** IAPWS surface-tension release. |
| \(\Gamma_l,\Pi_l\) | 7.15; \(3.067\times10^8\) Pa | **D:** ajusta \(c_l\) al estado inicial; verificar \(p,e,c\). |
| \(\Gamma_g,\Pi_g\) | 1.4; 0 Pa | **D:** gas ideal efectivo. |
| \(\rho_{g0}\) | 0.0278 kg m\(^{-3}\) | **D:** aire ideal compatible con \(p_{g0},T_0\), no valor libre. |
| Dominio \(L_r=L_z\) | \(100R_0=0.165\) m | **D:** retrasa retorno acústico; comparar \(80,100,120R_0\). |
| Niveles AMR | min 6, max 15 | **D:** \(\Delta_{min}=5.04\ \mu\)m; convergencia 14/15/16. |
| CFL / `CFLac` | 0.4 / 1.0 | **D:** sensibilidad `CFLac` 0.5, 1, 2. |
| Tiempo final | \(1.3t_R\approx197\ \mu\)s | captura impacto y primer rebote temprano antes de reflexión. |

El tiempo acústico de ida y vuelta del dominio \(100R_0\) es aproximadamente
223 µs. La corrida debe terminar antes, crecer a \(120R_0\), o demostrar una
condición no reflectante con una prueba de pulso. Un dominio pequeño con presión
Dirichlet no es aceptable por conveniencia computacional.

Los grupos iniciales son \(Re=\rho_lU_RR_0/\mu_l\approx1.64\times10^4\),
\(We=\rho_lU_R^2R_0/\sigma\approx2.25\times10^3\) y
\(Ma=U_R/c_l\approx6.7\times10^{-3}\). El Mach global pequeño no elimina la
necesidad de compresibilidad durante el impacto local.

## Inicialización y condiciones de frontera

- **Pared \(z=0\):** \(u_n=0\), deslizamiento libre para el MVP y gradiente
  normal compatible de presión. Esto permite verificar primero la carga normal.
  La extracción de cortante físico se habilita después con no deslizamiento y un
  estudio específico de resolución normal.
- **Eje \(r=0\):** simetría, \(u_r=0\), derivadas radiales nulas de escalares.
- **Lejos de la burbuja:** \(p=p_\infty\) y condición de salida/inflow consistente
  del solver; la reflexión se mide con un pulso acústico.
- **Interfaz inicial:** VOF esférico, \(\mathbf u=0\). En vez de imponer
  \(p_\infty\) uniformemente alrededor de una cavidad a baja presión, se resuelve
  una inicialización de Laplace con \(p_l=p_{g0}-2\sigma/R_0\) en la interfaz,
  \(p=p_\infty\) lejos y \(\partial_n p=0\) en la pared. Se compara con la
  inicialización del test oficial `test/bubble.h`.

La discrepancia de presión es deliberada: representa el instante de radio máximo,
con velocidad cero pero aceleración de colapso no nula. Masa, energía y entropía
adiabática del gas se registran desde el primer paso para detectar el transitorio
espurio.

## Refinamiento y control temporal

Se adapta con indicadores adimensionalizados de \(f\), \(p\), \(\rho\),
\(|\mathbf u|\) y vorticidad. Una banda de pared y todas las celdas interfaciales
se fuerzan a nivel alto durante impacto. Las tolerancias iniciales son
\(10^{-3}\) para \(f\) y \(p/(p_\infty-p_{g0})\), y \(10^{-2}\) para
\(\mathbf u/U_R\); no son resultados calibrados. Se ajustan con un estudio donde
\(t_c\), velocidad de chorro, presión promediada por sensor e impulso cambien
menos de 2 % entre los dos niveles más finos.

La salida de cargas debe resolver al menos 20 muestras dentro de la duración a
media altura del pulso. El impacto de Dular dura cerca de 0.4 µs; como punto de
partida se exporta cada 20 ns dentro de una ventana activada por presión/velocidad
y cada 0.5 µs fuera de ella. Siempre se guardan los pasos reales de Basilisk
necesarios para integrar impulso; no se rellena un pulso submuestreado por spline.

## Magnitudes de pared y chorro

En cada cara de pared se evalúa

\[
\mathbf t=\boldsymbol\sigma_f\mathbf n
=-p\mathbf n+\boldsymbol\tau\mathbf n,
\qquad p_{load}=p_w-p_{ref}.
\]

Las caras se acumulan en anillos de bordes \([r_i,r_{i+1}]\):

\[
\bar p_i(t)=\frac{2}{r_{i+1}^2-r_i^2}
\int_{r_i}^{r_{i+1}}p_{load}(r,t)r\,dr,
\quad A_i=\pi(r_{i+1}^2-r_i^2).
\]

Así,

\[
F_z(t)=\sum_i\bar p_iA_i,
\qquad I_i=\int_{t_0}^{t_f}\bar p_i(t)\,dt.
\]

El primer anillo es un disco de área \(\pi r_1^2\); nunca se divide por \(r=0\).
Los padres AMR cubiertos por hijos no se cuentan. Se exportan presión absoluta y
de referencia como metadatos, pero la carga canónica es manométrica.

La punta del microchorro se identifica sobre la interfaz VOF del lado opuesto a
la pared; \(u_j=dz_{tip}/dt\) usa una derivada local ajustada y se contrasta con
la velocidad líquida interpolada. \(d_j\) es dos veces el radio del cuello del
chorro en el plano normal que pasa por la punta. Umbral VOF, ventana de ajuste y
resolución se guardan para que la medición sea reproducible.

## Pico, impulso y sensor equivalente

No se usa el máximo de una sola celda como carga. Se reportan, para radios de
sensor \(R_s=\{\Delta_{min},10,25,50,100,250,500\}\ \mu\mathrm m\),

\[
p_s(t)=\frac{1}{\pi R_s^2}\int_{A_s}p_{load}\,dA.
\]

Cada serie conserva su dato crudo. Un filtro solo se admite tras demostrar que
la frecuencia removida sigue la malla o el paso temporal, no una onda física;
se publica la señal antes/después y el cambio de pico e impulso. El criterio de
convergencia principal es el impulso y, secundariamente, el pico dependiente del
sensor.

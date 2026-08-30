# Verificación, validación y riesgos

## Matriz V&V

“Verificación” comprueba que se resolvieron las ecuaciones elegidas;
“validación” compara esas ecuaciones con realidad. Una coincidencia experimental
no sustituye balances y convergencia, ni viceversa.

| Bloque | Prueba/referencia | Métricas | Criterio inicial |
| --- | --- | --- | --- |
| EOS | estados analíticos SG/NASG | \(p,e,c,T\), positividad | error <\(10^{-10}\) en doble precisión |
| Basilisk | burbuja estática de Laplace | \(\Delta p=2\sigma/R\), corrientes espurias | <1 % presión; velocidad decrece con malla |
| Basilisk | Rayleigh–Plesset/Keller–Miksis | \(R(t),t_c,p_gV^\Gamma\) | \(t_c<2\)% y convergencia monotónica |
| Basilisk | pulso acústico homogéneo | velocidad, amplitud, reflexión | velocidad <1 %; reflexión de frontera <1 % |
| Basilisk pared | Dular, Philipp–Lauterborn, Supponen | forma, \(t_c,u_j,d_j\) | bandas experimentales, sin ajustar a presión no medida |
| Carga pared | experimento con sensor publicado | llegada, FWHM, pico por sensor, impulso | intervalo experimental + incertidumbre |
| MPM elástico | onda 1-D/placa analítica | \(c_L,R,T,u,\sigma,E\) | <2 % en ROI |
| MPM plástico | Johnson–Cook MPM/cupón publicado | curva esfuerzo–deformación, disipación instrumentada | tolerancia del dato y refinamiento |
| MPM contacto | impacto/indentación publicado | fuerza, rebote, energía | tendencia y <5 % si los datos lo permiten |
| Mapeo | campos uniforme, cuadrático y pulsos exactos | columnas de \(M\), \(F,J\) | \(10^{-10}\) unitario; <1 % producción |
| MVP acoplado | FEniCSx lineal independiente | normas \(L_2\), máximos filtrados, energía | <5 % y misma tendencia de convergencia |
| Gradación | ondas en laminado/FGM publicado | transmisión, reflexión, tiempos | <5 % antes de plasticidad/daño |
| Validación daño | cráter/daño de burbuja única | radio, profundidad, volumen, tiempo | intervalo experimental; no calibrar y validar con el mismo caso |

La comparación con Dular usa su diámetro, tiempo, forma, velocidades y daño de
lámina. Ese artículo no midió \(p_w(r,t)\); no se inventará una validación de
presión a partir de la profundidad del cráter. Para presión e impulso se eligen
experimentos con sensor, se reproduce su área activa y se propaga su ancho de
banda.

## Convergencia y separación de errores

### Fluido

- Niveles máximos 14, 15 y 16; tolerancias AMR reducidas por dos.
- `CFLac` 0.5, 1 y 2; cadencia de salida 10, 20 y 40 ns en impacto.
- Dominios 80, 100 y \(120R_0\), o condición no reflectante validada.
- Sensores equivalentes fijos en unidades físicas, no en número de celdas.
- Reportar GCI/orden observado cuando haya régimen asintótico; si el pico no
  converge, reportar su dependencia y privilegiar impulso/área promedio.

### Sólido

- \(\Delta x=200,100,50\ \mu\)m; 1, 8 y 27 puntos/celda.
- \(C_s=0.2,0.4\) y carga promediada exactamente en cada paso.
- Dominio por separado de la malla y ventana anterior al retorno de ondas.
- Daño regularizado con longitud física; comprobar disipación por unidad de área.

Se conservan cuatro componentes: error de discretización fluida, error del
mapeo, error de discretización sólida y discrepancia del modelo físico. La
comparación FEM usa la **misma carga mapeada** para aislar el sólido; una segunda
comparación usa la carga radial analítica para aislar el mapeo. La incertidumbre
de \(p_{g0}\), propiedades de alta tasa, porosidad y sensor se propaga después de
cerrar los errores numéricos.

## Balances

En Basilisk se registran masa por fase, momento, energía cinética, interna,
superficial y flujo por fronteras. Para el Kratos MPM elástico:

\[
E_k+E_e-W_{ext}=E_0+\varepsilon_E.
\]

Kratos entrega energía cinética, de deformación, potencial y total; el adaptador
debe calcular (W_{ext}) con la fuerza aplicada. (E_p,E_v,E_d,E_{abs}) solo se
añaden cuando una ley o condición instrumentada las exponga y verifique: no se
deducen como nombres distintos del residuo. El mapeo verifica fuerza e impulso;
el trabajo no tiene un “balance” con la pared rígida de CFD.

## Validez del acoplamiento unidireccional

Después de cada caso MPM se calculan

\[
\epsilon_R=\frac{\max|u_z|}{R_0},\qquad
\epsilon_g=\frac{\max|u_z|}{\max(H-R_0,\,0.1R_0)},
\]

\[
\epsilon_v=\frac{\max|\dot u_z|}{\max(U_j,U_R)},\qquad
\epsilon_{pulse}=\frac{\max|\dot u_z|\tau_p}
{\max(H-R_0,\,0.1R_0)},
\qquad \Theta=\frac{\tau_{surface}}{t_R}.
\]

El modelo se considera de perturbación pequeña si
\(\epsilon_R<0.01\), \(\epsilon_g<0.05\),
\(\epsilon_v<0.05\) y \(\epsilon_{pulse}<0.01\). Son umbrales de trabajo y se
somete su efecto a sensibilidad. Si se excede cualquiera, el hueco, la velocidad
relativa o el tiempo de impacto pueden cambiar y se requiere pared móvil o
acoplamiento bidireccional.

Hay un límite adicional aun con desplazamiento pequeño: la pared rígida refleja
una onda de manera distinta de una superficie de impedancia finita. Para incidencia
normal lineal,

\[
\mathcal R_p=\frac{Z_s-Z_l}{Z_s+Z_l}.
\]

Se reporta \(1-|\mathcal R_p|\); si supera 5 %, la carga rígida solo permite una
**comparación controlada bajo carga común**, no una predicción fiel de la burbuja
sobre ese recubrimiento. Este chequeo es especialmente importante porque la
variable de diseño es precisamente \(Z_s\). El resultado del MVP debe separar
“filtrado estructural de una carga rígida prescrita” de “reducción real de carga
por interacción fluido–estructura”.

## Riesgos y mitigaciones

| Riesgo | Señal diagnóstica | Mitigación/criterio de parada |
| --- | --- | --- |
| Pico depende de malla | crece al reducir \(\Delta\) mientras el impulso se estabiliza | promedios de sensor físicos, GCI e impulso; no usar celda máxima. |
| Oscilación compresible numérica | frecuencia sigue \(\Delta\) o CFL | tests de pulso/EOS, limitador, refinamiento; filtro solo con evidencia y copia cruda. |
| EOS inconsistente | \(c,e,T\) o presión inicial erróneos | test unitario por estado, tabla de unidades y auditoría NASG antes de usarla. |
| Onda inicial espuria | pulso antes del colapso | inicialización Laplace/compatible y balance de energía desde \(t=0\). |
| Reflexión exterior | segunda llegada dependiente de \(L\) | dominio mayor/no reflectante verificada; recortar ventana. |
| Pérdida al exportar | fuerza HDF5 no coincide con runtime | bordes anulares, float64, checksum, reducción MPI y validación antes de borrar checkpoint. |
| Mapeo no conservativo | columnas de \(M\), fuerza o impulso fallan | intersección geométrica, área común y fallo >2 %. |
| Pulso submuestreado | pico cambia con cadencia; pocos puntos/FWHM | salida activada, ≥20 muestras/FWHM, promedio temporal exacto en MPM. |
| MPM inestable | energía/momento explotan | CFL acústico, rampa solo si física, refinar tiempo; nunca ensanchar el pulso para estabilizar. |
| Cell crossing/grid noise | bandas ligadas a grid/patrón de partículas | estudio puntos/celda y traslación de grid; otra base de partícula solo tras benchmark Kratos compatible. |
| Daño dependiente de malla | volumen/energía tienden a cero | longitud/energía regularizada y estudio de objetividad. |
| Reflexión sólida | ondas retornan antes de ventana | ampliar dominio o recortar ventana; absorbentes solo como desarrollo calibrado. |
| Datos de alta tasa ausentes | parámetros no identificables | ensayos dedicados, intervalos, análisis de sensibilidad; detener afirmación cuantitativa. |
| Interfaz idealizada | tensiones altas sin modo de delaminación | reportar unión perfecta; añadir cohesión solo con datos de adhesión/fractura. |
| Pared rígida sobreinterpretada | \(\epsilon\) o impedancia fuera de umbral | etiquetar como carga común o migrar a pared móvil/two-way. |
| Daño confundido con erosión | `D=1` se llama pérdida de masa | taxonomía explícita; múltiples colapsos/calibración antes de erosión acumulada. |
| Licencia/procedencia | código copiado sin commit/licencia | parches mínimos, solver lock, auditoría de compatibilidad y DOI de datos. |

## Incertidumbre

Se asignan distribuciones o intervalos únicamente a magnitudes medibles:
\(p_{g0}\), \(R_0,H\), propiedades del agua, área/ancho de banda del sensor,
\(E,\nu,\rho,\sigma_y\), parámetros de tasa, porosidad y espesor. La incertidumbre
numérica se informa por separado. Se reservan datos experimentales para
validación ciega; ajustar y evaluar el mismo cráter solo mide capacidad de ajuste.

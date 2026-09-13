---
description: Transferencia conservativa de cargas de cavitación entre Basilisk y Kratos MPM. Modelo, ejemplos reproducibles y alcance del proyecto MC-Andes.
---

# Colapso de burbujas y respuesta de paredes

<p class="project-kicker">MC-Andes · Investigación en mecánica computacional</p>

<div class="project-intro" markdown>

De la presión de una burbuja a la carga que recibe una estructura.
**Basilisk–MPM** organiza ese intercambio con unidades, procedencia y
comprobaciones de fuerza e impulso.

</div>

[Comenzar](getting-started.md){ .md-button .md-button--primary }
[Ver el código](https://github.com/MC-Andes/cavitation-coupling){ .md-button }

<picture>
  <source media="(max-width: 600px)" srcset="assets/data-flow-mobile.svg">
  <img src="assets/data-flow.svg" alt="Esquema del método: fluido, transferencia de cargas y estructura; sin realimentación al fluido.">
</picture>

!!! info "Alcance publicado"
    La versión pública ofrece contratos HDF5, mapeo conservativo, un adaptador
    para Kratos y ejemplos sintéticos. La investigación física está en
    desarrollo; los ejemplos no son resultados validados de cavitación ni
    predicciones de erosión. [Estado y limitaciones](project-status.md).

## Un problema, tres componentes

<div class="grid cards" markdown>

- :material-waves: **Presión de la burbuja**

    ---

    Una cavidad axisimétrica próxima a una pared rígida define el problema
    fluido: geometría, ecuaciones, condiciones y escalas temporales.

    [Modelo físico](physics.md)

- :material-swap-horizontal: **Transferencia de cargas**

    ---

    La presión media de cada anillo se integra en fuerzas superficiales.
    El intercambio conserva unidades, tiempos y procedencia.

    [Contrato y conservación](coupling.md)

- :material-grid: **Respuesta de la pared**

    ---

    Kratos MPM es el solver estructural seleccionado. El primer caso plantea
    una pared homogénea elástica bajo la carga transferida.

    [Modelo MPM](mpm.md)

</div>

## Recorrido recomendado

1. Ejecuta el [ejemplo de inicio](getting-started.md) para conocer los archivos
   y comprobar el mapeo con una carga sintética.
2. Revisa el [alcance publicado](project-status.md) y los supuestos del
   [modelo físico](physics.md).
3. Consulta [verificación y validación](verification.md) y
   [reproducibilidad](reproducibility.md) antes de interpretar resultados.
4. Explora el [plan técnico](framework-and-2d-roadmap.md) y las
   [etapas de investigación](implementation.md) para contribuir al desarrollo.

## Dentro de MC-Andes

Este proyecto forma parte de la investigación abierta en mecánica computacional
de [MC-Andes](https://mc-andes.github.io/). Comparte sus normas de contribución,
revisión por pares y documentación reproducible.

[Catálogo de proyectos](https://mc-andes.github.io/projects/){ .md-button }
[Cómo contribuir](https://github.com/MC-Andes/cavitation-coupling/blob/main/CONTRIBUTING.md){ .md-button }

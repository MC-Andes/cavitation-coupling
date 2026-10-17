# Estado y alcance publicado

Esta página describe lo que incluye la rama pública `main`. Los planes de
investigación y los ensayos de otras ramas deben acompañarse de sus propias
fuentes y evidencias antes de incorporarse como resultados de esta versión.

## Paquete disponible

| Área | Qué se puede usar | Cómo comprobarlo |
| --- | --- | --- |
| Datos | Lectura, escritura y validación del HDF5 de cargas | Ejemplo de inicio y pruebas del esquema |
| Mapeo | Transferencia axisimétrica a puntos superficiales | Errores de fuerza e impulso del ejemplo sintético |
| Kratos | Exportador de fuerzas y proceso Python de aplicación de cargas | Ejemplo de tabla y pruebas del adaptador |
| Visualización | Series VTK, mapa radial–temporal e historia de fuerza | Exportación del mismo ejemplo sintético |
| Documentación | Formulación, convenciones, plan de verificación y procedencia | Guías de modelo y reproducibilidad |

[Ejecutar el ejemplo](getting-started.md){ .md-button .md-button--primary }

## Alcance de investigación

El primer problema contempla una cavidad gaseosa individual y axisimétrica
próxima a una pared. Basilisk proporciona la presión de la pared rígida; el
acoplamiento transfiere esa carga a una pared homogénea elástica en Kratos MPM.
El sólido no retroalimenta el fluido en esta formulación unidireccional.

La cavidad de gas con masa fija no resuelve condensación. La extensión hacia
plasticidad, materiales gradados, daño o eliminación de partículas requiere
leyes constitutivas, parámetros y validación propios.

!!! warning "Límites de interpretación"
    Esta versión pública no incluye un caso físico completo validado de
    cavitación, una predicción de erosión o una comparación experimental de
    deformación permanente. Pasar pruebas de software o conservar una carga
    sintética no demuestra esos resultados físicos.

## Cómo interpretar la evidencia

| Evidencia | Qué demuestra |
| --- | --- |
| Pruebas unitarias | Comportamiento del esquema y de los operadores ensayados |
| Ejemplo sintético | Funcionamiento del intercambio con una carga conocida |
| Ejecución de un solver | Que una configuración puede ejecutarse en ese entorno |
| Balances | Compatibilidad de las magnitudes discretas comprobadas |
| Validación física | Comparación documentada con una referencia compatible y su incertidumbre |

Las cifras de un nivel no se presentan como evidencia de otro. La fuerza total
se integra sobre el área de la superficie; el máximo local de presión no es un
promedio de sensor ni un impulso.

## Documentos de referencia

- [Problema físico y supuestos](physics.md).
- [Modelo estructural MPM](mpm.md).
- [Transferencia conservativa y unidades](coupling.md).
- [Verificación, validación y riesgos](verification.md).
- [Versiones, licencias y reproducibilidad](reproducibility.md).
- [Plan técnico inicial de la pared](framework-and-2d-roadmap.md), fechado y
  conservado como especificación del desarrollo.
- [Etapas y extensiones de investigación](implementation.md).

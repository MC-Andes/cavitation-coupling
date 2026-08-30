# Módulo MPM

El solver seleccionado es
[Kratos Multiphysics MPMApplication](https://github.com/KratosMultiphysics/Kratos/tree/v10.4.3/applications/MPMApplication).
La integración vive en [`kratos/`](kratos/README.md) y mantiene Kratos como
programa externo: este repositorio aporta el contrato HDF5, el mapeo conservativo
y un `Process` Python, no una copia del solver.

El MVP usa condiciones puntuales materiales sobre la superficie. Cada
`POINT_LOAD` contiene una fuerza ya integrada en N y se actualiza con el promedio
temporal exacto del pulso durante cada paso explícito.

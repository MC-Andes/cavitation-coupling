# Changelog

Los cambios notables se documentan siguiendo Keep a Changelog y Semantic
Versioning.

## [Unreleased]

### Changed

- Reorganizada la presentación pública: README, portada, navegación, inicio
  rápido, alcance publicado e identidad visual compartida con MC-Andes.
- Añadidos metadatos de sitio y recuperación manual del despliegue de Pages.

- Sustituido Uintah por Kratos Multiphysics MPMApplication 10.4.3 como solver
  sólido seleccionado.
- Separada la presión canónica `p(r,t)` de las fuerzas puntuales integradas que
  recibe `MPMParticlePointLoadCondition`.

### Added

- Esquema HDF5 Kratos v1, exportador conservativo, promedio temporal exacto por
  paso y `AxisymmetricHdf5PointLoadProcess`.

## [0.1.0] - 2026-08-30

### Added

- Estrategia técnica para el MVP Basilisk–MPM y sus extensiones.
- Esquema HDF5 versionado para cargas de pared axisimétricas.
- Mapeo conservativo de presión a cuadratura superficial 3D.
- Pruebas de fuerza, impulso, validación de esquema e interpolación temporal.
- Exportación VTK XML, animación de presión y escena reproducible para ParaView.
- CI, documentación, metadatos de citación y plantillas MC-Andes.

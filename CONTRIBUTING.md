# Contribuir

Sigue la [guía de MC-Andes](https://github.com/MC-Andes/standards/blob/main/CONTRIBUTING.md).
Abre un issue, acuerda el alcance, crea una rama corta desde `main`, añade pruebas
y documentación y abre un Pull Request.

Antes de solicitar revisión ejecuta:

```bash
ruff check .
ruff format --check .
mypy src
pytest
mkdocs build --strict
```

Los cambios científicos deben declarar unidades, supuestos, procedencia de
parámetros, tolerancias y evidencia de convergencia. No se aceptan datos
generados, archivos de resultados grandes ni capacidades de software no
respaldadas por documentación oficial o una prueba reproducible.

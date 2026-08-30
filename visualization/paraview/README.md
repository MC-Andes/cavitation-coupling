# Visualización en ParaView

El bundle presenta tres vistas del HDF5 de cargas:

- `wall-pressure.pvd`: animación cartesiana de \(p_w(x,y,t)\) sobre la pared.
- `radial-time.vtr`: mapa \(p_w(r,t)\) para identificar ancho radial y duración.
- `force-history.vtp`: historia de fuerza normal integrada.

El caso incluido es **sintético y sirve para verificar el flujo de datos**. No es
una simulación Basilisk ni una predicción MPM.

## Generar el bundle

```bash
python examples/synthetic_mapping.py
cavitation-paraview-export \
  results/synthetic-wall-loads.h5 \
  results/paraview/synthetic-gaussian-pulse \
  --grid-points 101
```

## Abrir interactivamente

Abre `results/paraview/synthetic-gaussian-pulse/wall-pressure.pvd` en ParaView,
pulsa **Apply** y usa **Play** en la barra de animación. Colorea por
`pressure_gauge_MPa` y activa el scalar bar. Los otros dos archivos se abren en
vistas separadas.

## Crear preview y estado reproducible

En macOS con ParaView 6.1 instalado:

```bash
/Applications/ParaView-6.1.0.app/Contents/bin/pvpython \
  visualization/paraview/render_bundle.py \
  results/paraview/synthetic-gaussian-pulse
```

Esto produce `paraview-preview.png` y `cavitation-wall-loads.pvsm`. El estado
guarda rutas absolutas; vuelve a generarlo si se mueve el bundle.

Para datos físicos futuros se ejecuta exactamente el mismo comando sobre el HDF5
exportado por Basilisk, sin cambiar la semántica de los campos.

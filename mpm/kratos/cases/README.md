# Casos Kratos MPM

Cada caso ejecutable se mantendrá autocontenido con los nombres esperados por
MPMApplication:

```text
case_name/
├── MainKratos.py
├── ProjectParameters.json
├── ParticleMaterials.json
├── case_name_Grid.mdpa
├── case_name_Body.mdpa
├── surface-points.csv
└── case_name.kratos-loads.v1.h5
```

`Grid.mdpa` define la malla de fondo y el submodelpart
`Background_Grid.CavitationLoad` con una condición `Point3D` por cuadratura de
carga. `Body.mdpa` define la geometría inicial del recubrimiento y sustrato que
se convertirá en puntos materiales. `ParticleMaterials.json` comienza con la ley
elástica nativa y propiedades constantes por capa.

El primer caso será axisimétrico, homogéneo y elástico. Antes de agregar el
recubrimiento gradado debe superar:

- onda elástica 1-D y retorno de fronteras;
- presión uniforme, con fuerza $p\pi R^2$;
- pulso triangular no alineado con los pasos, con impulso exacto;
- comparación de desplazamiento y energía elástica con FEniCSx.

No se incluye todavía un caso físico: crear archivos `.mdpa` sin fijar geometría,
orientación de condiciones y discretización produciría un ejemplo aparentemente
ejecutable pero científicamente ambiguo. La tabla de carga y el proceso ya son
independientes de esas elecciones y se reutilizan cuando se genere la malla.

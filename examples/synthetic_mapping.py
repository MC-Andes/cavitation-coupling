"""Generate and conservatively map a synthetic cavitation pressure pulse."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cavitation_coupling.mapping import SurfaceQuadrature, map_axisymmetric_load
from cavitation_coupling.schema import WallLoadHistory


def main() -> None:
    time_s = np.linspace(0.0, 2.0e-6, 101)
    radial_edges_m = np.linspace(0.0, 2.0e-3, 41)
    centers = 0.5 * (radial_edges_m[:-1] + radial_edges_m[1:])
    pulse = np.exp(-(((time_s - 1.0e-6) / 0.18e-6) ** 2))
    profile = np.exp(-((centers / 0.45e-3) ** 2))
    pressure = 100.0e6 * pulse[:, None] * profile[None, :]
    history = WallLoadHistory(
        case_id="synthetic-gaussian-pulse",
        time_s=time_s,
        radial_edges_m=radial_edges_m,
        pressure_gauge_pa=pressure,
        shear_radial_pa=np.zeros_like(pressure),
        metadata={"warning": "synthetic verification data; not a Basilisk result"},
    )

    spacing = 0.05e-3
    coordinates = np.arange(-2.0e-3 + spacing / 2, 2.0e-3, spacing)
    x, y = np.meshgrid(coordinates, coordinates, indexing="xy")
    points = np.column_stack((x.ravel(), y.ravel()))
    surface = SurfaceQuadrature(
        points_xy_m=points,
        tributary_areas_m2=np.full(points.shape[0], spacing**2),
        outward_normals=np.tile([0.0, 0.0, 1.0], (points.shape[0], 1)),
    )
    result = map_axisymmetric_load(history, surface)
    output = Path("results/synthetic-wall-loads.h5")
    output.parent.mkdir(exist_ok=True)
    history.to_hdf5(output)
    print(f"wrote {output}")
    print(f"maximum force error: {np.max(result.diagnostics.relative_force_error):.3e}")
    print(f"impulse error: {result.diagnostics.relative_impulse_error:.3e}")


if __name__ == "__main__":
    main()

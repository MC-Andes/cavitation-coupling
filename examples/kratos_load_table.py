"""Create a Kratos-ready moving point-load table from the synthetic p(r,t)."""

import hashlib
from pathlib import Path

import numpy as np

from cavitation_coupling.kratos import (
    KratosSurfacePoints,
    build_kratos_load_table,
)
from cavitation_coupling.schema import WallLoadHistory


def main() -> None:
    source = Path("results/synthetic-wall-loads.h5")
    output_directory = Path("results/kratos/synthetic-gaussian-pulse")
    output_directory.mkdir(parents=True, exist_ok=True)
    history = WallLoadHistory.from_hdf5(source)

    spacing = 0.05e-3
    coordinates = np.arange(-2.0e-3 + spacing / 2, 2.0e-3, spacing)
    x_coord, y_coord = np.meshgrid(coordinates, coordinates, indexing="xy")
    n_points = x_coord.size
    surface = KratosSurfacePoints(
        condition_ids=np.arange(1, n_points + 1),
        coordinates_m=np.column_stack(
            (x_coord.ravel(), y_coord.ravel(), np.zeros(n_points))
        ),
        tributary_areas_m2=np.full(n_points, spacing**2),
        outward_normals=np.tile([0.0, 0.0, 1.0], (n_points, 1)),
    )
    surface_path = output_directory / "surface-points.csv"
    loads_path = output_directory / "cavitation.kratos-loads.v1.h5"
    surface.to_csv(surface_path)
    with source.open("rb") as source_stream:
        source_sha256 = hashlib.file_digest(source_stream, "sha256").hexdigest()
    with surface_path.open("rb") as surface_stream:
        surface_sha256 = hashlib.file_digest(surface_stream, "sha256").hexdigest()
    table = build_kratos_load_table(
        history,
        surface,
        source_sha256=source_sha256,
        surface_sha256=surface_sha256,
    )
    table.to_hdf5(loads_path)
    print(surface_path)
    print(loads_path)
    print(
        "maximum relative force error: "
        f"{table.metadata['maximum_relative_force_error']:.3e}"
    )


if __name__ == "__main__":
    main()

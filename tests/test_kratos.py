from __future__ import annotations

import csv
from pathlib import Path

import h5py
import numpy as np
import pytest

from cavitation_coupling.kratos import (
    KratosLoadTable,
    KratosSurfacePoints,
    build_kratos_load_table,
    main,
    match_surface_coordinates,
    piecewise_linear_time_average,
)
from cavitation_coupling.schema import WallLoadHistory


def history() -> WallLoadHistory:
    return WallLoadHistory(
        case_id="kratos-test",
        time_s=np.array([0.0, 1.0, 2.0]),
        radial_edges_m=np.array([0.0, 1.0, 2.0]),
        pressure_gauge_pa=np.array([[0.0, 0.0], [4.0, 2.0], [0.0, 0.0]]),
        shear_radial_pa=np.zeros((3, 2)),
        metadata={"warning": "synthetic"},
    )


def surface() -> KratosSurfacePoints:
    return KratosSurfacePoints(
        condition_ids=np.array([11, 12]),
        coordinates_m=np.array([[0.5, 0.0, 0.0], [1.5, 0.0, 0.0]]),
        tributary_areas_m2=np.array([np.pi, 3.0 * np.pi]),
        outward_normals=np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]),
    )


def test_build_kratos_table_conserves_force_and_sign() -> None:
    table = build_kratos_load_table(history(), surface(), source_sha256="abc")
    np.testing.assert_allclose(table.mapped_pressure_gauge_pa[1], [4.0, 2.0])
    np.testing.assert_allclose(
        table.point_force_n[1, :, 2], [-4.0 * np.pi, -6.0 * np.pi]
    )
    np.testing.assert_allclose(table.source_force_n, table.target_force_n)
    assert table.metadata["source_sha256"] == "abc"
    assert table.metadata["maximum_relative_force_error"] == pytest.approx(0.0)


def test_kratos_table_hdf5_round_trip(tmp_path: Path) -> None:
    original = build_kratos_load_table(history(), surface())
    target = tmp_path / "loads.h5"
    original.to_hdf5(target)
    recovered = KratosLoadTable.from_hdf5(target)
    np.testing.assert_allclose(
        recovered.source_pressure_gauge_pa, original.source_pressure_gauge_pa
    )
    np.testing.assert_allclose(recovered.point_force_n, original.point_force_n)
    assert recovered.surface.condition_ids.tolist() == [11, 12]
    with h5py.File(target, "r") as handle:
        assert bool(handle.attrs["complete"])
        assert handle["source/pressure_gauge"].attrs["units"] == "Pa"
        assert handle["loads/point_force"].attrs["units"] == "N"


def test_time_sampling_preserves_triangular_impulse() -> None:
    values = np.array([0.0, 2.0, 0.0])
    average = piecewise_linear_time_average(np.array([0.0, 1.0, 2.0]), values, 0.5, 1.5)
    assert float(average) == pytest.approx(1.5)
    table = build_kratos_load_table(history(), surface())
    np.testing.assert_allclose(table.sample_point_force(1.0), table.point_force_n[1])
    np.testing.assert_allclose(
        table.average_point_force(0.5, 1.5), 0.75 * table.point_force_n[1]
    )
    with pytest.raises(ValueError, match="extrapolation"):
        table.sample_point_force(-0.1)
    with pytest.raises(ValueError, match="less than"):
        piecewise_linear_time_average(table.time_s, table.point_force_n, 1.0, 1.0)


def test_surface_csv_round_trip_and_validation(tmp_path: Path) -> None:
    target = tmp_path / "surface.csv"
    surface().to_csv(target)
    recovered = KratosSurfacePoints.from_csv(target)
    np.testing.assert_allclose(recovered.coordinates_m, surface().coordinates_m)
    invalid = tmp_path / "invalid.csv"
    with invalid.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([["x", "y"], [0.0, 1.0]])
    with pytest.raises(ValueError, match="columns"):
        KratosSurfacePoints.from_csv(invalid)


def test_wall_frame_and_surface_validation() -> None:
    with pytest.raises(ValueError, match="orthogonal"):
        build_kratos_load_table(
            history(), surface(), wall_y_axis=np.array([1.0, 0.0, 0.0])
        )
    shifted = KratosSurfacePoints(
        condition_ids=surface().condition_ids,
        coordinates_m=surface().coordinates_m + np.array([0.0, 0.0, 1.0e-3]),
        tributary_areas_m2=surface().tributary_areas_m2,
        outward_normals=surface().outward_normals,
    )
    with pytest.raises(ValueError, match="wall plane"):
        build_kratos_load_table(history(), shifted)
    tangent_normals = KratosSurfacePoints(
        condition_ids=surface().condition_ids,
        coordinates_m=surface().coordinates_m,
        tributary_areas_m2=surface().tributary_areas_m2,
        outward_normals=np.tile([1.0, 0.0, 0.0], (2, 1)),
    )
    with pytest.raises(ValueError, match="surface normals"):
        build_kratos_load_table(history(), tangent_normals)
    with pytest.raises(ValueError, match="positive and unique"):
        KratosSurfacePoints(
            condition_ids=np.array([1, 1]),
            coordinates_m=surface().coordinates_m,
            tributary_areas_m2=surface().tributary_areas_m2,
            outward_normals=surface().outward_normals,
        )


def test_coordinate_matching_is_order_independent() -> None:
    reference = surface().coordinates_m
    query = reference[[1, 0]] + np.array([[1.0e-12, 0.0, 0.0], [0.0, 0.0, 0.0]])
    assert match_surface_coordinates(reference, query, 1.0e-10).tolist() == [1, 0]
    with pytest.raises(ValueError, match="one-to-one"):
        match_surface_coordinates(reference, query[[0, 0]], 1.0e-10)
    with pytest.raises(ValueError, match="positive"):
        match_surface_coordinates(reference, query, 0.0)


def test_kratos_export_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wall_loads = tmp_path / "wall-loads.h5"
    surface_csv = tmp_path / "surface.csv"
    output = tmp_path / "kratos-loads.h5"
    history().to_hdf5(wall_loads)
    surface().to_csv(surface_csv)
    assert main([str(wall_loads), str(surface_csv), str(output)]) == 0
    printed = capsys.readouterr().out
    assert "maximum relative force error" in printed
    assert output.exists()
    assert KratosLoadTable.from_hdf5(output).case_id == "kratos-test"


def test_kratos_table_rejects_incomplete_file(tmp_path: Path) -> None:
    target = tmp_path / "incomplete.h5"
    with h5py.File(target, "w") as handle:
        handle.attrs["schema_name"] = "mc-andes-kratos-mpm-point-loads"
        handle.attrs["schema_version"] = "1.0.0"
        handle.attrs["complete"] = False
    with pytest.raises(ValueError, match="incomplete"):
        KratosLoadTable.from_hdf5(target)


def test_kratos_table_rejects_missing_provenance(tmp_path: Path) -> None:
    target = tmp_path / "loads.h5"
    build_kratos_load_table(history(), surface()).to_hdf5(target)
    with h5py.File(target, "r+") as handle:
        handle.attrs.modify("metadata_json", "{}")
    with pytest.raises(ValueError, match="missing metadata"):
        KratosLoadTable.from_hdf5(target)

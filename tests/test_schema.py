from __future__ import annotations

import h5py
import numpy as np
import pytest

from cavitation_coupling.schema import WallLoadHistory


def history() -> WallLoadHistory:
    return WallLoadHistory(
        case_id="synthetic-pulse",
        time_s=np.array([0.0, 1.0e-6, 2.0e-6]),
        radial_edges_m=np.array([0.0, 1.0e-3, 2.0e-3]),
        pressure_gauge_pa=np.array([[0.0, 0.0], [2.0e6, 1.0e6], [0.0, 0.0]]),
        shear_radial_pa=np.zeros((3, 2)),
        metadata={"source": "unit-test", "level": 12},
    )


def test_hdf5_round_trip(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "loads.h5"  # type: ignore[operator]
    original = history()
    original.to_hdf5(path)
    recovered = WallLoadHistory.from_hdf5(path)

    assert recovered.case_id == original.case_id
    assert recovered.metadata == original.metadata
    np.testing.assert_array_equal(recovered.time_s, original.time_s)
    np.testing.assert_array_equal(
        recovered.pressure_gauge_pa, original.pressure_gauge_pa
    )
    np.testing.assert_allclose(recovered.impulse_pressure_pa_s, [2.0, 1.0])
    np.testing.assert_allclose(
        recovered.force_normal_n,
        [0.0, 5.0 * np.pi, 0.0],
    )
    with h5py.File(path, "r") as handle:
        assert handle["fields/pressure_gauge"].attrs["units"] == "Pa"
        assert handle["coordinates/radial_edges"].attrs["units"] == "m"
        assert handle["derived/force_normal"].attrs["units"] == "N"


def test_rejects_non_monotone_time() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        WallLoadHistory(
            case_id="bad",
            time_s=np.array([0.0, 0.0]),
            radial_edges_m=np.array([0.0, 1.0]),
            pressure_gauge_pa=np.zeros((2, 1)),
            shear_radial_pa=np.zeros((2, 1)),
        )


def test_rejects_wrong_field_shape() -> None:
    with pytest.raises(ValueError, match="shape"):
        WallLoadHistory(
            case_id="bad",
            time_s=np.array([0.0, 1.0]),
            radial_edges_m=np.array([0.0, 1.0, 2.0]),
            pressure_gauge_pa=np.zeros((2, 1)),
            shear_radial_pa=np.zeros((2, 2)),
        )


def test_rejects_unknown_schema(tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "unknown.h5"  # type: ignore[operator]
    with h5py.File(path, "w") as handle:
        handle.attrs["schema_name"] = "unknown"
    with pytest.raises(ValueError, match="schema_name"):
        WallLoadHistory.from_hdf5(path)


def test_rejects_incomplete_wall_load_file(
    tmp_path: pytest.TempPathFactory,
) -> None:
    path = tmp_path / "incomplete.h5"  # type: ignore[operator]
    history().to_hdf5(path)
    with h5py.File(path, "r+") as handle:
        handle.attrs.modify("complete", False)
    with pytest.raises(ValueError, match="incomplete"):
        WallLoadHistory.from_hdf5(path)

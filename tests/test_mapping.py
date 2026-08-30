from __future__ import annotations

import numpy as np
import pytest

from cavitation_coupling.mapping import (
    ConservativePressureOperator,
    SurfaceQuadrature,
    annular_areas,
    force_from_annular_averages,
    interpolate_history,
    map_axisymmetric_load,
)
from cavitation_coupling.schema import WallLoadHistory


def pulse_history() -> WallLoadHistory:
    return WallLoadHistory(
        case_id="pulse",
        time_s=np.array([0.0, 1.0, 2.0]),
        radial_edges_m=np.array([0.0, 1.0, 2.0]),
        pressure_gauge_pa=np.array([[0.0, 0.0], [4.0, 2.0], [0.0, 0.0]]),
        shear_radial_pa=np.zeros((3, 2)),
    )


def square_surface(spacing: float = 0.1) -> SurfaceQuadrature:
    coordinates = np.arange(-2.0 + spacing / 2, 2.0, spacing)
    x, y = np.meshgrid(coordinates, coordinates, indexing="xy")
    points = np.column_stack((x.ravel(), y.ravel()))
    areas = np.full(points.shape[0], spacing**2)
    normals = np.tile([0.0, 0.0, 1.0], (points.shape[0], 1))
    return SurfaceQuadrature(points, areas, normals)


def test_annular_area_and_force_are_exact() -> None:
    edges = np.array([0.0, 1.0, 2.0])
    np.testing.assert_allclose(annular_areas(edges), [np.pi, 3.0 * np.pi])
    pressure = np.array([[4.0, 2.0]])
    np.testing.assert_allclose(
        force_from_annular_averages(pressure, edges), [10.0 * np.pi]
    )
    np.testing.assert_allclose(
        force_from_annular_averages(pressure, edges, 1.5), [6.5 * np.pi]
    )


def test_mapping_conserves_force_and_impulse() -> None:
    result = map_axisymmetric_load(pulse_history(), square_surface())
    assert np.max(result.diagnostics.relative_force_error) < 1.0e-14
    assert result.diagnostics.relative_impulse_error < 1.0e-14
    np.testing.assert_allclose(
        np.sum(result.force_vectors_n[:, :, 2], axis=1),
        -result.diagnostics.source_force_n,
    )


def test_matrix_operator_conserves_each_annulus() -> None:
    operator = ConservativePressureOperator(
        radial_edges_m=np.array([0.0, 1.0, 2.0]),
        weights_m2=np.array([[np.pi, 0.0], [0.0, 3.0 * np.pi]]),
        outward_normals=np.tile([0.0, 0.0, 1.0], (2, 1)),
    )
    result = operator.apply(pulse_history())
    assert np.max(result.diagnostics.relative_force_error) < 1.0e-14
    assert result.diagnostics.relative_impulse_error < 1.0e-14
    np.testing.assert_allclose(result.pressure_pa[1], [4.0, 2.0])


def test_matrix_operator_rejects_nonconservative_columns() -> None:
    with pytest.raises(ValueError, match="columns"):
        ConservativePressureOperator(
            radial_edges_m=np.array([0.0, 1.0]),
            weights_m2=np.array([[0.5 * np.pi]]),
            outward_normals=np.array([[0.0, 0.0, 1.0]]),
        )


def test_axis_and_outer_domain_are_handled() -> None:
    surface = SurfaceQuadrature(
        points_xy_m=np.array([[0.0, 0.0], [0.5, 0.0], [3.0, 0.0]]),
        tributary_areas_m2=np.ones(3),
        outward_normals=np.tile([0.0, 0.0, 1.0], (3, 1)),
    )
    result = map_axisymmetric_load(pulse_history(), surface)
    assert result.pressure_pa[1, 0] == result.pressure_pa[1, 1]
    assert result.pressure_pa[1, 2] == 0.0


def test_linear_time_interpolation_does_not_overshoot() -> None:
    target = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    interpolated = interpolate_history(pulse_history(), target)
    assert np.min(interpolated.pressure_gauge_pa) >= 0.0
    assert np.max(interpolated.pressure_gauge_pa) == 4.0
    np.testing.assert_allclose(interpolated.pressure_gauge_pa[:, 0], [0, 2, 4, 2, 0])


def test_temporal_extrapolation_is_rejected() -> None:
    with pytest.raises(ValueError, match="extrapolation"):
        interpolate_history(pulse_history(), np.array([-0.1, 1.0]))


def test_invalid_surface_is_rejected() -> None:
    with pytest.raises(ValueError, match="unit vectors"):
        SurfaceQuadrature(np.zeros((1, 2)), np.ones(1), np.zeros((1, 3)))


def test_map_radius_and_empty_overlap_are_checked() -> None:
    with pytest.raises(ValueError, match="radial range"):
        map_axisymmetric_load(pulse_history(), square_surface(), map_radius_m=3.0)
    outside = SurfaceQuadrature(
        np.array([[3.0, 0.0]]), np.ones(1), np.array([[0.0, 0.0, 1.0]])
    )
    with pytest.raises(ValueError, match="no quadrature"):
        map_axisymmetric_load(pulse_history(), outside)

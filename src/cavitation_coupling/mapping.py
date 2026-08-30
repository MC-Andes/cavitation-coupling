"""Conservative axisymmetric wall-load mapping onto an MPM surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from cavitation_coupling.schema import FloatArray, WallLoadHistory


def _as_float_array(value: object) -> FloatArray:
    return cast(FloatArray, np.asarray(value, dtype=np.float64))


@dataclass(frozen=True)
class SurfaceQuadrature:
    """Surface integration points and positive tributary areas.

    Coordinates are relative to the projected bubble axis. Each entry can be a
    surface material point or a quadrature point attached to an MPM boundary
    patch. Normals point out of the solid.
    """

    points_xy_m: FloatArray
    tributary_areas_m2: FloatArray
    outward_normals: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(self, "points_xy_m", _as_float_array(self.points_xy_m))
        object.__setattr__(
            self, "tributary_areas_m2", _as_float_array(self.tributary_areas_m2)
        )
        object.__setattr__(
            self, "outward_normals", _as_float_array(self.outward_normals)
        )
        self.validate()

    @property
    def radii_m(self) -> FloatArray:
        return cast(FloatArray, np.sqrt(np.sum(self.points_xy_m**2, axis=1)))

    def validate(self) -> None:
        if self.points_xy_m.ndim != 2 or self.points_xy_m.shape[1] != 2:
            raise ValueError("points_xy_m must have shape (n_points, 2)")
        n_points = self.points_xy_m.shape[0]
        if self.tributary_areas_m2.shape != (n_points,):
            raise ValueError("tributary_areas_m2 must have shape (n_points,)")
        if self.outward_normals.shape != (n_points, 3):
            raise ValueError("outward_normals must have shape (n_points, 3)")
        if np.any(~np.isfinite(self.points_xy_m)):
            raise ValueError("points_xy_m must be finite")
        if np.any(~np.isfinite(self.tributary_areas_m2)) or np.any(
            self.tributary_areas_m2 <= 0
        ):
            raise ValueError("tributary areas must be finite and positive")
        normal_lengths = np.linalg.norm(self.outward_normals, axis=1)
        if np.any(~np.isfinite(normal_lengths)) or not np.allclose(
            normal_lengths, 1.0, rtol=1e-10, atol=1e-12
        ):
            raise ValueError("outward_normals must be finite unit vectors")


@dataclass(frozen=True)
class MappingDiagnostics:
    source_force_n: FloatArray
    target_force_n: FloatArray
    relative_force_error: FloatArray
    source_impulse_ns: float
    target_impulse_ns: float
    relative_impulse_error: float
    relative_l2_correction: FloatArray


@dataclass(frozen=True)
class MappingResult:
    time_s: FloatArray
    pressure_pa: FloatArray
    force_vectors_n: FloatArray
    diagnostics: MappingDiagnostics


@dataclass(frozen=True)
class ConservativePressureOperator:
    """Precomputed surface-shape-function integrals for each source annulus.

    ``weights_m2[a, i]`` is the integral of target shape function ``a`` over
    source annulus ``i``. Column sums must equal the exact annular areas, which
    makes pressure force conservation algebraic rather than corrective.
    """

    radial_edges_m: FloatArray
    weights_m2: FloatArray
    outward_normals: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(self, "radial_edges_m", _as_float_array(self.radial_edges_m))
        object.__setattr__(self, "weights_m2", _as_float_array(self.weights_m2))
        object.__setattr__(
            self, "outward_normals", _as_float_array(self.outward_normals)
        )
        self.validate()

    def validate(self) -> None:
        if self.weights_m2.ndim != 2:
            raise ValueError("weights_m2 must have shape (n_targets, n_annuli)")
        n_targets, n_annuli = self.weights_m2.shape
        if self.radial_edges_m.shape != (n_annuli + 1,):
            raise ValueError("radial_edges_m does not match the operator annuli")
        if self.outward_normals.shape != (n_targets, 3):
            raise ValueError("outward_normals must have shape (n_targets, 3)")
        if np.any(~np.isfinite(self.weights_m2)) or np.any(self.weights_m2 < 0):
            raise ValueError("weights_m2 must be finite and nonnegative")
        normal_lengths = np.linalg.norm(self.outward_normals, axis=1)
        if np.any(~np.isfinite(normal_lengths)) or not np.allclose(
            normal_lengths, 1.0, rtol=1e-10, atol=1e-12
        ):
            raise ValueError("outward_normals must be finite unit vectors")
        expected_areas = annular_areas(self.radial_edges_m)
        if not np.allclose(
            np.sum(self.weights_m2, axis=0),
            expected_areas,
            rtol=1e-10,
            atol=1e-14,
        ):
            raise ValueError("operator columns must sum to exact annular areas")

    def apply(
        self,
        history: WallLoadHistory,
        *,
        target_time_s: FloatArray | None = None,
    ) -> MappingResult:
        """Apply annular pressure averages to target degrees of freedom."""

        working = (
            history
            if target_time_s is None
            else interpolate_history(history, target_time_s)
        )
        if not np.array_equal(working.radial_edges_m, self.radial_edges_m):
            raise ValueError("history radial edges do not match the operator")
        nodal_force = working.pressure_gauge_pa @ self.weights_m2.T
        force_vectors = -nodal_force[:, :, None] * self.outward_normals[None, :, :]
        nodal_area = np.sum(self.weights_m2, axis=1)
        equivalent_pressure = np.zeros_like(nodal_force)
        active = nodal_area > 0
        equivalent_pressure[:, active] = nodal_force[:, active] / nodal_area[active]

        source_force = force_from_annular_averages(
            working.pressure_gauge_pa, working.radial_edges_m
        )
        target_force = cast(FloatArray, np.sum(nodal_force, axis=1))
        source_impulse = float(_time_integral(source_force[:, None], working.time_s)[0])
        target_impulse = float(_time_integral(target_force[:, None], working.time_s)[0])
        impulse_scale = max(abs(source_impulse), float(np.finfo(np.float64).eps))
        diagnostics = MappingDiagnostics(
            source_force_n=source_force,
            target_force_n=target_force,
            relative_force_error=_relative_error(target_force, source_force),
            source_impulse_ns=source_impulse,
            target_impulse_ns=target_impulse,
            relative_impulse_error=abs(target_impulse - source_impulse) / impulse_scale,
            relative_l2_correction=np.zeros(working.n_times),
        )
        return MappingResult(
            time_s=working.time_s,
            pressure_pa=equivalent_pressure,
            force_vectors_n=force_vectors,
            diagnostics=diagnostics,
        )


def annular_areas(
    radial_edges_m: FloatArray, map_radius_m: float | None = None
) -> FloatArray:
    """Return exact overlap area of each annulus with the mapped disk."""

    edges = _as_float_array(radial_edges_m)
    if edges.ndim != 1 or edges.size < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError("radial_edges_m must be a strictly increasing vector")
    if map_radius_m is None:
        clipped = edges
    else:
        if map_radius_m <= 0:
            raise ValueError("map_radius_m must be positive")
        clipped = np.minimum(edges, map_radius_m)
    return np.pi * np.maximum(clipped[1:] ** 2 - clipped[:-1] ** 2, 0.0)


def force_from_annular_averages(
    pressure_pa: FloatArray,
    radial_edges_m: FloatArray,
    map_radius_m: float | None = None,
) -> FloatArray:
    """Integrate annulus-area-average pressure into normal force magnitude."""

    pressure = _as_float_array(pressure_pa)
    areas = annular_areas(radial_edges_m, map_radius_m)
    if pressure.shape[-1] != areas.size:
        raise ValueError("last pressure dimension must match the annulus count")
    return cast(FloatArray, np.sum(pressure * areas, axis=-1))


def _piecewise_constant_profile(
    pressure_pa: FloatArray, radial_edges_m: FloatArray, radii_m: FloatArray
) -> tuple[FloatArray, NDArray[np.bool_]]:
    indices = np.searchsorted(radial_edges_m, radii_m, side="right") - 1
    on_outer_edge = np.isclose(radii_m, radial_edges_m[-1], rtol=0.0, atol=1e-14)
    indices[on_outer_edge] = radial_edges_m.size - 2
    active = (indices >= 0) & (indices < radial_edges_m.size - 1)
    mapped = np.zeros((pressure_pa.shape[0], radii_m.size), dtype=np.float64)
    mapped[:, active] = pressure_pa[:, indices[active]]
    return mapped, active


def _time_integral(values: FloatArray, time_s: FloatArray) -> FloatArray:
    dt = np.diff(time_s)
    return cast(
        FloatArray,
        np.sum(0.5 * (values[1:] + values[:-1]) * dt[:, None], axis=0),
    )


def _relative_error(actual: FloatArray, reference: FloatArray) -> FloatArray:
    scale = np.maximum(np.abs(reference), np.finfo(np.float64).eps)
    return cast(FloatArray, np.abs(actual - reference) / scale)


def interpolate_history(
    history: WallLoadHistory, target_time_s: FloatArray
) -> WallLoadHistory:
    """Linearly interpolate in time without extrapolation or overshoot."""

    target = _as_float_array(target_time_s)
    if target.ndim != 1 or target.size < 2 or np.any(np.diff(target) <= 0):
        raise ValueError("target_time_s must be strictly increasing")
    tolerance = 10.0 * np.finfo(np.float64).eps * max(1.0, history.time_s[-1])
    if target[0] < history.time_s[0] - tolerance or target[-1] > (
        history.time_s[-1] + tolerance
    ):
        raise ValueError("temporal extrapolation is not allowed")

    def interpolate(values: FloatArray) -> FloatArray:
        columns = [
            np.interp(target, history.time_s, values[:, i])
            for i in range(values.shape[1])
        ]
        return np.column_stack(columns)

    metadata = dict(history.metadata)
    metadata["temporal_interpolation"] = "piecewise-linear-no-extrapolation"
    return WallLoadHistory(
        case_id=history.case_id,
        time_s=target,
        radial_edges_m=history.radial_edges_m,
        pressure_gauge_pa=interpolate(history.pressure_gauge_pa),
        shear_radial_pa=interpolate(history.shear_radial_pa),
        metadata=metadata,
    )


def map_axisymmetric_load(
    history: WallLoadHistory,
    surface: SurfaceQuadrature,
    *,
    map_radius_m: float | None = None,
    target_time_s: FloatArray | None = None,
) -> MappingResult:
    """Map pressure to a 3-D surface and enforce force conservation.

    Annular values are treated as area averages. A piecewise-constant radial
    reconstruction is sampled at surface quadrature points. The remaining
    quadrature error is removed by the minimum-L2 uniform pressure correction
    over active points at every source time. No temporal or spatial smoothing
    is applied.
    """

    working = (
        history
        if target_time_s is None
        else interpolate_history(history, target_time_s)
    )
    available_radius = float(working.radial_edges_m[-1])
    radius = available_radius if map_radius_m is None else map_radius_m
    if radius <= 0 or radius > available_radius:
        raise ValueError("map_radius_m must lie inside the exported radial range")

    raw_pressure, within_export = _piecewise_constant_profile(
        working.pressure_gauge_pa, working.radial_edges_m, surface.radii_m
    )
    active = within_export & (surface.radii_m <= radius)
    raw_pressure[:, ~active] = 0.0
    if not np.any(active):
        raise ValueError("the target surface has no quadrature points in the map disk")

    areas = surface.tributary_areas_m2
    source_force = force_from_annular_averages(
        working.pressure_gauge_pa, working.radial_edges_m, radius
    )
    raw_force = np.sum(raw_pressure * areas[None, :], axis=1)
    active_area = float(np.sum(areas[active]))
    delta_pressure = (source_force - raw_force) / active_area
    mapped_pressure = raw_pressure.copy()
    mapped_pressure[:, active] += delta_pressure[:, None]

    target_force = np.sum(mapped_pressure * areas[None, :], axis=1)
    force_vectors = (
        -mapped_pressure[:, :, None]
        * areas[None, :, None]
        * surface.outward_normals[None, :, :]
    )

    source_impulse = float(_time_integral(source_force[:, None], working.time_s)[0])
    target_impulse = float(_time_integral(target_force[:, None], working.time_s)[0])
    impulse_scale = max(abs(source_impulse), float(np.finfo(np.float64).eps))

    correction_norm = cast(
        FloatArray, np.linalg.norm(mapped_pressure - raw_pressure, axis=1)
    )
    raw_norm = cast(
        FloatArray,
        np.maximum(np.linalg.norm(raw_pressure, axis=1), np.finfo(np.float64).eps),
    )
    diagnostics = MappingDiagnostics(
        source_force_n=source_force,
        target_force_n=target_force,
        relative_force_error=_relative_error(target_force, source_force),
        source_impulse_ns=source_impulse,
        target_impulse_ns=target_impulse,
        relative_impulse_error=abs(target_impulse - source_impulse) / impulse_scale,
        relative_l2_correction=correction_norm / raw_norm,
    )
    return MappingResult(
        time_s=working.time_s,
        pressure_pa=mapped_pressure,
        force_vectors_n=force_vectors,
        diagnostics=diagnostics,
    )

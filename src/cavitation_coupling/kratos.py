"""Kratos MPM adapter for conservative axisymmetric pressure histories."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import h5py
import numpy as np
from numpy.typing import NDArray

from cavitation_coupling.mapping import SurfaceQuadrature, map_axisymmetric_load
from cavitation_coupling.schema import SCHEMA_VERSION as WALL_LOAD_SCHEMA_VERSION
from cavitation_coupling.schema import FloatArray, WallLoadHistory

IntArray = NDArray[np.int64]
KRATOS_LOAD_SCHEMA_NAME = "mc-andes-kratos-mpm-point-loads"
KRATOS_LOAD_SCHEMA_VERSION = "1.0.0"
REQUIRED_KRATOS_METADATA = frozenset(
    {
        "source_schema_name",
        "source_schema_version",
        "source_sha256",
        "surface_sha256",
        "mapping",
        "map_radius_m",
        "wall_origin_m",
        "wall_x_axis",
        "wall_y_axis",
    }
)
SURFACE_COLUMNS = (
    "condition_id",
    "x_m",
    "y_m",
    "z_m",
    "area_m2",
    "nx",
    "ny",
    "nz",
)


def _float_array(value: object) -> FloatArray:
    return cast(FloatArray, np.asarray(value, dtype=np.float64))


def _int_array(value: object) -> IntArray:
    return cast(IntArray, np.asarray(value, dtype=np.int64))


def _unit_vector(value: object, name: str) -> FloatArray:
    vector = _float_array(value)
    if vector.shape != (3,) or np.any(~np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite three-vector")
    length = float(np.linalg.norm(vector))
    if not np.isclose(length, 1.0, rtol=1e-10, atol=1e-12):
        raise ValueError(f"{name} must be a unit vector")
    return vector


def _sample_piecewise_linear(
    time_s: FloatArray, values: FloatArray, target_time_s: float
) -> FloatArray:
    tolerance = 10.0 * np.finfo(np.float64).eps * max(1.0, abs(time_s[-1]))
    if target_time_s < time_s[0] - tolerance or target_time_s > (
        time_s[-1] + tolerance
    ):
        raise ValueError("temporal extrapolation is not allowed")
    target = float(np.clip(target_time_s, time_s[0], time_s[-1]))
    flattened = values.reshape(values.shape[0], -1)
    sampled = np.array(
        [
            np.interp(target, time_s, flattened[:, index])
            for index in range(flattened.shape[1])
        ]
    )
    return cast(FloatArray, sampled.reshape(values.shape[1:]))


def piecewise_linear_time_average(
    time_s: FloatArray,
    values: FloatArray,
    start_time_s: float,
    end_time_s: float,
) -> FloatArray:
    """Return the exact step average of a piecewise-linear time history."""

    times = _float_array(time_s)
    field = _float_array(values)
    if times.ndim != 1 or times.size < 2 or np.any(np.diff(times) <= 0):
        raise ValueError("time_s must be strictly increasing")
    if field.shape[0] != times.size:
        raise ValueError("values first dimension must match time_s")
    if not start_time_s < end_time_s:
        raise ValueError("start_time_s must be less than end_time_s")
    tolerance = 10.0 * np.finfo(np.float64).eps * max(1.0, abs(times[-1]))
    if start_time_s < times[0] - tolerance or end_time_s > times[-1] + tolerance:
        raise ValueError("temporal extrapolation is not allowed")
    start = float(np.clip(start_time_s, times[0], times[-1]))
    end = float(np.clip(end_time_s, times[0], times[-1]))
    if not start < end:
        raise ValueError("averaging interval collapses at the source boundary")
    interior = times[(times > start) & (times < end)]
    knots = np.concatenate(([start], interior, [end]))
    samples = np.stack(
        [_sample_piecewise_linear(times, field, float(time)) for time in knots]
    )
    reshape = (-1,) + (1,) * (field.ndim - 1)
    widths = np.diff(knots).reshape(reshape)
    integral = np.sum(0.5 * (samples[:-1] + samples[1:]) * widths, axis=0)
    return cast(FloatArray, integral / (end - start))


@dataclass(frozen=True)
class KratosSurfacePoints:
    """Quadrature points used as Kratos moving point-load conditions."""

    condition_ids: IntArray
    coordinates_m: FloatArray
    tributary_areas_m2: FloatArray
    outward_normals: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition_ids", _int_array(self.condition_ids))
        object.__setattr__(self, "coordinates_m", _float_array(self.coordinates_m))
        object.__setattr__(
            self, "tributary_areas_m2", _float_array(self.tributary_areas_m2)
        )
        object.__setattr__(self, "outward_normals", _float_array(self.outward_normals))
        self.validate()

    @property
    def n_points(self) -> int:
        return int(self.condition_ids.size)

    def validate(self) -> None:
        if self.condition_ids.ndim != 1 or self.condition_ids.size == 0:
            raise ValueError("condition_ids must be a nonempty vector")
        if np.any(self.condition_ids <= 0) or np.unique(self.condition_ids).size != (
            self.condition_ids.size
        ):
            raise ValueError("condition_ids must be positive and unique")
        expected_vector = (self.n_points, 3)
        if self.coordinates_m.shape != expected_vector:
            raise ValueError(f"coordinates_m must have shape {expected_vector}")
        if self.outward_normals.shape != expected_vector:
            raise ValueError(f"outward_normals must have shape {expected_vector}")
        if self.tributary_areas_m2.shape != (self.n_points,):
            raise ValueError("tributary_areas_m2 must have shape (n_points,)")
        if np.any(~np.isfinite(self.coordinates_m)):
            raise ValueError("coordinates_m must be finite")
        if np.any(~np.isfinite(self.tributary_areas_m2)) or np.any(
            self.tributary_areas_m2 <= 0
        ):
            raise ValueError("tributary areas must be finite and positive")
        lengths = np.linalg.norm(self.outward_normals, axis=1)
        if np.any(~np.isfinite(lengths)) or not np.allclose(
            lengths, 1.0, rtol=1e-10, atol=1e-12
        ):
            raise ValueError("outward_normals must be finite unit vectors")

    @classmethod
    def from_csv(cls, path: str | Path) -> KratosSurfacePoints:
        """Read the documented SI surface-point CSV exchange format."""

        rows: list[dict[str, str]] = []
        with Path(path).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or tuple(reader.fieldnames) != SURFACE_COLUMNS:
                raise ValueError(
                    "surface CSV columns must be exactly: " + ",".join(SURFACE_COLUMNS)
                )
            rows.extend(reader)
        if not rows:
            raise ValueError("surface CSV must contain at least one point")
        return cls(
            condition_ids=np.array(
                [int(row["condition_id"]) for row in rows], dtype=np.int64
            ),
            coordinates_m=np.array(
                [
                    [float(row["x_m"]), float(row["y_m"]), float(row["z_m"])]
                    for row in rows
                ],
                dtype=np.float64,
            ),
            tributary_areas_m2=np.array(
                [float(row["area_m2"]) for row in rows], dtype=np.float64
            ),
            outward_normals=np.array(
                [
                    [float(row["nx"]), float(row["ny"]), float(row["nz"])]
                    for row in rows
                ],
                dtype=np.float64,
            ),
        )

    def to_csv(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(SURFACE_COLUMNS)
            for point_id, coordinates, area, normal in zip(
                self.condition_ids,
                self.coordinates_m,
                self.tributary_areas_m2,
                self.outward_normals,
                strict=True,
            ):
                writer.writerow([int(point_id), *coordinates, float(area), *normal])


@dataclass(frozen=True)
class KratosLoadTable:
    """Self-contained p(r,t) source and mapped Kratos point-force table."""

    case_id: str
    time_s: FloatArray
    radial_edges_m: FloatArray
    source_pressure_gauge_pa: FloatArray
    surface: KratosSurfacePoints
    mapped_pressure_gauge_pa: FloatArray
    point_force_n: FloatArray
    source_force_n: FloatArray
    target_force_n: FloatArray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "time_s",
            "radial_edges_m",
            "source_pressure_gauge_pa",
            "mapped_pressure_gauge_pa",
            "point_force_n",
            "source_force_n",
            "target_force_n",
        ):
            object.__setattr__(self, name, _float_array(getattr(self, name)))
        self.validate()

    def validate(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.time_s.ndim != 1 or self.time_s.size < 2:
            raise ValueError("time_s must contain at least two values")
        if np.any(~np.isfinite(self.time_s)) or np.any(np.diff(self.time_s) <= 0):
            raise ValueError("time_s must be finite and strictly increasing")
        n_times = self.time_s.size
        n_annuli = self.radial_edges_m.size - 1
        n_points = self.surface.n_points
        expected_shapes = {
            "source_pressure_gauge_pa": (n_times, n_annuli),
            "mapped_pressure_gauge_pa": (n_times, n_points),
            "point_force_n": (n_times, n_points, 3),
            "source_force_n": (n_times,),
            "target_force_n": (n_times,),
        }
        if (
            self.radial_edges_m.ndim != 1
            or self.radial_edges_m.size < 2
            or self.radial_edges_m[0] < 0
            or np.any(np.diff(self.radial_edges_m) <= 0)
        ):
            raise ValueError("radial_edges_m must be nonnegative and increasing")
        for name, shape in expected_shapes.items():
            values = cast(FloatArray, getattr(self, name))
            if values.shape != shape or np.any(~np.isfinite(values)):
                raise ValueError(f"{name} must be finite with shape {shape}")

    def sample_point_force(self, time_s: float) -> FloatArray:
        return _sample_piecewise_linear(self.time_s, self.point_force_n, time_s)

    def average_point_force(self, start_time_s: float, end_time_s: float) -> FloatArray:
        return piecewise_linear_time_average(
            self.time_s, self.point_force_n, start_time_s, end_time_s
        )

    def to_hdf5(self, path: str | Path) -> None:
        """Atomically write the Kratos-ready table with checksummed datasets."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with h5py.File(temporary, "w") as handle:
                handle.attrs["schema_name"] = KRATOS_LOAD_SCHEMA_NAME
                handle.attrs["schema_version"] = KRATOS_LOAD_SCHEMA_VERSION
                handle.attrs["case_id"] = self.case_id
                handle.attrs["complete"] = False
                handle.attrs["units_system"] = "SI"
                handle.attrs["pressure_convention"] = "gauge-positive-in-compression"
                handle.attrs["load_semantics"] = "point-force-on-moving-mpm-condition"
                handle.attrs["metadata_json"] = json.dumps(
                    self.metadata, sort_keys=True
                )

                source = handle.create_group("source")
                time = source.create_dataset("time", data=self.time_s)
                time.attrs["units"] = "s"
                edges = source.create_dataset("radial_edges", data=self.radial_edges_m)
                edges.attrs["units"] = "m"
                pressure = source.create_dataset(
                    "pressure_gauge",
                    data=self.source_pressure_gauge_pa,
                    compression="gzip",
                    shuffle=True,
                    fletcher32=True,
                )
                pressure.attrs["units"] = "Pa"
                pressure.attrs["spatial_representation"] = "annulus_area_average"

                conditions = handle.create_group("conditions")
                conditions.create_dataset("ids", data=self.surface.condition_ids)
                coordinates = conditions.create_dataset(
                    "coordinates_initial", data=self.surface.coordinates_m
                )
                coordinates.attrs["units"] = "m"
                area = conditions.create_dataset(
                    "tributary_area", data=self.surface.tributary_areas_m2
                )
                area.attrs["units"] = "m2"
                conditions.create_dataset(
                    "outward_normal", data=self.surface.outward_normals
                )

                loads = handle.create_group("loads")
                mapped_pressure = loads.create_dataset(
                    "pressure_gauge",
                    data=self.mapped_pressure_gauge_pa,
                    compression="gzip",
                    shuffle=True,
                    fletcher32=True,
                )
                mapped_pressure.attrs["units"] = "Pa"
                mapped_pressure.attrs["location"] = "surface_condition"
                point_force = loads.create_dataset(
                    "point_force",
                    data=self.point_force_n,
                    compression="gzip",
                    shuffle=True,
                    fletcher32=True,
                )
                point_force.attrs["units"] = "N"
                point_force.attrs["sign_convention"] = (
                    "minus-pressure-times-area-times-outward-normal"
                )

                diagnostics = handle.create_group("diagnostics")
                diagnostics.create_dataset("source_force", data=self.source_force_n)
                diagnostics.create_dataset("target_force", data=self.target_force_n)
                handle.attrs.modify("complete", True)
                handle.flush()
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def from_hdf5(cls, path: str | Path) -> KratosLoadTable:
        with h5py.File(Path(path), "r") as handle:
            if str(handle.attrs.get("schema_name", "")) != KRATOS_LOAD_SCHEMA_NAME:
                raise ValueError("unsupported Kratos load schema")
            version = str(handle.attrs.get("schema_version", ""))
            if version.split(".", 1)[0] != KRATOS_LOAD_SCHEMA_VERSION.split(".", 1)[0]:
                raise ValueError(f"unsupported Kratos load schema version: {version}")
            if not bool(handle.attrs.get("complete", False)):
                raise ValueError("Kratos load table is incomplete")
            metadata = json.loads(str(handle.attrs.get("metadata_json", "{}")))
            if not isinstance(metadata, dict):
                raise ValueError("metadata_json must encode an object")
            missing_metadata = REQUIRED_KRATOS_METADATA.difference(metadata)
            if missing_metadata:
                raise ValueError(
                    "Kratos load table is missing metadata: "
                    + ", ".join(sorted(missing_metadata))
                )
            surface = KratosSurfacePoints(
                condition_ids=_int_array(handle["conditions/ids"][:]),
                coordinates_m=_float_array(handle["conditions/coordinates_initial"][:]),
                tributary_areas_m2=_float_array(handle["conditions/tributary_area"][:]),
                outward_normals=_float_array(handle["conditions/outward_normal"][:]),
            )
            return cls(
                case_id=str(handle.attrs["case_id"]),
                time_s=_float_array(handle["source/time"][:]),
                radial_edges_m=_float_array(handle["source/radial_edges"][:]),
                source_pressure_gauge_pa=_float_array(
                    handle["source/pressure_gauge"][:]
                ),
                surface=surface,
                mapped_pressure_gauge_pa=_float_array(
                    handle["loads/pressure_gauge"][:]
                ),
                point_force_n=_float_array(handle["loads/point_force"][:]),
                source_force_n=_float_array(handle["diagnostics/source_force"][:]),
                target_force_n=_float_array(handle["diagnostics/target_force"][:]),
                metadata=metadata,
            )


def build_kratos_load_table(
    history: WallLoadHistory,
    surface: KratosSurfacePoints,
    *,
    wall_origin_m: FloatArray | None = None,
    wall_x_axis: FloatArray | None = None,
    wall_y_axis: FloatArray | None = None,
    map_radius_m: float | None = None,
    plane_tolerance_m: float = 1.0e-9,
    source_sha256: str = "",
    surface_sha256: str = "",
) -> KratosLoadTable:
    """Map annular p(r,t) averages to Kratos moving point-load conditions."""

    origin = _float_array(np.zeros(3) if wall_origin_m is None else wall_origin_m)
    if origin.shape != (3,) or np.any(~np.isfinite(origin)):
        raise ValueError("wall_origin_m must be a finite three-vector")
    x_axis = _unit_vector(
        np.array([1.0, 0.0, 0.0]) if wall_x_axis is None else wall_x_axis,
        "wall_x_axis",
    )
    y_axis = _unit_vector(
        np.array([0.0, 1.0, 0.0]) if wall_y_axis is None else wall_y_axis,
        "wall_y_axis",
    )
    if not np.isclose(float(np.dot(x_axis, y_axis)), 0.0, atol=1e-12):
        raise ValueError("wall_x_axis and wall_y_axis must be orthogonal")
    if plane_tolerance_m <= 0:
        raise ValueError("plane_tolerance_m must be positive")
    relative = surface.coordinates_m - origin[None, :]
    plane_normal = np.cross(x_axis, y_axis)
    distances = np.abs(np.sum(relative * plane_normal[None, :], axis=1))
    if np.any(distances > plane_tolerance_m):
        raise ValueError("surface points do not lie in the specified wall plane")
    normal_alignment = np.sum(surface.outward_normals * plane_normal[None, :], axis=1)
    if not np.allclose(np.abs(normal_alignment), 1.0, rtol=1e-10, atol=1e-12) or (
        np.any(normal_alignment > 0.0) and np.any(normal_alignment < 0.0)
    ):
        raise ValueError("surface normals must be consistently normal to the wall")
    points_xy = np.column_stack(
        (
            np.sum(relative * x_axis[None, :], axis=1),
            np.sum(relative * y_axis[None, :], axis=1),
        )
    )
    quadrature = SurfaceQuadrature(
        points_xy_m=points_xy,
        tributary_areas_m2=surface.tributary_areas_m2,
        outward_normals=surface.outward_normals,
    )
    mapped = map_axisymmetric_load(history, quadrature, map_radius_m=map_radius_m)
    radius = (
        float(history.radial_edges_m[-1])
        if map_radius_m is None
        else float(map_radius_m)
    )
    metadata: dict[str, Any] = {
        "source_schema_name": "mc-andes-basilisk-wall-loads",
        "source_schema_version": WALL_LOAD_SCHEMA_VERSION,
        "source_case_id": history.case_id,
        "source_sha256": source_sha256,
        "surface_sha256": surface_sha256,
        "mapping": "annulus-sampling-with-global-minimum-l2-force-correction",
        "map_radius_m": radius,
        "wall_origin_m": origin.tolist(),
        "wall_x_axis": x_axis.tolist(),
        "wall_y_axis": y_axis.tolist(),
        "plane_tolerance_m": plane_tolerance_m,
        "maximum_relative_force_error": float(
            np.max(mapped.diagnostics.relative_force_error)
        ),
        "relative_impulse_error": mapped.diagnostics.relative_impulse_error,
        "maximum_relative_l2_correction": float(
            np.max(mapped.diagnostics.relative_l2_correction)
        ),
    }
    return KratosLoadTable(
        case_id=history.case_id,
        time_s=history.time_s,
        radial_edges_m=history.radial_edges_m,
        source_pressure_gauge_pa=history.pressure_gauge_pa,
        surface=surface,
        mapped_pressure_gauge_pa=mapped.pressure_pa,
        point_force_n=mapped.force_vectors_n,
        source_force_n=mapped.diagnostics.source_force_n,
        target_force_n=mapped.diagnostics.target_force_n,
        metadata=metadata,
    )


def match_surface_coordinates(
    reference_coordinates_m: FloatArray,
    query_coordinates_m: FloatArray,
    tolerance_m: float,
) -> IntArray:
    """Return a unique reference index for every query coordinate."""

    reference = _float_array(reference_coordinates_m)
    query = _float_array(query_coordinates_m)
    if reference.ndim != 2 or reference.shape[1] != 3:
        raise ValueError("reference_coordinates_m must have shape (n, 3)")
    if query.ndim != 2 or query.shape[1] != 3:
        raise ValueError("query_coordinates_m must have shape (m, 3)")
    if tolerance_m <= 0:
        raise ValueError("tolerance_m must be positive")
    if np.any(~np.isfinite(reference)) or np.any(~np.isfinite(query)):
        raise ValueError("coordinates must be finite")
    buckets: dict[tuple[int, int, int], list[int]] = {}
    reference_keys = np.floor(reference / tolerance_m).astype(np.int64)
    for index, key in enumerate(reference_keys):
        bucket_key = (int(key[0]), int(key[1]), int(key[2]))
        buckets.setdefault(bucket_key, []).append(index)
    offsets = (-1, 0, 1)
    matches: list[int] = []
    used: set[int] = set()
    for coordinate in query:
        key = np.floor(coordinate / tolerance_m).astype(np.int64)
        candidates: list[int] = []
        for dx in offsets:
            for dy in offsets:
                for dz in offsets:
                    candidates.extend(
                        buckets.get(
                            (int(key[0] + dx), int(key[1] + dy), int(key[2] + dz)),
                            [],
                        )
                    )
        within = [
            index
            for index in candidates
            if np.linalg.norm(reference[index] - coordinate) <= tolerance_m
            and index not in used
        ]
        if len(within) != 1:
            raise ValueError("surface coordinate matching is not one-to-one")
        matches.append(within[0])
        used.add(within[0])
    return np.array(matches, dtype=np.int64)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Map an annular wall-load HDF5 to Kratos MPM point conditions."
    )
    parser.add_argument("wall_loads", type=Path)
    parser.add_argument("surface_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--wall-origin", nargs=3, type=float, default=(0.0, 0.0, 0.0))
    parser.add_argument("--wall-x-axis", nargs=3, type=float, default=(1.0, 0.0, 0.0))
    parser.add_argument("--wall-y-axis", nargs=3, type=float, default=(0.0, 1.0, 0.0))
    parser.add_argument("--map-radius", type=float)
    parser.add_argument("--plane-tolerance", type=float, default=1.0e-9)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    history = WallLoadHistory.from_hdf5(args.wall_loads)
    surface = KratosSurfacePoints.from_csv(args.surface_csv)
    table = build_kratos_load_table(
        history,
        surface,
        wall_origin_m=np.array(args.wall_origin, dtype=np.float64),
        wall_x_axis=np.array(args.wall_x_axis, dtype=np.float64),
        wall_y_axis=np.array(args.wall_y_axis, dtype=np.float64),
        map_radius_m=args.map_radius,
        plane_tolerance_m=args.plane_tolerance,
        source_sha256=_sha256(args.wall_loads),
        surface_sha256=_sha256(args.surface_csv),
    )
    table.to_hdf5(args.output)
    print(args.output)
    print(
        "maximum relative force error: "
        f"{table.metadata['maximum_relative_force_error']:.3e}"
    )
    print(f"relative impulse error: {table.metadata['relative_impulse_error']:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

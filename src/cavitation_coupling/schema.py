"""Versioned HDF5 exchange schema for axisymmetric wall-load histories."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import h5py
import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
SCHEMA_NAME = "mc-andes-basilisk-wall-loads"
SCHEMA_VERSION = "1.1.0"


def _as_float_array(value: Any) -> FloatArray:
    return cast(FloatArray, np.asarray(value, dtype=np.float64))


def _trapezoidal_integral(values: FloatArray, time_s: FloatArray) -> FloatArray:
    dt = np.diff(time_s)
    return cast(
        FloatArray,
        np.sum(0.5 * (values[1:] + values[:-1]) * dt[:, None], axis=0),
    )


@dataclass(frozen=True)
class WallLoadHistory:
    """Cell-average wall tractions over concentric annuli.

    Pressure is gauge pressure, positive in compression. ``radial_edges_m``
    defines the annuli; fields have shape ``(n_times, n_annuli)``.
    """

    case_id: str
    time_s: FloatArray
    radial_edges_m: FloatArray
    pressure_gauge_pa: FloatArray
    shear_radial_pa: FloatArray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_s", _as_float_array(self.time_s))
        object.__setattr__(self, "radial_edges_m", _as_float_array(self.radial_edges_m))
        object.__setattr__(
            self, "pressure_gauge_pa", _as_float_array(self.pressure_gauge_pa)
        )
        object.__setattr__(
            self, "shear_radial_pa", _as_float_array(self.shear_radial_pa)
        )
        self.validate()

    @property
    def n_times(self) -> int:
        return int(self.time_s.size)

    @property
    def n_annuli(self) -> int:
        return int(self.radial_edges_m.size - 1)

    @property
    def radial_centers_m(self) -> FloatArray:
        return 0.5 * (self.radial_edges_m[:-1] + self.radial_edges_m[1:])

    @property
    def impulse_pressure_pa_s(self) -> FloatArray:
        return _trapezoidal_integral(self.pressure_gauge_pa, self.time_s)

    @property
    def force_normal_n(self) -> FloatArray:
        annular_areas = np.pi * (
            self.radial_edges_m[1:] ** 2 - self.radial_edges_m[:-1] ** 2
        )
        return cast(
            FloatArray,
            np.sum(self.pressure_gauge_pa * annular_areas[None, :], axis=1),
        )

    def validate(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.time_s.ndim != 1 or self.time_s.size < 2:
            raise ValueError("time_s must be one-dimensional with at least 2 values")
        if np.any(~np.isfinite(self.time_s)) or np.any(np.diff(self.time_s) <= 0):
            raise ValueError("time_s must be finite and strictly increasing")
        if self.radial_edges_m.ndim != 1 or self.radial_edges_m.size < 2:
            raise ValueError("radial_edges_m must define at least one annulus")
        if self.radial_edges_m[0] < 0 or np.any(np.diff(self.radial_edges_m) <= 0):
            raise ValueError("radial_edges_m must be nonnegative and increasing")
        expected = (self.n_times, self.n_annuli)
        for name, values in (
            ("pressure_gauge_pa", self.pressure_gauge_pa),
            ("shear_radial_pa", self.shear_radial_pa),
        ):
            if values.shape != expected:
                raise ValueError(f"{name} must have shape {expected}")
            if np.any(~np.isfinite(values)):
                raise ValueError(f"{name} must contain only finite values")

    def to_hdf5(self, path: str | Path) -> None:
        """Atomically write a self-describing, compressed HDF5 exchange file."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            self._write_hdf5(temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_hdf5(self, target: Path) -> None:
        with h5py.File(target, "w") as handle:
            handle.attrs["schema_name"] = SCHEMA_NAME
            handle.attrs["schema_version"] = SCHEMA_VERSION
            handle.attrs["case_id"] = self.case_id
            handle.attrs["complete"] = False
            handle.attrs["units_system"] = "SI"
            handle.attrs["coordinate_system"] = "axisymmetric-rz"
            handle.attrs["pressure_convention"] = "gauge-positive-in-compression"
            handle.attrs["temporal_interpolation"] = "piecewise-linear"
            handle.attrs["metadata_json"] = json.dumps(self.metadata, sort_keys=True)

            coordinates = handle.create_group("coordinates")
            radial_edges = coordinates.create_dataset(
                "radial_edges", data=self.radial_edges_m
            )
            radial_edges.attrs["units"] = "m"
            radial_edges.attrs["location"] = "annulus_edges"

            time = handle.create_dataset("time", data=self.time_s)
            time.attrs["units"] = "s"

            fields = handle.create_group("fields")
            pressure = fields.create_dataset(
                "pressure_gauge",
                data=self.pressure_gauge_pa,
                compression="gzip",
                shuffle=True,
                fletcher32=True,
            )
            pressure.attrs["units"] = "Pa"
            pressure.attrs["spatial_representation"] = "annulus_area_average"
            shear = fields.create_dataset(
                "shear_radial",
                data=self.shear_radial_pa,
                compression="gzip",
                shuffle=True,
                fletcher32=True,
            )
            shear.attrs["units"] = "Pa"
            shear.attrs["spatial_representation"] = "annulus_area_average"

            derived = handle.create_group("derived")
            impulse = derived.create_dataset(
                "impulse_pressure", data=self.impulse_pressure_pa_s
            )
            impulse.attrs["units"] = "Pa s"
            force = derived.create_dataset("force_normal", data=self.force_normal_n)
            force.attrs["units"] = "N"
            force.attrs["sign_convention"] = "positive-compression-magnitude"
            handle.attrs.modify("complete", True)
            handle.flush()

    @classmethod
    def from_hdf5(cls, path: str | Path) -> WallLoadHistory:
        """Read and validate an exchange file with the current schema."""

        with h5py.File(Path(path), "r") as handle:
            schema_name = str(handle.attrs.get("schema_name", ""))
            schema_version = str(handle.attrs.get("schema_version", ""))
            if schema_name != SCHEMA_NAME:
                raise ValueError(f"unsupported schema_name: {schema_name!r}")
            if schema_version.split(".", 1)[0] != SCHEMA_VERSION.split(".", 1)[0]:
                raise ValueError(f"unsupported schema_version: {schema_version!r}")
            if "complete" in handle.attrs and not bool(handle.attrs["complete"]):
                raise ValueError("wall-load file is incomplete")
            raw_metadata = str(handle.attrs.get("metadata_json", "{}"))
            metadata = json.loads(raw_metadata)
            if not isinstance(metadata, dict):
                raise ValueError("metadata_json must encode an object")
            return cls(
                case_id=str(handle.attrs["case_id"]),
                time_s=_as_float_array(handle["time"][:]),
                radial_edges_m=_as_float_array(handle["coordinates/radial_edges"][:]),
                pressure_gauge_pa=_as_float_array(handle["fields/pressure_gauge"][:]),
                shear_radial_pa=_as_float_array(handle["fields/shear_radial"][:]),
                metadata=metadata,
            )

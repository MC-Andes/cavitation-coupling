"""Export wall-load histories as ParaView-readable VTK XML datasets."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from cavitation_coupling.schema import FloatArray, WallLoadHistory

IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class ParaviewBundle:
    """Paths produced for a ParaView visualization bundle."""

    pressure_series: Path
    radial_time_map: Path
    force_history: Path
    manifest: Path


def _ascii(values: FloatArray | IntArray) -> str:
    flattened = values.ravel(order="C")
    if np.issubdtype(flattened.dtype, np.integer):
        return " ".join(str(int(value)) for value in flattened)
    return " ".join(f"{float(value):.12g}" for value in flattened)


def _data_array(
    parent: ET.Element,
    name: str,
    values: FloatArray | IntArray,
    *,
    vtk_type: str = "Float64",
    components: int | None = None,
) -> ET.Element:
    attributes = {"type": vtk_type, "Name": name, "format": "ascii"}
    if components is not None:
        attributes["NumberOfComponents"] = str(components)
    element = ET.SubElement(parent, "DataArray", attributes)
    element.text = _ascii(values)
    return element


def _write_xml(root: ET.Element, path: Path) -> None:
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _frame_indices(n_times: int, stride: int) -> list[int]:
    if stride < 1:
        raise ValueError("frame_stride must be at least 1")
    indices = list(range(0, n_times, stride))
    if indices[-1] != n_times - 1:
        indices.append(n_times - 1)
    return indices


def _pressure_on_cartesian_grid(
    history: WallLoadHistory, time_index: int, grid_points: int
) -> tuple[FloatArray, FloatArray, float, float]:
    if grid_points < 9 or grid_points % 2 == 0:
        raise ValueError("grid_points must be an odd integer of at least 9")
    radius = float(history.radial_edges_m[-1])
    coordinates = np.linspace(-radius, radius, grid_points, dtype=np.float64)
    x_coord, y_coord = np.meshgrid(coordinates, coordinates, indexing="xy")
    radii = np.sqrt(x_coord**2 + y_coord**2)
    indices = np.searchsorted(history.radial_edges_m, radii, side="right") - 1
    on_outer_edge = np.isclose(radii, radius, rtol=0.0, atol=1e-14)
    indices[on_outer_edge] = history.n_annuli - 1
    active = (indices >= 0) & (indices < history.n_annuli) & (radii <= radius)
    pressure_mpa = np.zeros_like(radii)
    pressure_mpa[active] = (
        history.pressure_gauge_pa[time_index, indices[active]] / 1.0e6
    )
    mask = active.astype(np.float64)
    spacing = float(coordinates[1] - coordinates[0])
    # ParaView axes are easier to read at this scale when the visualization
    # geometry is expressed in millimetres. The physical load data remain in
    # MPa and the coupling schema remains strictly SI.
    return pressure_mpa, mask, -radius * 1.0e3, spacing * 1.0e3


def _write_vti_frame(
    history: WallLoadHistory,
    time_index: int,
    grid_points: int,
    path: Path,
) -> None:
    pressure_mpa, mask, origin, spacing = _pressure_on_cartesian_grid(
        history, time_index, grid_points
    )
    extent = f"0 {grid_points - 1} 0 {grid_points - 1} 0 0"
    root = ET.Element(
        "VTKFile",
        {"type": "ImageData", "version": "0.1", "byte_order": "LittleEndian"},
    )
    image = ET.SubElement(
        root,
        "ImageData",
        {
            "WholeExtent": extent,
            "Origin": f"{origin:.12g} {origin:.12g} 0",
            "Spacing": f"{spacing:.12g} {spacing:.12g} 1",
        },
    )
    piece = ET.SubElement(image, "Piece", {"Extent": extent})
    point_data = ET.SubElement(piece, "PointData", {"Scalars": "pressure_gauge_MPa"})
    _data_array(point_data, "pressure_gauge_MPa", pressure_mpa)
    _data_array(point_data, "loaded_area_mask", mask)
    ET.SubElement(piece, "CellData")
    field_data = ET.SubElement(piece, "FieldData")
    _data_array(
        field_data,
        "time_s",
        np.array([history.time_s[time_index]], dtype=np.float64),
    )
    _data_array(
        field_data,
        "time_us",
        np.array([history.time_s[time_index] * 1.0e6], dtype=np.float64),
    )
    _write_xml(root, path)


def _write_pvd(
    history: WallLoadHistory,
    indices: list[int],
    frame_names: list[str],
    path: Path,
) -> None:
    root = ET.Element(
        "VTKFile",
        {"type": "Collection", "version": "0.1", "byte_order": "LittleEndian"},
    )
    collection = ET.SubElement(root, "Collection")
    for time_index, frame_name in zip(indices, frame_names, strict=True):
        ET.SubElement(
            collection,
            "DataSet",
            {
                "timestep": f"{history.time_s[time_index]:.12g}",
                "group": "wall-loads",
                "part": "0",
                "file": frame_name,
            },
        )
    _write_xml(root, path)


def _write_radial_time_map(history: WallLoadHistory, path: Path) -> None:
    n_radius = history.n_annuli
    n_times = history.n_times
    extent = f"0 {n_radius - 1} 0 {n_times - 1} 0 0"
    root = ET.Element(
        "VTKFile",
        {
            "type": "RectilinearGrid",
            "version": "0.1",
            "byte_order": "LittleEndian",
        },
    )
    grid = ET.SubElement(root, "RectilinearGrid", {"WholeExtent": extent})
    piece = ET.SubElement(grid, "Piece", {"Extent": extent})
    point_data = ET.SubElement(piece, "PointData", {"Scalars": "pressure_gauge_MPa"})
    _data_array(point_data, "pressure_gauge_MPa", history.pressure_gauge_pa / 1.0e6)
    impulse_map = np.tile(history.impulse_pressure_pa_s[None, :] * 1.0e-6, (n_times, 1))
    _data_array(point_data, "impulse_MPa_us", impulse_map)
    ET.SubElement(piece, "CellData")
    coordinates = ET.SubElement(piece, "Coordinates")
    _data_array(coordinates, "radius_mm", history.radial_centers_m * 1.0e3)
    _data_array(coordinates, "time_us", history.time_s * 1.0e6)
    _data_array(coordinates, "z", np.array([0.0], dtype=np.float64))
    _write_xml(root, path)


def _write_force_history(history: WallLoadHistory, path: Path) -> None:
    n_points = history.n_times
    time_us = history.time_s * 1.0e6
    force_n = history.force_normal_n
    points = np.column_stack((time_us, force_n, np.zeros(n_points)))
    connectivity = np.arange(n_points, dtype=np.int64)
    offsets = np.array([n_points], dtype=np.int64)

    root = ET.Element(
        "VTKFile",
        {"type": "PolyData", "version": "0.1", "byte_order": "LittleEndian"},
    )
    poly_data = ET.SubElement(root, "PolyData")
    piece = ET.SubElement(
        poly_data,
        "Piece",
        {
            "NumberOfPoints": str(n_points),
            "NumberOfVerts": "0",
            "NumberOfLines": "1",
            "NumberOfStrips": "0",
            "NumberOfPolys": "0",
        },
    )
    point_data = ET.SubElement(piece, "PointData")
    _data_array(point_data, "time_us", time_us)
    _data_array(point_data, "force_normal_N", force_n)
    ET.SubElement(piece, "CellData")
    points_element = ET.SubElement(piece, "Points")
    _data_array(points_element, "Points", points, components=3)
    lines = ET.SubElement(piece, "Lines")
    _data_array(lines, "connectivity", connectivity, vtk_type="Int64")
    _data_array(lines, "offsets", offsets, vtk_type="Int64")
    _write_xml(root, path)


def export_paraview_bundle(
    history: WallLoadHistory,
    output_dir: str | Path,
    *,
    grid_points: int = 101,
    frame_stride: int = 1,
) -> ParaviewBundle:
    """Write pressure animation, radial-time map and force history for ParaView."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    indices = _frame_indices(history.n_times, frame_stride)
    frame_names: list[str] = []
    for frame_number, time_index in enumerate(indices):
        name = f"wall-pressure-{frame_number:04d}.vti"
        _write_vti_frame(history, time_index, grid_points, frames / name)
        frame_names.append(f"frames/{name}")

    pressure_series = output / "wall-pressure.pvd"
    radial_time_map = output / "radial-time.vtr"
    force_history = output / "force-history.vtp"
    manifest = output / "manifest.json"
    _write_pvd(history, indices, frame_names, pressure_series)
    _write_radial_time_map(history, radial_time_map)
    _write_force_history(history, force_history)

    peak_index = int(np.argmax(np.abs(history.pressure_gauge_pa)))
    peak_time_index, peak_annulus_index = np.unravel_index(
        peak_index, history.pressure_gauge_pa.shape
    )
    manifest.write_text(
        json.dumps(
            {
                "case_id": history.case_id,
                "data_kind": "wall-load visualization",
                "source_warning": history.metadata.get("warning", ""),
                "n_frames": len(indices),
                "grid_points": grid_points,
                "peak_pressure_MPa": float(
                    history.pressure_gauge_pa[peak_time_index, peak_annulus_index]
                    / 1.0e6
                ),
                "peak_pressure_time_s": float(history.time_s[peak_time_index]),
                "peak_force_N": float(np.max(np.abs(history.force_normal_n))),
                "files": {
                    "pressure_series": pressure_series.name,
                    "radial_time_map": radial_time_map.name,
                    "force_history": force_history.name,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return ParaviewBundle(
        pressure_series=pressure_series,
        radial_time_map=radial_time_map,
        force_history=force_history,
        manifest=manifest,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cavitation-paraview-export")
    parser.add_argument("input", type=Path, help="wall-load HDF5 file")
    parser.add_argument("output", type=Path, help="output bundle directory")
    parser.add_argument("--grid-points", type=int, default=101)
    parser.add_argument("--frame-stride", type=int, default=1)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    history = WallLoadHistory.from_hdf5(args.input)
    bundle = export_paraview_bundle(
        history,
        args.output,
        grid_points=args.grid_points,
        frame_stride=args.frame_stride,
    )
    print(bundle.pressure_series)
    print(bundle.radial_time_map)
    print(bundle.force_history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

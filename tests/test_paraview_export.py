from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from cavitation_coupling.paraview_export import export_paraview_bundle, main
from cavitation_coupling.schema import WallLoadHistory


def small_history() -> WallLoadHistory:
    return WallLoadHistory(
        case_id="paraview-test",
        time_s=np.array([0.0, 1.0e-6, 2.0e-6]),
        radial_edges_m=np.array([0.0, 1.0e-3, 2.0e-3]),
        pressure_gauge_pa=np.array([[0.0, 0.0], [2.0e6, 1.0e6], [0.0, 0.0]]),
        shear_radial_pa=np.zeros((3, 2)),
        metadata={"warning": "synthetic"},
    )


def test_export_bundle_is_valid_vtk_xml(tmp_path: Path) -> None:
    bundle = export_paraview_bundle(
        small_history(), tmp_path / "bundle", grid_points=9, frame_stride=2
    )
    pvd = ET.parse(bundle.pressure_series).getroot()
    datasets = pvd.findall("./Collection/DataSet")
    assert len(datasets) == 2
    frame = ET.parse(bundle.pressure_series.parent / datasets[1].attrib["file"])
    names = {element.attrib.get("Name") for element in frame.findall(".//DataArray")}
    assert "pressure_gauge_MPa" in names
    assert "loaded_area_mask" in names
    assert ET.parse(bundle.radial_time_map).getroot().attrib["type"] == (
        "RectilinearGrid"
    )
    assert ET.parse(bundle.force_history).getroot().attrib["type"] == "PolyData"
    manifest = json.loads(bundle.manifest.read_text(encoding="utf-8"))
    assert manifest["peak_pressure_MPa"] == 2.0
    assert manifest["source_warning"] == "synthetic"


def test_export_rejects_invalid_visual_grid(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="odd integer"):
        export_paraview_bundle(small_history(), tmp_path, grid_points=10)
    with pytest.raises(ValueError, match="frame_stride"):
        export_paraview_bundle(small_history(), tmp_path, frame_stride=0)


def test_export_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "loads.h5"
    output = tmp_path / "bundle"
    small_history().to_hdf5(source)
    assert main([str(source), str(output), "--grid-points", "9"]) == 0
    printed = capsys.readouterr().out
    assert "wall-pressure.pvd" in printed
    assert (output / "force-history.vtp").exists()

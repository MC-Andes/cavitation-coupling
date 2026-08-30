from __future__ import annotations

import json

import numpy as np
import pytest

from cavitation_coupling.cli import main
from cavitation_coupling.schema import WallLoadHistory


def test_cli_reports_valid_file(
    tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "loads.h5"  # type: ignore[operator]
    WallLoadHistory(
        case_id="cli-case",
        time_s=np.array([0.0, 1.0]),
        radial_edges_m=np.array([0.0, 1.0]),
        pressure_gauge_pa=np.array([[0.0], [2.0]]),
        shear_radial_pa=np.zeros((2, 1)),
    ).to_hdf5(path)
    assert main([str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["case_id"] == "cli-case"
    assert output["schema_valid"] is True

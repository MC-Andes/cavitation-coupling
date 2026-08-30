"""Small command-line validator for wall-load exchange files."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from cavitation_coupling.mapping import force_from_annular_averages
from cavitation_coupling.schema import WallLoadHistory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cavitation-coupling")
    parser.add_argument("file", type=Path, help="HDF5 wall-load file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    history = WallLoadHistory.from_hdf5(args.file)
    force = force_from_annular_averages(
        history.pressure_gauge_pa, history.radial_edges_m
    )
    summary = {
        "case_id": history.case_id,
        "n_annuli": history.n_annuli,
        "n_times": history.n_times,
        "peak_abs_force_N": float(np.max(np.abs(force))),
        "peak_abs_pressure_Pa": float(np.max(np.abs(history.pressure_gauge_pa))),
        "schema_valid": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

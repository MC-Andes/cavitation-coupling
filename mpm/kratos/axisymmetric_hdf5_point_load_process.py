"""Kratos Process applying a pre-integrated p(r,t) load table to MPM conditions.

This file is loaded by Kratos through ``ProjectParameters.json``. Install the
``mc-andes-cavitation-coupling`` package in the same Python environment and add
this directory to ``PYTHONPATH`` before launching ``MainKratos.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

import KratosMultiphysics as KM
import KratosMultiphysics.MPMApplication as KMPM
import numpy as np
from KratosMultiphysics.MPMApplication import (
    apply_mpm_particle_neumann_condition_process as particle_neumann,
)

from cavitation_coupling.kratos import (
    KratosLoadTable,
    match_surface_coordinates,
    piecewise_linear_time_average,
)


def Factory(settings, model):
    if not isinstance(settings, KM.Parameters):
        raise TypeError("settings must be a Kratos Parameters object")
    return AxisymmetricHdf5PointLoadProcess(model, settings["Parameters"])


class AxisymmetricHdf5PointLoadProcess(KM.Process):
    """Apply exact-step-average forces to moving MPM point-load conditions."""

    def __init__(self, model, settings):
        super().__init__()
        defaults = KM.Parameters(
            r"""
            {
                "model_part_name": "PLEASE_SPECIFY_MODEL_PART_NAME",
                "kratos_loads_hdf5": "PLEASE_SPECIFY_LOAD_TABLE",
                "material_points_per_condition": 1,
                "time_sampling": "step_average",
                "coordinate_tolerance_m": 1e-10,
                "diagnostics_csv": ""
            }
            """
        )
        settings.ValidateAndAssignDefaults(defaults)
        self._load_path = Path(settings["kratos_loads_hdf5"].GetString()).resolve()
        self._sampling = settings["time_sampling"].GetString()
        if self._sampling not in {"step_average", "linear"}:
            raise ValueError("time_sampling must be 'step_average' or 'linear'")
        self._coordinate_tolerance_m = settings["coordinate_tolerance_m"].GetDouble()
        if self._coordinate_tolerance_m <= 0:
            raise ValueError("coordinate_tolerance_m must be positive")
        diagnostic_name = settings["diagnostics_csv"].GetString()
        self._diagnostics_path = (
            Path(diagnostic_name).resolve() if diagnostic_name else None
        )
        points_per_condition = settings["material_points_per_condition"].GetInt()
        if points_per_condition != 1:
            raise ValueError(
                "Kratos Point3D load conditions require exactly one material "
                "point per condition"
            )

        base_settings = KM.Parameters(
            r"""
            {
                "model_part_name": "",
                "material_points_per_condition": 1,
                "variable_name": "POINT_LOAD",
                "modulus": 0.0,
                "constrained": "fixed",
                "direction": [0.0, 0.0, 0.0],
                "interval": [0.0, 1e30],
                "option": "",
                "local_axes": {}
            }
            """
        )
        base_settings["model_part_name"].SetString(
            settings["model_part_name"].GetString()
        )
        base_settings["material_points_per_condition"].SetInt(points_per_condition)
        self._base_process = particle_neumann.ApplyMPMParticleNeumannConditionProcess(
            model, base_settings
        )
        self._conditions = []
        self._table_indices = np.empty(0, dtype=np.int64)
        self._table = None
        self._model_part = None

    def ExecuteBeforeSolutionLoop(self):
        self._base_process.ExecuteBeforeSolutionLoop()
        self._model_part = self._base_process.model_part
        self._table = KratosLoadTable.from_hdf5(self._load_path)
        self._conditions = list(self._model_part.Conditions)
        if len(self._conditions) != self._table.surface.n_points:
            raise RuntimeError(
                "the Kratos load submodelpart and HDF5 table have different "
                "numbers of point conditions"
            )
        coordinates = np.array(
            [
                condition.CalculateOnIntegrationPoints(
                    KMPM.MPC_COORD, self._model_part.ProcessInfo
                )[0]
                for condition in self._conditions
            ],
            dtype=np.float64,
        )
        self._table_indices = match_surface_coordinates(
            self._table.surface.coordinates_m,
            coordinates,
            self._coordinate_tolerance_m,
        )
        self._initialize_diagnostics()
        self.ExecuteInitializeSolutionStep()

    def ExecuteInitializeSolutionStep(self):
        if self._table is None or self._model_part is None:
            return
        current_time = float(self._model_part.ProcessInfo[KM.TIME])
        delta_time = float(self._model_part.ProcessInfo[KM.DELTA_TIME])
        first_time = float(self._table.time_s[0])
        tolerance = (
            10.0
            * np.finfo(np.float64).eps
            * max(1.0, abs(float(self._table.time_s[-1])))
        )

        if (
            self._sampling == "step_average"
            and delta_time > 0.0
            and current_time - delta_time >= first_time - tolerance
        ):
            start_time = max(first_time, current_time - delta_time)
            forces = self._table.average_point_force(start_time, current_time)
            source_force = float(
                piecewise_linear_time_average(
                    self._table.time_s,
                    self._table.source_force_n,
                    start_time,
                    current_time,
                )
            )
        else:
            start_time = current_time
            forces = self._table.sample_point_force(current_time)
            source_force = float(
                np.interp(current_time, self._table.time_s, self._table.source_force_n)
            )

        ordered_forces = forces[self._table_indices]
        for condition, force in zip(self._conditions, ordered_forces, strict=True):
            value = KM.Vector(3)
            for component in range(3):
                value[component] = float(force[component])
            condition.SetValuesOnIntegrationPoints(
                KMPM.POINT_LOAD, [value], self._model_part.ProcessInfo
            )
        self._append_diagnostics(
            start_time,
            current_time,
            source_force,
            np.sum(ordered_forces, axis=0),
        )

    def _initialize_diagnostics(self):
        if self._diagnostics_path is None:
            return
        self._diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._diagnostics_path.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(
                [
                    "step_start_s",
                    "step_end_s",
                    "source_force_n",
                    "applied_fx_n",
                    "applied_fy_n",
                    "applied_fz_n",
                ]
            )

    def _append_diagnostics(self, start, end, source_force, applied_force):
        if self._diagnostics_path is None:
            return
        with self._diagnostics_path.open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(
                [start, end, source_force, *[float(value) for value in applied_force]]
            )

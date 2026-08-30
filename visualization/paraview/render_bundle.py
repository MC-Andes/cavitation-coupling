"""Render and save a ParaView state for a wall-load visualization bundle.

Run this file with ParaView's ``pvpython``, not regular Python.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paraview.simple import (  # type: ignore[import-not-found]
    AssignViewToLayout,
    ColorBy,
    CreateLayout,
    CreateView,
    GetAnimationScene,
    GetColorTransferFunction,
    GetOpacityTransferFunction,
    GetScalarBar,
    PVDReader,
    Render,
    ResetSession,
    SaveScreenshot,
    SaveState,
    Show,
    Text,
    XMLRectilinearGridReader,
)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("bundle", type=Path)
    argument_parser.add_argument("--output", type=Path)
    argument_parser.add_argument("--state", type=Path)
    return argument_parser


def configure_plane_view(view: object) -> None:
    view.OrientationAxesVisibility = 1
    view.CameraParallelProjection = 1
    view.Background = [0.96, 0.97, 0.99]
    view.UseColorPaletteForBackground = 0


def configure_axes(display: object, x_title: str, y_title: str) -> None:
    axes = display.DataAxesGrid
    axes.GridAxesVisibility = 1
    axes.XTitle = x_title
    axes.YTitle = y_title
    axes.XTitleColor = [0.10, 0.11, 0.14]
    axes.YTitleColor = [0.10, 0.11, 0.14]
    axes.XLabelColor = [0.10, 0.11, 0.14]
    axes.YLabelColor = [0.10, 0.11, 0.14]
    axes.XTitleFontSize = 15
    axes.YTitleFontSize = 15
    axes.XLabelFontSize = 12
    axes.YLabelFontSize = 12
    axes.ShowGrid = 1
    axes.GridColor = [0.78, 0.80, 0.84]


def configure_scalar_bar(lut: object, view: object) -> None:
    bar = GetScalarBar(lut, view)
    bar.Title = "Presión manométrica"
    bar.ComponentTitle = "MPa"
    bar.TitleColor = [0.10, 0.11, 0.14]
    bar.LabelColor = [0.10, 0.11, 0.14]
    bar.TitleFontSize = 15
    bar.LabelFontSize = 12
    bar.ScalarBarThickness = 16
    bar.ScalarBarLength = 0.42


def add_title(view: object, text: str) -> None:
    source = Text(registrationName=text)
    source.Text = text
    display = Show(source, view)
    display.WindowLocation = "Upper Center"
    display.Color = [0.08, 0.09, 0.12]
    display.FontSize = 18
    display.Bold = 1


def main() -> int:
    args = parser().parse_args()
    bundle = args.bundle.resolve()
    output = (args.output or bundle / "paraview-preview.png").resolve()
    state = (args.state or bundle / "cavitation-wall-loads.pvsm").resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

    ResetSession()
    pressure_reader = PVDReader(
        registrationName="Presión de pared", FileName=str(bundle / "wall-pressure.pvd")
    )
    radial_reader = XMLRectilinearGridReader(
        registrationName="Mapa radial-tiempo",
        FileName=[str(bundle / "radial-time.vtr")],
    )

    pressure_view = CreateView("RenderView")
    pressure_view.ViewSize = [900, 760]
    configure_plane_view(pressure_view)
    pressure_display = Show(pressure_reader, pressure_view, "UniformGridRepresentation")
    pressure_display.Representation = "Surface"
    ColorBy(pressure_display, ("POINTS", "pressure_gauge_MPa"))
    pressure_lut = GetColorTransferFunction("pressure_gauge_MPa")
    pressure_lut.RescaleTransferFunction(0.0, manifest["peak_pressure_MPa"])
    pressure_lut.ApplyPreset("Inferno", True)
    pressure_pwf = GetOpacityTransferFunction("pressure_gauge_MPa")
    pressure_pwf.RescaleTransferFunction(0.0, manifest["peak_pressure_MPa"])
    pressure_display.SetScalarBarVisibility(pressure_view, True)
    configure_axes(pressure_display, "x [mm]", "y [mm]")
    configure_scalar_bar(pressure_lut, pressure_view)
    add_title(
        pressure_view,
        f"Carga superficial a t = {manifest['peak_pressure_time_s'] * 1.0e6:.2f} µs",
    )

    radial_view = CreateView("RenderView")
    radial_view.ViewSize = [900, 760]
    configure_plane_view(radial_view)
    radial_display = Show(radial_reader, radial_view, "RectilinearGridRepresentation")
    radial_display.Representation = "Surface"
    ColorBy(radial_display, ("POINTS", "pressure_gauge_MPa"))
    radial_display.LookupTable = pressure_lut
    radial_display.SetScalarBarVisibility(radial_view, True)
    configure_axes(radial_display, "radio [mm]", "tiempo [µs]")
    configure_scalar_bar(pressure_lut, radial_view)
    add_title(radial_view, "Mapa radial–tiempo p_w(r,t)")

    layout = CreateLayout(name="Cargas de cavitación")
    layout.SplitHorizontal(0, 0.52)
    AssignViewToLayout(view=pressure_view, layout=layout, hint=1)
    AssignViewToLayout(view=radial_view, layout=layout, hint=2)

    scene = GetAnimationScene()
    scene.UpdateAnimationUsingDataTimeSteps()
    scene.AnimationTime = manifest["peak_pressure_time_s"]
    pressure_reader.UpdatePipeline(time=scene.AnimationTime)
    pressure_view.ResetCamera()
    radial_view.ResetCamera()
    Render(pressure_view)
    Render(radial_view)
    SaveScreenshot(str(output), layout, ImageResolution=[1800, 760])
    SaveState(str(state))
    print(output)
    print(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Thin repository entry point for the ParaView export command."""

from __future__ import annotations

from cavitation_coupling.paraview_export import main

if __name__ == "__main__":
    raise SystemExit(main())

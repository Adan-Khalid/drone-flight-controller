"""Battery input range for a LiPo-powered flight controller.

A LiPo pack of N cells in series has a voltage of N times the cell voltage. The board must
work from the emptiest pack it supports (fewest cells, lowest safe cell voltage) up to the
fullest (most cells, fully charged), and survive high-voltage (HV) cells charged higher.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InputRange:
    """Battery voltage range the board must handle, in volts."""

    v_min: float
    v_max: float
    v_max_hv: float


def pack_voltage(cells: int, cell_v: float) -> float:
    """Voltage of a pack of `cells` LiPo cells in series, each at `cell_v` volts."""
    if cells < 1:
        raise ValueError("a pack needs at least one cell")
    if cell_v <= 0:
        raise ValueError("cell voltage must be positive")
    return cells * cell_v


def input_range(
    cells_min: int,
    cells_max: int,
    cell_v_min: float,
    cell_v_full: float,
    cell_v_full_hv: float,
) -> InputRange:
    """Lowest and highest battery voltage for packs from `cells_min` to `cells_max` cells."""
    if cells_min > cells_max:
        raise ValueError("cells_min must not exceed cells_max")
    if not cell_v_min < cell_v_full <= cell_v_full_hv:
        raise ValueError("expected cell_v_min < cell_v_full <= cell_v_full_hv")
    return InputRange(
        v_min=pack_voltage(cells_min, cell_v_min),
        v_max=pack_voltage(cells_max, cell_v_full),
        v_max_hv=pack_voltage(cells_max, cell_v_full_hv),
    )

"""Read the DMA plan out of the hwdef.h that ArduPilot's chibios_hwdef.py generates."""

from __future__ import annotations

import re
from dataclasses import dataclass

UNRESOLVED_MARK = "can't be resolved for DMA"

_STREAM = re.compile(
    r"#define STM32_(?:SPI|TIM|UART|ADC|I2C|SDMMC)_(?P<periph>[A-Z0-9_]+?)_DMA_STREAM\s+"
    r"STM32_DMA_STREAM_ID\((?P<dma>\d+),\s*(?P<stream>\d+)\)(?:\s*//\s*shared\s*(?P<shared>.*))?"
)


@dataclass(frozen=True)
class DmaAssignment:
    peripheral: str
    dma: int
    stream: int
    shared_with: tuple[str, ...]


def unresolved_line(hwdef_h: str) -> str | None:
    """The line listing peripherals that got no DMA stream, or None if every request was met."""
    for line in hwdef_h.splitlines():
        if UNRESOLVED_MARK in line:
            return line.strip()
    return None


def dma_assignments(hwdef_h: str) -> list[DmaAssignment]:
    """Every DMA stream assignment written by ArduPilot's dma_resolver.py."""
    out = []
    for m in _STREAM.finditer(hwdef_h):
        shared = tuple(s.strip() for s in (m.group("shared") or "").split(",") if s.strip())
        out.append(DmaAssignment(m.group("periph"), int(m.group("dma")), int(m.group("stream")),
                                 shared))
    return out


def exclusive(assignments: list[DmaAssignment], prefixes: tuple[str, ...]) -> dict[str, bool]:
    """For peripherals starting with any prefix, whether their stream is used by nothing else.

    A timer's update (UP) and input-capture (CHx) requests may share one stream: that is how
    ArduPilot's bidirectional DShot uses a timer, so they count as one owner.
    """
    owners: dict[tuple[int, int], set[str]] = {}
    for a in assignments:
        owner = a.peripheral.split("_")[0]  # TIM3_UP and TIM3_CH3 both belong to TIM3
        owners.setdefault((a.dma, a.stream), set()).add(owner)
    result = {}
    for a in assignments:
        if a.peripheral.startswith(prefixes):
            result[a.peripheral] = len(owners[(a.dma, a.stream)]) == 1
    return result

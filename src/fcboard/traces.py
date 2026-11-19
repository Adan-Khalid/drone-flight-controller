"""PCB trace width for a current, from IPC-2221 as implemented in KiCad's PCB calculator.

I = k * dT^0.44 * A^0.725, with I in amps, dT in degrees C and A the copper cross-section in
square mils; k = 0.048 for outer layers and 0.024 for inner layers.
"""

from __future__ import annotations

MM_PER_MIL = 0.0254


def max_current(width_mm: float, thickness_mm: float, delta_t_c: float, k: float) -> float:
    """Current a trace can carry for a temperature rise `delta_t_c`."""
    area_mil2 = (width_mm / MM_PER_MIL) * (thickness_mm / MM_PER_MIL)
    return k * delta_t_c**0.44 * area_mil2**0.725


def min_width_mm(current_a: float, thickness_mm: float, delta_t_c: float, k: float) -> float:
    """Narrowest trace for `current_a` at a temperature rise `delta_t_c` (inverse of above)."""
    if current_a <= 0 or thickness_mm <= 0 or delta_t_c <= 0:
        raise ValueError("current, thickness and temperature rise must be positive")
    area_mil2 = (current_a / (k * delta_t_c**0.44)) ** (1.0 / 0.725)
    thickness_mil = thickness_mm / MM_PER_MIL
    return area_mil2 / thickness_mil * MM_PER_MIL

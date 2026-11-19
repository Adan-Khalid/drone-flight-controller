"""First-order RC circuits: low-pass filters and edge times."""

from __future__ import annotations

import math


def cutoff_hz(r_ohm: float, c_farad: float) -> float:
    """-3 dB corner of a first-order RC low-pass: 1 / (2 pi R C)."""
    return 1.0 / (2.0 * math.pi * r_ohm * c_farad)


def attenuation_db(f_hz: float, fc_hz: float) -> float:
    """Gain of a first-order low-pass at f, in dB (negative means attenuation)."""
    return -10.0 * math.log10(1.0 + (f_hz / fc_hz) ** 2)


def rise_time_10_90(r_ohm: float, c_farad: float) -> float:
    """10 % to 90 % rise time of an RC step response: ln(9) R C, about 2.2 R C."""
    return math.log(9.0) * r_ohm * c_farad


def settle_time(r_ohm: float, c_farad: float, fraction_left: float) -> float:
    """Time until the remaining error is `fraction_left` of the step: -ln(fraction) R C."""
    if not 0 < fraction_left < 1:
        raise ValueError("fraction_left must be between 0 and 1")
    return -math.log(fraction_left) * r_ohm * c_farad


def step_value_at(t: float, tau: float, final: float) -> float:
    """Value of a first-order step response from 0 to `final` after time t."""
    return final * (1.0 - math.exp(-t / tau))

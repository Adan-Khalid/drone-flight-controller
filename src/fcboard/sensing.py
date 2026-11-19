"""Battery voltage sensing: resistor divider and RC filter in front of the processor's ADC."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DividerResult:
    ratio: float              # battery volts per ADC-pin volt (ArduPilot BATT_VOLT_MULT)
    v_full_scale: float       # battery voltage that reaches the ADC full scale
    source_impedance: float   # Thevenin resistance seen by the ADC pin, ohms
    lsb_battery_v: float      # battery volts per ADC step
    cutoff_hz: float          # RC filter corner frequency
    tau_s: float              # RC time constant
    charge_share_error: float  # relative error from the sample capacitor, worst case


def divider_ratio(r_top: float, r_bot: float) -> float:
    """VBAT / VPIN for a two-resistor divider."""
    return (r_top + r_bot) / r_bot


def pin_voltage(v_battery: float, r_top: float, r_bot: float) -> float:
    """Voltage at the ADC pin for a battery voltage."""
    return v_battery / divider_ratio(r_top, r_bot)


def design_divider(
    r_top: float, r_bot: float, c_filter: float, adc_full_scale: float, adc_bits: int,
    c_sample: float,
) -> DividerResult:
    """Key figures of a divider with a filter capacitor from the ADC pin to ground."""
    ratio = divider_ratio(r_top, r_bot)
    r_th = r_top * r_bot / (r_top + r_bot)
    tau = r_th * c_filter
    return DividerResult(
        ratio=ratio,
        v_full_scale=adc_full_scale * ratio,
        source_impedance=r_th,
        lsb_battery_v=adc_full_scale / (2**adc_bits) * ratio,
        cutoff_hz=1.0 / (2.0 * math.pi * tau),
        tau_s=tau,
        charge_share_error=c_sample / (c_sample + c_filter),
    )


def min_ratio_for(v_max: float, adc_full_scale: float) -> float:
    """Smallest divider ratio that keeps the pin at or below full scale for `v_max`."""
    return v_max / adc_full_scale

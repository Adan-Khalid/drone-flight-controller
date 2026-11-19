"""Design equations for a synchronous step-down (buck) regulator.

The equations follow the ADI LT8641 datasheet (Rev B, Applications Information, equations 1 to
10). Units: volts, amps, ohms, seconds and hertz unless a name says otherwise.
"""

from __future__ import annotations


def vout_from_divider(vfb: float, r_top: float, r_bot: float) -> float:
    """Output voltage set by a feedback divider: VOUT = VFB * (1 + Rtop / Rbot) (eq. 1)."""
    return vfb * (1.0 + r_top / r_bot)


def vout_extremes(
    vfb_min: float, vfb_max: float, r_top: float, r_bot: float, tol: float
) -> tuple[float, float]:
    """Lowest and highest output voltage from reference spread and resistor tolerance."""
    low = vout_from_divider(vfb_min, r_top * (1 - tol), r_bot * (1 + tol))
    high = vout_from_divider(vfb_max, r_top * (1 + tol), r_bot * (1 - tol))
    return low, high


def rt_for_frequency_k(fsw_mhz: float, k_per_mhz: float = 46.5, offset_k: float = 5.2) -> float:
    """RT resistor in kOhm for a switching frequency in MHz (LT8641 eq. 3)."""
    return k_per_mhz / fsw_mhz - offset_k


def frequency_from_rt_mhz(rt_k: float, k_per_mhz: float = 46.5, offset_k: float = 5.2) -> float:
    """Switching frequency in MHz for an RT resistor in kOhm (eq. 3 rearranged)."""
    return k_per_mhz / (rt_k + offset_k)


def fsw_max(vout: float, vin: float, t_on_min: float, vsw_top: float, vsw_bot: float) -> float:
    """Highest switching frequency before the minimum on-time is violated (eq. 4)."""
    return (vout + vsw_bot) / (t_on_min * (vin - vsw_top + vsw_bot))


def vin_min_full_frequency(
    vout: float, fsw: float, t_off_min: float, vsw_top: float, vsw_bot: float
) -> float:
    """Lowest input voltage without skipped cycles at frequency `fsw` (eq. 5)."""
    return (vout + vsw_bot) / (1.0 - fsw * t_off_min) - vsw_bot + vsw_top


def inductor_first_choice_uh(vout: float, fsw_mhz: float, vsw_bot: float) -> float:
    """Suggested inductance in uH: L = (VOUT + VSW(BOT)) / fSW with fSW in MHz (eq. 6)."""
    return (vout + vsw_bot) / fsw_mhz


def ripple_current(vout: float, vin_max: float, inductance: float, fsw: float) -> float:
    """Peak-to-peak inductor ripple current, worst at the highest input voltage (eq. 9)."""
    return vout / (inductance * fsw) * (1.0 - vout / vin_max)


def peak_inductor_current(i_load: float, ripple: float) -> float:
    """Peak inductor current = load + half the ripple (eq. 7)."""
    return i_load + ripple / 2.0


def max_output_current(i_lim: float, ripple: float) -> float:
    """Output current available before the switch current limit (eq. 8)."""
    return i_lim - ripple / 2.0


def l_min_subharmonic_uh(vin: float, vout: float, fsw_mhz: float) -> float:
    """Minimum inductance in uH to avoid subharmonic oscillation above 50 % duty (eq. 10).

    Returns 0 when the duty cycle is 50 % or less, where the limit does not apply.
    """
    duty = vout / vin
    if duty <= 0.5:
        return 0.0
    return vin * (2.0 * duty - 1.0) / (2.5 * fsw_mhz)


def output_ripple_capacitive(ripple: float, fsw: float, c_out: float) -> float:
    """Peak-to-peak output ripple from the capacitance alone: dV = dI / (8 f C).

    The triangular inductor ripple charges and discharges the output capacitor; ESR and ESL
    of real ceramic capacitors and the layout add to this, so it is a lower bound.
    """
    return ripple / (8.0 * fsw * c_out)


def soft_start_time(c_ss: float, i_ss: float, v_ref: float) -> float:
    """Time for the soft-start capacitor to charge from 0 V to the reference voltage."""
    return c_ss * v_ref / i_ss


def conduction_loss(i_out: float, vout: float, vin: float, rds_top: float, rds_bot: float) -> float:
    """Switch conduction loss I^2 (R_top D + R_bot (1 - D)).

    Switching and inductor losses are not included, so this is a lower bound.
    """
    duty = min(vout / vin, 1.0)
    return i_out**2 * (rds_top * duty + rds_bot * (1.0 - duty))


def diode_conduction_loss(i_out: float, vout: float, vin: float, vf: float) -> float:
    """Catch-diode loss in a non-synchronous buck: VF * I * (1 - D).

    The diode carries the load current while the switch is off. Junction-capacitance and
    recovery losses are not included, so this is a lower bound.
    """
    duty = min(vout / vin, 1.0)
    return vf * i_out * (1.0 - duty)


def temperature_rise(power_w: float, theta_ja: float) -> float:
    """Junction temperature rise above ambient: P * theta_JA."""
    return power_w * theta_ja

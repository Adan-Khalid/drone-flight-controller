"""Linear regulator (LDO) dissipation."""

from __future__ import annotations


def ldo_dissipation(vin: float, vout: float, i_out: float) -> float:
    """Power burnt in a linear regulator: (VIN - VOUT) * IOUT (ground current neglected)."""
    if vin < vout:
        raise ValueError("an LDO cannot output more than its input voltage")
    return (vin - vout) * i_out


def junction_temperature(ambient_c: float, power_w: float, theta_ja: float) -> float:
    """Junction temperature = ambient + P * theta_JA."""
    return ambient_c + power_w * theta_ja

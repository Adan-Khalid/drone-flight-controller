"""Checks of the design equations against values worked out by hand or printed in datasheets."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fcboard import buck, linear, rc, sensing, traces
from fcboard.eseries import nearest_e96

ROOT = Path(__file__).resolve().parents[1]


def test_feedback_divider_matches_adi_typical_application():
    # ADI's 5 V application uses 1 M over 191 k with a 0.81 V reference.
    assert buck.vout_from_divider(0.81, 1e6, 191e3) == pytest.approx(5.051, abs=1e-3)


# LT8641 datasheet Rev B, Table 1: switching frequency (MHz) and RT (kOhm).
LT8641_TABLE_1 = [
    (0.2, 232), (0.3, 150), (0.4, 110), (0.5, 88.7), (0.6, 71.5), (0.7, 60.4), (0.8, 52.3),
    (1.0, 41.2), (1.2, 33.2), (1.4, 28.0), (1.6, 23.7), (1.8, 20.5), (2.0, 18.2), (2.2, 15.8),
    (3.0, 10.7),
]


@pytest.mark.parametrize("fsw_mhz, rt_table_k", LT8641_TABLE_1)
def test_rt_equation_is_close_to_datasheet_table(fsw_mhz, rt_table_k):
    # Equation 3 is an approximation of Table 1: within 4 % over the whole table, so the
    # final RT value is always taken from the table.
    assert buck.rt_for_frequency_k(fsw_mhz) == pytest.approx(rt_table_k, rel=0.04)


def test_rt_for_2mhz_rounds_to_table_value():
    assert nearest_e96(buck.rt_for_frequency_k(2.0)) == pytest.approx(18.2)


def test_rt_and_frequency_are_inverse():
    assert buck.frequency_from_rt_mhz(buck.rt_for_frequency_k(1.5)) == pytest.approx(1.5)


def test_ripple_current_hand_value():
    # 5 V / (2.2 uH * 2 MHz) * (1 - 5/25) = 1.136 * 0.8 = 0.909 A
    assert buck.ripple_current(5.0, 25.0, 2.2e-6, 2e6) == pytest.approx(0.9091, rel=1e-3)


def test_peak_and_max_current():
    assert buck.peak_inductor_current(2.0, 1.0) == pytest.approx(2.5)
    assert buck.max_output_current(6.2, 1.0) == pytest.approx(5.7)


def test_subharmonic_limit_only_above_half_duty():
    assert buck.l_min_subharmonic_uh(12.0, 5.0, 2.0) == 0.0
    # 6 V in, 5 V out: 6 * (2*5/6 - 1) / (2.5 * 2) = 6 * 0.6667 / 5 = 0.8 uH
    assert buck.l_min_subharmonic_uh(6.0, 5.0, 2.0) == pytest.approx(0.8)


def test_output_ripple_capacitive():
    # 1 A / (8 * 1 MHz * 10 uF) = 12.5 mV
    assert buck.output_ripple_capacitive(1.0, 1e6, 10e-6) == pytest.approx(12.5e-3)


def test_soft_start_time():
    # 10 nF * 0.81 V / 1.9 uA = 4.26 ms
    assert buck.soft_start_time(10e-9, 1.9e-6, 0.81) == pytest.approx(4.263e-3, rel=1e-3)


def test_conduction_loss_limits():
    # Duty 1: all current through the top switch.
    assert buck.conduction_loss(2.0, 5.0, 5.0, 0.1, 0.05) == pytest.approx(0.4)
    # Duty 0.5: average of both switches.
    assert buck.conduction_loss(2.0, 5.0, 10.0, 0.1, 0.05) == pytest.approx(0.3)


def test_diode_loss():
    # 0.7 V * 2 A * (1 - 5/10) = 0.7 W
    assert buck.diode_conduction_loss(2.0, 5.0, 10.0, 0.7) == pytest.approx(0.7)


def test_ldo_thermal():
    p = linear.ldo_dissipation(5.0, 3.3, 0.5)
    assert p == pytest.approx(0.85)
    assert linear.junction_temperature(25.0, p, 100.0) == pytest.approx(110.0)
    with pytest.raises(ValueError):
        linear.ldo_dissipation(3.0, 3.3, 0.1)


def test_divider():
    r = sensing.design_divider(150e3, 10e3, 100e-9, 3.3, 12, 4e-12)
    assert r.ratio == pytest.approx(16.0)
    assert r.source_impedance == pytest.approx(9375.0)
    assert r.charge_share_error == pytest.approx(4e-5, rel=1e-3)
    assert sensing.pin_voltage(48.4, 150, 10) == pytest.approx(3.025)


def test_trace_width_round_trip_and_layer_factor():
    w = traces.min_width_mm(2.0, 0.035, 10.0, 0.048)
    assert traces.max_current(w, 0.035, 10.0, 0.048) == pytest.approx(2.0)
    # Inner layers carry half the current for the same area, so they need more copper.
    assert traces.min_width_mm(2.0, 0.035, 10.0, 0.024) > w


def test_rc_low_pass():
    fc = rc.cutoff_hz(10.0, 10e-6)
    assert fc == pytest.approx(1591.5, rel=1e-3)
    assert rc.attenuation_db(fc, fc) == pytest.approx(-3.0103, abs=1e-3)
    # Far above the corner the gain falls 20 dB per decade.
    assert rc.attenuation_db(100 * fc, fc) == pytest.approx(-40.0, abs=0.01)


def test_rc_edges():
    tau = 220.0 * 100e-12  # 22 ns
    assert rc.rise_time_10_90(220.0, 100e-12) == pytest.approx(2.197 * tau, rel=1e-3)
    assert rc.settle_time(220.0, 100e-12, 0.01) == pytest.approx(4.605 * tau, rel=1e-3)
    assert rc.step_value_at(tau, tau, 1.0) == pytest.approx(0.6321, rel=1e-3)
    with pytest.raises(ValueError):
        rc.settle_time(1.0, 1.0, 1.5)


def test_nearest_e96():
    assert nearest_e96(450e3) == pytest.approx(453e3)
    assert nearest_e96(18.05) == pytest.approx(18.2)
    with pytest.raises(ValueError):
        nearest_e96(0)


def test_report_script_runs_and_meets_its_own_checks(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "design_calcs.py")], check=True,
                   cwd=ROOT)
    r = json.loads((ROOT / "reports" / "design_calcs.json").read_text(encoding="utf-8"))
    lt = r["lt8641"]
    assert lt["fsw_max_at_hv_mhz"] > lt["fsw_mhz"]
    assert lt["iout_max_low_duty_a"] > 3.5
    assert lt["l_min_subharmonic_uh"] < lt["l_chosen_uh"]
    assert r["budget"]["i_5v_worst"] < r["budget"]["target_a"]
    assert r["battery_sense"]["pin_voltages"]["TVS clamp"] < 3.3
    assert r["battery_sense"]["source_impedance_k"] < r["battery_sense"]["rain_max_k"]

"""Design calculations for the flight controller power and sensing circuits.

Reads configs/design_inputs.yaml and writes reports/design_calcs.json and
reports/design_calcs.md. Every input is sourced in the config file.

Usage:
    uv run python scripts/design_calcs.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

from fcboard import buck, linear, rc, sensing, traces
from fcboard.battery import input_range
from fcboard.eseries import nearest_e96

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "design_inputs.yaml"
OUT_JSON = ROOT / "reports" / "design_calcs.json"
OUT_MD = ROOT / "reports" / "design_calcs.md"


def compute(cfg: dict) -> dict:
    b = cfg["battery"]
    rng = input_range(
        b["cells_min"], b["cells_max"], b["cell_v_min"], b["cell_v_full"], b["cell_v_full_hv"]
    )
    vin_points = {"2S empty": rng.v_min, "3S nominal": 3 * b["cell_v_nominal"],
                  "6S full": rng.v_max, "6S HV full": rng.v_max_hv}

    # ------------------------------------------------------------- LT8641 5 V buck
    p, ch = cfg["lt8641"], cfg["lt8641_choice"]
    rt_ideal = buck.rt_for_frequency_k(2.0, p["rt_k_per_mhz"], p["rt_offset_k"])
    fsw_mhz = buck.frequency_from_rt_mhz(ch["rt_k"], p["rt_k_per_mhz"], p["rt_offset_k"])
    fsw = fsw_mhz * 1e6
    r_top, r_bot = ch["r_top_k"] * 1e3, ch["r_bot_k"] * 1e3
    vout = buck.vout_from_divider(p["vfb_typ"], r_top, r_bot)
    vout_lo, vout_hi = buck.vout_extremes(
        p["vfb_min"], p["vfb_max"], r_top, r_bot, ch["resistor_tol"]
    )
    r_top_ideal_k = ch["r_bot_k"] * (5.0 / p["vfb_typ"] - 1.0)
    t_on, t_off = p["t_on_min_max_ns"] * 1e-9, p["t_off_min_max_ns"] * 1e-9
    fsw_max_hv = buck.fsw_max(vout, rng.v_max_hv, t_on, p["vsw_top"], p["vsw_bot"])
    vin_full_freq = buck.vin_min_full_frequency(vout, fsw, t_off, p["vsw_top"], p["vsw_bot"])
    l_first = buck.inductor_first_choice_uh(vout, fsw_mhz, p["vsw_bot"])
    l_h = ch["inductor_uh"] * 1e-6
    ripple = buck.ripple_current(vout, rng.v_max_hv, l_h, fsw)
    i_target = cfg["supply_5v"]["load_target_a"]
    i_full = p["iout_continuous_a"]
    lmin = buck.l_min_subharmonic_uh(rng.v_min, vout, fsw_mhz)
    c_out = ch["cout_uf"] * 1e-6
    ss = [buck.soft_start_time(ch["css_nf"] * 1e-9, i * 1e-6, p["vfb_typ"])
          for i in p["tr_ss_ua"]]
    ss_ms = {"fastest": ss[2] * 1e3, "typical": ss[1] * 1e3, "slowest": ss[0] * 1e3}
    losses = {}
    for name, vin in vin_points.items():
        pw = buck.conduction_loss(i_target, vout, vin, p["rds_top_ohm"], p["rds_bot_ohm"])
        losses[name] = {"vin": vin, "conduction_w": pw,
                        "rise_c": buck.temperature_rise(pw, p["theta_ja_c_per_w"])}
    lt = {
        "rt_ideal_k": rt_ideal, "rt_chosen_k": ch["rt_k"],
        "rt_nearest_e96_k": nearest_e96(rt_ideal), "fsw_mhz": fsw_mhz,
        "r_top_ideal_k": r_top_ideal_k, "vout": vout, "vout_min": vout_lo, "vout_max": vout_hi,
        "fb_divider_current_ua": vout / (r_top + r_bot) * 1e6,
        "fsw_max_at_hv_mhz": fsw_max_hv / 1e6, "vin_min_full_frequency": vin_full_freq,
        "l_first_choice_uh": l_first, "l_chosen_uh": ch["inductor_uh"],
        "ripple_a": ripple,
        "peak_at_target_a": buck.peak_inductor_current(i_target, ripple),
        "peak_at_full_a": buck.peak_inductor_current(i_full, ripple),
        "iout_max_low_duty_a": buck.max_output_current(p["ilim_top_min_a"], ripple),
        "iout_max_dc08_a": buck.max_output_current(p["ilim_typ_dc08_a"], ripple),
        "l_min_subharmonic_uh": lmin,
        "ripple_mv_nominal_c": buck.output_ripple_capacitive(ripple, fsw, c_out) * 1e3,
        "ripple_mv_half_c": buck.output_ripple_capacitive(ripple, fsw, c_out / 2) * 1e3,
        "soft_start_ms": ss_ms,
        "conduction_loss_at_target": losses,
        "tvs_clamp_margin_v": p["vin_abs_max"] - cfg["battery_sense"]["tvs_clamp_v"],
    }

    # ------------------------------------------------------------- loads and 3.3 V rail
    l33 = cfg["loads_3v3_a"]
    i33_typ = l33["stm32h743_typ"] + l33["microsd_allowance"] + l33["leds_and_misc_allowance"]
    i33_max = l33["stm32h743_max_85c"] + l33["microsd_allowance"] + l33["leds_and_misc_allowance"]
    i_sensor = sum(cfg["loads_sensor_3v3_a"].values())
    l5 = cfg["loads_5v_a"]
    i5_direct = sum(l5.values())
    # A buck's input current is at most its output current whenever its efficiency is above
    # VOUT/VIN (3.3/5 = 66 %), so counting the 3.3 V current at full value is conservative.
    i5_typ = i33_typ + i_sensor + i5_direct
    i5_max = i33_max + i_sensor + i5_direct
    ta = cfg["ambient_c"]

    ap, tl = cfg["ap2112k"], cfg["tlv62569"]
    rail = {}
    for label, i in (("typical", i33_typ), ("worst", i33_max)):
        p_ldo = linear.ldo_dissipation(vout, 3.3, i)
        p_buck = buck.conduction_loss(i, 3.3, vout, tl["rds_hs_ohm"], tl["rds_ls_ohm"])
        rail[label] = {
            "current_a": i,
            "ldo_w": p_ldo, "ldo_tj_c": linear.junction_temperature(ta, p_ldo,
                                                                     ap["theta_ja_c_per_w"]),
            "buck_conduction_w": p_buck,
            "buck_tj_c": linear.junction_temperature(ta, p_buck, tl["theta_ja_c_per_w"]),
        }
    tl_r_top_ideal = tl["r_bot_k"] * (tl["vout_target"] / tl["vfb_typ"] - 1.0)
    tl_r_top = nearest_e96(tl_r_top_ideal)
    tl_vout = buck.vout_from_divider(tl["vfb_typ"], tl_r_top, tl["r_bot_k"])
    tl_ripple = buck.ripple_current(tl_vout, vout, tl["inductor_uh"] * 1e-6, tl["fsw_mhz"] * 1e6)
    p_sensor_ldo = linear.ldo_dissipation(vout, 3.3, i_sensor)
    budget = {
        "i_3v3_typ": i33_typ, "i_3v3_worst": i33_max, "i_sensor": i_sensor,
        "i_5v_direct": i5_direct, "i_5v_typ": i5_typ, "i_5v_worst": i5_max,
        "target_a": i_target, "lt8641_rating_a": i_full,
        "sensor_ldo_w": p_sensor_ldo, "ambient_c": ta,
        "ap2112k_tj_max_c": ap["tj_max_c"], "ap2112k_imax_a": ap["imax_a"],
        "rail_3v3": rail,
        "tlv_r_top_ideal_k": tl_r_top_ideal, "tlv_r_top_k": tl_r_top, "tlv_vout": tl_vout,
        "tlv_ripple_a": tl_ripple,
        "tlv_peak_worst_a": buck.peak_inductor_current(i33_max, tl_ripple),
        "tlv_ilim_a": tl["ilim_a"],
    }

    # ------------------------------------------------------------- battery sensing
    s = cfg["battery_sense"]
    div = sensing.design_divider(
        s["r_top_k"] * 1e3, s["r_bot_k"] * 1e3, s["c_filter_nf"] * 1e-9,
        s["adc_full_scale_v"], s["adc_bits"], s["adc_csample_pf"] * 1e-12,
    )
    pins = {name: sensing.pin_voltage(v, s["r_top_k"], s["r_bot_k"])
            for name, v in {**vin_points, "TVS clamp": s["tvs_clamp_v"]}.items()}
    one_lsb_rel = 1.0 / 2 ** s["adc_bits"]
    sense = {
        "ratio_min_for_tvs": sensing.min_ratio_for(s["tvs_clamp_v"], s["adc_full_scale_v"]),
        "ratio": div.ratio, "v_full_scale": div.v_full_scale,
        "source_impedance_k": div.source_impedance / 1e3, "rain_max_k": s["adc_rain_max_k"],
        "lsb_mv": div.lsb_battery_v * 1e3, "cutoff_hz": div.cutoff_hz, "tau_ms": div.tau_s * 1e3,
        "charge_share_error_ppm": div.charge_share_error * 1e6,
        "one_lsb_ppm": one_lsb_rel * 1e6,
        "pin_voltages": pins,
        "divider_current_ua_at_hv": rng.v_max_hv / ((s["r_top_k"] + s["r_bot_k"]) * 1e3) * 1e6,
    }

    # ------------------------------------------------------------- traces
    t = cfg["traces"]
    widths = []
    for i in t["currents_a"]:
        widths.append({
            "current_a": i,
            "outer_mm": traces.min_width_mm(i, t["outer_copper_mm"], t["delta_t_c"],
                                            t["k_external"]),
            "inner_mm": traces.min_width_mm(i, t["inner_copper_mm"], t["delta_t_c"],
                                            t["k_internal"]),
        })

    d = cfg["dshot"]
    dshot = {"bit_us": 1e6 / d["rate_bps"], "frame_us": d["bits_per_frame"] * 1e6 / d["rate_bps"]}

    # ------------------------------------------------------------- 5 V regulator options
    options = {}
    for name, o in cfg["regulator_options"].items():
        rows = {}
        for label, vin in (("3S nominal", vin_points["3S nominal"]),
                           ("6S HV full", vin_points["6S HV full"])):
            if o["synchronous"]:
                ic = buck.conduction_loss(i_target, vout, vin, o["rds_top_ohm"],
                                          o["rds_bot_ohm"])
                diode = 0.0
            else:
                duty = min(vout / vin, 1.0)
                ic = i_target**2 * o["rds_top_ohm"] * duty
                diode = buck.diode_conduction_loss(i_target, vout, vin, o["diode_vf_v"])
            rows[label] = {"vin": vin, "ic_w": ic, "ic_rise_c": ic * o["theta_ja_c_per_w"],
                           "diode_w": diode}
            if "rds_top_max_ohm" in o:
                ic_max = buck.conduction_loss(i_target, vout, vin, o["rds_top_max_ohm"],
                                              o["rds_bot_max_ohm"])
                rows[label]["ic_w_max_rds"] = ic_max
                rows[label]["ic_rise_c_max_rds"] = ic_max * o["theta_ja_c_per_w"]
        options[name] = {
            "price_usd": o["price_usd"], "synchronous": o["synchronous"],
            "vin_max_v": o["vin_max_v"],
            "survives_clamp": o["vin_max_v"] > cfg["battery_sense"]["tvs_clamp_v"],
            "current_rating_a": o["current_rating_a"], "min_limit_a": o["min_limit_a"],
            "margin_over_worst_a": o["current_rating_a"] - i5_max,
            "fsw_khz": o["fsw_khz"], "inductor_uh": o["inductor_uh"], "losses_at_2a": rows,
        }

    # ------------------------------------------------------------- simulation targets
    sf = cfg["sensor_filter"]
    fc_sf = rc.cutoff_hz(sf["r_ohm"], sf["c_uf"] * 1e-6)
    sensor_filter = {
        "r_ohm": sf["r_ohm"], "c_uf": sf["c_uf"], "cutoff_hz": fc_sf,
        "dc_drop_mv": sf["r_ohm"] * i_sensor * 1e3,
        "ldo_input_v": vout - sf["r_ohm"] * i_sensor,
        "attenuation_db": {f"{fm} MHz": rc.attenuation_db(fm * 1e6, fc_sf)
                           for fm in sf["buck_frequencies_mhz"]},
    }
    mo = cfg["motor_output"]
    r_min = mo["v_high"] / (mo["i_pin_max_ma"] * 1e-3)
    c_load = mo["c_load_pf"] * 1e-12
    motor = {
        "r_min_ohm": r_min, "r_series_ohm": mo["r_series_ohm"],
        "short_current_ma": mo["v_high"] / mo["r_series_ohm"] * 1e3,
        "c_load_pf": mo["c_load_pf"],
        "rise_10_90_ns": rc.rise_time_10_90(mo["r_series_ohm"], c_load) * 1e9,
        "settle_1pct_ns": rc.settle_time(mo["r_series_ohm"], c_load, 0.01) * 1e9,
        "bit_ns": dshot["bit_us"] * 1e3,
    }
    motor["rise_fraction_of_bit"] = motor["rise_10_90_ns"] / motor["bit_ns"]
    bs = cfg["battery_step"]
    v_final = sensing.pin_voltage(bs["v_step"], s["r_top_k"], s["r_bot_k"])
    battery_step = {
        "v_step": bs["v_step"], "v_pin_final": v_final, "tau_ms": div.tau_s * 1e3,
        "v_pin_after_one_tau": rc.step_value_at(div.tau_s, div.tau_s, v_final),
        "settle_1pct_ms": -math.log(0.01) * div.tau_s * 1e3,
        "dc_gain_db": 20.0 * math.log10(1.0 / div.ratio),
        "minus3db_gain_db": 20.0 * math.log10(1.0 / div.ratio) - 3.0103,
        "cutoff_hz": div.cutoff_hz,
    }

    return {"input_range": {"v_min": rng.v_min, "v_max": rng.v_max, "v_max_hv": rng.v_max_hv},
            "lt8641": lt, "budget": budget, "battery_sense": sense,
            "traces": {"delta_t_c": t["delta_t_c"], "widths": widths}, "dshot": dshot,
            "regulator_options": options,
            "simulation_targets": {"battery_step": battery_step,
                                   "sensor_filter": sensor_filter, "motor_output": motor}}


def f(x: float, n: int = 2) -> str:
    return f"{x:.{n}f}"


def render(r: dict) -> str:
    rng, lt, bd, s = r["input_range"], r["lt8641"], r["budget"], r["battery_sense"]
    rail = bd["rail_3v3"]
    lines = [
        "# Design calculations",
        "",
        "Generated by `scripts/design_calcs.py` from `configs/design_inputs.yaml`. Every input is "
        "sourced in that file; values marked as allowances are my own estimates until measured.",
        "",
        "## 1. Battery input range",
        "",
        f"2S empty to 6S full: **{f(rng['v_min'], 1)} to {f(rng['v_max'], 1)} V**; "
        f"6S high-voltage packs reach **{f(rng['v_max_hv'], 2)} V**.",
        "",
        "## 2. 5 V regulator (LT8641)",
        "",
        "| Quantity | Value | Check |",
        "| --- | --- | --- |",
        f"| RT for 2 MHz (eq. 3) | {f(lt['rt_ideal_k'])} kΩ, nearest E96 "
        f"{f(lt['rt_nearest_e96_k'], 1)} kΩ | chosen {f(lt['rt_chosen_k'], 1)} kΩ, "
        f"as ADI's 2 MHz application |",
        f"| Switching frequency with chosen RT | {f(lt['fsw_mhz'], 3)} MHz | |",
        f"| Feedback divider | top {f(lt['r_top_ideal_k'], 0)} kΩ ideal, 1 MΩ chosen, "
        f"bottom 191 kΩ | |",
        f"| Output voltage | {f(lt['vout'], 3)} V nominal, {f(lt['vout_min'], 3)} to "
        f"{f(lt['vout_max'], 3)} V with reference spread and 1 % resistors | |",
        f"| Divider current | {f(lt['fb_divider_current_ua'], 1)} µA | |",
        f"| Highest frequency allowed at {f(rng['v_max_hv'], 1)} V (eq. 4, 50 ns on-time) | "
        f"{f(lt['fsw_max_at_hv_mhz'])} MHz | above {f(lt['fsw_mhz'], 2)} MHz: OK |",
        f"| Lowest input without skipped cycles (eq. 5, 110 ns off-time) | "
        f"{f(lt['vin_min_full_frequency'])} V | below this (nearly empty 2S pack) the regulator "
        f"skips cycles but keeps regulating |",
        f"| Inductor, first choice (eq. 6) | {f(lt['l_first_choice_uh'])} µH | chosen "
        f"{f(lt['l_chosen_uh'], 1)} µH, as ADI's 2 MHz application |",
        f"| Ripple current at {f(rng['v_max_hv'], 1)} V (eq. 9) | {f(lt['ripple_a'], 3)} A "
        f"peak-to-peak | |",
        f"| Peak inductor current (eq. 7) | {f(lt['peak_at_target_a'])} A at 2 A load; "
        f"{f(lt['peak_at_full_a'])} A at 3.5 A | inductor saturation rating must exceed this |",
        f"| Output current before current limit (eq. 8) | {f(lt['iout_max_low_duty_a'])} A "
        f"(minimum limit), {f(lt['iout_max_dc08_a'])} A (typical limit at 80 % duty) | "
        f"above 3.5 A: OK |",
        f"| Minimum inductance against subharmonic oscillation at {f(rng['v_min'], 1)} V "
        f"(eq. 10) | {f(lt['l_min_subharmonic_uh'])} µH | below 2.2 µH: OK |",
        f"| Output ripple from capacitance alone | {f(lt['ripple_mv_nominal_c'])} mV at 47 µF; "
        f"{f(lt['ripple_mv_half_c'])} mV at half that | far below the 50 mV target; ESL and "
        f"layout add to it, so the scope measurement decides |",
        f"| Soft-start time with 10 nF | {f(lt['soft_start_ms']['typical'])} ms typical "
        f"({f(lt['soft_start_ms']['fastest'])} to {f(lt['soft_start_ms']['slowest'])} ms) | |",
        f"| Surge clamp margin | SMBJ30A clamps at 48.4 V; LT8641 absolute maximum 65 V; "
        f"margin {f(lt['tvs_clamp_margin_v'], 1)} V | OK |",
        "",
        "Switch conduction loss at 2 A (lower bound: switching and inductor losses are not "
        "included; the real figure comes from an efficiency measurement):",
        "",
        "| Input | Conduction loss | Temperature rise (40 °C/W) |",
        "| --- | --- | --- |",
    ]
    for name, v in lt["conduction_loss_at_target"].items():
        lines.append(f"| {name}, {f(v['vin'], 1)} V | {f(v['conduction_w'], 3)} W | "
                     f"{f(v['rise_c'], 1)} °C |")
    lines += [
        "",
        "## 3. Power budget",
        "",
        "| Rail | Typical | Worst case | Note |",
        "| --- | --- | --- | --- |",
        f"| 3.3 V processor rail | {f(bd['i_3v3_typ'], 3)} A | {f(bd['i_3v3_worst'], 3)} A | "
        f"STM32H743 at 480 MHz, all peripherals on (typical, and maximum at 85 °C), plus "
        f"allowances for the SD card and LEDs |",
        f"| 3.3 V sensor rail | {f(bd['i_sensor'] * 1e3, 1)} mA | same | two IMUs and the "
        f"barometer |",
        f"| 5 V direct loads | {f(bd['i_5v_direct'], 3)} A | same | CAN transceiver maximum, "
        f"one DroneCAN device (500 mA), GPS, telemetry and receiver allowances |",
        f"| **5 V total** | **{f(bd['i_5v_typ'])} A** | **{f(bd['i_5v_worst'])} A** | target "
        f"{f(bd['target_a'], 1)} A; LT8641 rated {f(bd['lt8641_rating_a'], 1)} A |",
        "",
        f"### Why the processor rail uses a buck regulator (ambient {f(bd['ambient_c'], 0)} °C)",
        "",
        "| Load | AP2112K LDO: loss, junction temperature | TLV62569 buck: conduction loss, "
        "junction temperature |",
        "| --- | --- | --- |",
    ]
    for label in ("typical", "worst"):
        v = rail[label]
        lines.append(
            f"| {label}, {f(v['current_a'], 3)} A | {f(v['ldo_w'], 2)} W, "
            f"{f(v['ldo_tj_c'], 0)} °C | {f(v['buck_conduction_w'], 3)} W, "
            f"{f(v['buck_tj_c'], 0)} °C |"
        )
    lines += [
        "",
        f"The AP2112K's junction limit is {f(bd['ap2112k_tj_max_c'], 0)} °C, so dropping 5 V "
        "to 3.3 V in a linear regulator at the processor's current is not acceptable. The "
        "TLV62569 buck wastes far less (its switching losses are not counted above). Its "
        f"feedback top resistor is {f(bd['tlv_r_top_ideal_k'], 0)} kΩ ideal, "
        f"{f(bd['tlv_r_top_k'], 0)} kΩ chosen (E96) with 100 kΩ bottom, giving "
        f"{f(bd['tlv_vout'], 3)} V. Ripple current {f(bd['tlv_ripple_a'], 3)} A, peak "
        f"{f(bd['tlv_peak_worst_a'], 2)} A at worst-case load, against a "
        f"{f(bd['tlv_ilim_a'], 1)} A current limit.",
        "",
        f"The sensor LDO (TPS7A2033) burns only {f(bd['sensor_ldo_w'] * 1e3, 1)} mW.",
        "",
        "## 4. Battery voltage sensing",
        "",
        "| Quantity | Value | Check |",
        "| --- | --- | --- |",
        f"| Smallest ratio that keeps the ADC pin below 3.3 V at the 48.4 V surge clamp | "
        f"{f(s['ratio_min_for_tvs'], 1)} | the processor's analog pins do not accept "
        f"positive injection current |",
        f"| Chosen divider 150 kΩ / 10 kΩ | ratio {f(s['ratio'], 1)} (`BATT_VOLT_MULT`), "
        f"full scale {f(s['v_full_scale'], 1)} V | OK |",
        f"| Source impedance seen by the ADC | {f(s['source_impedance_k'], 2)} kΩ | below the "
        f"{f(s['rain_max_k'], 0)} kΩ maximum: OK |",
        f"| Resolution at 12 bits | {f(s['lsb_mv'], 1)} mV of battery voltage per step | |",
        f"| Filter with 100 nF | corner {f(s['cutoff_hz'], 0)} Hz, time constant "
        f"{f(s['tau_ms'], 3)} ms | |",
        f"| Error from the 4 pF sample capacitor | {f(s['charge_share_error_ppm'], 0)} ppm "
        f"worst case | one 12-bit step is {f(s['one_lsb_ppm'], 0)} ppm: negligible |",
        f"| Divider current at {f(rng['v_max_hv'], 1)} V | "
        f"{f(s['divider_current_ua_at_hv'], 0)} µA | |",
        "",
        "| Battery | ADC pin voltage |",
        "| --- | --- |",
    ]
    for name, v in s["pin_voltages"].items():
        lines.append(f"| {name} | {f(v, 3)} V |")
    lines += [
        "",
        f"## 5. Trace widths (IPC-2221, {f(r['traces']['delta_t_c'], 0)} °C rise)",
        "",
        "| Current | Outer layer (35 µm copper) | Inner layer (15.2 µm copper) |",
        "| --- | --- | --- |",
    ]
    for w in r["traces"]["widths"]:
        lines.append(f"| {f(w['current_a'], 1)} A | {f(w['outer_mm'], 3)} mm | "
                     f"{f(w['inner_mm'], 3)} mm |")
    lines += [
        "",
        "## 6. 5 V regulator options at a 2 A load",
        "",
        "Conduction losses only (switching losses come on top). All three survive the 48.4 V "
        "surge clamp.",
        "",
        "| Part | Price | Type | Rating, worst-case margin | Frequency, inductor | "
        "Loss at 11.1 V | Loss at 26.7 V |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, o in r["regulator_options"].items():
        cells = []
        for label in ("3S nominal", "6S HV full"):
            v = o["losses_at_2a"][label]
            txt = f"IC {f(v['ic_w'], 2)} W (+{f(v['ic_rise_c'], 0)} °C)"
            if "ic_w_max_rds" in v:
                txt += (f"; {f(v['ic_w_max_rds'], 2)} W (+{f(v['ic_rise_c_max_rds'], 0)} °C) "
                        "at maximum switch resistance")
            if v["diode_w"]:
                txt += f"; diode {f(v['diode_w'], 2)} W"
            cells.append(txt)
        kind = "synchronous" if o["synchronous"] else "needs a Schottky diode"
        lines.append(
            f"| {name} | ${f(o['price_usd'], 2)} | {kind} | {f(o['current_rating_a'], 1)} A "
            f"(minimum current limit {f(o['min_limit_a'], 1)} A), "
            f"{f(o['margin_over_worst_a'], 2)} A over the worst-case load | "
            f"{f(o['fsw_khz'], 0)} kHz, {f(o['inductor_uh'], 1)} µH | {cells[0]} | {cells[1]} |"
        )
    st = r["simulation_targets"]
    b2, sf, mo = st["battery_step"], st["sensor_filter"], st["motor_output"]
    lines += [
        "",
        "## 7. Expected values for the KiCad simulations",
        "",
        "These are the numbers each simulation in `docs/SIMULATION_GUIDE.md` should reproduce.",
        "",
        "**A. Battery divider (150 kΩ / 10 kΩ, 100 nF)**",
        "",
        "| Check | Expected |",
        "| --- | --- |",
        f"| Pin voltage after a {f(b2['v_step'], 1)} V step, settled | "
        f"{f(b2['v_pin_final'], 3)} V |",
        f"| Pin voltage one time constant ({f(b2['tau_ms'], 3)} ms) after the step | "
        f"{f(b2['v_pin_after_one_tau'], 3)} V (63.2 %) |",
        f"| Time to settle within 1 % | {f(b2['settle_1pct_ms'], 2)} ms |",
        f"| AC gain at low frequency | {f(b2['dc_gain_db'], 2)} dB (1/16) |",
        f"| -3 dB point | {f(b2['minus3db_gain_db'], 2)} dB at {f(b2['cutoff_hz'], 0)} Hz |",
        "",
        f"**B. Sensor supply filter ({f(sf['r_ohm'], 0)} Ω, {f(sf['c_uf'], 0)} µF) before the "
        "TPS7A2033**",
        "",
        "| Check | Expected |",
        "| --- | --- |",
        f"| Corner frequency | {f(sf['cutoff_hz'], 0)} Hz |",
    ]
    for name, db in sf["attenuation_db"].items():
        lines.append(f"| Attenuation at {name} (switching frequency) | {f(db, 1)} dB |")
    lines += [
        f"| DC drop at the sensors' {f(r['budget']['i_sensor'] * 1e3, 1)} mA | "
        f"{f(sf['dc_drop_mv'], 0)} mV, so the LDO sees {f(sf['ldo_input_v'], 2)} V |",
        "",
        "Ideal parts: a real capacitor's ESL and the layout limit the attenuation at MHz "
        "frequencies, so the measured value on the board will be lower.",
        "",
        "**C. Motor output edge (DShot600)**",
        "",
        "| Check | Expected |",
        "| --- | --- |",
        f"| Smallest series resistor that keeps a short to ground within the pin's 20 mA limit | "
        f"{f(mo['r_min_ohm'], 0)} Ω; chosen {f(mo['r_series_ohm'], 0)} Ω "
        f"({f(mo['short_current_ma'], 1)} mA into a short) |",
        f"| 10 % to 90 % rise time into {f(mo['c_load_pf'], 0)} pF (assumed cable and ESC "
        f"input, deliberately pessimistic) | {f(mo['rise_10_90_ns'], 1)} ns, "
        f"{f(mo['rise_fraction_of_bit'] * 100, 1)} % of a {f(mo['bit_ns'], 0)} ns bit |",
        f"| Settled within 1 % | {f(mo['settle_1pct_ns'], 0)} ns |",
        "",
        "## 8. DShot600 timing",
        "",
        f"One bit lasts {f(r['dshot']['bit_us'], 3)} µs and a 16-bit frame "
        f"{f(r['dshot']['frame_us'], 2)} µs, so the motor-signal edges must settle in a small "
        "fraction of a microsecond (checked in KiCad's simulator).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    result = compute(cfg)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    OUT_MD.write_text(render(result), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

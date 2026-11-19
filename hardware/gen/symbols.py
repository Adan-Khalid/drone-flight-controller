"""Write the project symbol library (parts KiCad's library does not have).

Pin numbers and names come from the datasheets (see docs/RESEARCH_LOG.md):
- ICM-45686: TDK DS-000489 Rev 1.1, pin table section 4
- DPS368: Infineon datasheet v1.1, section 2.1
- LT8641: ADI datasheet Rev B, pin functions (UDC 18-lead; pins 5 and 12 absent; pads 21, 22 = SW)
- BMI088: KiCad's Sensor_Motion:BMI088 with SDO1 and SDO2 set to tri-state. Bosch's SPI
  connection diagram (BST-BMI088-DS000-19, section 7.2, figure 8) joins both on one MISO line,
  so each releases the line while its chip select is high; the stock "output" type would raise a
  false output-to-output ERC error.

Usage (from hardware/gen):
    uv run python symbols.py
"""

from __future__ import annotations

import math
from pathlib import Path

from kicad_lib import symbol_def
from sexp import Sym, dump, find, find_all, fmt, q

OUT = Path(__file__).resolve().parents[1] / "kicad" / "lib" / "dronefc.kicad_sym"
FONT = "(effects (font (size 1.27 1.27)))"
FONT_HIDE = "(hide yes) (effects (font (size 1.27 1.27)))"


def prop(name, value, x, y, hide=False, rot=0, justify=""):
    font = FONT_HIDE if hide else FONT
    if justify:
        font = font[:-1] + f" (justify {justify}))"
    return (f'    (property {q(name)} {q(value)} (at {fmt(x)} {fmt(y)} {fmt(rot)}) {font})')


def pin(etype, num, name, x, y, angle, hidden=False, length=2.54):
    h = " (hide yes)" if hidden else ""
    return (f'      (pin {etype} line (at {fmt(x)} {fmt(y)} {fmt(angle)}) (length {fmt(length)}){h} '
            f'(name {q(name)} {FONT}) (number {q(num)} {FONT}))')


def symbol(name, ref, value, footprint, datasheet, descr, w, h, pins):
    """Rectangle body w x h (mm, centred); pins are (etype, number, name, side, slot, hidden).

    side: L, R, T, B; slot: position along the side in 2.54 mm steps from the top or left.
    """
    # leave room inside the body for the vertical names of top and bottom pins, so they do not
    # run into the names of the side pins
    def margin(side):
        names = [p[2] for p in pins if p[3] == side and not p[5]]
        return 2.54 * math.ceil((0.9 * 1.27 * max(map(len, names)) + 1.5) / 2.54) if names else 0.0

    top_m, bot_m = margin("T"), margin("B")
    side_slots = max([p[4] for p in pins if p[3] in "LR"], default=0) + 2
    h = max(h, top_m + bot_m + 2.54 * side_slots)
    h = 2.54 * math.ceil(h / 2.54)
    hw, hh = w / 2, h / 2
    lines = [
        f'  (symbol {q(name)} (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)',
        # outside the body corners, clear of the top and bottom pins
        prop("Reference", ref, -hw, hh + 1.27, justify="right bottom"),
        prop("Value", value, hw, -hh - 1.27, justify="left top"),
        prop("Footprint", footprint, 0, -hh - 3.81, hide=True),
        prop("Datasheet", datasheet, 0, -hh - 6.35, hide=True),
        prop("Description", descr, 0, -hh - 8.89, hide=True),
        f'    (symbol {q(name + "_0_1")}',
        f'      (rectangle (start {fmt(-hw)} {fmt(hh)}) (end {fmt(hw)} {fmt(-hh)}) '
        '(stroke (width 0.254) (type default)) (fill (type background)))',
        '    )',
        f'    (symbol {q(name + "_1_1")}',
    ]
    for etype, num, pname, side, slot, hidden in pins:
        if side == "L":
            x, y, a = -hw - 2.54, hh - top_m - 2.54 * (slot + 1), 0
        elif side == "R":
            x, y, a = hw + 2.54, hh - top_m - 2.54 * (slot + 1), 180
        elif side == "T":
            x, y, a = -hw + 2.54 * (slot + 1), hh + 2.54, 270
        else:
            x, y, a = -hw + 2.54 * (slot + 1), -hh - 2.54, 90
        lines.append(pin(etype, num, pname, x, y, a, hidden))
    lines += ["    )", "  )"]
    return "\n".join(lines)


def derived(lib_id, name, etypes, descr):
    """Copy a KiCad library symbol under a new name, changing the electrical type of some pins."""
    node = symbol_def(lib_id)
    node[1] = name
    for unit in find_all(node, "symbol"):
        for p in find_all(unit, "pin"):
            num = str(find(p, "number")[1])
            if num in etypes:
                p[1] = Sym(etypes[num])
    for pr in find_all(node, "property"):
        if pr[1] == "Description":
            pr[2] = descr
    return "  " + dump(node, 1)


def main():
    syms = [
        symbol("ICM-45686", "U", "ICM-45686", "dronefc:TDK_LGA-14_3x2.5mm_P0.5mm_ICM-45686",
               "https://invensense.tdk.com/products/motion-tracking/6-axis/icm-45686/",
               "6-axis IMU, SPI/I2C/I3C, LGA-14 2.5x3 mm", 22.86, 17.78, [
                   ("input", "12", "AP_CS", "L", 0, False),
                   ("input", "13", "AP_SCLK", "L", 1, False),
                   ("input", "14", "AP_SDI", "L", 2, False),
                   ("output", "1", "AP_SDO", "L", 3, False),
                   ("output", "4", "INT1", "R", 0, False),
                   ("bidirectional", "9", "INT2/FSYNC", "R", 1, False),
                   ("passive", "2", "RESV", "R", 2, False),
                   ("passive", "3", "RESV", "R", 3, False),
                   ("passive", "7", "RESV", "R", 4, False),
                   ("passive", "10", "RESV", "R", 5, False),
                   ("passive", "11", "RESV", "R", 6, False),
                   ("power_in", "8", "VDD", "T", 1, False),
                   ("power_in", "5", "VDDIO", "T", 3, False),
                   ("power_in", "6", "GND", "B", 2, False),
               ]),
        symbol("DPS368", "U", "DPS368", "dronefc:Infineon_PG-VLGA-8_2x2.5mm_P0.65mm_DPS368",
               "https://www.infineon.com/cms/en/product/sensor/pressure-sensors/pressure-sensors-for-iot/dps368/",
               "Barometric pressure sensor, I2C/SPI, VLGA-8 2x2.5 mm", 12.7, 12.7, [
                   ("input", "2", "CSB", "L", 0, False),
                   ("bidirectional", "3", "SDI", "L", 1, False),
                   ("input", "4", "SCK", "L", 2, False),
                   # SDO doubles as the I2C address bit, so it is tied to a rail on this board
                   ("passive", "5", "SDO", "L", 3, False),
                   ("power_in", "8", "VDD", "T", 1, False),
                   ("power_in", "6", "VDDIO", "T", 3, False),
                   ("power_in", "1", "GND", "B", 1, False),
                   ("power_in", "7", "GND", "B", 3, False),
               ]),
        symbol("LT8641", "U", "LT8641", "dronefc:ADI_UDC-18_3x4mm_P0.5mm_LT8641",
               "https://www.analog.com/en/products/lt8641.html",
               "65 V 3.5 A synchronous step-down regulator, UDC 3x4 mm", 17.78, 22.86, [
                   ("power_in", "4", "VIN1", "L", 0, False),
                   ("power_in", "13", "VIN2", "L", 1, False),
                   ("input", "14", "EN/UV", "L", 3, False),
                   ("passive", "15", "RT", "L", 5, False),
                   ("passive", "16", "TR/SS", "L", 6, False),
                   ("input", "17", "SYNC/MODE", "L", 7, False),
                   ("passive", "3", "BST", "R", 0, False),
                   ("power_out", "8", "SW", "R", 1, False),
                   ("passive", "9", "SW", "R", 1, True),
                   ("passive", "21", "SW", "R", 1, True),
                   ("passive", "22", "SW", "R", 1, True),
                   ("power_in", "1", "BIAS", "R", 3, False),
                   ("input", "20", "FB", "R", 4, False),
                   ("open_collector", "19", "PG", "R", 6, False),
                   ("power_out", "2", "INTVCC", "R", 7, False),
                   ("power_in", "18", "GND", "B", 2, False),
                   ("passive", "6", "GND", "B", 2, True),
                   ("passive", "7", "GND", "B", 2, True),
                   ("passive", "10", "GND", "B", 2, True),
                   ("passive", "11", "GND", "B", 2, True),
               ]),
    ]
    syms.append(derived("Sensor_Motion:BMI088", "BMI088", {"10": "tri_state", "15": "tri_state"},
                        "6-axis IMU (separate accel and gyro dies), SPI/I2C, LGA-16; SDO pins "
                        "tri-state when their chip select is high"))
    text = ('(kicad_symbol_lib\n  (version 20251024)\n  (generator "kicad_symbol_editor")\n'
            '  (generator_version "10.0")\n' + "\n".join(syms) + "\n)\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()

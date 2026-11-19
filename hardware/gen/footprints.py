"""Write the project footprints that KiCad's library lacks or gets wrong for this board.

Pad geometry sources (checked 2026-11-16, see docs/RESEARCH_LOG.md):
- LT8641 UDC20(18) 3x4 mm: ADI datasheet Rev B, page 24, recommended solder pad layout
  (drawing 05-08-1116 Rev C); identical in relative pad positions to JLCPCB's footprint for C462660.
- ICM-45686 LGA-14 2.5x3 mm: JLCPCB footprint for C22459454, checked against TDK DS-000489
  Rev 1.1 page 52 (lead 0.25 x 0.475 mm, pitch 0.5 mm); pads extend 0.1 mm past each lead end.
- DPS368 PG-VLGA-8 2.0x2.5 mm: Infineon datasheet v1.1 figure 18 (0.35 mm pads, columns at
  +/-0.725 mm, rows at +/-0.325 and +/-0.975 mm); pin order from figure 17, matching JLCPCB C3232508.
- CSD18543Q3A VSON-8 3.3x3.3 mm: KiCad's VSON-8_3.3x3.3mm_P0.65mm_NexFET with the gate pad (4)
  trimmed from 0.50 to 0.47 mm, its inner edge moved 0.03 mm away from source pad 3: the library
  leaves 0.14 mm between them, under JLCPCB's 0.15 mm for SMD pads on different nets.

Usage (from the repo root):
    uv run python hardware/gen/footprints.py
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from sexp import fmt, q

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "hardware" / "kicad" / "lib"
PRETTY = LIB / "dronefc.pretty"
SHAPES = LIB / "dronefc.3dshapes"
EASYEDA = ROOT / ".cache" / "easyeda" / "jlc.3dshapes"


def uid() -> str:
    return str(uuid.uuid4())


def pad(num, x, y, w, h, shape="roundrect"):
    rr = "(roundrect_rratio 0.25)" if shape == "roundrect" else ""
    return (f'  (pad {q(num)} smd {shape} (at {fmt(x)} {fmt(y)}) (size {fmt(w)} {fmt(h)}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") {rr} (uuid {q(uid())}))')


def rect(layer, x0, y0, x1, y1, width):
    return (f'  (fp_rect (start {fmt(x0)} {fmt(y0)}) (end {fmt(x1)} {fmt(y1)}) '
            f'(stroke (width {fmt(width)}) (type solid)) (fill none) (layer {q(layer)}) (uuid {q(uid())}))')


def line(layer, x0, y0, x1, y1, width=0.12):
    return (f'  (fp_line (start {fmt(x0)} {fmt(y0)}) (end {fmt(x1)} {fmt(y1)}) '
            f'(stroke (width {fmt(width)}) (type solid)) (layer {q(layer)}) (uuid {q(uid())}))')


def circle(layer, x, y, r, width=0.12, fill="solid"):
    return (f'  (fp_circle (center {fmt(x)} {fmt(y)}) (end {fmt(x + r)} {fmt(y)}) '
            f'(stroke (width {fmt(width)}) (type solid)) (fill {fill}) (layer {q(layer)}) (uuid {q(uid())}))')


def footprint(name, descr, body_w, body_h, pads, model, model_rot=0.0, pin1=(0.0, 0.0)):
    """A complete SMD footprint with fab outline, courtyard, silkscreen corners and a pin-1 dot."""
    xs = [p[1] - p[3] / 2 for p in pads] + [p[1] + p[3] / 2 for p in pads]
    ys = [p[2] - p[4] / 2 for p in pads] + [p[2] + p[4] / 2 for p in pads]
    cx0, cx1 = min(min(xs), -body_w / 2) - 0.25, max(max(xs), body_w / 2) + 0.25
    cy0, cy1 = min(min(ys), -body_h / 2) - 0.25, max(max(ys), body_h / 2) + 0.25
    bw, bh = body_w / 2, body_h / 2
    s = 0.11  # silkscreen sits just outside the body
    silk = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            silk.append(line("F.SilkS", sx * (bw + s), sy * (bh + s), sx * (bw + s - 0.3), sy * (bh + s)))
            silk.append(line("F.SilkS", sx * (bw + s), sy * (bh + s), sx * (bw + s), sy * (bh + s - 0.3)))
    parts = [
        f'(footprint {q("dronefc:" + name)}',
        '  (version 20241229)',
        '  (generator "pcbnew")',
        '  (generator_version "10.0")',
        '  (layer "F.Cu")',
        f'  (descr {q(descr)})',
        '  (attr smd)',
        f'  (property "Reference" "REF**" (at 0 {fmt(cy0 - 0.8)} 0) (layer "F.SilkS") (uuid {q(uid())}) '
        '(effects (font (size 0.8 0.8) (thickness 0.12))))',
        f'  (property "Value" {q(name)} (at 0 {fmt(cy1 + 0.8)} 0) (layer "F.Fab") (uuid {q(uid())}) '
        '(effects (font (size 0.8 0.8) (thickness 0.12))))',
        rect("F.Fab", -bw, -bh, bw, bh, 0.1),
        rect("F.CrtYd", cx0, cy0, cx1, cy1, 0.05),
        *silk,
        circle("F.SilkS", pin1[0], pin1[1], 0.1),
        *[pad(*p) for p in pads],
        f'  (model {q("${KIPRJMOD}/lib/dronefc.3dshapes/" + model)} (offset (xyz 0 0 0)) '
        f'(scale (xyz 1 1 1)) (rotate (xyz 0 0 {fmt(model_rot)})))',
        ")",
    ]
    (PRETTY / f"{name}.kicad_mod").write_text("\n".join(parts) + "\n", encoding="utf-8")


def lt8641():
    pads = []
    side_y = {1: -1.25, 2: -0.75, 3: -0.25, 4: 0.25, 6: 1.25}
    for n, y in side_y.items():
        pads.append((str(n), -1.40, y, 0.70, 0.25))
    for n, y in {11: 1.25, 13: 0.25, 14: -0.25, 15: -0.75, 16: -1.25}.items():
        pads.append((str(n), 1.40, y, 0.70, 0.25))
    for n, x in {7: -0.75, 8: -0.25, 9: 0.25, 10: 0.75}.items():
        pads.append((str(n), x, 1.90, 0.25, 0.70))
    for n, x in {17: 0.75, 18: 0.25, 19: -0.25, 20: -0.75}.items():
        pads.append((str(n), x, -1.90, 0.25, 0.70))
    pads.append(("21", 0.0, 1.08, 0.22, 0.40, "rect"))
    pads.append(("22", 0.0, 0.31, 0.22, 0.40, "rect"))
    footprint("ADI_UDC-18_3x4mm_P0.5mm_LT8641",
              "ADI UDC20(18) 3x4 mm QFN, drawing 05-08-1116 Rev C, LT8641 recommended pad layout",
              3.0, 4.0, pads, "LT8641_UDC-18.step", 0.0, pin1=(-1.95, -1.85))


def icm45686():
    pads = []
    for n, y in {1: -0.75, 2: -0.25, 3: 0.25, 4: 0.75}.items():
        pads.append((str(n), -1.26, y, 0.675, 0.28))
    for n, x in {5: -0.5, 6: 0.0, 7: 0.5}.items():
        pads.append((str(n), x, 1.01, 0.28, 0.675))
    for n, y in {8: 0.75, 9: 0.25, 10: -0.25, 11: -0.75}.items():
        pads.append((str(n), 1.26, y, 0.675, 0.28))
    for n, x in {12: 0.5, 13: 0.0, 14: -0.5}.items():
        pads.append((str(n), x, -1.01, 0.28, 0.675))
    footprint("TDK_LGA-14_3x2.5mm_P0.5mm_ICM-45686",
              "TDK InvenSense LGA-14 2.5x3x0.81 mm (ICM-45686, DS-000489 Rev 1.1)",
              3.0, 2.5, pads, "ICM-45686_LGA-14.step", 0.0, pin1=(-1.85, -1.25))


def dps368():
    pads = []
    for n, y in {1: -0.975, 2: -0.325, 3: 0.325, 4: 0.975}.items():
        pads.append((str(n), 0.725, y, 0.35, 0.35))
    for n, y in {5: 0.975, 6: 0.325, 7: -0.325, 8: -0.975}.items():
        pads.append((str(n), -0.725, y, 0.35, 0.35))
    footprint("Infineon_PG-VLGA-8_2x2.5mm_P0.65mm_DPS368",
              "Infineon PG-VLGA-8 2.0x2.5 mm (DPS368 datasheet v1.1 figure 18), vent hole on top",
              2.0, 2.5, pads, "DPS368_VLGA-8.step", 90.0, pin1=(1.25, -1.45))


def nexfet():
    win = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0/share/kicad/footprints"
    lib = Path(os.environ.get("KICAD10_FOOTPRINT_DIR",
                              win if win.exists() else "/usr/share/kicad/footprints"))
    src = (lib / "Package_SON.pretty" / "VSON-8_3.3x3.3mm_P0.65mm_NexFET.kicad_mod").read_text(
        encoding="utf-8")
    name = "TI_VSON-8_3.3x3.3mm_P0.65mm_NexFET_GatePad0.47mm"
    old_pad = '(pad "4" smd roundrect\n\t\t(at -1.44 0.97)\n\t\t(size 0.63 0.5)'
    new_pad = '(pad "4" smd roundrect\n\t\t(at -1.44 0.985)\n\t\t(size 0.63 0.47)'
    if old_pad not in src:
        raise SystemExit("KiCad's NexFET footprint changed; check pad 4 by hand")
    out = src.replace(old_pad, new_pad).replace(
        '(footprint "VSON-8_3.3x3.3mm_P0.65mm_NexFET"', f'(footprint {q(name)}', 1)
    (PRETTY / f"{name}.kicad_mod").write_text(out, encoding="utf-8")


def copy_models():
    SHAPES.mkdir(parents=True, exist_ok=True)
    mapping = {
        "QFN-20_L4.0-W3.0-H0.8-P0.50-TL_LT8641EUDC.step": "LT8641_UDC-18.step",
        "LGA-14_L2.5-W3.0-H0.9-P0.50.step": "ICM-45686_LGA-14.step",
        "LGA-8_L2.5-W2.0-P0.65-TR_DPS368.step": "DPS368_VLGA-8.step",
    }
    for src, dst in mapping.items():
        if (EASYEDA / src).exists():
            shutil.copyfile(EASYEDA / src, SHAPES / dst)


def main():
    PRETTY.mkdir(parents=True, exist_ok=True)
    lt8641()
    icm45686()
    dps368()
    nexfet()
    copy_models()
    print("footprints written to", PRETTY.relative_to(ROOT))


if __name__ == "__main__":
    main()

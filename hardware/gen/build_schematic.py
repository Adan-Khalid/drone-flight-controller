"""Generate the KiCad schematic (root sheet plus one sub-sheet per section) from circuit.py.

Style: every connected pin gets a short wire stub ending in a net label (global label when the
net spans sheets), a power symbol for GND/+5V/+3V3, or a no-connect flag. Parts are grouped into
titled blocks by function (GROUPS below) and the blocks are packed onto each sheet.

Usage (from hardware/gen):
    uv run python build_schematic.py
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from pathlib import Path

import circuit
from kicad_lib import pins, symbol_def
from sexp import Sym, dump, find, find_all, fmt, q

OUT = Path(__file__).resolve().parents[1] / "kicad"
PROJECT = "dronefc"
STUB = 2.54
GRID = 2.54
PAPER = ("A3", 420.0, 297.0)
MARGIN = 20.32
CONTENT_BOTTOM = 297.0 - 50.0      # keep clear of the title block
GROUP_MAX_W = 140.0
GAP = 7.62
PAD = 5.08
TITLE_H = 6.35
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "dronefc/root"))

GROUPS = {
    "power": [
        ("Battery and ESC connector, reverse-battery protection",
         ["J1", "Q1", "U1", "C1", "D1", "C2", "C3", "C4"]),
        ("5 V regulator, 7 V to 26 V in (LT8641)",
         ["U2", "R1", "C5", "C6", "C7", "L1", "R2", "R3", "C8", "C9"]),
        ("5 V source select: regulator or USB (TPS2116)", ["U3", "R4", "R5", "C10", "C11"]),
        ("3.3 V regulator (TLV62569)", ["U4", "C12", "L2", "R6", "R7", "C13", "C14", "C15"]),
        ("Filtered 3.3 V for the sensors (TPS7A2033)", ["R8", "C16", "U5", "C17", "C18"]),
        ("Battery voltage and current sensing", ["R9", "R10", "C19", "R11", "C20"]),
        ("Power flags (tell ERC these nets are driven)", [f"#FLG{i:02d}" for i in range(1, 8)]),
    ],
    "mcu": [
        ("Processor (STM32H743)", ["U7"]),
        ("Supply decoupling and core regulator capacitors",
         [f"C{i}" for i in range(21, 31)]),
        ("Reset and boot", ["C31", "R12", "TP3", "TP4"]),
        ("8 MHz crystal", ["Y1", "C32", "C33"]),
        ("Status LEDs", ["R13", "D2", "R14", "D3"]),
        ("Debug pads (SWD)", ["TP1", "TP2", "TP5", "TP6"]),
    ],
    "sensors": [
        ("IMU 1 (ICM-45686, SPI1)", ["U8", "C34", "C35"]),
        ("IMU 2 (BMI088, SPI4)", ["U9", "C36", "C37"]),
        ("Barometer (DPS368, I2C2)", ["U10", "C38", "C39", "R15", "R16"]),
        ("microSD card (SDMMC1, 4-bit)",
         ["J2", "R17", "R18", "R19", "R20", "R21", "C40", "C41"]),
    ],
    "io": [
        ("USB-C with ESD protection", ["J3", "R22", "R23", "U6"]),
        ("Telemetry and GPS ports (JST GH, Pixhawk pinout)", ["J5", "J6", "R25", "R26"]),
        ("Receiver and TELEM2 pads", [f"TP{i}" for i in range(18, 24)]),
        ("Motor outputs 1 to 4 (series resistors on the DShot lines)",
         [f"R{i}" for i in range(27, 31)]),
        ("Spare pads", ["TP11", "TP12", "TP13", "TP14", "R35", "TP15"]),
    ],
}


def uid(*key) -> str:
    """Stable UUIDs, so regenerating does not churn the files."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "dronefc/" + "/".join(map(str, key))))


def snap(v: float) -> float:
    return round(v / GRID) * GRID


def text_w(s: str, size: float = 1.27) -> float:
    return 0.85 * size * len(s)


# ----------------------------------------------------------------------------- resolve parts
def resolve(part):
    """Return (connections by pin number, set of NC pin numbers) with every visible pin covered."""
    ps = pins(part.lib)
    conn = dict(part.conn)
    if part.ref == "U7":
        by_name = {p.name: p.number for p in ps}
        for name, net in circuit.PINMAP.items():
            conn[by_name[name]] = net
    nc = set(part.nc)
    if part.ref == "U7":  # every processor port pin not in the pin plan is left unconnected
        for p in ps:
            if p.number not in conn and re.fullmatch(r"P[A-K]\d+(_C)?", p.name):
                nc.add(p.number)
    numbers = {p.number for p in ps}
    for n in list(conn) + list(nc):
        if n not in numbers:
            raise SystemExit(f"{part.ref}: pin {n} does not exist on {part.lib}")
    pos = defaultdict(list)
    for p in ps:
        pos[(p.x, p.y)].append(p)
    for p in ps:
        if p.number in conn or p.number in nc:
            continue
        stacked = [o for o in pos[(p.x, p.y)] if o.number in conn and o is not p]
        if p.hidden and (stacked or p.etype == "no_connect"):
            continue
        if part.lib.startswith("power:"):
            continue
        raise SystemExit(f"{part.ref} ({part.lib}): pin {p.number} {p.name} is neither connected nor NC")
    return conn, nc


# ----------------------------------------------------------------------------- geometry
def out_dir(angle: float) -> tuple[int, int]:
    """Unit vector in schematic coordinates (y down) pointing away from the body."""
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(angle) % 360]


def label_angle(d) -> int:
    return {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]


def power_rotation(net: str, d) -> int:
    if net == "GND":   # body below the pin at 0 degrees
        return {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]
    return {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]  # supply arrow above the pin


def rotate(dx: float, dy: float, rot: int) -> tuple[float, float]:
    """Rotate a schematic offset (y down) counter-clockwise on screen by rot degrees."""
    t = math.radians(rot)
    c, s = round(math.cos(t)), round(math.sin(t))
    return dx * c + dy * s, -dx * s + dy * c


# horizontal text to the right of small vertical two-pin parts (the library draws some vertically)
TWO_PIN = {"Device:R_Small", "Device:C_Small", "Device:L"}
TWO_PIN_FIELDS = {"Reference": (2.032, -0.635), "Value": (2.032, 1.905)}


def lib_field(lib_id: str, name: str):
    """(x, y, angle, effects node) of a library field, schematic offsets (y down)."""
    if lib_id in TWO_PIN and name in TWO_PIN_FIELDS:
        x, y = TWO_PIN_FIELDS[name]
        return x, y, 0.0, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]],
                           [Sym("justify"), Sym("left")]]
    for pr in find_all(symbol_def(lib_id), "property"):
        if pr[1] == name:
            at = find(pr, "at")
            eff = find(pr, "effects")
            return float(at[1]), -float(at[2]), float(at[3]) if len(at) > 3 else 0.0, eff
    return 0.0, 0.0, 0.0, None


def field_box(x, y, angle, eff, text):
    """Rough box of a field's text for layout spacing."""
    w = text_w(text)
    just = []
    if eff is not None:
        j = find(eff, "justify")
        just = [str(v) for v in j[1:]] if j else []
    if int(angle) % 180 == 90:
        return x - 1, y - w, x + 1, y + w
    x0 = x if "left" in just else x - w if "right" in just else x - w / 2
    return x0, y - 1.3, x0 + w, y + 1.3


def extents(part, conn, power_nets):
    """Box around pins, labels and fields in schematic offsets from the symbol origin."""
    xs, ys = [], []
    for p in pins(part.lib):
        sx, sy = p.x, -p.y
        xs.append(sx)
        ys.append(sy)
        if p.number in conn and not p.hidden:
            dx, dy = out_dir(p.angle)
            net = conn[p.number]
            ln = STUB + (5.08 if net in power_nets else text_w(net) + 2.5)
            xs.append(sx + dx * ln)
            ys.append(sy + dy * ln)
    for name, text in (("Reference", part.ref), ("Value", part.value)):
        if part.ref.startswith("#"):
            continue
        fx, fy, fa, eff = lib_field(part.lib, name)
        bx0, by0, bx1, by1 = field_box(fx, fy, fa, eff, text)
        xs += [bx0, bx1]
        ys += [by0, by1]
    return min(xs) - 1.27, min(ys) - 1.27, max(xs) + 1.27, max(ys) + 1.27


# ----------------------------------------------------------------------------- writers
def prop(name, value, x, y, angle=0, hide=False, effects=None):
    h = " (hide yes)" if hide else ""
    eff = dump(effects) if effects is not None else "(effects (font (size 1.27 1.27)))"
    eff = eff.replace(" (hide yes)", "")
    return f'(property {q(name)} {q(value)} (at {fmt(x)} {fmt(y)} {fmt(angle)}){h} {eff})'


def symbol_instance(ref, lib_id, value, fp, x, y, rot, sheet_uuid, pin_numbers, extra=None,
                    in_bom=True, on_board=True, dnp=False, show_value=True):
    fields = []
    for name, text, hide in (("Reference", ref, ref.startswith("#")),
                             ("Value", value, not show_value)):
        fx, fy, fa, eff = lib_field(lib_id, name)
        dx, dy = rotate(fx, fy, rot)
        fields.append(prop(name, text, x + dx, y + dy, 0 if rot else fa, hide, eff))
    lines = [
        f'(symbol (lib_id {q(lib_id)}) (at {fmt(x)} {fmt(y)} {rot}) (unit 1) '
        f'(exclude_from_sim no) (in_bom {"yes" if in_bom else "no"}) '
        f'(on_board {"yes" if on_board else "no"}) (dnp {"yes" if dnp else "no"}) '
        f'(uuid {q(uid("sym", ref))})',
        *fields,
        prop("Footprint", fp, x, y, hide=True),
        prop("Datasheet", "", x, y, hide=True),
    ]
    for k, v in (extra or {}).items():
        lines.append(prop(k, v, x, y, hide=True))
    for n in pin_numbers:
        lines.append(f'(pin {q(n)} (uuid {q(uid("pin", ref, n))}))')
    lines.append(f'(instances (project {q(PROJECT)} (path {q("/" + ROOT_UUID + "/" + sheet_uuid)} '
                 f'(reference {q(ref)}) (unit 1))))')
    lines.append(")")
    return "\n  ".join(lines)


def wire(x0, y0, x1, y1, key):
    return (f'(wire (pts (xy {fmt(x0)} {fmt(y0)}) (xy {fmt(x1)} {fmt(y1)})) '
            f'(stroke (width 0) (type default)) (uuid {q(uid("wire", *key))}))')


def label(net, x, y, angle, glob, key):
    just = "right" if angle in (180, 270) else "left"
    if glob:
        return (f'(global_label {q(net)} (shape passive) (at {fmt(x)} {fmt(y)} {angle}) '
                f'(fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just})) '
                f'(uuid {q(uid("glabel", *key))}))')
    return (f'(label {q(net)} (at {fmt(x)} {fmt(y)} {angle}) (effects (font (size 1.27 1.27)) '
            f'(justify {just} bottom)) (uuid {q(uid("label", *key))}))')


def no_connect(x, y, key):
    return f'(no_connect (at {fmt(x)} {fmt(y)}) (uuid {q(uid("nc", *key))}))'


def frame(x0, y0, x1, y1, title, key):
    return (f'(rectangle (start {fmt(x0)} {fmt(y0)}) (end {fmt(x1)} {fmt(y1)}) '
            f'(stroke (width 0.1524) (type dash) (color 72 72 72 1)) (fill (type none)) '
            f'(uuid {q(uid("frame", *key))}))\n  '
            f'(text {q(title)} (exclude_from_sim no) (at {fmt(x0 + 1.27)} {fmt(y0 + 4.445)} 0) '
            f'(effects (font (size 2.032 2.032) (thickness 0.254) (bold yes)) (justify left bottom)) '
            f'(uuid {q(uid("ftext", *key))}))')


# ----------------------------------------------------------------------------- layout
def pack(boxes, max_w, gap):
    """Shelf packing. boxes: list of (w, h). Returns positions (x, y) and total (w, h)."""
    pos, x, y, row_h, total_w = [], 0.0, 0.0, 0.0, 0.0
    for w, h in boxes:
        if x > 0 and x + w > max_w:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        pos.append((x, y))
        x += w + gap
        row_h = max(row_h, h)
        total_w = max(total_w, x - gap)
    return pos, (total_w, y + row_h)


def build():
    by_ref = {p.ref: p for p in circuit.PARTS}
    resolved = {}
    net_sheets = defaultdict(set)
    for p in circuit.PARTS:
        conn, nc = resolve(p)
        resolved[p.ref] = (conn, nc)
        for net in conn.values():
            net_sheets[net].add(p.sheet)
    grouped = [r for groups in GROUPS.values() for _, refs in groups for r in refs]
    missing = set(by_ref) - set(grouped)
    dup = {r for r in grouped if grouped.count(r) > 1}
    unknown = set(grouped) - set(by_ref)
    if missing or dup or unknown:
        raise SystemExit(f"GROUPS: missing {sorted(missing)}, duplicated {sorted(dup)}, "
                         f"unknown {sorted(unknown)}")
    power_nets = set(circuit.POWER_SYMBOLS)
    pwr = [0]

    sheet_files = {}
    for sheet_key, title in circuit.SHEETS:
        sheet_uuid = uid("sheet", sheet_key)
        items, lib_ids = [], set()

        # lay out parts inside each group, then the groups on the sheet
        group_layouts = []
        for gtitle, refs in GROUPS[sheet_key]:
            ext = [extents(by_ref[r], resolved[r][0], power_nets) for r in refs]
            boxes = [(e[2] - e[0], e[3] - e[1]) for e in ext]
            pos, (gw, gh) = pack(boxes, GROUP_MAX_W, 2.54)
            gw = max(gw, text_w(gtitle, 2.032) + 2.54)
            group_layouts.append((gtitle, refs, ext, pos, gw + 2 * PAD, gh + 2 * PAD + TITLE_H))
        gpos, (_, total_h) = pack([(g[4], g[5]) for g in group_layouts],
                                  PAPER[1] - 2 * MARGIN, GAP)
        for g, (gx, gy) in zip(group_layouts, gpos, strict=True):
            if MARGIN + gx + g[4] > PAPER[1] - 140 and MARGIN + gy + g[5] > CONTENT_BOTTOM:
                print(f"warning: block '{g[0]}' on sheet {sheet_key} overlaps the title block")
            if MARGIN + gy + g[5] > PAPER[2] - 15:
                print(f"warning: block '{g[0]}' on sheet {sheet_key} runs off the page")

        for (gtitle, refs, ext, pos, gw, gh), (gx, gy) in zip(group_layouts, gpos, strict=True):
            x0, y0 = MARGIN + gx, MARGIN + gy
            items.append(frame(x0, y0, x0 + gw, y0 + gh, gtitle, (sheet_key, gtitle)))
            for ref, e, (px, py) in zip(refs, ext, pos, strict=True):
                part = by_ref[ref]
                conn, nc = resolved[ref]
                ox = snap(x0 + PAD + px - e[0])
                oy = snap(y0 + PAD + TITLE_H + py - e[1])
                items += place_part(part, conn, nc, ox, oy, sheet_uuid, net_sheets, power_nets,
                                    lib_ids, pwr)

        lib_symbols = "\n    ".join(dump(symbol_def(lid), 2) for lid in sorted(lib_ids))
        body = "\n  ".join(items)
        text = (f'(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")\n'
                f'  (uuid {q(sheet_uuid)})\n  (paper {q(PAPER[0])})\n'
                f'  (title_block (title {q(title)}) (date "2026-11-16") (rev "1") '
                f'(company "Drone flight controller"))\n'
                f'  (lib_symbols\n    {lib_symbols}\n  )\n  {body}\n)\n')
        fname = f"{sheet_key}.kicad_sch"
        (OUT / fname).write_text(text, encoding="utf-8")
        sheet_files[sheet_key] = (fname, title, sheet_uuid)

    write_root(sheet_files)
    write_tables()
    print("schematic written:", ", ".join(f for f, _, _ in sheet_files.values()))


def place_part(part, conn, nc, ox, oy, sheet_uuid, net_sheets, power_nets, lib_ids, pwr):
    items = []
    lib_ids.add(part.lib)
    ps = pins(part.lib)
    extra = {}
    if part.lcsc:
        extra["LCSC"] = part.lcsc
    if part.mpn:
        extra["MPN"] = part.mpn
    is_flag = part.lib.startswith("power:")
    copper_only = part.ref.startswith(("TP", "JP"))   # pads and jumpers: nothing to buy
    items.append(symbol_instance(part.ref, part.lib, part.value, part.fp, ox, oy, 0, sheet_uuid,
                                 [p.number for p in ps], extra, in_bom=not (is_flag or copper_only),
                                 on_board=not is_flag, dnp=part.dnp, show_value=not is_flag))
    power_runs = defaultdict(list)
    for p in ps:
        px, py = ox + p.x, oy - p.y
        if p.number in nc:
            items.append(no_connect(px, py, (part.ref, p.number)))
            continue
        if p.number not in conn or p.hidden:
            continue
        net = conn[p.number]
        d = out_dir(p.angle)
        ex, ey = px + d[0] * STUB, py + d[1] * STUB
        items.append(wire(px, py, ex, ey, (part.ref, p.number)))
        if net in power_nets:
            # stub ends on the same side share a line: (net, side, coordinate across the side)
            power_runs[(net, d, round(ex if d[0] else ey, 3))].append((ex, ey, p.number))
        else:
            glob = len(net_sheets[net]) > 1
            items.append(label(net, ex, ey, label_angle(d), glob, (part.ref, p.number)))
    for (net, d, _), ends in power_runs.items():
        ends.sort(key=lambda e: (e[1], e[0]) if d[0] else (e[0], e[1]))
        # join neighbours 2.54 mm apart with a wire; a gap starts a new run with its own symbol
        runs = [[ends[0]]]
        for a, b in zip(ends, ends[1:], strict=False):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 2.54 + 1e-6:
                items.append(wire(a[0], a[1], b[0], b[1], (part.ref, "pwr", a[2], b[2])))
                runs[-1].append(b)
            else:
                runs.append([b])
        for run in runs:
            for e in run[1:-1]:
                items.append(f'(junction (at {fmt(e[0])} {fmt(e[1])}) (diameter 0) '
                             f'(color 0 0 0 0) (uuid {q(uid("junction", part.ref, e[2]))}))')
            ex, ey, num = run[0]
            if len(run) > 1:
                items.append(f'(junction (at {fmt(ex)} {fmt(ey)}) (diameter 0) '
                             f'(color 0 0 0 0) (uuid {q(uid("junction", part.ref, num))}))')
            pwr[0] += 1
            lid = circuit.POWER_SYMBOLS[net]
            lib_ids.add(lid)
            items.append(symbol_instance(f"#PWR{pwr[0]:03d}", lid, net, "", ex, ey,
                                         power_rotation(net, d), sheet_uuid, ["1"],
                                         in_bom=False, on_board=False))
    return items


def write_root(sheet_files):
    blocks = []
    for i, (fname, title, s_uuid) in enumerate(sheet_files.values()):
        x, y = 30.48 + (i % 2) * 101.6, 40.64 + (i // 2) * 60.96
        blocks.append(
            f'(sheet (at {fmt(x)} {fmt(y)}) (size 76.2 38.1) (exclude_from_sim no) (in_bom yes) '
            f'(on_board yes) (dnp no) (fields_autoplaced yes) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0.0000)) (uuid {q(s_uuid)})\n'
            f'    (property "Sheetname" {q(title)} (at {fmt(x)} {fmt(y - 0.7)} 0) '
            f'(effects (font (size 1.27 1.27)) (justify left bottom)))\n'
            f'    (property "Sheetfile" {q(fname)} (at {fmt(x)} {fmt(y + 38.7)} 0) '
            f'(effects (font (size 1.27 1.27)) (justify left top)))\n'
            f'    (instances (project {q(PROJECT)} (path {q("/" + ROOT_UUID)} (page {q(str(i + 2))}))))\n'
            f'  )')
    root = (f'(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")\n'
            f'  (uuid {q(ROOT_UUID)})\n  (paper "A4")\n'
            f'  (title_block (title "Drone flight controller") (date "2026-11-16") (rev "1") '
            f'(company "STM32H743, ArduPilot"))\n  (lib_symbols)\n  ' + "\n  ".join(blocks) +
            '\n  (sheet_instances (path "/" (page "1")))\n)\n')
    (OUT / f"{PROJECT}.kicad_sch").write_text(root, encoding="utf-8")


def write_tables():
    (OUT / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n  (lib (name "dronefc")(type "KiCad")'
        '(uri "${KIPRJMOD}/lib/dronefc.kicad_sym")(options "")(descr "Project symbols"))\n)\n',
        encoding="utf-8")
    (OUT / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n  (lib (name "dronefc")(type "KiCad")'
        '(uri "${KIPRJMOD}/lib/dronefc.pretty")(options "")(descr "Project footprints"))\n)\n',
        encoding="utf-8")
    pro = OUT / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text('{\n  "meta": {\n    "filename": "dronefc.kicad_pro",\n    "version": 3\n  }\n}\n',
                       encoding="utf-8")


if __name__ == "__main__":
    build()

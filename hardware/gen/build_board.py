"""Build the board: rules, stack-up, outline, mounting holes and every part placed on both sides.

Big parts (processor, connectors, regulators, sensors, microSD) are placed by hand in ANCHORS.
Every other part is placed by a greedy search: the free spot nearest to the pins it connects to
(or to the pin named in TARGETS, for decoupling capacitors), with courtyards not overlapping,
inside the outline, clear of the mounting hardware and of through-hole pegs on the other side.

Run with KiCad's Python (it has pcbnew), from the repo root:
    "%LOCALAPPDATA%/Programs/KiCad/10.0/bin/python.exe" hardware/gen/build_board.py
Writes hardware/kicad/dronefc.kicad_pcb, dronefc.kicad_pro and reports/hardware/placement.md.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pcbnew  # noqa: E402
from board_common import KICAD_DIR, PCB, ROOT, load_footprint, netlist, short  # noqa: E402

CX = CY = 100.0          # board centre on the drawing sheet, mm
HALF = 18.0              # 36 x 36 mm
CORNER_R = 2.0
HOLE_XY = 15.25          # 30.5 mm mounting pattern
HOLE_KEEP = 3.5          # the M3 hole footprint's own courtyard is 3.45 mm in radius
EDGE_KEEP = 0.25         # courtyard to board edge
GAP = 0.1                # extra space between courtyards
MM = pcbnew.FromMM

# nets that reach most of the board: they say nothing about where a part belongs
GLOBAL = {"GND", "+3V3", "+5V", "+3V3_S", "VBAT", "VBUS"}

# side, x, y, rotation; or side, edge (N/S/E/W) the connector opens towards, position along it
ANCHORS = {
    "U7": ("F", 1.5, 0.5, 0),   # 1.5 mm east of centre: more room for the power corner
    "J6": ("F", "N", -5.75),
    "J3": ("F", "N", 6.4),
    "J1": ("F", "S", -4.0),
    "J5": ("F", "E", 2.0),
    "U2": ("F", -13.2, -1.2, 0),
    "L1": ("F", -13.2, 4.5, 0),
    "C9": ("F", -13.2, 8.9, 0),
    "U3": ("F", -12.4, -8.6, 0),
    "J2": ("B", "E", -1.6),
    "U8": ("B", -2.6, -1.4, 0),
    "U9": ("B", -2.6, 4.2, 0),
    "U10": ("B", -8.6, 4.4, 0),
    "U5": ("B", -8.6, -0.6, 0),
    "U4": ("B", -10.6, 11.0, 0),
    "D2": ("F", 6.5, 16.1, 0),
    "D3": ("F", 10.0, 16.1, 0),
}
# wire pads on the bottom: a row along the south edge and a column along the west edge
SOUTH_PADS = ["TP13", "TP14", "TP15", "TP11", "TP12"]
WEST_PADS = ["TP18", "TP19", "TP20", "TP21", "TP22", "TP23"]
PAD_PITCH = 2.3
for i, ref in enumerate(SOUTH_PADS):
    ANCHORS[ref] = ("B", (i - (len(SOUTH_PADS) - 1) / 2) * PAD_PITCH, 16.4, 0)
for i, ref in enumerate(WEST_PADS):
    ANCHORS[ref] = ("B", -16.4, (i - (len(WEST_PADS) - 1) / 2) * PAD_PITCH, 0)

# escape band around fine-pitch parts (mm), kept free of other parts on the same side
ESCAPE_BAND = {"U7": 1.2, "U2": 0.5}

# parts whose nets are all global: place next to this pad
TARGETS = {
    "C2": ("U2", "4"), "C3": ("U2", "4"), "C4": ("U2", "13"), "D1": ("Q1", "5"),
    "C10": ("U3", "6"), "C11": ("U3", "2"), "C12": ("U4", "1"), "C14": ("L2", "2"),
    "C15": ("L2", "2"), "C18": ("U5", "5"),
    "C21": ("U7", "11"), "C22": ("U7", "27"), "C23": ("U7", "50"), "C24": ("U7", "75"),
    "C25": ("U7", "100"), "C26": ("U7", "6"), "C27": ("U7", "21"), "C28": ("U7", "20"),
    "C34": ("U8", "8"), "C35": ("U8", "5"), "C36": ("U9", "3"), "C37": ("U9", "11"),
    "C38": ("U10", "8"), "C39": ("U10", "6"), "C40": ("J2", "4"), "C41": ("J2", "4"),
    "TP5": ("U7", "94"), "TP6": ("U7", "72"),
}
# parts that must sit on one side (LEDs are seen from the top)
# (C27 and C28 go underneath so the analog ground pin beside them keeps room for its via)
SIDE = {"D2": "F", "D3": "F", "R13": "F", "R14": "F", "C27": "B", "C28": "B"}
# placement order for the greedy search: closest-coupled parts first
FIRST = ["C21", "C22", "C23", "C24", "C25", "C27", "C28", "C29", "C30", "C26", "Y1", "C32", "C33",
         "C3", "C4", "C2", "R1", "C5", "C6", "C7", "R2", "R3", "C8", "Q1", "U1", "C1", "D1",
         "C10", "C11", "R4", "R5", "C12", "L2", "R6", "R7", "C13", "C14", "C15",
         "C34", "C35", "C36", "C37", "C38", "C39", "C16", "C17", "C18", "R8"]


# ----------------------------------------------------------------------------- project file
NETCLASSES = [
    # name, track, clearance, via diameter, via drill, nets
    # 0.1 mm track and space, 0.45 / 0.2 mm vias: inside JLCPCB's limits (0.09 mm track and space,
    # 0.1 mm pad to track, 0.15 mm via hole, 0.2 mm via hole to track) and at no extra cost (holes of
    # 0.2 mm cost more only with vias under 0.45 mm). The via ring (0.125 mm) plus 0.1 mm clearance
    # keeps every via hole 0.225 mm from other copper.
    ("Default", 0.1, 0.1, 0.45, 0.2, []),
    # battery-side power, all inside the regulator corner; local pours add the copper (D9)
    ("Power", 0.3, 0.127, 0.6, 0.3, ["VBAT_IN", "VBAT", "SW5", "+5V_REG"]),
    # supplies spread over the whole board; +5V also has the inner-layer pour
    ("Supply", 0.2, 0.1, 0.45, 0.2, ["+3V3", "+3V3_S", "+5V_F", "SW3", "+5V", "VBUS"]),
    # ground reaches the inner plane through a via at each pad; the router skips this class
    ("Ground", 0.3, 0.1, 0.45, 0.2, ["GND"]),
]


def write_project():
    classes = []
    for i, (name, track, clr, vdia, vdrill, _) in enumerate(NETCLASSES):
        classes.append({
            "name": name, "track_width": track, "clearance": clr, "via_diameter": vdia,
            "via_drill": vdrill, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "bus_width": 12, "wire_width": 6, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "priority": 2147483647 if name == "Default" else i,
            "tuning_profile": "",
        })
    patterns = [{"netclass": name, "pattern": f"*{net}"} for name, *_, nets in NETCLASSES
                for net in nets]
    pro = {
        "board": {
            "design_settings": {
                "meta": {"version": 2},
                # JLCPCB 4-layer limits (docs/RESEARCH_LOG.md, [J1]): 0.09 mm trace and space,
                # 0.15 mm via hole, 0.25 mm via diameter; edge clearance is my own margin
                # PTH to track (0.28 mm) and SMD pad to pad (0.15 mm) are custom rules in
                # dronefc.kicad_dru; via hole to track and hole-to-hole are 0.2 mm, copper to a
                # routed edge 0.2 mm (0.25 here)
                "rules": {
                    "max_error": 0.005, "min_clearance": 0.09, "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.25, "min_groove_width": 0.0,
                    "min_hole_clearance": 0.2, "min_hole_to_hole": 0.2,
                    "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2, "min_silk_clearance": 0.0,
                    "min_text_height": 0.8, "min_text_thickness": 0.08,
                    "min_through_hole_diameter": 0.15, "min_track_width": 0.09,
                    "min_via_annular_width": 0.05, "min_via_diameter": 0.25,
                    "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True,
                },
                "track_widths": [0.0, 0.1, 0.25, 0.4, 0.8],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                   {"diameter": 0.45, "drill": 0.2}],
                "drc_exclusions": [],
            }
        },
        "net_settings": {"classes": classes, "meta": {"version": 5},
                         "netclass_patterns": patterns, "netclass_assignments": None,
                         "net_colors": None},
        "meta": {"filename": "dronefc.kicad_pro", "version": 3},
    }
    path = KICAD_DIR / "dronefc.kicad_pro"
    if path.exists():   # keep anything KiCad itself added (schematic settings, sheets)
        old = json.loads(path.read_text(encoding="utf-8"))
        old.update({k: v for k, v in pro.items() if k != "board"})
        old.setdefault("board", {}).setdefault("design_settings", {}).update(
            pro["board"]["design_settings"])
        pro = old
    path.write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")
    (KICAD_DIR / "dronefc.kicad_dru").write_text(DRU, encoding="utf-8")


# custom rules for JLCPCB limits that KiCad's board setup has no single field for
DRU = """(version 1)
(rule "JLCPCB: plated through-hole to track 0.28 mm"
  (constraint hole_clearance (min 0.28mm))
  (condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole'"))
(rule "JLCPCB: SMD pads on different nets 0.15 mm apart"
  (constraint clearance (min 0.15mm))
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Pad_Type == 'SMD' && B.Pad_Type == 'SMD' && A.Net != B.Net"))
"""


# JLCPCB JLC04161H-7628 (docs/RESEARCH_LOG.md, [J10]): 35 um outer copper, 0.2104 mm 7628
# prepreg, 15.2 um inner copper, 1.065 mm core
STACKUP = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628"))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4"))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628"))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
"""


def add_stackup(path: Path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\t\t\(stackup\n.*?\n\t\t\)\n", "", text, flags=re.S)
    text = text.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------------------- geometry
class Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def shift(self, dx, dy):
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def hits(self, o, gap=GAP):
        return not (self.x1 + gap <= o.x0 or o.x1 + gap <= self.x0 or
                    self.y1 + gap <= o.y0 or o.y1 + gap <= self.y0)

    def inside_board(self):
        lim = HALF - EDGE_KEEP
        return self.x0 >= -lim and self.x1 <= lim and self.y0 >= -lim and self.y1 <= lim

    def near_hole(self):
        for hx in (-HOLE_XY, HOLE_XY):
            for hy in (-HOLE_XY, HOLE_XY):
                nx = min(max(hx, self.x0), self.x1)
                ny = min(max(hy, self.y0), self.y1)
                if math.hypot(nx - hx, ny - hy) < HOLE_KEEP:
                    return True
        return False

    @property
    def centre(self):
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2


def to_mm(v):
    return pcbnew.ToMM(v.x) - CX, pcbnew.ToMM(v.y) - CY


def courtyard(fp, side):
    layer = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    cy = fp.GetCourtyard(layer)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    x0, y0 = to_mm(bb.GetOrigin())
    return Rect(x0, y0, x0 + pcbnew.ToMM(bb.GetWidth()), y0 + pcbnew.ToMM(bb.GetHeight()))


def put(fp, side, x, y, rot):
    """Place a footprint: side F or B, centre position in board mm, rotation in degrees."""
    if (side == "B") != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(MM(CX + x), MM(CY + y)))


def opening_vector(fp):
    """Direction a connector opens towards: from its signal pads to its mounting/shield pads."""
    sig, mnt = [], []
    for pd in fp.Pads():
        (mnt if pd.GetNumber() in ("MP", "SH") or not pd.GetNumber() else sig).append(
            to_mm(pd.GetPosition()))
    sx = sum(p[0] for p in sig) / len(sig)
    sy = sum(p[1] for p in sig) / len(sig)
    mx = sum(p[0] for p in mnt) / len(mnt)
    my = sum(p[1] for p in mnt) / len(mnt)
    return mx - sx, my - sy


EDGE_DIR = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OVERHANG = {"J3": 0.5, "J2": 0.2}   # USB-C and microSD fronts stand slightly past the edge


def put_on_edge(fp, ref, side, edge, along):
    dx, dy = EDGE_DIR[edge]
    best = None
    for rot in (0, 90, 180, 270):
        put(fp, side, 0, 0, rot)
        vx, vy = opening_vector(fp)
        score = (vx * dx + vy * dy) / max(math.hypot(vx, vy), 1e-9)
        if best is None or score > best[0]:
            best = (score, rot)
    put(fp, side, 0, 0, best[1])
    r = courtyard(fp, side)
    over = OVERHANG.get(ref, 0.0)
    if edge in "NS":
        y = (-HALF - over - r.y0) if edge == "N" else (HALF + over - r.y1)
        put(fp, side, along, y, best[1])
    else:
        x = (-HALF - over - r.x0) if edge == "W" else (HALF + over - r.x1)
        put(fp, side, x, along, best[1])


# ----------------------------------------------------------------------------- build
def build():
    write_project()
    parts, pin_net = netlist()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    board.SetLayerName(pcbnew.In1_Cu, "In1.Cu")
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_MIXED)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))

    nets = {}
    for name in sorted(set(pin_net.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    fps = {}
    for ref, p in parts.items():
        if not p["footprint"]:
            continue
        fp = load_footprint(pcbnew, p["footprint"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH(p["path"]))
        fp.SetSheetname(p["sheet"].strip("/"))
        for key in ("LCSC", "MPN"):
            if p["fields"].get(key):
                fp.SetField(key, p["fields"][key])
                fp.GetField(key).SetVisible(False)
        for pad in fp.Pads():
            net = pin_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
        board.Add(fp)
        fps[ref] = fp

    occupied = {"F": [], "B": []}
    placed = {}

    def block(fp, side):
        occupied[side].append(courtyard(fp, side))
        other = "B" if side == "F" else "F"
        for pd in fp.Pads():   # through-hole pegs block the other side too
            if pd.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = pd.GetBoundingBox()
                x0, y0 = to_mm(bb.GetOrigin())
                occupied[other].append(Rect(x0 - 0.3, y0 - 0.3, x0 + pcbnew.ToMM(bb.GetWidth()) + 0.3,
                                            y0 + pcbnew.ToMM(bb.GetHeight()) + 0.3))

    for ref, spec in ANCHORS.items():
        fp = fps[ref]
        if isinstance(spec[1], str):
            put_on_edge(fp, ref, spec[0], spec[1], spec[2])
        else:
            put(fp, *spec)
        r = courtyard(fp, spec[0])
        clash = [o for o in occupied[spec[0]] if r.hits(o, 0.0)]
        on_edge = isinstance(spec[1], str)
        lim = HALF + OVERHANG.get(ref, 0.0) + 1e-3 if on_edge else HALF - EDGE_KEEP
        outside = min(r.x0, r.y0) < -lim or max(r.x1, r.y1) > lim
        if clash or outside or r.near_hole():
            print(f"warning: anchor {ref}: overlaps {len(clash)}, outside {outside}, "
                  f"near hole {r.near_hole()}, courtyard x {r.x0:.2f}..{r.x1:.2f} "
                  f"y {r.y0:.2f}..{r.y1:.2f}")
        block(fp, spec[0])
        placed[ref] = spec[0]

    # label strips beside the wire-pad rows on the bottom, kept free for the silkscreen names
    x_south = max(abs(ANCHORS[r][1]) for r in SOUTH_PADS) + 1.1
    occupied["B"].append(Rect(-x_south, 14.35, x_south, 15.3))
    y_west = max(abs(ANCHORS[r][2]) for r in WEST_PADS) + 1.1
    occupied["B"].append(Rect(-15.3, -y_west, -13.3, y_west))

    # mounting holes, outside the schematic
    for i, (hx, hy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), start=1):
        h = load_footprint(pcbnew, "MountingHole:MountingHole_3.2mm_M3")
        h.SetReference(f"H{i}")
        h.SetValue("M3")
        h.SetBoardOnly(True)
        h.SetExcludedFromBOM(True)
        h.SetExcludedFromPosFiles(True)
        h.Reference().SetLayer(pcbnew.F_Fab)
        h.Value().SetVisible(False)
        put(h, "F", hx * HOLE_XY, hy * HOLE_XY, 0)
        board.Add(h)

    # greedy placement of everything else
    order = FIRST + sorted(r for r in fps if r not in FIRST and r not in placed)
    rel = {}

    def rel_rect(ref, side, rot):
        key = (ref, side, rot)
        if key not in rel:
            put(fps[ref], side, 0, 0, rot)
            rel[key] = courtyard(fps[ref], side)
        return rel[key]

    def target_of(ref):
        if ref in TARGETS:
            a, pad = TARGETS[ref]
            for pd in fps[a].Pads():
                if pd.GetNumber() == pad:
                    return [to_mm(pd.GetPosition())], placed[a]
            raise SystemExit(f"{ref}: target pad {a}.{pad} not found")
        pts, sides = [], []
        for pd in fps[ref].Pads():
            net = pd.GetNetname()
            if not net or short(net) in GLOBAL or net.startswith("unconnected"):
                continue
            for other, ofp in fps.items():
                if other == ref or other not in placed:
                    continue
                for opd in ofp.Pads():
                    if opd.GetNetname() == net:
                        pts.append(to_mm(opd.GetPosition()))
                        sides.append(placed[other])
        if not pts:
            return None, None
        # majority side; a tie goes to the side of the first partner found (deterministic,
        # unlike iterating a set, whose order changes between runs)
        return pts, max(("F", "B"), key=lambda s: (sides.count(s), s == sides[0]))

    # escape bands: small parts stay this far from a fine-pitch part's courtyard on its side,
    # so its pins have room for a short trace and a via before the next part
    rings = {"F": [], "B": []}
    for ref, width in ESCAPE_BAND.items():
        c = courtyard(fps[ref], placed[ref])
        rings[placed[ref]].append(Rect(c.x0 - width, c.y0 - width, c.x1 + width, c.y1 + width))

    report = []
    pending = list(order)
    for _ in range(3):   # parts whose partners are not placed yet wait for the next pass
        later = []
        for ref in pending:
            pts, side_pref = target_of(ref)
            if pts is None:
                later.append(ref)
                continue
            tx = sum(p[0] for p in pts) / len(pts)
            ty = sum(p[1] for p in pts) / len(pts)
            sides = [SIDE[ref]] if ref in SIDE else [side_pref, "B" if side_pref == "F" else "F"]
            best = None
            for side in sides:
                penalty = 0.0 if side == sides[0] else 2.5
                for rot in (0, 90):
                    r0 = rel_rect(ref, side, rot)
                    cx0, cy0 = r0.centre
                    for step in range(0, 100):
                        rad = step * 0.25
                        n = max(1, int(2 * math.pi * rad / 0.25))
                        for k in range(n):
                            a = 2 * math.pi * k / n
                            cx, cy = tx + rad * math.cos(a), ty + rad * math.sin(a)
                            cand = r0.shift(cx - cx0, cy - cy0)
                            if not cand.inside_board() or cand.near_hole():
                                continue
                            if any(cand.hits(o) for o in occupied[side]):
                                continue
                            if any(cand.hits(r) for r in rings[side]):
                                continue
                            cost = rad + penalty
                            if best is None or cost < best[0]:
                                best = (cost, side, rot, cx - cx0, cy - cy0)
                            break
                        else:
                            continue
                        break
            if best is None:
                raise SystemExit(f"no room for {ref} near ({tx:.1f}, {ty:.1f}) on {sides}")
            _, side, rot, x, y = best
            put(fps[ref], side, x, y, rot)
            block(fps[ref], side)
            placed[ref] = side
            report.append((ref, side, round(best[0], 2)))
        pending = later
    if pending:
        raise SystemExit(f"could not place (no placed partner): {pending}")

    tidy_text(fps, placed)
    add_outline(board)
    add_planes(board, nets)
    PCB.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(PCB), board, True)
    add_stackup(PCB)
    write_report(placed, report)
    print(f"placed {len(placed)} parts: top {sum(s == 'F' for s in placed.values())}, "
          f"bottom {sum(s == 'B' for s in placed.values())}")


def tidy_text(fps, placed):
    """References go to the fabrication layer (assembly drawing); silkscreen keeps pad labels."""
    for ref, fp in fps.items():
        side = placed[ref]
        fab = pcbnew.F_Fab if side == "F" else pcbnew.B_Fab
        silk = pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS
        fp.Reference().SetLayer(fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
        fp.Reference().SetTextThickness(MM(0.08))
        fp.Reference().SetPosition(fp.GetPosition())
        fp.Value().SetVisible(False)
        if ref.startswith("TP") and fp.GetValue() not in ("SWDIO", "SWCLK", "NRST", "BOOT0", "3V3", "GND"):
            pass  # wire pad labels are added as board text in the routing step
        for item in fp.GraphicalItems():   # drop library silkscreen outlines on tiny parts
            if item.GetLayer() == silk and ref[0] in "RC" and not ref.startswith("CN"):
                item.SetVisible(False) if hasattr(item, "SetVisible") else None


def add_outline(board):
    r, h = CORNER_R, HALF

    def seg(x0, y0, x1, y1):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(CX + x0), MM(CY + y0)))
        s.SetEnd(pcbnew.VECTOR2I(MM(CX + x1), MM(CY + y1)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)

    def arc(cx, cy, a0):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in (a0, a0 + 45, a0 + 90)]
        s.SetArcGeometry(*[pcbnew.VECTOR2I(MM(CX + x), MM(CY + y)) for x, y in pts])
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)

    seg(-h + r, -h, h - r, -h)
    seg(h, -h + r, h, h - r)
    seg(h - r, h, -h + r, h)
    seg(-h, h - r, -h, -h + r)
    arc(h - r, -h + r, 270)
    arc(h - r, h - r, 0)
    arc(-h + r, h - r, 90)
    arc(-h + r, -h + r, 180)


def zone(board, net, layer, priority=0, inset=0.0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority)
    z.SetMinThickness(MM(0.15))
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetLocalClearance(MM(0.2))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    # corners added through the zone itself: SetOutline() takes ownership of a
    # polygon that Python later frees, and Outline() can return a raw pointer
    h = HALF - inset
    for x, y in ((-h, -h), (h, -h), (h, h), (-h, h)):
        z.AppendCorner(pcbnew.VECTOR2I(MM(CX + x), MM(CY + y)), -1)
    board.Add(z)
    return z


def add_planes(board, nets):
    zone(board, nets["GND"], pcbnew.In1_Cu)
    # keep tracks and vias 0.3 mm inside the edge (JLCPCB: copper 0.2 mm from a routed edge);
    # the router reads this keepout, so KiCad's edge rule then has margin
    for x0, y0, x1, y1 in ((-HALF, -HALF, HALF, -HALF + 0.3), (-HALF, HALF - 0.3, HALF, HALF),
                           (-HALF, -HALF, -HALF + 0.3, HALF), (HALF - 0.3, -HALF, HALF, HALF)):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False)
        z.SetDoNotAllowFootprints(False)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        # corners added through the zone itself: SetOutline() takes ownership of a
        # polygon that Python later frees, and Outline() can return a raw pointer
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            z.AppendCorner(pcbnew.VECTOR2I(MM(CX + x), MM(CY + y)), -1)
        board.Add(z)


def write_report(placed, report):
    out = ROOT / "reports" / "hardware" / "placement.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    top = sorted(r for r, s in placed.items() if s == "F")
    bot = sorted(r for r, s in placed.items() if s == "B")
    lines = ["# Placement", "", "Generated by `hardware/gen/build_board.py`.", "",
             f"- Top side: {len(top)} parts", f"- Bottom side: {len(bot)} parts", "",
             "Greedy placements (distance in mm from the pins each part serves):", "",
             "| Part | Side | Distance |", "| --- | --- | --- |"]
    lines += [f"| {r} | {'top' if s == 'F' else 'bottom'} | {d} |" for r, s, d in report]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()

"""Finish the routed board: copper pours, silkscreen labels, zone fill.

- Ground pours on both outer layers, ground plane on inner layer 1 (already there), a 5 V pour on
  inner layer 2 that fills around the signals routed there.
- Local pours on the battery-side power nets, so their current is not limited to the 0.4 mm tracks.
- Silkscreen: a label next to every wire pad and connector, and the board name.

Run with KiCad's Python, from the repo root:
    "%LOCALAPPDATA%/Programs/KiCad/10.0/bin/python.exe" hardware/gen/finish_board.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pcbnew  # noqa: E402
from board_common import PCB  # noqa: E402

MM = pcbnew.FromMM
CX = CY = 100.0
HALF = 18.0
TEXT_H = 0.8          # silkscreen text height (the board's minimum rule)
TEXT_T = 0.15

CONNECTOR_LABELS = {"J1": "ESC", "J3": "USB", "J4": "CAN", "J5": "TELEM1", "J6": "GPS1"}
SWD_PADS = {"TP1", "TP2", "TP3", "TP4", "TP5", "TP6"}
LOCAL_POURS = ["VBAT_IN", "VBAT", "+5V_REG"]   # battery-side nets, all inside the power corner


def V(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))


def rect_mm(bb):
    x0, y0 = pcbnew.ToMM(bb.GetX()) - CX, pcbnew.ToMM(bb.GetY()) - CY
    return [x0, y0, x0 + pcbnew.ToMM(bb.GetWidth()), y0 + pcbnew.ToMM(bb.GetHeight())]


def overlap(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def zone(board, net, layer, pts, priority, clearance=0.2):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority)
    z.SetMinThickness(MM(0.15))
    z.SetLocalClearance(MM(clearance))
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    # corners added through the zone itself: SetOutline() takes ownership of a
    # polygon that Python later frees, and Outline() can return a raw pointer
    for x, y in pts:
        z.AppendCorner(pcbnew.VECTOR2I(MM(CX + x), MM(CY + y)), -1)
    board.Add(z)
    return z


def full():
    h = HALF - 0.3
    return [(-h, -h), (h, -h), (h, h), (-h, h)]


def add_pours(board):
    # read everything first: pcbnew can crash if pads are listed after zones were removed
    copper = []   # (net name, layer, rect) for pads and tracks on the outer layers
    for item in list(board.GetPads()) + list(board.GetTracks()):
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if item.IsOnLayer(layer):
                copper.append((item.GetNetname(), layer, rect_mm(item.GetBoundingBox())))
    for z in list(board.Zones()):   # earlier pours go; the ground plane and keepouts stay
        if not z.GetIsRuleArea() and z.GetLayer() != pcbnew.In1_Cu:
            board.Remove(z)
    gnd = board.FindNet("GND")
    zone(board, gnd, pcbnew.F_Cu, full(), 0)
    zone(board, gnd, pcbnew.B_Cu, full(), 0)
    # +5V carries up to 2 A to the connectors: the inner pour gives it the width a
    # 0.25 mm track cannot (D9); 3.3 V draws far less and runs on tracks
    zone(board, board.FindNet("+5V"), pcbnew.In2_Cu, full(), 0)
    # local power pours: the box around each net's copper on each outer layer, higher priority
    names = {n for n, _, _ in copper}
    for name in LOCAL_POURS:
        net_name = next(n for n in names if n.rsplit("/", 1)[-1] == name)  # e.g. /Power/VBAT
        net = board.FindNet(net_name)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            boxes = [r for n, lyr, r in copper if n == net_name and lyr == layer]
            if len(boxes) < 2:
                continue
            x0 = min(b[0] for b in boxes) - 0.3
            y0 = min(b[1] for b in boxes) - 0.3
            x1 = max(b[2] for b in boxes) + 0.3
            y1 = max(b[3] for b in boxes) + 0.3
            z = zone(board, net, layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 1)
            # power pours join their pads solidly: thermal spokes were starved in this corner
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)


def survey(board):
    """Everything the labels need, read before the board is changed (see add_pours)."""
    data = {"avoid": {"F": [], "B": []}, "parts": []}
    for p in board.GetPads():
        r = rect_mm(p.GetBoundingBox())
        th = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        for side, layer in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
            if th or p.IsOnLayer(layer):
                data["avoid"][side].append(r)
    # vias are covered by solder mask, so a label may sit over them
    for fp in board.GetFootprints():
        side = "B" if fp.IsFlipped() else "F"
        body = rect_mm(fp.GetBoundingBox(False))
        ref = fp.GetReference()
        x, y = pcbnew.ToMM(fp.GetPosition().x) - CX, pcbnew.ToMM(fp.GetPosition().y) - CY
        data["parts"].append((ref, side, x, y, fp.GetValue(), body))
        if not ref.startswith(("TP", "H")):   # text on top of a part would be hidden by it
            data["avoid"][side].append(body)
    return data


def add_text(board, text, side, x, y, size=TEXT_H, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(TEXT_T if size <= 1 else 0.2))
    t.SetPosition(V(x, y))
    t.SetTextAngleDegrees(angle)
    if side == "B":
        t.SetMirrored(True)
    board.Add(t)
    return t


def place_label(board, text, side, anchor, avoid, size=TEXT_H, search=6.0):
    """Put text at the free spot nearest to anchor (x, y); returns True if placed."""
    w = 0.75 * size * len(text) + 0.2
    h = size + 0.2
    ax, ay = anchor
    best = None
    steps = int(search / 0.2)
    for i in range(steps + 1):
        for j in range(steps + 1):
            for sx in (1, -1):
                for sy in (1, -1):
                    dx, dy = sx * i * 0.2, sy * j * 0.2
                    cost = abs(dx) + abs(dy)
                    if best and cost >= best[0]:
                        continue
                    x, y = ax + dx, ay + dy
                    r = [x - w / 2, y - h / 2, x + w / 2, y + h / 2]
                    if r[0] < -HALF + 0.5 or r[2] > HALF - 0.5 or r[1] < -HALF + 0.5 or r[3] > HALF - 0.5:
                        continue
                    if any(overlap(r, o, 0.15) for o in avoid):
                        continue
                    best = (cost, x, y, r)
    if not best:
        print(f"no room for label {text}")
        return False
    _, x, y, r = best
    add_text(board, text, side, x, y, size)
    avoid.append(r)
    return True


def add_labels(board, data):
    for d in list(board.Drawings()):
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            board.Remove(d)
    avoid = data["avoid"]
    placed, missed = 0, []
    for ref, side, x, y, value, bb in data["parts"]:
        if ref in CONNECTOR_LABELS:
            # just inside the board, on the side of the connector facing the board centre
            if abs(x) < abs(y):
                ax, ay = (bb[0] + bb[2]) / 2, (bb[1] - 0.9 if y > 0 else bb[3] + 0.9)
            else:
                ax, ay = (bb[0] - 2.0 if x > 0 else bb[2] + 2.0), (bb[1] + bb[3]) / 2
            ok = place_label(board, CONNECTOR_LABELS[ref], side, (ax, ay), avoid[side])
            if not ok:   # no room beside it: name it on the other side, behind the connector
                other = "B" if side == "F" else "F"
                ok = place_label(board, CONNECTOR_LABELS[ref], other, (x, y), avoid[other])
        elif ref.startswith("TP"):
            # wire pads: the label strip beside each row (build_board.py keeps it free)
            if y > 15:
                anchor = (x, 14.85)
            elif x < -15:
                anchor = (-14.3, y)
            else:
                anchor = (x, y - 1.4)
            ok = place_label(board, value, side, anchor, avoid[side], search=3.2)
        else:
            continue
        placed += ok
        if not ok:
            missed.append(ref)
    return placed, missed


def main():
    board = pcbnew.LoadBoard(str(PCB))
    data = survey(board)
    add_pours(board)
    placed, missed = add_labels(board, data)
    print(f"labels placed: {placed}, no room: {missed}")
    pcbnew.SaveBoard(str(PCB), board, True)
    # fill from a fresh load: filling in the session that removed zones crashes pcbnew
    fresh = pcbnew.LoadBoard(str(PCB))
    pcbnew.ZONE_FILLER(fresh).Fill(fresh.Zones())
    pcbnew.SaveBoard(str(PCB), fresh, True)


if __name__ == "__main__":
    main()

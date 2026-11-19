"""Route the board with Freerouting and save.

Steps:
1. Ground fan-out: a short track and a via from every surface ground pad down to the solid ground
   plane on inner layer 1 (what a person would do by hand before routing).
2. Export the board to Specctra DSN and adapt it for Freerouting 2.5.0's command-line build, which
   crashes when it snapshots planes, keepouts or component outlines (UnsupportedFeatureError in its
   native image): outlines and the plane are removed, keepouts become net-less pins (so they still
   block routing), and the ground class is skipped because the plane connects it.
3. Run Freerouting, import its session file and save.

Run with KiCad's Python, from the repo root:
    "%LOCALAPPDATA%/Programs/KiCad/10.0/bin/python.exe" hardware/gen/route_board.py [passes]
    ... route_board.py [passes] --continue    # start from the routes already on the board
Freerouting: the Java build (freerouting-2.5.0.jar, needs Java 25) in .cache/tools/freerouting/jar/
with a JRE in .cache/tools/jre/, or set FREEROUTING_JAR and JAVA. The native command-line build
(FREEROUTING_CLI) also works for the first pass but crashes on the second (see step 2).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pcbnew  # noqa: E402
from board_common import PCB, ROOT  # noqa: E402

WORK = ROOT / ".cache" / "route"
FREEROUTING = Path(os.environ.get(
    "FREEROUTING_CLI", ROOT / ".cache" / "tools" / "freerouting" / "cli" / "freerouting-cli.exe"))
FREEROUTING_JAR = Path(os.environ.get(
    "FREEROUTING_JAR", ROOT / ".cache" / "tools" / "freerouting" / "jar" / "freerouting-2.5.0.jar"))


def java() -> str:
    if os.environ.get("JAVA"):
        return os.environ["JAVA"]
    exe = "java.exe" if os.name == "nt" else "java"
    found = sorted((ROOT / ".cache" / "tools" / "jre").glob(f"jdk-*-jre/bin/{exe}"))
    return str(found[0]) if found else "java"


def router_command() -> list[str]:
    if FREEROUTING_JAR.exists():
        return [java(), "-jar", str(FREEROUTING_JAR)]
    return [str(FREEROUTING)]
MM = pcbnew.FromMM
CX = CY = 100.0
HALF = 18.0
HOLE_XY = 15.25

VIA_D, VIA_DRILL = 0.45, 0.2
FAN_W = 0.25          # fan-out track width
CLR = 0.11            # clearance used for fan-out (design rule 0.1, plus margin)
INWARD = {"U7"}       # QFP: ground vias go under the body, leaving the outside for signals
# ground: each pad to the plane; 3.3 V: each pad gets an escape via the router then joins up
FANOUT_NETS = ["GND", "+3V3"]
# the ground plane stays whole under these (no routes on inner layer 1 there)
QUIET = {"U8", "U9", "U10"}


# ----------------------------------------------------------------------------- geometry
def rect_of(item):
    bb = item.GetBoundingBox()
    x0, y0 = pcbnew.ToMM(bb.GetX()) - CX, pcbnew.ToMM(bb.GetY()) - CY
    return (x0, y0, x0 + pcbnew.ToMM(bb.GetWidth()), y0 + pcbnew.ToMM(bb.GetHeight()))


def pt_rect(px, py, r):
    dx = max(r[0] - px, 0.0, px - r[2])
    dy = max(r[1] - py, 0.0, py - r[3])
    return math.hypot(dx, dy)


def pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def seg_hits_rect(ax, ay, bx, by, r):
    """Liang-Barsky clip: does the segment pass through the rectangle?"""
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - r[0]), (dx, r[2] - ax), (-dy, ay - r[1]), (dy, r[3] - ay)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def seg_rect(ax, ay, bx, by, r):
    """Exact distance between a segment and an axis-aligned rectangle."""
    if seg_hits_rect(ax, ay, bx, by, r):
        return 0.0
    corners = ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]))
    d = min(pt_seg(cx, cy, ax, ay, bx, by) for cx, cy in corners)
    return min(d, pt_rect(ax, ay, r), pt_rect(bx, by, r))


def pos(item):
    p = item.GetPosition()
    return pcbnew.ToMM(p.x) - CX, pcbnew.ToMM(p.y) - CY


# ----------------------------------------------------------------------------- fan-out
def seg_seg(a, b, c, d):
    """Distance between segments ab and cd (points as (x, y))."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2 = cross(c, d, a), cross(c, d, b)
    d3, d4 = cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(pt_seg(*a, *c, *d), pt_seg(*b, *c, *d), pt_seg(*c, *a, *b), pt_seg(*d, *a, *b))


def fanout(board, net_name):
    """A short track and a via from every surface pad of one net (see the module docstring)."""
    net = board.FindNet(net_name)
    pads = list(board.GetPads())
    net_pads = [p for p in pads if p.GetNetname() == net_name
                and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    other = [(rect_of(p), p) for p in pads]
    vias = []   # (x, y, net) of every via on the board
    segs = []   # (a, b, width, net, layer) of every track on the board
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.append((*pos(t), t.GetNetname()))
        else:
            s0, e0 = t.GetStart(), t.GetEnd()
            segs.append(((pcbnew.ToMM(s0.x) - CX, pcbnew.ToMM(s0.y) - CY),
                         (pcbnew.ToMM(e0.x) - CX, pcbnew.ToMM(e0.y) - CY),
                         pcbnew.ToMM(t.GetWidth()), t.GetNetname(), t.GetLayer()))
    # footprint keepouts (the microSD socket, the BMI088): no vias, and no tracks on their layer
    via_keepouts, track_keepouts = [], []
    for fp in board.GetFootprints():
        for z in fp.Zones():
            if not z.GetIsRuleArea():
                continue
            r = rect_of(z)
            if z.GetDoNotAllowVias():
                via_keepouts.append(r)
            if z.GetDoNotAllowTracks():
                track_keepouts.extend((r, layer) for layer in z.GetLayerSet().Seq())

    def add_track(a, b, layer):
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(pcbnew.VECTOR2I(MM(CX + a[0]), MM(CY + a[1])))
        tr.SetEnd(pcbnew.VECTOR2I(MM(CX + b[0]), MM(CY + b[1])))
        tr.SetWidth(MM(FAN_W))
        tr.SetLayer(layer)
        tr.SetNet(net)
        board.Add(tr)
        segs.append((a, b, FAN_W, net_name, layer))

    def track_clear(a, b, layer, pad):
        for r, op in other:
            if op is pad or op.GetNetname() == net_name or not op.IsOnLayer(layer):
                continue
            if seg_rect(*a, *b, r) < FAN_W / 2 + CLR:
                return False
        for c, d, w, n, lyr in segs:
            if n != net_name and lyr == layer and seg_seg(a, b, c, d) < FAN_W / 2 + w / 2 + CLR:
                return False
        for vx, vy, n in vias:
            if n != net_name and pt_seg(vx, vy, *a, *b) < FAN_W / 2 + VIA_D / 2 + CLR:
                return False
        return not any(lyr == layer and seg_rect(*a, *b, r) < FAN_W / 2 + 0.1
                       for r, lyr in track_keepouts)

    def via_clear(vx, vy, pad):
        if abs(vx) > HALF - 0.6 or abs(vy) > HALF - 0.6:
            return False
        if any(math.hypot(vx - sx * HOLE_XY, vy - sy * HOLE_XY) < 3.5
               for sx in (-1, 1) for sy in (-1, 1)):
            return False
        # KiCad lets same-net vias touch, but Freerouting checks copper clearance between them
        # too, so every via keeps its full clearance
        if any(math.hypot(vx - x, vy - y) < VIA_D + 0.15 for x, y, _ in vias):
            return False
        if any(pt_rect(vx, vy, r) < VIA_D / 2 + 0.1 for r in via_keepouts):
            return False
        for r, op in other:
            if op is pad:
                if pt_rect(vx, vy, r) < VIA_D / 2 + 0.05:   # no via in its own pad
                    return False
                continue
            same = op.GetNetname() == net_name
            if pt_rect(vx, vy, r) < VIA_D / 2 + (0.05 if same else CLR):   # never in a pad
                return False
        return all(n == net_name or pt_seg(vx, vy, *c, *d) >= VIA_D / 2 + w / 2 + CLR
                   for c, d, w, n, _ in segs)

    done, failed, linked = 0, [], []
    # fine-pitch parts first, they have the fewest free spots
    net_pads.sort(key=lambda p: min(pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)))
    for pad in net_pads:
        px, py = pos(pad)
        fp = pad.GetParentFootprint()
        fx, fy = pos(fp)
        ox, oy = px - fx, py - fy
        if math.hypot(ox, oy) < 1e-6:
            ox, oy = 1.0, 0.0
        pr = rect_of(pad)
        w, h = pr[2] - pr[0], pr[3] - pr[1]
        if max(w, h) > 1.5 * min(w, h):   # long pad: leave along its long axis
            ox, oy = (math.copysign(1.0, ox), 0.0) if w > h else (0.0, math.copysign(1.0, oy))
        base = math.atan2(oy, ox)
        if fp.GetReference() in INWARD:   # under the package body, inside the pin ring
            base += math.pi
        half = max(w, h) / 2
        layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        best = None
        for da in (0, 20, -20, 40, -40, 60, -60, 90, -90, 120, -120, 150, -150, 180):
            a = base + math.radians(da)
            for k in range(0, 40):
                d = half * 0.6 + VIA_D / 2 + CLR + 0.1 * k
                vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                cost = d + 0.4 * abs(da) / 90
                if best and cost >= best[0]:
                    break
                if via_clear(vx, vy, pad) and track_clear((px, py), (vx, vy), layer, pad):
                    best = (cost, vx, vy)
                    break
        if best:
            _, vx, vy = best
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(MM(CX + vx), MM(CY + vy)))
            via.SetWidth(MM(VIA_D))
            via.SetDrill(MM(VIA_DRILL))
            via.SetNet(net)
            board.Add(via)
            add_track((px, py), (vx, vy), layer)
            vias.append((vx, vy, net_name))
            other.append(((vx - VIA_D / 2, vy - VIA_D / 2, vx + VIA_D / 2, vy + VIA_D / 2), via))
            done += 1
            continue
        # fall back to a track to the nearest via or pad of the same net on the same layer
        near = [(x, y) for x, y, n in vias if n == net_name] + [
            pos(op) for _, op in other if op is not pad and op.GetClass() == "PAD"
            and op.GetNetname() == net_name and op.IsOnLayer(layer)]
        near.sort(key=lambda t: math.hypot(t[0] - px, t[1] - py))
        link = next((t for t in near[:12] if math.hypot(t[0] - px, t[1] - py) <= 4.0
                     and track_clear((px, py), t, layer, pad)), None)
        if link:
            add_track((px, py), link, layer)
            linked.append(f"{fp.GetReference()}.{pad.GetNumber()}")
        else:
            failed.append(f"{fp.GetReference()}.{pad.GetNumber()}")
    print(f"{net_name} fan-out: {done} vias, {len(linked)} pads linked by track {linked}, "
          f"failed {failed}")
    return failed


# ----------------------------------------------------------------------------- DSN fixes
def find_block(text, start):
    depth, k, quoted = 0, start, False
    while True:
        c = text[k]
        if c == '"':
            quoted = not quoted
        elif not quoted and c == "(":
            depth += 1
        elif not quoted and c == ")":
            depth -= 1
            if depth == 0:
                return k + 1
        k += 1


def drop_blocks(text: str, head: str) -> str:
    """Remove every balanced s-expression that starts with head, e.g. "(outline"."""
    out, i = [], 0
    while True:
        j = text.find(head, i)
        if j < 0:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:j])
        i = find_block(text, j)


def keepouts_to_pins(text: str) -> str:
    """Turn footprint keepouts into net-less pins with the same shape, so they still block routes."""
    stacks, out, i, n = [], [], 0, 0
    while True:
        j = text.find('(keepout "" ', i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        end = find_block(text, j)
        shape = text[j + len('(keepout "" '):end - 1].strip()
        n += 1
        stacks.append(f"    (padstack KO_{n}\n      (shape {shape})\n      (attach off)\n    )\n")
        out.append(f"(pin KO_{n} KO{n} 0 0)")
        i = end
    text = "".join(out)
    lib = text.find("(library")
    lib_end = find_block(text, lib)
    return text[:lib_end - 1] + "".join(stacks) + text[lib_end - 1:]


def fix_dsn(path: Path, native: bool, quiet: list):
    """Ground is joined by the plane, not the router, so the plane leaves the routing file. That
    frees inner layer 1 for short routes, except under the motion sensors and barometer (quiet,
    board mm rectangles), where a keepout keeps the ground plane whole. (Freerouting's keepouts
    also stop vias, so a keepout over the whole layer starves the router.) The native build
    also needs outlines removed and keepouts turned into pins."""
    text = path.read_text(encoding="utf-8")
    text = drop_blocks(text, "(plane ")
    keep = ""
    for x0, y0, x1, y1 in quiet:   # DSN units are micrometres and KiCad writes y upwards
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        ring = " ".join(f"{int((CX + x) * 1000)} {-int((CY + y) * 1000)}" for x, y in pts)
        keep += f'    (keepout "quiet ground" (polygon In1.Cu 0  {ring}))\n'
    i = text.index("    (via ", text.index("(structure"))
    text = text[:i] + keep + text[i:]
    if native:
        text = drop_blocks(text, "(outline")
        text = keepouts_to_pins(text)
    path.write_text(text, encoding="utf-8")


def quiet_areas(board):
    """Rectangles (board mm) under the motion sensors and barometer, 1 mm beyond their bodies."""
    out = []
    for fp in board.GetFootprints():
        if fp.GetReference() in QUIET:
            x0, y0, x1, y1 = rect_of(fp)
            out.append((x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0))
    return out


# ----------------------------------------------------------------------------- main
def route(passes: int, keep: bool = False) -> None:
    """Route from scratch, or with keep=True start from the routes already on the board."""
    WORK.mkdir(parents=True, exist_ok=True)
    dsn, ses, result = WORK / "dronefc.dsn", WORK / "dronefc.ses", WORK / "result.json"
    board = pcbnew.LoadBoard(str(PCB))
    if not keep:
        for t in list(board.GetTracks()):
            board.Remove(t)
        for net_name in FANOUT_NETS:
            fanout(board, net_name)
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise SystemExit("DSN export failed")
    fix_dsn(dsn, native=not FREEROUTING_JAR.exists(), quiet=quiet_areas(board))
    for f in (ses, result):
        f.unlink(missing_ok=True)
    t0 = time.time()
    log = WORK / "freerouting.log"
    with log.open("w", encoding="utf-8") as fh:
        subprocess.run([*router_command(), "-de", str(dsn), "-do", str(ses),
                        f"--router.autorouter.max_passes={passes}",
                        "--router.autorouter.ignore_net_classes=Ground",
                        # the fan-out pre-pass puts an escape via 2.5 to 4.5 mm from every surface
                        # pin; on a board this dense that takes the room the routes need
                        "--router.fanout.enabled=false",
                        # no automatic neck-down: it narrows tracks below the 0.09 mm minimum
                        "--router.automatic_neckdown=false",
                        # one run once took 8 hours in the optimizer; cap the whole job
                        "--router.job_timeout=00:45:00",
                        f"--router.result_json={result}"],
                       stdout=fh, stderr=subprocess.STDOUT, check=False, timeout=3 * 3600)
    print(f"freerouting finished in {time.time() - t0:.0f} s")
    if not ses.exists():
        raise SystemExit(f"no session file; see {log}")
    if result.exists():
        res = json.loads(result.read_text(encoding="utf-8"))
        print("result:", {k: v for k, v in res.items() if not isinstance(v, (dict, list))})
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise SystemExit("SES import failed")
    pcbnew.SaveBoard(str(PCB), board, True)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    print(f"imported {len(tracks)} track segments and {len(vias)} vias")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    route(int(args[0]) if args else 40, keep="--continue" in sys.argv)

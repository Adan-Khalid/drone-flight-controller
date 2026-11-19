"""Shared helpers for the board scripts (run with KiCad's bundled Python, which has pcbnew).

- netlist(): KiCad's own netlist of the schematic (parts, symbol paths, pin nets)
- load_footprint(): a footprint from KiCad's library or the project library, linked to its symbol
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sexp import find, find_all, parse  # noqa: E402

ROOT = HERE.parents[1]
KICAD_DIR = HERE.parent / "kicad"
SCH = KICAD_DIR / "dronefc.kicad_sch"
PCB = KICAD_DIR / "dronefc.kicad_pcb"
KICAD = Path(os.environ.get("KICAD_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
_WIN_FP = KICAD / "share" / "kicad" / "footprints"
STD_FP = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", _WIN_FP if _WIN_FP.exists()
                             else "/usr/share/kicad/footprints"))
PROJECT_FP = KICAD_DIR / "lib" / "dronefc.pretty"


def kicad_cli() -> str:
    exe = os.environ.get("KICAD_CLI")
    if exe:
        return exe
    win = KICAD / "bin" / "kicad-cli.exe"
    return str(win) if win.exists() else "kicad-cli"


def netlist():
    """Return (parts, pin_net). parts: ref -> dict(value, footprint, path, fields)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dronefc.net"
        subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadsexpr",
                        "-o", str(out), str(SCH)], check=True, capture_output=True)
        tree = parse(out.read_text(encoding="utf-8"))
    parts = {}
    for comp in find_all(find(tree, "components"), "comp"):
        ref = str(find(comp, "ref")[1])
        sheet = str(find(find(comp, "sheetpath"), "tstamps")[1])
        stamp = find(comp, "tstamps")
        fields = {}
        for fld in find_all(find(comp, "fields") or [], "field"):
            name = str(find(fld, "name")[1])
            fields[name] = str(fld[2]) if len(fld) > 2 else ""
        parts[ref] = {
            "value": str(find(comp, "value")[1]),
            "footprint": str(find(comp, "footprint")[1]) if find(comp, "footprint") else "",
            "path": sheet.rstrip("/") + "/" + str(stamp[1]),
            "sheet": str(find(find(comp, "sheetpath"), "names")[1]),
            "fields": fields,
        }
    pin_net = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1])   # full name, e.g. "/Power/SW5" for a local label
        for node in find_all(net, "node"):
            pin_net[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return parts, pin_net


def short(net: str) -> str:
    """Net name without its sheet path ("/Power/SW5" -> "SW5")."""
    return net.rsplit("/", 1)[-1]


def load_footprint(pcbnew, fpid: str):
    lib, name = fpid.split(":", 1)
    path = PROJECT_FP if lib == "dronefc" else STD_FP / f"{lib}.pretty"
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f"footprint {fpid} not found in {path}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp

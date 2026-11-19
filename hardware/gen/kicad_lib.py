"""Load schematic symbols from KiCad's installed libraries and the project library.

Derived symbols ("extends") are flattened, because a schematic's lib_symbols block needs the
complete definition. Pin positions are returned in library coordinates (y up).
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from sexp import Sym, find, find_all, parse

KICAD = Path(os.environ.get("KICAD_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
_WIN_SYMBOLS = KICAD / "share" / "kicad" / "symbols"
# Windows install, else the Linux location (KiCad's Docker image used in CI)
STD_SYMBOLS = Path(os.environ.get("KICAD10_SYMBOL_DIR", _WIN_SYMBOLS if _WIN_SYMBOLS.exists()
                                  else "/usr/share/kicad/symbols"))
PROJECT_LIB = Path(__file__).resolve().parents[1] / "kicad" / "lib" / "dronefc.kicad_sym"


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    etype: str      # electrical type: power_in, passive, input, ...
    x: float        # connection point, library coordinates (y up)
    y: float
    angle: float    # direction from the connection point towards the body
    hidden: bool


@cache
def _library(path: str) -> dict:
    tree = parse(Path(path).read_text(encoding="utf-8"))
    return {s[1]: s for s in find_all(tree, "symbol")}


def _lib_path(lib: str) -> Path:
    if lib == "dronefc":
        return PROJECT_LIB
    return STD_SYMBOLS / f"{lib}.kicad_sym"


def symbol_def(lib_id: str):
    """Flattened symbol definition named lib_id ("Library:Name"), ready for lib_symbols."""
    lib, name = lib_id.split(":", 1)
    syms = _library(str(_lib_path(lib)))
    node = copy.deepcopy(syms[name])
    ext = find(node, "extends")
    if ext:
        base = copy.deepcopy(syms[ext[1]])
        # keep the derived symbol's properties, take the base's units (graphics and pins)
        props = find_all(node, "property")
        keep = [c for c in base if not (isinstance(c, list) and c and c[0] in ("property",))]
        node = [Sym("symbol"), name]
        for c in keep[2:]:
            if isinstance(c, list) and c and c[0] == "symbol":
                c[1] = c[1].replace(ext[1], name, 1)
            node.append(c)
        node[2:2] = props
    node[1] = lib_id
    return node


def pins(lib_id: str) -> list[Pin]:
    """All pins of a symbol (unit and body style 1 or common)."""
    out = []
    for unit in find_all(symbol_def(lib_id), "symbol"):
        for p in find_all(unit, "pin"):
            at = find(p, "at")
            name = find(p, "name")
            num = find(p, "number")
            hidden = any(isinstance(c, list) and c and c[0] == "hide" and str(c[1]) == "yes" for c in p) or \
                any(c == "hide" for c in p if isinstance(c, str))
            out.append(Pin(str(num[1]), str(name[1]), str(p[1]), float(at[1]), float(at[2]),
                           float(at[3]) if len(at) > 3 else 0.0, hidden))
    return out


def body_box(lib_id: str) -> tuple[float, float, float, float]:
    """Bounding box (x0, y0, x1, y1) of all pins' connection points, library coordinates."""
    ps = pins(lib_id)
    xs = [p.x for p in ps] or [0]
    ys = [p.y for p in ps] or [0]
    return min(xs), min(ys), max(xs), max(ys)


if __name__ == "__main__":
    import sys
    for lid in sys.argv[1:]:
        print("==", lid)
        for p in sorted(pins(lid), key=lambda p: (len(p.number), p.number)):
            print(f"  {p.number:>4} {p.name:<22} {p.etype:<14} ({p.x}, {p.y}) a{p.angle:g}{' hidden' if p.hidden else ''}")

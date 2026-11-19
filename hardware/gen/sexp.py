"""Minimal S-expression reader and writer for KiCad files."""

from __future__ import annotations

import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


class Sym(str):
    """An unquoted atom (keyword or number), as opposed to a quoted string."""


def parse(text: str):
    """Parse one S-expression into nested lists of Sym (atoms) and str (quoted strings)."""
    stack: list[list] = [[]]
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"bad token at {pos}: {text[pos:pos + 30]!r}")
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            done = stack.pop()
            stack[-1].append(done)
        elif m.group(3) is not None:
            stack[-1].append(m.group(3).replace('\\"', '"').replace("\\\\", "\\"))
        elif m.group(4) is not None:
            stack[-1].append(Sym(m.group(4)))
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def q(s: str) -> str:
    """Quote a string for KiCad."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump(node, indent: int = 0) -> str:
    """Serialise nested lists back to KiCad-style text."""
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return str(node)
        if isinstance(node, (int, float)):
            return fmt(node)
        return q(node)
    pad = "  " * indent
    simple = all(not isinstance(c, list) for c in node)
    if simple:
        return "(" + " ".join(dump(c) for c in node) + ")"
    head = []
    rest = []
    for c in node:
        (rest if (isinstance(c, list) or rest) else head).append(c)
    out = "(" + " ".join(dump(c) for c in head)
    for c in rest:
        out += "\n" + pad + "  " + dump(c, indent + 1)
    return out + "\n" + pad + ")"


def fmt(v: float) -> str:
    """Format a number the way KiCad writes it (no trailing zeros)."""
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find(node, key: str):
    """First child list whose head is `key`."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key: str):
    """All child lists whose head is `key`."""
    return [c for c in node if isinstance(c, list) and c and c[0] == key]

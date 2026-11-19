"""Checks of the circuit description and the KiCad file writer that need no KiCad install.

The full checks (ERC, pin-by-pin netlist comparison, DRC) run in the KiCad job in CI.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware" / "gen"))

import circuit  # noqa: E402
from sexp import Sym, dump, parse  # noqa: E402

BOM_PARTS = [p for p in circuit.PARTS if not p.lib.startswith("power:")]
COPPER_ONLY = ("TP", "JP")   # test pads and solder jumpers are copper, nothing is bought


def test_sexp_round_trip():
    text = '(kicad_sch (version 20260306) (lib_symbols (symbol "Device:R" (pin passive line ' \
           '(at 0 3.81 270) (length 1.27)))) (label "VBAT" (at 1.5 -2 0)))'
    tree = parse(text)
    assert parse(dump(tree)) == tree
    assert isinstance(tree[0], Sym)
    assert tree[2][1][1] == "Device:R"


def test_every_part_has_a_footprint():
    missing = [p.ref for p in BOM_PARTS if not p.fp]
    assert missing == []


def test_every_bought_part_has_an_lcsc_number():
    missing = [p.ref for p in BOM_PARTS
               if not p.ref.startswith(COPPER_ONLY) and not p.lcsc.startswith("C")]
    assert missing == []


def test_references_are_unique():
    counts = Counter(p.ref for p in circuit.PARTS)
    assert [r for r, n in counts.items() if n > 1] == []


def test_no_net_has_a_single_pin():
    members = Counter()
    for p in circuit.PARTS:
        for net in p.conn.values():
            members[net] += 1
    for net in circuit.PINMAP.values():
        members[net] += 1
    assert sorted(n for n, c in members.items() if c < 2) == []


@pytest.mark.parametrize("net", ["IMU1_SCK", "IMU1_MISO", "IMU1_MOSI", "IMU1_CS",
                                 "IMU2_SCK", "IMU2_MISO", "IMU2_MOSI", "IMU2_ACS", "IMU2_GCS"])
def test_each_imu_line_reaches_the_processor(net):
    # the pin plan puts the two IMUs on separate SPI buses (docs/PIN_PLAN.md)
    assert net in circuit.PINMAP.values()


def test_motor_outputs_have_series_resistors():
    for i in range(1, 5):   # outputs 1 to 4; 5 to 8 were removed (DECISIONS D31)
        r = [p for p in circuit.PARTS if p.ref == f"R{26 + i}"][0]
        assert set(r.conn.values()) == {f"M{i}", f"M{i}_OUT"}
        assert r.value == "220"

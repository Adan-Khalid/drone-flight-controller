"""Bill of materials and a cost estimate for the board.

Parts come from hardware/gen/circuit.py. For each LCSC part number the script reads LCSC's product
data (model, maker, package, stock, price ladder) with curl, keeps a copy in .cache/lcsc/ and
records when it was fetched. Solder joints are counted from the board file. Fees and the board
quote come from configs/costs.yaml, where each value names the page it was read on.

Writes reports/hardware/bom.csv (JLCPCB's BOM columns), reports/hardware/cost.md and cost.json.

Usage:
    uv run python scripts/bom_cost.py            # use cached LCSC data where present
    uv run python scripts/bom_cost.py --refresh  # fetch every part again
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware" / "gen"))

import circuit  # noqa: E402

CACHE = ROOT / ".cache" / "lcsc"
OUT = ROOT / "reports" / "hardware"
PCB = ROOT / "hardware" / "kicad" / "dronefc.kicad_pcb"
URL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={}"


def fetch(code: str, refresh: bool) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{code}.json"
    if refresh or not path.exists():
        # LCSC answers curl but refuses Python's default client
        raw = subprocess.run(["curl", "-s", "--max-time", "30", URL.format(code)],
                             capture_output=True, check=True).stdout
        data = json.loads(raw)
        if not data.get("result"):
            raise SystemExit(f"LCSC returned no data for {code}")
        data["_fetched"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        path.write_text(json.dumps(data), encoding="utf-8")
        time.sleep(0.5)
    return json.loads(path.read_text(encoding="utf-8"))


def smt_joints() -> int:
    if not PCB.exists():
        raise SystemExit("needs the placed board: run hardware/gen/build_board.py "
                         "with KiCad's Python")
    text = PCB.read_text(encoding="utf-8")
    return len(re.findall(r'\(pad "[^"]*" smd ', text))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs" / "costs.yaml").read_text(encoding="utf-8"))

    groups = defaultdict(list)
    for p in circuit.PARTS:
        if p.lcsc:
            groups[p.lcsc].append(p)
    rows, fetched = [], set()
    for code, parts in sorted(groups.items(), key=lambda kv: kv[1][0].ref):
        d = fetch(code, args.refresh)
        r = d["result"]
        fetched.add(d.get("_fetched", "unknown"))
        ladder = r.get("productPriceList") or []
        unit = float(ladder[0]["usdPrice"]) if ladder else None
        rows.append({
            "lcsc": code,
            "refs": [p.ref for p in parts],
            "qty": len(parts),
            "value": parts[0].value,
            "footprint": parts[0].fp.split(":", 1)[1],
            "model": r.get("productModel"),
            "maker": r.get("brandNameEn"),
            "stock": r.get("stockNumber"),
            "min_buy": r.get("minBuyNumber"),
            "unit_usd": unit,
            "line_usd": None if unit is None else round(unit * len(parts), 4),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "bom.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for row in rows:
            w.writerow([row["value"], ",".join(row["refs"]), row["footprint"], row["lcsc"]])

    parts_per_board = round(sum(r["line_usd"] or 0 for r in rows), 2)
    unpriced = [r["lcsc"] for r in rows if r["unit_usd"] is None]
    out_of_stock = [f'{r["lcsc"]} ({r["model"]})' for r in rows if not r["stock"]]
    a = cfg["assembly_standard"]
    joints = smt_joints()
    types = len(rows)
    estimates = []
    for n in cfg["boards_assembled"]:
        assembly = (a["setup_double_side"] + a["stencil_double_side"] + a["fixtures_1_to_29_boards"]
                    + a["feeder_loading_per_part_type"] * types + a["smt_per_joint"] * joints * n
                    + a["xray_per_leadless_part_1_to_10"] * len(a["leadless_parts"]) * n
                    + a["packing_base"])
        parts = parts_per_board * n
        pcb = cfg["pcb"]["price_5_boards_enig"]
        for ship_key in ("shipping_epost_0_15kg", "shipping_dhl_0_15kg"):
            ship = cfg["pcb"][ship_key]
            estimates.append({"boards_assembled": n, "shipping": ship_key,
                              "pcb": pcb, "assembly_fees": round(assembly, 2),
                              "parts": round(parts, 2), "shipping_usd": ship,
                              "total": round(pcb + assembly + parts + ship, 2)})

    summary = {
        "part_types": types,
        "parts_placed": sum(r["qty"] for r in rows),
        "smt_joints_per_board": joints,
        "parts_cost_per_board_usd": parts_per_board,
        "lcsc_data_fetched": sorted(fetched),
        "unpriced": unpriced,
        "zero_lcsc_stock": out_of_stock,
        "estimates": estimates,
    }
    (OUT / "cost.json").write_text(json.dumps({"summary": summary, "lines": rows}, indent=2) + "\n",
                                   encoding="utf-8")

    lines = [
        "# Bill of materials and cost estimate",
        "",
        "Generated by `scripts/bom_cost.py`. Part prices are LCSC's single-unit price for each "
        f"part number, read on {', '.join(sorted(fetched))}; JLCPCB charges its own part prices "
        "at assembly, so this is an estimate, not a quote. Fees: `configs/costs.yaml`.",
        "",
        f"- Part types (LCSC numbers): {types}",
        f"- Parts placed per board: {summary['parts_placed']}",
        f"- Surface-mount solder joints per board: {joints}",
        f"- Parts cost per board: ${parts_per_board:.2f}",
        f"- Parts with no LCSC stock on the day: {', '.join(out_of_stock) or 'none'}",
        "",
        "| Boards assembled | Shipping | Bare boards (5) | Assembly fees | Parts | Shipping cost "
        "| Total (USD) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for e in estimates:
        ship = "E-POST" if "epost" in e["shipping"] else "DHL"
        lines.append(f"| {e['boards_assembled']} | {ship} | {e['pcb']:.2f} | "
                     f"{e['assembly_fees']:.2f} | {e['parts']:.2f} | {e['shipping_usd']:.2f} | "
                     f"{e['total']:.2f} |")
    fixed = (a["setup_double_side"] + a["stencil_double_side"] + a["fixtures_1_to_29_boards"]
             + a["feeder_loading_per_part_type"] * types)
    lines += ["", f"Assembly fees that do not depend on the number of boards (setup, stencil, "
              f"fixtures, feeder loading for {types} part types): ${fixed:.2f}."]
    lines += ["", "Cost per assembled board (total divided by boards assembled): "
              + "; ".join(f"{e['boards_assembled']} boards with "
                          f"{'E-POST' if 'epost' in e['shipping'] else 'DHL'}: "
                          f"${e['total'] / e['boards_assembled']:.2f}" for e in estimates) + "."]
    if cfg.get("market"):
        lines += ["", "Ready-made boards for comparison (makers' stores, `configs/costs.yaml`):",
                  "", "| Board | Price (USD) | Note |", "| --- | --- | --- |"]
        lines += [f"| {m['name']} | {m['price']:.2f} | {m['note']} |" for m in cfg["market"]]
    lines += [
        "",
        "Not included: customs duty and taxes in Pakistan, JLCPCB's extra parts for machine "
        "losses, minimum-order rounding, the debug probe and the test drone.",
        "",
        "| LCSC | Model | Maker | Parts | Qty | Unit (USD) | Stock |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        unit = "n/a" if r["unit_usd"] is None else f"{r['unit_usd']:.4f}"
        lines.append(f"| {r['lcsc']} | {r['model']} | {r['maker']} | {', '.join(r['refs'])} | "
                     f"{r['qty']} | {unit} | {r['stock']} |")
    (OUT / "cost.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    for e in estimates:
        print(e)


if __name__ == "__main__":
    main()

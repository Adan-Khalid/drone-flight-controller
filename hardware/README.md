# Hardware

| Folder | Contents |
| --- | --- |
| `kicad/` | KiCad 10 project: root schematic and four sheets (power, processor, sensors and storage, connectors), and the project library (`lib/`: symbols, footprints and 3D models for the LT8641, ICM-45686 and DPS368, a tri-state BMI088 symbol, and a NexFET footprint with a trimmed gate pad) |
| `gen/` | Python scripts that generate and check the KiCad files from one circuit description |

## How the design is built

| Step | Script | Output |
| --- | --- | --- |
| Project symbols and footprints | `gen/symbols.py`, `gen/footprints.py` | `kicad/lib/` |
| Circuit: every part, value, footprint, LCSC number and pin net | `gen/circuit.py` | (input to the next steps) |
| Schematic | `gen/build_schematic.py` | `kicad/*.kicad_sch` |
| Pin-by-pin check against KiCad's own netlist | `gen/check_netlist.py` | `reports/hardware/netlist_check.md` |
| Placement, rules, stack-up, outline | `gen/build_board.py` (KiCad's Python) | `kicad/dronefc.kicad_pcb`, `reports/hardware/placement.md` |
| Ground fan-out and routing (Freerouting) | `gen/route_board.py` (KiCad's Python) | routed board |
| Copper pours and silkscreen labels | `gen/finish_board.py` (KiCad's Python) | finished board |

`scripts/kicad_checks.sh` runs KiCad's electrical rules check (ERC) on every push, and the design rules check (DRC) once a board file is committed.

**Board layout status:** not finished. `build_board.py` places the parts on a 36 x 36 mm, 4-layer board (the placement renders in the main README come from it), but routing with `route_board.py` and Freerouting left connections open and cut into the ground layer, so the board file is not committed. The routing scripts stay here as a record of what was tried (`docs/LEARNING.md`, section 13).

The Altium Designer redraw comes later and will live in `altium/`.

## 3D models

The 3D models of the LT8641, ICM-45686 and DPS368 come from LCSC's EasyEDA library and are not in this repo. To see them in KiCad's 3D viewer, fetch them with easyeda2kicad (a dev dependency) into `.cache/easyeda/` and run `uv run python hardware/gen/footprints.py`, which copies them into `kicad/lib/dronefc.3dshapes/`:

```bash
uv run easyeda2kicad --3d --lcsc_id=C462660 --output .cache/easyeda/jlc
uv run easyeda2kicad --3d --lcsc_id=C22459454 --output .cache/easyeda/jlc
uv run easyeda2kicad --3d --lcsc_id=C3232508 --output .cache/easyeda/jlc
uv run python hardware/gen/footprints.py
```

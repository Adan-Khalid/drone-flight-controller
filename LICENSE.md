# Licences

Copyright (c) 2026 Adan Khalid.

| What | Where | Licence |
| --- | --- | --- |
| Hardware design files (KiCad and Altium projects, the footprints and symbols made for this board, fabrication outputs) | `hardware/kicad/`, `fab/` | CERN Open Hardware Licence Version 2, Permissive (CERN-OHL-P-2.0), see [LICENSES/CERN-OHL-P-2.0.txt](LICENSES/CERN-OHL-P-2.0.txt) |
| ArduPilot board definition files | `firmware/hwdef/` | GPL-3.0-or-later, the same as ArduPilot, because they are built into ArduPilot |
| Scripts, calculations, board generators, simulation files, tests | `scripts/`, `src/`, `hardware/gen/`, `sim/`, `tests/` | MIT, see [LICENSES/MIT.txt](LICENSES/MIT.txt) |
| Documentation, figures and photos | `docs/`, `reports/`, `assets/` | CC BY 4.0 |

Symbols and footprints taken from the KiCad libraries keep their own licence (CC-BY-SA 4.0 with an exception for designs that use them). Part datasheets belong to their makers and are linked, not copied.

The 3D models of the LT8641, ICM-45686 and DPS368 come from LCSC's EasyEDA library; they are not included here. `hardware/gen/footprints.py` copies them into `hardware/kicad/lib/dronefc.3dshapes/` after they are fetched with easyeda2kicad (see `hardware/README.md`).

#!/usr/bin/env bash
# Run KiCad's electrical rules check (ERC) and design rules check (DRC) from the command line.
# Used by CI on every push. Reports go to reports/kicad/. Exits non-zero on any violation.
set -euo pipefail

proj_dir="hardware/kicad"
out_dir="reports/kicad"
mkdir -p "$out_dir"

shopt -s nullglob
pro_files=("$proj_dir"/*.kicad_pro)
if [ ${#pro_files[@]} -eq 0 ]; then
  echo "No KiCad project in $proj_dir yet: nothing to check."
  exit 0
fi

name="$(basename "${pro_files[0]}" .kicad_pro)"
sch="$proj_dir/$name.kicad_sch"
pcb="$proj_dir/$name.kicad_pcb"

kicad-cli version

if [ -f "$sch" ]; then
  echo "ERC: $sch"
  # Errors and warnings fail the check; violations excluded in KiCad (with a reason) do not.
  kicad-cli sch erc --format json --severity-error --severity-warning --exit-code-violations \
    --output "$out_dir/erc.json" "$sch"
fi

if [ -f "$pcb" ]; then
  echo "DRC: $pcb"
  kicad-cli pcb drc --format json --severity-error --severity-warning --schematic-parity \
    --refill-zones --exit-code-violations --output "$out_dir/drc.json" "$pcb"
fi

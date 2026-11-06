#!/usr/bin/env bash
# Use an installed KiCad10 CLI, or supply KICAD_CLI as an absolute executable path.
set -euo pipefail
electronics_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
kicad_exec="${KICAD_CLI:-kicad-cli}"
mkdir -p "$electronics_dir/reports"
for pcb_name in controller led_leaf power_adapter; do
  "$kicad_exec" pcb drc --format json -o "$electronics_dir/reports/${pcb_name}_drc.json" "$electronics_dir/native/$pcb_name/$pcb_name.kicad_pcb"
done
python3 "$electronics_dir/design/check_electrical_margins.py"
python3 "$electronics_dir/design/snapshot_qualification.py"

#!/usr/bin/env bash
set -euo pipefail

mkdir -p results/spice

run_one() {
  local name="$1"
  local netlist="hardware/spice/${name}.cir"
  local log="results/spice/${name}.log"

  echo "=== ${name} ==="
  set +e
  ngspice -b -o "$log" "$netlist"
  local rc=$?
  set -e

  cat "$log"

  if [ "$rc" -ne 0 ] || grep -Eiq '(^|[^[:alpha:]])(fatal|error)([^[:alpha:]]|$)|measure.*failed|no such vector|singular matrix' "$log"; then
    echo "SPICE failure detected in ${name} (exit=${rc})"
    exit 1
  fi
}

run_one sensor_interface
run_one echo_interface
run_one alarm_driver
run_one microphone_frontend
run_one microphone_vmid_startup
run_one power_distribution_star
run_one power_distribution_shared_return
run_one revd_sensor_frontend

python3 hardware/spice/check_results.py

echo "ALL ELECTRICAL SPICE SIMULATIONS COMPLETED"

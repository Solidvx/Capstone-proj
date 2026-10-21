#!/usr/bin/env bash
# Run only on the ECU, from the delivered source root, after IVI readiness.
set -eu
if [ "${1-}" != "--ivi-ready" ]; then
    printf '%s\n' 'No transmission. After IVI READY and capture start, run: bash run_physical_pilot_c1.sh --ivi-ready'
    exit 2
fi
test -x .venv/bin/python
test -x adaptive_ecu/build/adaptive_ecu
test -f security/experiments/live_ablation.py
metadata=results/physical-pilot-001-c1-meta
run=results/physical-pilot-001-c1
test ! -e "$metadata"
test ! -e "$run"
.venv/bin/python -c 'from security.experiments.can_capture import inspect_interface; info=inspect_interface("can0", "physical"); assert info["bitrate"] == 500000, info; print(info)'
mkdir -p results
mkdir "$metadata"
date --iso-8601=seconds > "$metadata/start.txt"
ip -details -statistics link show can0 > "$metadata/can-before.txt"
.venv/bin/python -m pip freeze > "$metadata/python-packages.txt"
set +e
.venv/bin/python -m security.experiments.live_ablation --channel can0 --environment physical --config 1 --trials 1 --rate 1000 --duration 3 --ecu adaptive_ecu/build/adaptive_ecu --run-id PHYSICAL-PILOT-001 --ivi-run-id SECURITY-PILOT-OFF-001 --i-am-on-a-test-bus --out "$run" > "$metadata/runner.log" 2>&1
runner_exit=$?
set -e
printf 'exit_code=%s\n' "$runner_exit" > "$metadata/exit.txt"
date --iso-8601=seconds > "$metadata/end.txt"
ip -details -statistics link show can0 > "$metadata/can-after.txt"
cat "$metadata/runner.log"
cat "$metadata/exit.txt"
exit "$runner_exit"

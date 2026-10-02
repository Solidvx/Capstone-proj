#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: Linux SocketCAN is required" >&2
  exit 2
fi
if [[ "$#" -lt 2 ]]; then
  echo "usage: $0 IVI_DASHBOARD OUTPUT_DIR [SAMPLES]" >&2
  exit 2
fi

dashboard="$1"
output_dir="$2"
samples="${3:-1000}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
raw_csv="${output_dir}/latency_raw.csv"
summary_csv="${output_dir}/latency_summary.csv"
key_file="${output_dir}/p4_dummy_key.bin"

mkdir -p "${output_dir}"
chmod 700 "${output_dir}"
P4_KEY_FILE="${key_file}" python3 -c \
  'import os, pathlib; pathlib.Path(os.environ["P4_KEY_FILE"]).write_bytes(bytes(range(32)))'
chmod 600 "${key_file}"

cleanup() {
  if [[ -n "${dashboard_pid:-}" ]]; then
    kill "${dashboard_pid}" >/dev/null 2>&1 || true
    wait "${dashboard_pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${key_file}"
}
trap cleanup EXIT

QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "${dashboard}" \
  --interface vcan0 --secoc-key "${key_file}" \
  --latency-csv "${raw_csv}" --latency-samples "${samples}" &
dashboard_pid=$!
sleep 1
python3 "${script_dir}/send_ivi_test_vectors.py" bms --interface vcan0 \
  --dummy-key --count "${samples}" --interval-ms 100

for _ in $(seq 1 100); do
  if ! kill -0 "${dashboard_pid}" >/dev/null 2>&1; then
    wait "${dashboard_pid}"
    dashboard_pid=""
    break
  fi
  sleep 0.1
done
if [[ -n "${dashboard_pid}" ]]; then
  echo "ERROR: dashboard did not complete ${samples} rendered samples" >&2
  exit 1
fi

python3 "${script_dir}/measure_latency.py" --input "${raw_csv}" \
  --output "${summary_csv}" --expected-samples "${samples}"

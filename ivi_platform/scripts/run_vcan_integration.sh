#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: Linux SocketCAN is required" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="${1:-/tmp/ivi-p4-vcan-build}"
created_vcan=0

cleanup() {
  if [[ "${created_vcan}" == "1" ]]; then
    sudo ip link delete vcan0 type vcan || true
  fi
}
trap cleanup EXIT

if ! ip link show vcan0 >/dev/null 2>&1; then
  sudo modprobe vcan
  sudo ip link add dev vcan0 type vcan
  created_vcan=1
fi
sudo ip link set dev vcan0 up

cmake -S "${repo_root}/ivi_platform" -B "${build_dir}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DIVI_BUILD_QT_APP=OFF \
  -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wpedantic -Werror"
cmake --build "${build_dir}" --parallel
ctest --test-dir "${build_dir}" --output-on-failure

ip -details -statistics link show vcan0

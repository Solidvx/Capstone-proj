#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: RPi build requires Linux" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="${1:-${repo_root}/ivi_platform/build-rpi}"

cmake -S "${repo_root}/ivi_platform" -B "${build_dir}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DIVI_BUILD_TESTS=ON \
  -DIVI_BUILD_QT_APP=ON \
  -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wpedantic -Werror"
cmake --build "${build_dir}" --parallel
ctest --test-dir "${build_dir}" --output-on-failure \
  --exclude-regex '^test_socketcan_receiver$'

test -x "${build_dir}/ivi_dashboard"
echo "PASS: RPi Release dashboard built at ${build_dir}/ivi_dashboard"

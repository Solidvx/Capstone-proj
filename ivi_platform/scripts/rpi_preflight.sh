#!/usr/bin/env bash
set -euo pipefail

service_mode=0
if [[ "${1:-}" == "--service" ]]; then
  service_mode=1
elif [[ "$#" -ne 0 ]]; then
  echo "usage: $0 [--service]" >&2
  exit 2
fi

interface_name="${IVI_CAN_INTERFACE:-can0}"
key_path="${IVI_SECOC_KEY:-/etc/ivi/secoc.key}"
failures=0

pass() { printf '[OK]   %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1" >&2; failures=$((failures + 1)); }

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
fi
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:22.04 | debian:13)
    pass "supported OS: ${PRETTY_NAME:-${ID} ${VERSION_ID}}"
    ;;
  *)
    fail "expected Ubuntu 22.04 or Debian 13, found ${PRETTY_NAME:-unknown OS}"
    ;;
esac

if [[ "$(uname -m)" == "aarch64" ]]; then
  pass "aarch64 userspace"
else
  fail "expected aarch64 userspace, found $(uname -m)"
fi

if [[ -r /proc/device-tree/model ]] && tr -d '\0' </proc/device-tree/model | grep -q 'Raspberry Pi 4'; then
  pass "Raspberry Pi 4 model"
else
  fail "Raspberry Pi 4 model was not detected"
fi

if [[ -e "/sys/class/net/${interface_name}" ]]; then
  pass "${interface_name} exists"
else
  fail "${interface_name} is absent"
fi
if ip link show "${interface_name}" 2>/dev/null | grep -q 'UP'; then
  pass "${interface_name} is UP"
else
  fail "${interface_name} is not UP"
fi

if [[ -f "${key_path}" ]] && [[ "$(stat -c %s "${key_path}")" -eq 32 ]]; then
  pass "SecOC key is exactly 32 bytes"
else
  fail "SecOC key is missing or has the wrong size"
fi
if [[ "$(stat -c %a "${key_path}" 2>/dev/null || true)" == "640" ]]; then
  pass "SecOC key mode is 0640"
else
  fail "SecOC key mode must be 0640"
fi
if [[ "$(stat -c %U:%G "${key_path}" 2>/dev/null || true)" == "root:ivi" ]]; then
  pass "SecOC key owner is root:ivi"
else
  fail "SecOC key owner must be root:ivi"
fi

if [[ "${service_mode}" == "1" ]] && [[ ! -x /opt/ivi/bin/ivi_dashboard ]]; then
  fail "installed dashboard binary is missing"
fi

ip -details -statistics link show "${interface_name}" 2>/dev/null || true
if [[ "${failures}" -ne 0 ]]; then
  echo "FAIL: ${failures} RPi preflight check(s) failed" >&2
  exit 1
fi
echo "PASS: RPi IVI preflight"

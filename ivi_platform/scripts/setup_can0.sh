#!/usr/bin/env bash
set -euo pipefail

interface_name="${IVI_CAN_INTERFACE:-can0}"
bitrate="${IVI_CAN_BITRATE:-500000}"
restart_ms="${IVI_CAN_RESTART_MS:-100}"
action="${1:-up}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: setup_can0.sh must run as root" >&2
  exit 2
fi
if [[ ! "${interface_name}" =~ ^can[0-9]+$ ]]; then
  echo "ERROR: invalid physical CAN interface: ${interface_name}" >&2
  exit 2
fi
if [[ ! "${bitrate}" =~ ^[0-9]+$ ]] || [[ ! "${restart_ms}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: bitrate and restart delay must be non-negative integers" >&2
  exit 2
fi
if [[ ! -e "/sys/class/net/${interface_name}" ]]; then
  echo "ERROR: ${interface_name} is absent; check SPI, overlay, oscillator and INT wiring" >&2
  exit 3
fi

if [[ "${action}" == "down" ]]; then
  ip link set dev "${interface_name}" down
  exit 0
fi
if [[ "${action}" != "up" ]]; then
  echo "usage: $0 [up|down]" >&2
  exit 2
fi

ip link set dev "${interface_name}" down 2>/dev/null || true
ip link set dev "${interface_name}" type can bitrate "${bitrate}" restart-ms "${restart_ms}"
ip link set dev "${interface_name}" up
ip -details -statistics link show "${interface_name}"

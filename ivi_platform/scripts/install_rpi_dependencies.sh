#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: this installer requires Linux" >&2
  exit 2
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo" >&2
  exit 2
fi
if [[ ! -r /etc/os-release ]]; then
  echo "ERROR: cannot identify the target OS" >&2
  exit 2
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "debian" ]] || [[ "${VERSION_ID:-}" != "13" ]]; then
  echo "ERROR: expected Debian 13, found ${PRETTY_NAME:-unknown OS}" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  build-essential cmake libssl-dev can-utils iproute2 kmod libcap2-bin \
  qt6-base-dev qt6-declarative-dev qt6-shadertools-dev \
  qt6-wayland \
  qml6-module-qtqml-workerscript qml6-module-qtquick \
  qml6-module-qtquick-controls qml6-module-qtquick-layouts

echo "PASS: RPi IVI build and runtime dependencies installed on ${PRETTY_NAME}"

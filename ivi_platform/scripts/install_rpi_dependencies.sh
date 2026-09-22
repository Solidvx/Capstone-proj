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
if [[ "${ID:-}" != "ubuntu" ]] || [[ "${VERSION_ID:-}" != "22.04" ]]; then
  echo "ERROR: expected Ubuntu 22.04, found ${PRETTY_NAME:-unknown OS}" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  build-essential cmake libssl-dev can-utils iproute2 kmod \
  qt6-base-dev qt6-declarative-dev qt6-shadertools-dev \
  qml6-module-qtqml-workerscript qml6-module-qtquick \
  qml6-module-qtquick-controls qml6-module-qtquick-layouts

echo "PASS: RPi IVI build and runtime dependencies installed"

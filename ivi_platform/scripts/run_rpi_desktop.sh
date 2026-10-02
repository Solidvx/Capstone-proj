#!/usr/bin/env bash
set -euo pipefail

dashboard=/opt/ivi/bin/ivi_dashboard
key_path=/etc/ivi/secoc.key
interface_name=can0

if [[ ! -x "${dashboard}" ]]; then
  echo "ERROR: installed dashboard binary is missing" >&2
  exit 2
fi
if [[ ! -r "${key_path}" ]] || [[ "$(stat -c %s "${key_path}")" -ne 32 ]]; then
  echo "ERROR: ${key_path} must be a readable 32-byte key" >&2
  exit 3
fi
if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
  echo "ERROR: XDG_RUNTIME_DIR is unavailable; launch from a desktop session" >&2
  exit 4
fi

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  wayland_path="$(find "${XDG_RUNTIME_DIR}" -maxdepth 1 -type s \
    -name 'wayland-*' -print -quit)"
  if [[ -z "${wayland_path}" ]]; then
    echo "ERROR: no Wayland display socket found in ${XDG_RUNTIME_DIR}" >&2
    exit 5
  fi
  export WAYLAND_DISPLAY="$(basename "${wayland_path}")"
fi

export QT_QPA_PLATFORM=wayland
exec "${dashboard}" --interface "${interface_name}" --secoc-key "${key_path}"

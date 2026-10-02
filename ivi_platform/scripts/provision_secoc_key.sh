#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]] || [[ "$#" -ne 1 ]]; then
  echo "usage: sudo $0 SOURCE_32_BYTE_KEY" >&2
  exit 2
fi
source_key="$1"
if [[ ! -f "${source_key}" ]] || [[ "$(stat -c %s "${source_key}")" -ne 32 ]]; then
  echo "ERROR: source key must be a regular file of exactly 32 bytes" >&2
  exit 3
fi
if ! id ivi >/dev/null 2>&1; then
  echo "ERROR: install the IVI package before provisioning its key" >&2
  exit 3
fi

install -d -m 0750 -o root -g ivi /etc/ivi
install -m 0640 -o root -g ivi "${source_key}" /etc/ivi/secoc.key
echo "PASS: SecOC key installed at /etc/ivi/secoc.key without displaying its contents"

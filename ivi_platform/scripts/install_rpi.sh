#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="${1:-${repo_root}/ivi_platform/build-rpi}"
deploy_dir="${repo_root}/ivi_platform/deploy/rpi"

if [[ ! -x "${build_dir}/ivi_dashboard" ]]; then
  echo "ERROR: missing ${build_dir}/ivi_dashboard; run build_rpi.sh first" >&2
  exit 3
fi

if ! id ivi >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/ivi \
    --shell /usr/sbin/nologin ivi
fi
for device_group in video render input; do
  if ! getent group "${device_group}" >/dev/null; then
    groupadd --system "${device_group}"
  fi
  usermod -a -G "${device_group}" ivi
done

install -d -m 0755 /opt/ivi/bin /opt/ivi/libexec
install -d -m 0750 -o root -g ivi /etc/ivi
install -m 0755 "${build_dir}/ivi_dashboard" /opt/ivi/bin/ivi_dashboard
install -m 0755 "${repo_root}/ivi_platform/scripts/setup_can0.sh" \
  /opt/ivi/libexec/setup_can0.sh
install -m 0755 "${repo_root}/ivi_platform/scripts/rpi_preflight.sh" \
  /opt/ivi/libexec/rpi_preflight.sh
install -m 0644 "${deploy_dir}/ivi-dashboard.env" /etc/ivi/ivi-dashboard.env
install -m 0644 "${deploy_dir}/ivi-can0.service" /etc/systemd/system/ivi-can0.service
install -m 0644 "${deploy_dir}/ivi-dashboard.service" \
  /etc/systemd/system/ivi-dashboard.service

systemctl daemon-reload
echo "PASS: IVI files installed; services remain disabled"
echo "NEXT: provision the key, verify can0, then enable ivi-can0 and ivi-dashboard"

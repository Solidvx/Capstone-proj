#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo" >&2
  exit 2
fi
if [[ "$#" -gt 1 ]]; then
  echo "usage: $0 [desktop-user]" >&2
  exit 2
fi

desktop_user="${1:-${SUDO_USER:-}}"
if [[ -z "${desktop_user}" ]] || [[ "${desktop_user}" == "root" ]]; then
  echo "ERROR: pass the non-root desktop user name" >&2
  exit 2
fi
if ! id "${desktop_user}" >/dev/null 2>&1; then
  echo "ERROR: desktop user ${desktop_user} does not exist" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"${repo_root}/ivi_platform/scripts/install_rpi.sh"

install -m 0755 "${repo_root}/ivi_platform/scripts/run_rpi_desktop.sh" \
  /opt/ivi/libexec/run_rpi_desktop.sh
install -d -m 0755 /etc/xdg/autostart
install -m 0644 "${repo_root}/ivi_platform/deploy/rpi/ivi-dashboard.desktop" \
  /etc/xdg/autostart/ivi-dashboard.desktop

usermod -a -G ivi,video,render,input "${desktop_user}"
setcap cap_net_raw=ep /opt/ivi/bin/ivi_dashboard

systemctl disable --now ivi-dashboard.service >/dev/null 2>&1 || true
systemctl enable --now ivi-can0.service

echo "PASS: Wayland desktop autostart installed for ${desktop_user}"
echo "NEXT: log out and back in, or reboot, to apply group membership"

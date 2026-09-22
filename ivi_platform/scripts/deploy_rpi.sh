#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 USER@RPi_HOST" >&2
  exit 2
fi
target="$1"
if [[ ! "${target}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9.-]*$ ]]; then
  echo "ERROR: target must be USER@HOST without shell characters" >&2
  exit 2
fi
for required_command in git ssh scp shasum; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "ERROR: missing deployment command: ${required_command}" >&2
    exit 2
  fi
done

repo_root="$(git rev-parse --show-toplevel)"
if [[ -n "$(git -C "${repo_root}" status --porcelain)" ]]; then
  echo "ERROR: commit or discard local changes before deployment" >&2
  exit 3
fi
commit_id="$(git -C "${repo_root}" rev-parse --verify HEAD)"
archive="/tmp/ivi-rpi-${commit_id}.tar.gz"
checksum="${archive}.sha256"
remote_root="/tmp/ivi-rpi-${commit_id}"

cleanup() {
  rm -f "${archive}" "${checksum}"
}
trap cleanup EXIT

git -C "${repo_root}" archive --format=tar.gz \
  --prefix=Capstone-proj/ --output="${archive}" HEAD
(cd /tmp && shasum -a 256 "$(basename "${archive}")" >"$(basename "${checksum}")")

ssh "${target}" "mkdir -p ${remote_root}"
scp "${archive}" "${checksum}" "${target}:${remote_root}/"
ssh "${target}" \
  "cd ${remote_root} && sha256sum -c $(basename "${checksum}") && tar -xzf $(basename "${archive}")"

echo "PASS: commit ${commit_id} uploaded and verified at ${target}:${remote_root}/Capstone-proj"
echo "NEXT ON RPi:"
echo "  cd ${remote_root}/Capstone-proj"
echo "  sudo ./ivi_platform/scripts/install_rpi_dependencies.sh"
echo "  ./ivi_platform/scripts/build_rpi.sh"
echo "  sudo ./ivi_platform/scripts/install_rpi.sh"

#!/usr/bin/env bash
set -euo pipefail
mode=${1:-}
case "$mode" in knob|physical) ;; *) echo '사용법: bash ~/demo.sh knob 또는 bash ~/demo.sh physical'; exit 2;; esac
case "$(id -un)" in acorn1) role=ecu;; acorn2) role=ivi;; verus) role=keypad;; *) echo 'Pi의 기존 시연 계정에서 실행해줘'; exit 2;; esac
repo="$HOME/physical-pilot-20261118/capstone-physical-pilot"
echo 'CAN can0 준비 중...'
state=$(ip -details link show can0) || { echo 'can0 장치를 찾지 못했어'; exit 1; }
if ! grep -q 'can state ERROR-ACTIVE' <<<"$state" || ! grep -Eq 'bitrate 500000([[:space:]]|$)' <<<"$state"; then
  sudo ip link set can0 down
  sudo ip link set can0 type can bitrate 500000
  sudo ip link set can0 up
fi
if [[ $role == ecu ]]; then
  sudo ip link set dev can0 txqueuelen 100
fi
state=$(ip -details -statistics link show can0) || { echo 'can0 상태를 읽지 못했어'; exit 1; }
printf '%s\n' "$state"
grep -q 'can state ERROR-ACTIVE' <<<"$state" && grep -Eq 'bitrate 500000([[:space:]]|$)' <<<"$state" || { echo 'CAN 상태 확인 필요'; exit 1; }
echo 'CAN 준비 완료'
if [[ $role == keypad && $mode == knob ]]; then
  test -r "$HOME/knob-input.py"
  /usr/bin/python3 -c 'import glob,evdev; from contextlib import closing; p=glob.glob("/dev/input/by-id/usb-1189_USB_Composite_Device_*-event-kbd"); assert len(p)==1,"키패드 연결 확인"; closing(evdev.InputDevice(p[0])).__exit__(None,None,None)'
  echo '키패드 읽기 확인. ECU가 SSH로 노브 리더를 실행해.'
  exit 0
fi
if [[ $role == keypad ]]; then
  if [[ $mode == physical ]]; then
    shopt -s nullglob
    keypads=(/dev/input/by-id/usb-1189_USB_Composite_Device_*-if01-event-kbd)
    [[ ${#keypads[@]} -eq 1 ]] || { echo '키패드 연결을 확인해줘'; exit 1; }
    keypad=${keypads[0]}
    controller="$HOME/capstone-keypad.py"
    worker="$HOME/capstone-attacker-config.pyz"
    log_root="$HOME/Capstone-attacker/keypad-logs"
    [[ -r $controller && -r $worker ]] || { echo '공격 컨트롤러 또는 worker 파일을 찾지 못했어'; exit 1; }
    if pgrep -f '[c]apstone-keypad.py' >/dev/null; then
      echo '기존 키패드 컨트롤러를 Ctrl+C로 종료한 뒤 다시 실행해줘'
      exit 1
    fi
    mkdir -p "$log_root"
    echo '공격 키패드 시작. LISTENING 다음 READY_FOR_KEY가 뜨면 입력 가능해.'
    exec sudo /usr/bin/python3 "$controller" \
      --device "$keypad" \
      --worker "$worker" \
      --out "$log_root" \
      --config 3 \
      --live \
      --i-am-on-a-test-bus
  fi
  echo 'CAN 준비 완료'
  exit 0
fi
cd "$repo"
if pgrep -x adaptive_ecu >/dev/null || pgrep -f '/ivi_(dashboard|dashb)(_experiment)?([[:space:]]|$)' >/dev/null; then echo '기존 시연을 Ctrl+C로 종료한 뒤 다시 실행해줘'; exit 1; fi
if [[ $mode == physical ]]; then
  exec bash run-config-node.sh "$role" 3 "PHYS-DEMO-$(date +%Y%m%d-%H%M%S)"
fi
policy=adaptive_ecu/data/session-v2-development.conf
if [[ $role == ecu ]]; then
  read -rp "Verus IP: " knob_ip
  /usr/bin/python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$knob_ip" 2>/dev/null || { echo 'IPv4 주소를 확인해줘'; exit 1; }
  ssh -o ConnectTimeout=5 -T "verus@$knob_ip" 'python3 ~/knob-input.py' | ./adaptive_ecu/build/adaptive_ecu --interface can0 --sensor-mode ads1115 --knob-stdin --secoc on --protocol session-v2 --session-policy "$policy" --key /etc/secoc/key.bin
else
  export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
  if [[ -z ${DISPLAY:-} && -z ${WAYLAND_DISPLAY:-} ]]; then
    if [[ -S "$XDG_RUNTIME_DIR/wayland-0" ]]; then export WAYLAND_DISPLAY=wayland-0; else export DISPLAY=:0; fi
  fi
  for bin in ivi_platform/build-handoff/ivi_dashboard_experiment ivi_platform/build-handoff/ivi_dashb_experiment; do
    if [[ -x $bin ]]; then exec "$bin" --interface can0 --protocol session-v2 --session-policy "$policy" --secoc-key /etc/ivi/secoc.key --run-id "KNOB-$(date +%Y%m%d-%H%M%S)"; fi
  done
  echo 'IVI build-handoff 실행 파일을 찾지 못했어'; exit 1
fi

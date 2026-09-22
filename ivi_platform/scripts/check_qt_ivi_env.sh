#!/usr/bin/env sh
set -u

failures=0

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        printf '[OK]   %-12s %s\n' "$1" "$(command -v "$1")"
    else
        printf '[MISS] %-12s %s\n' "$1" "$2"
        failures=$((failures + 1))
    fi
}

echo "IVI Qt Plan B environment"
check_command c++ "Install a C++17 compiler."
check_command cmake "Install CMake 3.22 or newer."

if command -v qt-cmake >/dev/null 2>&1 || command -v qmake6 >/dev/null 2>&1; then
    echo "[OK]   Qt 6 tools"
else
    echo "[MISS] Qt 6 tools   Install Qt 6 Core/Gui/Qml/Quick/QuickControls2 development packages."
    failures=$((failures + 1))
fi

if [ "$(uname -s)" = "Linux" ]; then
    check_command ip "Install iproute2."
    check_command candump "Install can-utils."
    check_command cansend "Install can-utils."
    if command -v ip >/dev/null 2>&1 && ip link show vcan0 >/dev/null 2>&1; then
        echo "[OK]   vcan0"
    else
        echo "[WARN] vcan0 is not configured; this does not block core unit tests."
    fi
else
    echo "[WARN] SocketCAN runtime checks require Linux; core tests can run on $(uname -s)."
fi

if [ "$failures" -eq 0 ]; then
    echo "PASS: required build tools are available"
else
    echo "FAIL: $failures required tool group(s) missing"
fi
exit "$failures"

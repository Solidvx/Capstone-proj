# RPi4 deployment assets

These files target Debian 13 arm64 with Qt 6.8 on Raspberry Pi 4 and install the Node B Qt dashboard under `/opt/ivi`.

Two display modes are available:

- `install_rpi.sh` installs `ivi-dashboard.service` for a dedicated EGLFS display. It owns the DRM output and cannot run alongside the desktop compositor.
- `install_rpi_desktop.sh <user>` installs an XDG autostart entry that opens the dashboard as a Wayland window in that user's desktop session. It disables the EGLFS dashboard service while keeping `ivi-can0.service` enabled.

The deployment also defines two system services:

- `ivi-can0.service`: brings `can0` up at 500 kbit/s with automatic bus-off restart.
- `ivi-dashboard.service`: starts the dashboard as the restricted `ivi` user after `can0` is ready.

`config.txt.fragment` matches the recorded 8 MHz MCP2515 module and GPIO25 interrupt. Check the crystal marking and wiring before appending it to `/boot/firmware/config.txt`; a 16 MHz module must use `oscillator=16000000`.

The installer never creates or downloads a SecOC key. Provision the team-agreed 32-byte key locally on the RPi with `provision_secoc_key.sh`, run `rpi_preflight.sh`, and enable the services only after the physical bus is connected.

Desktop mode adds the selected user to the `ivi` group and grants only `CAP_NET_RAW` to the installed dashboard binary. Log out and back in, or reboot, after the first desktop-mode installation so the new group membership takes effect.

## Current session and event policies

Both launch paths explicitly select `session-v2` and require a session policy plus an event-store policy. ECU and IVI must use compatible session settings. Installation copies `adaptive_ecu/data/session-v2-development.conf` to `/etc/ivi/session-v2.conf` only if absent. These are development timing/budget values, not measured production guarantees.

The system service reads `IVI_SESSION_POLICY` and `IVI_EVENT_POLICY` from `/etc/ivi/ivi-dashboard.env`. Its default private journal is `/var/lib/capstone-ivi/events`, owned by `ivi` with mode0700. The systemd write exception permits that directory only; a custom store path also needs a corresponding service write exception. Existing env/policy files and history are not overwritten. When upgrading an older install, merge the added fields from `ivi-dashboard.env.example`; preflight rejects missing policy paths instead of silently falling back to legacy mode.

The desktop installer creates `$HOME/.config/capstone-ivi/event-store.json` and `$HOME/.local/state/capstone-ivi/events` as the selected user, preserving existing files. Its launcher uses that policy by default, or `IVI_EVENT_POLICY` when explicitly set. `XDG_CONFIG_HOME` overrides the lookup directory; with a custom XDG directory, place the policy there or set the explicit path. Do not point the desktop app at the service user's private journal. The app checks directory ownership and reports unavailable storage; a running display is not proof of successful persistence.

Both policies initially use `event-store.development.json` limits. Review the retention/space limits before deployment. No key contents are copied into policies. The dedicated service has `TimeoutStopSec=5`. Desktop mode now runs the rebuilt dashboard through `supervise_dashboard.py` using Python3. The installer updates both the binary and helper; update them together.

The desktop owner forwards INT/TERM/HUP and gives teardown5seconds from the first stop request or private Qt quit notification. Repeated signals do not extend this deadline. On expiry it requests SIGKILL and waits up to1additional second to reap. Exit124 records a forced stop with uncommitted events unconfirmed; exit125 reports an unreaped child. Kernel-level uninterruptible I/O may prevent immediate process death; this is not a hard real-time guarantee. The owner does not start another dashboard automatically or delete journal evidence. A later explicit launch recovers the existing writer marker as a possible recording gap. Without the helper, direct binary execution has no external stop deadline.

Linux validation uses a test-only preload to stall the actual journal's fsync, verifies bounded teardown and the preserved writer marker, then relaunches without the fixture and checks the gap annotation. The interposer is neither linked into nor installed with the dashboard. Real disk/power-loss acceptance remains separate. The pending3second storage-delay UI policy is not implemented by this shutdown guard.

Repository validation covers shell syntax and systemd unit structure. Actual Pi installation, desktop login/startup and reboot acceptance remain separate; these scripts have not been run on the user's nodes during this change.

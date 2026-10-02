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

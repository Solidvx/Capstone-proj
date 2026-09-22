# RPi4 deployment assets

These files target Ubuntu 22.04 arm64 on Raspberry Pi 4, install the Node B Qt dashboard under `/opt/ivi`, and define two services:

- `ivi-can0.service`: brings `can0` up at 500 kbit/s with automatic bus-off restart.
- `ivi-dashboard.service`: starts the dashboard as the restricted `ivi` user after `can0` is ready.

`config.txt.fragment` matches the recorded 8 MHz MCP2515 module and GPIO25 interrupt. Check the crystal marking and wiring before appending it to `/boot/firmware/config.txt`; a 16 MHz module must use `oscillator=16000000`.

The installer never creates or downloads a SecOC key. Provision the team-agreed 32-byte key locally on the RPi with `provision_secoc_key.sh`, run `rpi_preflight.sh`, and enable the services only after the physical bus is connected.

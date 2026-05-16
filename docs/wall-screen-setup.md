# Raspberry Pi Wall Display Setup Guide

This guide explains how to set up a Raspberry Pi as a dedicated wall display for OpenFamHub.

## Hardware Requirements
- **Raspberry Pi**: Any model with HDMI output (Pi 3, 4, or 5 recommended).
- **MicroSD Card**: At least 16GB (Class 10 or better).
- **Power Supply**: Reliable power source for the Pi.
- **HDMI Cable**: To connect the Pi to your wall display.
- **Internet/LAN Connection**: For accessing the OpenFamHub server.

## Installation Steps

### 1. Install Raspberry Pi OS
- Use the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS (64-bit) Desktop** onto your MicroSD card.
- Complete the initial setup (WiFi, SSH, etc.) via the Imager or upon first boot.

### 2. Run the Setup Script
- Transfer the `setup-wall-pi.sh` script to your Pi (via SCP or USB drive).
- Open a terminal on the Pi and run:
  ```bash
  chmod +x setup-wall-pi.sh
  sudo ./setup-wall-pi.sh
  ```

### 3. Trust the Server Certificate (CRITICAL)
Since OpenFamHub uses local HTTPS (`https://openfamhub.local`), you must trust the Caddy certificate on the Pi to avoid "Your connection is not private" errors in Chromium.
- Follow the steps in [docs/cert-trust.md](./docs/cert-trust.md) to import the CA certificate into the Pi's trusted store.

### 4. Reboot and Verify
- Reboot your Raspberry Pi: `sudo reboot`.
- The system should automatically launch Chromium in kiosk mode, pointing to your wall display URL.

## Troubleshooting

| Issue | Possible Cause | Solution |
| :--- | :--- | :--- |
| **Chromium won't start** | Missing `chromium-browser` or incorrect autostart path. | Ensure `unclutter` and `chromium-browser` are installed. Check `/etc/xdg/autostart/homehub-kiosk.desktop`. |
| **Blank screen / No display** | Power management or HDMI issues. | Check if `xset` commands in autostart are working. Ensure the Pi is powered correctly. |
| **Certificate Error** | The browser is blocking the connection due to untrusted SSL. | Re-follow the [cert trust steps](./docs/cert-trust.md). |
| **Wall doesn't update** | Network issues or server downtime. | Ensure the Pi has a stable connection to `openfamhub.local`. |

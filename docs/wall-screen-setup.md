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
- Optionally pass the display's pairing link (see step 4) so it pairs itself on every boot:
  ```bash
  sudo ./setup-wall-pi.sh "https://openfamhub.vernonmyers.cloud/wall?token=..."
  ```
- Without an argument the kiosk opens `https://openfamhub.local/wall`.
- The script works on Raspberry Pi OS Bookworm (Wayland: labwc/Wayfire) and Bullseye (LXDE). It's safe to re-run, for example to change the URL.

### 3. Trust the Server Certificate (LAN mode only)
If OpenFamHub runs behind a reverse proxy with a real certificate (e.g. `https://openfamhub.vernonmyers.cloud`), skip this step.

In LAN mode (`https://openfamhub.local`, Caddy's internal CA), the Pi must trust Caddy's root certificate or Chromium shows "Your connection is not private".
- Follow the Raspberry Pi steps in [cert-trust.md](cert-trust.md).

### 4. Pair the Display
The wall doesn't use a family member's login. Instead, each display is paired once:
1. On a phone or computer, sign in as an admin and open **Admin › Wall displays**.
2. Enter a name (e.g. "Kitchen") and click **Create pairing link**. The link is shown only once.
3. Open that link on the Pi (or pass it to the setup script as above).

The display then stays signed in indefinitely (its cookie refreshes on every load). To cut a display off, click **Unpair** on the same page. A display that isn't paired shows the clock and a short "not paired" message instead of the login page.

### 5. Reboot and Verify
- Reboot your Raspberry Pi: `sudo reboot`.
- The system should automatically launch Chromium in kiosk mode, pointing to your wall display URL.

## Troubleshooting

| Issue | Possible Cause | Solution |
| :--- | :--- | :--- |
| **Chromium won't start** | Browser not installed or autostart file missing. | Re-run the setup script. Check `/etc/xdg/autostart/openfamhub-kiosk.desktop`. |
| **Blank screen / No display** | Power management or HDMI issues. | Check if `xset` commands in autostart are working. Ensure the Pi is powered correctly. |
| **Certificate Error** | The browser is blocking the connection due to untrusted SSL. | Re-follow the [cert trust steps](cert-trust.md). |
| **"This display isn't paired"** | Never paired, unpaired by an admin, or browser data cleared. | Create a new pairing link under Admin › Wall displays and open it on the Pi. |
| **Wall doesn't update** | Network issues or server downtime. | Ensure the Pi can reach the server, and that the proxy passes WebSockets (`/api/wall/ws`). Displays also refresh every 15 minutes. |

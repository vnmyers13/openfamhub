#!/bin/bash
#
# Turn a Raspberry Pi (Raspberry Pi OS Desktop) into an OpenFamHub wall display.
# Safe to re-run: every step replaces its own config instead of appending.
#
#   sudo ./setup-wall-pi.sh [pairing-or-wall-url]
#
# With a pairing link from Admin > Wall displays the display pairs itself on
# every boot (until it is unpaired). Default: https://openfamhub.local/wall
set -euo pipefail

WALL_URL="${1:-https://openfamhub.local/wall}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0 [url]" >&2
    exit 1
fi
if ! grep -qiE "raspbian|debian" /etc/os-release 2>/dev/null; then
    echo "Warning: this script targets Raspberry Pi OS; continuing anyway."
fi

echo "==> Installing the browser"
apt-get update -q
# Bookworm ships "chromium"; older releases ship "chromium-browser".
if apt-cache show chromium >/dev/null 2>&1; then
    apt-get install -y -q chromium
    BROWSER=chromium
else
    apt-get install -y -q chromium-browser
    BROWSER=chromium-browser
fi
apt-get install -y -q unclutter || true   # hides the mouse pointer on X11 desktops

echo "==> Turning off screen blanking"
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_blanking 1 || true    # works on X11 and Wayland (Bookworm)
fi
# Older LXDE (X11) desktops: also disable DPMS in the session autostart.
LXDE_AUTOSTART="/etc/xdg/lxsession/LXDE-pi/autostart"
if [ -f "$LXDE_AUTOSTART" ]; then
    for line in "@xset s off" "@xset -dpms" "@xset s noblank" "@unclutter -idle 0.5 -root"; do
        grep -qxF "$line" "$LXDE_AUTOSTART" || echo "$line" >> "$LXDE_AUTOSTART"
    done
fi

echo "==> Configuring kiosk autostart"
# XDG autostart is honoured by LXDE (Bullseye) and by labwc/wayfire on
# Bookworm (they run lxsession-xdg-autostart), so one .desktop file covers all.
mkdir -p /etc/xdg/autostart
rm -f /etc/xdg/autostart/homehub-kiosk.desktop   # pre-0.30 name
cat > /etc/xdg/autostart/openfamhub-kiosk.desktop <<EOF
[Desktop Entry]
Type=Application
Name=OpenFamHub Kiosk
Exec=$BROWSER --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --ozone-platform-hint=auto --touch-events=enabled --disable-pinch --overscroll-history-navigation=0 --check-for-update-interval=31536000 $WALL_URL
X-GNOME-Autostart-enabled=true
EOF

cat <<EOF
------------------------------------------------------------
Done. The display opens: $WALL_URL
Next:
 1. LAN (openfamhub.local) installs only: trust the server certificate
    (docs/cert-trust.md). Not needed behind a proxy with a real certificate.
 2. If you didn't pass a pairing link, open one on this screen once
    (Admin > Wall displays).
 3. Reboot: sudo reboot
------------------------------------------------------------
EOF

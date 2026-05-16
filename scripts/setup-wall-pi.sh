#!/bin/bash

# Check if running on Raspberry Pi OS (Debian-based)
if [ ! -f /etc/os-release ]; then
    echo "Error: This script must be run on a Debian-based system like Raspberry Pi OS."
    exit 1
fi

if ! grep -qE "raspbian|debian" /etc/os-release; then
    echo "Warning: This script is intended for Raspberry Pi OS. Proceeding anyway..."
fi

echo "Starting OpenFamHub Kiosk Setup..."

# 1. Update and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y chromium-browser unclutter

# 2. Configure LXDE Autostart
# Note: This path is specific to Raspberry Pi OS Desktop (LXDE)
AUTOSTART_FILE="/etc/xdg/lxsession/LXDE-pi/autostart"

if [ -f "$AUTOSTART_FILE" ]; then
    echo "Configuring LXDE autostart..."
    # Disable screensaver and power management
    echo "@xset s off" | sudo tee -a "$AUTOSTART_FILE" > /dev/null
    echo "@xset -dpms" | sudo tee -a "$AUTOSTART_FILE" > /dev/null
    echo "@xset s noblank" | sudo tee -a "$AUTOSTART_FILE" > /dev/null
    echo "@unclutter -idle 0.5 -root" | sudo tee -a "$AUTOSTART_FILE" > /dev/null
else
    echo "Warning: Could not find LXDE autostart file at $AUTOSTART_FILE. Manual configuration might be required."
fi

# 3. Create Kiosk Desktop Entry
# This ensures Chromium launches in kiosk mode on boot via the desktop environment.
KIOSK_DIR="/etc/xdg/autostart"
sudo mkdir -p "$KIOSK_DIR"

cat <<EOF | sudo tee "$KIOSK_DIR/homehub-kiosk.desktop" > /dev/null
[Desktop Entry]
Type=Application
Name=OpenFamHub Kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --touch-events=enabled --disable-pinch --overscroll-history-navigation=0 https://openfamhub.local/wall
ExecRetry=3
X-GNOME-Autostart-enabled=true
EOF

echo "------------------------------------------------------------"
echo "Setup Complete!"
echo "------------------------------------------------------------"
echo "Next Steps:"
echo "1. Trust the server certificate on your Pi: see docs/cert-trust.md"
echo "2. Reboot the Raspberry Pi."
echo "3. The wall display should launch automatically in kiosk mode."
echo "------------------------------------------------------------"

#!/bin/bash

# Modem Connection Rotator Setup Script
# Run this script on your Raspberry Pi to install and configure the service

set -e

echo "Setting up Modem Connection Rotator Service..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "Please don't run this script as root. It will use sudo when needed."
   exit 1
fi

# Create directory (use current user's home)
INSTALL_DIR="$HOME/rotator"
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying service files..."
cp rotator.py "$INSTALL_DIR/"
cp config.json "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/rotator.py"

# Install systemd service
echo "Installing systemd service..."
# Create service file with current user and path
sed -e "s|USER_PLACEHOLDER|$CURRENT_USER|g" \
    -e "s|INSTALL_DIR_PLACEHOLDER|$INSTALL_DIR|g" \
    rotator.service > /tmp/rotator.service
sudo cp /tmp/rotator.service /etc/systemd/system/
rm /tmp/rotator.service
sudo systemctl daemon-reload

# Add user to sudoers for network commands (if not already there)
CURRENT_USER=$(whoami)
echo "Configuring sudo permissions for network commands for user: $CURRENT_USER"
if ! sudo grep -q "$CURRENT_USER.*NOPASSWD.*ip\|nmcli\|dhclient\|killall" /etc/sudoers; then
    echo "$CURRENT_USER ALL=(ALL) NOPASSWD: /sbin/ip, /usr/bin/nmcli, /sbin/dhclient, /usr/bin/killall" | sudo tee -a /etc/sudoers
fi

# Enable and start service
echo "Enabling and starting service..."
sudo systemctl enable rotator.service
sudo systemctl start rotator.service

# Check status
echo "Service status:"
sudo systemctl status rotator.service --no-pager

echo ""
echo "Setup complete!"
echo ""
echo "Service is running on port 8080"
echo "Test with:"
echo "  curl http://localhost:8080/status"
echo "  curl -X POST http://localhost:8080/rotate"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u rotator.service -f"
echo ""
echo "To stop/start/restart:"
echo "  sudo systemctl stop rotator.service"
echo "  sudo systemctl start rotator.service"
echo "  sudo systemctl restart rotator.service"
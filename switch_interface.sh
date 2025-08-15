#!/bin/bash

# Script to easily switch between different network interfaces for testing

if [ $# -eq 0 ]; then
    echo "Usage: $0 <interface_name>"
    echo ""
    echo "Available interfaces on your system:"
    ip link show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d ' ' | while read iface; do
        if [ "$iface" != "lo" ]; then
            status=$(ip addr show "$iface" | grep "inet " | awk '{print $2}' | head -1)
            if [ ! -z "$status" ]; then
                echo "  $iface - IP: $status"
            else
                echo "  $iface - No IP"
            fi
        fi
    done
    echo ""
    echo "Current config.json interface:"
    grep '"interface"' /home/node2/rotator/config.json 2>/dev/null || echo "  config.json not found"
    echo ""
    echo "Examples:"
    echo "  $0 wwan0    # Switch to cellular modem"
    echo "  $0 eth0     # Switch to ethernet"
    echo "  $0 ppp0     # Switch to PPP connection"
    exit 1
fi

NEW_INTERFACE=$1
CONFIG_FILE="/home/node2/rotator/config.json"

# Check if interface exists
if ! ip link show "$NEW_INTERFACE" >/dev/null 2>&1; then
    echo "❌ Error: Interface '$NEW_INTERFACE' not found!"
    echo ""
    echo "Available interfaces:"
    ip link show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d ' '
    exit 1
fi

echo "🔄 Switching rotator service to interface: $NEW_INTERFACE"
echo ""

# Show current interface
echo "Current configuration:"
grep '"interface"' "$CONFIG_FILE" 2>/dev/null || echo "  config.json not found"

# Update config.json
if [ -f "$CONFIG_FILE" ]; then
    # Backup original
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
    
    # Update interface
    sed -i "s/\"interface\": \"[^\"]*\"/\"interface\": \"$NEW_INTERFACE\"/" "$CONFIG_FILE"
    
    echo ""
    echo "Updated configuration:"
    grep '"interface"' "$CONFIG_FILE"
    
    echo ""
    echo "🔄 Restarting rotator service..."
    sudo systemctl restart rotator.service
    
    echo ""
    echo "⏳ Waiting for service to start..."
    sleep 3
    
    echo ""
    echo "📊 Service status:"
    sudo systemctl status rotator.service --no-pager -l | head -10
    
    echo ""
    echo "🧪 Testing new interface:"
    echo "========================="
    
    # Test status endpoint
    echo "Checking connection status..."
    curl -s "http://localhost:8080/status" | python3 -m json.tool 2>/dev/null || echo "❌ Service not responding"
    
    echo ""
    echo "✅ Interface switched to $NEW_INTERFACE"
    echo ""
    echo "To test rotation:"
    echo "  curl -X POST http://localhost:8080/rotate"
    echo ""
    echo "To switch back to previous interface:"
    echo "  cp $CONFIG_FILE.backup $CONFIG_FILE"
    echo "  sudo systemctl restart rotator.service"
    
else
    echo "❌ Config file not found at $CONFIG_FILE"
    echo "Make sure the rotator service is installed properly."
fi
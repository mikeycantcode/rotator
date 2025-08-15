#!/bin/bash

# Test Interface Script - manually test disconnecting/reconnecting an interface

if [ $# -eq 0 ]; then
    echo "Usage: $0 <interface_name>"
    echo ""
    echo "This script will test disconnecting and reconnecting a specific interface"
    echo "to see if it affects your internet connection."
    echo ""
    echo "Run './check_interfaces.sh' first to see available interfaces"
    echo ""
    echo "Example: $0 wwan0"
    exit 1
fi

INTERFACE=$1

echo "=== TESTING INTERFACE: $INTERFACE ==="
echo ""

# Check if interface exists
if ! ip link show "$INTERFACE" >/dev/null 2>&1; then
    echo "❌ Error: Interface '$INTERFACE' not found!"
    echo ""
    echo "Available interfaces:"
    ip link show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d ' '
    exit 1
fi

echo "✓ Interface '$INTERFACE' found"
echo ""

# Get initial status
echo "1. INITIAL STATUS:"
echo "=================="
initial_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
echo "Current public IP: $initial_ip"
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "Internet: ✓ Working"
else
    echo "Internet: ❌ Not working"
fi
echo ""

# Show interface status
echo "Interface status:"
ip addr show "$INTERFACE" | grep -E "(inet |state )" || echo "No IP assigned"
echo ""

echo "2. DISCONNECTING INTERFACE:"
echo "============================"
echo "Bringing down $INTERFACE..."

# Try different disconnect methods
if command -v nmcli >/dev/null; then
    echo "Trying NetworkManager disconnect..."
    sudo nmcli device disconnect "$INTERFACE" 2>/dev/null && echo "✓ NetworkManager disconnect successful" || echo "⚠ NetworkManager disconnect failed"
fi

echo "Trying direct interface down..."
sudo ip link set "$INTERFACE" down 2>/dev/null && echo "✓ Interface down successful" || echo "⚠ Interface down failed"

echo ""
echo "Waiting 3 seconds..."
sleep 3

echo "3. STATUS AFTER DISCONNECT:"
echo "============================"
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "Internet: ✓ Still working (this interface might not be your main connection)"
    after_disconnect_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    echo "Public IP: $after_disconnect_ip"
else
    echo "Internet: ❌ Disconnected (this IS your main internet interface!)"
fi

# Show interface status
echo "Interface status:"
ip addr show "$INTERFACE" | grep -E "(inet |state )" || echo "Interface is down"
echo ""

echo "4. RECONNECTING INTERFACE:"
echo "=========================="
echo "Bringing up $INTERFACE..."

# Bring interface back up
sudo ip link set "$INTERFACE" up 2>/dev/null && echo "✓ Interface up successful" || echo "⚠ Interface up failed"

if command -v nmcli >/dev/null; then
    echo "Trying NetworkManager connect..."
    sudo nmcli device connect "$INTERFACE" 2>/dev/null && echo "✓ NetworkManager connect successful" || echo "⚠ NetworkManager connect failed"
fi

# Try to get DHCP
echo "Attempting DHCP..."
sudo dhclient "$INTERFACE" 2>/dev/null && echo "✓ DHCP successful" || echo "⚠ DHCP failed"

echo ""
echo "Waiting 10 seconds for connection to establish..."
sleep 10

echo "5. FINAL STATUS:"
echo "================"
final_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
echo "Public IP: $final_ip"

if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "Internet: ✓ Working"
    
    if [ "$initial_ip" != "$final_ip" ] && [ "$final_ip" != "unknown" ]; then
        echo ""
        echo "🎉 SUCCESS! IP changed from $initial_ip to $final_ip"
        echo "✅ Interface '$INTERFACE' is your modem interface!"
        echo ""
        echo "Update your config.json:"
        echo '{'
        echo '  "port": 8080,'
        echo "  \"interface\": \"$INTERFACE\","
        echo '  "disconnect_delay": 5,'
        echo '  "reconnect_timeout": 30,'
        echo '  "log_level": "INFO"'
        echo '}'
    else
        echo ""
        echo "⚠ IP didn't change. This might not be your modem interface."
    fi
else
    echo "Internet: ❌ Still not working after reconnect"
    echo ""
    echo "❌ There might be an issue with reconnecting this interface."
fi

echo ""
echo "Interface final status:"
ip addr show "$INTERFACE" | grep -E "(inet |state )" || echo "No IP assigned"
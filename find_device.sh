#!/bin/bash

echo "=== FINDING CORRECT DEVICE NAME ==="
echo ""

echo "1. NetworkManager devices:"
nmcli device status
echo ""

echo "2. Network interfaces (ip):"
ip link show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d ' '
echo ""

echo "3. Looking for cellular/modem devices in NetworkManager:"
nmcli device status | grep -E "(gsm|wwan|cellular|modem|lte)"
echo ""

echo "4. All NetworkManager connections:"
nmcli connection show
echo ""

echo "5. Active connections:"
nmcli connection show --active
echo ""

echo "6. Current wwan0 IP interface:"
ip addr show wwan0 2>/dev/null || echo "wwan0 not found via ip command"
echo ""

echo "7. Suggestion:"
echo "NetworkManager device name might be different from interface name."
echo "Look for the device with your current IP (10.2.79.44) in the list above."
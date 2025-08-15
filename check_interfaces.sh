#!/bin/bash

echo "=== NETWORK INTERFACE DETECTIVE ==="
echo ""

echo "1. ALL NETWORK INTERFACES:"
echo "=========================="
ip link show | grep -E "^[0-9]+:" | while read line; do
    interface=$(echo "$line" | cut -d: -f2 | tr -d ' ')
    state=$(echo "$line" | grep -o "state [A-Z]*" | cut -d' ' -f2)
    echo "  $interface - $state"
done
echo ""

echo "2. INTERFACES WITH IP ADDRESSES:"
echo "==============================="
ip addr show | grep -E "inet " | grep -v "127.0.0.1" | while read line; do
    ip=$(echo "$line" | awk '{print $2}')
    interface=$(ip route get 8.8.8.8 2>/dev/null | grep -o "dev [^ ]*" | cut -d' ' -f2 2>/dev/null || echo "unknown")
    echo "  IP: $ip"
done
echo ""

echo "3. COMMON MODEM INTERFACE PATTERNS:"
echo "==================================="
ip link show | grep -E "(wwan|ppp|usb|eth)" | while read line; do
    interface=$(echo "$line" | cut -d: -f2 | tr -d ' ')
    echo "  Found potential modem interface: $interface"
done
echo ""

echo "4. USB DEVICES (looking for modems):"
echo "===================================="
if command -v lsusb >/dev/null; then
    lsusb | grep -iE "(modem|cellular|sierra|huawei|zte|qualcomm|broadcom)" || echo "  No obvious modem devices found in lsusb"
else
    echo "  lsusb not available"
fi
echo ""

echo "5. NETWORK MANAGER STATUS:"
echo "=========================="
if command -v nmcli >/dev/null; then
    nmcli device status | head -10
else
    echo "  NetworkManager (nmcli) not available"
fi
echo ""

echo "6. CURRENT DEFAULT ROUTE:"
echo "========================="
ip route show default | head -5
echo ""

echo "7. ACTIVE CONNECTIONS (netstat style):"
echo "======================================"
if command -v ss >/dev/null; then
    ss -tuln | grep ":80\|:443\|:53" | head -5
else
    echo "  ss command not available"
fi
echo ""

echo "8. CHECKING CURRENT INTERNET CONNECTION:"
echo "========================================"
echo "Testing connectivity..."
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "  ✓ Internet is working"
    current_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    echo "  Current public IP: $current_ip"
    
    # Try to identify which interface is being used
    route_interface=$(ip route get 8.8.8.8 2>/dev/null | grep -o "dev [^ ]*" | cut -d' ' -f2)
    if [ ! -z "$route_interface" ]; then
        echo "  Traffic going through interface: $route_interface"
        echo ""
        echo "*** RECOMMENDATION: Use interface '$route_interface' in config.json ***"
    fi
else
    echo "  ✗ No internet connection detected"
fi
echo ""

echo "9. SUGGESTED CONFIG.JSON UPDATE:"
echo "==============================="
route_interface=$(ip route get 8.8.8.8 2>/dev/null | grep -o "dev [^ ]*" | cut -d' ' -f2 2>/dev/null)
if [ ! -z "$route_interface" ]; then
    echo "Based on current routing, update your config.json:"
    echo ""
    echo '{'
    echo '  "port": 8080,'
    echo "  \"interface\": \"$route_interface\","
    echo '  "disconnect_delay": 5,'
    echo '  "reconnect_timeout": 30,'
    echo '  "log_level": "INFO"'
    echo '}'
else
    echo "Could not determine active interface automatically."
    echo "Common modem interfaces to try:"
    echo "  - wwan0 (USB cellular modems)"
    echo "  - ppp0 (dial-up connections)"
    echo "  - usb0 (USB tethering)"
    echo "  - eth1 (some USB ethernet adapters)"
fi
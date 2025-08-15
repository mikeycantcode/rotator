#!/bin/bash

# Debug script to check what's happening with the connection

echo "=== CONNECTION DEBUG TOOL ==="
echo ""

echo "1. CURRENT INTERFACE STATUS:"
echo "============================"
ip addr show wwan0 2>/dev/null || echo "wwan0 interface not found"
echo ""

echo "2. CURRENT ROUTES:"
echo "=================="
ip route show | head -10
echo ""

echo "3. MODEM MANAGER STATUS:"
echo "========================"
if command -v mmcli >/dev/null; then
    echo "ModemManager available - checking modems:"
    mmcli -L 2>/dev/null || echo "No modems found or ModemManager not running"
    echo ""
    
    # Try to get modem 0 status
    echo "Modem 0 details:"
    mmcli -m 0 2>/dev/null || echo "Cannot access modem 0"
    echo ""
else
    echo "ModemManager (mmcli) not available"
fi
echo ""

echo "4. NETWORK MANAGER STATUS:"
echo "=========================="
if command -v nmcli >/dev/null; then
    echo "NetworkManager available - device status:"
    nmcli device status
    echo ""
    
    echo "Connection details:"
    nmcli connection show --active | head -5
    echo ""
else
    echo "NetworkManager (nmcli) not available"
fi
echo ""

echo "5. PROCESS CHECK:"
echo "================="
echo "DHCP processes:"
ps aux | grep dhclient | grep -v grep || echo "No dhclient processes"
echo ""

echo "PPP processes:"
ps aux | grep -E "(ppp|wvdial)" | grep -v grep || echo "No PPP processes"
echo ""

echo "6. SYSTEM LOGS (last 20 network related):"
echo "=========================================="
journalctl -n 20 | grep -iE "(network|wwan|modem|dhcp)" || echo "No recent network logs"
echo ""

echo "7. INTERNET CONNECTIVITY TEST:"
echo "==============================="
echo "Ping test:"
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ Internet connectivity: WORKING"
    
    echo ""
    echo "Public IP check:"
    public_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    echo "Current public IP: $public_ip"
else
    echo "❌ Internet connectivity: NOT WORKING"
fi
echo ""

echo "8. SUGGESTED MANUAL RECOVERY:"
echo "============================="
echo "If wwan0 is down, try these commands manually:"
echo ""
echo "# Bring interface up:"
echo "sudo ip link set wwan0 up"
echo ""
echo "# Try ModemManager connect:"
echo "mmcli -m 0 --simple-connect"
echo ""
echo "# Try NetworkManager connect:"
echo "nmcli device connect wwan0"
echo ""
echo "# Check if interface gets IP:"
echo "ip addr show wwan0"
echo ""
echo "# Force DHCP (usually doesn't work for cellular, but worth trying):"
echo "sudo dhclient wwan0"
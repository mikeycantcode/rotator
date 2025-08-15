#!/bin/bash

# Manual recovery script to get wwan0 back online

echo "=== MANUAL CONNECTION RECOVERY ==="
echo ""

INTERFACE="wwan0"

echo "1. CHECKING CURRENT STATUS:"
echo "==========================="
echo "Interface status:"
ip addr show $INTERFACE 2>/dev/null | grep -E "(state |inet )" || echo "Interface not found or no IP"
echo ""

echo "Internet test:"
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ Internet is working - no recovery needed!"
    exit 0
else
    echo "❌ No internet - starting recovery..."
fi
echo ""

echo "2. STEP-BY-STEP RECOVERY:"
echo "========================="

echo "Step 1: Bringing interface up..."
sudo ip link set $INTERFACE up
if [ $? -eq 0 ]; then
    echo "✅ Interface up successful"
else
    echo "❌ Interface up failed"
fi
sleep 2
echo ""

echo "Step 2: Checking if interface got IP automatically..."
ip_check=$(ip addr show $INTERFACE | grep "inet " | grep -v "127.0.0.1")
if [ ! -z "$ip_check" ]; then
    echo "✅ Interface has IP: $ip_check"
else
    echo "⚠️ No IP yet, trying additional methods..."
    
    echo ""
    echo "Step 3: Trying ModemManager..."
    if command -v mmcli >/dev/null; then
        echo "Enabling modem..."
        mmcli -m 0 --enable 2>/dev/null && echo "✅ Modem enabled" || echo "❌ Modem enable failed"
        sleep 3
        
        echo "Connecting modem..."
        mmcli -m 0 --simple-connect 2>/dev/null && echo "✅ Modem connected" || echo "❌ Modem connect failed"
        sleep 5
    else
        echo "ModemManager not available"
    fi
    
    echo ""
    echo "Step 4: Trying NetworkManager..."
    if command -v nmcli >/dev/null; then
        nmcli device connect $INTERFACE 2>/dev/null && echo "✅ NetworkManager connected" || echo "❌ NetworkManager failed"
        sleep 5
    else
        echo "NetworkManager not available"
    fi
fi
echo ""

echo "3. FINAL STATUS CHECK:"
echo "======================"
sleep 3

echo "Interface status:"
ip addr show $INTERFACE | grep -E "(state |inet )" || echo "No IP assigned"
echo ""

echo "Route check:"
ip route show | grep $INTERFACE || echo "No routes via $INTERFACE"
echo ""

echo "Internet test:"
if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ RECOVERY SUCCESSFUL!"
    
    new_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    echo "Current public IP: $new_ip"
    
    echo ""
    echo "✅ Connection is now working. You can:"
    echo "  - Test the rotator: curl -X POST http://localhost:8080/rotate"
    echo "  - Check status: curl http://localhost:8080/status"
else
    echo "❌ RECOVERY FAILED"
    echo ""
    echo "Additional troubleshooting:"
    echo "1. Check if modem is physically connected: lsusb | grep -i modem"
    echo "2. Check system logs: journalctl -f | grep -i modem"
    echo "3. Restart ModemManager: sudo systemctl restart ModemManager"
    echo "4. Restart NetworkManager: sudo systemctl restart NetworkManager"
    echo ""
    echo "Manual commands to try:"
    echo "  sudo systemctl status ModemManager"
    echo "  mmcli -L"
    echo "  nmcli device status"
fi
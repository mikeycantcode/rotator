#!/bin/bash

echo "=== QUICK NMCLI DEBUG ==="
echo ""

echo "1. NetworkManager status:"
systemctl status NetworkManager --no-pager -l | head -5
echo ""

echo "2. nmcli device status:"
nmcli device status
echo ""

echo "3. Test disconnect manually:"
echo "Running: nmcli device disconnect wwan0"
nmcli device disconnect wwan0
echo "Exit code: $?"
echo ""

echo "4. Check wwan0 status after disconnect:"
nmcli device status | grep wwan0
ip addr show wwan0 | grep "inet "
echo ""

echo "5. Test connect manually:"
echo "Running: nmcli device connect wwan0"
nmcli device connect wwan0
echo "Exit code: $?"
echo ""

echo "6. Final status:"
nmcli device status | grep wwan0
ip addr show wwan0 | grep "inet "
echo ""

echo "7. Check rotator service logs:"
sudo journalctl -u rotator.service -n 10 --no-pager
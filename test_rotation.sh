#!/bin/bash

# Test script to verify the rotation service is working
# Usage: ./test_rotation.sh [PI_IP_ADDRESS]

PI_IP=${1:-"localhost"}
PORT=8080

echo "=== TESTING MODEM ROTATOR SERVICE ==="
echo "Target: $PI_IP:$PORT"
echo ""

# Test 1: Service Info
echo "1. TESTING SERVICE INFO:"
echo "========================"
curl -s "http://$PI_IP:$PORT/" | python3 -m json.tool 2>/dev/null || echo "❌ Service not responding"
echo ""

# Test 2: Health Check
echo "2. TESTING HEALTH CHECK:"
echo "========================"
curl -s "http://$PI_IP:$PORT/health" | python3 -m json.tool 2>/dev/null || echo "❌ Health check failed"
echo ""

# Test 3: Initial Status
echo "3. INITIAL CONNECTION STATUS:"
echo "============================="
initial_status=$(curl -s "http://$PI_IP:$PORT/status")
echo "$initial_status" | python3 -m json.tool 2>/dev/null || echo "❌ Status check failed"

# Extract initial IP
initial_ip=$(echo "$initial_status" | grep -o '"ip_address": "[^"]*"' | cut -d'"' -f4)
echo ""
echo "Current IP: $initial_ip"
echo ""

# Test 4: Connection Rotation
echo "4. PERFORMING CONNECTION ROTATION:"
echo "=================================="
echo "Sending rotation request..."
rotation_result=$(curl -s "http://$PI_IP:$PORT/rotate" -X POST)
echo "$rotation_result" | python3 -m json.tool 2>/dev/null || echo "❌ Rotation failed"

# Check if rotation was successful
success=$(echo "$rotation_result" | grep -o '"success": [^,]*' | cut -d' ' -f2)
if [ "$success" = "true" ]; then
    echo ""
    echo "✅ Rotation request completed successfully"
    
    # Extract new IP
    new_ip=$(echo "$rotation_result" | grep -o '"ip_address": "[^"]*"' | tail -1 | cut -d'"' -f4)
    
    if [ "$initial_ip" != "$new_ip" ] && [ "$new_ip" != "null" ] && [ ! -z "$new_ip" ]; then
        echo "🎉 IP CHANGED: $initial_ip → $new_ip"
        echo "✅ ROTATION SUCCESSFUL!"
    else
        echo "⚠️  IP didn't change. Check logs for details."
    fi
else
    echo ""
    echo "❌ Rotation failed. Check the response above for details."
fi

echo ""

# Test 5: Final Status Check
echo "5. FINAL STATUS CHECK:"
echo "======================"
sleep 2
final_status=$(curl -s "http://$PI_IP:$PORT/status")
echo "$final_status" | python3 -m json.tool 2>/dev/null || echo "❌ Final status check failed"

echo ""
echo "=== TEST COMPLETE ==="

# Summary
final_ip=$(echo "$final_status" | grep -o '"ip_address": "[^"]*"' | cut -d'"' -f4)
internet_connected=$(echo "$final_status" | grep -o '"internet_connected": [^,]*' | cut -d' ' -f2)

echo ""
echo "SUMMARY:"
echo "========="
echo "Initial IP:     $initial_ip"
echo "Final IP:       $final_ip"
echo "Internet:       $internet_connected"

if [ "$internet_connected" = "true" ]; then
    echo "Status:         ✅ Connected"
else
    echo "Status:         ❌ Disconnected"
fi

if [ "$initial_ip" != "$final_ip" ] && [ "$final_ip" != "null" ] && [ ! -z "$final_ip" ]; then
    echo "IP Change:      ✅ Success"
else
    echo "IP Change:      ❌ No change detected"
fi
# Modem Connection Rotator

A simple HTTP service for Raspberry Pi that allows you to rotate modem connections via REST API calls.

## Features

- **HTTP API**: Simple REST endpoints to control modem connections
- **Connection Status**: Real-time monitoring of connection state
- **Automatic Rotation**: Disconnect and reconnect modem with configurable delays
- **Multiple Methods**: Supports NetworkManager, direct interface control, and dial-up processes
- **Logging**: Comprehensive logging to file and console
- **Systemd Integration**: Runs as a system service with auto-restart

## Quick Start

1. **Transfer files to your Raspberry Pi:**
   ```bash
   scp -r * pi@your-pi-ip:/home/pi/rotator/
   ```

2. **Run setup script on Pi:**
   ```bash
   cd /home/pi/rotator
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Test the service:**
   ```bash
   # Check connection status
   curl http://localhost:8080/status
   
   # Rotate connection
   curl -X POST http://localhost:8080/rotate
   ```

## API Endpoints

### GET /
Service information and available endpoints

### GET /status
Returns current connection status:
```json
{
  "interface": "wwan0",
  "interface_up": true,
  "ip_address": "192.168.1.100",
  "internet_connected": true,
  "last_rotation": "2024-01-01T12:00:00",
  "rotation_count": 5
}
```

### GET /health
Simple health check endpoint

### POST /rotate
Rotates the modem connection (disconnect + reconnect):
```json
{
  "success": true,
  "message": "Connection rotated successfully",
  "initial_status": {...},
  "final_status": {...},
  "rotation_time": "2024-01-01T12:05:00",
  "total_rotations": 6
}
```

## Configuration

Edit `config.json` to customize settings:

```json
{
  "port": 8080,
  "interface": "wwan0",
  "disconnect_delay": 5,
  "reconnect_timeout": 30,
  "log_level": "INFO"
}
```

- **port**: HTTP server port
- **interface**: Network interface name (common: `wwan0`, `ppp0`, `usb0`)
- **disconnect_delay**: Seconds to wait between disconnect and reconnect
- **reconnect_timeout**: Maximum seconds to wait for reconnection
- **log_level**: Logging level (DEBUG, INFO, WARNING, ERROR)

## Finding Your Interface

To find your modem's interface name:

```bash
# List all network interfaces
ip link show

# Check for cellular/modem interfaces
ip link show | grep -E "(wwan|ppp|usb)"

# Check NetworkManager devices
nmcli device status
```

Common interface names:
- `wwan0` - USB cellular modems
- `ppp0` - Dial-up connections
- `usb0` - USB tethering
- `eth1` - Some USB ethernet adapters

## Service Management

```bash
# View service status
sudo systemctl status rotator.service

# Start/stop/restart
sudo systemctl start rotator.service
sudo systemctl stop rotator.service
sudo systemctl restart rotator.service

# View logs
sudo journalctl -u rotator.service -f

# Disable auto-start
sudo systemctl disable rotator.service
```

## Remote Usage

To access from other devices on your network:

1. **Find Pi's IP address:**
   ```bash
   ip addr show | grep inet
   ```

2. **Test from remote device:**
   ```bash
   curl http://PI_IP_ADDRESS:8080/status
   curl -X POST http://PI_IP_ADDRESS:8080/rotate
   ```

3. **Open firewall if needed:**
   ```bash
   sudo ufw allow 8080
   ```

## Troubleshooting

### Permission Issues
The service needs sudo access for network commands. If you get permission errors:

```bash
# Check sudoers configuration
sudo visudo

# Should include something like:
pi ALL=(ALL) NOPASSWD: /sbin/ip, /usr/bin/nmcli, /sbin/dhclient, /usr/bin/killall
```

### Interface Not Found
If the service can't find your modem interface:

1. Check available interfaces: `ip link show`
2. Update `interface` in `config.json`
3. Restart service: `sudo systemctl restart rotator.service`

### Connection Issues
If rotation fails:

1. Check logs: `sudo journalctl -u rotator.service -n 50`
2. Test manually: `sudo nmcli device disconnect wwan0`
3. Verify modem is detected: `lsusb | grep -i modem`

### Service Won't Start
Check the logs for errors:

```bash
sudo journalctl -u rotator.service -n 20
```

Common issues:
- Python3 not installed: `sudo apt install python3`
- Port already in use: Change port in `config.json`
- File permissions: `chmod +x /home/pi/rotator/rotator.py`

## Examples

### Bash Script to Rotate and Wait
```bash
#!/bin/bash
echo "Rotating connection..."
curl -X POST http://localhost:8080/rotate
echo "Waiting for new IP..."
sleep 10
curl http://localhost:8080/status | grep ip_address
```

### Python Client
```python
import requests
import time

# Rotate connection
response = requests.post('http://PI_IP:8080/rotate')
if response.json()['success']:
    print("Connection rotated successfully")
    
    # Wait and check new status
    time.sleep(5)
    status = requests.get('http://PI_IP:8080/status').json()
    print(f"New IP: {status['ip_address']}")
```

### Cron Job for Periodic Rotation
```bash
# Add to crontab (crontab -e)
# Rotate every hour
0 * * * * curl -X POST http://localhost:8080/rotate >/dev/null 2>&1
```

## License

MIT License - feel free to modify and distribute.
#!/usr/bin/env python3
"""
Modem Connection Rotator Service
A simple HTTP service to rotate modem connections on Raspberry Pi
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock
from typing import Dict, Any
import os

# Configuration
CONFIG = {
    "port": 8080,
    "interface": "wwan0",  # Common interface for USB modems
    "disconnect_delay": 5,  # Seconds to wait before reconnecting
    "reconnect_timeout": 30,  # Max seconds to wait for reconnection
    "log_level": "INFO"
}

# Load config from file if it exists
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            user_config = json.load(f)
            CONFIG.update(user_config)
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")

# Setup logging
logging.basicConfig(
    level=getattr(logging, CONFIG["log_level"]),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rotator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ModemRotator:
    def __init__(self):
        self.lock = Lock()
        self.last_rotation = None
        self.rotation_count = 0
        
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        try:
            # Check if interface is up
            result = subprocess.run(
                ['ip', 'link', 'show', CONFIG["interface"]], 
                capture_output=True, text=True, timeout=10
            )
            interface_up = result.returncode == 0 and 'UP' in result.stdout
            
            # Get IP address if interface is up
            ip_address = None
            if interface_up:
                ip_result = subprocess.run(
                    ['ip', 'addr', 'show', CONFIG["interface"]], 
                    capture_output=True, text=True, timeout=10
                )
                if ip_result.returncode == 0:
                    lines = ip_result.stdout.split('\n')
                    for line in lines:
                        if 'inet ' in line and not 'inet 127.' in line:
                            ip_address = line.strip().split()[1].split('/')[0]
                            break
            
            # Test internet connectivity
            internet_connected = False
            try:
                ping_result = subprocess.run(
                    ['ping', '-c', '1', '-W', '3', '8.8.8.8'], 
                    capture_output=True, timeout=5
                )
                internet_connected = ping_result.returncode == 0
            except:
                pass
                
            return {
                "interface": CONFIG["interface"],
                "interface_up": interface_up,
                "ip_address": ip_address,
                "internet_connected": internet_connected,
                "last_rotation": self.last_rotation,
                "rotation_count": self.rotation_count
            }
        except Exception as e:
            logger.error(f"Error getting connection status: {e}")
            return {"error": str(e)}
    
    def disconnect_modem(self) -> bool:
        """Disconnect the modem using multiple methods for better IP rotation"""
        try:
            logger.info("Disconnecting modem...")
            disconnected = False
            
            # Method 1: ModemManager disconnect (most reliable for cellular)
            if CONFIG["interface"].startswith('wwan'):
                try:
                    # First try to disconnect via ModemManager
                    result = subprocess.run(
                        ['mmcli', '--modem=0', '--simple-disconnect'], 
                        capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        logger.info("Disconnected using ModemManager")
                        disconnected = True
                    else:
                        # Try to disable the modem entirely
                        result = subprocess.run(
                            ['mmcli', '--modem=0', '--disable'], 
                            capture_output=True, text=True, timeout=15
                        )
                        if result.returncode == 0:
                            logger.info("Disabled modem using ModemManager")
                            disconnected = True
                except FileNotFoundError:
                    logger.info("ModemManager not available")
                except Exception as e:
                    logger.info(f"ModemManager disconnect failed: {e}")
            
            # Method 2: NetworkManager disconnect
            if not disconnected:
                try:
                    result = subprocess.run(
                        ['nmcli', 'device', 'disconnect', CONFIG["interface"]], 
                        capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        logger.info("Disconnected using NetworkManager")
                        disconnected = True
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.info(f"NetworkManager disconnect failed: {e}")
            
            # Method 3: Physical interface down
            if not disconnected:
                result = subprocess.run(
                    ['sudo', 'ip', 'link', 'set', CONFIG["interface"], 'down'], 
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    logger.info("Interface brought down")
                    disconnected = True
            
            # Method 4: Kill related processes for more aggressive disconnect
            if disconnected:
                try:
                    subprocess.run(['sudo', 'killall', 'wvdial'], capture_output=True, timeout=5)
                    subprocess.run(['sudo', 'killall', 'pppd'], capture_output=True, timeout=5)
                    logger.info("Killed dial-up processes for clean disconnect")
                except:
                    pass
            
            if not disconnected:
                logger.warning("Could not disconnect modem using any method")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting modem: {e}")
            return False
    
    def connect_modem(self) -> bool:
        """Connect the modem"""
        try:
            logger.info("Connecting modem...")
            
            # Method 1: ModemManager enable/connect (for cellular)
            if CONFIG["interface"].startswith('wwan'):
                try:
                    # Enable modem first
                    result = subprocess.run(
                        ['mmcli', '--modem=0', '--enable'], 
                        capture_output=True, text=True, timeout=20
                    )
                    if result.returncode == 0:
                        logger.info("Enabled modem using ModemManager")
                        time.sleep(3)  # Wait for modem to initialize
                    
                    # Connect modem
                    result = subprocess.run(
                        ['mmcli', '--modem=0', '--simple-connect'], 
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        logger.info("Connected using ModemManager")
                        return True
                except FileNotFoundError:
                    logger.info("ModemManager not available")
                except Exception as e:
                    logger.info(f"ModemManager connect failed: {e}")
            
            # Method 2: Use NetworkManager if available
            try:
                result = subprocess.run(
                    ['nmcli', 'device', 'connect', CONFIG["interface"]], 
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    logger.info("Connected using NetworkManager")
                    return True
            except FileNotFoundError:
                pass
            
            # Method 2: Bring interface up
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', CONFIG["interface"], 'up'], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info("Interface brought up")
                
                # Handle different interface types
                if CONFIG["interface"].startswith('wwan'):
                    # Cellular modems: wait for automatic connection
                    logger.info("Waiting for cellular modem auto-connection...")
                    time.sleep(8)  # Give cellular modems more time
                    
                    # Try ModemManager if available
                    try:
                        result = subprocess.run(
                            ['mmcli', '--modem=0', '--simple-connect'], 
                            capture_output=True, text=True, timeout=20
                        )
                        if result.returncode == 0:
                            logger.info("Connected using ModemManager")
                    except FileNotFoundError:
                        logger.info("ModemManager not available, relying on auto-connection")
                    except:
                        logger.info("ModemManager connection attempt failed")
                        
                elif CONFIG["interface"].startswith('ppp'):
                    # PPP connections: usually managed by pppd/wvdial
                    logger.info("PPP interface detected, waiting for dial-up connection...")
                    time.sleep(5)
                    
                else:
                    # Ethernet-like interfaces: try DHCP
                    logger.info("Attempting DHCP for ethernet-like interface...")
                    try:
                        result = subprocess.run(
                            ['sudo', 'dhclient', CONFIG["interface"]], 
                            capture_output=True, text=True, timeout=15
                        )
                        if result.returncode != 0:
                            logger.warning(f"DHCP failed for {CONFIG['interface']}")
                    except Exception as e:
                        logger.warning(f"DHCP attempt failed: {e}")
                
                return True
            
            logger.warning("Could not connect modem using standard methods")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting modem: {e}")
            return False
    
    def rotate_connection(self) -> Dict[str, Any]:
        """Rotate the modem connection"""
        with self.lock:
            try:
                logger.info("Starting connection rotation...")
                
                # Get initial status
                initial_status = self.get_connection_status()
                
                # Disconnect
                if not self.disconnect_modem():
                    return {
                        "success": False,
                        "error": "Failed to disconnect modem",
                        "status": initial_status
                    }
                
                # Wait before reconnecting (longer delay for aggressive rotation)
                if CONFIG.get("aggressive_rotation", False):
                    delay = CONFIG.get("modem_reset_delay", 10)
                    logger.info(f"Aggressive rotation: waiting {delay} seconds for complete session reset...")
                    time.sleep(delay)
                else:
                    logger.info(f"Waiting {CONFIG['disconnect_delay']} seconds...")
                    time.sleep(CONFIG["disconnect_delay"])
                
                # Reconnect
                if not self.connect_modem():
                    return {
                        "success": False,
                        "error": "Failed to reconnect modem",
                        "status": self.get_connection_status()
                    }
                
                # Wait for connection to establish
                logger.info("Waiting for connection to establish...")
                start_time = time.time()
                while time.time() - start_time < CONFIG["reconnect_timeout"]:
                    time.sleep(2)
                    status = self.get_connection_status()
                    if status.get("internet_connected"):
                        break
                
                # Update tracking
                self.last_rotation = datetime.now().isoformat()
                self.rotation_count += 1
                
                final_status = self.get_connection_status()
                logger.info("Connection rotation completed")
                
                return {
                    "success": True,
                    "message": "Connection rotated successfully",
                    "initial_status": initial_status,
                    "final_status": final_status,
                    "rotation_time": self.last_rotation,
                    "total_rotations": self.rotation_count
                }
                
            except Exception as e:
                logger.error(f"Error during connection rotation: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "status": self.get_connection_status()
                }

class RotatorHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, rotator=None, **kwargs):
        self.rotator = rotator
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "service": "Modem Connection Rotator",
                "version": "1.0",
                "endpoints": {
                    "/status": "Get connection status",
                    "/rotate": "Rotate connection",
                    "/health": "Health check"
                }
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = self.rotator.get_connection_status()
            self.wfile.write(json.dumps(status, indent=2).encode())
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "timestamp": datetime.now().isoformat()}
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"error": "Endpoint not found"}
            self.wfile.write(json.dumps(response).encode())
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/rotate':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = self.rotator.rotate_connection()
            self.wfile.write(json.dumps(result, indent=2).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"error": "Endpoint not found"}
            self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

def create_handler(rotator):
    def handler(*args, **kwargs):
        return RotatorHandler(*args, rotator=rotator, **kwargs)
    return handler

def main():
    rotator = ModemRotator()
    handler = create_handler(rotator)
    
    server = HTTPServer(('0.0.0.0', CONFIG["port"]), handler)
    logger.info(f"Starting Modem Rotator Service on port {CONFIG['port']}")
    logger.info(f"Interface: {CONFIG['interface']}")
    logger.info("Endpoints:")
    logger.info("  GET  /         - Service info")
    logger.info("  GET  /status   - Connection status")
    logger.info("  GET  /health   - Health check")
    logger.info("  POST /rotate   - Rotate connection")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.shutdown()

if __name__ == "__main__":
    main()
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
    "interface": "cdc-wdm0",
    "disconnect_delay": 1,
    "reconnect_timeout": 8,
    "log_level": "INFO",
    "modem_reset_delay": 1
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
            # For NetworkManager devices like cdc-wdm0, check the actual network interface (wwan0)
            network_interface = "wwan0"  # Always check wwan0 for IP status
            
            # Check if interface is up
            result = subprocess.run(
                ['ip', 'link', 'show', network_interface], 
                capture_output=True, text=True, timeout=10
            )
            interface_up = result.returncode == 0 and 'UP' in result.stdout
            
            # Get IP address if interface is up
            ip_address = None
            if interface_up:
                ip_result = subprocess.run(
                    ['ip', 'addr', 'show', network_interface], 
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
                "interface": network_interface,  # Show wwan0 in status
                "nm_device": CONFIG["interface"],  # Show cdc-wdm0 as the control device
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
        """Disable modem completely - airplane mode style"""
        try:
            logger.info("Disabling modem completely (airplane mode style)...")
            
            # Turn off modem completely
            result = subprocess.run(
                ['mmcli', '-m', '0', '--disable'], 
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0:
                logger.info("Modem disabled successfully")
                return True
            else:
                logger.error(f"mmcli disable failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("ModemManager (mmcli) not found")
            return False
        except Exception as e:
            logger.error(f"Error disabling modem: {e}")
            return False
    
    def connect_modem(self) -> bool:
        """Enable and connect modem - airplane mode style"""
        try:
            logger.info("Enabling modem...")
            
            # Turn modem back on
            result = subprocess.run(
                ['mmcli', '-m', '0', '--enable'], 
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0:
                logger.info("Modem enabled successfully")
            else:
                logger.error(f"mmcli enable failed: {result.stderr}")
                return False
            
            # Wait for modem to initialize
            time.sleep(3)
            
            # Connect modem
            logger.info("Connecting modem...")
            result = subprocess.run(
                ['mmcli', '-m', '0', '--simple-connect'], 
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info("Modem connected successfully")
                return True
            else:
                logger.error(f"mmcli connect failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("ModemManager (mmcli) not found")
            return False
        except Exception as e:
            logger.error(f"Error enabling/connecting modem: {e}")
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
                    time.sleep(1)  # Check every 1 second instead of 2
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
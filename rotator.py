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
    
    def find_usb_modem_path(self, vendor_product: str) -> str:
        """Find the USB device path for the modem in sysfs"""
        try:
            vendor_id, product_id = vendor_product.split(':')
            logger.info(f"Searching for USB device with vendor:{vendor_id} product:{product_id}")
            
            # Method 1: Direct check of the likely device paths first
            # Based on the debug output, the modem is likely at 1-1.2
            likely_devices = ['1-1.2', '1-1', '2-1']  # Common modem locations
            
            for device_name in likely_devices:
                device_path = f"/sys/bus/usb/devices/{device_name}"
                vendor_file = f"{device_path}/idVendor"
                product_file = f"{device_path}/idProduct"
                auth_file = f"{device_path}/authorized"
                
                try:
                    if os.path.exists(vendor_file) and os.path.exists(product_file):
                        with open(vendor_file, 'r') as f:
                            dev_vendor = f.read().strip()
                        with open(product_file, 'r') as f:
                            dev_product = f.read().strip()
                        
                        logger.info(f"Checking device {device_name}: vendor={dev_vendor} product={dev_product}")
                        
                        if dev_vendor == vendor_id and dev_product == product_id:
                            if os.path.exists(auth_file):
                                logger.info(f"Found modem device at: {device_path}")
                                logger.info(f"Authorized file found: {auth_file}")
                                return device_path
                            else:
                                logger.warning(f"Device found but no authorized file: {auth_file}")
                except Exception as e:
                    logger.debug(f"Error checking device {device_name}: {e}")
                    continue
            
            # Method 2: Search by vendor/product ID in sysfs (fallback)
            find_result = subprocess.run(
                ['find', '/sys/bus/usb/devices', '-name', 'idVendor'], 
                capture_output=True, text=True, timeout=10
            )
            
            logger.info(f"Find command found {len(find_result.stdout.strip().split())} vendor files")
            
            for vendor_file in find_result.stdout.strip().split('\n'):
                if not vendor_file:
                    continue
                try:
                    with open(vendor_file, 'r') as f:
                        file_vendor = f.read().strip()
                    if file_vendor == vendor_id:
                        # Check product ID too
                        product_file = vendor_file.replace('idVendor', 'idProduct')
                        with open(product_file, 'r') as f:
                            file_product = f.read().strip()
                        logger.info(f"Found matching vendor in {vendor_file}: vendor={file_vendor} product={file_product}")
                        if file_product == product_id:
                            usb_device_path = os.path.dirname(vendor_file)
                            logger.info(f"Found USB device at: {usb_device_path}")
                            
                            # Verify the authorized file exists and is writable
                            auth_file = f"{usb_device_path}/authorized"
                            if os.path.exists(auth_file):
                                logger.info(f"Authorized file found: {auth_file}")
                                return usb_device_path
                            else:
                                logger.warning(f"Authorized file not found: {auth_file}")
                                # Try to find parent device if this is an interface
                                parent_path = os.path.dirname(usb_device_path)
                                parent_auth = f"{parent_path}/authorized"
                                if os.path.exists(parent_auth):
                                    logger.info(f"Found parent device authorized file: {parent_auth}")
                                    return parent_path
                except Exception as e:
                    logger.debug(f"Error checking USB device {vendor_file}: {e}")
                    continue
            
            # Method 3: Look for devices that match the pattern from debug listing
            try:
                ls_result = subprocess.run(
                    ['ls', '-la', '/sys/bus/usb/devices/'], 
                    capture_output=True, text=True, timeout=5
                )
                logger.info("Debug: Available USB devices in /sys/bus/usb/devices:")
                logger.info(f"USB devices listing:\n{ls_result.stdout}")
                
                # Look for device entries that could be the modem (non-interface entries)
                for line in ls_result.stdout.split('\n'):
                    if '->' in line and ':' not in line:
                        # This is a device, not an interface (no colon)
                        parts = line.split()
                        if len(parts) >= 9:
                            device_name = parts[8]  # Get the symlink name
                            if device_name not in ['usb1', 'usb2', '.', '..'] and device_name.startswith('1-'):
                                device_path = f"/sys/bus/usb/devices/{device_name}"
                                vendor_file = f"{device_path}/idVendor"
                                product_file = f"{device_path}/idProduct"
                                auth_file = f"{device_path}/authorized"
                                
                                logger.info(f"Scanning device: {device_name}")
                                try:
                                    if os.path.exists(vendor_file) and os.path.exists(product_file):
                                        with open(vendor_file, 'r') as f:
                                            dev_vendor = f.read().strip()
                                        with open(product_file, 'r') as f:
                                            dev_product = f.read().strip()
                                        logger.info(f"Device {device_name}: vendor={dev_vendor} product={dev_product}")
                                        if dev_vendor == vendor_id and dev_product == product_id:
                                            if os.path.exists(auth_file):
                                                logger.info(f"Found modem device by scanning: {device_path}")
                                                return device_path
                                            else:
                                                logger.warning(f"Found modem but no authorized file: {auth_file}")
                                except Exception as e:
                                    logger.debug(f"Error scanning device {device_name}: {e}")
                                    continue
            except Exception as e:
                logger.debug(f"Error in device scanning: {e}")
                pass
                
            return None
        except Exception as e:
            logger.error(f"Error finding USB device path: {e}")
            return None
        
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
        """USB power cycle - nuclear option"""
        try:
            logger.info("Power cycling USB modem (nuclear option)...")
            
            # Step 1: Find the USB modem device
            try:
                result = subprocess.run(
                    ['lsusb'], capture_output=True, text=True, timeout=10
                )
                usb_info = None
                vendor_product = None
                
                for line in result.stdout.split('\n'):
                    line_upper = line.upper()
                    if ('SIMCOM' in line_upper or 'SIM7600' in line_upper or 
                        'QUALCOMM' in line_upper or 'SIMTECH' in line_upper or
                        'OPTION' in line_upper):
                        # Extract vendor:product ID
                        # Format: Bus 001 Device 004: ID 1e0e:9001 Qualcomm / Option SimTech
                        if ' ID ' in line:
                            id_part = line.split(' ID ')[1].split()[0]  # Get "1e0e:9001"
                            vendor_product = id_part
                            logger.info(f"Found modem with ID: {vendor_product} - {line.strip()}")
                            break
                
                if not vendor_product:
                    logger.warning("Could not find USB modem, falling back to rfkill")
                    # Fallback to rfkill
                    result = subprocess.run(
                        ['sudo', 'rfkill', 'block', 'wwan'], 
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        logger.info("Cellular radio blocked via rfkill")
                        return True
                    else:
                        return False
                
                # Find the USB device path
                usb_info = self.find_usb_modem_path(vendor_product)
                
                if not usb_info:
                    logger.warning("Could not find USB modem device path, falling back to rfkill")
                    # Fallback to rfkill
                    result = subprocess.run(
                        ['sudo', 'rfkill', 'block', 'wwan'], 
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        logger.info("Cellular radio blocked via rfkill")
                        return True
                    else:
                        return False
                
                # Step 2: Disable USB device
                auth_file = f"{usb_info}/authorized"
                
                result = subprocess.run(
                    ['sudo', 'sh', '-c', f'echo 0 > {auth_file}'], 
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    logger.info("USB modem powered down successfully")
                    return True
                else:
                    logger.error(f"USB power down failed: {result.stderr}")
                    return False
                    
            except Exception as e:
                logger.error(f"USB detection failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error power cycling USB: {e}")
            return False
    
    def connect_modem(self) -> bool:
        """Power up USB modem - nuclear option"""
        try:
            logger.info("Powering up USB modem...")
            
            # Step 1: Find the USB modem device (same logic as disconnect)
            try:
                result = subprocess.run(
                    ['lsusb'], capture_output=True, text=True, timeout=10
                )
                usb_info = None
                vendor_product = None
                
                for line in result.stdout.split('\n'):
                    line_upper = line.upper()
                    if ('SIMCOM' in line_upper or 'SIM7600' in line_upper or 
                        'QUALCOMM' in line_upper or 'SIMTECH' in line_upper or
                        'OPTION' in line_upper):
                        # Extract vendor:product ID
                        if ' ID ' in line:
                            id_part = line.split(' ID ')[1].split()[0]  # Get "1e0e:9001"
                            vendor_product = id_part
                            logger.info(f"Found modem with ID: {vendor_product} - {line.strip()}")
                            break
                
                if not vendor_product:
                    logger.warning("Could not find USB modem, falling back to rfkill")
                    # Fallback to rfkill
                    result = subprocess.run(
                        ['sudo', 'rfkill', 'unblock', 'wwan'], 
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        logger.info("Cellular radio unblocked via rfkill")
                        time.sleep(8)
                        return True
                    else:
                        return False
                
                # Find the USB device path
                usb_info = self.find_usb_modem_path(vendor_product)
                
                if not usb_info:
                    logger.warning("Could not find USB modem device path, falling back to rfkill")
                    # Fallback to rfkill
                    result = subprocess.run(
                        ['sudo', 'rfkill', 'unblock', 'wwan'], 
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        logger.info("Cellular radio unblocked via rfkill")
                        time.sleep(8)
                        return True
                    else:
                        return False
                
                # Step 2: Re-enable USB device
                auth_file = f"{usb_info}/authorized"
                
                result = subprocess.run(
                    ['sudo', 'sh', '-c', f'echo 1 > {auth_file}'], 
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    logger.info("USB modem powered up successfully")
                    
                    # Wait for USB re-enumeration and auto-connect
                    logger.info("Waiting for USB re-enumeration and auto-connect...")
                    time.sleep(10)
                    return True
                else:
                    logger.error(f"USB power up failed: {result.stderr}")
                    return False
                    
            except Exception as e:
                logger.error(f"USB re-enablement failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error powering up USB: {e}")
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
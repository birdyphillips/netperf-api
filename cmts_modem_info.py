#!/usr/bin/env python3
import paramiko
import sys
import os
import logging
from datetime import datetime
from config_loader import config

# Setup logging
log_dir = "/home/aphillips/Projects/LLD_TEST_CLT_Dev_linux_compatible/logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"cmts_modem_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress paramiko's verbose logging
logging.getLogger("paramiko").setLevel(logging.WARNING)

def ssh_cmts_collector(username, jumpserver, cmts_host, cmts_password, cm_mac, cmts_type, output_file=None):
    """SSH into jump server, then to CMTS and execute service flow commands"""
    
    logger.info(f"Starting CMTS collection for {cmts_type.upper()} {cmts_host}, CM MAC: {cm_mac}")
    
    # Determine commands based on CMTS type
    if cmts_type.lower() == 'icmts':
        commands = [
            f"scm {cm_mac}",
            f"scm {cm_mac} detail",
            f"scm {cm_mac} qos"
        ]
        labels = [
            "Cable Modem Summary",
            "Cable Modem Details",
            "QoS Information"
        ]
    else:  # vcmts
        commands = [
            f"scm {cm_mac} ip",
            f"scm {cm_mac} service-flow aqm",
            f"scm {cm_mac} cpe",
            f"scm {cm_mac} qos bps"
        ]
        labels = [
            "IP Address Information",
            "Service Flow AQM Configuration",
            "CPE Information",
            "QoS Bandwidth Information"
        ]
    
    try:
        # Create SSH client for jumpserver
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to jumpserver
        key_path = config.ssh_key_path
        connected = False
        
        try:
            if os.path.exists(key_path):
                logger.info(f"Connecting to jumpserver {jumpserver} with key: {key_path}")
                print(f"Connecting to jumpserver {jumpserver} with key: {key_path}")
                ssh.connect(jumpserver, username=username, key_filename=key_path, timeout=10)
                connected = True
        except Exception as e:
            logger.warning(f"Failed with key {key_path}: {e}")
            print(f"Failed with key {key_path}: {e}")
        
        if not connected:
            try:
                logger.info(f"Connecting to jumpserver {jumpserver} with default keys")
                print(f"Connecting to jumpserver {jumpserver} with default keys")
                ssh.connect(jumpserver, username=username, timeout=10)
                connected = True
            except Exception as e:
                logger.error(f"Failed with default keys: {e}")
                print(f"Failed with default keys: {e}")
        
        if not connected:
            logger.error(f"Failed to connect to jumpserver {jumpserver}")
            raise Exception(f"Failed to connect to jumpserver {jumpserver}")
        
        logger.info(f"Successfully connected to jumpserver {jumpserver}")
        print(f"Successfully connected to jumpserver {jumpserver}")
        
        logger.info(f"Executing commands on {cmts_type.upper()} {cmts_host} via jumpserver...")
        print(f"Executing commands on {cmts_type.upper()} {cmts_host} via jumpserver...")
        
        results = {}
        output_lines = []
        cm_ipv6 = None
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_lines.append(f"{cmts_type.upper()} Modem Information - {timestamp}")
        output_lines.append(f"{cmts_type.upper()} Host: {cmts_host}")
        output_lines.append(f"Cable Modem MAC: {cm_mac}")
        output_lines.append("="*80)
        
        # Execute commands via jumpserver using interactive shell
        for i, cmd in enumerate(commands):
            logger.info(f"Executing command {i+1}/{len(commands)}: {cmd}")
            print(f"\nExecuting: {cmd}")
            
            # Open interactive shell on jumpserver
            shell = ssh.invoke_shell()
            
            # SSH from jumpserver to CMTS
            shell.send(f"ssh -o StrictHostKeyChecking=no {username}@{cmts_host}\n")
            
            # Wait for password prompt
            import time
            time.sleep(1)
            output_buffer = shell.recv(4096).decode()
            
            # Send password if prompted
            if 'password' in output_buffer.lower():
                shell.send(cmts_password + '\n')
                time.sleep(1)
                output_buffer += shell.recv(4096).decode()
            
            # Execute command
            shell.send(cmd + '\n')
            time.sleep(2)  # Wait for command to complete
            
            # Collect output and handle --More-- pagination
            output = ''
            max_iterations = 50  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                if shell.recv_ready():
                    chunk = shell.recv(4096).decode()
                    output += chunk
                    
                    # Check if --More-- prompt is present
                    if '--More--' in chunk:
                        shell.send(' ')  # Send space to continue
                        time.sleep(0.5)
                    else:
                        time.sleep(0.1)
                else:
                    # No more data available
                    time.sleep(0.2)
                    if not shell.recv_ready():
                        break
                
                iteration += 1
            
            # Exit CMTS session
            shell.send('exit\n')
            time.sleep(0.5)
            
            shell.close()
            
            error = ''
            
            results[labels[i]] = {
                'output': output,
                'error': error if error else None
            }
            
            # Extract IPv6 on first command (IP info)
            if i == 0:
                import re
                # Match full IPv6 address (at least 4 groups with colons)
                ipv6_match = re.search(r'([0-9a-f]{1,4}:[0-9a-f]{1,4}:[0-9a-f:]+:[0-9a-f:]+)', output, re.IGNORECASE)
                if ipv6_match:
                    cm_ipv6 = ipv6_match.group(1)
                    logger.info(f"Extracted Cable Modem IPv6: {cm_ipv6}")
                    print(f"\nCable Modem IPv6: {cm_ipv6}")
            
        ssh.close()
        
        # Build organized output based on CMTS type
        organized_output = []
        organized_output.append(output_lines[0])  # Title
        organized_output.append(output_lines[1])  # CMTS Host
        organized_output.append(output_lines[2])  # CM MAC
        if cm_ipv6:
            organized_output.append(f"Cable Modem IPv6: {cm_ipv6}")
        organized_output.append(output_lines[3])  # Separator
        
        # Add sections in order
        for label in labels:
            organized_output.append(f"\n{label}")
            organized_output.append("="*80)
            organized_output.append(results[label]['output'])
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write('\n'.join(organized_output))
                logger.info(f"Results saved to: {output_file}")
                print(f"Results saved to: {output_file}")
        
        logger.info(f"CMTS collection completed successfully")
        return {'results': results, 'cm_ipv6': cm_ipv6}
        
    except Exception as e:
        error_msg = f"SSH connection failed: {e}"
        logger.error(error_msg)
        print(error_msg)
        if output_file:
            with open(output_file, 'w') as f:
                f.write(f"ERROR: {error_msg}\n")
        return None

def collect_cmts_data(cmts_host, cm_mac, cmts_type='vcmts', test_name=None, output_dir="Results"):
    """Collect CMTS service flow data and return IPv6 address"""
    username = config.snmp_username
    jumpserver = config.snmp_jumpserver
    cmts_password = config.vcmts_password
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cm_mac_clean = cm_mac.replace('.', '').replace(':', '')
    if test_name:
        filename = os.path.join(output_dir, f"{test_name}_{cmts_type}_{cm_mac_clean}_{timestamp}.txt")
    else:
        filename = os.path.join(output_dir, f"{cmts_type}_{cm_mac_clean}_{timestamp}.txt")
    
    logger.info(f"Collecting {cmts_type.upper()} service flow data for CM: {cm_mac}")
    print(f"Collecting {cmts_type.upper()} service flow data for CM: {cm_mac}")
    result = ssh_cmts_collector(username, jumpserver, cmts_host, cmts_password, cm_mac, cmts_type, filename)
    
    if result and 'cm_ipv6' in result:
        return result['cm_ipv6']
    return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cmts_modem_info.py <cmts_host> <cm_mac> [cmts_type] [test_name] [output_dir]")
        print("Example (vCMTS): python cmts_modem_info.py apc01k1dccc e0db.d161.3d18 vcmts ByteBlower_Test Results")
        print("Example (iCMTS): python cmts_modem_info.py cts01k1dccc 0cb9.379c.64b4 icmts ByteBlower_Test Results")
        sys.exit(1)
    
    cmts_host = sys.argv[1]
    cm_mac = sys.argv[2]
    cmts_type = sys.argv[3] if len(sys.argv) > 3 else 'vcmts'
    test_name = sys.argv[4] if len(sys.argv) > 4 else None
    output_dir = sys.argv[5] if len(sys.argv) > 5 else "Results"
    
    cm_ipv6 = collect_cmts_data(cmts_host, cm_mac, cmts_type, test_name, output_dir)
    if cm_ipv6:
        logger.info(f"Cable Modem IPv6 Address: {cm_ipv6}")
        print(f"\n{'='*80}")
        print(f"Cable Modem IPv6 Address: {cm_ipv6}")
        print(f"{'='*80}")
    
    logger.info(f"Log file: {log_file}")

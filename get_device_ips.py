#!/usr/bin/env python3
import paramiko
import re
import yaml

def get_cpe_ips_vcmts(channel, cm_mac, verbose=True):
    """Get CPE IPs from vCMTS using 'scm cpe' commands"""
    import time
    devices = {}
    
    # Get IPv4 addresses
    if verbose:
        print(f"  Running: scm {cm_mac} cpe")
    channel.send(f"scm {cm_mac} cpe\n")
    time.sleep(2)
    output_ipv4 = ""
    timeout = time.time() + 10
    while time.time() < timeout:
        if channel.recv_ready():
            chunk = channel.recv(9999).decode()
            output_ipv4 += chunk
            if "--More--" in chunk:
                channel.send(" ")
                time.sleep(0.5)
            elif "(END)" in chunk:
                channel.send("q")
                time.sleep(0.5)
            elif "aphillips@" in chunk:
                break
        time.sleep(0.3)
    if verbose:
        print(f"  Received {len(output_ipv4)} bytes")
        print("\n" + "="*60)
        print(output_ipv4)
        print("="*60 + "\n")
    
    # Get IPv6 addresses
    if verbose:
        print(f"  Running: scm {cm_mac} cpe ipv6")
    channel.send(f"scm {cm_mac} cpe ipv6\n")
    time.sleep(2)
    output_ipv6 = ""
    timeout = time.time() + 10
    while time.time() < timeout:
        if channel.recv_ready():
            chunk = channel.recv(9999).decode()
            output_ipv6 += chunk
            if "--More--" in chunk:
                channel.send(" ")
                time.sleep(0.5)
            elif "(END)" in chunk:
                channel.send("q")
                time.sleep(0.5)
            elif "aphillips@" in chunk:
                break
        time.sleep(0.3)
    if verbose:
        print(f"  Received {len(output_ipv6)} bytes")
        print("\n" + "="*60)
        print(output_ipv6)
        print("="*60 + "\n")
    
    # Parse IPv4
    for line in output_ipv4.split('\n'):
        match = re.search(r'(\w+\.\w+\.\w+)\s+d4\s+(\d+\.\d+\.\d+\.\d+)', line)
        if match:
            mac = match.group(1).replace('.', ':')
            ipv4 = match.group(2)
            devices[mac] = {'ipv4': ipv4}
            if verbose:
                print(f"  Found IPv4: {mac} -> {ipv4}")
    
    # Parse IPv6
    for line in output_ipv6.split('\n'):
        parts = line.split()
        if len(parts) >= 5 and 'cpe' in parts:
            try:
                mac = parts[3].replace('.', ':')
                ipv6 = parts[4]
                if ':' in ipv6 and not ipv6.startswith('fe80'):
                    if mac in devices:
                        devices[mac]['ipv6'] = ipv6
                    else:
                        devices[mac] = {'ipv6': ipv6}
                    if verbose:
                        print(f"  Found IPv6: {mac} -> {ipv6}")
            except:
                pass
    
    return devices

def get_cpe_ips_icmts(channel, cm_mac, verbose=True):
    """Get CPE IPs from iCMTS using 'scm detail' command"""
    import time
    devices = {}
    
    if verbose:
        print(f"  Running: scm {cm_mac} detail")
    channel.send(f"scm {cm_mac} detail\n")
    time.sleep(3)
    output = ""
    while channel.recv_ready():
        chunk = channel.recv(9999).decode()
        output += chunk
        time.sleep(0.5)
    if verbose:
        print(f"  Received {len(output)} bytes")
        print("\n" + "="*60)
        print(output)
        print("="*60 + "\n")
    
    # Parse CPE lines
    for line in output.split('\n'):
        if 'CPE' in line and ('IPv4=' in line or 'IPv6=' in line):
            # Extract MAC
            mac_match = re.search(r'CPE\s+(\w+\.\w+\.\w+)', line)
            if mac_match:
                mac = mac_match.group(1).replace('.', ':')
                if mac not in devices:
                    devices[mac] = {}
                
                # Extract IPv4
                ipv4_match = re.search(r'IPv4=(\d+\.\d+\.\d+\.\d+)', line)
                if ipv4_match:
                    devices[mac]['ipv4'] = ipv4_match.group(1)
                    if verbose:
                        print(f"  Found IPv4: {mac} -> {ipv4_match.group(1)}")
                
                # Extract IPv6 (skip fe80 link-local)
                ipv6_match = re.search(r'IPv6=([\da-f:]+)', line)
                if ipv6_match:
                    ipv6 = ipv6_match.group(1)
                    if not ipv6.startswith('fe80'):
                        devices[mac]['ipv6'] = ipv6
                        if verbose:
                            print(f"  Found IPv6: {mac} -> {ipv6}")
    
    return devices

def get_cpe_ips(cmts_host, cm_mac, tacacs_password, jumpserver, jumpserver_user, ssh_key_path, cmts_type='vcmts', verbose=True):
    """Get CPE IPv4 and IPv6 addresses from CMTS"""
    import time
    if verbose:
        print(f"\nConnecting to jumpserver {jumpserver}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Connect to jumpserver
    client.connect(jumpserver, username=jumpserver_user, key_filename=ssh_key_path)
    channel = client.invoke_shell()
    time.sleep(2)
    if verbose:
        print(f"Connected to jumpserver")
    
    # Connect to CMTS
    if verbose:
        print(f"Connecting to CMTS {cmts_host}...")
    channel.send(f"ssh {cmts_host}\n")
    time.sleep(3)
    channel.recv(9999)
    channel.send(f"{tacacs_password}\n")
    time.sleep(2)
    channel.recv(9999)
    if verbose:
        print(f"Connected to CMTS")
    
    # Get CPE IPs based on CMTS type
    if cmts_type == 'icmts':
        devices = get_cpe_ips_icmts(channel, cm_mac, verbose)
    else:
        devices = get_cpe_ips_vcmts(channel, cm_mac, verbose)
    
    client.close()
    return devices

def update_config(devices, config_file='config.yaml'):
    """Update config.yaml with device IPs"""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Map MACs to client names
    for client_name, client_config in config['speedtest'].items():
        mac = client_config.get('mac', '').replace('.', ':')
        if mac in devices:
            if 'ipv4' in devices[mac]:
                client_config['host'] = devices[mac]['ipv4']
            if 'ipv6' in devices[mac]:
                client_config['ipv6'] = devices[mac]['ipv6']
    
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        cmts_host = sys.argv[1]
        cm_mac = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        # Load from config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        cmts_host = config['vcmts']['host']
        cm_mac = config['vcmts']['cm_mac']
    
    if not cm_mac:
        print("Usage: python3 get_device_ips.py [cmts_host] [cm_mac]")
        print("Example: python3 get_device_ips.py apc01k1dccc 802b.f9fa.ee17")
        print("Or run without arguments to use config.yaml")
        sys.exit(1)
    
    # Load config for credentials
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    tacacs_password = config['cmts']['tacacs_password']
    jumpserver = config['snmp']['jumpserver']
    jumpserver_user = config['snmp']['username']
    ssh_key_path = config['ssh']['key_path'].replace('~', '/home/aphillips')
    
    # Detect CMTS type
    cmts_type = 'icmts' if 'cts01k1dccc' in cmts_host else 'vcmts'
    
    print(f"Fetching device IPs from {cmts_type.upper()} {cmts_host} for CM {cm_mac}...")
    devices = get_cpe_ips(cmts_host, cm_mac, tacacs_password, jumpserver, jumpserver_user, ssh_key_path, cmts_type)
    
    print("\n" + "="*60)
    print("FOUND DEVICES")
    print("="*60)
    for mac, ips in devices.items():
        print(f"\nMAC: {mac}")
        if 'ipv4' in ips:
            print(f"  IPv4: {ips['ipv4']}")
        if 'ipv6' in ips:
            print(f"  IPv6: {ips['ipv6']}")
    print("="*60)
    
    print("\nUpdating config.yaml...")
    update_config(devices)
    print("Done!")

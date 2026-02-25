#!/usr/bin/env python3
import paramiko
import sys
import os
import re
import logging
from datetime import datetime
from config_loader import config

# Suppress paramiko's verbose logging (including SSH banners)
logging.getLogger("paramiko").setLevel(logging.WARNING)

# Excel export functionality
try:
    import pandas as pd
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

def parse_snmp_data(file_path):
    """Parse SNMP data from text file and return structured data"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract metadata
    timestamp_match = re.search(r'SNMP Collection - (.+)', content)
    target_ip_match = re.search(r'Target IP: (.+)', content)
    
    timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
    target_ip = target_ip_match.group(1) if target_ip_match else "Unknown"
    
    # Split content into sections
    sections = re.split(r'\n([A-Z][^\n]+)\n=+\n', content)
    
    data = []
    current_section = "Unknown"
    
    for i in range(len(sections)):
        # Section headers are at odd indices after split
        if i > 0 and i % 2 == 1:
            current_section = sections[i].strip()
        elif i % 2 == 0 and i > 0:
            # Parse SNMP entries in this section
            snmp_pattern = r'SNMPv2-SMI::(.+?) = (.+?): (.+)'
            matches = re.findall(snmp_pattern, sections[i])
            
            for oid, data_type, value in matches:
                data.append({
                    'SNMP_Name': current_section,
                    'OID': oid,
                    'Type': data_type,
                    'Value': value,
                    'Timestamp': timestamp,
                    'Target_IP': target_ip
                })
    
    return data

def export_to_excel(test_name, phase, timestamp, output_dir):
    if not EXCEL_AVAILABLE:
        return None
    
    # Create Excel filename with same naming convention
    excel_filename = os.path.join(output_dir, f"{test_name}_SNMP_Combined_{timestamp}.xlsx")
    
    # Check if Excel file already exists to avoid duplicates
    if os.path.exists(excel_filename):
        print(f"Excel file already exists: {excel_filename}")
        return excel_filename
    
    # Find all SNMP files for this test
    before_file = None
    after_file = None
    
    for file in os.listdir(output_dir):
        if file.startswith(f"{test_name}_SNMP_before_"):
            before_file = os.path.join(output_dir, file)
        elif file.startswith(f"{test_name}_SNMP_after_"):
            after_file = os.path.join(output_dir, file)
    
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        # Process before data
        if before_file and os.path.exists(before_file):
            before_data = parse_snmp_data(before_file)
            if before_data:
                df_before = pd.DataFrame(before_data)
                df_before.to_excel(writer, sheet_name='Before_Test', index=False)
        
        # Process after data
        if after_file and os.path.exists(after_file):
            after_data = parse_snmp_data(after_file)
            if after_data:
                df_after = pd.DataFrame(after_data)
                df_after.to_excel(writer, sheet_name='After_Test', index=False)
        
        # Create comparison sheet if both exist
        if before_file and after_file and os.path.exists(before_file) and os.path.exists(after_file):
            before_data = parse_snmp_data(before_file)
            after_data = parse_snmp_data(after_file)
            
            if before_data and after_data:
                # Create comparison dataframe
                df_before = pd.DataFrame(before_data)
                df_after = pd.DataFrame(after_data)
                
                # Merge on OID for comparison, include SNMP_Name
                comparison = pd.merge(df_before[['SNMP_Name', 'OID', 'Value']], 
                                    df_after[['OID', 'Value']], 
                                    on='OID', 
                                    suffixes=('_Before', '_After'))
                
                # Calculate differences for numeric values
                def safe_numeric_diff(before_val, after_val):
                    try:
                        before_num = float(re.sub(r'[^\d.]', '', str(before_val)))
                        after_num = float(re.sub(r'[^\d.]', '', str(after_val)))
                        return after_num - before_num
                    except:
                        return "N/A"
                
                comparison['Difference'] = comparison.apply(
                    lambda row: safe_numeric_diff(row['Value_Before'], row['Value_After']), 
                    axis=1
                )
                
                comparison.to_excel(writer, sheet_name='Comparison', index=False)
    
    print(f"Excel file created: {excel_filename}")
    return excel_filename

def ssh_snmp_collector(username, jumpserver, target_ip, output_file=None, snmp_community=None, snmp_timeout=None, snmp_retries=None):
    """SSH into jump server and execute SNMP commands"""
    
    # Use config values if not provided
    if snmp_community is None:
        snmp_community = config.snmp_community
    if snmp_timeout is None:
        snmp_timeout = config.snmp_timeout
    if snmp_retries is None:
        snmp_retries = config.snmp_retries
    
    # Modem information command
    modem_info_cmd = f"snmpwalk -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} sysDescr"
    
    # SNMP commands from your notes
    commands = [
        f"snmpwalk -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} 1.3.6.1.4.1.4491.2.1.21.1.4",
        f"snmpwalk -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} 1.3.6.1.4.1.4491.2.1.21.1.27", 
        f"snmpwalk -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} 1.3.6.1.4.1.4491.2.1.21.1.29.2",
        f"snmpwalk -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} 1.3.6.1.4.1.4491.2.1.21.1.30",
        f"snmpbulkget -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} .1.3.6.1.4.1.4998.1.1.15.10.2",
        f"snmpbulkget -v 2c -c {snmp_community} -t {snmp_timeout} -r {snmp_retries} {target_ip} .1.3.6.1.4.1.4998.1.1.15.10.8"
    ]
    
    labels = [
        "Flow Stats Table (Entry Qos Service Flow Octets)",
        "Aggregate Service Flow Stats Table", 
        "Latency Stats Table",
        "Congestion Stats Table",
        "Cadant Map Stats Mib",
        "Map Stats Pages Flows"
    ]
    
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Try SSH key first
        key_path = config.ssh_key_path
        connected = False
        connection_method = None
        
        try:
            if os.path.exists(key_path):
                print(f"Attempting SSH connection to {jumpserver} with key: {key_path}")
                ssh.connect(jumpserver, username=username, key_filename=key_path, timeout=10)
                connected = True
                connection_method = f"SSH key: {key_path}"
        except Exception as e:
            print(f"Failed to connect with {key_path}: {e}")
        
        if not connected:
            try:
                print(f"Attempting SSH connection to {jumpserver} with default keys")
                ssh.connect(jumpserver, username=username, timeout=10)
                connected = True
                connection_method = "Default SSH keys"
            except Exception as e:
                print(f"Failed to connect with default keys: {e}")
        
        if not connected:
            raise Exception(f"Failed to connect to {jumpserver} as {username}. Tried: {key_path} and default keys. No authentication methods available.")
        
        print(f"Successfully connected to {jumpserver} using {connection_method}")
        
        results = {}
        output_lines = []
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_lines.append(f"SNMP Collection - {timestamp}")
        output_lines.append(f"Target IP: {target_ip}")
        output_lines.append("="*60)
        
        # Get modem information first
        print(f"Executing: snmpwalk -v 2c -c open {target_ip} sysDescr")
        stdin, stdout, stderr = ssh.exec_command(modem_info_cmd)
        modem_output = stdout.read().decode()
        modem_error = stderr.read().decode()
        
        output_lines.append(f"\nCurrent Modem Information")
        output_lines.append("="*50)
        if modem_output:
            output_lines.append(modem_output)
            print(modem_output)  # Display in terminal
        if modem_error:
            output_lines.append(f"ERROR: {modem_error}")
            print(f"ERROR: {modem_error}")
        
        # Execute each SNMP command
        for i, cmd in enumerate(commands):
            print(f"Executing: {labels[i]}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            results[labels[i]] = {
                'output': output,
                'error': error if error else None
            }
            
            # Add to output lines
            output_lines.append(f"\n{labels[i]}")
            output_lines.append("="*50)
            if output:
                output_lines.append(output)
            if error:
                output_lines.append(f"ERROR: {error}")
                print(f"Error in {labels[i]}: {error}")
        
        ssh.close()
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write('\n'.join(output_lines))
            print(f"Results saved to: {output_file}")
        
        return results
        
    except Exception as e:
        error_msg = f"SSH connection failed: {e}"
        print(error_msg)
        if output_file:
            with open(output_file, 'w') as f:
                f.write(f"ERROR: {error_msg}\n")
        return None

def collect_snmp_data(target_ip, test_name, phase, output_dir):
    """Collect SNMP data for a specific test and phase"""
    username = config.snmp_username
    jumpserver = config.snmp_jumpserver
    
    # Use provided output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create filename in output folder with SCN naming convention
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"{test_name}_SNMP_{phase}_{timestamp}.txt")
    
    print(f"Collecting SNMP data - {phase} {test_name}")
    result = ssh_snmp_collector(username, jumpserver, target_ip, filename)
    
    # Create Excel export after 'after' phase
    if phase == "after":
        try:
            export_to_excel(test_name, phase, timestamp, output_dir)
        except Exception as e:
            print(f"Excel export failed: {e}")
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python snmp_collector.py <target_ip> [test_name] [phase]")
        print("Example: python snmp_collector.py <target_ip> ByteBlower_Test before")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    test_name = sys.argv[2] if len(sys.argv) > 2 else "manual_test"
    phase = sys.argv[3] if len(sys.argv) > 3 else "standalone"
    
    if len(sys.argv) > 2:
        collect_snmp_data(target_ip, test_name, phase, "Results")
    else:
        # Original behavior for backward compatibility
        username = config.snmp_username
        jumpserver = config.snmp_jumpserver
        
        results = ssh_snmp_collector(username, jumpserver, target_ip)
        
        if results:
            for label, data in results.items():
                print(f"\n{'='*50}")
                print(f"{label}")
                print(f"{'='*50}")
                if data['output']:
                    print(data['output'])
                if data['error']:
                    print(f"ERROR: {data['error']}")
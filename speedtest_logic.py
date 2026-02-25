#!/home/aphillips/Projects/LLD_TEST_CLT_v1.4_20260115_160000_linux_compatible/venv/bin/python3
import subprocess
import time
import os
from datetime import datetime
from logger import Logger
from snmp_collector import collect_snmp_data
from config_loader import config
import glob

import csv

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

class SpeedTestLogic:
    def __init__(self, clients, test_group_name=None):
        self.logger = Logger("SpeedTestLogic")
        self.clients = clients
        self.test_group_name = test_group_name or "Speedtest"
        self.output_prefix = self._generate_output_prefix()
        
        # Load client configurations from config file
        self.client_configs = {}
        for client_name in ['linux', 'macos', 'nvidia']:
            client_cfg = config.speedtest_client_config(client_name)
            if client_cfg:
                self.client_configs[client_name] = client_cfg
    
    def _generate_output_prefix(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.test_group_name}_{timestamp}"
    
    def _run_ssh_command(self, host, username, password, command, description):
        ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no {username}@{host} '{command}'"
        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                self.logger.info(f"✓ {description} completed")
                return True, result.stdout
            else:
                self.logger.error(f"✗ {description} failed: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            self.logger.error(f"✗ {description} timed out")
            return False, "Timeout"
        except Exception as e:
            self.logger.error(f"✗ {description} error: {str(e)}")
            return False, str(e)
    
    def _copy_file_from_remote(self, host, username, password, remote_path, local_path):
        scp_cmd = f"sshpass -p '{password}' scp -o StrictHostKeyChecking=no {username}@{host}:{remote_path} {local_path}"
        try:
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"✓ File copied successfully")
                return True
            else:
                self.logger.error(f"✗ File copy failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"✗ File copy error: {str(e)}")
            return False
    
    def _run_speedtest_on_client(self, client_name, output_dir, iterations=1):
        config = self.client_configs[client_name]
        host = config["host"]
        username = config["username"]
        password = config["password"]
        
        self.logger.info(f"Starting speedtest on {client_name.upper()} ({host}) - {iterations} iteration(s)")
        
        target_ip = "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
        snmp_test_name = f"{self.test_group_name}_{client_name}"
        
        # SNMP collection before
        self.logger.info(f"Running SNMP collection - before {snmp_test_name}")
        try:
            collect_snmp_data(target_ip, snmp_test_name, "before", output_dir)
            self.logger.info(f"✓ SNMP before collection completed for {client_name}")
        except Exception as e:
            self.logger.error(f"✗ SNMP before collection failed for {client_name}: {e}")
        
        success_count = 0
        is_windows = client_name.lower() == "nvidia"
        
        for iteration in range(1, iterations + 1):
            self.logger.info(f"Iteration {iteration}/{iterations} for {client_name}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if iterations > 1:
                output_file = f"{self.test_group_name}_{client_name}_iteration_{iteration}_{timestamp}.txt"
            else:
                output_file = f"{self.test_group_name}_{client_name}_{timestamp}.txt"
            
            if is_windows:
                speedtest_cmd = f'cd C:\\\\Users\\\\Administrator\\\\Desktop\\\\ookla-speedtest-1.2.0-win64 && echo === {self.test_group_name} Speedtest Results - {client_name.upper()} - Iteration {iteration} === > {output_file} && echo Timestamp: {timestamp} >> {output_file} && echo. >> {output_file} && speedtest.exe >> {output_file}'
            else:
                speedtest_cmd = f'echo "=== {self.test_group_name} Speedtest Results - {client_name.upper()} - Iteration {iteration} ===" > {output_file} && echo "Timestamp: {timestamp}" >> {output_file} && echo "" >> {output_file}'
                if client_name.lower() == "macos":
                    speedtest_cmd += f' && /opt/homebrew/bin/speedtest >> {output_file}'
                else:
                    speedtest_cmd += f' && speedtest >> {output_file}'
            
            success, _ = self._run_ssh_command(host, username, password, speedtest_cmd, f"Speedtest iteration {iteration}")
            
            if success:
                success_count += 1
                local_file_path = os.path.join(output_dir, output_file)
                remote_file_path = f"C:/Users/Administrator/Desktop/ookla-speedtest-1.2.0-win64/{output_file}" if is_windows else output_file
                
                if self._copy_file_from_remote(host, username, password, remote_file_path, local_file_path):
                    self.logger.info(f"✓ Results saved: {output_file}")
                else:
                    self.logger.error(f"✗ Failed to copy results from {client_name}")
            else:
                self.logger.error(f"✗ Speedtest iteration {iteration} failed on {client_name}")
            
            if iteration < iterations:
                time.sleep(10)
        
        # SNMP collection after
        self.logger.info(f"Running SNMP collection - after {snmp_test_name}")
        try:
            collect_snmp_data(target_ip, snmp_test_name, "after", output_dir)
            self.logger.info(f"✓ SNMP after collection completed for {client_name}")
        except Exception as e:
            self.logger.error(f"✗ SNMP after collection failed for {client_name}: {e}")
        
        self.logger.info(f"Completed {client_name}: {success_count}/{iterations} iterations successful")
        return success_count
    
    def _consolidate_to_csv(self, output_dir):
        # SNMP consolidation removed - files kept as individual txt files
        pass
    
    def run_iterations(self, iterations=1):
        output_dir = f"Results/{self.output_prefix}"
        os.makedirs(output_dir, exist_ok=True)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"SpeedTest: {self.test_group_name}")
        self.logger.info(f"Clients: {', '.join([c.upper() for c in self.clients])}")
        self.logger.info(f"Iterations: {iterations}")
        self.logger.info(f"Output: {output_dir}")
        self.logger.info(f"{'='*60}\n")
        
        total_success = 0
        for client in self.clients:
            if client.lower() in self.client_configs:
                success = self._run_speedtest_on_client(client.lower(), output_dir, iterations)
                total_success += success
                if client != self.clients[-1]:
                    time.sleep(15)
        
        # Consolidate SNMP results to CSV
        self._consolidate_to_csv(output_dir)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"SpeedTest completed: {total_success} successful tests")
        self.logger.info(f"Results saved to: {output_dir}")
        self.logger.info(f"{'='*60}\n")
        return total_success > 0

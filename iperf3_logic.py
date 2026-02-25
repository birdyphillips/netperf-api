import subprocess
import os
import time
from datetime import datetime
from logger import Logger
from log_rotator import LogRotator
from config_loader import config
import platform

# Import Windows SSH helper if on Windows
if platform.system().lower() == 'windows':
    try:
        from windows_ssh_helper import WindowsSSHHelper
        USE_WINDOWS_SSH = True
    except ImportError:
        USE_WINDOWS_SSH = False
else:
    USE_WINDOWS_SSH = False

class IPerf3Logic:
    def __init__(self, client_ip, scenario_name, test_group_name=None, rtt_suffix="", output_format=None, platform_override=None, parent_output_dir=None):
        self.logger = Logger("IPerf3Logic")
        self.client_ip = client_ip
        self.scenario_name = scenario_name
        self.test_group_name = test_group_name
        self.rtt_suffix = rtt_suffix
        self.output_format = output_format.lower() if output_format else "json"
        self.test_id = int(datetime.now().timestamp())
        self.timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.parent_output_dir = parent_output_dir
        
        # SSH connection details - platform specific passwords and users
        if platform_override == 'macos':
            self.ssh_user = config.iperf3_macos_client_username
            self.ssh_password = config.iperf3_macos_client_password
        else:
            self.ssh_user = config.iperf3_linux_client_username
            self.ssh_password = config.iperf3_linux_client_password
        
        # Server details - platform specific
        if platform_override == 'macos':
            self.server_user = config.iperf3_macos_server_username
            self.server_password = config.iperf3_macos_server_password
            self.server_ip = config.iperf3_macos_server_host
        else:
            self.server_user = config.iperf3_linux_server_username
            self.server_password = config.iperf3_linux_server_password
            self.server_ip = config.iperf3_linux_server_host
        self.ssh_key_path = config.ssh_key_path
        
        # Create output directory name
        platform_suffix = "_macOS" if platform_override == 'macos' else "_Linux"
        if self.test_group_name:
            self.output_prefix = f"{self.test_group_name}_iPerf3{platform_suffix}_{self.timestamp_str}"
        else:
            self.output_prefix = f"iPerf3{platform_suffix}_{self.timestamp_str}"
            
        self.log_file = os.path.join(os.getcwd(), "logs", f"iperf3_{self.test_id}.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.log_rotator = LogRotator(self.log_file)
        
        # Define scenario commands based on output format and platform
        json_ext = "-i 1" if platform_override == 'macos' else ""
        file_ext = "txt"
        group_name = self.test_group_name or "HSI029"
        
        # Detect platform for command selection
        import platform
        is_macos = platform_override == 'macos' if platform_override else platform.system().lower() == 'darwin'
        self.platform_override = platform_override
        
        if is_macos:
            # macOS commands using iperf3-darwin with Apple QUIC and L4S
            self.scenario_commands = {
                "US_Combined": [
                    f"iperf3-darwin -c {self.server_ip} --apple-quic -t 30 -P 4 -p 9201 {json_ext} > US_{group_name}_Combined_4QUIC_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > US_{group_name}_Combined_1QUIC_LL.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} -u -b 0.8192M -t 30 -p 9209 {json_ext} > US_{group_name}_Combined_1UDP_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} -u -b 0.8192M --dscp 45 -t 30 -p 9211 {json_ext} > US_{group_name}_Combined_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "US_Classic_Only": [
                    f"iperf3-darwin -c {self.server_ip} --apple-quic -t 30 -P 4 -p 9201 {json_ext} > US_{group_name}_Classic_Only_4QUIC_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} -u -b 0.8192M -t 30 -p 9209 {json_ext} > US_{group_name}_Classic_Only_1UDP_CL.{file_ext} &",
                    "wait"
                ],
                "US_LL_Only": [
                    f"iperf3-darwin -c {self.server_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > US_{group_name}_LL_Only_1QUIC_LL.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} -u -b 0.8192M --dscp 45 -t 30 -p 9211 {json_ext} > US_{group_name}_LL_Only_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "DS_Combined": [
                    f"iperf3-darwin -c {self.client_ip} --apple-quic -t 30 -P 4 -p 9201 {json_ext} > DS_{group_name}_Combined_4QUIC_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > DS_{group_name}_Combined_1QUIC_LL.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} -u -b 0.8192M -t 30 -p 9209 {json_ext} > DS_{group_name}_Combined_1UDP_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} -u -b 0.8192M --dscp 45 -t 30 -p 9211 {json_ext} > DS_{group_name}_Combined_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "DS_Classic_Only": [
                    f"iperf3-darwin -c {self.client_ip} --apple-quic -t 30 -P 4 -p 9201 {json_ext} > DS_{group_name}_Classic_Only_4QUIC_CL.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} -u -b 0.8192M -t 30 -p 9209 {json_ext} > DS_{group_name}_Classic_Only_1UDP_CL.{file_ext} &",
                    "wait"
                ],
                "DS_LL_Only": [
                    f"iperf3-darwin -c {self.client_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > DS_{group_name}_LL_Only_1QUIC_LL.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} -u -b 0.8192M --dscp 45 -t 30 -p 9211 {json_ext} > DS_{group_name}_LL_Only_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "US_UDP_NC": [
                    f"iperf3-darwin -c {self.server_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > US_{group_name}_UDP_NC_QUIC.{file_ext} &",
                    f"iperf3-darwin -c {self.server_ip} -u -b 530M --dscp 45 -t 30 -p 9211 {json_ext} > US_{group_name}_UDP_NC.{file_ext} &",
                    "wait"
                ],
                "DS_UDP_NC": [
                    f"iperf3-darwin -c {self.client_ip} --apple-quic -t 30 -P 1 -p 9207 --apple-l4s {json_ext} > DS_{group_name}_UDP_NC_QUIC.{file_ext} &",
                    f"iperf3-darwin -c {self.client_ip} -u -b 530M --dscp 45 -t 30 -p 9211 {json_ext} > DS_{group_name}_UDP_NC.{file_ext} &",
                    "wait"
                ]
            }
            # macOS uses different server ports
            self.server_ports = config.iperf3_macos_ports
        else:
            # Linux commands using standard iperf3 with TCP and Prague
            self.scenario_commands = {
                "US_Combined": [
                    f"iperf3 -c {self.server_ip} -t 30 -p 9210 -P 4 -C cubic {json_ext} > US_{group_name}_Combined_4TCP_CL.{file_ext} &",
                    f"iperf3 -c {self.server_ip} -t 30 -p 9205 -P 1 -C prague {json_ext} > US_{group_name}_Combined_1TCP_LL.{file_ext} &",
                    f"iperf3 -c {self.server_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > US_{group_name}_Combined_1UDP_CL.{file_ext} &",
                    f"iperf3 -c {self.server_ip} -t 30 -u -b 0.82M -p 9206 -P 1 --dscp 45 {json_ext} > US_{group_name}_Combined_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "US_Classic_Only": [
                    f"iperf3 -c {self.server_ip} -t 30 -p 9210 -P 4 -C cubic {json_ext} > US_{group_name}_Classic_Only_4TCP_CL.{file_ext} &",
                    f"iperf3 -c {self.server_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > US_{group_name}_Classic_Only_1UDP_CL.{file_ext} &",
                    "wait"
                ],
                "US_LL_Only": [
                    f"iperf3 -c {self.server_ip} -t 30 -p 9205 -P 1 -C prague {json_ext} > US_{group_name}_LL_Only_1TCP_LL.{file_ext} &",
                    f"iperf3 -c {self.server_ip} -t 30 -u -b 0.82M -p 9206 -P 1 --dscp 45 {json_ext} > US_{group_name}_LL_Only_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "DS_Combined": [
                    f"iperf3 -c {self.client_ip} -t 30 -p 9210 -P 4 -C cubic {json_ext} > DS_{group_name}_Combined_4TCP_CL.{file_ext} &",
                    f"iperf3 -c {self.client_ip} -t 30 -p 9205 -P 1 -C prague {json_ext} > DS_{group_name}_Combined_1TCP_LL.{file_ext} &",
                    f"iperf3 -c {self.client_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > DS_{group_name}_Combined_1UDP_CL.{file_ext} &",
                    f"iperf3 -c {self.client_ip} -t 30 -u -b 0.82M -p 9206 -P 1 --dscp 45 {json_ext} > DS_{group_name}_Combined_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "DS_Classic_Only": [
                    f"iperf3 -c {self.client_ip} -t 30 -p 9210 -P 4 -C cubic {json_ext} > DS_{group_name}_Classic_Only_4TCP_CL.{file_ext} &",
                    f"iperf3 -c {self.client_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > DS_{group_name}_Classic_Only_1UDP_CL.{file_ext} &",
                    "wait"
                ],
                "DS_LL_Only": [
                    f"iperf3 -c {self.client_ip} -t 30 -p 9205 -P 1 -C prague {json_ext} > DS_{group_name}_LL_Only_1TCP_LL.{file_ext} &",
                    f"iperf3 -c {self.client_ip} -t 30 -u -b 0.82M -p 9206 -P 1 --dscp 45 {json_ext} > DS_{group_name}_LL_Only_1UDP_LL.{file_ext} &",
                    "wait"
                ],
                "US_UDP_NC": [
                    f"iperf3 -c {self.server_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > US_{group_name}_UDP_NC.{file_ext} &",
                    "wait"
                ],
                "DS_UDP_NC": [
                    f"iperf3 -c {self.client_ip} -t 30 -u -b 0.82M -p 9202 -P 1 {json_ext} > DS_{group_name}_UDP_NC.{file_ext} &",
                    "wait"
                ]
            }
            # Linux uses different server ports
            self.server_ports = config.iperf3_linux_ports
    
    def _ssh_command(self, command):
        """Execute SSH command using key authentication with password fallback"""
        try:
            # On Windows, use the default SSH key location
            if platform.system().lower() == 'windows':
                ssh_key_path = os.path.expanduser("~/.ssh/id_rsa")
                if not os.path.exists(ssh_key_path):
                    ssh_key_path = os.path.expanduser("~/.ssh/lld_key")
            else:
                ssh_key_path = self.ssh_key_path
                
            if os.path.exists(ssh_key_path):
                result = subprocess.run([
                    "ssh", "-i", ssh_key_path, "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=20",
                    f"{self.server_user}@{self.server_ip}", command
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return result
            
            # Try without specifying key (use default SSH behavior)
            result = subprocess.run([
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=20",
                f"{self.server_user}@{self.server_ip}", command
            ], capture_output=True, text=True, timeout=30)
            
            return result
            
        except Exception as e:
            self.logger.error(f"SSH command failed: {e}")
            raise

    def stop_iperf3_servers(self):
        """Stop iPerf3 servers on remote host"""
        # For DS tests, stop servers on client; for US tests, stop on server
        if self.scenario_name.startswith('DS_'):
            target_host = self.client_ip
            target_user = self.ssh_user
            target_password = self.ssh_password
            self.logger.info(f"Stopping iPerf3 servers on CLIENT: {self.client_ip}")
        else:
            target_host = self.server_ip
            target_user = self.server_user
            target_password = self.server_password
            self.logger.info(f"Stopping iPerf3 servers on SERVER: {self.server_ip}")
            
        kill_cmd = "pkill -f 'iperf3 -s' ; pkill -f 'iperf3-darwin -s'"
        
        try:
            # Try SSH key first
            key_path = os.path.expanduser("~/.ssh/lld_key")
            if os.path.exists(key_path):
                result = subprocess.run([
                    "ssh", "-i", key_path, "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=20",
                    f"{target_user}@{target_host}", kill_cmd
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    self.logger.info(f"iPerf3 servers stopped on {target_host}")
                    return
            
            # Fallback to password
            subprocess.run([
                "sshpass", "-p", target_password,
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=20",
                f"{target_user}@{target_host}", kill_cmd
            ], capture_output=True, text=True, timeout=30)
                
            self.logger.info(f"iPerf3 servers stopped on {target_host}")
        except Exception as e:
            self.logger.error(f"Exception stopping iPerf3 servers on {target_host}: {e}")
    
    def setup_iperf3_servers(self):
        """Start iPerf3 servers on required ports"""
        # Use platform-specific server ports
        server_ports = getattr(self, 'server_ports', [5202, 5205, 5206, 5210])
        
        # For DS tests, start servers on client; for US tests, start on server
        if self.scenario_name.startswith('DS_'):
            target_host = self.client_ip
            target_user = self.ssh_user
            target_password = self.ssh_password
            self.logger.info(f"Starting iPerf3 servers on CLIENT: {self.client_ip} ports: {server_ports}")
        else:
            target_host = self.server_ip
            target_user = self.server_user
            target_password = self.server_password
            self.logger.info(f"Starting iPerf3 servers on SERVER: {self.server_ip} ports: {server_ports}")
        
        # Kill any existing iperf3 processes first
        kill_cmd = "pkill -f 'iperf3 -s' ; pkill -f 'iperf3-darwin -s'"
        
        try:
            # Use SSH to target host
            if os.path.exists(self.ssh_key_path):
                result = subprocess.run([
                    "ssh", "-i", self.ssh_key_path, "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                    "-o", "ConnectTimeout=10",
                    f"{target_user}@{target_host}", kill_cmd
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode != 0:
                    subprocess.run([
                        "sshpass", "-p", target_password,
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "ConnectTimeout=10",
                        f"{target_user}@{target_host}", kill_cmd
                    ], capture_output=True, text=True, timeout=15)
            else:
                subprocess.run([
                    "sshpass", "-p", target_password,
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=10",
                    f"{target_user}@{target_host}", kill_cmd
                ], capture_output=True, text=True, timeout=15)
            
            # Set Prague congestion control on client for Prague tests
            if not self.platform_override == 'macos':
                prague_cmd = "sudo sysctl net.ipv4.tcp_congestion_control=prague"
                if os.path.exists(self.ssh_key_path):
                    subprocess.run([
                        "ssh", "-i", self.ssh_key_path, "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=10",
                        f"{self.ssh_user}@{self.client_ip}", prague_cmd
                    ], capture_output=True, text=True, timeout=15)
                else:
                    subprocess.run([
                        "sshpass", "-p", self.ssh_password,
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "ConnectTimeout=10",
                        f"{self.ssh_user}@{self.client_ip}", prague_cmd
                    ], capture_output=True, text=True, timeout=15)
                self.logger.info(f"Set Prague congestion control on client: {self.client_ip}")
            
            # Start servers on all required ports individually
            for port in server_ports:
                if self.platform_override == 'macos':
                    server_cmd = f"nohup iperf3-darwin -s -p {port} > /dev/null 2>&1 &"
                else:
                    server_cmd = f"nohup iperf3 -s -p {port} > /dev/null 2>&1 &"
                
                if os.path.exists(self.ssh_key_path):
                    result = subprocess.run([
                        "ssh", "-i", self.ssh_key_path, "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=10",
                        f"{target_user}@{target_host}", server_cmd
                    ], capture_output=True, text=True, timeout=15)
                    
                    if result.returncode != 0:
                        subprocess.run([
                            "sshpass", "-p", target_password,
                            "ssh", "-o", "StrictHostKeyChecking=no",
                            "-o", "UserKnownHostsFile=/dev/null",
                            "-o", "ConnectTimeout=10",
                            f"{target_user}@{target_host}", server_cmd
                        ], capture_output=True, text=True, timeout=15)
                else:
                    subprocess.run([
                        "sshpass", "-p", target_password,
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "ConnectTimeout=10",
                        f"{target_user}@{target_host}", server_cmd
                    ], capture_output=True, text=True, timeout=15)
                
            self.logger.info(f"iPerf3 servers started on {target_host}")
            time.sleep(2)  # Allow servers to start
            return True
            
        except Exception as e:
            self.logger.error(f"Exception setting up iPerf3 servers on {target_host}: {e}")
            return False
    
    def setup_ssh_keys(self):
        """Setup SSH keys for passwordless authentication"""
        # On Windows, assume SSH keys are already configured
        if platform.system().lower() == 'windows':
            self.logger.info("Windows detected - using existing SSH configuration")
            # Test SSH connection with appropriate timeout for network latency
            test_cmd = "echo 'SSH test successful'"
            try:
                result = subprocess.run([
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=20",
                    f"{self.ssh_user}@{self.client_ip}", test_cmd
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    self.logger.info("SSH connection test successful")
                    return True
                else:
                    self.logger.error(f"SSH connection test failed: {result.stderr}")
                    return False
            except subprocess.TimeoutExpired:
                self.logger.error(f"SSH connection timeout to {self.client_ip}")
                return False
            except Exception as e:
                self.logger.error(f"SSH test exception: {e}")
                return False
            
        try:
            # Test SSH connection first
            test_cmd = "echo 'SSH test successful'"
            result = subprocess.run([
                "sshpass", "-p", self.ssh_password,
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=30",
                f"{self.ssh_user}@{self.client_ip}", test_cmd
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"SSH connection test failed: {result.stderr.strip()}")
                self.logger.error(f"SSH stdout: {result.stdout.strip()}")
                return False
            
            self.logger.info("SSH connection test successful")
            
            # Generate SSH key if it doesn't exist
            key_path = os.path.expanduser("~/.ssh/lld_key")
            if not os.path.exists(key_path):
                self.logger.info("Generating SSH key for Linux client")
                subprocess.run([
                    "ssh-keygen", "-t", "rsa", "-b", "2048", 
                    "-f", key_path, "-N", "", "-q"
                ], check=True)
            
            # Copy public key to remote host
            pub_key_path = f"{key_path}.pub"
            if os.path.exists(pub_key_path):
                self.logger.info(f"Setting up SSH key for {self.ssh_user}@{self.client_ip}")
                
                # Use ssh-copy-id with proper options
                result = subprocess.run([
                    "sshpass", "-p", self.ssh_password,
                    "ssh-copy-id", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-i", pub_key_path,
                    f"{self.ssh_user}@{self.client_ip}"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    self.logger.info("SSH key setup completed")
                    return True
                else:
                    self.logger.warning(f"SSH key setup failed, will use password auth: {result.stderr}")
                    return True  # Continue with password auth
            else:
                self.logger.error("Public key file not found")
                return True  # Continue with password auth
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"SSH connection timeout after 30 seconds to {self.client_ip}")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"SSH key setup failed: {e}")
            return True  # Continue with password auth
        except Exception as e:
            self.logger.error(f"SSH key setup exception: {e}")
            return True  # Continue with password auth
    
    def run_scenario(self, iteration, total_iterations):
        """Run iPerf3 scenario on appropriate host"""
        if self.scenario_name.startswith('US_'):
            execution_host = self.client_ip
            execution_password = self.ssh_password
            direction = "UPSTREAM"
        else:
            execution_host = self.server_ip
            execution_password = self.server_password
            direction = "DOWNSTREAM"
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"iPerf3 {direction}: {self.scenario_name}")
        self.logger.info(f"Iteration {iteration + 1}/{total_iterations}")
        self.logger.info(f"Host: {execution_host}")
        self.logger.info(f"{'='*60}")
        
        if self.parent_output_dir:
            platform_suffix = "_macOS" if self.platform_override == 'macos' else "_Linux"
            rtt_suffix = self.rtt_suffix if self.rtt_suffix else ""
            scenario_dir = f"{self.scenario_name}{platform_suffix}{rtt_suffix}"
            if total_iterations > 1:
                output_dir = os.path.join(self.parent_output_dir, scenario_dir, f"iteration_{iteration + 1}")
            else:
                output_dir = os.path.join(self.parent_output_dir, scenario_dir)
        else:
            if total_iterations > 1:
                output_dir = os.path.join("Results", f"{self.output_prefix}", f"iteration_{iteration + 1}")
            else:
                output_dir = os.path.join("Results", self.output_prefix)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Get commands for scenario
        commands = self.scenario_commands.get(self.scenario_name)
        if not commands:
            self.logger.error(f"Unknown scenario: {self.scenario_name}")
            return False
        
        try:
            # Create remote directory on execution host
            if self.scenario_name.startswith('US_'):
                # Upstream: run on client
                execution_host = self.client_ip
                execution_user = self.ssh_user
                execution_password = self.ssh_password
                self.logger.info(f"Running iPerf3 scenario: {self.scenario_name} on CLIENT: {self.client_ip} (iteration {iteration + 1})")
            else:
                # Downstream: run on server
                execution_host = self.server_ip
                execution_user = self.server_user
                execution_password = self.server_password
                self.logger.info(f"Running iPerf3 scenario: {self.scenario_name} on SERVER: {self.server_ip} (iteration {iteration + 1})")
            
            # Create remote directory path based on platform
            if self.platform_override == 'macos':
                remote_dir = f"/Users/{execution_user}/{self.output_prefix}"
            else:
                remote_dir = f"/home/{execution_user}/{self.output_prefix}"
            mkdir_cmd = f"mkdir -p {remote_dir}"
            
            # Try SSH key first, fallback to password
            ssh_cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null"
            ]
            
            key_path = os.path.expanduser("~/.ssh/lld_key")
            if os.path.exists(key_path):
                ssh_cmd.extend(["-i", key_path])
                ssh_cmd.append(f"{execution_user}@{execution_host}")
                ssh_cmd.append(mkdir_cmd)
                result = subprocess.run(ssh_cmd, capture_output=True, text=True)
            else:
                # Use password authentication
                result = subprocess.run([
                    "sshpass", "-p", execution_password,
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{execution_user}@{execution_host}", mkdir_cmd
                ], capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Failed to create remote directory: {result.stderr}")
                return False
            
            # Start all commands in background (non-blocking)
            processes = []
            cmd_count = len([c for c in commands if c != "wait"])
            self.logger.info(f"Starting {cmd_count} parallel flows...")
            
            for idx, cmd in enumerate(commands, 1):
                if cmd == "wait":
                    continue
                
                full_cmd = f"cd {remote_dir} && {cmd}"
                flow_name = cmd.split('>')[1].strip() if '>' in cmd else cmd[:40]
                self.logger.info(f"  [{idx}/{cmd_count}] {flow_name}")
                
                # Try SSH key first, fallback to password
                key_path = os.path.expanduser("~/.ssh/lld_key")
                if os.path.exists(key_path):
                    proc = subprocess.Popen([
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        "-i", key_path,
                        f"{execution_user}@{execution_host}", full_cmd
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                else:
                    proc = subprocess.Popen([
                        "sshpass", "-p", execution_password,
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        f"{execution_user}@{execution_host}", full_cmd
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                processes.append(proc)
            
            # Wait for all processes to complete
            self.logger.info(f"Waiting for flows to complete (30s timeout)...")
            for idx, proc in enumerate(processes, 1):
                stdout, stderr = proc.communicate()
                if proc.returncode != 0:
                    self.logger.error(f"Flow {idx} failed: {stderr}")
                else:
                    self.logger.info(f"Flow {idx} completed")
            
            # Check final results
            wait_cmd = f"cd {remote_dir} && ls -la"
            
            key_path = os.path.expanduser("~/.ssh/lld_key")
            if os.path.exists(key_path):
                result = subprocess.run([
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-i", key_path,
                    f"{execution_user}@{execution_host}", wait_cmd
                ], capture_output=True, text=True)
            else:
                result = subprocess.run([
                    "sshpass", "-p", execution_password,
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{execution_user}@{execution_host}", wait_cmd
                ], capture_output=True, text=True)
            
            # Log command output
            log_content = f"\\n=== iPerf3 Individual Execution ===\\n"
            log_content += f"Return code: {result.returncode}\\n"
            log_content += f"STDOUT:\\n{result.stdout}\\n"
            log_content += f"STDERR:\\n{result.stderr}\\n"
            self.log_rotator.write_log(log_content)
            
            if result.returncode != 0:
                self.logger.error(f"iPerf3 execution failed: {result.stderr}")
                return False
            
            # Copy results directly to output directory
            key_path = os.path.expanduser("~/.ssh/lld_key")
            if os.path.exists(key_path):
                scp_cmd = [
                    "scp", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-i", key_path,
                    f"{execution_user}@{execution_host}:{remote_dir}/*",
                    output_dir
                ]
            else:
                scp_cmd = [
                    "sshpass", "-p", execution_password,
                    "scp", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"{execution_user}@{execution_host}:{remote_dir}/*",
                    output_dir
                ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Failed to copy results: {result.stderr}")
                return False
            
            result_files = [f for f in os.listdir(output_dir) if f.endswith(('.json', '.txt'))]
            self.logger.info(f"✓ Iteration {iteration + 1} completed - {len(result_files)} result files")
            
            # Wait 10 seconds between iterations (except after last iteration)
            if iteration < total_iterations - 1:
                time.sleep(10)
            
            return True
            
        except Exception as e:
            error_msg = f"iPerf3 execution exception: {str(e)}"
            self.logger.error(error_msg)
            self.log_rotator.write_log(f"\\nERROR: {error_msg}\\n")
            return False
    
    def run_iterations(self, count=1):
        """Run multiple iPerf3 iterations"""
        self.logger.info(f"Starting {count} iPerf3 iterations")
        
        # Setup SSH keys first
        if not self.setup_ssh_keys():
            self.logger.error("SSH key setup failed, cannot proceed")
            return False
        
        # Setup iPerf3 servers
        if not self.setup_iperf3_servers():
            self.logger.error("iPerf3 server setup failed, cannot proceed")
            return False
        
        success_count = 0
        
        for i in range(count):
            if self.run_scenario(i, count):
                success_count += 1
            else:
                self.logger.error(f"Iteration {i + 1} failed")
            
            # Wait 10 seconds between iterations (except after last iteration)
            if i < count - 1:
                self.logger.info("Waiting 10 seconds before next iteration...")
                time.sleep(10)
        
        self.logger.info(f"iPerf3 completed: {success_count}/{count} iterations successful")
        
        # Stop iPerf3 servers after completion
        self.stop_iperf3_servers()
        
        return success_count == count
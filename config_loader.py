#!/usr/bin/env python3
import yaml
import os
import sys

class Config:
    """Configuration loader for LLD Test CLI Tool"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path=None):
        """Load configuration from YAML file"""
        if config_path is None:
            # Look for config.yaml in current directory or script directory
            current_dir = os.getcwd()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            if os.path.exists(os.path.join(current_dir, 'config.yaml')):
                config_path = os.path.join(current_dir, 'config.yaml')
            elif os.path.exists(os.path.join(script_dir, 'config.yaml')):
                config_path = os.path.join(script_dir, 'config.yaml')
            else:
                print("ERROR: config.yaml not found!")
                print(f"Searched in: {current_dir} and {script_dir}")
                print("Please create config.yaml from config.yaml.example")
                sys.exit(1)
        
        try:
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            print(f"Configuration loaded from: {config_path}")
        except Exception as e:
            print(f"ERROR: Failed to load config.yaml: {e}")
            sys.exit(1)
    
    def get(self, *keys, default=None):
        """Get configuration value by nested keys"""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    # ByteBlower
    @property
    def byteblower_cli_path(self):
        return os.path.expanduser(self.get('byteblower', 'cli_path'))
    
    @property
    def byteblower_bb_flows_dir(self):
        return self.get('byteblower', 'bb_flows_dir', default='bb_flows')
    
    # PacketStorm
    @property
    def packetstorm_url(self):
        return self.get('packetstorm', 'url')
    
    @property
    def packetstorm_username(self):
        return self.get('packetstorm', 'username')
    
    @property
    def packetstorm_password(self):
        return self.get('packetstorm', 'password')
    
    @property
    def packetstorm_timeout(self):
        return self.get('packetstorm', 'timeout', default=30)
    
    # iPerf3 Linux
    @property
    def iperf3_linux_client_host(self):
        return self.get('iperf3_linux', 'client', 'host')
    
    @property
    def iperf3_linux_client_username(self):
        return self.get('iperf3_linux', 'client', 'username')
    
    @property
    def iperf3_linux_client_password(self):
        return self.get('iperf3_linux', 'client', 'password')
    
    @property
    def iperf3_linux_server_host(self):
        return self.get('iperf3_linux', 'server', 'host')
    
    @property
    def iperf3_linux_server_username(self):
        return self.get('iperf3_linux', 'server', 'username')
    
    @property
    def iperf3_linux_server_password(self):
        return self.get('iperf3_linux', 'server', 'password')
    
    @property
    def iperf3_linux_ports(self):
        return self.get('iperf3_linux', 'ports', default=[9202, 9205, 9206, 9210])
    
    # iPerf3 macOS
    @property
    def iperf3_macos_client_host(self):
        return self.get('iperf3_macos', 'client', 'host')
    
    @property
    def iperf3_macos_client_username(self):
        return self.get('iperf3_macos', 'client', 'username')
    
    @property
    def iperf3_macos_client_password(self):
        return self.get('iperf3_macos', 'client', 'password')
    
    @property
    def iperf3_macos_server_host(self):
        return self.get('iperf3_macos', 'server', 'host')
    
    @property
    def iperf3_macos_server_username(self):
        return self.get('iperf3_macos', 'server', 'username')
    
    @property
    def iperf3_macos_server_password(self):
        return self.get('iperf3_macos', 'server', 'password')
    
    @property
    def iperf3_macos_ports(self):
        return self.get('iperf3_macos', 'ports', default=[9201, 9207, 9209, 9211])
    
    # SpeedTest
    def speedtest_client_config(self, client_name):
        """Get SpeedTest client configuration"""
        return self.get('speedtest', client_name.lower(), default={})
    
    # SNMP
    @property
    def snmp_jumpserver(self):
        return self.get('snmp', 'jumpserver')
    
    @property
    def snmp_username(self):
        return self.get('snmp', 'username')
    
    @property
    def snmp_community(self):
        return self.get('snmp', 'community', default='open')
    
    @property
    def snmp_timeout(self):
        return self.get('snmp', 'timeout', default=5)
    
    @property
    def snmp_retries(self):
        return self.get('snmp', 'retries', default=2)
    
    # SSH
    @property
    def ssh_key_path(self):
        return os.path.expanduser(self.get('ssh', 'key_path', default='~/.ssh/lld_key'))
    
    @property
    def ssh_connect_timeout(self):
        return self.get('ssh', 'connect_timeout', default=20)
    
    @property
    def ssh_command_timeout(self):
        return self.get('ssh', 'command_timeout', default=30)

# Singleton instance
config = Config()

# NetPerf Orchestrator - Setup Guide

## Quick Start

### 1. Create Configuration File
```bash
cp config.yaml.example config.yaml
nano config.yaml  # Edit for your environment
chmod 600 config.yaml
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
sudo apt install -y sshpass openssh-client  # Linux only
```

### 3. Configure Settings
Edit `config.yaml` with your:
- ByteBlower CLI path
- PacketStorm URL and credentials
- iPerf3 client/server IPs and credentials
- SpeedTest client IPs and credentials
- SNMP jump server and credentials

## ByteBlower Setup

```bash
# Install ByteBlower CLI
tar -xzf ByteBlower-CLT-*.tar.gz -C /opt/

# Update config.yaml
byteblower:
  cli_path: "/opt/ByteBlower-CLT"
  bb_flows_dir: "bb_flows"
```

## iPerf3 Setup

### Linux Client
```bash
# Install iPerf3 with Prague support
git clone https://github.com/L4STeam/iperf.git
cd iperf && ./bootstrap.sh && ./configure && make && sudo make install

# Enable Prague congestion control
sudo sysctl net.ipv4.tcp_congestion_control=prague

# Configure SSH
sudo apt install openssh-server
sudo useradd -m -s /bin/bash lld
echo "lld:aqm@2024" | sudo chpasswd
```

### macOS Client
```bash
# Install iperf3-darwin
brew install iperf3

# Enable Remote Login
sudo systemsetup -setremotelogin on
```

## SpeedTest Setup

### Linux
```bash
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
sudo apt install speedtest
speedtest --accept-license
```

### macOS
```bash
brew tap teamookla/speedtest
brew install speedtest --force
speedtest --accept-license
```

### Windows
```powershell
# Download from https://www.speedtest.net/apps/cli
# Extract to C:\Users\Administrator\Desktop\ookla-speedtest-1.2.0-win64\

# Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
```

## SSH Key Setup

```bash
# Generate SSH key
ssh-keygen -t rsa -b 2048 -f ~/.ssh/lld_key -N ""

# Deploy to clients
ssh-copy-id -i ~/.ssh/lld_key.pub lld@96.37.176.19  # Linux
ssh-copy-id -i ~/.ssh/lld_key.pub lld_mac_client@96.37.176.11  # macOS
ssh-copy-id -i ~/.ssh/lld_key.pub aphillips@ctec-jump.ctec.charterlab.com  # Jump server
```

## SNMP Setup

```bash
# On jump server
sudo apt install -y snmp snmp-mibs-downloader
sudo sed -i 's/mibs :/# mibs :/g' /etc/snmp/snmp.conf

# Test SNMP
snmpwalk -v 2c -c open -t 5 -r 2 YOUR_MODEM_IP sysDescr
```

## Troubleshooting

### Config not found
```bash
ls -la config.yaml
cp config.yaml.example config.yaml
```

### YAML syntax error
```bash
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### SSH connection failed
```bash
ssh -i ~/.ssh/lld_key lld@96.37.176.19
```

### ByteBlower CLI not found
```bash
/path/to/ByteBlower-CLT --version
```

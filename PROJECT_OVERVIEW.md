# NetPerf Orchestrator

**Network Performance Testing Orchestration Tool**

[![Version](https://img.shields.io/badge/version-1.3-blue.svg)](VERSION)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

## Overview

NetPerf Orchestrator is a comprehensive network performance testing framework that orchestrates multiple industry-standard tools for automated network quality assessment. It provides unified CLI interface for ByteBlower, PacketStorm, iPerf3, and SpeedTest with integrated SNMP metrics collection.

## Key Features

- **Multi-Tool Integration**: Seamlessly orchestrates ByteBlower, PacketStorm, iPerf3, and SpeedTest
- **Automated Testing**: Configurable iterations with intelligent result organization
- **SNMP Metrics**: Real-time network metrics collection before/after tests
- **RTT Simulation**: PacketStorm integration for latency testing (10ms-50ms)
- **Cross-Platform**: Linux and macOS support with Apple QUIC/L4S
- **Configuration Management**: YAML-based configuration for easy environment portability
- **Professional Reporting**: Multiple output formats (HTML, PDF, CSV, JSON, Excel)

## Use Cases

- **Network QoS Testing**: Validate Quality of Service configurations
- **Low Latency Testing**: L4S and Low Latency DOCSIS (LLD) validation
- **Performance Benchmarking**: Comprehensive throughput and latency analysis
- **CI/CD Integration**: Automated network regression testing
- **Multi-Client Testing**: Parallel testing across Linux, macOS, and Windows clients

## Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/netperf-orchestrator.git
cd netperf-orchestrator

# Setup configuration
cp config.yaml.example config.yaml
nano config.yaml

# Install dependencies
pip install -r requirements.txt

# Run test
./netperf -byteblower --bbp Port_20_example.bbp --scenario US_Classic_Only -test-group-name TEST_001
```

## Architecture

```
NetPerf Orchestrator
├── ByteBlower Integration    → Traffic generation & analysis
├── PacketStorm Integration    → RTT/latency simulation
├── iPerf3 Integration         → Linux/macOS throughput testing
├── SpeedTest Integration      → Real-world performance testing
└── SNMP Collector            → Network metrics collection
```

## Supported Test Scenarios

- **Upstream/Downstream Classic**: Traditional service flows
- **Upstream/Downstream Combined**: Classic + Low Latency mixed traffic
- **Upstream/Downstream LL Only**: Pure Low Latency flows
- **Non-Conforming Traffic**: UDP/TCP stress testing

## Technologies

- **Python 3.8+**: Core orchestration engine
- **ByteBlower CLI**: Professional traffic generation
- **PacketStorm API**: Network impairment simulation
- **iPerf3/iPerf3-darwin**: Throughput measurement
- **SNMP**: Real-time metrics collection
- **SSH/Paramiko**: Remote test execution

## Professional Applications

- Network equipment validation
- ISP quality assurance testing
- DOCSIS 3.1/4.0 certification
- Low Latency DOCSIS (LLD) testing
- Apple L4S protocol validation
- Multi-vendor interoperability testing

## Documentation

- [Setup Guide](SETUP_GUIDE.md) - Complete installation instructions
- [README](README.md) - Comprehensive usage documentation
- [Configuration](config.yaml.example) - Configuration reference

## Requirements

- Python 3.8+
- ByteBlower CLI (optional)
- PacketStorm appliance (optional)
- iPerf3 clients/servers (optional)
- SNMP-enabled network devices

## Contributing

Contributions welcome! This tool is designed for network engineers and QA professionals working with DOCSIS, L4S, and low-latency networking technologies.

## Author

**Andrew Phillips**
- Network Performance Testing Specialist
- DOCSIS & Low Latency Technologies
- [LinkedIn](https://www.linkedin.com/in/yourprofile)
- [GitHub](https://github.com/yourusername)

## Version History

- **v1.3** (2025-01-16): Configuration file system, professional rebranding
- **v1.2** (2025-01-15): Documentation consolidation
- **v1.1** (2025-01-15): SpeedTest integration
- **v1.0** (2025-01-03): Initial release

---

*NetPerf Orchestrator - Professional Network Performance Testing*

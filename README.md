# NetPerf API v2.0

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-netperf--api-black.svg)](https://github.com/birdyphillips/netperf-api)

REST API for automated DOCSIS 3.1 and 4.0 network performance testing with ByteBlower, iPerf3, PacketStorm, and SpeedTest. Provides HTTP endpoints for running comprehensive network tests with SNMP monitoring, RTT configuration, and multi-scenario support.

## 🚀 Features

- **16 REST API Endpoints** - Complete HTTP interface for all test operations
- **ByteBlower Integration** - Automated traffic generation and analysis
- **iPerf3 Support** - Linux (TCP/Prague) and macOS (Apple QUIC/L4S) testing
- **PacketStorm RTT** - Configurable round-trip time emulation
- **SpeedTest** - Multi-client speed testing (Linux, macOS, Windows)
- **SNMP Monitoring** - Automatic before/after data collection with delta analysis
- **Async Execution** - Background test execution with status polling
- **Result Management** - UUID-based result identification, ZIP downloads, file browsing
- **Multi-Scenario** - Run multiple test scenarios in single API call
- **CORS Enabled** - Ready for web frontend integration
- **Postman Collection** - Pre-configured API testing collection included

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [API Endpoints](#-api-endpoints)
- [Test Types](#-test-types)
- [Usage Examples](#-usage-examples)
- [Scenarios](#-scenarios)
- [Advanced Usage](#-advanced-usage)
- [Configuration](#-configuration)
- [Postman Collection](#-postman-collection)
- [Architecture](#-architecture)
- [Contributing](#-contributing)

## 🎯 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp config.yaml.example config.yaml
nano config.yaml  # Edit for your environment
```

### 3. Start API Server
```bash
# Start in background
./start_api.sh

# Stop server
./stop_api.sh

# View logs
tail -f api.log
```

Server runs on `http://0.0.0.0:5000`

### Web UI
Access the interactive API documentation at:
- **Local**: http://localhost:5000/
- **Remote**: http://24.28.218.10:5000/

Swagger-like interface with all 16 endpoints, try-it-out functionality, and live response display.

## 📡 API Endpoints

### Health & Configuration
- `GET /health` - Health check
- `POST /api/config/modem` - Set modem IPv6 for SNMP
- `GET /api/cmts/modem/info` - Get CMTS modem information

### Test Execution
- `POST /api/byteblower/run` - ByteBlower tests
- `POST /api/iperf3/run` - iPerf3 tests (Linux/macOS)
- `POST /api/speedtest/run` - SpeedTest
- `POST /api/packetstorm/start` - Start RTT config
- `POST /api/packetstorm/stop` - Stop RTT config

### SNMP
- `POST /api/snmp/collect` - Manual SNMP collection
- `GET /api/results/{result_id}/snmp` - SNMP analysis with deltas

### Test Management
- `GET /api/test/status/{test_id}` - Async test status
- `GET /api/test/list` - List all tests

### Results
- `GET /api/results` - List all results
- `GET /api/results/{result_id}` - Get result files
- `GET /api/results/{result_id}/download` - Download ZIP
- `GET /api/results/{result_id}/download/{file_path}` - Download file

### Resources
- `GET /api/bb_flows` - List ByteBlower flows

**Total: 17 endpoints**

---

## 🧪 Test Types

### ByteBlower
High-performance traffic generation and analysis with:
- Multiple traffic scenarios (US/DS, Classic/LL/Combined)
- Configurable RTT via PacketStorm
- HTML/PDF/CSV/JSON/Excel report generation
- Automatic SNMP collection per iteration

### iPerf3
**Linux:** TCP (cubic/prague) and UDP testing
**macOS:** Apple QUIC with L4S support
- Multi-scenario support
- Configurable iterations
- Platform-specific optimizations

### PacketStorm
RTT emulation for latency testing:
- Start/stop configurations
- Multiple RTT profiles (10ms, 20ms, 30ms, etc.)

### SpeedTest
Multi-client speed testing:
- Linux, macOS, Windows (NVIDIA) clients
- Parallel execution
- Configurable iterations

---

## 📚 API Endpoints

### Health Check
```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-16T10:30:00"
}
```

---

### Set Modem IPv6
```bash
POST /api/config/modem
Content-Type: application/json

{
  "ipv6": "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
}
```

**Response:**
```json
{
  "message": "Modem IPv6 set",
  "ipv6": "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
}
```

---

### ByteBlower Test
```bash
POST /api/byteblower/run
Content-Type: application/json

{
  "bbp_file": "Port_20_example.bbp",
  "scenario": "US_Classic_Only",
  "test_group_name": "TEST_SCN_RTT_0",
  "iterations": 1,
  "rtt_config": "vcmts10ms.json",
  "async": false
}
```

**Parameters:**
- `bbp_file`: ByteBlower project file (required)
- `scenario`: Test scenario name - single or comma-separated (required, e.g., "US_Classic_Only" or "US_Classic_Only,DS_Classic_Only")
- `test_group_name`: Test group identifier (required)
- `iterations`: Number of test iterations (default: 1)
- `rtt_config`: PacketStorm RTT config file - single or comma-separated (optional, e.g., "vcmts10ms.json" or "vcmts10ms.json,vcmts20ms.json")
- `async`: Run test in background (default: false)

**Synchronous Response (async: false):**
```json
{
  "success": true,
  "output_dir": "Results/TEST_SCN_RTT_0_ByteBlower_RTT_10ms_20250225_185300",
  "scenarios": 1,
  "rtt_configs": 1,
  "iterations": 1
}
```

**Asynchronous Response (async: true):**
```json
{
  "test_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "message": "Test started in background"
}
```

**Single Scenario:**
```json
{
  "bbp_file": "Port_20_example.bbp",
  "scenario": "US_Classic_Only",
  "test_group_name": "TEST_SCN_RTT_10",
  "iterations": 1,
  "rtt_config": "vcmts10ms.json"
}
```

**Multiple Scenarios:**
```json
{
  "bbp_file": "Port_20_example.bbp",
  "scenario": "US_Classic_Only,DS_Classic_Only,US_Combined",
  "test_group_name": "TEST_SCN_RTT_10",
  "iterations": 1,
  "rtt_config": "vcmts10ms.json"
}
```

**Multiple RTT Configs:**
```json
{
  "bbp_file": "Port_20_example.bbp",
  "scenario": "US_Classic_Only",
  "test_group_name": "TEST_SCN_RTT",
  "iterations": 1,
  "rtt_config": "vcmts10ms.json,vcmts20ms.json,vcmts30ms.json"
}
```

**Response:**
```json
{
  "success": true,
  "output_dir": "Results/TEST_SCN_RTT_0_ByteBlower_RTT_10ms_20250225_185300",
  "iterations": 1
}
```

**Output Structure:**
```
Results/TEST_SCN_RTT_0_ByteBlower_RTT_10ms_20250225_185300/
├── US_Classic_Only_RTT_10ms/
│   ├── ByteBlower_US_Classic_Only_iteration_1_SNMP_before_*.txt
│   ├── ByteBlower_US_Classic_Only_iteration_1_SNMP_after_*.txt
│   ├── US_Classic_Only - 20250225_185300_1.csv
│   ├── US_Classic_Only - 20250225_185300_1.json
│   └── US_Classic_Only - 20250225_185300_1_R2_1.html
```

---

### PacketStorm Start
```bash
POST /api/packetstorm/start
Content-Type: application/json

{
  "rtt_config": "vcmts10ms.json"
}
```

**Response:**
```json
{
  "success": true,
  "config": "vcmts10ms.json"
}
```

---

### PacketStorm Stop
```bash
POST /api/packetstorm/stop
Content-Type: application/json

{
  "rtt_config": "vcmts10ms.json"
}
```

**Response:**
```json
{
  "success": true
}
```

---

### iPerf3 Test
```bash
POST /api/iperf3/run
Content-Type: application/json

{
  "client_ip": "96.37.176.19",
  "scenario": "US_Classic_Only",
  "test_group_name": "TEST_SCN_RTT_0",
  "iterations": 1,
  "output_format": "json",
  "platform": "linux",
  "rtt_config": "vcmts10ms.json"
}
```

**Parameters:**
- `client_ip`: Client IP address (required)
- `scenario`: Test scenario name - single or comma-separated (required)
- `test_group_name`: Test group identifier (required)
- `iterations`: Number of test iterations (default: 1)
- `output_format`: `"json"` or `"txt"` (default: "json")
- `platform`: `"linux"` or `"macos"` (default: "linux")
- `rtt_config`: PacketStorm RTT config file - single or comma-separated (optional)

**Linux Example:**
```json
{
  "client_ip": "96.37.176.19",
  "scenario": "US_Classic_Only",
  "test_group_name": "TEST_SCN_RTT_0",
  "iterations": 1,
  "platform": "linux",
  "rtt_config": "vcmts10ms.json"
}
```

**macOS Example (Apple QUIC/L4S):**
```json
{
  "client_ip": "96.37.176.19",
  "scenario": "US_Combined",
  "test_group_name": "TEST_SCN_RTT_0",
  "iterations": 1,
  "platform": "macos",
  "rtt_config": "vcmts10ms.json"
}
```

**Response:**
```json
{
  "success": true,
  "output_dir": "Results/TEST_SCN_RTT_0_iPerf3_Linux_RTT_10ms_20250225_185300",
  "iterations": 1
}
```

**Output Structure:**
```
Results/TEST_SCN_RTT_0_iPerf3_Linux_RTT_10ms_20250225_185300/
├── US_Classic_Only_Linux_RTT_10ms/
│   ├── iPerf3_Linux_US_Classic_Only_iteration_1_SNMP_before_*.txt
│   ├── iPerf3_Linux_US_Classic_Only_iteration_1_SNMP_after_*.txt
│   ├── US_TEST_SCN_Classic_Only_4TCP_CL.txt
│   └── US_TEST_SCN_Classic_Only_1UDP_CL.txt
```

**macOS Output Structure:**
```
Results/TEST_SCN_RTT_0_iPerf3_macOS_RTT_10ms_20250225_185300/
├── US_Combined_macOS_RTT_10ms/
│   ├── iPerf3_macOS_US_Combined_iteration_1_SNMP_before_*.txt
│   ├── iPerf3_macOS_US_Combined_iteration_1_SNMP_after_*.txt
│   ├── US_TEST_SCN_Combined_4QUIC_CL.txt
│   ├── US_TEST_SCN_Combined_1QUIC_LL.txt
│   ├── US_TEST_SCN_Combined_1UDP_CL.txt
│   └── US_TEST_SCN_Combined_1UDP_LL.txt
```

---

### SpeedTest
```bash
POST /api/speedtest/run
Content-Type: application/json

{
  "clients": ["linux", "macos", "nvidia"],
  "test_group_name": "Speedtest",
  "iterations": 3
}
```

**Response:**
```json
{
  "success": true,
  "clients": ["linux", "macos", "nvidia"],
  "iterations": 3
}
```

---

### SNMP Collection
```bash
POST /api/snmp/collect
Content-Type: application/json

{
  "target_ip": "2605:1c00:50f2:203:a49d:6fa2:3d34:7329",
  "test_name": "TEST_SCN_RTT_0",
  "phase": "before",
  "output_dir": "Results"
}
```

**Parameters:**
- `phase`: `"before"` or `"after"`

**Response:**
```json
{
  "success": true,
  "phase": "before"
}
```

---

### Get Test Status
```bash
GET /api/test/status/{test_id}
```

**Example:**
```bash
GET /api/test/status/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "status": "completed",
  "type": "byteblower",
  "started": "2025-02-25T18:53:00",
  "completed": "2025-02-25T18:58:00",
  "output_dir": "Results/TEST_SCN_RTT_0_ByteBlower_20250225_185300",
  "result": {
    "success": true,
    "output_dir": "Results/TEST_SCN_RTT_0_ByteBlower_20250225_185300",
    "scenarios": 1,
    "rtt_configs": 1,
    "iterations": 1
  }
}
```

**Status Values:**
- `running` - Test in progress
- `completed` - Test finished successfully
- `failed` - Test finished with errors
- `error` - Test encountered exception

---

### List All Tests
```bash
GET /api/test/list
```

**Response:**
```json
{
  "tests": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "status": "completed",
      "type": "byteblower",
      "started": "2025-02-25T18:53:00",
      "completed": "2025-02-25T18:58:00",
      "output_dir": "Results/TEST_SCN_RTT_0_ByteBlower_20250225_185300"
    }
  }
}
```

---

### List Results
```bash
GET /api/results
```

**Response:**
```json
{
  "results": [
    {
      "id": "c3865f92-d53d-4d05-bc0e-a5b516f0afff",
      "name": "TEST_SCN_RTT_0_ByteBlower_20250116_103000",
      "path": "Results/TEST_SCN_RTT_0_ByteBlower_20250116_103000",
      "created": "2025-01-16T10:30:00"
    }
  ]
}
```

---

### Get Result Files
```bash
GET /api/results/{result_id}
```

**Example:**
```bash
GET /api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff
```

**Response:**
```json
{
  "files": [
    {
      "name": "US_Classic_Only.csv",
      "path": "US_Classic_Only.csv",
      "size": 2048
    }
  ]
}
```

---

### Get SNMP Analysis
```bash
GET /api/results/{result_id}/snmp
```

**Example:**
```bash
GET /api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff/snmp
```

**Response:**
```json
{
  "result_id": "c3865f92-d53d-4d05-bc0e-a5b516f0afff",
  "iterations": [
    {
      "iteration": 1,
      "before_file": "ByteBlower_US_Classic_Only_iteration_1_SNMP_before_20250116_103000.txt",
      "after_file": "ByteBlower_US_Classic_Only_iteration_1_SNMP_after_20250116_103500.txt",
      "metrics": {
        "ifHCInOctets": {
          "before": 1234567890,
          "after": 1235616466,
          "delta": 1048576
        },
        "ifHCOutOctets": {
          "before": 9876543210,
          "after": 9877067498,
          "delta": 524288
        },
        "ifInUcastPkts": {
          "before": 100000,
          "after": 101000,
          "delta": 1000
        },
        "ifOutUcastPkts": {
          "before": 95000,
          "after": 95800,
          "delta": 800
        }
      }
    }
  ]
}
```

---

### Download Result Folder (ZIP)
```bash
GET /api/results/{result_id}/download
```

**Example:**
```bash
GET /api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff/download
```

Returns entire folder as ZIP file.

---

### Download Result File
```bash
GET /api/results/{result_id}/download/{file_path}
```

**Example:**
```bash
GET /api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff/download/US_Classic_Only/results.csv
```

Returns individual file as attachment.

---

### List ByteBlower Flows
```bash
GET /api/bb_flows
```

**Response:**
```json
{
  "bb_flows": [
    {
      "name": "Port_20_example.bbp",
      "path": "bb_flows/Port_20_example.bbp",
      "size": 12345
    }
  ]
}
```

---

## 💻 Usage Examples

### Python
```python
import requests
import time

BASE_URL = 'http://24.28.218.10:5000'

# 1. Set modem IPv6
requests.post(f'{BASE_URL}/api/config/modem', 
              json={'ipv6': '2605:1c00:50f2:203:a49d:6fa2:3d34:7329'})

# 2. Run ByteBlower test asynchronously
response = requests.post(f'{BASE_URL}/api/byteblower/run', json={
    'bbp_file': 'Port_20_example.bbp',
    'scenario': 'US_Classic_Only',
    'test_group_name': 'TEST_SCN_RTT_10',
    'iterations': 1,
    'rtt_config': 'vcmts10ms.json',
    'async': True
})
test_id = response.json()['test_id']
print(f"Test started: {test_id}")

# 3. Poll test status
while True:
    status = requests.get(f'{BASE_URL}/api/test/status/{test_id}').json()
    print(f"Status: {status['status']}")
    if status['status'] in ['completed', 'failed', 'error']:
        break
    time.sleep(10)

# 4. Get result ID from results list
results = requests.get(f'{BASE_URL}/api/results').json()
result_id = results['results'][0]['id']

# 5. Download results by ID
zip_file = requests.get(f'{BASE_URL}/api/results/{result_id}/download')
with open('results.zip', 'wb') as f:
    f.write(zip_file.content)
print(f"Results downloaded: results.zip")

# 6. Get SNMP analysis
snmp_data = requests.get(f'{BASE_URL}/api/results/{result_id}/snmp').json()
print(f"SNMP deltas: {snmp_data['scenarios']}")
```

### cURL
```bash
BASE_URL="http://24.28.218.10:5000"

# 1. Set modem IPv6
curl -X POST $BASE_URL/api/config/modem \
  -H "Content-Type: application/json" \
  -d '{"ipv6": "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"}'

# 2. List available ByteBlower flows
curl $BASE_URL/api/bb_flows

# 3. Run iPerf3 test with RTT
curl -X POST $BASE_URL/api/iperf3/run \
  -H "Content-Type: application/json" \
  -d '{
    "client_ip": "96.37.176.19",
    "scenario": "US_Classic_Only",
    "test_group_name": "TEST_SCN_RTT_10",
    "iterations": 1,
    "platform": "linux",
    "rtt_config": "vcmts10ms.json"
  }'

# 4. List results and get ID
curl $BASE_URL/api/results

# 5. Download entire result folder as ZIP by ID
curl -O -J $BASE_URL/api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff/download

# 6. Get SNMP analysis by ID
curl $BASE_URL/api/results/c3865f92-d53d-4d05-bc0e-a5b516f0afff/snmp
```

### JavaScript
```javascript
const BASE_URL = 'http://24.28.218.10:5000';

// 1. Set modem IPv6
await fetch(`${BASE_URL}/api/config/modem`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({ipv6: '2605:1c00:50f2:203:a49d:6fa2:3d34:7329'})
});

// 2. Run SpeedTest
const response = await fetch(`${BASE_URL}/api/speedtest/run`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    clients: ['linux', 'macos'],
    test_group_name: 'Speedtest',
    iterations: 1
  })
});
const result = await response.json();
console.log(`Test completed: ${result.output_dir}`);

// 3. List all results
const results = await fetch(`${BASE_URL}/api/results`).then(r => r.json());
console.log(results.results);
```

## 🎯 Scenarios

All endpoints support these scenarios:
- `US_Classic_Only` - Upstream Classic (4 TCP + 1 UDP)
- `DS_Classic_Only` - Downstream Classic (4 TCP + 1 UDP)
- `US_Combined` - Upstream Classic + Low Latency (4 TCP Classic + 1 TCP LL + 1 UDP Classic + 1 UDP LL)
- `DS_Combined` - Downstream Classic + Low Latency (4 TCP Classic + 1 TCP LL + 1 UDP Classic + 1 UDP LL)
- `US_LL_Only` - Upstream Low Latency (1 TCP + 1 UDP with DSCP 45)
- `DS_LL_Only` - Downstream Low Latency (1 TCP + 1 UDP with DSCP 45)

## CLI Capabilities Supported

✅ **All test types**: ByteBlower, PacketStorm, iPerf3 (Linux/macOS), SpeedTest
✅ **Multiple scenarios**: Comma-separated scenarios in single request
✅ **Multiple RTT configs**: Comma-separated RTT configs for comprehensive testing
✅ **Automatic SNMP**: Before/after collection for each iteration
✅ **Iterations**: Configurable test repetitions with 10s intervals
✅ **Result management**: List, browse, download files or entire folders
✅ **Exact folder structure**: Matches CLI output organization
✅ **Platform support**: Linux and macOS iPerf3 with Apple QUIC/L4S
✅ **Multi-client SpeedTest**: Linux, macOS, and Windows NVIDIA clients

## 🚀 Advanced Usage

### Run All SCN RTT Tests (36 combinations)
```python
import requests

BASE_URL = 'http://24.28.218.10:5000'

# Set modem
requests.post(f'{BASE_URL}/api/config/modem',
              json={'ipv6': '2605:1c00:50f2:203:a49d:6fa2:3d34:7329'})

# Run all 6 scenarios with all 6 RTT configs = 36 tests
response = requests.post(f'{BASE_URL}/api/byteblower/run', json={
    'bbp_file': 'Port_20_example.bbp',
    'scenario': 'US_Classic_Only,DS_Classic_Only,US_Combined,DS_Combined,US_LL_Only,DS_LL_Only',
    'test_group_name': 'TEST_SCN_RTT',
    'iterations': 1,
    'rtt_config': 'vcmts10ms.json,vcmts20ms.json,vcmts30ms.json,vcmts40ms.json,vcmts50ms.json'
})

print(f"Completed {response.json()['scenarios']} scenarios × {response.json()['rtt_configs']} RTT configs")
```

### ByteBlower + PacketStorm Workflow
```python
# 1. Start PacketStorm
requests.post(f'{BASE_URL}/api/packetstorm/start',
              json={'rtt_config': 'vcmts10ms.json'})

# 2. Run ByteBlower test
requests.post(f'{BASE_URL}/api/byteblower/run', json={
    'bbp_file': 'Port_20_example.bbp',
    'scenario': 'US_Classic_Only',
    'test_group_name': 'TEST_SCN_RTT_10',
    'iterations': 3,
    'rtt_config': 'vcmts10ms.json'
})

# 3. Stop PacketStorm
requests.post(f'{BASE_URL}/api/packetstorm/stop',
              json={'rtt_config': 'vcmts10ms.json'})
```

### iPerf3 Multi-Scenario Test
```bash
curl -X POST http://24.28.218.10:5000/api/iperf3/run \
  -H "Content-Type: application/json" \
  -d '{
    "client_ip": "96.37.176.19",
    "scenario": "US_Classic_Only,DS_Classic_Only,US_Combined",
    "test_group_name": "TEST_SCN_RTT_10",
    "iterations": 1,
    "platform": "linux",
    "rtt_config": "vcmts10ms.json"
  }'
```

### iPerf3 macOS Test (Apple QUIC/L4S)
```bash
curl -X POST http://24.28.218.10:5000/api/iperf3/run \
  -H "Content-Type: application/json" \
  -d '{
    "client_ip": "96.37.176.19",
    "scenario": "US_Combined",
    "test_group_name": "TEST_SCN_RTT_10",
    "iterations": 1,
    "platform": "macos",
    "rtt_config": "vcmts10ms.json"
  }'
```assic_Only` - Upstream Classic
- `DS_Classic_Only` - Downstream Classic
- `US_Combined` - Upstream Classic + Low Latency
- `DS_Combined` - Downstream Classic + Low Latency
- `US_LL_Only` - Upstream Low Latency
- `DS_LL_Only` - Downstream Low Latency

## Error Responses

```json
{
  "error": "Error message description"
}
```

HTTP Status Codes:
- `200` - Success
- `400` - Bad Request (missing parameters)
- `404` - Not Found
- `500` - Internal Server Error

## ⚙️ Configuration

Edit `config.yaml` for:
- ByteBlower CLI path
- PacketStorm URL/credentials
- iPerf3 client/server IPs
- SpeedTest client IPs
- SNMP settings
- SSH credentials

## Server Management

```bash
# Start server
./start_api.sh

# Stop server
./stop_api.sh

# View logs
tail -f api.log

# Check status
ps aux | grep app.py
```

## Production Deployment

### Using systemd
```ini
[Unit]
Description=NetPerf API
After=network.target

[Service]
User=aphillips
WorkingDirectory=/home/aphillips/Projects/netperf_api
ExecStart=/home/aphillips/Projects/netperf_api/venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable netperf-api
sudo systemctl start netperf-api
```

## 📦 Postman Collection

Import `NetPerf_API.postman_collection.json` into Postman for pre-configured requests.

**Variables:**
- `base_url`: `http://24.28.218.10:5000`
- `modem_ipv6`: `2605:1c00:50f2:203:a49d:6fa2:3d34:7329`
- `result_id`: `c3865f92-d53d-4d05-bc0e-a5b516f0afff`

## 🔑 Key Features

✅ **Exact CLI behavior** - Same folder structure and SNMP collection as CLI tool
✅ **SNMP integration** - Automatic before/after collection per iteration
✅ **Result management** - List, browse, and download test results
✅ **Folder downloads** - Download entire result folders as ZIP
✅ **Background execution** - Tests run asynchronously via API
✅ **CORS enabled** - Ready for web frontend integration

## 🏗️ Architecture

### Technology Stack
- **Backend:** Python 3.8+, Flask 3.0+
- **Testing:** ByteBlower CLI, iPerf3, Ookla SpeedTest
- **Network:** PacketStorm RTT emulation, SNMP v2c
- **Data:** YAML config, JSON API, CSV/Excel reports

### Components
```
netperf_api/
├── app.py                 # Flask REST API server
├── byteblower_logic.py    # ByteBlower test orchestration
├── iperf3_logic.py        # iPerf3 test execution
├── packetstorm_logic.py   # RTT configuration
├── speedtest_logic.py     # SpeedTest execution
├── snmp_collector.py      # SNMP data collection
├── config_loader.py       # Configuration management
├── logger.py              # Logging system
└── bb_flows/              # ByteBlower flow definitions
```

### Test Flow
1. **Configuration** - Set modem IPv6 via `/api/config/modem`
2. **Execution** - POST to test endpoint (sync or async)
3. **SNMP Collection** - Automatic before/after capture
4. **Results** - UUID-based result identification
5. **Analysis** - SNMP delta calculations, report generation
6. **Download** - ZIP archives or individual files

---

## 📊 SNMP Monitoring

Automatic SNMP collection provides network interface metrics:

### Metrics Collected
- `ifHCInOctets` / `ifHCOutOctets` - High capacity byte counters
- `ifInUcastPkts` / `ifOutUcastPkts` - Unicast packet counters
- `ifInDiscards` / `ifOutDiscards` - Discard counters
- `ifInErrors` / `ifOutErrors` - Error counters

### Analysis Endpoint
```bash
GET /api/results/{result_id}/snmp
```

Returns before/after/delta values for all metrics per iteration.

---

## 🔧 Development

### Prerequisites
- Python 3.8+
- ByteBlower CLI installed
- iPerf3 installed on test clients/servers
- PacketStorm access (optional)
- SNMP v2c enabled on test devices

### Installation
```bash
git clone git@github.com:birdyphillips/netperf-api.git
cd netperf-api
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
./start_api.sh
```

### Running Tests
```bash
# Health check
curl http://localhost:5000/health

# Set modem IPv6
curl -X POST http://localhost:5000/api/config/modem \
  -H "Content-Type: application/json" \
  -d '{"ipv6": "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"}'

# Run ByteBlower test
curl -X POST http://localhost:5000/api/byteblower/run \
  -H "Content-Type: application/json" \
  -d '{
    "bbp_file": "Port_20_example.bbp",
    "scenario": "US_Classic_Only",
    "test_group_name": "TEST",
    "iterations": 1
  }'
```

---

## 📝 API Documentation

Full API documentation with request/response examples is available in the [README.md](README.md).

Import the [Postman Collection](NetPerf_API.postman_collection.json) for interactive API testing.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📝 License

MIT License - see LICENSE file for details

---

## 👤 Author

**birdyphillips**
- GitHub: [@birdyphillips](https://github.com/birdyphillips)
- Repository: [netperf-api](https://github.com/birdyphillips/netperf-api)

---

## ⭐ Support

If you find this project useful, please consider giving it a star on GitHub!

---
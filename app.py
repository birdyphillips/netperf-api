#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from flasgger import Swagger
import os
import glob
from datetime import datetime
from byteblower_logic import ByteBlowerLogic
from packetstorm_logic import PacketStormLogic
from iperf3_logic import IPerf3Logic
from speedtest_logic import SpeedTestLogic
from snmp_collector import collect_snmp_data, generate_latency_report, find_snmp_files, parse_latency_bins, compute_deltas, calc_percentile, calc_percentile_avg, calc_weighted_avg, compute_throughput_and_loss, BIN_EDGES_MS, NUM_BINS
from cmts_modem_info import collect_cmts_data
from logger import Logger

try:
    from cmts_collector import CmtsCollector
    CMTS_KAFKA_AVAILABLE = True
except ImportError:
    CMTS_KAFKA_AVAILABLE = False
import shutil
import tempfile
import re
import threading
import uuid
import yaml

app = Flask(__name__)
CORS(app)

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "NetPerf API",
        "description": """REST API for Network Performance Testing - ByteBlower, iPerf3, PacketStorm, SpeedTest

## Documentation

- **GitHub**: [netperf-api](https://github.com/birdyphillips/netperf-api)
- **Full README**: [Documentation](https://github.com/birdyphillips/netperf-api#readme)
- **Usage Examples**: [Examples](https://github.com/birdyphillips/netperf-api#-usage-examples)
- **Postman Collection**: Available in repository

## Support

For issues or questions, visit the [GitHub repository](https://github.com/birdyphillips/netperf-api).
""",
        "version": "2.0.0",
        "contact": {
            "name": "birdyphillips",
            "url": "https://github.com/birdyphillips/netperf-api"
        }
    },
    "host": "24.28.218.10:5000",
    "basePath": "/",
    "schemes": ["http"],
    "tags": [
        {"name": "Health", "description": "Health check and configuration"},
        {"name": "Tests", "description": "Test execution endpoints"},
        {"name": "Results", "description": "Results management"},
        {"name": "Management", "description": "Test status and monitoring"}
    ],
    "uiversion": 3
}

Swagger(app, config=swagger_config, template=swagger_template)
logger = Logger("FlaskAPI")

modem_ipv6 = None
running_tests = {}  # Store test status
result_registry = {}  # Map result_id to folder path
cmts_collectors = {}  # Active CMTS Kafka collectors by test_id


def _start_cmts_collection(test_id, scenario, output_dir):
    """Start CMTS Kafka collection for a test. Non-blocking."""
    if not CMTS_KAFKA_AVAILABLE:
        logger.warning("CMTS Kafka collector not available (kafka-python not installed)")
        return None
    try:
        direction = "upstream" if scenario.lower().startswith("us") else "downstream"
        collector = CmtsCollector(direction=direction)
        collector.start()
        cmts_collectors[test_id] = {"collector": collector, "output_dir": output_dir, "scenario": scenario}
        return collector
    except Exception as e:
        logger.warning(f"CMTS collection failed to start: {e}")
        return None


def _stop_cmts_collection(test_id, snmp_dir, scenario):
    """Stop CMTS Kafka collection and generate report."""
    if test_id not in cmts_collectors:
        return None
    try:
        entry = cmts_collectors.pop(test_id)
        collector = entry["collector"]
        collector.stop()
        report = collector.generate_report(snmp_dir, scenario)
        if report:
            logger.info(f"\u2713 CMTS latency report: {os.path.basename(report)}")
        return report
    except Exception as e:
        logger.warning(f"CMTS report generation failed: {e}")
        cmts_collectors.pop(test_id, None)
        return None

@app.route('/health', methods=['GET'])
def health():
    """
    Health Check
    ---
    tags:
      - Health
    responses:
      200:
        description: API is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            timestamp:
              type: string
              example: "2025-02-25T10:30:00"
    """
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/config/modem', methods=['POST'])
def set_modem():
    """
    Set Modem IPv6 for SNMP Collection
    ---
    tags:
      - Health
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - ipv6
          properties:
            ipv6:
              type: string
              example: "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
    responses:
      200:
        description: Modem IPv6 configured successfully
      400:
        description: Invalid request
    """
    global modem_ipv6
    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    modem_ipv6 = data.get('ipv6')
    if not modem_ipv6:
        return jsonify({"error": "ipv6 is required"}), 400
    
    logger.info(f"Modem IPv6 configured: {modem_ipv6}")
    return jsonify({"message": "Modem IPv6 set", "ipv6": modem_ipv6}), 200

@app.route('/api/config', methods=['GET'])
def get_config():
    """
    Get Configuration
    ---
    tags:
      - Health
    responses:
      200:
        description: Configuration retrieved successfully
        schema:
          type: object
      500:
        description: Failed to load configuration
    """
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        return jsonify(config), 200
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cmts/devices', methods=['GET'])
def get_cmts_devices():
    """
    Get CPE Device IPs from CMTS
    ---
    tags:
      - Health
    parameters:
      - in: query
        name: cmts_host
        type: string
        required: true
        description: CMTS hostname
        enum: [apc01k1dccc, cts01k1dccc]
        example: "apc01k1dccc"
      - in: query
        name: cm_mac
        type: string
        required: true
        description: Cable modem MAC address
        example: "802b.f9fa.ee17"
    responses:
      200:
        description: Device IPs retrieved successfully
        schema:
          type: object
          properties:
            cmts_host:
              type: string
            cm_mac:
              type: string
            cmts_type:
              type: string
            devices:
              type: object
              additionalProperties:
                type: object
                properties:
                  ipv4:
                    type: string
                  ipv6:
                    type: string
      400:
        description: Invalid request - missing required parameters
      500:
        description: Failed to retrieve device IPs
    """
    cmts_host = request.args.get('cmts_host')
    cm_mac = request.args.get('cm_mac')
    
    if not all([cmts_host, cm_mac]):
        return jsonify({"error": "cmts_host and cm_mac are required"}), 400
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return jsonify({"error": f"Failed to load config: {str(e)}"}), 500
    
    tacacs_password = config['cmts']['tacacs_password']
    jumpserver = config['snmp']['jumpserver']
    jumpserver_user = config['snmp']['username']
    ssh_key_path = config['ssh']['key_path'].replace('~', os.path.expanduser('~'))
    
    # Detect CMTS type
    cmts_type = 'icmts' if 'cts01k1dccc' in cmts_host else 'vcmts'
    
    try:
        logger.info(f"Fetching device IPs from {cmts_type.upper()} {cmts_host} for CM {cm_mac}")
        
        # Import get_cpe_ips function
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from get_device_ips import get_cpe_ips
        
        devices = get_cpe_ips(cmts_host, cm_mac, tacacs_password, jumpserver, jumpserver_user, ssh_key_path, cmts_type)
        
        logger.info(f"Successfully retrieved {len(devices)} devices")
        return jsonify({
            "cmts_host": cmts_host,
            "cm_mac": cm_mac,
            "cmts_type": cmts_type,
            "devices": devices
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve device IPs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cmts/modem/info', methods=['GET'])
def get_cmts_modem_info():
    """
    Get CMTS Modem Information
    ---
    tags:
      - Health
    parameters:
      - in: query
        name: cmts_host
        type: string
        required: true
        description: CMTS hostname
        enum: [apc01k1dccc, cts01k1dccc]
        example: "apc01k1dccc"
      - in: query
        name: cm_mac
        type: string
        required: true
        description: Cable modem MAC address
        example: "e0db.d161.3d18"
    responses:
      200:
        description: Modem information retrieved successfully
        schema:
          type: object
          properties:
            cm_ipv6:
              type: string
              example: "2605:1c00:50f2:203:75c4:f09:ddc3:6c27"
            cmts_host:
              type: string
            cm_mac:
              type: string
            cmts_type:
              type: string
      400:
        description: Invalid request - missing required parameters
      404:
        description: Cable modem not found
      500:
        description: Failed to retrieve modem information
    """
    cmts_host = request.args.get('cmts_host')
    cm_mac = request.args.get('cm_mac')
    
    if not all([cmts_host, cm_mac]):
        return jsonify({"error": "cmts_host and cm_mac are required"}), 400
    
    # Auto-detect CMTS type based on hostname
    if cmts_host == 'apc01k1dccc':
        cmts_type = 'vcmts'
    elif cmts_host == 'cts01k1dccc':
        cmts_type = 'icmts'
    else:
        cmts_type = 'vcmts'  # default
    
    try:
        logger.info(f"Collecting {cmts_type.upper()} modem info for {cm_mac} from {cmts_host}")
        cm_ipv6 = collect_cmts_data(cmts_host, cm_mac, cmts_type, output_dir="Results")
        
        if cm_ipv6:
            logger.info(f"Successfully retrieved modem IPv6: {cm_ipv6}")
            return jsonify({
                "cm_ipv6": cm_ipv6,
                "cmts_host": cmts_host,
                "cm_mac": cm_mac,
                "cmts_type": cmts_type
            }), 200
        else:
            logger.warning(f"Cable modem not found: {cm_mac} on {cmts_host}")
            return jsonify({"error": "Cable modem not found or IPv6 could not be extracted"}), 404
    except Exception as e:
        logger.error(f"CMTS modem info collection failed: {e}")
        return jsonify({"error": str(e)}), 500

def run_snmp_collection(target_ip, test_name, phase, output_dir):
    try:
        logger.info(f"Running SNMP collection - {phase} {test_name}")
        collect_snmp_data(target_ip, test_name, phase, output_dir)
        return True
    except TimeoutError:
        logger.error(f"SNMP timeout: No response from {target_ip}")
        return False
    except Exception as e:
        logger.error(f"SNMP collection failed: {e}")
        return False

@app.route('/api/byteblower/run', methods=['POST'])
def run_byteblower():
    """
    Run ByteBlower Test
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - bbp_file
            - scenario
            - test_group_name
          properties:
            bbp_file:
              type: string
              example: "Port_20_example.bbp"
            scenario:
              type: string
              example: "US_Classic_Only"
            test_group_name:
              type: string
              example: "TEST_SCN_RTT_0"
            iterations:
              type: integer
              default: 1
              minimum: 1
              example: 1
            rtt_config:
              type: string
              example: "vcmts10ms.json"
            async:
              type: boolean
              default: false
              description: "Run test asynchronously in background (returns immediately with test_id)"
    responses:
      200:
        description: Test completed successfully
      202:
        description: Test started in background
      400:
        description: Invalid request
      500:
        description: Test failed
    """
    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    bbp_file = data.get('bbp_file')
    scenarios = data.get('scenario')
    test_group_name = data.get('test_group_name')
    iterations = max(1, data.get('iterations', 1) or 1)
    rtt_configs = data.get('rtt_config', '')
    async_mode = data.get('async', False)
    
    if not all([bbp_file, scenarios, test_group_name]):
        return jsonify({"error": "bbp_file, scenario, and test_group_name are required"}), 400
    
    if not modem_ipv6:
        logger.warning("ByteBlower test started without modem IPv6 configured")
    
    test_id = str(uuid.uuid4())
    
    if async_mode:
        thread = threading.Thread(target=_run_byteblower_test, args=(test_id, bbp_file, scenarios, test_group_name, iterations, rtt_configs))
        thread.daemon = True
        thread.start()
        
        running_tests[test_id] = {
            "status": "running",
            "type": "byteblower",
            "started": datetime.now().isoformat(),
            "output_dir": None
        }
        
        return jsonify({"test_id": test_id, "status": "running", "message": "Test started in background"}), 202
    else:
        result = _run_byteblower_test(test_id, bbp_file, scenarios, test_group_name, iterations, rtt_configs)
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500

def _run_byteblower_test(test_id, bbp_file, scenarios, test_group_name, iterations, rtt_configs):
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting ByteBlower test: {test_id}")
        logger.info(f"Test group: {test_group_name}")
        logger.info(f"Scenarios: {scenarios}")
        logger.info(f"Iterations: {iterations}")
        logger.info(f"Modem IPv6: {modem_ipv6}")
        logger.info(f"{'='*60}")
        
        scenario_list = [s.strip() for s in scenarios.split(',')]
        rtt_list = [r.strip() for r in rtt_configs.split(',')] if rtt_configs else ['']
        
        rtt_suffix = ""
        if rtt_list[0]:
            rtt_match = re.search(r'(\d+)ms', rtt_list[0])
            if rtt_match:
                rtt_suffix = f"_RTT_{rtt_match.group(1)}ms"
        
        parent_output_dir = f"Results/{test_group_name}_ByteBlower{rtt_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(parent_output_dir, exist_ok=True)
        logger.info(f"Output directory: {parent_output_dir}")
        
        # Register result with ID
        result_id = str(uuid.uuid4())
        result_registry[result_id] = parent_output_dir
        
        if test_id in running_tests:
            running_tests[test_id]["output_dir"] = parent_output_dir
            running_tests[test_id]["result_id"] = result_id
        
        all_success = True
        test_count = 0
        total_tests = len(scenario_list) * len(rtt_list)
        
        for scenario in scenario_list:
            for rtt_file in rtt_list:
                test_count += 1
                rtt_suffix_current = ""
                if rtt_file:
                    rtt_match = re.search(r'(\d+)ms', rtt_file)
                    if rtt_match:
                        rtt_suffix_current = f"_RTT_{rtt_match.group(1)}ms"
                
                logger.info(f"\nRunning scenario: {scenario}{rtt_suffix_current} ({test_count}/{total_tests})")
                
                # Start PacketStorm if RTT config provided
                ps = None
                if rtt_file:
                    logger.info(f"Starting PacketStorm with config: {rtt_file}")
                    ps = PacketStormLogic(rtt_file)
                    if not ps.start_config():
                        logger.error(f"Failed to start PacketStorm config: {rtt_file}")
                        all_success = False
                        continue
                
                bb = ByteBlowerLogic(bbp_file, scenario, scenario, test_group_name, rtt_suffix_current, "html pdf csv xls xlsx json docx")
                snmp_dir = os.path.join(parent_output_dir, scenario)
                os.makedirs(snmp_dir, exist_ok=True)
                logger.info(f"SNMP directory: {snmp_dir}")
                
                cmts_key = f"{test_id}_{scenario}"
                _start_cmts_collection(cmts_key, scenario, snmp_dir)
                
                for i in range(iterations):
                    logger.info(f"Iteration {i+1}/{iterations}")
                    if modem_ipv6:
                        logger.info(f"Collecting SNMP before - iteration {i+1}")
                        run_snmp_collection(modem_ipv6, f"ByteBlower_{scenario}_iteration_{i+1}", "before", snmp_dir)
                    else:
                        logger.warning("Modem IPv6 not set - skipping SNMP collection")
                    
                    if not bb.run_scenario(i, iterations, parent_output_dir):
                        all_success = False
                    
                    if modem_ipv6:
                        logger.info(f"Collecting SNMP after - iteration {i+1}")
                        run_snmp_collection(modem_ipv6, f"ByteBlower_{scenario}_iteration_{i+1}", "after", snmp_dir)
                
                # Generate latency report from SNMP before/after
                _stop_cmts_collection(cmts_key, snmp_dir, scenario)
                _run_latency_report(snmp_dir)
                
                # Stop PacketStorm if it was started
                if ps:
                    logger.info("Stopping PacketStorm")
                    if not ps.stop_config():
                        logger.error("Failed to stop PacketStorm config")
                        all_success = False
                
                # Wait 15 seconds between tests (except after last test)
                if test_count < total_tests:
                    import time
                    logger.info("Waiting 15 seconds before next test...")
                    time.sleep(15)
        
        logger.info(f"\nTest completed: {test_id}")
        logger.info(f"Success: {all_success}")
        logger.info(f"Output: {parent_output_dir}")
        logger.info(f"Result ID: {result_id}")
        
        result = {"success": all_success, "result_id": result_id, "output_dir": parent_output_dir, "scenarios": len(scenario_list), "rtt_configs": len(rtt_list), "iterations": iterations}
        
        if test_id in running_tests:
            running_tests[test_id]["status"] = "completed" if all_success else "failed"
            running_tests[test_id]["completed"] = datetime.now().isoformat()
            running_tests[test_id]["result"] = result
        
        return result
    except Exception as e:
        logger.error(f"Test failed: {test_id} - {str(e)}")
        if test_id in running_tests:
            running_tests[test_id]["status"] = "error"
            running_tests[test_id]["error"] = str(e)
        return {"success": False, "error": str(e)}

@app.route('/api/packetstorm/start', methods=['POST'])
def start_packetstorm():
    """
    Start PacketStorm RTT Configuration
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - rtt_config
          properties:
            rtt_config:
              type: string
              example: "vcmts10ms.json"
    responses:
      200:
        description: PacketStorm started successfully
      400:
        description: Invalid request
      500:
        description: Failed to start
    """
    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    rtt_config = data.get('rtt_config')
    if not rtt_config:
        return jsonify({"error": "rtt_config is required"}), 400
    
    ps = PacketStormLogic(rtt_config)
    success = ps.start_config()
    
    if success:
        return jsonify({"success": True, "config": rtt_config}), 200
    else:
        return jsonify({"success": False, "error": "Failed to start PacketStorm config"}), 500

@app.route('/api/packetstorm/stop', methods=['POST'])
def stop_packetstorm():
    """
    Stop PacketStorm RTT Configuration
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            rtt_config:
              type: string
              example: "vcmts10ms.json"
    responses:
      200:
        description: PacketStorm stopped successfully
      500:
        description: Failed to stop
    """
    data = request.json
    rtt_config = data.get('rtt_config', 'default.json') if data else 'default.json'
    
    ps = PacketStormLogic(rtt_config)
    success = ps.stop_config()
    
    if success:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "error": "Failed to stop PacketStorm config"}), 500

@app.route('/api/iperf3/run', methods=['POST'])
def run_iperf3():
    """
    Run iPerf3 Test
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - client_ip
            - scenario
            - test_group_name
          properties:
            client_ip:
              type: string
              example: "96.37.176.19"
            scenario:
              type: string
              example: "US_Classic_Only"
            test_group_name:
              type: string
              example: "TEST_SCN_RTT_0"
            iterations:
              type: integer
              default: 1
              minimum: 1
              example: 1
            platform:
              type: string
              enum: [linux, macos]
              default: linux
            output_format:
              type: string
              enum: [json, txt]
              default: json
            rtt_config:
              type: string
              example: "vcmts10ms.json"
    responses:
      200:
        description: Test completed successfully
      400:
        description: Invalid request
      500:
        description: Test failed
    """
    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    client_ip = data.get('client_ip')
    scenarios = data.get('scenario')
    test_group_name = data.get('test_group_name')
    iterations = max(1, data.get('iterations', 1) or 1)
    output_format = data.get('output_format', 'json')
    platform = data.get('platform', 'linux')
    rtt_configs = data.get('rtt_config', '')
    
    if not all([client_ip, scenarios, test_group_name]):
        return jsonify({"error": "client_ip, scenario, and test_group_name are required"}), 400
    
    # Parse comma-separated scenarios and RTT configs
    scenario_list = [s.strip() for s in scenarios.split(',')]
    rtt_list = [r.strip() for r in rtt_configs.split(',')] if rtt_configs else ['']
    
    # Extract RTT suffix from first RTT file
    rtt_suffix = ""
    if rtt_list[0]:
        rtt_match = re.search(r'(\d+)ms', rtt_list[0])
        if rtt_match:
            rtt_suffix = f"_RTT_{rtt_match.group(1)}ms"
    
    platform_override = 'macos' if platform == 'macos' else None
    platform_suffix = "_macOS" if platform == 'macos' else "_Linux"
    
    # Create parent output directory
    parent_output_dir = f"Results/{test_group_name}_iPerf3{platform_suffix}{rtt_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(parent_output_dir, exist_ok=True)
    
    all_success = True
    
    # Run all scenario/RTT combinations
    for scenario in scenario_list:
        for rtt_file in rtt_list:
            # Extract RTT suffix for this combination
            rtt_suffix_current = ""
            if rtt_file:
                rtt_match = re.search(r'(\d+)ms', rtt_file)
                if rtt_match:
                    rtt_suffix_current = f"_RTT_{rtt_match.group(1)}ms"
            
            iperf3 = IPerf3Logic(client_ip, scenario, test_group_name, rtt_suffix_current, output_format, platform_override, parent_output_dir)
            
            if not iperf3.setup_ssh_keys():
                return jsonify({"error": "SSH key setup failed"}), 500
            
            if not iperf3.setup_iperf3_servers():
                return jsonify({"error": "iPerf3 server setup failed"}), 500
            
            # Create SNMP subdirectory
            snmp_dir = os.path.join(parent_output_dir, scenario + platform_suffix + rtt_suffix_current)
            os.makedirs(snmp_dir, exist_ok=True)
            
            cmts_key = f"iperf3_{scenario}_{rtt_suffix_current}"
            _start_cmts_collection(cmts_key, scenario, snmp_dir)
            
            for i in range(iterations):
                if modem_ipv6:
                    run_snmp_collection(modem_ipv6, f"iPerf3{platform_suffix}_{scenario}_iteration_{i+1}", "before", snmp_dir)
                if not iperf3.run_scenario(i, iterations):
                    all_success = False
                if modem_ipv6:
                    run_snmp_collection(modem_ipv6, f"iPerf3{platform_suffix}_{scenario}_iteration_{i+1}", "after", snmp_dir)
            
            _stop_cmts_collection(cmts_key, snmp_dir, scenario)
            _run_latency_report(snmp_dir)
            iperf3.stop_iperf3_servers()
    
    return jsonify({"success": all_success, "output_dir": parent_output_dir, "scenarios": len(scenario_list), "rtt_configs": len(rtt_list), "iterations": iterations})

@app.route('/api/speedtest/run', methods=['POST'])
def run_speedtest():
    """
    Run SpeedTest
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            clients:
              type: array
              items:
                type: string
              example: ["linux", "macos", "nvidia"]
            test_group_name:
              type: string
              example: "Speedtest"
            iterations:
              type: integer
              default: 1
              minimum: 1
              example: 1
            target_ip:
              type: string
              example: "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
    responses:
      200:
        description: Test completed successfully
      400:
        description: Invalid request
      500:
        description: Test failed
    """
    data = request.json if request.json else {}
    clients = data.get('clients', ['linux', 'macos', 'nvidia'])
    test_group_name = data.get('test_group_name', 'Speedtest')
    iterations = max(1, data.get('iterations', 1) or 1)
    target_ip = data.get('target_ip') or modem_ipv6
    
    if not target_ip:
        return jsonify({"error": "target_ip is required or modem IPv6 must be configured"}), 400
    
    try:
        st = SpeedTestLogic(clients, test_group_name, target_ip)
        success = st.run_iterations(iterations)
        return jsonify({"success": success, "clients": clients, "iterations": iterations}), 200
    except Exception as e:
        logger.error(f"SpeedTest failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/snmp/collect', methods=['POST'])
def collect_snmp():
    """
    Collect SNMP Data
    ---
    tags:
      - Tests
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - test_name
          properties:
            target_ip:
              type: string
              example: "2605:1c00:50f2:203:a49d:6fa2:3d34:7329"
            test_name:
              type: string
              example: "TEST_SCN_RTT_0"
            phase:
              type: string
              enum: [before, after]
              default: before
            output_dir:
              type: string
              default: "Results"
              example: "Results"
    responses:
      200:
        description: SNMP data collected successfully
      400:
        description: Invalid request
      504:
        description: SNMP timeout - no response from target IP
      500:
        description: Collection failed
    """
    data = request.json
    target_ip = data.get('target_ip') or modem_ipv6
    test_name = data.get('test_name')
    phase = data.get('phase', 'before')
    output_dir = data.get('output_dir', 'Results')
    
    if not target_ip or not test_name:
        return jsonify({"error": "target_ip and test_name are required"}), 400
    
    try:
        collect_snmp_data(target_ip, test_name, phase, output_dir)
        return jsonify({"success": True, "phase": phase})
    except TimeoutError as e:
        return jsonify({"error": str(e), "target_ip": target_ip}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/snmp/live', methods=['GET'])
def get_live_snmp():
    """
    Get Live SNMP Data from Modem
    ---
    tags:
      - Tests
    parameters:
      - in: query
        name: target_ip
        type: string
        description: Modem IPv6 address (uses configured modem_ipv6 if not provided)
    responses:
      200:
        description: Live SNMP data retrieved
        schema:
          type: object
          properties:
            target_ip:
              type: string
            timestamp:
              type: string
            metrics:
              type: object
      400:
        description: Modem IPv6 not configured
      504:
        description: SNMP timeout - no response from target IP
      500:
        description: SNMP collection failed
    """
    target_ip = request.args.get('target_ip') or modem_ipv6
    
    if not target_ip:
        return jsonify({"error": "Modem IPv6 not configured. Use POST /api/config/modem first."}), 400
    
    try:
        import tempfile
        import re
        
        # Create temp directory for SNMP output
        temp_dir = tempfile.mkdtemp()
        test_name = f"live_snmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Collect SNMP data
        try:
            collect_snmp_data(target_ip, test_name, "live", temp_dir)
        except TimeoutError:
            shutil.rmtree(temp_dir)
            return jsonify({"error": f"SNMP timeout: No response from {target_ip}", "target_ip": target_ip}), 504
        
        # Find the SNMP file
        snmp_files = [f for f in os.listdir(temp_dir) if f.endswith('.txt')]
        if not snmp_files:
            return jsonify({"error": "No SNMP data collected"}), 500
        
        # Parse SNMP file
        snmp_file = os.path.join(temp_dir, snmp_files[0])
        with open(snmp_file, 'r') as f:
            content = f.read()
        
        # Extract OID values with names
        oid_pattern = r'SNMPv2-SMI::(.+?) = (.+?): (.+)'
        matches = re.findall(oid_pattern, content)
        
        # OID prefix to section name mapping
        oid_sections = {
            'enterprises.4491.2.1.21.1.4': 'Flow Stats Table (Entry Qos Service Flow Octets)',
            'enterprises.4491.2.1.21.1.27': 'Aggregate Service Flow Stats Table',
            'enterprises.4491.2.1.21.1.29': 'Latency Stats Table',
            'enterprises.4491.2.1.21.1.30': 'Congestion Stats Table',
            'enterprises.4998.1.1.15.10.2': 'Cadant Map Stats Mib',
            'enterprises.4998.1.1.15.10.8': 'Map Stats Pages Flows',
            'enterprises.15007': 'Cadant Map Stats Mib',
            'mib-2': 'Current Modem Information'
        }
        
        sections = {}
        for oid, data_type, value in matches:
            # Extract numeric value
            numeric_match = re.search(r'(\d+)', value)
            if numeric_match:
                # Determine section name
                section_name = 'Unknown'
                for prefix, name in oid_sections.items():
                    if oid.startswith(prefix):
                        section_name = name
                        break
                
                if section_name not in sections:
                    sections[section_name] = {}
                
                sections[section_name][oid] = {
                    'value': int(numeric_match.group(1)),
                    'type': data_type
                }
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir)
        
        return jsonify({
            "target_ip": target_ip,
            "timestamp": datetime.now().isoformat(),
            "sections": sections
        }), 200
        
    except Exception as e:
        logger.error(f"Live SNMP collection failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/bb_flows', methods=['GET'])
def list_bb_flows():
    """
    List ByteBlower Flows
    ---
    tags:
      - Management
    responses:
      200:
        description: List of available ByteBlower flow files
        schema:
          type: object
          properties:
            bb_flows:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  path:
                    type: string
                  size:
                    type: integer
    """
    bb_flows_dir = 'bb_flows'
    if not os.path.exists(bb_flows_dir):
        return jsonify({"bb_flows": []})
    
    flows = []
    for item in os.listdir(bb_flows_dir):
        if item.endswith('.bbp'):
            item_path = os.path.join(bb_flows_dir, item)
            flows.append({"name": item, "path": item_path, "size": os.path.getsize(item_path)})
    
    return jsonify({"bb_flows": sorted(flows, key=lambda x: x['name'])})

@app.route('/api/test/status/<test_id>', methods=['GET'])
def get_test_status(test_id):
    """
    Get Test Status
    ---
    tags:
      - Management
    parameters:
      - in: path
        name: test_id
        required: true
        type: string
        description: Test UUID
    responses:
      200:
        description: Test status retrieved
      404:
        description: Test not found
    """
    if test_id not in running_tests:
        return jsonify({"error": "Test not found"}), 404
    
    return jsonify(running_tests[test_id])

@app.route('/api/test/list', methods=['GET'])
def list_tests():
    """
    List All Tests
    ---
    tags:
      - Management
    responses:
      200:
        description: List of all tests
        schema:
          type: object
          properties:
            tests:
              type: object
    """
    return jsonify({"tests": running_tests})

@app.route('/api/results', methods=['GET'])
def list_results():
    """
    List All Results
    ---
    tags:
      - Results
    responses:
      200:
        description: List of all test results
        schema:
          type: object
          properties:
            results:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string
                  path:
                    type: string
                  created:
                    type: string
    """
    results_dir = 'Results'
    if not os.path.exists(results_dir):
        return jsonify({"results": []}), 200
    
    results = []
    for item in os.listdir(results_dir):
        item_path = os.path.join(results_dir, item)
        if os.path.isdir(item_path):
            # Find or create result_id for this folder
            result_id = None
            for rid, path in result_registry.items():
                if path == item_path:
                    result_id = rid
                    break
            
            if not result_id:
                result_id = str(uuid.uuid4())
                result_registry[result_id] = item_path
            
            results.append({
                "id": result_id,
                "name": item,
                "path": item_path,
                "created": datetime.fromtimestamp(os.path.getctime(item_path)).isoformat()
            })
    
    return jsonify({"results": sorted(results, key=lambda x: x['created'], reverse=True)}), 200

@app.route('/api/results/<result_id>', methods=['GET'])
def get_result_files(result_id):
    """
    Get Result Files
    ---
    tags:
      - Results
    parameters:
      - in: path
        name: result_id
        required: true
        type: string
        description: Result UUID
    responses:
      200:
        description: List of files in result
      404:
        description: Result not found
    """
    if result_id not in result_registry:
        return jsonify({"error": "Result not found"}), 404
    
    result_path = result_registry[result_id]
    if not os.path.exists(result_path):
        return jsonify({"error": "Result folder not found"}), 404
    
    files = []
    for root, dirs, filenames in os.walk(result_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, result_path)
            files.append({"name": filename, "path": rel_path, "size": os.path.getsize(file_path)})
    
    return jsonify({"id": result_id, "name": os.path.basename(result_path), "files": files}), 200

@app.route('/api/results/<result_id>/snmp', methods=['GET'])
def get_snmp_analysis(result_id):
    """
    Get SNMP Analysis
    ---
    tags:
      - Results
    parameters:
      - in: path
        name: result_id
        required: true
        type: string
        description: Result UUID
    responses:
      200:
        description: SNMP analysis with deltas
      404:
        description: Result or SNMP files not found
    """
    if result_id not in result_registry:
        return jsonify({"error": "Result not found"}), 404
    
    result_path = result_registry[result_id]
    if not os.path.exists(result_path):
        return jsonify({"error": "Result folder not found"}), 404
    
    # Find all SNMP files
    snmp_files = []
    for root, dirs, filenames in os.walk(result_path):
        for filename in filenames:
            if '_SNMP_' in filename and filename.endswith('.txt'):
                snmp_files.append(os.path.join(root, filename))
    
    if not snmp_files:
        return jsonify({"error": "No SNMP files found"}), 404
    
    # Parse SNMP files and group by iteration
    iterations = {}
    for snmp_file in snmp_files:
        filename = os.path.basename(snmp_file)
        
        # Extract iteration and phase
        if '_before_' in filename:
            phase = 'before'
        elif '_after_' in filename:
            phase = 'after'
        else:
            continue
        
        # Extract iteration number
        import re
        iter_match = re.search(r'iteration_(\d+)', filename)
        if iter_match:
            iter_num = int(iter_match.group(1))
        else:
            iter_num = 1
        
        if iter_num not in iterations:
            iterations[iter_num] = {}
        
        # Parse SNMP file
        with open(snmp_file, 'r') as f:
            content = f.read()
        
        # Extract OID values with names
        oid_pattern = r'SNMPv2-SMI::(.+?) = (.+?): (.+)'
        matches = re.findall(oid_pattern, content)
        
        # OID to metric name mapping
        oid_names = {
            'mib-2.2.2.1.10': 'ifInOctets',
            'mib-2.2.2.1.16': 'ifOutOctets',
            'mib-2.31.1.1.1.6': 'ifHCInOctets',
            'mib-2.31.1.1.1.10': 'ifHCOutOctets',
            'mib-2.2.2.1.11': 'ifInUcastPkts',
            'mib-2.2.2.1.17': 'ifOutUcastPkts',
            'mib-2.2.2.1.12': 'ifInNUcastPkts',
            'mib-2.2.2.1.18': 'ifOutNUcastPkts',
            'mib-2.2.2.1.13': 'ifInDiscards',
            'mib-2.2.2.1.19': 'ifOutDiscards',
            'mib-2.2.2.1.14': 'ifInErrors',
            'mib-2.2.2.1.20': 'ifOutErrors'
        }
        
        oid_data = {}
        for oid, data_type, value in matches:
            # Extract numeric value
            numeric_match = re.search(r'(\d+)', value)
            if numeric_match:
                # Get base OID (without interface index)
                base_oid = '.'.join(oid.split('.')[:-1])
                metric_name = oid_names.get(base_oid, oid)
                oid_data[metric_name] = int(numeric_match.group(1))
        
        iterations[iter_num][phase] = {
            'file': filename,
            'oids': oid_data
        }
    
    # Calculate deltas
    analysis = []
    for iter_num in sorted(iterations.keys()):
        iter_data = iterations[iter_num]
        
        if 'before' not in iter_data or 'after' not in iter_data:
            continue
        
        before_oids = iter_data['before']['oids']
        after_oids = iter_data['after']['oids']
        
        deltas = {}
        for metric_name in before_oids:
            if metric_name in after_oids:
                delta = after_oids[metric_name] - before_oids[metric_name]
                deltas[metric_name] = {
                    'before': before_oids[metric_name],
                    'after': after_oids[metric_name],
                    'delta': delta
                }
        
        analysis.append({
            'iteration': iter_num,
            'before_file': iter_data['before']['file'],
            'after_file': iter_data['after']['file'],
            'metrics': deltas
        })
    
    return jsonify({
        "result_id": result_id,
        "iterations": analysis
    }), 200

def _run_latency_report(snmp_dir):
    """Generate latency bin report from SNMP before/after files in a directory."""
    try:
        before_file, after_file = find_snmp_files(snmp_dir)
        if before_file and after_file:
            result = generate_latency_report(before_file, after_file)
            if result:
                logger.info(f"✓ Latency report: {os.path.basename(result)}")
            else:
                logger.warning("Latency report skipped (no latency data in SNMP)")
        else:
            logger.warning(f"Latency report skipped (SNMP files not found in {snmp_dir})")
    except Exception as e:
        logger.error(f"Latency report failed: {e}")


@app.route('/api/results/<result_id>/latency', methods=['GET'])
def get_latency_analysis(result_id):
    """
    Get Latency Bin Analysis from SNMP Before/After Data
    ---
    tags:
      - Results
    parameters:
      - in: path
        name: result_id
        required: true
        type: string
        description: Result UUID
      - in: query
        name: generate_excel
        type: boolean
        default: false
        description: Also generate Excel report in result folder
    responses:
      200:
        description: Latency bin analysis with percentiles per service flow
        schema:
          type: object
          properties:
            result_id:
              type: string
            service_flows:
              type: array
              items:
                type: object
                properties:
                  sfid:
                    type: integer
                  total_packets:
                    type: integer
                  p50_ms:
                    type: number
                  p99_ms:
                    type: number
                  p999_ms:
                    type: number
                  peak_bin:
                    type: string
                  bins:
                    type: array
                    items:
                      type: object
      404:
        description: Result not found or no latency data
    """
    if result_id not in result_registry:
        return jsonify({"error": "Result not found"}), 404

    result_path = result_registry[result_id]
    if not os.path.exists(result_path):
        return jsonify({"error": "Result folder not found"}), 404

    gen_excel = request.args.get('generate_excel', 'false').lower() == 'true'

    # Find SNMP before/after pairs across all subdirectories
    all_sf_data = []
    for root, dirs, files in os.walk(result_path):
        before_file, after_file = find_snmp_files(root)
        if not before_file or not after_file:
            continue

        before_bins = parse_latency_bins(before_file)
        after_bins = parse_latency_bins(after_file)
        all_deltas = compute_deltas(before_bins, after_bins)

        if not all_deltas:
            continue

        tp_stats = compute_throughput_and_loss(before_file, after_file)
        subdir = os.path.relpath(root, result_path)

        for sfid, sf_data in sorted(all_deltas.items()):
            deltas = sf_data["deltas"]
            total = sum(deltas)
            p50 = calc_percentile(deltas, 0.50)
            p99 = calc_percentile(deltas, 0.99)
            p999 = calc_percentile(deltas, 0.999)
            peak_idx = deltas.index(max(deltas))

            bins_detail = []
            cumulative = 0
            for i in range(NUM_BINS):
                cumulative += deltas[i]
                bins_detail.append({
                    "bin": i + 1,
                    "lower_ms": BIN_EDGES_MS[i],
                    "upper_ms": BIN_EDGES_MS[i + 1],
                    "delta": deltas[i],
                    "cumulative": cumulative,
                    "cumulative_pct": round(cumulative / total * 100, 2) if total else 0,
                })

            tp = tp_stats.get(sfid, {})
            all_sf_data.append({
                "directory": subdir,
                "sfid": sfid,
                "total_packets": total,
                "avg_ms": round(calc_weighted_avg(deltas), 4),
                "p50_ms": round(p50, 4),
                "p99_ms": round(p99, 4),
                "p999_ms": round(p999, 4),
                "p50_avg_ms": round(calc_percentile_avg(deltas, 0.50), 4),
                "p99_avg_ms": round(calc_percentile_avg(deltas, 0.99), 4),
                "p999_avg_ms": round(calc_percentile_avg(deltas, 0.999), 4),
                "peak_bin": f"{BIN_EDGES_MS[peak_idx]}-{BIN_EDGES_MS[peak_idx+1]} ms",
                "throughput_mbps": round(tp.get("throughput_mbps", 0), 4),
                "lost_packets": tp.get("lost_packets", 0),
                "loss_pct": round(tp.get("loss_pct", 0), 4),
                "bins": bins_detail,
            })

        if gen_excel:
            generate_latency_report(before_file, after_file)

    if not all_sf_data:
        return jsonify({"error": "No latency data found in SNMP files"}), 404

    return jsonify({"result_id": result_id, "service_flows": all_sf_data}), 200


@app.route('/api/latency/calculate', methods=['POST'])
def calculate_latency():
    """
    Calculate Latency from SNMP Before/After Files
    ---
    tags:
      - Results
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - results_dir
          properties:
            results_dir:
              type: string
              description: Path to results directory containing SNMP before/after files
              example: "Results/Config_4_iPerf3_Linux_20260325_173114"
            generate_excel:
              type: boolean
              default: true
              description: Generate Excel report
    responses:
      200:
        description: Latency calculated successfully
        schema:
          type: object
          properties:
            service_flows:
              type: array
              items:
                type: object
                properties:
                  sfid:
                    type: integer
                  total_packets:
                    type: integer
                  p50_ms:
                    type: number
                  p99_ms:
                    type: number
                  p999_ms:
                    type: number
            excel_report:
              type: string
      400:
        description: Invalid request
      404:
        description: No SNMP files or latency data found
    """
    data = request.json
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    results_dir = data.get('results_dir')
    if not results_dir:
        return jsonify({"error": "results_dir is required"}), 400

    if not os.path.isdir(results_dir):
        return jsonify({"error": f"Directory not found: {results_dir}"}), 404

    gen_excel = data.get('generate_excel', True)

    before_file, after_file = find_snmp_files(results_dir)
    if not before_file or not after_file:
        return jsonify({"error": "No SNMP before/after files found"}), 404

    before_bins = parse_latency_bins(before_file)
    after_bins = parse_latency_bins(after_file)
    all_deltas = compute_deltas(before_bins, after_bins)

    if not all_deltas:
        return jsonify({"error": "No latency data (all deltas zero)"}), 404

    tp_stats = compute_throughput_and_loss(before_file, after_file)

    sf_results = []
    for sfid, sf_data in sorted(all_deltas.items()):
        deltas = sf_data["deltas"]
        total = sum(deltas)
        tp = tp_stats.get(sfid, {})
        sf_results.append({
            "sfid": sfid,
            "total_packets": total,
            "avg_ms": round(calc_weighted_avg(deltas), 4),
            "p50_ms": round(calc_percentile(deltas, 0.50), 4),
            "p99_ms": round(calc_percentile(deltas, 0.99), 4),
            "p999_ms": round(calc_percentile(deltas, 0.999), 4),
            "p50_avg_ms": round(calc_percentile_avg(deltas, 0.50), 4),
            "p99_avg_ms": round(calc_percentile_avg(deltas, 0.99), 4),
            "p999_avg_ms": round(calc_percentile_avg(deltas, 0.999), 4),
            "peak_bin": f"{BIN_EDGES_MS[deltas.index(max(deltas))]}-{BIN_EDGES_MS[deltas.index(max(deltas))+1]} ms",
            "throughput_mbps": round(tp.get("throughput_mbps", 0), 4),
            "lost_packets": tp.get("lost_packets", 0),
            "loss_pct": round(tp.get("loss_pct", 0), 4),
        })

    response = {"service_flows": sf_results, "before_file": before_file, "after_file": after_file}

    if gen_excel:
        report = generate_latency_report(before_file, after_file)
        if report:
            response["excel_report"] = report

    return jsonify(response), 200


@app.route('/api/results/<result_id>/download', methods=['GET'])
def download_result_folder(result_id):
    """
    Download Result Folder as ZIP
    ---
    tags:
      - Results
    parameters:
      - in: path
        name: result_id
        required: true
        type: string
        description: Result UUID
    responses:
      200:
        description: ZIP file download
      404:
        description: Result not found
    """
    if result_id not in result_registry:
        return jsonify({"error": "Result not found"}), 404
    
    result_path = result_registry[result_id]
    if not os.path.exists(result_path):
        return jsonify({"error": "Result folder not found"}), 404
    
    temp_dir = tempfile.mkdtemp()
    result_name = os.path.basename(result_path)
    zip_path = os.path.join(temp_dir, result_name)
    shutil.make_archive(zip_path, 'zip', result_path)
    
    return send_file(f"{zip_path}.zip", as_attachment=True, download_name=f"{result_name}.zip", mimetype='application/zip')

@app.route('/api/results/<result_id>/download/<path:file_path>', methods=['GET'])
def download_result_file(result_id, file_path):
    """
    Download Individual Result File
    ---
    tags:
      - Results
    parameters:
      - in: path
        name: result_id
        required: true
        type: string
        description: Result UUID
      - in: path
        name: file_path
        required: true
        type: string
        description: File path within result
    responses:
      200:
        description: File download
      404:
        description: Result or file not found
    """
    if result_id not in result_registry:
        return jsonify({"error": "Result not found"}), 404
    
    result_path = result_registry[result_id]
    full_path = os.path.join(result_path, file_path)
    
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404
    
    return send_file(full_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

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
from snmp_collector import collect_snmp_data
from logger import Logger
import shutil
import tempfile
import re
import threading
import uuid

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

def run_snmp_collection(target_ip, test_name, phase, output_dir):
    try:
        logger.info(f"Running SNMP collection - {phase} {test_name}")
        collect_snmp_data(target_ip, test_name, phase, output_dir)
        return True
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
            rtt_config:
              type: string
              example: "vcmts10ms.json"
            async:
              type: boolean
              default: false
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
    iterations = data.get('iterations', 1)
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
        
        for scenario in scenario_list:
            for rtt_file in rtt_list:
                rtt_suffix_current = ""
                if rtt_file:
                    rtt_match = re.search(r'(\d+)ms', rtt_file)
                    if rtt_match:
                        rtt_suffix_current = f"_RTT_{rtt_match.group(1)}ms"
                
                logger.info(f"\nRunning scenario: {scenario}{rtt_suffix_current}")
                bb = ByteBlowerLogic(bbp_file, scenario, scenario, test_group_name, rtt_suffix_current, "html pdf csv xls xlsx json docx")
                snmp_dir = os.path.join(parent_output_dir, scenario + rtt_suffix_current)
                os.makedirs(snmp_dir, exist_ok=True)
                logger.info(f"SNMP directory: {snmp_dir}")
                
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
    iterations = data.get('iterations', 1)
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
            
            for i in range(iterations):
                if modem_ipv6:
                    run_snmp_collection(modem_ipv6, f"iPerf3{platform_suffix}_{scenario}_iteration_{i+1}", "before", snmp_dir)
                if not iperf3.run_scenario(i, iterations):
                    all_success = False
                if modem_ipv6:
                    run_snmp_collection(modem_ipv6, f"iPerf3{platform_suffix}_{scenario}_iteration_{i+1}", "after", snmp_dir)
            
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
    responses:
      200:
        description: Test completed successfully
    """
    data = request.json
    clients = data.get('clients', ['linux', 'macos', 'nvidia'])
    test_group_name = data.get('test_group_name', 'Speedtest')
    iterations = data.get('iterations', 1)
    
    st = SpeedTestLogic(clients, test_group_name)
    success = st.run_iterations(iterations)
    
    return jsonify({"success": success, "clients": clients, "iterations": iterations})

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
    responses:
      200:
        description: SNMP data collected successfully
      400:
        description: Invalid request
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
        collect_snmp_data(target_ip, test_name, "live", temp_dir)
        
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
        
        metrics = {}
        for oid, data_type, value in matches:
            # Extract numeric value
            numeric_match = re.search(r'(\d+)', value)
            if numeric_match:
                # Get base OID (without interface index)
                base_oid = '.'.join(oid.split('.')[:-1])
                metric_name = oid_names.get(base_oid, oid)
                metrics[metric_name] = int(numeric_match.group(1))
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir)
        
        return jsonify({
            "target_ip": target_ip,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
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

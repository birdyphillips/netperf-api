# DELTA-API - MySQL Integration Plan

## Overview

Add MySQL database to record SNMP metrics, ByteBlower JSON data, iPerf3 results, and latency calculations for historical tracking, comparison, and reporting.

---

## Phase 1: Database Schema & Setup

### Tables

#### test_runs
Master record per test execution.

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_id | VARCHAR(36) UNIQUE | UUID |
| test_group_name | VARCHAR(255) | e.g. "Latency_Test" |
| traffic_type | VARCHAR(50) | ByteBlower, iPerf3_Linux, iPerf3_macOS, SpeedTest |
| scenario | VARCHAR(100) | e.g. US_Combined, DS_Classic_Only |
| rtt_config | VARCHAR(100) | e.g. vcmts10ms.json |
| modem_ipv6 | VARCHAR(100) | Target modem IPv6 |
| iterations | INT | Number of iterations |
| output_dir | VARCHAR(500) | Results directory path |
| status | VARCHAR(20) | running, completed, failed |
| started_at | DATETIME | |
| completed_at | DATETIME | |

#### snmp_metrics
Raw SNMP OID values per collection.

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_run_id | INT FK → test_runs.id | |
| phase | VARCHAR(10) | before, after |
| iteration | INT | |
| section | VARCHAR(100) | e.g. "Latency Stats Table" |
| oid | VARCHAR(255) | Full OID string |
| data_type | VARCHAR(30) | Counter64, Gauge32, etc. |
| value | BIGINT | Numeric value |
| collected_at | DATETIME | |

#### latency_bins
Per-SFID bin data (after − before deltas).

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_run_id | INT FK → test_runs.id | |
| sfid | INT | Service flow ID |
| bin_number | INT | 1–16 |
| lower_ms | DECIMAL(10,4) | Bin lower edge |
| upper_ms | DECIMAL(10,4) | Bin upper edge |
| start_count | BIGINT | Before packet count |
| end_count | BIGINT | After packet count |
| delta | BIGINT | end_count − start_count |
| cumulative | BIGINT | Running total |
| cumulative_pct | DECIMAL(8,4) | Cumulative percentage |

#### latency_results
Percentile summaries per service flow.

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_run_id | INT FK → test_runs.id | |
| sfid | INT | Service flow ID |
| method | VARCHAR(20) | interpolation, avg |
| p50_ms | DECIMAL(10,4) | |
| p99_ms | DECIMAL(10,4) | |
| p999_ms | DECIMAL(10,4) | |
| total_packets | BIGINT | |

#### byteblower_results
Parsed ByteBlower JSON result fields.

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_run_id | INT FK → test_runs.id | |
| scenario | VARCHAR(100) | |
| iteration | INT | |
| flow_name | VARCHAR(255) | |
| throughput_bps | BIGINT | |
| frame_loss | BIGINT | |
| latency_avg_ms | DECIMAL(10,4) | |
| latency_min_ms | DECIMAL(10,4) | |
| latency_max_ms | DECIMAL(10,4) | |
| jitter_ms | DECIMAL(10,4) | |

#### iperf3_results
Parsed iPerf3 JSON result fields.

| Column | Type | Description |
|--------|------|-------------|
| id | INT AUTO_INCREMENT PK | |
| test_run_id | INT FK → test_runs.id | |
| scenario | VARCHAR(100) | |
| iteration | INT | |
| protocol | VARCHAR(10) | TCP, UDP, QUIC |
| streams | INT | |
| bandwidth_bps | BIGINT | |
| retransmits | INT | |
| congestion_algo | VARCHAR(30) | cubic, prague, etc. |
| rtt_ms | DECIMAL(10,4) | |
| dscp | INT | |

---

## Phase 2: Implementation Files

### db_config.py
- MySQL connection pool using `mysql-connector-python`
- Reads credentials from `config.yaml` → `mysql:` section
- Connection pool with auto-reconnect
- Context manager for transactions

### db_models.py
- Table creation DDL (CREATE TABLE IF NOT EXISTS)
- Insert helper functions per table
- Query helper functions (by test_run_id, date range, scenario)
- Migration/init function to create all tables

---

## Phase 3: Integration Points

### snmp_collector.py
- After writing SNMP `.txt` file, parse OIDs and insert into `snmp_metrics`
- Store phase (before/after), iteration number, section name

### latency_calculator.py
- After computing deltas/percentiles, insert into `latency_bins` + `latency_results`
- Store both interpolation and AVG method results
- Include start_count/end_count for verification

### byteblower_logic.py
- After test completes, parse result `.json` files
- Insert per-flow metrics into `byteblower_results`

### iperf3_logic.py
- After SCP of results from remote host, parse `.json` files
- Insert per-stream metrics into `iperf3_results`

### delta_orchestrator.py / app.py
- Create `test_runs` record at test start (status=running)
- Update status to completed/failed at end
- Pass test_run_id down to all sub-modules for FK linkage

---

## Phase 4: API Endpoints (DELTA-API only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/db/test-runs` | List/filter test runs (by date, scenario, traffic_type) |
| GET | `/api/db/test-runs/<id>/metrics` | SNMP metrics for a test run |
| GET | `/api/db/test-runs/<id>/latency` | Latency bin results from DB |
| GET | `/api/db/test-runs/<id>/throughput` | ByteBlower/iPerf3 results |
| GET | `/api/db/compare?run1=X&run2=Y` | Compare two test runs side-by-side |
| DELETE | `/api/db/test-runs/<id>` | Delete a test run and all related data |

---

## Phase 5: Dependencies

### requirements.txt addition
```
mysql-connector-python>=8.0
```

### config.yaml addition
```yaml
mysql:
  host: localhost
  port: 3306
  user: delta
  password: <password>
  database: delta
```

### MySQL server setup
```sql
CREATE DATABASE delta;
CREATE USER 'delta'@'localhost' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON delta.* TO 'delta'@'localhost';
FLUSH PRIVILEGES;
```

---

## Implementation Order

1. Add `mysql:` config to `config.yaml`
2. Create `db_config.py` (connection pool)
3. Create `db_models.py` (DDL + helpers)
4. Update `snmp_collector.py` (insert SNMP metrics)
5. Update `latency_calculator.py` (insert latency bins/results)
6. Update `byteblower_logic.py` (insert ByteBlower results)
7. Update `iperf3_logic.py` (insert iPerf3 results)
8. Update `app.py` / `netperf_orchestrator.py` (test_runs lifecycle)
9. Add DB query API endpoints
10. Test end-to-end with a full test run

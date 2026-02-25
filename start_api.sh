#!/bin/bash
cd /home/aphillips/Projects/netperf_api
nohup /home/aphillips/Projects/netperf_api/venv/bin/python3 app.py > api.log 2>&1 &
echo $! > api.pid
echo "NetPerf API started on port 5000 (PID: $(cat api.pid))"

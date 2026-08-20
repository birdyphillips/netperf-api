#!/bin/bash
cd /home/aphillips/Projects/DELTA-API
nohup /home/aphillips/Projects/DELTA-API/venv/bin/python3 app.py > api.log 2>&1 &
echo $! > api.pid
echo "DELTA-API started on port 5000 (PID: $(cat api.pid))"

#!/bin/bash
cd /home/aphillips/Projects/netperf_api
if [ -f api.pid ]; then
    kill $(cat api.pid)
    rm api.pid
    echo "NetPerf API stopped"
else
    echo "No PID file found"
fi

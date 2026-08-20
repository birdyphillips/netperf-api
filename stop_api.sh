#!/bin/bash
cd /home/aphillips/Projects/DELTA-API
if [ -f api.pid ]; then
    kill $(cat api.pid)
    rm api.pid
    echo "DELTA-API stopped"
else
    echo "No PID file found"
fi

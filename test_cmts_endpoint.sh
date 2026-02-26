#!/bin/bash
# Test CMTS Modem Info API Endpoint

echo "Testing vCMTS endpoint..."
curl "http://localhost:5000/api/cmts/modem/info?cmts_host=apc01k1dccc&cm_mac=e0db.d161.3d18&cmts_type=vcmts"

echo -e "\n\nTesting iCMTS endpoint..."
curl "http://localhost:5000/api/cmts/modem/info?cmts_host=cts01k1dccc&cm_mac=0cb9.379c.64b4&cmts_type=icmts"

import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    if f.get('name') == 'Parse Telemetry -> DB1512':
        print(f['func'])

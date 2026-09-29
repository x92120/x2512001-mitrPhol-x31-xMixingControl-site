import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    if 'Sub Telemetry Plant 1' in f.get('name', ''):
        print(f.get('topic'))

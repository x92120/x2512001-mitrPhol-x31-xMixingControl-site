import json
import requests
with open('final_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('name') in ['Sub Telemetry Plant 1', 'Sub Telemetry Plant 2', 'Sub Telemetry Plant 3']:
        f['topic'] = 'DO_NOT_USE_MIX_01'
        print(f"Disabled {f.get('name')}")
    if f.get('type') == 'function' and 'Parse Telemetry -> DB' in f.get('name', ''):
        f['func'] = "return null;\n" + f['func']
        print(f"Disabled {f.get('name')}")

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

r = requests.post('http://localhost:1880/flows', json=flows)
print("Deploy status:", r.status_code)

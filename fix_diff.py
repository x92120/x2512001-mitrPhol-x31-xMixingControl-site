import json

with open('new_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('type') == 's7 in':
        f['diff'] = True

with open('new_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

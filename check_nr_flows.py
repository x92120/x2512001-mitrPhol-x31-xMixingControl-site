import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    name = f.get('name', '')
    if 'Read' in name or 'Format' in name or 'DB15' in name:
        print(name, ":", f.get('type'))

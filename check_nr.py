import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    if f.get('type') == 'function' and f.get('name', '').startswith('Format Plant'):
        print(f['name'], ":")
        print(f['func'])
        print("-" * 20)

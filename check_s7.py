import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    if f.get('type') == 's7 endpoint':
        print(f.get('name'))
        for v in f.get('vartable', []):
            if 'mix' in v.get('name', '').lower() or 'hopper' in v.get('name', '').lower():
                print("  ", v['name'], v['addr'])

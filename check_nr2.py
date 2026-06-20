import json
with open('final_flows.json', 'r') as f:
    flows = json.load(f)
for f in flows:
    if 'DB1512' in f.get('name', ''):
        print(f['name'], ":", f['type'])
        if f.get('func'):
            print(f['func'][:100] + "...")
        print("-" * 20)

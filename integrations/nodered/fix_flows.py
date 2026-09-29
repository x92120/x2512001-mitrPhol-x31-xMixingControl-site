import json

with open('new_flows.json', 'r') as f:
    flows = json.load(f)

# Find first endpoint
ep1 = next(f for f in flows if f.get('type') == 's7 endpoint' and f['name'] == 'Siemens_S7-1200')
# Find second endpoint
ep2 = next((f for f in flows if f.get('type') == 's7 endpoint' and f['name'] == 'Siemens_S7-1200_Plant3'), None)

if ep2:
    # Append vartable from ep2 to ep1
    ep1['vartable'].extend(ep2['vartable'])
    # Update nodes to use ep1
    for f in flows:
        if f.get('endpoint') == ep2['id']:
            f['endpoint'] = ep1['id']
    # Remove ep2
    flows.remove(ep2)

with open('new_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

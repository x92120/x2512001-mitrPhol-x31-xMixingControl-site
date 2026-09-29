import sys
with open('app/pages/x50-PackingList.vue', 'r') as f:
    lines = f.readlines()

part1 = lines[716:846] # lines 717-846
middle = lines[846:851] # lines 847-851
middle[2] = "      <!-- ═══ RIGHT PANEL: Warehouse Pre-Batch + Transfer Logs ═══ -->\n"
part2 = lines[851:1006] # lines 852-1006

new_lines = lines[:716] + part2 + middle + part1 + lines[1006:]

with open('app/pages/x50-PackingList.vue', 'w') as f:
    f.writelines(new_lines)

print("Swapped successfully")

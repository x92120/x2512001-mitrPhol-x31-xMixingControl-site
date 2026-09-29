import sys

with open('app/pages/x50-PackingList.vue', 'r') as f:
    lines = f.readlines()

def get_block(start_marker, end_marker=None):
    pass
    
# Let's cleanly replace the Middle and Right panels
# Middle Panel:
# Card 1 = Packing Box (lines 662-715)
# Card 2 = Packing List (lines 717-871)
# Right Panel:
# Card 3 = Table (lines 877-1006)
# Card 4 = Already transferred logs (1008-1050)

# Extract Middle Panel body (lines 660 to 872)
# Extract Right Panel body (lines 875 to 1051)

middle_panel_start = 659 # <!-- ═══ MIDDLE PANEL: Warehouse Pre-Batch ═══ -->
right_panel_start = 874 # <!-- ═══ RIGHT PANEL: Warehouse Pre-Batch + Transfer Logs ═══ -->
right_panel_end = 1051 # last </div> closing right panel

packing_box_card = lines[662:716]
packing_list_card = lines[717:872]
table_card = lines[877:1007]
transferred_card = lines[1008:1051]

# Now, we mutate the individual cards
# 1. Packing box card: Add warehouse select
import re
packing_box_text = "".join(packing_box_card)
packing_box_text = packing_box_text.replace(
'''            <div class="row items-center q-gutter-xs">
              <q-icon name="qr_code_scanner" size="sm" />
              <div class="text-subtitle2 text-weight-bold">Packing Box</div>
            </div>''',
'''            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="qr_code_scanner" size="sm" />
                <div class="text-subtitle2 text-weight-bold">Packing Box</div>
              </div>
              <div class="row items-center q-gutter-sm">
                <q-select
                  v-model="filterMiddleWh"
                  :options="['FH', 'SPP']"
                  dense borderless dark options-dense
                  style="width: 70px; font-size: 0.85rem;"
                  class="text-weight-bold"
                >
                  <template v-slot:selected>
                    <div class="text-white">{{ filterMiddleWh }}</div>
                  </template>
                </q-select>
              </div>
            </div>'''
)

# 2. Packing List -> Rename to Wahehouse Pre-Batch Package
packing_list_text = "".join(packing_list_card).replace(
    '<div class="text-subtitle2 text-weight-bold">Packing List</div>',
    '<div class="text-subtitle2 text-weight-bold">Warehouse Pre-Batch Package</div>'
)

# 3. Table Card -> Remove Q-Select, change title to "List all PreBatch Package of this Warehouse"
table_card_text = "".join(table_card).replace(
'''            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="warehouse" size="sm" />
                <div class="text-subtitle2 text-weight-bold">Warehouse Pre-Batch Packing</div>
              </div>
              <div class="row items-center q-gutter-sm">
                <q-select
                  v-model="filterMiddleWh"
                  :options="['FH', 'SPP']"
                  dense
                  borderless
                  dark
                  options-dense
                  style="width: 70px; font-size: 0.85rem;"
                  class="text-weight-bold"
                >
                  <template v-slot:selected>
                    <div class="text-white">{{ filterMiddleWh }}</div>
                  </template>
                </q-select>
                <q-badge color="white" text-color="blue-8" class="text-weight-bold">
                  <q-spinner-dots v-if="loadingRecords" size="14px" color="blue-8" class="q-mr-xs" />
                  {{ middlePanelFH.length + middlePanelSPP.length }}
                </q-badge>
              </div>
            </div>''',
'''            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="warehouse" size="sm" />
                <div class="text-subtitle2 text-weight-bold" style="font-size: 0.8rem">List all PreBatch Package of this Warehouse</div>
              </div>
              <div class="row items-center q-gutter-sm">
                <q-badge color="white" text-color="blue-8" class="text-weight-bold">
                  <q-spinner-dots v-if="loadingRecords" size="14px" color="blue-8" class="q-mr-xs" />
                  {{ middlePanelFH.length + middlePanelSPP.length }}
                </q-badge>
              </div>
            </div>'''
)

# We want 3 cards in the Middle Panel, but to not squish them we should use `col` vs `col-auto` 
# packing_box = col-auto
# packing_list = col
# table_list = col

packing_box_text = packing_box_text.replace('<q-card class="shadow-2" style="height: auto;">', '<q-card class="col-auto shadow-2">')
# Actually wait: let's give the first row heights.
# packing_list col
# table_card col (already has 'col column shadow-2')

middle_panel_wrapper = f"""      <!-- ═══ MIDDLE PANEL: Warehouse Pre-Batch ═══ -->
      <div class="col-4 column q-gutter-y-sm">
{packing_box_text}
{packing_list_text}
{table_card_text}      </div>
"""

right_panel_wrapper = f"""
      <!-- ═══ RIGHT PANEL: Transfer Logs ═══ -->
      <div class="col-4 column q-gutter-y-sm">
{"".join(transferred_card)}      </div>
"""

new_content = lines[:659] + [middle_panel_wrapper, right_panel_wrapper] + lines[1051:]

with open('app/pages/x50-PackingList.vue', 'w') as f:
    f.writelines(new_content)

print("Rewritten exactly as user requested!")

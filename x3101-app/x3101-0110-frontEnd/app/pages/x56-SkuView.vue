<script setup lang="ts">
definePageMeta({ title: 'SKU View' })
useHead({ title: 'SKU View | xMixing Control' })

import { appConfig } from '~/appConfig/config'
const apiBase = appConfig.apiBaseUrl

// ── Types ─────────────────────────────────────────────────
interface SkuStep {
  sku_id: string; phase_id: string; phase_number: string
  sub_step: number; action: string; re_code: string
  action_code: string; require: number; uom: string
  low_tol: number; high_tol: number; temperature: number | null
  agitator_rpm: number; high_shear_rpm: number
  step_condition?: string; destination?: string
}
interface Sku {
  id: number; sku_id: string; sku_name: string
  std_batch_size: number; uom: string; sku_group: number | null
  status: string; creat_by: string; created_at: string
  updated_at: string; steps: SkuStep[]
}
interface SkuGroup {
  id: number; group_code: string; group_name: string
  description: string; status: string
}

// ── State ─────────────────────────────────────────────────
const skus        = ref<Sku[]>([])
const groups      = ref<SkuGroup[]>([])
const loading     = ref(false)
const search      = ref('')
const statusFilter = ref<'All'|'Active'|'Deleted'>('Active')
const groupFilter  = ref<string>('All')
const selectedSku  = ref<Sku | null>(null)
const activeTab    = ref<'recipe'|'info'>('recipe')

// ── Fetch ─────────────────────────────────────────────────
const fetchAll = async () => {
  loading.value = true
  try {
    const [skuRes, grpRes] = await Promise.all([
      fetch(`${apiBase}/skus/?limit=500`),
      fetch(`${apiBase}/sku-groups/`)
    ])
    const skuData = await skuRes.json()
    skus.value   = skuData?.skus ?? skuData ?? []
    groups.value = await grpRes.json()
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

// ── Computed ──────────────────────────────────────────────
const groupOptions = computed(() => {
  const opts = [{ label: 'All Groups', value: 'All' }]
  groups.value.forEach(g => opts.push({ label: `${g.group_name}`, value: String(g.group_code) }))
  return opts
})

const filteredSkus = computed(() => {
  let r = skus.value
  if (statusFilter.value !== 'All') r = r.filter(s => s.status === statusFilter.value)
  if (groupFilter.value !== 'All')  r = r.filter(s => String(s.sku_group) === groupFilter.value)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    r = r.filter(s =>
      s.sku_id.toLowerCase().includes(q) ||
      s.sku_name.toLowerCase().includes(q)
    )
  }
  return r
})

const stats = computed(() => ({
  total:   skus.value.length,
  active:  skus.value.filter(s => s.status === 'Active').length,
  deleted: skus.value.filter(s => s.status === 'Deleted').length,
  groups:  new Set(skus.value.map(s => s.sku_group)).size,
}))

// Group steps by phase
const phases = computed(() => {
  if (!selectedSku.value?.steps) return []
  const map: Record<string, { phase_id: string; steps: SkuStep[] }> = {}
  for (const s of selectedSku.value.steps) {
    if (!map[s.phase_id]) map[s.phase_id] = { phase_id: s.phase_id, steps: [] }
    map[s.phase_id].steps.push(s)
  }
  return Object.values(map)
})

const totalRequire = computed(() =>
  selectedSku.value?.steps?.reduce((sum, s) => sum + (s.require || 0), 0) ?? 0
)

const groupName = (groupCode: number | null) => {
  if (!groupCode) return '—'
  const g = groups.value.find(g => String(g.group_code) === String(groupCode))
  return g ? g.group_name : String(groupCode)
}

// ── Helpers ───────────────────────────────────────────────
const actionColor = (code: string) => {
  if (String(code).startsWith('1')) return { bg: 'blue-1', fg: 'blue-9' }
  if (String(code).startsWith('2')) return { bg: 'teal-1', fg: 'teal-9' }
  return { bg: 'orange-1', fg: 'orange-9' }
}
const formatDate = (d: string) =>
  d ? new Date(d).toLocaleDateString('th-TH', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—'

watch([statusFilter, groupFilter, search], () => {
  if (selectedSku.value && !filteredSkus.value.find(s => s.id === selectedSku.value!.id))
    selectedSku.value = null
})

onMounted(fetchAll)
</script>

<template>
  <q-page class="sku-page">

    <!-- ══ Header ══════════════════════════════════════════ -->
    <div class="sku-header row items-center q-pa-sm q-gutter-sm">
      <q-icon name="science" size="28px" color="deep-purple-6" />
      <div>
        <div class="text-subtitle1 text-weight-bold">SKU Library</div>
        <div class="text-caption text-grey-6">รายการ SKU และ Recipe สูตรการผลิต</div>
      </div>
      <q-space />

      <!-- Stats -->
      <div class="stat-pill">
        <span class="stat-val text-deep-purple-6">{{ stats.total }}</span>
        <span class="stat-lbl">Total SKU</span>
      </div>
      <div class="stat-pill">
        <span class="stat-val text-green-7">{{ stats.active }}</span>
        <span class="stat-lbl">Active</span>
      </div>
      <div class="stat-pill">
        <span class="stat-val text-blue-7">{{ stats.groups }}</span>
        <span class="stat-lbl">Groups</span>
      </div>

      <q-btn flat round dense icon="refresh" color="deep-purple-6" @click="fetchAll" :loading="loading">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- ══ Filters ══════════════════════════════════════════ -->
    <div class="sku-filters row q-px-sm q-py-xs q-gutter-xs items-center">
      <q-input v-model="search" dense outlined placeholder="Search SKU ID / Name..." clearable
        style="min-width:200px; max-width:280px" bg-color="white">
        <template #prepend><q-icon name="search" size="xs" /></template>
      </q-input>

      <q-btn-toggle v-model="statusFilter"
        :options="[{label:'Active',value:'Active'},{label:'All',value:'All'},{label:'Deleted',value:'Deleted'}]"
        dense unelevated toggle-color="deep-purple-6" color="white" text-color="grey-7" rounded size="sm" />

      <q-select v-model="groupFilter" :options="groupOptions" dense outlined
        label="Group" emit-value map-options style="min-width:130px;" bg-color="white" />

      <div class="text-caption text-grey-6">{{ filteredSkus.length }} SKUs</div>
    </div>

    <!-- ══ Split View ═══════════════════════════════════════ -->
    <div class="sku-split">

      <!-- ── Left: SKU List ──────────────────────────────── -->
      <div class="sku-list">
        <div v-if="loading" class="text-center q-py-xl">
          <q-spinner-dots color="deep-purple-6" size="40px" />
        </div>

        <q-virtual-scroll v-else :items="filteredSkus" v-slot="{ item: sku }" style="height:100%">
          <div :key="sku.id"
            class="sku-card"
            :class="{
              'sku-card--active': selectedSku?.id === sku.id,
              'sku-card--deleted': sku.status === 'Deleted'
            }"
            @click="selectedSku = sku; activeTab = 'recipe'">

            <div class="row items-start no-wrap q-gutter-xs">
              <div class="col">
                <div class="row items-center q-gutter-xs">
                  <span class="text-caption text-weight-bold text-deep-purple-7">{{ sku.sku_id }}</span>
                  <q-chip v-if="sku.status === 'Deleted'" dense size="xs" color="red-2" text-color="red-8">Deleted</q-chip>
                </div>
                <div class="text-caption text-grey-8 q-mt-xs" style="line-height:1.3">{{ sku.sku_name }}</div>
                <div class="row items-center q-gutter-xs q-mt-xs">
                  <q-chip dense size="xs" color="blue-1" text-color="blue-9" icon="scale">
                    {{ sku.std_batch_size?.toLocaleString() }} {{ sku.uom }}
                  </q-chip>
                  <q-chip v-if="sku.sku_group" dense size="xs" color="purple-1" text-color="purple-9">
                    {{ groupName(sku.sku_group) }}
                  </q-chip>
                </div>
              </div>
              <div class="text-right col-shrink">
                <div class="text-caption text-grey-5">{{ sku.steps?.length || 0 }} steps</div>
              </div>
            </div>
          </div>
        </q-virtual-scroll>
      </div>

      <!-- ── Right: SKU Detail ───────────────────────────── -->
      <div class="sku-detail">

        <!-- Empty state -->
        <div v-if="!selectedSku" class="sku-empty">
          <q-icon name="science" size="64px" color="grey-3" />
          <div class="q-mt-md text-subtitle1 text-grey-4">Select a SKU to view recipe</div>
        </div>

        <template v-else>
          <!-- ─ SKU Title Bar ────────────────────────────── -->
          <div class="sku-detail-header q-px-md q-py-sm">
            <div class="row items-center">
              <div class="col">
                <div class="text-h6 text-weight-bold text-deep-purple-7">{{ selectedSku.sku_id }}</div>
                <div class="text-body2 text-grey-7">{{ selectedSku.sku_name }}</div>
              </div>
              <q-chip :color="selectedSku.status==='Active'?'green-6':'red-5'" text-color="white" dense>
                {{ selectedSku.status }}
              </q-chip>
            </div>

            <!-- Tabs -->
            <q-tabs v-model="activeTab" dense align="left" class="q-mt-xs"
              active-color="deep-purple-7" indicator-color="deep-purple-7">
              <q-tab name="recipe" icon="list_alt" label="Recipe Steps" />
              <q-tab name="info"   icon="info"     label="SKU Info" />
            </q-tabs>
          </div>

          <q-scroll-area style="flex:1; height:0">

            <!-- ═════ Tab: Recipe Steps ══════════════════ -->
            <div v-if="activeTab === 'recipe'" class="q-pa-md">

              <!-- Summary row -->
              <div class="row q-gutter-sm q-mb-md">
                <div class="recipe-stat-card">
                  <div class="recipe-stat-val text-deep-purple-7">{{ selectedSku.steps?.length || 0 }}</div>
                  <div class="recipe-stat-lbl">Total Steps</div>
                </div>
                <div class="recipe-stat-card">
                  <div class="recipe-stat-val text-blue-7">{{ phases.length }}</div>
                  <div class="recipe-stat-lbl">Phases</div>
                </div>
                <div class="recipe-stat-card">
                  <div class="recipe-stat-val text-teal-7">{{ totalRequire.toFixed(2) }}</div>
                  <div class="recipe-stat-lbl">Total Require ({{ selectedSku.uom }})</div>
                </div>
                <div class="recipe-stat-card">
                  <div class="recipe-stat-val text-orange-7">{{ selectedSku.std_batch_size?.toLocaleString() }}</div>
                  <div class="recipe-stat-lbl">Batch Size ({{ selectedSku.uom }})</div>
                </div>
              </div>

              <!-- Phase blocks -->
              <div v-for="phase in phases" :key="phase.phase_id" class="q-mb-md">
                <div class="phase-header row items-center q-gutter-xs q-mb-xs">
                  <q-icon name="layers" color="deep-purple-6" size="sm" />
                  <span class="text-caption text-weight-bold text-deep-purple-7">{{ phase.phase_id }}</span>
                  <span class="text-caption text-grey-5">{{ phase.steps.length }} steps</span>
                </div>

                <q-card flat bordered>
                  <q-markup-table dense flat separator="horizontal" class="recipe-tbl">
                    <thead>
                      <tr class="bg-deep-purple-1">
                        <th class="text-center" style="width:36px">Step</th>
                        <th class="text-center" style="width:68px">Code</th>
                        <th class="text-left">Action</th>
                        <th class="text-left">RE Code</th>
                        <th class="text-right">Require</th>
                        <th class="text-center">UOM</th>
                        <th class="text-center">Tol ±%</th>
                        <th class="text-center">Temp</th>
                        <th class="text-center">Agitator</th>
                        <th class="text-center">Hi-Shear</th>
                        <th class="text-left">Destination</th>
                        <th class="text-left">Condition</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="step in phase.steps" :key="step.sub_step" class="recipe-row">
                        <td class="text-center">
                          <q-chip dense size="xs" outline color="grey-6">{{ step.sub_step }}</q-chip>
                        </td>
                        <td class="text-center">
                          <q-chip dense size="xs"
                            :color="actionColor(step.action_code).bg"
                            :text-color="actionColor(step.action_code).fg">
                            {{ step.action_code }}
                          </q-chip>
                        </td>
                        <td class="text-caption">{{ step.action }}</td>
                        <td>
                          <span v-if="step.re_code" class="text-weight-bold text-deep-purple-7 text-caption">{{ step.re_code }}</span>
                          <span v-else class="text-grey-4">—</span>
                        </td>
                        <td class="text-right text-weight-bold text-caption">
                          {{ step.require?.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 }) }}
                        </td>
                        <td class="text-center text-caption text-grey-7">{{ step.uom }}</td>
                        <td class="text-center text-caption">
                          <span v-if="step.low_tol" class="text-orange-8">
                            ±{{ (step.low_tol * 100).toFixed(2) }}%
                          </span>
                          <span v-else class="text-grey-4">—</span>
                        </td>
                        <td class="text-center">
                          <q-chip v-if="step.temperature" dense size="xs" color="red-1" text-color="red-8">
                            {{ step.temperature }}°C
                          </q-chip>
                          <span v-else class="text-grey-4 text-caption">—</span>
                        </td>
                        <td class="text-center text-caption">
                          <span v-if="step.agitator_rpm" class="text-teal-8">{{ step.agitator_rpm }} rpm</span>
                          <span v-else class="text-grey-4">—</span>
                        </td>
                        <td class="text-center text-caption">
                          <span v-if="step.high_shear_rpm" class="text-deep-orange-7">{{ step.high_shear_rpm }} rpm</span>
                          <span v-else class="text-grey-4">—</span>
                        </td>
                        <td class="text-caption text-grey-7">{{ step.destination || '—' }}</td>
                        <td class="text-caption text-grey-7">{{ step.step_condition || '—' }}</td>
                      </tr>
                    </tbody>
                  </q-markup-table>
                </q-card>
              </div>
            </div>

            <!-- ═════ Tab: SKU Info ══════════════════════ -->
            <div v-if="activeTab === 'info'" class="q-pa-md">
              <q-card flat bordered>
                <q-card-section>
                  <div class="row q-gutter-lg">
                    <div class="col-12 col-md-5">
                      <div class="info-section-title">Basic Information</div>
                      <q-list dense separator>
                        <q-item v-for="row in [
                          { label:'SKU ID',       val: selectedSku.sku_id },
                          { label:'SKU Name',     val: selectedSku.sku_name },
                          { label:'Batch Size',   val: `${selectedSku.std_batch_size?.toLocaleString()} ${selectedSku.uom}` },
                          { label:'SKU Group',    val: groupName(selectedSku.sku_group) },
                          { label:'Status',       val: selectedSku.status },
                          { label:'Created By',   val: selectedSku.creat_by || '—' },
                          { label:'Created At',   val: formatDate(selectedSku.created_at) },
                          { label:'Updated At',   val: formatDate(selectedSku.updated_at) },
                        ]" :key="row.label">
                          <q-item-section class="text-caption text-grey-6" style="max-width:120px">{{ row.label }}</q-item-section>
                          <q-item-section class="text-caption text-weight-medium">{{ row.val }}</q-item-section>
                        </q-item>
                      </q-list>
                    </div>

                    <div class="col">
                      <div class="info-section-title">Recipe Summary</div>
                      <div class="row q-gutter-sm q-mt-sm">
                        <div v-for="phase in phases" :key="phase.phase_id"
                          class="phase-summary-card">
                          <div class="text-caption text-weight-bold text-deep-purple-7">{{ phase.phase_id }}</div>
                          <div class="text-h6 text-weight-bold">{{ phase.steps.length }}</div>
                          <div class="text-caption text-grey-6">steps</div>
                          <div class="text-caption text-primary q-mt-xs">
                            {{ phase.steps.reduce((s,x) => s + (x.require||0), 0).toFixed(2) }} {{ selectedSku.uom }}
                          </div>
                        </div>
                      </div>

                      <!-- RE Codes used -->
                      <div class="q-mt-md">
                        <div class="info-section-title">Materials Used</div>
                        <div class="row q-gutter-xs q-mt-sm">
                          <q-chip v-for="code in [...new Set(selectedSku.steps?.filter(s=>s.re_code).map(s=>s.re_code))]"
                            :key="code" dense color="blue-1" text-color="blue-9" size="sm" icon="inventory_2">
                            {{ code }}
                          </q-chip>
                        </div>
                      </div>
                    </div>
                  </div>
                </q-card-section>
              </q-card>
            </div>

          </q-scroll-area>
        </template>
      </div>
    </div>

  </q-page>
</template>

<style scoped>
/* ── Layout ─────────────────────────────────── */
.sku-page { display:flex; flex-direction:column; height:100vh; background:#f3f0fa; overflow:hidden; }
.sku-header { background:white; border-bottom:1px solid #e8e0f0; flex-shrink:0; }
.sku-filters { background:#faf8fc; border-bottom:1px solid #e8e0f0; flex-shrink:0; }
.sku-split { display:flex; flex:1; min-height:0; }

/* ── Left List ──────────────────────────────── */
.sku-list { width:320px; min-width:260px; background:white; border-right:1px solid #e8e0f0; overflow:hidden; display:flex; flex-direction:column; }
.sku-card { padding:10px 12px; border-bottom:1px solid #f4f0f8; cursor:pointer; transition:background 0.12s; }
.sku-card:hover { background:#f5f0ff; }
.sku-card--active { background:#ede7f6 !important; border-left:3px solid #7b1fa2; }
.sku-card--deleted { opacity:0.5; }

/* ── Right Detail ───────────────────────────── */
.sku-detail { flex:1; min-width:0; display:flex; flex-direction:column; overflow:hidden; background:#faf8fc; }
.sku-empty { flex:1; display:flex; align-items:center; justify-content:center; flex-direction:column; }
.sku-detail-header { background:white; border-bottom:1px solid #e8e0f0; flex-shrink:0; }

/* ── Stats ──────────────────────────────────── */
.stat-pill { display:flex; flex-direction:column; align-items:center; min-width:60px; border-left:1px solid #eee; padding:0 10px; }
.stat-val { font-size:20px; font-weight:700; line-height:1; }
.stat-lbl { font-size:9px; color:#aaa; text-transform:uppercase; letter-spacing:0.5px; }

/* ── Recipe stat cards ──────────────────────── */
.recipe-stat-card { background:white; border:1px solid #e8e0f0; border-radius:10px; padding:8px 14px; text-align:center; min-width:80px; }
.recipe-stat-val { font-size:20px; font-weight:700; line-height:1.1; }
.recipe-stat-lbl { font-size:10px; color:#9e9e9e; margin-top:2px; }

/* ── Phase ──────────────────────────────────── */
.phase-header { margin-bottom:4px; }

/* ── Recipe Table ───────────────────────────── */
.recipe-tbl :deep(th) { font-size:10px !important; font-weight:700; color:#555; padding:4px 6px !important; white-space:nowrap; }
.recipe-tbl :deep(td) { font-size:11px !important; padding:4px 6px !important; }
.recipe-row:hover { background:#f5f0ff; }

/* ── Info Tab ───────────────────────────────── */
.info-section-title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#7b1fa2; margin-bottom:6px; }
.phase-summary-card { background:white; border:1px solid #e8e0f0; border-radius:10px; padding:10px 16px; text-align:center; min-width:80px; }

/* ── Filter toggle ──────────────────────────── */
:deep(.q-btn-toggle .q-btn) { font-size:10px !important; padding:2px 8px !important; min-height:26px !important; }
</style>

<script setup lang="ts">
definePageMeta({ title: 'Production Plan' })
useHead({ title: 'Production Plan | xMixing Control' })

import { appConfig } from '~/appConfig/config'
const apiBase = appConfig.apiBaseUrl

// ── Types ─────────────────────────────────────────────────
interface Batch {
  id: number; batch_id: string; sku_id: string; plant: string
  batch_size: number; status: string; batch_prepare: boolean
  production: boolean; done: boolean
}
interface Plan {
  id: number; plan_id: string; sku_id: string; sku_name: string
  plant: string; total_volume: number; batch_size: number
  num_batches: number; start_date: string; finish_date: string
  status: string; flavour_house: boolean; spp: boolean
  created_at: string; batches: Batch[]
}
interface SkuStep {
  phase_id: string; phase_number: string; sub_step: number
  action: string; re_code: string; action_code: string
  require: number; uom: string; low_tol: number; high_tol: number
  temperature: number | null; step_condition?: string
  agitator_rpm?: number; high_shear_rpm?: number
}
interface Sku {
  sku_id: string; sku_name: string; std_batch_size: number
  uom: string; status: string; steps: SkuStep[]
}

// ── State ─────────────────────────────────────────────────
const plans       = ref<Plan[]>([])
const loading     = ref(false)
const search      = ref('')
const statusFilter = ref('All')
const plantFilter  = ref('All')
const selectedPlan = ref<Plan | null>(null)
const skuData      = ref<Sku | null>(null)
const skuLoading   = ref(false)
const page         = ref(1)
const rowsPerPage  = ref(20)

// ── Constants ─────────────────────────────────────────────
const statusOptions = ['All', 'Planned', 'In-Progress', 'Completed', 'Cancelled']
const plantOptions  = ['All', 'Line-1', 'Line-2', 'Line-3']

const statusColor: Record<string, string> = {
  'Planned': 'blue-7', 'In-Progress': 'orange-8',
  'Completed': 'green-7', 'Cancelled': 'red-6',
}
const batchStatusColor: Record<string, string> = {
  'Created': 'grey-5', 'Prepared': 'blue-5',
  'In-Progress': 'orange-7', 'Done': 'green-7',
}
const actionCodeColor = (code: string) => {
  if (String(code).startsWith('1')) return { bg: 'blue-1', text: 'blue-9' }
  if (String(code).startsWith('2')) return { bg: 'teal-1', text: 'teal-9' }
  return { bg: 'orange-1', text: 'orange-9' }
}
const plantChipColor = (plant: string) => {
  if (plant === 'Line-1') return { bg: 'blue-1', text: 'blue-8' }
  if (plant === 'Line-2') return { bg: 'teal-1', text: 'teal-8' }
  return { bg: 'purple-1', text: 'purple-8' }
}

// ── Computed ──────────────────────────────────────────────
const filteredPlans = computed(() => {
  let r = plans.value
  if (statusFilter.value !== 'All') r = r.filter(p => p.status === statusFilter.value)
  if (plantFilter.value  !== 'All') r = r.filter(p => p.plant  === plantFilter.value)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    r = r.filter(p =>
      p.plan_id.toLowerCase().includes(q) ||
      p.sku_id.toLowerCase().includes(q) ||
      p.sku_name.toLowerCase().includes(q)
    )
  }
  return r
})
const totalPages    = computed(() => Math.ceil(filteredPlans.value.length / rowsPerPage.value))
const paginatedPlans = computed(() => {
  const s = (page.value - 1) * rowsPerPage.value
  return filteredPlans.value.slice(s, s + rowsPerPage.value)
})
const stats = computed(() => ({
  total:      plans.value.length,
  planned:    plans.value.filter(p => p.status === 'Planned').length,
  inProgress: plans.value.filter(p => p.status === 'In-Progress').length,
  completed:  plans.value.filter(p => p.status === 'Completed').length,
  cancelled:  plans.value.filter(p => p.status === 'Cancelled').length,
}))

// Group SKU steps by phase
const skuPhases = computed(() => {
  if (!skuData.value?.steps) return []
  const phases: Record<string, { phase_id: string; phase_number: string; steps: SkuStep[] }> = {}
  for (const s of skuData.value.steps) {
    if (!phases[s.phase_id]) phases[s.phase_id] = { phase_id: s.phase_id, phase_number: s.phase_number, steps: [] }
    phases[s.phase_id].steps.push(s)
  }
  return Object.values(phases)
})

const batchDone = (b: Batch) => b.status === 'Done' || b.done
const batchProgress = (batches: Batch[]) => {
  if (!batches?.length) return 0
  return Math.round((batches.filter(batchDone).length / batches.length) * 100)
}
const formatDate = (d: string) =>
  d ? new Date(d).toLocaleDateString('th-TH', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '-'

// ── Methods ───────────────────────────────────────────────
const fetchPlans = async () => {
  loading.value = true
  try {
    const res  = await fetch(`${apiBase}/production-plans/?limit=500`)
    const data = await res.json()
    plans.value = data.plans ?? (Array.isArray(data) ? data : [])
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const selectPlan = async (plan: Plan) => {
  selectedPlan.value = plan
  skuData.value = null
  skuLoading.value = true
  try {
    const res = await fetch(`${apiBase}/skus/${plan.sku_id}`)
    skuData.value = await res.json()
  } catch (e) { console.error(e) }
  finally { skuLoading.value = false }
}

watch([statusFilter, plantFilter, search], () => { page.value = 1 })
onMounted(fetchPlans)
</script>

<template>
  <q-page class="pp-page">

    <!-- ══ Top Header ══════════════════════════════════════ -->
    <div class="pp-header row items-center q-pa-sm q-gutter-sm">
      <q-icon name="calendar_month" size="28px" color="primary" />
      <div>
        <div class="text-subtitle1 text-weight-bold">Production Plan</div>
        <div class="text-caption text-grey-6">แผนการผลิตและรายละเอียด SKU</div>
      </div>
      <q-space />

      <!-- Stats inline -->
      <div v-for="(val, key) in { Total: stats.total, Planned: stats.planned, 'In-Progress': stats.inProgress, Completed: stats.completed, Cancelled: stats.cancelled }"
        :key="key" class="stat-pill">
        <span class="stat-pill-val"
          :class="key==='Total'?'text-blue-8':key==='Planned'?'text-blue-6':key==='In-Progress'?'text-orange-8':key==='Completed'?'text-green-7':'text-red-6'">
          {{ val }}
        </span>
        <span class="stat-pill-lbl">{{ key }}</span>
      </div>

      <q-btn flat round icon="refresh" color="primary" dense @click="fetchPlans" :loading="loading">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- ══ Filters ══════════════════════════════════════════ -->
    <div class="pp-filters row q-px-sm q-py-xs q-gutter-xs items-center">
      <q-input v-model="search" dense outlined placeholder="Search Plan / SKU..." clearable
        style="min-width:180px; max-width:260px" bg-color="white">
        <template #prepend><q-icon name="search" size="xs" /></template>
      </q-input>
      <q-btn-toggle v-model="statusFilter"
        :options="statusOptions.map(s=>({label:s, value:s}))"
        dense unelevated toggle-color="primary" color="white" text-color="grey-7"
        rounded size="sm" class="filter-tog" />
      <q-select v-model="plantFilter" :options="plantOptions" dense outlined
        label="Plant" emit-value map-options style="min-width:100px;" bg-color="white" />
      <div class="text-caption text-grey-6 q-ml-xs">{{ filteredPlans.length }} plans</div>
    </div>

    <!-- ══ Split View ═══════════════════════════════════════ -->
    <div class="pp-split">

      <!-- ── Left: Plan List ─────────────────────────────── -->
      <div class="pp-list">
        <q-virtual-scroll :items="paginatedPlans" v-slot="{ item: plan }" style="height:100%">
          <div :key="plan.id"
            class="plan-card"
            :class="{ 'plan-card--active': selectedPlan?.id === plan.id }"
            @click="selectPlan(plan)">

            <div class="row items-start no-wrap">
              <div class="col">
                <div class="row items-center q-gutter-xs">
                  <span class="text-weight-bold text-primary text-caption">{{ plan.plan_id }}</span>
                  <q-chip dense :color="statusColor[plan.status]||'grey-5'" text-color="white" size="xs">
                    {{ plan.status }}
                  </q-chip>
                  <q-chip dense :color="plantChipColor(plan.plant).bg" :text-color="plantChipColor(plan.plant).text" size="xs">
                    {{ plan.plant }}
                  </q-chip>
                </div>
                <div class="text-caption text-weight-medium q-mt-xs">{{ plan.sku_id }}</div>
                <div class="text-caption text-grey-6 ellipsis" style="max-width:220px">{{ plan.sku_name }}</div>
              </div>
              <div class="text-right col-shrink">
                <div class="text-caption text-weight-bold">{{ plan.total_volume?.toLocaleString() }} kg</div>
                <div class="text-caption text-grey-6">{{ plan.num_batches }} batches</div>
              </div>
            </div>

            <!-- Progress bar -->
            <div class="q-mt-xs">
              <q-linear-progress :value="batchProgress(plan.batches)/100"
                :color="batchProgress(plan.batches)===100?'green-6':'orange-6'"
                rounded size="5px" />
              <div class="row justify-between">
                <span class="text-caption text-grey-5">{{ formatDate(plan.start_date) }} → {{ formatDate(plan.finish_date) }}</span>
                <span class="text-caption text-grey-6">{{ batchProgress(plan.batches) }}%</span>
              </div>
            </div>
          </div>
        </q-virtual-scroll>

        <!-- Pagination -->
        <div class="pp-list-footer row items-center justify-between q-px-sm">
          <q-pagination v-if="totalPages > 1" v-model="page" :max="totalPages"
            direction-links flat color="primary" size="sm" />
          <q-select v-model="rowsPerPage" :options="[10,20,50,100]" dense borderless
            label="Rows/page" style="width:90px" emit-value map-options />
        </div>
      </div>

      <!-- ── Right: Detail Panel ─────────────────────────── -->
      <div class="pp-detail">

        <!-- Empty state -->
        <div v-if="!selectedPlan" class="pp-empty col flex-center column text-grey-4">
          <q-icon name="touch_app" size="64px" />
          <div class="q-mt-md text-subtitle1">Select a plan to view details</div>
        </div>

        <template v-else>
          <!-- ─ Plan Header ──────────────────────────────── -->
          <div class="detail-plan-header q-pa-md">
            <div class="row items-start">
              <div class="col">
                <div class="text-h6 text-weight-bold text-primary">{{ selectedPlan.plan_id }}</div>
                <div class="text-caption text-grey-6">
                  {{ formatDate(selectedPlan.start_date) }} → {{ formatDate(selectedPlan.finish_date) }}
                  &nbsp;·&nbsp; {{ selectedPlan.total_volume?.toLocaleString() }} kg
                  &nbsp;·&nbsp; {{ selectedPlan.num_batches }} batches
                </div>
              </div>
              <q-chip :color="statusColor[selectedPlan.status]||'grey-5'" text-color="white" dense>
                {{ selectedPlan.status }}
              </q-chip>
            </div>
          </div>

          <q-scroll-area style="flex:1; height:0">

            <!-- ─ SKU Info Card ─────────────────────────── -->
            <div class="q-pa-md q-pb-xs">
              <div class="section-title q-mb-sm">
                <q-icon name="inventory_2" color="primary" size="sm" />
                SKU Information
              </div>
              <q-card flat bordered class="sku-info-card">
                <q-card-section class="q-py-sm">
                  <div v-if="skuLoading" class="text-center q-py-md">
                    <q-spinner-dots color="primary" size="30px" />
                  </div>
                  <template v-else-if="skuData">
                    <div class="row q-gutter-md items-center">
                      <div>
                        <div class="info-label">SKU ID</div>
                        <div class="text-weight-bold text-primary">{{ skuData.sku_id }}</div>
                      </div>
                      <div class="col">
                        <div class="info-label">Name</div>
                        <div class="text-weight-medium">{{ skuData.sku_name }}</div>
                      </div>
                      <div>
                        <div class="info-label">Batch Size</div>
                        <div class="text-weight-bold">{{ skuData.std_batch_size?.toLocaleString() }} {{ skuData.uom }}</div>
                      </div>
                      <q-chip dense :color="skuData.status==='Active'?'green-6':'red-5'" text-color="white" size="sm">
                        {{ skuData.status }}
                      </q-chip>
                    </div>
                  </template>
                </q-card-section>
              </q-card>
            </div>

            <!-- ─ Batch List ────────────────────────────── -->
            <div class="q-px-md q-pb-xs">
              <div class="section-title q-mb-sm">
                <q-icon name="view_list" color="primary" size="sm" />
                Batches ({{ selectedPlan.batches?.length || 0 }})
                <q-linear-progress class="q-ml-sm" style="width:80px; display:inline-flex;"
                  :value="batchProgress(selectedPlan.batches)/100"
                  :color="batchProgress(selectedPlan.batches)===100?'green-6':'orange-6'"
                  rounded size="8px" />
                <span class="text-caption text-grey-6 q-ml-xs">{{ batchProgress(selectedPlan.batches) }}%</span>
              </div>

              <div class="row q-gutter-xs">
                <div v-for="batch in selectedPlan.batches" :key="batch.id"
                  class="batch-chip-card">
                  <div class="row items-center q-gutter-xs">
                    <q-icon :name="batchDone(batch)?'check_circle':batch.production?'precision_manufacturing':batch.batch_prepare?'hourglass_top':'radio_button_unchecked'"
                      :color="batchDone(batch)?'green-6':batch.production?'orange-7':batch.batch_prepare?'blue-5':'grey-4'"
                      size="14px" />
                    <span class="text-caption text-weight-medium">{{ batch.batch_id.split('-').slice(-1)[0] }}</span>
                  </div>
                  <q-chip dense size="xs" :color="batchStatusColor[batch.status]||'grey-4'" text-color="white" class="q-mt-xs">
                    {{ batch.status }}
                  </q-chip>
                  <q-tooltip>
                    <div class="text-caption">{{ batch.batch_id }}</div>
                    <div>{{ batch.batch_size?.toLocaleString() }} kg · {{ batch.plant }}</div>
                  </q-tooltip>
                </div>
              </div>
            </div>

            <!-- ─ SKU Recipe Steps ──────────────────────── -->
            <div class="q-px-md q-pb-md">
              <div class="section-title q-mb-sm q-mt-xs">
                <q-icon name="list_alt" color="primary" size="sm" />
                Recipe Steps
                <span v-if="skuData" class="text-caption text-grey-6 q-ml-xs">({{ skuData.steps?.length }} steps)</span>
              </div>

              <div v-if="skuLoading" class="text-center q-py-lg">
                <q-spinner-dots color="primary" size="36px" />
              </div>

              <template v-else-if="skuData && skuPhases.length">
                <div v-for="phase in skuPhases" :key="phase.phase_id" class="phase-block q-mb-sm">
                  <!-- Phase Header -->
                  <div class="phase-label row items-center q-gutter-xs q-mb-xs">
                    <q-chip dense color="primary" text-color="white" size="sm" icon="layers">
                      {{ phase.phase_id }}
                    </q-chip>
                    <span class="text-caption text-grey-6">{{ phase.steps.length }} steps</span>
                  </div>

                  <!-- Steps Table -->
                  <q-card flat bordered>
                    <q-markup-table dense flat separator="horizontal" class="recipe-table">
                      <thead>
                        <tr class="bg-grey-1">
                          <th class="text-center" style="width:36px">Step</th>
                          <th class="text-center" style="width:64px">Code</th>
                          <th class="text-left">Action</th>
                          <th class="text-left">RE Code</th>
                          <th class="text-right">Require</th>
                          <th class="text-center">UOM</th>
                          <th class="text-center">Tol.</th>
                          <th class="text-center">Temp</th>
                          <th class="text-center">Agitator</th>
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
                              :color="actionCodeColor(step.action_code).bg"
                              :text-color="actionCodeColor(step.action_code).text">
                              {{ step.action_code }}
                            </q-chip>
                          </td>
                          <td class="text-caption">{{ step.action }}</td>
                          <td>
                            <span v-if="step.re_code" class="text-weight-medium text-primary text-caption">{{ step.re_code }}</span>
                            <span v-else class="text-grey-4 text-caption">—</span>
                          </td>
                          <td class="text-right text-weight-bold text-caption">
                            {{ step.require?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 3 }) }}
                          </td>
                          <td class="text-center text-caption text-grey-7">{{ step.uom }}</td>
                          <td class="text-center text-caption">
                            <span v-if="step.low_tol" class="text-orange-8">
                              ±{{ (step.low_tol * 100).toFixed(1) }}%
                            </span>
                            <span v-else class="text-grey-4">—</span>
                          </td>
                          <td class="text-center text-caption">
                            <span v-if="step.temperature" class="text-red-7">{{ step.temperature }}°C</span>
                            <span v-else class="text-grey-4">—</span>
                          </td>
                          <td class="text-center text-caption text-grey-7">
                            {{ step.agitator_rpm ? step.agitator_rpm + ' rpm' : '—' }}
                          </td>
                          <td class="text-caption text-grey-7">{{ step.step_condition || '—' }}</td>
                        </tr>
                      </tbody>
                    </q-markup-table>
                  </q-card>
                </div>
              </template>
            </div>
          </q-scroll-area>
        </template>
      </div>
    </div>

  </q-page>
</template>

<style scoped>
/* ── Layout ─────────────────────────────────────────── */
.pp-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f0f2f8;
  overflow: hidden;
}
.pp-header {
  background: white;
  border-bottom: 1px solid #e4e8f0;
  flex-shrink: 0;
}
.pp-filters {
  background: #f8f9fc;
  border-bottom: 1px solid #e4e8f0;
  flex-shrink: 0;
}
.pp-split {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 0;
}
/* ── Left List ───────────────────────────────────────── */
.pp-list {
  width: 340px;
  min-width: 280px;
  max-width: 380px;
  background: white;
  border-right: 1px solid #e4e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pp-list-footer {
  border-top: 1px solid #eee;
  padding: 4px 8px;
  flex-shrink: 0;
}
/* ── Plan Card ───────────────────────────────────────── */
.plan-card {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.12s;
}
.plan-card:hover { background: #f4f7ff; }
.plan-card--active {
  background: #e8f0fe !important;
  border-left: 3px solid #1976d2;
}
/* ── Right Detail ────────────────────────────────────── */
.pp-detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f5f7fb;
}
.pp-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}
/* ── Detail sections ─────────────────────────────────── */
.detail-plan-header {
  background: white;
  border-bottom: 1px solid #e8eaf0;
  flex-shrink: 0;
}
.section-title {
  font-size: 12px;
  font-weight: 700;
  color: #444;
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.sku-info-card { background: white; }
.info-label { font-size: 10px; color: #9e9e9e; text-transform: uppercase; letter-spacing: 0.4px; }
/* ── Batch Chips ─────────────────────────────────────── */
.batch-chip-card {
  background: white;
  border: 1px solid #e8eaf0;
  border-radius: 8px;
  padding: 6px 10px;
  min-width: 72px;
  text-align: center;
  cursor: default;
}
/* ── Recipe Table ────────────────────────────────────── */
.phase-block {}
.phase-label { margin-bottom: 4px; }
.recipe-table :deep(th) {
  font-size: 10px !important;
  font-weight: 700;
  color: #666;
  padding: 4px 6px !important;
  white-space: nowrap;
}
.recipe-table :deep(td) {
  font-size: 11px !important;
  padding: 4px 6px !important;
}
.recipe-row:hover { background: #f5f8ff; }
/* ── Stats ───────────────────────────────────────────── */
.stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 52px;
  border-left: 1px solid #eee;
  padding: 0 10px;
}
.stat-pill-val { font-size: 18px; font-weight: 700; line-height: 1; }
.stat-pill-lbl { font-size: 9px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; }
/* ── Filter toggle ───────────────────────────────────── */
.filter-tog :deep(.q-btn) {
  font-size: 10px !important;
  padding: 2px 8px !important;
  min-height: 26px !important;
}
</style>

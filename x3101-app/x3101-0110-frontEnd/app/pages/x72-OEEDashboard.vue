<template>
  <q-page class="oee-page">

    <!-- ── Top Bar (non-sticky, let Quasar layout scroll) ── -->
    <div class="oee-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:12px;flex-wrap:wrap">
      <q-icon name="analytics" size="24px" color="lime-4" />
      <span class="text-subtitle1 text-white text-weight-bold">OEE Dashboard</span>
      <q-chip dense color="lime-9" text-color="lime-2" size="sm" icon="precision_manufacturing">Mixing Plant</q-chip>
      <q-space />

      <!-- Plant Filter -->
      <span class="text-caption text-grey-5">PLANT:</span>
      <q-btn-toggle
        v-model="selectedPlant"
        :options="[{label:'All',value:'all'},{label:'1',value:'1'},{label:'2',value:'2'},{label:'3',value:'3'}]"
        dense unelevated rounded
        color="blue-grey-8" text-color="grey-4"
        toggle-color="lime-8" toggle-text-color="white"
        size="sm"
        @update:model-value="loadData"
      />

      <!-- Period Filter -->
      <span class="text-caption text-grey-5">PERIOD:</span>
      <q-btn-toggle
        v-model="period"
        :options="[{label:'7d',value:7},{label:'30d',value:30},{label:'90d',value:90}]"
        dense unelevated rounded
        color="blue-grey-8" text-color="grey-4"
        toggle-color="cyan-8" toggle-text-color="white"
        size="sm"
        @update:model-value="loadData"
      />

      <q-btn flat dense round icon="refresh" color="grey-4" @click="loadData" :loading="loading" />
    </div>

    <div class="q-px-lg q-pb-xl" v-if="!loading && stats">

      <!-- ── Row 1: OEE + A/P/Q ── -->
      <div class="row q-col-gutter-md q-mb-md">

        <!-- Main OEE -->
        <div class="col-12 col-md-4">
          <div class="oee-card h-100 flex column items-center justify-center q-pa-lg">
            <div class="text-caption text-grey-5 text-weight-bold q-mb-md" style="letter-spacing:2px">OVERALL OEE · LAST {{ period }} DAYS</div>
            <div v-if="selectedPlant !== 'all'" class="text-caption text-lime-4 q-mb-sm">Plant {{ selectedPlant }}</div>
            <div v-else class="text-caption text-grey-5 q-mb-sm">All Plants</div>

            <!-- SVG Donut -->
            <div style="position:relative;width:180px;height:180px">
              <svg viewBox="0 0 36 36" style="width:100%;height:100%;transform:rotate(-90deg)">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1e293b" stroke-width="3.8"/>
                <!-- Quality ring -->
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#22c55e"
                  stroke-width="3.8" stroke-dasharray="100 100"
                  :stroke-dasharray="`${stats.quality} ${100-stats.quality}`" stroke-linecap="round"/>
                <!-- Performance ring (inner) -->
                <circle cx="18" cy="18" r="11.5" fill="none" stroke="#f59e0b"
                  stroke-width="3.2" :stroke-dasharray="`${stats.performance} ${100-stats.performance}`" stroke-linecap="round"/>
                <!-- Availability ring (innermost) -->
                <circle cx="18" cy="18" r="7.5" fill="none" stroke="#3b82f6"
                  stroke-width="3" :stroke-dasharray="`${stats.availability} ${100-stats.availability}`" stroke-linecap="round"/>
              </svg>
              <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center">
                <div class="text-h4 text-weight-bolder text-white">{{ stats.oee }}%</div>
                <div class="text-caption text-grey-5">OEE</div>
              </div>
            </div>

            <!-- Legend -->
            <div class="row q-mt-md" style="gap:16px">
              <div class="text-center">
                <div class="text-caption text-blue-4">Availability</div>
                <div class="text-subtitle1 text-weight-bold text-white">{{ stats.availability }}%</div>
              </div>
              <div class="text-center">
                <div class="text-caption text-amber-4">Performance</div>
                <div class="text-subtitle1 text-weight-bold text-white">{{ stats.performance }}%</div>
              </div>
              <div class="text-center">
                <div class="text-caption text-green-4">Quality</div>
                <div class="text-subtitle1 text-weight-bold text-white">{{ stats.quality }}%</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Per-Plant Cards -->
        <div class="col-12 col-md-8">
          <div class="row q-col-gutter-md h-100">
            <div v-for="p in ['1','2','3']" :key="p" class="col-12 col-sm-4">
              <div class="oee-card q-pa-md" :class="`plant-border-${p}`">
                <div class="row items-center q-mb-sm">
                  <q-icon name="factory" :color="plantColor(p)" size="18px" class="q-mr-xs"/>
                  <span class="text-weight-bold text-white text-subtitle2">Plant {{ p }}</span>
                  <q-space/>
                  <q-chip dense :color="plantStats[p]?.oee >= 65 ? 'positive' : 'warning'" text-color="white" size="xs">
                    {{ plantStats[p]?.oee ?? '--' }}%
                  </q-chip>
                </div>

                <!-- Mini donut -->
                <div class="flex flex-center q-mb-sm">
                  <div style="position:relative;width:90px;height:90px">
                    <svg viewBox="0 0 36 36" style="width:100%;height:100%;transform:rotate(-90deg)">
                      <circle cx="18" cy="18" r="14" fill="none" stroke="#1e293b" stroke-width="4"/>
                      <circle cx="18" cy="18" r="14" fill="none" :stroke="plantColorHex(p)"
                        stroke-width="4" :stroke-dasharray="`${plantStats[p]?.oee ?? 0} ${100-(plantStats[p]?.oee ?? 0)}`"
                        stroke-linecap="round"/>
                    </svg>
                    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center">
                      <div class="text-body1 text-weight-bolder text-white">{{ plantStats[p]?.oee ?? '--' }}%</div>
                    </div>
                  </div>
                </div>

                <div class="q-gutter-xs">
                  <div v-for="(val, key) in {A: plantStats[p]?.availability, P: plantStats[p]?.performance, Q: plantStats[p]?.quality}" :key="key"
                    class="row items-center" style="gap:6px">
                    <span class="text-caption text-grey-5" style="width:14px">{{ key }}</span>
                    <q-linear-progress :value="(val??0)/100" :color="key==='A'?'blue-5':key==='P'?'amber-5':'green-5'"
                      track-color="blue-grey-9" class="col" style="height:6px;border-radius:3px"/>
                    <span class="text-caption text-grey-4" style="width:34px;text-align:right">{{ val ?? '--' }}%</span>
                  </div>
                </div>

                <div class="q-mt-sm text-caption text-grey-6 text-center">{{ plantStats[p]?.doneBatches ?? 0 }} / {{ plantStats[p]?.totalBatches ?? 0 }} batches done</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Row 2: Batch Status Breakdown ── -->
      <div class="row q-col-gutter-md q-mb-md">
        <div class="col-12 col-md-6">
          <div class="oee-card q-pa-md">
            <div class="text-caption text-grey-5 text-weight-bold q-mb-md" style="letter-spacing:2px">BATCH STATUS BREAKDOWN</div>
            <div v-for="s in statusBreakdown" :key="s.label" class="row items-center q-mb-sm" style="gap:10px">
              <q-icon :name="s.icon" :color="s.color" size="16px"/>
              <div style="width:130px;font-size:12px" :class="`text-${s.color}`">{{ s.label }}</div>
              <q-linear-progress
                :value="s.pct/100"
                :color="s.color"
                track-color="blue-grey-9"
                class="col"
                style="height:14px;border-radius:4px"
              />
              <span class="text-caption text-grey-4" style="width:40px;text-align:right">{{ s.count }}</span>
              <span class="text-caption text-grey-6" style="width:36px;text-align:right">{{ s.pct }}%</span>
            </div>
          </div>
        </div>

        <!-- Summary stats -->
        <div class="col-12 col-md-6">
          <div class="oee-card q-pa-md">
            <div class="text-caption text-grey-5 text-weight-bold q-mb-md" style="letter-spacing:2px">PRODUCTION SUMMARY</div>
            <div class="row q-col-gutter-md">
              <div v-for="m in summaryMetrics" :key="m.label" class="col-6">
                <div class="stat-box q-pa-md rounded-borders text-center">
                  <q-icon :name="m.icon" :color="m.color" size="24px" class="q-mb-xs"/>
                  <div class="text-h5 text-weight-bolder text-white">{{ m.value }}</div>
                  <div class="text-caption text-grey-5">{{ m.label }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Row 3: ApexChart Trend ── -->
      <div class="oee-card q-pa-md q-mb-md">
        <div class="text-caption text-grey-5 text-weight-bold q-mb-sm" style="letter-spacing:2px">OEE TREND (BATCH COMPLETION RATE BY DAY)</div>
        <apexchart v-if="trendSeries.length" type="bar" height="180"
          :options="trendOptions" :series="trendSeries" />
        <div v-else class="flex flex-center text-grey-6" style="height:120px">No trend data</div>
      </div>

    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="flex flex-center" style="height:60vh">
      <div class="text-center">
        <q-spinner-dots color="lime-4" size="48px"/>
        <div class="text-grey-5 q-mt-md">Calculating OEE...</div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { appConfig } from '~/appConfig/config'

const { getAuthHeader } = useAuth()
const apiBase = appConfig.apiBaseUrl

const loading = ref(false)
const selectedPlant = ref<string>('all')
const period = ref<number>(30)
const allBatches = ref<any[]>([])

// ── Load Data ──────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/production-plans/`, {
      headers: getAuthHeader() as Record<string, string>,
      query: { status: 'all', limit: 1000 }
    })
    const plans: any[] = Array.isArray(res) ? res : (res?.plans ?? [])
    const flat: any[] = []
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - period.value)

    plans.forEach((p: any) => {
      ;(p.batches || []).forEach((b: any) => {
        const batchDate = new Date(b.updated_at || b.created_at || 0)
        if (batchDate >= cutoff) {
          flat.push({
            ...b,
            sku_name: p.sku_name || b.sku_id,
            plant: b.plant || p.plant || '1',
            date: batchDate.toISOString().slice(0, 10)
          })
        }
      })
    })
    allBatches.value = flat
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

// ── Filtered batches ───────────────────────────────────────
const filteredBatches = computed(() => {
  if (selectedPlant.value === 'all') return allBatches.value
  return allBatches.value.filter(b => String(b.plant || '').includes(selectedPlant.value))
})

// ── OEE per plant ─────────────────────────────────────────
function calcOEE(batches: any[]) {
  const total = batches.length
  if (!total) return { availability: 0, performance: 0, quality: 0, oee: 0, doneBatches: 0, totalBatches: 0 }
  const done = batches.filter(b => b.status === 'Done').length
  const cancelled = batches.filter(b => b.status === 'Cancelled').length
  const running = batches.filter(b => ['In-Progress', 'Prepared', 'Created'].includes(b.status)).length
  const availability = Math.round((done + running) / total * 100)
  const performance  = Math.round(done / Math.max(total - cancelled, 1) * 100)
  const quality      = cancelled === 0 ? 100 : Math.round(done / (done + cancelled) * 100)
  const oee = Math.round(availability * performance * quality / 10000)
  return { availability, performance, quality, oee, doneBatches: done, totalBatches: total }
}

const stats = computed(() => calcOEE(filteredBatches.value))

const plantStats = computed(() => {
  const result: Record<string, any> = {}
  for (const p of ['1','2','3']) {
    const pBatches = allBatches.value.filter(b => String(b.plant || '').includes(p))
    result[p] = calcOEE(pBatches)
  }
  return result
})

// ── Status Breakdown ──────────────────────────────────────
const statusBreakdown = computed(() => {
  const total = filteredBatches.value.length || 1
  const statuses = [
    { label: 'Done',        icon: 'check_circle', color: 'positive',  key: 'Done' },
    { label: 'In-Progress', icon: 'sync',         color: 'orange-5',  key: 'In-Progress' },
    { label: 'Prepared',    icon: 'inventory',    color: 'blue-4',    key: 'Prepared' },
    { label: 'Created',     icon: 'schedule',     color: 'grey-5',    key: 'Created' },
    { label: 'Cancelled',   icon: 'cancel',       color: 'negative',  key: 'Cancelled' },
    { label: 'Hold',        icon: 'pause_circle', color: 'amber-5',   key: 'Hold' },
  ]
  return statuses.map(s => {
    const count = filteredBatches.value.filter(b => b.status === s.key).length
    return { ...s, count, pct: Math.round(count / total * 100) }
  }).filter(s => s.count > 0)
})

// ── Summary Metrics ───────────────────────────────────────
const summaryMetrics = computed(() => {
  const b = filteredBatches.value
  const total = b.length
  const done  = b.filter(x => x.status === 'Done').length
  const plants = [...new Set(b.map(x => x.plant).filter(Boolean))].length
  const skus   = [...new Set(b.map(x => x.sku_id).filter(Boolean))].length
  return [
    { label: 'Total Batches',  icon: 'layers',           color: 'cyan-4',   value: total },
    { label: 'Completed',      icon: 'check_circle',     color: 'positive', value: done },
    { label: 'Active Plants',  icon: 'factory',          color: 'lime-4',   value: plants || '—' },
    { label: 'SKU Types',      icon: 'category',         color: 'purple-4', value: skus },
  ]
})

// ── Trend Chart ───────────────────────────────────────────
const trendSeries = computed(() => {
  const byDay: Record<string, { done: number; total: number }> = {}
  for (const b of filteredBatches.value) {
    if (!byDay[b.date]) byDay[b.date] = { done: 0, total: 0 }
    byDay[b.date].total++
    if (b.status === 'Done') byDay[b.date].done++
  }
  const sorted = Object.keys(byDay).sort()
  if (!sorted.length) return []
  return [{
    name: 'Done',
    data: sorted.map(d => byDay[d].done)
  }, {
    name: 'Total',
    data: sorted.map(d => byDay[d].total)
  }]
})

const trendOptions = computed(() => {
  const byDay: Record<string, any> = {}
  for (const b of filteredBatches.value) {
    if (!byDay[b.date]) byDay[b.date] = { done: 0, total: 0 }
    byDay[b.date].total++
    if (b.status === 'Done') byDay[b.date].done++
  }
  const cats = Object.keys(byDay).sort().map(d => d.slice(5))
  return {
    chart: { type: 'bar', background: 'transparent', toolbar: { show: false }, stacked: false },
    theme: { mode: 'dark' },
    colors: ['#84cc16', '#334155'],
    plotOptions: { bar: { borderRadius: 3, columnWidth: '60%' } },
    xaxis: { categories: cats, labels: { style: { colors: '#94a3b8', fontSize: '11px' } } },
    yaxis: { labels: { style: { colors: '#94a3b8' } } },
    grid: { borderColor: '#1e293b' },
    legend: { labels: { colors: '#94a3b8' } },
    tooltip: { theme: 'dark' },
    dataLabels: { enabled: false }
  }
})

// ── Helpers ───────────────────────────────────────────────
const plantColorMap: Record<string,string> = { '1': 'blue-4', '2': 'teal-4', '3': 'indigo-4' }
const plantColorHexMap: Record<string,string> = { '1': '#60a5fa', '2': '#2dd4bf', '3': '#818cf8' }
const plantColor = (p: string) => plantColorMap[p] || 'grey-4'
const plantColorHex = (p: string) => plantColorHexMap[p] || '#94a3b8'

onMounted(() => loadData())
</script>

<style scoped>
.oee-page {
  background: #0f172a;
  min-height: 100vh;
  color: #e2e8f0;
  font-family: 'Inter', 'Segoe UI', sans-serif;
  padding-bottom: 48px;   /* ensure trend chart not clipped */
}

.oee-topbar {
  background: #1e293b;
  border-bottom: 1px solid #334155;
  /* NOT sticky — Quasar layout handles scroll; sticky breaks page scroll */
}

.oee-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  height: 100%;
}

.h-100 { height: 100%; }

.plant-border-1 { border-left: 3px solid #60a5fa !important; }
.plant-border-2 { border-left: 3px solid #2dd4bf !important; }
.plant-border-3 { border-left: 3px solid #818cf8 !important; }

.stat-box {
  background: #0f172a;
  border: 1px solid #334155;
  transition: transform 0.2s;
}
.stat-box:hover { transform: translateY(-2px); }
</style>

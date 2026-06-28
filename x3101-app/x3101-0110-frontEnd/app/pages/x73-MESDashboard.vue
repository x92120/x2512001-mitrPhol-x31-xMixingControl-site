<template>
  <q-page class="mes-page" style="padding:0">
    <q-scroll-area class="mes-scroll" style="height:calc(100vh - 106px)">

      <!-- Top Bar -->
      <div class="mes-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:12px;flex-wrap:wrap">
        <q-icon name="precision_manufacturing" size="24px" color="teal-4" />
        <span class="text-subtitle1 text-white text-weight-bold">MES Dashboard</span>
        <q-chip dense color="teal-9" text-color="teal-2" size="sm" icon="factory">Manufacturing Execution</q-chip>
        <q-space />
        <span class="text-caption text-grey-5">PLANT:</span>
        <q-btn-toggle v-model="selectedPlant"
          :options="[{label:'All',value:'all'},{label:'1',value:'1'},{label:'2',value:'2'},{label:'3',value:'3'}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="teal-8" toggle-text-color="white" size="sm"
          @update:model-value="loadData" />
        <span class="text-caption text-grey-5">PERIOD:</span>
        <q-btn-toggle v-model="period"
          :options="[{label:'7d',value:7},{label:'30d',value:30},{label:'90d',value:90}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="cyan-8" toggle-text-color="white" size="sm"
          @update:model-value="loadData" />
        <q-btn flat dense round icon="refresh" color="grey-4" @click="loadData" :loading="loading" />
        <div v-if="lastUpdated" class="text-caption text-grey-6 no-wrap">
          <q-icon name="schedule" size="12px" class="q-mr-xs"/>{{ lastUpdated }}
        </div>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" :to="'/x72-OEEDashboard'">
          <q-tooltip>Switch to OEE Dashboard</q-tooltip>
        </q-btn>
      </div>

      <!-- KPI Bar -->
      <div v-if="!loading && kpis" class="mes-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in kpis" :key="k.label" class="mes-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder text-white">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl" v-if="!loading">

        <!-- Row 1: WIP Status + Schedule Adherence -->
        <div class="row q-col-gutter-md q-mb-md q-mt-md">

          <!-- WIP Funnel -->
          <div class="col-12 col-md-5">
            <div class="mes-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="account_tree" color="teal-4" size="16px" class="q-mr-xs"/>Work In Progress (WIP)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Batch flow by stage</div>
              <apexchart v-if="wipSeries.length" type="bar" height="220"
                :options="wipOptions" :series="wipSeries" />
            </div>
          </div>

          <!-- Schedule Adherence Pie -->
          <div class="col-12 col-md-3">
            <div class="mes-card q-pa-md flex column items-center justify-center">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="event_available" color="lime-4" size="16px" class="q-mr-xs"/>Schedule Adherence
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">On-time vs Delayed batches</div>
              <apexchart v-if="scheduleSeries.length" type="donut" height="200"
                :options="scheduleOptions" :series="scheduleSeries" />
            </div>
          </div>

          <!-- Line Utilization -->
          <div class="col-12 col-md-4">
            <div class="mes-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="speed" color="amber-4" size="16px" class="q-mr-xs"/>Line Utilization
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Active vs idle batches per plant</div>
              <div class="q-mt-sm">
                <div v-for="p in ['1','2','3']" :key="p" class="q-mb-md">
                  <div class="row items-center q-mb-xs" style="gap:8px">
                    <q-chip dense :color="plantColors[p]" text-color="white" size="sm">Plant {{ p }}</q-chip>
                    <span class="text-caption text-grey-4">{{ lineUtil[p]?.active || 0 }} active / {{ lineUtil[p]?.total || 0 }} total</span>
                    <q-space/>
                    <span class="text-caption text-weight-bold" :class="`text-${plantColors[p]}`">{{ lineUtil[p]?.pct || 0 }}%</span>
                  </div>
                  <q-linear-progress :value="(lineUtil[p]?.pct || 0)/100"
                    :color="plantColors[p]" track-color="blue-grey-9"
                    style="height:12px;border-radius:6px" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Cycle Time + Throughput -->
        <div class="row q-col-gutter-md q-mb-md">

          <!-- Cycle Time per SKU -->
          <div class="col-12 col-md-6">
            <div class="mes-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="timer" color="cyan-4" size="16px" class="q-mr-xs"/>Cycle Time per SKU
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Avg hours Created → Done · top 8 SKUs</div>
              <apexchart v-if="cycleSeries.length" type="bar" height="240"
                :options="cycleOptions" :series="cycleSeries" />
              <div v-else class="flex flex-center text-grey-6" style="height:180px">No cycle data</div>
            </div>
          </div>

          <!-- Daily Throughput -->
          <div class="col-12 col-md-6">
            <div class="mes-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="trending_up" color="lime-4" size="16px" class="q-mr-xs"/>Daily Throughput
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Done batches per day · last {{ period }} days</div>
              <apexchart v-if="throughputSeries.length" type="area" height="240"
                :options="throughputOptions" :series="throughputSeries" />
              <div v-else class="flex flex-center text-grey-6" style="height:180px">No data</div>
            </div>
          </div>
        </div>

        <!-- Row 3: Production Order Status Table -->
        <div class="mes-card q-pa-md q-mb-md">
          <div class="row items-center q-mb-md">
            <div>
              <div class="text-subtitle2 text-white text-weight-bold">
                <q-icon name="list_alt" color="purple-4" size="16px" class="q-mr-xs"/>Production Orders — Latest 20
              </div>
              <div class="text-caption text-grey-5">Real-time batch status · filtered by plant & period</div>
            </div>
            <q-space/>
            <q-input v-model="search" dark dense outlined placeholder="Search SKU / Batch..."
              input-class="text-white" style="width:200px" bg-color="blue-grey-9">
              <template #prepend><q-icon name="search" color="grey-5"/></template>
            </q-input>
          </div>
          <q-table :rows="filteredOrders" :columns="orderColumns" row-key="batch_id"
            dark flat dense virtual-scroll :rows-per-page-options="[20]"
            :filter="search" hide-bottom
            table-header-class="text-grey-5 text-caption"
          >
            <template #body-cell-status="props">
              <q-td :props="props">
                <q-chip dense :color="statusColor(props.value)" text-color="white" size="sm">
                  {{ props.value }}
                </q-chip>
              </q-td>
            </template>
            <template #body-cell-cycle_h="props">
              <q-td :props="props" class="text-right">
                <span :class="props.value > 8 ? 'text-negative' : 'text-positive'">
                  {{ props.value ?? '—' }}h
                </span>
              </q-td>
            </template>
          </q-table>
        </div>

      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex flex-center" style="height:60vh">
        <div class="text-center">
          <q-spinner-dots color="teal-4" size="48px"/>
          <div class="text-grey-5 q-mt-md">Loading MES data...</div>
        </div>
      </div>

    </q-scroll-area>
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
const lastUpdated = ref<string>('')
const search = ref('')

const plantColors: Record<string, string> = { '1': 'blue-4', '2': 'teal-4', '3': 'indigo-4' }

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
          const durH = (b.updated_at && b.created_at && b.status === 'Done')
            ? Math.round((new Date(b.updated_at).getTime() - new Date(b.created_at).getTime()) / 360000) / 10
            : null
          flat.push({
            ...b,
            sku_name: p.sku_name || b.sku_id,
            plant: String(b.plant || p.plant || '1'),
            date: batchDate.toISOString().slice(0, 10),
            cycle_h: durH,
            created_fmt: b.created_at ? new Date(b.created_at).toLocaleString('th-TH') : '—'
          })
        }
      })
    })
    allBatches.value = flat
    lastUpdated.value = new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const filteredBatches = computed(() => {
  if (selectedPlant.value === 'all') return allBatches.value
  return allBatches.value.filter(b => b.plant === selectedPlant.value)
})

// KPIs
const kpis = computed(() => {
  const b = filteredBatches.value
  const total = b.length
  const done = b.filter(x => x.status === 'Done').length
  const inProg = b.filter(x => x.status === 'In-Progress').length
  const prepared = b.filter(x => x.status === 'Prepared').length
  const cancelled = b.filter(x => x.status === 'Cancelled').length
  const durations = b.filter(x => x.cycle_h && x.cycle_h > 0 && x.cycle_h < 72).map(x => x.cycle_h!)
  const avgCycle = durations.length ? Math.round(durations.reduce((a, c) => a + c, 0) / durations.length * 10) / 10 : 0
  return [
    { label: 'TOTAL ORDERS',    icon: 'layers',              color: 'cyan-4',   value: total },
    { label: 'IN PROGRESS',     icon: 'sync',                color: 'orange-4', value: inProg },
    { label: 'PREPARED',        icon: 'inventory',           color: 'blue-4',   value: prepared },
    { label: 'COMPLETED',       icon: 'check_circle',        color: 'positive', value: done },
    { label: 'CANCELLED',       icon: 'cancel',              color: 'negative', value: cancelled },
    { label: 'AVG CYCLE TIME',  icon: 'timer',               color: 'lime-4',   value: `${avgCycle}h` },
  ]
})

// WIP Bar
const wipSeries = computed(() => {
  const stages = ['Created','Prepared','In-Progress','Done','Cancelled','Hold']
  const counts = stages.map(s => filteredBatches.value.filter(b => b.status === s).length)
  if (!counts.some(v => v > 0)) return []
  return [{ name: 'Batches', data: counts }]
})
const wipOptions = computed(() => ({
  chart: { type: 'bar', background: 'transparent', toolbar: { show: false } },
  plotOptions: { bar: { horizontal: false, borderRadius: 4, distributed: true, columnWidth: '55%' } },
  colors: ['#64748b','#60a5fa','#f97316','#22c55e','#ef4444','#f59e0b'],
  xaxis: { categories: ['Created','Prepared','In-Progress','Done','Cancelled','Hold'],
    labels: { style: { colors: '#64748b', fontSize: '11px' } } },
  yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '11px' } } },
  grid: { borderColor: '#1e293b', strokeDashArray: 4 },
  dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' } },
  legend: { show: false },
  tooltip: { theme: 'dark' }
}))

// Schedule Adherence Donut
const scheduleSeries = computed(() => {
  const done = filteredBatches.value.filter(b => b.status === 'Done')
  const onTime = done.filter(b => !b.cycle_h || b.cycle_h <= 8).length
  const delayed = done.length - onTime
  if (!done.length) return []
  return [onTime, delayed]
})
const scheduleOptions = computed(() => ({
  chart: { background: 'transparent', toolbar: { show: false } },
  labels: ['On-time (≤8h)', 'Delayed (>8h)'],
  colors: ['#22c55e', '#f97316'],
  legend: { position: 'bottom', labels: { colors: '#94a3b8' } },
  dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' },
    formatter: (v: number) => `${Math.round(v)}%` },
  stroke: { width: 2, colors: ['#0f172a'] },
  tooltip: { theme: 'dark' },
  plotOptions: { pie: { donut: { size: '60%',
    labels: { show: true, total: { show: true, label: 'Done', color: '#94a3b8',
      formatter: () => String(filteredBatches.value.filter(b => b.status === 'Done').length)
    }}
  }}}
}))

// Line Utilization
const lineUtil = computed(() => {
  const result: Record<string, { active: number; total: number; pct: number }> = {}
  ;['1','2','3'].forEach(p => {
    const plant = allBatches.value.filter(b => b.plant === p)
    const active = plant.filter(b => b.status === 'In-Progress').length
    const total = plant.length || 1
    result[p] = { active, total, pct: Math.round(active / total * 100) }
  })
  return result
})

// Cycle Time per SKU
const cycleSeries = computed(() => {
  const skuMap: Record<string, number[]> = {}
  for (const b of filteredBatches.value) {
    if (b.cycle_h && b.cycle_h > 0 && b.cycle_h < 72 && b.sku_name) {
      const k = b.sku_name.slice(0, 20)
      if (!skuMap[k]) skuMap[k] = []
      skuMap[k].push(b.cycle_h)
    }
  }
  const sorted = Object.entries(skuMap)
    .map(([k, v]) => ({ name: k, avg: v.reduce((a, b) => a + b, 0) / v.length }))
    .sort((a, b) => b.avg - a.avg).slice(0, 8)
  if (!sorted.length) return []
  return [{ name: 'Avg Cycle (h)', data: sorted.map(s => Math.round(s.avg * 10) / 10) }]
})
const cycleOptions = computed(() => {
  const skuMap: Record<string, number[]> = {}
  for (const b of filteredBatches.value) {
    if (b.cycle_h && b.cycle_h > 0 && b.cycle_h < 72 && b.sku_name) {
      const k = b.sku_name.slice(0, 20)
      if (!skuMap[k]) skuMap[k] = []
      skuMap[k].push(b.cycle_h)
    }
  }
  const sorted = Object.entries(skuMap)
    .map(([k, v]) => ({ name: k, avg: v.reduce((a, b) => a + b, 0) / v.length }))
    .sort((a, b) => b.avg - a.avg).slice(0, 8)
  return {
    chart: { type: 'bar', background: 'transparent', toolbar: { show: false } },
    plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: true } },
    colors: ['#22d3ee','#84cc16','#818cf8','#f97316','#ec4899','#f59e0b','#10b981','#60a5fa'],
    xaxis: { categories: sorted.map(s => s.name),
      labels: { style: { colors: '#64748b', fontSize: '11px' } },
      title: { text: 'Hours', style: { color: '#64748b' } } },
    yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '11px' } } },
    grid: { borderColor: '#1e293b', strokeDashArray: 4 },
    dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' },
      formatter: (v: number) => `${v}h` },
    legend: { show: false },
    annotations: { xaxis: [{ x: 8, borderColor: '#f59e0b', strokeDashArray: 4,
      label: { text: 'Target 8h', style: { background: '#f59e0b', color: '#000', fontSize: '10px' } }
    }]},
    tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v} hours` } }
  }
})

// Daily Throughput Area
const throughputSeries = computed(() => {
  const byDay: Record<string, number> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.date) byDay[b.date] = (byDay[b.date] || 0) + 1
  }
  const sorted = Object.keys(byDay).sort()
  if (!sorted.length) return []
  return [{ name: 'Done Batches', data: sorted.map(d => byDay[d]) }]
})
const throughputOptions = computed(() => {
  const byDay: Record<string, number> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.date) byDay[b.date] = (byDay[b.date] || 0) + 1
  }
  const cats = Object.keys(byDay).sort().map(d => d.slice(5))
  return {
    chart: { type: 'area', background: 'transparent', toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
      dropShadow: { enabled: true, color: '#14b8a6', top: 6, blur: 10, opacity: 0.25 } },
    stroke: { width: 2.5, curve: 'smooth' },
    fill: { type: 'gradient', gradient: { shade: 'dark', type: 'vertical',
      gradientToColors: ['#22d3ee'], opacityFrom: 0.5, opacityTo: 0.03 } },
    colors: ['#14b8a6'],
    markers: { size: 3, colors: ['#14b8a6'], strokeColors: '#0f172a', strokeWidth: 2 },
    xaxis: { categories: cats, labels: { style: { colors: '#64748b', fontSize: '10px' }, rotate: -30 } },
    yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '11px' } },
      title: { text: 'Batches', style: { color: '#64748b' } } },
    grid: { borderColor: '#1e293b', strokeDashArray: 4 },
    dataLabels: { enabled: false },
    tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v} batches` } }
  }
})

// Production Orders Table
const orderColumns = [
  { name: 'date',      label: 'Date',       field: 'date',       align: 'left'  as const, sortable: true },
  { name: 'batch_id',  label: 'Batch ID',   field: 'batch_id',   align: 'left'  as const, sortable: true },
  { name: 'sku_name',  label: 'SKU',        field: 'sku_name',   align: 'left'  as const, sortable: true },
  { name: 'plant',     label: 'Plant',      field: 'plant',      align: 'center'as const, sortable: true },
  { name: 'status',    label: 'Status',     field: 'status',     align: 'center'as const, sortable: true },
  { name: 'cycle_h',   label: 'Cycle (h)',  field: 'cycle_h',    align: 'right' as const, sortable: true },
  { name: 'created_fmt',label: 'Created',   field: 'created_fmt',align: 'left'  as const },
]

const filteredOrders = computed(() =>
  filteredBatches.value.slice().sort((a, b) =>
    new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
  ).slice(0, 20)
)

function statusColor(s: string) {
  const m: Record<string, string> = {
    Done: 'positive', 'In-Progress': 'orange-6', Prepared: 'blue-5',
    Created: 'grey-6', Cancelled: 'negative', Hold: 'amber-6'
  }
  return m[s] || 'grey-6'
}

onMounted(() => loadData())
</script>

<style scoped>
.mes-page { background: #0a1628; color: #e2e8f0; font-family: 'Inter','Segoe UI',sans-serif; padding-bottom: 80px; }
.mes-scroll { background: #0a1628; width: 100%; }
.mes-topbar { background: #0f2744; border-bottom: 1px solid #1e3a5f; }
.mes-kpi-bar { background: #061122; border-top: 1px solid #1e3a5f; border-bottom: 1px solid #1e3a5f; }
.mes-kpi-chip { border-right: 1px solid #1e293b; transition: background 0.2s; min-width: 0; }
.mes-kpi-chip:last-child { border-right: none; }
.mes-kpi-chip:hover { background: rgba(20,184,166,0.06); border-radius: 6px; }
.mes-card {
  background: #0f2030;
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  height: 100%;
}
</style>

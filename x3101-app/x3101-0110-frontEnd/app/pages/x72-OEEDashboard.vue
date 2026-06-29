<template>
  <q-page class="oee-page" style="padding:0">
    <!-- Quasar body:overflow:hidden → must use q-scroll-area for internal scrolling -->
    <q-scroll-area class="oee-scroll" style="height:calc(100vh - 106px)">

      <!-- ── Top Bar ── -->
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

        <!-- Date Range Picker -->
        <span class="text-caption text-grey-5">FROM:</span>
        <q-input v-model="dateFrom" dark dense outlined type="date" input-class="text-white"
          style="width:130px;font-size:12px" bg-color="blue-grey-9"
          @update:model-value="loadData"
        />
        <span class="text-caption text-grey-5">TO:</span>
        <q-input v-model="dateTo" dark dense outlined type="date" input-class="text-white"
          style="width:130px;font-size:12px" bg-color="blue-grey-9"
          @update:model-value="loadData"
        />

        <q-btn flat dense round icon="refresh" color="grey-4" @click="loadData" :loading="loading" />

        <!-- Auto-refresh toggle -->
        <q-toggle v-model="autoRefresh" color="lime" dense size="xs"
          :label="autoRefresh ? 'Auto' : 'Manual'" left-label
          class="text-caption text-grey-5"
        />

        <!-- Last Updated -->
        <div v-if="lastUpdated" class="text-caption text-grey-6 no-wrap">
          <q-icon name="schedule" size="12px" class="q-mr-xs"/>
          {{ lastUpdated }}
        </div>

        <!-- Export PDF -->
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="picture_as_pdf" label="Export" size="sm"
          @click="exportPDF"
        >
          <q-tooltip>Print / Save as PDF</q-tooltip>
        </q-btn>
      </div>

      <!-- ── KPI Quick Stats Bar ── -->
      <div v-if="!loading && kpiStats" class="kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in kpiStats" :key="k.label" class="kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <div class="row items-baseline" style="gap:6px">
              <span class="text-subtitle1 text-weight-bolder text-white">{{ k.value }}</span>
              <span v-if="k.delta !== undefined"
                :class="k.delta >= 0 ? 'text-positive' : 'text-negative'"
                style="font-size:11px;font-weight:600">
                {{ k.delta >= 0 ? '▲' : '▼' }} {{ Math.abs(k.delta) }}%
              </span>
            </div>
          </div>
        </div>
      </div>


      <!-- ── Alert Panel ── -->
      <transition-group name="alert-slide" tag="div" class="q-px-lg">
        <div v-for="alert in activeAlerts" :key="alert.id"
          class="alert-card row items-center q-mb-xs q-px-md q-py-sm"
          :class="`alert-${alert.type}`"
        >
          <q-icon :name="alert.icon" :color="alert.type === 'critical' ? 'negative' : 'warning'" size="18px" class="q-mr-sm"/>
          <span class="text-weight-medium" style="font-size:13px">{{ alert.msg }}</span>
          <q-space/>
          <q-btn flat dense round icon="close" size="xs" color="grey-5"
            @click="dismissAlert(alert.id)"
          />
        </div>
      </transition-group>

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

      <!-- ── Row 2: 3 Charts Side by Side ── -->
      <div class="row q-col-gutter-md q-mb-md">

        <!-- Chart 1: Batch Status Donut -->
        <div class="col-12 col-md-4">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">Batch Status</div>
            <div class="text-caption text-grey-5 q-mb-sm">Distribution over last {{ period }} days</div>
            <apexchart v-if="donutSeries.length" type="donut" height="240"
              :options="donutOptions" :series="donutSeries" />
          </div>
        </div>

        <!-- Chart 2: Downtime / Status Horizontal Bar -->
        <div class="col-12 col-md-4">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">Production Volume</div>
            <div class="text-caption text-grey-5 q-mb-sm">Batches per status · last {{ period }} days</div>
            <apexchart v-if="hbarSeries.length" type="bar" height="240"
              :options="hbarOptions" :series="hbarSeries" />
          </div>
        </div>

        <!-- Chart 3: OEE % Trend -->
        <div class="col-12 col-md-4">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">OEE Trend</div>
            <div class="text-caption text-grey-5 q-mb-sm">Daily OEE % · last {{ period }} days</div>
            <apexchart v-if="miniTrendSeries.length" type="area" height="240"
              :options="miniTrendOptions" :series="miniTrendSeries" />
          </div>
        </div>
      </div>

      <!-- ── Row 3: Daily Batch Timeline (Stacked Bar) ── -->
      <div class="oee-card q-pa-md q-mb-md">
        <div class="row items-center q-mb-md">
          <div>
            <div class="text-subtitle2 text-white text-weight-bold">Daily Batch Timeline</div>
            <div class="text-caption text-grey-5">Batch status breakdown per day · last {{ period }} days</div>
          </div>
          <q-space/>
          <div class="row items-center" style="gap:12px">
            <div v-for="s in stackedLegend" :key="s.label" class="row items-center" style="gap:5px">
              <div :style="`width:10px;height:10px;background:${s.color};border-radius:2px`"></div>
              <span class="text-caption text-grey-4">{{ s.label }}</span>
            </div>
          </div>
        </div>
        <apexchart v-if="stackedSeries.length" type="bar" height="240"
          :options="stackedOptions" :series="stackedSeries" />
        <div v-else class="flex flex-center text-grey-6" style="height:180px">
          <div class="text-center">
            <q-icon name="bar_chart" size="48px" color="grey-8" class="q-mb-sm"/>
            <div>No data for selected period</div>
          </div>
        </div>
      </div>

      <!-- ── Row 4: Top SKUs + OEE target gauge ── -->
      <div class="row q-col-gutter-md q-mb-md">

        <!-- Top 5 SKUs by Done Batches -->
        <div class="col-12 col-md-7">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">Top SKUs by Production</div>
            <div class="text-caption text-grey-5 q-mb-sm">Done batches per SKU · last {{ period }} days</div>
            <apexchart v-if="skuSeries.length" type="bar" height="220"
              :options="skuOptions" :series="skuSeries" />
            <div v-else class="flex flex-center text-grey-6" style="height:180px">No SKU data</div>
          </div>
        </div>

        <!-- OEE Achievement Radial -->
        <div class="col-12 col-md-5">
          <div class="oee-card q-pa-md flex column items-center justify-center">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">OEE Achievement</div>
            <div class="text-caption text-grey-5 q-mb-sm">vs Target 65% · last {{ period }} days</div>
            <apexchart v-if="radialSeries.length" type="radialBar" height="220"
              :options="radialOptions" :series="radialSeries" />
          </div>
        </div>
      </div>

      <!-- ── Row 5: Avg Duration per SKU + Operator Leaderboard ── -->
      <div class="row q-col-gutter-md q-mb-md q-px-lg">

        <!-- Avg Batch Duration per SKU -->
        <div class="col-12 col-md-7">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
              <q-icon name="timer" color="cyan-4" size="16px" class="q-mr-xs"/>Avg Batch Duration per SKU
            </div>
            <div class="text-caption text-grey-5 q-mb-sm">Average hours from Created → Done · top 8 SKUs</div>
            <apexchart v-if="durationSeries.length" type="bar" height="220"
              :options="durationOptions" :series="durationSeries" />
            <div v-else class="flex flex-center text-grey-6" style="height:160px">No duration data</div>
          </div>
        </div>

        <!-- Operator Leaderboard -->
        <div class="col-12 col-md-5">
          <div class="oee-card q-pa-md">
            <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
              <q-icon name="emoji_events" color="amber-4" size="16px" class="q-mr-xs"/>Operator Leaderboard
            </div>
            <div class="text-caption text-grey-5 q-mb-sm">Done batches per operator · last {{ period }} days</div>
            <div v-if="operatorRank.length">
              <div v-for="(op, idx) in operatorRank" :key="op.name"
                class="leader-row row items-center q-mb-sm" style="gap:10px">
                <div class="leader-rank" :class="idx===0?'rank-gold':idx===1?'rank-silver':idx===2?'rank-bronze':'rank-other'">
                  {{ idx+1 }}
                </div>
                <div class="col text-white" style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ op.name }}</div>
                <q-linear-progress :value="op.pct/100" color="lime-6" track-color="blue-grey-9"
                  style="width:80px;height:8px;border-radius:4px" class="q-mr-xs"/>
                <span class="text-caption text-lime-4" style="width:24px;text-align:right">{{ op.count }}</span>
              </div>
            </div>
            <div v-else class="flex flex-center text-grey-6" style="height:100px">No operator data</div>
          </div>
        </div>
      </div>

      <!-- ── Row 6: Activity Heatmap ── -->
      <div class="oee-card q-pa-md q-mb-md q-mx-lg">
        <div class="row items-center q-mb-md">
          <div>
            <div class="text-subtitle2 text-white text-weight-bold">
              <q-icon name="calendar_month" color="purple-4" size="16px" class="q-mr-xs"/>Activity Heatmap
            </div>
            <div class="text-caption text-grey-5">Daily batch count — last 90 days</div>
          </div>
          <q-space/>
          <div class="row items-center" style="gap:4px">
            <span class="text-caption text-grey-6">Less</span>
            <div v-for="c in heatColors" :key="c" :style="`width:12px;height:12px;background:${c};border-radius:2px`"></div>
            <span class="text-caption text-grey-6">More</span>
          </div>
        </div>
        <div class="heatmap-wrap" style="overflow-x:auto">
          <svg :width="heatmapW" height="110" class="heatmap-svg">
            <text v-for="(d,i) in ['Mon','','Wed','','Fri','','Sun']" :key="i"
              :x="0" :y="i*14+22" fill="#64748b" font-size="9" text-anchor="end">{{ d }}</text>
            <g v-for="(col,ci) in heatmapCells" :key="ci" :transform="`translate(${ci*14+12},0)`">
              <text v-if="col[0]?.monthLabel" x="0" y="8" fill="#64748b" font-size="9">{{ col[0].monthLabel }}</text>
              <rect v-for="(cell,ri) in col" :key="ri"
                :x="0" :y="ri*14+12"
                width="11" height="11" rx="2"
                :fill="cell.color"
                class="heatmap-cell"
              >
                <title>{{ cell.date }}: {{ cell.count }} batches</title>
              </rect>
            </g>
          </svg>
        </div>
      </div>

    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="flex flex-center" style="height:60vh">
      <div class="text-center">
        <q-spinner-dots color="lime-4" size="48px"/>
        <div class="text-grey-5 q-mt-md">Calculating OEE...</div>
      </div>
    </div>

    </q-scroll-area>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { appConfig } from '~/appConfig/config'

const { getAuthHeader } = useAuth()
const apiBase = appConfig.apiBaseUrl

const loading = ref(false)
const selectedPlant = ref<string>('all')
const period = ref<number>(30)
const allBatches = ref<any[]>([])
const lastUpdated = ref<string>('')
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// Date range — default to last 30 days
const dateFrom = ref<string>('')
const dateTo   = ref<string>('')
const dismissedAlerts = ref<Set<string>>(new Set())

// Init default date range
;(() => {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 30)
  dateFrom.value = from.toISOString().slice(0, 10)
  dateTo.value   = to.toISOString().slice(0, 10)
})()

function exportPDF() {
  const styleId = 'oee-print-global'
  if (!document.getElementById(styleId)) {
    const s = document.createElement('style')
    s.id = styleId
    s.textContent = `
      @media print {
        .q-header, .q-drawer, .q-tabs, .q-scrollarea__thumb,
        .oee-topbar, .kpi-bar { display: none !important; }
        .q-scrollarea, .q-scrollarea__container, .q-scrollarea__content {
          height: auto !important; max-height: none !important;
          overflow: visible !important; position: static !important; contain: none !important;
        }
        .oee-page { background: #fff !important; color: #111 !important; }
        .oee-card { background: #f8fafc !important; border: 1px solid #cbd5e1 !important; break-inside: avoid; }
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      }
    `
    document.head.appendChild(s)
  }
  setTimeout(() => {
    window.print()
    setTimeout(() => { document.getElementById(styleId)?.remove() }, 500)
  }, 200)
}

function dismissAlert(id: string) {
  dismissedAlerts.value.add(id)
}

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
        const fromD = dateFrom.value ? new Date(dateFrom.value) : cutoff
        const toD   = dateTo.value   ? new Date(dateTo.value + 'T23:59:59') : new Date()
        if (batchDate >= fromD && batchDate <= toD) {
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
    // Update last-refreshed time
    const now = new Date()
    lastUpdated.value = now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
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

// ── Donut Chart (Batch Status) ────────────────────────────
const donutSeries = computed(() =>
  statusBreakdown.value.map(s => s.count)
)
const donutOptions = computed(() => ({
  chart: { background: 'transparent', toolbar: { show: false },
    animations: { enabled: true, speed: 500 } },
  labels: statusBreakdown.value.map(s => s.label),
  colors: ['#22c55e','#f97316','#60a5fa','#94a3b8','#ef4444','#f59e0b'],
  legend: { position: 'bottom', labels: { colors: '#94a3b8' } },
  dataLabels: {
    enabled: true,
    style: { colors: ['#fff'], fontSize: '11px' },
    formatter: (v: number) => `${Math.round(v)}%`
  },
  stroke: { width: 2, colors: ['#0f172a'] },
  tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v} batches` } },
  plotOptions: { pie: { donut: {
    size: '65%',
    labels: {
      show: true,
      total: { show: true, label: 'Total', color: '#94a3b8',
        formatter: () => String(filteredBatches.value.length)
      }
    }
  }}}
}))

// ── Horizontal Bar Chart (Production Volume) ──────────────
const hbarSeries = computed(() => [{
  name: 'Batches',
  data: statusBreakdown.value.map(s => s.count)
}])
const hbarOptions = computed(() => ({
  chart: { type: 'bar', background: 'transparent', toolbar: { show: false },
    animations: { enabled: true, speed: 500 } },
  plotOptions: { bar: {
    horizontal: true, borderRadius: 5,
    dataLabels: { position: 'center' }
  }},
  colors: ['#84cc16'],
  fill: { type: 'gradient', gradient: {
    shade: 'dark', type: 'horizontal',
    gradientToColors: ['#22d3ee'], opacityFrom: 1, opacityTo: 0.7
  }},
  xaxis: { categories: statusBreakdown.value.map(s => s.label),
    labels: { style: { colors: '#64748b', fontSize: '11px' } } },
  yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '11px' } } },
  grid: { borderColor: '#1e293b', strokeDashArray: 4 },
  dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' } },
  tooltip: { theme: 'dark' },
  legend: { show: false }
}))

// ── Mini Trend (OEE % only, area) ────────────────────────
const miniTrendSeries = computed(() => {
  const byDay = trendDays.value
  const sorted = Object.keys(byDay).sort()
  if (!sorted.length) return []
  return [{
    name: 'OEE %',
    data: sorted.map(d => {
      const r = byDay[d]
      if (!r.total) return 0
      const a = Math.round((r.done + (r.total - r.cancelled - r.done)) / r.total * 100)
      const p = Math.round(r.done / Math.max(r.total - r.cancelled, 1) * 100)
      const q = r.cancelled === 0 ? 100 : Math.round(r.done / (r.done + r.cancelled) * 100)
      return Math.round(a * p * q / 10000)
    })
  }]
})
const miniTrendOptions = computed(() => {
  const cats = Object.keys(trendDays.value).sort().map(d => d.slice(5))
  return {
    chart: { type: 'area', background: 'transparent', toolbar: { show: false },
      sparkline: { enabled: false },
      animations: { enabled: true, speed: 600 },
      dropShadow: { enabled: true, color: '#84cc16', top: 6, blur: 10, opacity: 0.25 }
    },
    stroke: { width: 2.5, curve: 'smooth' },
    fill: { type: 'gradient', gradient: {
      shade: 'dark', type: 'vertical', shadeIntensity: 0.4,
      gradientToColors: ['#22d3ee'], opacityFrom: 0.5, opacityTo: 0.03, stops: [0,90,100]
    }},
    colors: ['#84cc16'],
    markers: { size: 3, colors: ['#84cc16'], strokeColors: '#0f172a', strokeWidth: 2, hover: { size: 6 } },
    xaxis: { categories: cats, labels: { style: { colors: '#64748b', fontSize: '10px' }, rotate: -30 },
      axisBorder: { color: '#1e293b' } },
    yaxis: { min: 0, max: 100, labels: { style: { colors: '#94a3b8', fontSize: '10px' },
      formatter: (v: number) => `${v}%` } },
    grid: { borderColor: '#1e293b', strokeDashArray: 4 },
    annotations: { yaxis: [{ y: 65, borderColor: '#f59e0b', strokeDashArray: 4,
      label: { text: '65%', style: { background: '#f59e0b', color: '#000', fontSize: '10px' } }
    }]},
    tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v}%` } },
    dataLabels: { enabled: false }
  }
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
const trendDays = computed(() => {
  const byDay: Record<string, { done: number; total: number; cancelled: number }> = {}
  for (const b of filteredBatches.value) {
    if (!byDay[b.date]) byDay[b.date] = { done: 0, total: 0, cancelled: 0 }
    byDay[b.date].total++
    if (b.status === 'Done') byDay[b.date].done++
    if (b.status === 'Cancelled') byDay[b.date].cancelled++
  }
  return byDay
})

const trendSeries = computed(() => {
  const byDay = trendDays.value
  const sorted = Object.keys(byDay).sort()
  if (!sorted.length) return []
  return [
    {
      name: 'OEE %',
      type: 'area',
      data: sorted.map(d => {
        const r = byDay[d]
        if (!r.total) return 0
        const done = r.done, total = r.total, cancelled = r.cancelled
        const a = Math.round((done + (total - cancelled - done)) / total * 100)
        const p = Math.round(done / Math.max(total - cancelled, 1) * 100)
        const q = cancelled === 0 ? 100 : Math.round(done / (done + cancelled) * 100)
        return Math.round(a * p * q / 10000)
      })
    },
    {
      name: 'Done Batches',
      type: 'bar',
      data: sorted.map(d => byDay[d].done)
    },
    {
      name: 'Total Batches',
      type: 'bar',
      data: sorted.map(d => byDay[d].total)
    }
  ]
})

const trendOptions = computed(() => {
  const byDay = trendDays.value
  const cats = Object.keys(byDay).sort().map(d => d.slice(5))
  return {
    chart: {
      type: 'line',
      background: 'transparent',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600, animateGradually: { enabled: true, delay: 80 } },
      dropShadow: { enabled: true, color: '#84cc16', top: 4, blur: 8, opacity: 0.2 }
    },
    stroke: { width: [3, 0, 0], curve: 'smooth' },
    fill: {
      type: ['gradient', 'solid', 'solid'],
      gradient: {
        shade: 'dark',
        type: 'vertical',
        shadeIntensity: 0.5,
        gradientToColors: ['#22d3ee'],
        inverseColors: false,
        opacityFrom: 0.6,
        opacityTo: 0.05,
        stops: [0, 90, 100]
      }
    },
    colors: ['#84cc16', '#1d4ed8', '#334155'],
    plotOptions: {
      bar: { borderRadius: 4, columnWidth: '55%', dataLabels: { position: 'top' } }
    },
    markers: {
      size: [4, 0, 0],
      colors: ['#84cc16'],
      strokeColors: '#0f172a',
      strokeWidth: 2,
      hover: { size: 7 }
    },
    xaxis: {
      categories: cats,
      labels: { style: { colors: '#64748b', fontSize: '11px', fontFamily: 'Inter' }, rotate: -30 },
      axisBorder: { color: '#1e293b' },
      axisTicks: { color: '#1e293b' }
    },
    yaxis: [
      {
        seriesName: 'OEE %',
        min: 0, max: 100,
        labels: {
          style: { colors: '#84cc16', fontSize: '11px' },
          formatter: (v: number) => `${v}%`
        },
        title: { text: 'OEE %', style: { color: '#84cc16', fontSize: '11px' } }
      },
      {
        seriesName: 'Done Batches',
        opposite: true,
        labels: { style: { colors: '#60a5fa', fontSize: '11px' } },
        title: { text: 'Batches', style: { color: '#60a5fa', fontSize: '11px' } }
      },
      { seriesName: 'Total Batches', show: false, opposite: true }
    ],
    grid: {
      borderColor: '#1e293b',
      strokeDashArray: 4,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { left: 8, right: 8 }
    },
    annotations: {
      yaxis: [{
        y: 65,
        borderColor: '#f59e0b',
        borderWidth: 1,
        strokeDashArray: 4,
        label: {
          text: 'Target 65%',
          style: { background: '#f59e0b', color: '#000', fontSize: '10px', padding: { top: 2, bottom: 2, left: 6, right: 6 } }
        }
      }]
    },
    legend: {
      labels: { colors: '#94a3b8' },
      markers: { radius: 3 },
      position: 'bottom',
      horizontalAlign: 'center'
    },
    tooltip: {
      theme: 'dark',
      shared: true,
      intersect: false,
      y: [
        { formatter: (v: number) => `${v}%` },
        { formatter: (v: number) => `${v} batches` },
        { formatter: (v: number) => `${v} batches` }
      ]
    },
    dataLabels: { enabled: false }
  }
})

// ── Helpers ───────────────────────────────────────────────
const plantColorMap: Record<string,string> = { '1': 'blue-4', '2': 'teal-4', '3': 'indigo-4' }
const plantColorHexMap: Record<string,string> = { '1': '#60a5fa', '2': '#2dd4bf', '3': '#818cf8' }
const plantColor = (p: string) => plantColorMap[p] || 'grey-4'
const plantColorHex = (p: string) => plantColorHexMap[p] || '#94a3b8'

// ── Daily Stacked Bar Timeline ────────────────────────────
const STACK_STATUSES = [
  { key: 'Done',        color: '#22c55e', label: 'Done' },
  { key: 'In-Progress', color: '#f97316', label: 'In-Progress' },
  { key: 'Prepared',    color: '#60a5fa', label: 'Prepared' },
  { key: 'Created',     color: '#64748b', label: 'Created' },
  { key: 'Cancelled',   color: '#ef4444', label: 'Cancelled' },
  { key: 'Hold',        color: '#f59e0b', label: 'Hold' },
]
const stackedLegend = STACK_STATUSES

const stackedDays = computed(() => {
  const byDay: Record<string, Record<string, number>> = {}
  for (const b of filteredBatches.value) {
    if (!byDay[b.date]) byDay[b.date] = {}
    byDay[b.date][b.status] = (byDay[b.date][b.status] || 0) + 1
  }
  return byDay
})

const stackedSeries = computed(() => {
  const days = Object.keys(stackedDays.value).sort()
  if (!days.length) return []
  return STACK_STATUSES
    .map(s => ({
      name: s.label,
      data: days.map(d => stackedDays.value[d][s.key] || 0)
    }))
    .filter(s => s.data.some(v => v > 0))   // hide zero series
})

const stackedOptions = computed(() => {
  const days = Object.keys(stackedDays.value).sort()
  const cats = days.map(d => d.slice(5))     // show MM-DD
  const activeColors = STACK_STATUSES
    .filter(s => stackedSeries.value.some(ss => ss.name === s.label))
    .map(s => s.color)
  return {
    chart: {
      type: 'bar',
      background: 'transparent',
      toolbar: { show: false },
      stacked: true,
      animations: { enabled: true, speed: 500 }
    },
    plotOptions: { bar: { horizontal: false, borderRadius: 3, columnWidth: '70%' } },
    colors: activeColors,
    xaxis: {
      categories: cats,
      labels: { style: { colors: '#64748b', fontSize: '10px' }, rotate: -30 },
      axisBorder: { color: '#1e293b' },
      axisTicks: { color: '#1e293b' }
    },
    yaxis: {
      labels: { style: { colors: '#94a3b8', fontSize: '11px' } },
      title: { text: 'Batches', style: { color: '#64748b', fontSize: '11px' } }
    },
    grid: { borderColor: '#1e293b', strokeDashArray: 4 },
    legend: { show: false },   // custom legend above chart
    dataLabels: { enabled: false },
    tooltip: {
      theme: 'dark',
      shared: true,
      intersect: false,
      y: { formatter: (v: number) => `${v} batches` }
    },
    fill: { opacity: 0.92 }
  }
})

// ── KPI Quick Stats ──────────────────────────────────────
const kpiStats = computed(() => {
  const days = Object.keys(trendDays.value).sort()
  const oeeByDay = days.map(d => {
    const r = trendDays.value[d]
    if (!r.total) return 0
    const a = Math.round((r.done + (r.total - r.cancelled - r.done)) / r.total * 100)
    const p = Math.round(r.done / Math.max(r.total - r.cancelled, 1) * 100)
    const q = r.cancelled === 0 ? 100 : Math.round(r.done / (r.done + r.cancelled) * 100)
    return Math.round(a * p * q / 10000)
  }).filter(v => v > 0)

  const avg = oeeByDay.length ? Math.round(oeeByDay.reduce((a,b) => a+b,0) / oeeByDay.length) : 0
  const best = oeeByDay.length ? Math.max(...oeeByDay) : 0
  const worst = oeeByDay.length ? Math.min(...oeeByDay) : 0
  const done = filteredBatches.value.filter(b => b.status === 'Done').length
  const cancelled = filteredBatches.value.filter(b => b.status === 'Cancelled').length
  const total = filteredBatches.value.length
  const successRate = total ? Math.round(done / total * 100) : 0

  return [
    { label: 'BEST DAY OEE',    icon: 'emoji_events',   color: 'lime-4',   value: `${best}%`,         delta: undefined },
    { label: 'AVG OEE',         icon: 'analytics',      color: 'cyan-4',   value: `${avg}%`,          delta: undefined },
    { label: 'WORST DAY OEE',   icon: 'warning_amber',  color: 'amber-4',  value: `${worst}%`,        delta: undefined },
    { label: 'DONE BATCHES',    icon: 'check_circle',   color: 'positive', value: done,               delta: undefined },
    { label: 'CANCELLED',       icon: 'cancel',         color: 'negative', value: cancelled,          delta: undefined },
    { label: 'SUCCESS RATE',    icon: 'percent',        color: 'purple-4', value: `${successRate}%`,  delta: undefined },
  ]
})

// ── Top SKUs Chart ───────────────────────────────────────
const skuSeries = computed(() => {
  const skuMap: Record<string, number> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.sku_name) {
      skuMap[b.sku_name] = (skuMap[b.sku_name] || 0) + 1
    }
  }
  const sorted = Object.entries(skuMap).sort(([,a],[,b]) => b - a).slice(0, 8)
  if (!sorted.length) return []
  return [{ name: 'Done Batches', data: sorted.map(([,v]) => v) }]
})
const skuOptions = computed(() => {
  const skuMap: Record<string, number> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.sku_name) skuMap[b.sku_name] = (skuMap[b.sku_name] || 0) + 1
  }
  const sorted = Object.entries(skuMap).sort(([,a],[,b]) => b - a).slice(0, 8)
  return {
    chart: { type: 'bar', background: 'transparent', toolbar: { show: false },
      animations: { enabled: true, speed: 600 } },
    plotOptions: { bar: { horizontal: true, borderRadius: 5, distributed: true } },
    colors: ['#84cc16','#22d3ee','#818cf8','#f97316','#ec4899','#f59e0b','#10b981','#60a5fa'],
    xaxis: { categories: sorted.map(([k]) => k.length > 22 ? k.slice(0,22)+'…' : k),
      labels: { style: { colors: '#64748b', fontSize: '11px' } } },
    yaxis: { labels: { style: { colors: '#94a3b8', fontSize: '11px' } } },
    grid: { borderColor: '#1e293b', strokeDashArray: 4 },
    dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' } },
    legend: { show: false },
    tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v} batches` } }
  }
})

// ── Radial OEE Achievement ────────────────────────────────
const radialSeries = computed(() => [stats.value?.oee ?? 0])
const radialOptions = computed(() => ({
  chart: { type: 'radialBar', background: 'transparent',
    animations: { enabled: true, speed: 800 } },
  plotOptions: { radialBar: {
    startAngle: -135, endAngle: 135,
    hollow: { size: '60%', background: '#0f172a' },
    track: { background: '#1e293b', strokeWidth: '80%' },
    dataLabels: {
      name: { show: true, color: '#94a3b8', fontSize: '13px', offsetY: -10 },
      value: { show: true, color: '#fff', fontSize: '28px', fontWeight: 700,
        formatter: (v: number) => `${v}%` }
    }
  }},
  fill: { type: 'gradient', gradient: {
    shade: 'dark', type: 'horizontal',
    gradientToColors: ['#22d3ee'], stops: [0, 100]
  }},
  colors: ['#84cc16'],
  labels: ['OEE'],
  annotations: {},
  tooltip: { enabled: false }
}))

// ── Avg Batch Duration per SKU ───────────────────────────
const durationSeries = computed(() => {
  const skuDur: Record<string, number[]> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.created_at && b.updated_at) {
      const dur = (new Date(b.updated_at).getTime() - new Date(b.created_at).getTime()) / 3600000
      if (dur > 0 && dur < 72) {  // filter outliers < 72h
        const key = (b.sku_name || b.sku_id || 'Unknown').slice(0, 20)
        if (!skuDur[key]) skuDur[key] = []
        skuDur[key].push(dur)
      }
    }
  }
  const sorted = Object.entries(skuDur)
    .map(([k, v]) => ({ name: k, avg: v.reduce((a,b)=>a+b,0)/v.length }))
    .sort((a,b) => b.avg - a.avg)
    .slice(0, 8)
  if (!sorted.length) return []
  return [{ name: 'Avg Hours', data: sorted.map(s => Math.round(s.avg * 10)/10) }]
})
const durationOptions = computed(() => {
  const skuDur: Record<string, number[]> = {}
  for (const b of filteredBatches.value) {
    if (b.status === 'Done' && b.created_at && b.updated_at) {
      const dur = (new Date(b.updated_at).getTime() - new Date(b.created_at).getTime()) / 3600000
      if (dur > 0 && dur < 72) {
        const key = (b.sku_name || b.sku_id || 'Unknown').slice(0, 20)
        if (!skuDur[key]) skuDur[key] = []
        skuDur[key].push(dur)
      }
    }
  }
  const sorted = Object.entries(skuDur)
    .map(([k,v]) => ({ name: k, avg: v.reduce((a,b)=>a+b,0)/v.length }))
    .sort((a,b) => b.avg - a.avg).slice(0, 8)
  return {
    chart: { type: 'bar', background: 'transparent', toolbar: { show: false },
      animations: { enabled: true, speed: 600 } },
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
    tooltip: { theme: 'dark', y: { formatter: (v: number) => `${v} hours` } }
  }
})

// ── Operator Leaderboard ──────────────────────────────────
const operatorRank = computed(() => {
  const opMap: Record<string, number> = {}
  for (const b of filteredBatches.value) {
    if (b.status !== 'Done') continue
    const ops = [
      b.pour_operator_name, b.cook_operator_name,
      b.operator, b.operator_name
    ].filter(Boolean)
    const name = ops[0] || null
    if (name) opMap[name] = (opMap[name] || 0) + 1
  }
  const sorted = Object.entries(opMap).sort(([,a],[,b]) => b-a).slice(0, 8)
  const max = sorted[0]?.[1] || 1
  return sorted.map(([name, count]) => ({ name, count, pct: Math.round(count/max*100) }))
})

// ── Activity Heatmap (90 days, GitHub-style) ──────────────
const heatColors = ['#1e293b','#14532d','#166534','#16a34a','#22c55e','#86efac']

const heatmapCells = computed(() => {
  // Build count map for all batches (not just filtered by date)
  const countMap: Record<string, number> = {}
  for (const b of allBatches.value) {
    if (b.date) countMap[b.date] = (countMap[b.date] || 0) + 1
  }
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const today = new Date()
  // Go back 90 days, start from Monday of that week
  const start = new Date(today)
  start.setDate(start.getDate() - 89)
  const dow = start.getDay()  // 0=Sun..6=Sat
  const monday = new Date(start)
  monday.setDate(start.getDate() - ((dow + 6) % 7))  // roll back to Monday

  const cols: { date: string; count: number; color: string; monthLabel?: string }[][] = []
  const cursor = new Date(monday)
  const maxCount = Math.max(...Object.values(countMap), 1)

  while (cursor <= today) {
    const col: { date: string; count: number; color: string; monthLabel?: string }[] = []
    for (let d = 0; d < 7; d++) {
      const iso = cursor.toISOString().slice(0, 10)
      const count = countMap[iso] || 0
      const level = count === 0 ? 0 : Math.ceil(count / maxCount * 5)
      col.push({
        date: iso,
        count,
        color: heatColors[Math.min(level, 5)],
        monthLabel: (d === 0 && cursor.getDate() <= 7) ? MONTHS[cursor.getMonth()] : undefined
      })
      cursor.setDate(cursor.getDate() + 1)
    }
    cols.push(col)
  }
  return cols
})
const heatmapW = computed(() => heatmapCells.value.length * 14 + 20)

// ── Alert Panel ───────────────────────────────────────────
const activeAlerts = computed(() => {
  const alerts: { id: string; type: 'critical' | 'warning'; icon: string; msg: string }[] = []
  const byDay = trendDays.value
  const sorted = Object.keys(byDay).sort()

  // Check last 3 days below target (65%)
  if (sorted.length >= 3) {
    const recent = sorted.slice(-3)
    const allBelow = recent.every(d => {
      const r = byDay[d]
      if (!r.total) return false
      const a = (r.done + r.total - r.cancelled - r.done) / r.total * 100
      const p = r.done / Math.max(r.total - r.cancelled, 1) * 100
      const q = r.cancelled === 0 ? 100 : r.done / (r.done + r.cancelled) * 100
      return (a * p * q / 10000) < 65
    })
    if (allBelow) {
      const id = 'oee-below-target-3d'
      if (!dismissedAlerts.value.has(id))
        alerts.push({ id, type: 'critical', icon: 'warning', msg: '🚨 OEE ต่ำกว่าเป้า 65% ติดต่อกัน 3 วัน — ควรตรวจสอบด่วน!' })
    }
  }

  // Per plant: any plant OEE = 0?
  ;['1','2','3'].forEach(p => {
    const ps = plantStats.value[p]
    if (!ps) return
    if (ps.oee === 0 && ps.totalBatches > 10) {
      const id = `plant-${p}-zero-oee`
      if (!dismissedAlerts.value.has(id))
        alerts.push({ id, type: 'warning', icon: 'info', msg: `⚠️ Plant ${p}: OEE = 0% — ไม่มี batch สำเร็จในช่วงนี้` })
    }
  })

  // High cancellation rate
  const total = filteredBatches.value.length
  const cancelled = filteredBatches.value.filter(b => b.status === 'Cancelled').length
  if (total > 0 && cancelled / total > 0.15) {
    const id = 'high-cancel-rate'
    if (!dismissedAlerts.value.has(id))
      alerts.push({ id, type: 'warning', icon: 'cancel', msg: `⚠️ อัตรายกเลิก batch สูงผิดปกติ ${Math.round(cancelled/total*100)}% (${cancelled}/${total})` })
  }

  return alerts
})

// ── Auto-refresh ─────────────────────────────────────────
watch(autoRefresh, (val) => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (val) refreshTimer = setInterval(loadData, 60000)
})

onMounted(() => loadData())
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
.oee-page {
  background: #0f172a;
  color: #e2e8f0;
  font-family: 'Inter', 'Segoe UI', sans-serif;
  padding-bottom: 80px;
}

.oee-topbar {
  background: #1e293b;
  border-bottom: 1px solid #334155;
}

.oee-scroll {
  background: #0f172a;
  width: 100%;
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

.kpi-bar {
  background: #0d1b2e;
  border-top: 1px solid #1e3a5f;
  border-bottom: 1px solid #1e3a5f;
}

.kpi-chip {
  border-right: 1px solid #1e293b;
  transition: background 0.2s;
  min-width: 0;
}
.kpi-chip:last-child { border-right: none; }
.kpi-chip:hover { background: rgba(132,204,22,0.06); border-radius: 6px; }

/* ── Alert Panel ── */
.alert-card {
  border-radius: 8px;
  margin-bottom: 4px;
  font-size: 13px;
  border-left: 4px solid;
}
.alert-critical {
  background: rgba(239,68,68,0.12);
  border-color: #ef4444;
  color: #fca5a5;
}
.alert-warning {
  background: rgba(245,158,11,0.12);
  border-color: #f59e0b;
  color: #fcd34d;
}
.alert-slide-enter-active, .alert-slide-leave-active {
  transition: all 0.3s ease;
}
.alert-slide-enter-from, .alert-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── Operator Leaderboard ── */
.leader-row { padding: 4px 0; border-bottom: 1px solid #1e293b; }
.leader-row:last-child { border-bottom: none; }
.leader-rank {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
}
.rank-gold   { background: linear-gradient(135deg,#f59e0b,#fbbf24); color: #000; }
.rank-silver { background: linear-gradient(135deg,#9ca3af,#d1d5db); color: #000; }
.rank-bronze { background: linear-gradient(135deg,#b45309,#d97706); color: #fff; }
.rank-other  { background: #1e293b; color: #64748b; border: 1px solid #334155; }

/* ── Heatmap ── */
.heatmap-svg { display: block; }
.heatmap-cell { cursor: pointer; transition: opacity 0.15s; }
.heatmap-cell:hover { opacity: 0.75; }

/* ── Print / Export ── */
@media print {
  .oee-topbar, .kpi-bar, .q-header, .q-toolbar,
  .q-tabs, .q-drawer, .q-scrollarea__thumb { display: none !important; }
  /* Unclip Quasar scroll-area for printing */
  .oee-scroll,
  .oee-scroll .q-scrollarea,
  .oee-scroll .q-scrollarea__container,
  .oee-scroll .q-scrollarea__content {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    position: static !important;
    contain: none !important;
  }
  .oee-page { background: #fff !important; color: #111 !important; padding: 0 !important; }
  .oee-card { background: #f8fafc !important; border: 1px solid #cbd5e1 !important; break-inside: avoid; color: #111 !important; }
  .text-white, .text-grey-5, .text-grey-6 { color: #333 !important; }
  .q-px-lg { padding: 8px !important; }
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>

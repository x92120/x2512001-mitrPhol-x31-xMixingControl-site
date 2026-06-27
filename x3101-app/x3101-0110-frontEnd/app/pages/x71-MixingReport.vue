<template>
  <q-page class="bg-grey-2" style="min-height:100vh">
    <!-- ── Top Bar ───────────────────────────────────────────── -->
    <div class="row items-center q-px-md q-py-sm bg-indigo-9 text-white no-wrap" style="gap:8px">
      <q-btn flat dense round icon="arrow_back" color="white" @click="$router.back()" />
      <span class="text-subtitle1 text-weight-bold">Mixing Report</span>
      <q-chip v-if="selectedBatch" dense color="orange-7" text-color="white" size="sm">
        {{ selectedBatch.batch_id }}
      </q-chip>
      <q-space />
      <q-btn v-if="selectedBatch" flat dense icon="open_in_new" color="white" label="OPEN IN X70"
        @click="$router.push(`/x70-ProductionReport?batch_id=${selectedBatch.batch_id}`)" size="sm" />
      <q-btn flat dense icon="picture_as_pdf" color="amber-4" label="EXPORT PDF"
        @click="exportPDF" size="sm" :disable="!selectedBatch || !reportData"
        class="text-weight-bold" />
    </div>

    <!-- ── Batch Selector (Done only) ──────────────────────────── -->
    <div class="row q-px-md q-pt-sm q-pb-xs items-center" style="gap:8px">
      <q-select
        v-model="selectedBatch"
        :options="batches"
        option-label="batch_id"
        label="Select Completed Batch"
        dense outlined
        style="min-width:300px"
        :loading="loading"
        @update:model-value="onBatchSelect"
      >
        <template #option="{ itemProps, opt }">
          <q-item v-bind="itemProps">
            <q-item-section>
              <q-item-label class="text-weight-bold text-indigo-8">{{ opt.batch_id }}</q-item-label>
              <q-item-label caption>{{ opt.sku_name }} · {{ opt.plant }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-chip dense color="green-7" text-color="white" size="xs">Done</q-chip>
            </q-item-section>
          </q-item>
        </template>
      </q-select>
      <q-chip v-if="selectedBatch" dense color="green-7" text-color="white">
        Done
      </q-chip>
      <span v-if="batches.length" class="text-caption text-grey-6">{{ batches.length }} completed batches</span>
    </div>

    <!-- ── Report Preview ─────────────────────────────────────── -->
    <div class="q-px-md q-pb-xl" v-if="selectedBatch && reportData">
      <div id="mixing-report-content" class="report-page q-mx-auto" style="max-width:900px;background:#fff;padding:16px 20px;box-shadow:0 2px 12px rgba(0,0,0,0.12)">

        <!-- Header -->
        <table style="width:100%;border-collapse:collapse;margin-bottom:8px">
          <tr>
            <td style="width:120px;border:2px solid #333;padding:6px;vertical-align:middle;text-align:center">
              <img v-if="logoUrl" :src="logoUrl" style="max-width:90px;max-height:60px" />
              <div v-else style="font-size:18pt;font-weight:900;color:#1a237e;letter-spacing:1px">M</div>
              <div style="font-size:7pt;color:#666">MITR PHOL</div>
            </td>
            <td style="border:2px solid #333;padding:6px;text-align:center;vertical-align:middle">
              <div style="font-size:14pt;font-weight:800;color:#1a237e;letter-spacing:2px">MITR PHOL</div>
              <div style="font-size:12pt;font-weight:700;margin-top:2px">MIXING REPORT</div>
              <div style="font-size:8pt;color:#666;margin-top:4px">Document name : Record Log of Mixing</div>
            </td>
            <td style="width:260px;border:2px solid #333;padding:4px 8px;font-size:8pt;vertical-align:top">
              <table style="width:100%;border-collapse:collapse">
                <tr><td style="color:#555;white-space:nowrap">Date NO. :</td><td style="font-weight:600">{{ reportData.date_no }}</td><td style="color:#555">Operation Time :</td><td style="font-weight:700;color:#c62828">{{ reportData.operation_time }}</td></tr>
                <tr><td style="color:#555">Batch Ref. NO. :</td><td colspan="3" style="font-weight:700;color:#1565c0">{{ selectedBatch.batch_id }}</td></tr>
                <tr><td style="color:#555">Mixing Tank :</td><td style="font-weight:600">{{ selectedBatch.plant }}</td><td style="color:#555">Batch ID Name :</td><td style="font-weight:600">{{ selectedBatch.sku_id }}</td></tr>
                <tr><td style="color:#555">Batch Size :</td><td style="font-weight:600">{{ (selectedBatch.batch_size||0).toLocaleString() }} Kg</td><td style="color:#555">Operator Name :</td><td>{{ reportData.operator || '—' }}</td></tr>
                <tr><td style="color:#555">SKU :</td><td colspan="3" style="font-weight:700">{{ selectedBatch.sku_name }}</td></tr>
                <tr>
                  <td style="color:#555">Status :</td>
                  <td style="font-weight:700;color:#e65100">{{ selectedBatch.status }}</td>
                  <td style="color:#555">Page :</td>
                  <td>1 of 1</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- Material Table -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
          <div v-for="(half, hi) in [materials.slice(0, Math.ceil(materials.length/2)), materials.slice(Math.ceil(materials.length/2))]" :key="hi">
            <div style="text-align:center;font-weight:700;font-size:9pt;padding:3px;background:#e8eaf6;border:1px solid #9fa8da">Material Table</div>
            <table style="width:100%;border-collapse:collapse;font-size:8.5pt">
              <thead>
                <tr style="background:#c5cae9">
                  <th style="border:1px solid #9fa8da;padding:3px 6px;text-align:left">Item</th>
                  <th style="border:1px solid #9fa8da;padding:3px;text-align:right;width:70px">Require</th>
                  <th style="border:1px solid #9fa8da;padding:3px;text-align:right;width:70px">Actual</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(mat, mi) in padMaterials(half, 9)" :key="mi"
                  :style="mi%2===0 ? 'background:#f9f9f9' : ''">
                  <td style="border:1px solid #ddd;padding:2px 6px;color:#1565c0;font-weight:600">{{ mat.re_code || 'x' }}</td>
                  <td style="border:1px solid #ddd;padding:2px 6px;text-align:right">{{ mat.target_value != null ? Number(mat.target_value).toFixed(3) : '0.000' }}</td>
                  <td style="border:1px solid #ddd;padding:2px 6px;text-align:right;color:#2e7d32;font-weight:700">{{ mat.actual_value != null ? Number(mat.actual_value).toFixed(3) : '0.000' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Process Step Table -->
        <div style="font-weight:700;font-size:10pt;margin-bottom:4px">Process Step</div>
        <table style="width:100%;border-collapse:collapse;font-size:8.5pt;margin-bottom:16px">
          <thead>
            <tr style="background:#e8eaf6">
              <th rowspan="2" style="border:1px solid #9fa8da;padding:3px;text-align:center;width:46px">Step<br>NO.</th>
              <th rowspan="2" style="border:1px solid #9fa8da;padding:3px;text-align:center">Process Condition</th>
              <th colspan="3" style="border:1px solid #9fa8da;padding:3px;text-align:center">Time</th>
              <th colspan="4" style="border:1px solid #9fa8da;padding:3px;text-align:center">Batch Check</th>
            </tr>
            <tr style="background:#e8eaf6">
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:68px">Start</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:68px">Stop</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:60px">Duration<br>(HH:MM:SS)</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:72px">Temperature<br>(DegC)</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:44px">Brix</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:44px">pH</th>
              <th style="border:1px solid #9fa8da;padding:3px;text-align:center;width:44px">OK/NG</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(ps, pi) in processSteps" :key="pi" :style="pi%2===0 ? 'background:#f9f9f9' : ''">
              <td style="border:1px solid #ddd;padding:3px;text-align:center;font-weight:700">{{ pi+1 }}</td>
              <td style="border:1px solid #ddd;padding:3px 6px;font-weight:600;color:#1a237e">{{ ps.label }}</td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center;color:#546e7a">{{ ps.start || '—' }}</td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center;color:#546e7a">{{ ps.stop || '—' }}</td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center">{{ ps.duration || '' }}</td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center;color:#c62828;font-weight:700">{{ ps.temperature ? ps.temperature+'°C' : '' }}</td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center"></td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center"></td>
              <td style="border:1px solid #ddd;padding:3px;text-align:center"></td>
            </tr>
          </tbody>
        </table>

        <!-- Signature -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px;margin-top:24px;text-align:center;font-size:9pt">
          <div>
            <div style="font-weight:700;margin-bottom:32px">OPERATOR</div>
            <div style="border-top:1px solid #333;padding-top:4px;color:#666">Name / Signature / Date</div>
          </div>
          <div>
            <div style="font-weight:700;margin-bottom:32px">QC</div>
            <div style="border-top:1px solid #333;padding-top:4px;color:#666">Name / Signature / Date</div>
          </div>
          <div>
            <div style="font-weight:700;margin-bottom:32px">MANAGER</div>
            <div style="border-top:1px solid #333;padding-top:4px;color:#666">Name / Signature / Date</div>
          </div>
        </div>

      </div><!-- end report-page -->
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading" class="column items-center justify-center q-pa-xl text-grey-5" style="min-height:300px">
      <q-icon name="description" size="64px" />
      <div class="text-h6 q-mt-md">Select a batch to preview the Mixing Report</div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'

const $q = useQuasar()
const { getAuthHeader } = useAuth()

const apiBase = appConfig.apiBaseUrl

const loading     = ref(false)
const batches     = ref<any[]>([])
const selectedBatch = ref<any>(null)
const reportData  = ref<any>(null)
const rawLogs     = ref<any[]>([])
const logoUrl     = '/mitrphol_logo.png'

const statusColor: Record<string,string> = {
  Done: 'green-7', 'In-Progress': 'orange-7', Prepared: 'blue-5',
  Created: 'grey-5', Cancelled: 'red-5', Hold: 'amber-7'
}

// ── Computed ────────────────────────────────────────────────
const materials = computed(() => {
  // Unique ingredient rows (re_code has value)
  const seen = new Set<string>()
  const mats: any[] = []
  for (const l of rawLogs.value) {
    if (l.re_code && !seen.has(l.re_code)) {
      seen.add(l.re_code)
      mats.push(l)
    }
  }
  return mats
})

const processSteps = computed(() => {
  // Group by phase_id: track start/stop timestamps + sum all duration_sec
  const phaseMap: Record<string, any> = {}
  for (const l of rawLogs.value) {
    const pid = l.phase_id || '—'
    if (!phaseMap[pid]) {
      phaseMap[pid] = {
        label: l.phase_description ? `${pid} - ${l.phase_description}` : pid,
        start: l.completed_at,
        stop: l.completed_at,
        temperature: l.temperature,
        totalSec: Number(l.duration_sec || 0)
      }
    } else {
      if (l.completed_at && l.completed_at > phaseMap[pid].stop) {
        phaseMap[pid].stop = l.completed_at
      }
      phaseMap[pid].totalSec += Number(l.duration_sec || 0)
    }
  }
  return Object.values(phaseMap).map(ps => {
    const start = ps.start ? fmtHM(ps.start) : '—'
    const stop  = ps.stop  ? fmtHM(ps.stop)  : '—'
    // Priority 1: sum of duration_sec from DB (accurate for all phase types)
    // Priority 2: fallback to stop-start timestamp diff
    let dur: string | null = null
    if (ps.totalSec > 0) {
      dur = fmtHMS(ps.totalSec)
    } else if (ps.start && ps.stop && ps.start !== ps.stop) {
      const sec = Math.round((new Date(ps.stop).getTime() - new Date(ps.start).getTime()) / 1000)
      if (sec > 0) dur = fmtHMS(sec)
    }
    return { ...ps, start, stop, duration: dur }
  })
})

const reportData_computed = computed(() => {
  if (!selectedBatch.value || !rawLogs.value.length) return null
  const done = rawLogs.value.filter(l => l.completed_at)
  const first = done.length ? done[0].completed_at : null
  const last  = done.length ? done[done.length-1].completed_at : null
  let opTime = '—'
  if (first && last) {
    const sec = Math.round((new Date(last).getTime() - new Date(first).getTime()) / 1000)
    const h = Math.floor(sec/3600)
    const m = Math.floor((sec%3600)/60)
    opTime = fmtHMS(sec)
  }
  return {
    date_no:        first ? fmtDate(first) : '—',
    operation_time: opTime,
    operator:       done[0]?.operator2 || done[0]?.operator || '—'
  }
})

// ── Helpers ──────────────────────────────────────────────────
function fmtDate(dt: string) {
  try {
    const d = new Date(dt)
    const p = (n: number) => String(n).padStart(2,'0')
    return `${p(d.getDate())}/${p(d.getMonth()+1)}/${String(d.getFullYear()).slice(-2)}`
  } catch { return dt }
}
function fmtHM(dt: string) {
  try {
    const d = new Date(dt)
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  } catch { return '—' }
}
function fmtHMS(sec: number) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}
function padMaterials(arr: any[], n: number) {
  const out = [...arr]
  while (out.length < n) out.push({ re_code: 'x', target_value: 0, actual_value: 0 })
  return out
}

// ── Data fetching ─────────────────────────────────────────────
async function loadBatches() {
  loading.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/production-plans/`, {
      headers: getAuthHeader() as Record<string,string>,
      query: { status: 'all', limit: 500 }
    })
    const plans: any[] = Array.isArray(res) ? res : (res?.plans ?? [])
    const flat: any[] = []
    plans.forEach((p: any) => {
      ;(p.batches || []).forEach((b: any) => {
        flat.push({ ...b, sku_name: p.sku_name || b.sku_id, plan_id: p.plan_id, plant: b.plant || p.plant || '' })
      })
    })
    flat.sort((a, b) => new Date(b.updated_at||b.created_at||0).getTime() - new Date(a.updated_at||a.created_at||0).getTime())
    // ── DONE only ──
    batches.value = flat.filter(b => b.status === 'Done')
    // Auto-select latest Done batch
    const auto = batches.value[0]
    if (auto) { selectedBatch.value = auto; await loadLogs(auto.batch_id) }
  } finally { loading.value = false }
}

async function loadLogs(batchId: string) {
  reportData.value = null
  rawLogs.value = []
  try {
    const res = await $fetch<any>(`${apiBase}/production-batches/${batchId}/logs`, {
      headers: getAuthHeader() as Record<string,string>
    })
    rawLogs.value = (res.logs || []).sort((a: any, b: any) =>
      (a.completed_at||'') < (b.completed_at||'') ? -1 : 1
    )
    reportData.value = reportData_computed.value
  } catch (e) { console.error(e) }
}

async function onBatchSelect(batch: any) {
  // batch is the full object (no emit-value)
  const id = batch?.batch_id || batch
  if (id) await loadLogs(String(id))
}

function exportPDF() {
  if (!selectedBatch.value || !reportData.value) return
  const b   = selectedBatch.value
  const rd  = reportData.value
  const el  = document.getElementById('mixing-report-content')
  const body = el ? el.innerHTML : '<p>No data</p>'
  const win = window.open('', '_blank', 'width=1000,height=800')
  if (!win) return
  win.document.write(`<!DOCTYPE html><html>
<head><meta charset="UTF-8"><title>Mixing Report — ${b.batch_id}</title>
<style>
@page { size: A4 portrait; margin: 10mm 12mm; }
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap');
* { box-sizing:border-box; font-family:'Sarabun','Segoe UI',sans-serif; }
body { font-size:9pt; color:#212121; }
table { width:100%; border-collapse:collapse; }
th,td { font-size:8.5pt; }
</style></head>
<body onload="window.print();window.close()">
${body}
</body></html>`)
  win.document.close()
}

function printReport() {
  window.print()
}

onMounted(() => { loadBatches() })
</script>

<style scoped>
.report-page {
  font-family: 'Sarabun', 'Segoe UI', sans-serif;
  font-size: 9pt;
  color: #212121;
}
@media print {
  .report-page {
    max-width: 100% !important;
    box-shadow: none !important;
    padding: 0 !important;
  }
  .q-page > div:first-child, .q-page > div:nth-child(2) {
    display: none !important;
  }
}
</style>

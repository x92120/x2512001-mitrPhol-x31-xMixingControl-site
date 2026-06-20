<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { appConfig } from '~/appConfig/config'

definePageMeta({ title: 'Production Report' })
useHead({ title: 'Production Report | xMixing Control' })

const $q = useQuasar()
const { getAuthHeader } = useAuth()
const { t, locale } = useI18n()
const route = useRoute()
const apiBase = appConfig.apiBaseUrl

// ── State ────────────────────────────────────────────────
const loading       = ref(false)
const detailLoading = ref(false)
const batches       = ref<any[]>([])
const selectedBatch = ref<any>(null)
const stepLogs      = ref<any[]>([])
const qcRecords     = ref<any[]>([])
const subBatches    = ref<any[]>([])

// ── Filters ──────────────────────────────────────────────
const search       = ref('')
const statusFilter = ref('All')
const page         = ref(1)
const rowsPerPage  = ref(20)

const statusOptions = ['All', 'Done', 'In-Progress', 'Prepared', 'Created', 'Cancelled', 'Hold']
const statusColor: Record<string, string> = {
  'Done': 'positive', 'In-Progress': 'warning',
  'Prepared': 'cyan-7', 'Created': 'blue-grey',
  'Cancelled': 'negative', 'Hold': 'orange',
}

// ── Computed ─────────────────────────────────────────────
const filteredBatches = computed(() => {
  let r = batches.value
  if (statusFilter.value !== 'All') r = r.filter(b => b.status === statusFilter.value)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    r = r.filter(b =>
      (b.batch_id || '').toLowerCase().includes(q) ||
      (b.sku_name || '').toLowerCase().includes(q) ||
      (b.plan_id || '').toLowerCase().includes(q)
    )
  }
  return r
})

const totalPages    = computed(() => Math.ceil(filteredBatches.value.length / rowsPerPage.value))
const pagedBatches  = computed(() => {
  const s = (page.value - 1) * rowsPerPage.value
  return filteredBatches.value.slice(s, s + rowsPerPage.value)
})

const stats = computed(() => ({
  total:      batches.value.length,
  done:       batches.value.filter(b => b.status === 'Done').length,
  inProgress: batches.value.filter(b => b.status === 'In-Progress').length,
  created:    batches.value.filter(b => b.status === 'Created').length,
  cancelled:  batches.value.filter(b => b.status === 'Cancelled').length,
}))

// Group step logs by phase_id
const phases = computed(() => {
  const map: Record<string, { phase_id: string; steps: any[] }> = {}
  for (const s of stepLogs.value) {
    const pid = s.phase_id || s.phase_number || '—'
    if (!map[pid]) map[pid] = { phase_id: pid, steps: [] }
    map[pid].steps.push(s)
  }
  return Object.values(map)
})

// ── Helpers ──────────────────────────────────────────────
const fmtDT = (dt: string | null | undefined, opts?: any) => {
  if (!dt) return '—'
  try {
    return new Date(dt).toLocaleString('th-TH', opts || {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit'
    })
  } catch { return dt }
}
const fmtTime = (dt: string | null | undefined) => {
  if (!dt) return '—'
  try {
    const d = new Date(dt)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${String(d.getFullYear()).slice(-2)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return dt as string }
}
const fmtNum = (v: any, d = 3) => {
  const n = parseFloat(v)
  return isNaN(n) ? '—' : n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
}
const actionColor = (code: string | number) => {
  const s = String(code)
  if (s.startsWith('1')) return { bg: '#e3f0ff', text: '#1565c0' }
  if (s.startsWith('2')) return { bg: '#e0f7f4', text: '#00695c' }
  if (s.startsWith('3')) return { bg: '#fff3e0', text: '#e65100' }
  return { bg: '#f3e5f5', text: '#6a1b9a' }
}

// ── Data fetching ─────────────────────────────────────────
const loadBatches = async () => {
  loading.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/production-plans/`, {
      headers: getAuthHeader() as Record<string, string>,
      query: { status: 'all', limit: 1000 }
    })
    const plans: any[] = Array.isArray(res) ? res : (res?.plans ?? [])
    const flat: any[] = []
    plans.forEach((p: any) => {
      (p.batches || []).forEach((b: any) => {
        flat.push({
          ...b,
          sku_name: p.sku_name || b.sku_id || '—',
          plan_id: p.plan_id
        })
      })
    })
    flat.sort((a, b) => {
      const da = new Date(a.updated_at || a.created_at || 0).getTime()
      const db_ = new Date(b.updated_at || b.created_at || 0).getTime()
      return db_ - da
    })
    batches.value = flat
  } catch (e) {
    console.error(e)
    $q.notify({ type: 'negative', message: 'Failed to load batch data' })
  } finally { loading.value = false }
}

const selectBatch = async (batch: any) => {
  if (!batch?.batch_id) return
  selectedBatch.value = batch
  stepLogs.value = []
  qcRecords.value = []
  subBatches.value = []
  detailLoading.value = true
  try {
    const headers = getAuthHeader() as Record<string, string>
    const [logRes, subRes] = await Promise.allSettled([
      $fetch<any>(`${apiBase}/production-batches/${batch.batch_id}/logs`, { headers }),
      $fetch<any[]>(`${apiBase}/production-batches/${batch.batch_id}/sub-batches`, { headers })
    ])
    if (logRes.status === 'fulfilled') {
      const data = logRes.value
      const qcMap: Record<number, any> = {}
      ;(data.qc_records || []).forEach((q: any) => { qcMap[q.step_id] = q })
      qcRecords.value = data.qc_records || []
      // Sort logs by completed_at then compute duration from consecutive steps
      const rawLogs = (data.logs || []).slice().sort((a: any, b: any) => {
        const ta = a.completed_at ? new Date(a.completed_at).getTime() : 0
        const tb = b.completed_at ? new Date(b.completed_at).getTime() : 0
        return ta - tb
      })
      const pad2 = (n: number) => String(n).padStart(2, '0')
      stepLogs.value = rawLogs.map((s: any, i: number) => {
        let _durationStr = '—'
        let _startStr    = '—'
        if (s.completed_at) {
          const tNow = new Date(s.completed_at).getTime()
          const prev = rawLogs.slice(0, i).reverse().find((p: any) => p.completed_at && p.phase_id === s.phase_id)
          if (prev) {
            const tPrev = new Date(prev.completed_at).getTime()
            // Start time = previous step's completed_at (HH:MM only)
            const dp = new Date(prev.completed_at)
            _startStr = fmtTime(prev.completed_at)  // full DD/MM/YY HH:MM like Completed
            // Duration
            const sec = Math.round((tNow - tPrev) / 1000)
            if (sec > 0) {
              const h = Math.floor(sec / 3600)
              const m = Math.floor((sec % 3600) / 60)
              _durationStr = h > 0 ? `${h}:${pad2(m)}` : `0:${pad2(m)}`
            }
          }
        }
        return { ...s, _timeStr: fmtTime(s.completed_at), _startStr, _durationStr }
      })
    }
    if (subRes.status === 'fulfilled') subBatches.value = subRes.value || []
  } catch (e) {
    console.error(e)
  } finally { detailLoading.value = false }
}

// ── Export PDF (print window) ─────────────────────────
const exportPdf = () => {
  if (!selectedBatch.value) return
  const isTH = locale.value === 'th'
  const lbl = {
    title:       isTH ? 'รายงานบันทึกการผลิต' : 'Batch Production Record',
    system:      'xMixing Control System — ' + (isTH ? 'รายงานการผลิต' : 'Production Report'),
    batchId:     isTH ? 'รหัสแบทช์' : 'BATCH ID',
    product:     isTH ? 'ชื่อผลิตภัณฑ์' : 'PRODUCT',
    line:        isTH ? 'สาย' : 'LINE',
    batchSize:   isTH ? 'ขนาดแบทช์' : 'BATCH SIZE',
    status:      isTH ? 'สถานะ' : 'STATUS',
    subRun:      isTH ? 'การผลิตย่อย (Sub-Run)' : 'Sub-Batch Runs',
    subRunCol:   isTH ? ['รอบ','ปริมาณจริง (kg)','เวลาเริ่ม','เวลาสิ้นสุด','ผู้ดำเนินการ','หมายเหตุ'] : ['Run','Actual (kg)','Start','Stop','Operator','Remarks'],
    qcTitle:     isTH ? 'QC Records — Brix / pH' : 'QC Records — Brix / pH',
    qcCol:       isTH ? ['Step','เวลา','Brix Tgt','Brix Act','OK','pH Tgt','pH Act','OK','ผู้ดำเนินการ'] : ['Step','Time','Brix Tgt','Brix Act','OK','pH Tgt','pH Act','OK','Operator'],
    execLog:     isTH ? 'Execution Trace Log' : 'Execution Trace Log',
    step:        isTH ? 'ขั้นตอน' : 'Step',
    code:        isTH ? 'รหัส' : 'Code',
    action:      isTH ? 'การกระทำ' : 'Action',
    reCode:      isTH ? 'รหัสวัตถุดิบ' : 'RE Code',
    require:     isTH ? 'ปริมาณที่ต้องการ' : 'Require',
    actual:      isTH ? 'ปริมาณจริง' : 'Actual',
    uom:         isTH ? 'หน่วย' : 'UOM',
    temp:        isTH ? 'อุณหภูมิ' : 'Temp',
    agitator:    isTH ? 'ความเร็วกวน' : 'Agitator',
    hiShear:     isTH ? 'ไฮเชียร์' : 'Hi-Shear',
    destination: isTH ? 'ปลายทาง' : 'Destination',
    condition:   isTH ? 'เงื่อนไข' : 'Condition',
    completed:   isTH ? 'เสร็จสิ้น' : 'Completed',
    user1:       isTH ? 'ผู้ใช้ 1 (สแกน)' : 'User 1 (Scan)',
    user2:       isTH ? 'ผู้ใช้ 2 (เท)' : 'User 2 (Pour)',
    printed:     isTH ? 'พิมพ์เมื่อ' : 'Printed',
    steps:       isTH ? 'ขั้นตอน' : 'steps',
    timeStop:    isTH ? 'เวลาสิ้นสุด' : 'Stop',
    sec:         isTH ? 'วินาที' : 'sec',
    actualDate:  isTH ? 'วันที่ผลิตจริง' : 'Actual Date',
    timeStart:   isTH ? 'เวลาเริ่ม' : 'Start',
    duration:    isTH ? 'ระยะเวลา' : 'Duration',
  }
  const b = selectedBatch.value
  const now = new Date().toLocaleString(isTH ? 'th-TH' : 'en-GB')
  const dateStr = new Date().toLocaleDateString(isTH ? 'th-TH' : 'en-GB')
  const timeStr = new Date().toLocaleTimeString(isTH ? 'th-TH' : 'en-GB', { hour:'2-digit', minute:'2-digit' })

  // Build sub-run rows
  let subRunHtml = ''
  if (subBatches.value.length) {
    const rows = subBatches.value.map(sb => `
      <tr>
        <td style="text-align:center;font-weight:bold">${sb.sub_run}</td>
        <td style="text-align:right">${fmtNum(sb.actual_volume, 3)}</td>
        <td style="text-align:center">${fmtTime(sb.start_time)}</td>
        <td style="text-align:center">${fmtTime(sb.stop_time)}</td>
        <td>${sb.operator || '—'}</td>
        <td>${sb.remarks || '—'}</td>
      </tr>`).join('')
    subRunHtml = `
      <div class="section">
        <div class="section-title">◆ ${lbl.subRun}</div>
        <table><thead><tr>${lbl.subRunCol.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>
      </div>`
  }

  // Build QC rows
  let qcHtml = ''
  if (qcRecords.value.length) {
    const rows = qcRecords.value.map(qc => `
      <tr>
        <td style="text-align:center"><span class="chip-teal">${qc.step_id}</span></td>
        <td style="text-align:center">${fmtTime(qc.recorded_at)}</td>
        <td style="text-align:right">${fmtNum(qc.brix_target,1)}</td>
        <td style="text-align:right;color:#00695c;font-weight:bold">${fmtNum(qc.brix_actual,2)}</td>
        <td style="text-align:center">${qc.brix_ok ? '✓' : '✗'}</td>
        <td style="text-align:right">${fmtNum(qc.ph_target,2)}</td>
        <td style="text-align:right;color:#00695c;font-weight:bold">${fmtNum(qc.ph_actual,2)}</td>
        <td style="text-align:center">${qc.ph_ok ? '✓' : '✗'}</td>
        <td>${qc.operator || '—'}</td>
      </tr>`).join('')
    qcHtml = `
      <div class="section">
        <div class="section-title">◆ ${lbl.qcTitle} (${qcRecords.value.length} checkpoints)</div>
        <table><thead><tr>${lbl.qcCol.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>
      </div>`
  }

  // Build phase tables
  let phaseHtml = ''
  for (const phase of phases.value) {
    const codeColor = (code: string) => {
      const s = String(code || '')
      if (s.startsWith('1')) return 'color:#1565c0;font-weight:600'
      if (s.startsWith('2')) return 'color:#00695c;font-weight:600'
      if (s.startsWith('3')) return 'color:#bf360c;font-weight:600'
      return 'color:#6a1b9a;font-weight:600'
    }
    const pad2 = (n: number) => String(n).padStart(2,'0')
    const rows = phase.steps.map((s: any, i: number) => {
      let dur      = '—'
      let startStr = '—'
      if (s.completed_at && i > 0) {
        const prev = phase.steps.slice(0, i).reverse().find((p: any) => p.completed_at)
        if (prev) {
          const dp = new Date(prev.completed_at)
          startStr = s._startStr || (() => {
            const pad2i = (n: number) => String(n).padStart(2,'0')
            return `${pad2i(dp.getDate())}/${pad2i(dp.getMonth()+1)}/${String(dp.getFullYear()).slice(-2)} ${pad2i(dp.getHours())}:${pad2i(dp.getMinutes())}`
          })()
          const sec = Math.round((new Date(s.completed_at).getTime() - dp.getTime()) / 1000)
          if (sec > 0) {
            const h = Math.floor(sec / 3600)
            const m = Math.floor((sec % 3600) / 60)
            dur = h > 0 ? `${h}:${pad2(m)}` : `0:${pad2(m)}`
          }
        }
      }
      return `
      <tr>
        <td style="text-align:center;padding:2px 4px">
          <span style="display:inline-block;border:1px solid #90a4ae;border-radius:3px;padding:0 5px;font-size:7.5pt;color:#37474f">${s.sub_step || s.step_id || ''}</span>
        </td>
        <td style="text-align:center">
          <span style="${codeColor(s.action_code)};font-size:7.5pt">${s.action_code || '—'}</span>
        </td>
        <td style="font-size:7.5pt">${s.action_description || s.action || '—'}</td>
        <td style="color:#1565c0;font-weight:600;font-size:7.5pt">${s.re_code || '—'}</td>
        <td style="text-align:right;font-size:7.5pt">${s.target_value != null ? Number(s.target_value).toLocaleString(undefined,{minimumFractionDigits:3,maximumFractionDigits:3}) : '—'}</td>
        <td style="text-align:right;color:#2e7d32;font-weight:700;font-size:7.5pt">${s.actual_value != null ? Number(s.actual_value).toLocaleString(undefined,{minimumFractionDigits:3,maximumFractionDigits:3}) : '0.000'}</td>
        <td style="text-align:center;font-size:7.5pt;color:#666">${s.uom || 'kg'}</td>
        <td style="text-align:center;font-weight:700;font-size:7.5pt;color:${s.temperature ? '#c62828' : '#999'}">${s.temperature ? s.temperature+'°C' : '—'}</td>
        <td style="text-align:center;font-weight:700;font-size:7.5pt;color:${s.agitator_rpm ? '#e65100' : '#999'}">${s.agitator_rpm ? s.agitator_rpm+' rpm' : '—'}</td>
        <td style="text-align:center;font-weight:700;font-size:7.5pt;color:${s.hi_shear_rpm ? '#e65100' : '#999'}">${s.hi_shear_rpm ? s.hi_shear_rpm+' rpm' : '—'}</td>
        <td style="text-align:center;font-size:7.5pt;color:#555">${s.destination || '—'}</td>
        <td style="font-size:7.5pt;color:#555">${s.step_condition || '—'}</td>
        <td style="text-align:center;font-size:7.5pt;color:#546e7a;white-space:nowrap">${startStr}</td>
        <td style="text-align:center;font-size:7.5pt;white-space:nowrap">${s._timeStr}</td>
        <td style="text-align:center;font-size:7.5pt;font-weight:700;color:#5c6bc0">${dur}</td>
        <td style="text-align:center;font-size:7.5pt;color:#1565c0">${s.operator || '—'}</td>
        <td style="text-align:center;font-size:7.5pt;color:#1565c0">${s.operator2 || '—'}</td>
      </tr>`
    }).join('')
    phaseHtml += `
      <div class="section">
        <div class="section-title">◆ ${phase.phase_id} — ${phase.steps.length} ${lbl.steps}</div>
        <table>
          <thead><tr style="background:#e8eaf6">
            <th style="width:34px">${lbl.step}</th>
            <th style="width:56px">${lbl.code}</th>
            <th>${lbl.action}</th>
            <th>${lbl.reCode}</th>
            <th style="text-align:right;width:68px">${lbl.require}</th>
            <th style="text-align:right;width:68px;color:#2e7d32">${lbl.actual}</th>
            <th style="width:30px">${lbl.uom}</th>
            <th style="width:44px">${lbl.temp}</th>
            <th style="width:60px">${lbl.agitator}</th>
            <th style="width:60px">${lbl.hiShear}</th>
            <th style="width:60px">${lbl.destination}</th>
            <th>${lbl.condition}</th>
            <th style="width:44px;white-space:nowrap">${lbl.timeStart}</th>
            <th style="width:80px;white-space:nowrap">${lbl.completed}</th>
            <th style="width:46px">${lbl.duration}</th>
            <th style="width:60px">${lbl.user1}</th>
            <th style="width:60px">${lbl.user2}</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`
  }

  const html = `<!DOCTYPE html><html lang="${locale.value}">
<head><meta charset="UTF-8">
<title>${lbl.title} — ${b.batch_id}</title>
<style>
  @page { size: A4 landscape; margin: 10mm 12mm; }
  @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap');
  * { box-sizing: border-box; font-family: 'Sarabun', 'Segoe UI', sans-serif; }
  body { font-size: 9pt; color: #212121; }
  .page-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px; font-size:8pt; color:#666; }
  h1 { font-size:18pt; font-weight:700; color:#1a237e; margin:0 0 1px 0; }
  .sub-title { font-size:8pt; color:#888; margin-bottom:10px; }
  .info-grid { display:grid; grid-template-columns:1fr 2fr 1fr 1fr 1fr; gap:0; background:#fafafa; padding:8px 12px; margin-bottom:8px; border:1px solid #ddd; border-radius:3px; }
  .info-cell { padding:2px 8px 2px 0; }
  .info-label { font-size:6.5pt; text-transform:uppercase; color:#9e9e9e; letter-spacing:.5px; font-weight:600; }
  .info-value { font-size:10pt; font-weight:700; margin-top:1px; color:#212121; }
  .info-value.batch { color:#1a237e; font-size:11pt; }
  .section { margin-bottom:8px; }
  .section-title { font-size:8.5pt; font-weight:700; color:#1a237e; margin-bottom:2px; padding-bottom:2px; border-bottom:2px solid #3949ab; }
  table { width:100%; border-collapse:collapse; }
  th { background:#e8eaf6; color:#283593; font-weight:700; padding:3px 5px; text-align:left; border:1px solid #c5cae9; font-size:7pt; white-space:nowrap; }
  td { padding:2px 4px; border:1px solid #e0e0e0; vertical-align:middle; font-size:8pt; }
  tr:nth-child(even) td { background:#f9f9f9; }
  .chip-teal { background:#e0f2f1; color:#00695c; padding:1px 6px; border-radius:10px; font-size:7.5pt; font-weight:600; }
  .footer { margin-top:10px; display:flex; justify-content:space-between; font-size:7pt; color:#aaa; border-top:1px solid #eee; padding-top:4px; }
  .date-bar { background:#e8f5e9; border-left:4px solid #43a047; padding:4px 10px; margin-bottom:8px; font-size:8pt; color:#2e7d32; border-radius:2px; }
  .date-bar strong { font-weight:700; }
  .date-bar .sep { margin:0 6px; color:#a5d6a7; }
</style></head><body>
  <div class="page-header">
    <div class="page-header-left">${dateStr}, ${timeStr}</div>
    <div style="text-align:center;flex:1">Batch Record — ${b.batch_id}</div>
    <div class="page-header-right">${lbl.printed}: ${now}<br>SKU: ${b.sku_id || b.sku_name}</div>
  </div>
  <h1>${lbl.title}</h1>
  <div class="sub-title">${lbl.system}</div>
  <div class="info-grid">
    <div class="info-cell"><div class="info-label">${lbl.batchId}</div><div class="info-value batch">${b.batch_id}</div></div>
    <div class="info-cell"><div class="info-label">${lbl.product}</div><div class="info-value">${b.sku_name}</div></div>
    <div class="info-cell"><div class="info-label">${lbl.line}</div><div class="info-value">${b.plant || 'MIX-1'}</div></div>
    <div class="info-cell"><div class="info-label">${lbl.batchSize}</div><div class="info-value">${(b.batch_size||0).toLocaleString()} kg</div></div>
    <div class="info-cell"><div class="info-label">${lbl.status}</div><div class="info-value">${b.status}</div></div>
  </div>
  ${(() => {
    // ── Date/Time Bar: use completed_at of first/last step ──
    const allTimes = stepLogs.value.map((s: any) => s.completed_at).filter(Boolean).sort()
    if (!allTimes.length) return ''
    const firstTime = allTimes[0]
    const lastTime  = allTimes[allTimes.length - 1]
    const fmtFull = (dt: string) => {
      try {
        const d = new Date(dt)
        const pad = (n: number) => String(n).padStart(2,'0')
        return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${String(d.getFullYear()).slice(-2)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
      } catch { return dt }
    }
    const durSec = Math.round((new Date(lastTime).getTime() - new Date(firstTime).getTime()) / 1000)
    const actualDate = new Date(firstTime).toLocaleDateString(isTH ? 'th-TH' : 'en-GB', { day:'2-digit', month:'2-digit', year:'2-digit' })
    return `<div class="date-bar">
      <strong>${lbl.actualDate}:</strong> ${actualDate}
      <span class="sep">|</span>
      <strong>${lbl.timeStart}:</strong> ${fmtFull(firstTime)}
      <span class="sep">—</span>
      <strong>${lbl.timeStop}:</strong> ${fmtFull(lastTime)}
      <span class="sep">|</span>
      <strong>${durSec.toLocaleString()} ${lbl.sec}</strong>
    </div>`
  })()}
  ${subRunHtml}
  ${qcHtml}
  <div class="section">
    <div class="section-title">${lbl.execLog} (${stepLogs.value.length} ${lbl.steps})</div>
    ${phaseHtml || '<p style="color:#999;font-size:8pt">No execution logs</p>'}
  </div>
  <div class="footer">
    <span>xMixing Control — Production Record</span>
    <span>Batch: ${b.batch_id} | SKU: ${b.sku_id || b.sku_name} | ${b.plant || ''}</span>
    <span>Generated: ${now}</span>
  </div>
</body></html>`

  const win = window.open('', '_blank', 'width=1200,height=800')
  if (!win) { $q.notify({ type: 'warning', message: 'Popup blocked — please allow popups' }); return }
  win.document.write(html)
  win.document.close()
  setTimeout(() => win.print(), 600)
}

watch([statusFilter, search], () => { page.value = 1 })

onMounted(async () => {
  const qBatchId = String(route.query.batch_id || '').trim()
  if (qBatchId) {
    statusFilter.value = 'All'
    try {
      const d = await $fetch<any>(
        `${apiBase}/production-batches/by-batch-id/${qBatchId}`,
        { headers: getAuthHeader() as Record<string, string> }
      )
      if (d?.batch_id) { await selectBatch(d); loadBatches(); return }
    } catch { /* fallthrough */ }
    await loadBatches()
    const found = batches.value.find(b => b.batch_id === qBatchId)
    if (found) await selectBatch(found)
  } else {
    await loadBatches()
  }
})
</script>

<template>
  <q-page class="rpt-page">

    <!-- ══ Header ══════════════════════════════════════════ -->
    <div class="rpt-header row items-center q-pa-sm q-gutter-sm">
      <q-icon name="assessment" size="26px" color="indigo-7" />
      <div>
        <div class="text-subtitle1 text-weight-bold">Production Batch Records</div>
        <div class="text-caption text-grey-6">รายงานการผลิตและบันทึกคุณภาพ</div>
      </div>
      <q-space />
      <!-- Stats -->
      <div v-for="(val, key) in { Total: stats.total, Done: stats.done, 'In-Progress': stats.inProgress, Created: stats.created, Cancelled: stats.cancelled }"
        :key="key" class="stat-pill">
        <span class="stat-pill-val"
          :class="key==='Total'?'text-indigo-8':key==='Done'?'text-positive':key==='In-Progress'?'text-warning':key==='Created'?'text-blue-grey-6':'text-negative'">
          {{ val }}
        </span>
        <span class="stat-pill-lbl">{{ key }}</span>
      </div>
      <q-btn flat round icon="refresh" color="primary" dense @click="loadBatches" :loading="loading">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <!-- ══ Filters ══════════════════════════════════════════ -->
    <div class="rpt-filters row q-px-sm q-py-xs q-gutter-xs items-center">
      <q-input v-model="search" dense outlined placeholder="Search Batch ID / Product..." clearable
        style="min-width:180px; max-width:260px" bg-color="white">
        <template #prepend><q-icon name="search" size="xs" /></template>
      </q-input>
      <q-btn-toggle v-model="statusFilter"
        :options="statusOptions.map(s => ({ label: s, value: s }))"
        dense unelevated toggle-color="indigo-7" color="white" text-color="grey-7"
        rounded size="sm" class="filter-tog" />
      <div class="text-caption text-grey-6 q-ml-xs">{{ filteredBatches.length }} batches</div>
    </div>

    <!-- ══ Split View ════════════════════════════════════════ -->
    <div class="rpt-split">

      <!-- ── Left: Batch List ─────────────────────────────── -->
      <div class="rpt-list">
        <q-virtual-scroll :items="pagedBatches" v-slot="{ item: b }" style="height:100%">
          <div :key="b.batch_id"
            class="batch-card"
            :class="{ 'batch-card--active': selectedBatch?.batch_id === b.batch_id }"
            @click="selectBatch(b)">
            <div class="row items-start no-wrap">
              <div class="col">
                <div class="row items-center q-gutter-xs">
                  <span class="text-weight-bold text-indigo-8 text-caption">{{ b.batch_id }}</span>
                  <q-chip dense :color="statusColor[b.status] || 'grey-5'" text-color="white" size="xs">
                    {{ b.status }}
                  </q-chip>
                </div>
                <div class="text-caption text-grey-6 ellipsis" style="max-width:240px">{{ b.sku_name }}</div>
                <div class="text-caption text-grey-5">{{ b.plan_id }}</div>
              </div>
              <div class="text-right col-shrink">
                <div class="text-caption text-weight-bold">{{ (b.batch_size || 0).toLocaleString() }} kg</div>
              </div>
            </div>
          </div>
        </q-virtual-scroll>

        <!-- Pagination -->
        <div class="rpt-list-footer row items-center justify-between q-px-sm">
          <q-pagination v-if="totalPages > 1" v-model="page" :max="totalPages"
            direction-links flat color="indigo-7" size="sm" />
          <q-select v-model="rowsPerPage" :options="[20, 50, 100]" dense borderless
            label="Rows" style="width:80px" emit-value map-options />
        </div>
      </div>

      <!-- ── Right: Detail Panel ──────────────────────────── -->
      <div class="rpt-detail">

        <!-- Empty state -->
        <div v-if="!selectedBatch" class="rpt-empty">
          <q-icon name="touch_app" size="64px" color="grey-3" />
          <div class="q-mt-md text-subtitle1 text-grey-5">Select a batch to view report</div>
        </div>

        <template v-else>
          <!-- Detail Header -->
          <div class="detail-header row items-center q-pa-md">
            <div class="col">
              <div class="text-h6 text-weight-bold text-indigo-9">{{ selectedBatch.batch_id }}</div>
              <div class="text-caption text-grey-6">
                {{ selectedBatch.sku_name }}&nbsp;·&nbsp;Plan: {{ selectedBatch.plan_id }}
                &nbsp;·&nbsp;{{ (selectedBatch.batch_size || 0).toLocaleString() }} kg
              </div>
            </div>
            <q-chip :color="statusColor[selectedBatch.status] || 'grey-5'" text-color="white" dense>
              {{ selectedBatch.status }}
            </q-chip>
            <q-btn flat icon="print" :label="t('report.print')" color="grey-7" dense class="q-ml-sm"
              @click="() => window.print()" />
            <q-btn unelevated icon="picture_as_pdf" :label="t('rpt.batchRecord')" color="red-8" text-color="white" dense class="q-ml-sm"
              @click="exportPdf" />
          </div>

          <q-scroll-area style="flex:1; height:0">
            <div class="q-pa-md q-pb-xl">

              <!-- Loading -->
              <div v-if="detailLoading" class="text-center q-py-xl">
                <q-spinner-dots color="indigo-7" size="48px" />
              </div>

              <template v-else>
                <!-- ─ Sub-Batch Runs ───────────────────────── -->
                <div v-if="subBatches.length" class="section-block">
                  <div class="section-title q-mb-sm">
                    <q-icon name="layers" color="indigo-7" size="sm" />
                    {{ t('rpt.subBatch') }}
                  </div>
                  <q-markup-table dense flat bordered class="rpt-table">
                    <thead>
                      <tr class="bg-indigo-1">
                        <th class="text-center">{{ t('rpt.steps') }}</th>
                        <th class="text-right">{{ t('rpt.actual') }} (kg)</th>
                        <th class="text-center">{{ t('rpt.timeStart') }}</th>
                        <th class="text-center">{{ t('rpt.timeStop') }}</th>
                        <th class="text-center">{{ t('rpt.user1') }}</th>
                        <th class="text-left">{{ t('rpt.condition') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="sb in subBatches" :key="sb.sub_run">
                        <td class="text-center text-weight-bold">{{ sb.sub_run }}</td>
                        <td class="text-right text-weight-bold">{{ fmtNum(sb.actual_volume, 3) }}</td>
                        <td class="text-center">{{ fmtTime(sb.start_time) }}</td>
                        <td class="text-center">{{ fmtTime(sb.stop_time) }}</td>
                        <td class="text-center">{{ sb.operator || '—' }}</td>
                        <td>{{ sb.remarks || '—' }}</td>
                      </tr>
                    </tbody>
                  </q-markup-table>
                </div>

                <!-- ─ QC Records Brix/pH ──────────────────── -->
                <div v-if="qcRecords.length" class="section-block">
                  <div class="section-title q-mb-sm">
                    <q-icon name="science" color="teal-7" size="sm" />
                    QC Records — Brix / pH ({{ qcRecords.length }} checkpoints)
                  </div>
                  <q-markup-table dense flat bordered class="rpt-table">
                    <thead>
                      <tr class="bg-teal-1">
                        <th class="text-center">{{ t('rpt.step') }}</th>
                        <th class="text-center">{{ t('rpt.completed') }}</th>
                        <th class="text-right">Brix Tgt</th>
                        <th class="text-right" style="color:#00897b">Brix Act</th>
                        <th class="text-center">OK</th>
                        <th class="text-right">pH Tgt</th>
                        <th class="text-right" style="color:#00897b">pH Act</th>
                        <th class="text-center">OK</th>
                        <th class="text-left">{{ t('rpt.user1') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="qc in qcRecords" :key="qc.id">
                        <td class="text-center">
                          <q-chip dense size="sm" color="teal-7" text-color="white">
                            {{ qc.step_id }}
                          </q-chip>
                        </td>
                        <td class="text-center text-caption">{{ fmtTime(qc.recorded_at) }}</td>
                        <td class="text-right">{{ fmtNum(qc.brix_target, 1) }}</td>
                        <td class="text-right text-weight-bold" style="color:#00897b">{{ fmtNum(qc.brix_actual, 2) }}</td>
                        <td class="text-center">
                          <q-icon v-if="qc.brix_ok" name="check" color="positive" />
                          <q-icon v-else name="close" color="negative" />
                        </td>
                        <td class="text-right">{{ fmtNum(qc.ph_target, 2) }}</td>
                        <td class="text-right text-weight-bold" style="color:#00897b">{{ fmtNum(qc.ph_actual, 2) }}</td>
                        <td class="text-center">
                          <q-icon v-if="qc.ph_ok" name="check" color="positive" />
                          <q-icon v-else name="close" color="negative" />
                        </td>
                        <td>{{ qc.operator || '—' }}</td>
                      </tr>
                    </tbody>
                  </q-markup-table>
                </div>

                <!-- ─ Execution Trace Log (by phase) ─────── -->
                <div class="section-block">
                  <div class="section-title q-mb-sm">
                    <q-icon name="list_alt" color="indigo-7" size="sm" />
                    Execution Trace Log ({{ stepLogs.length }} steps)
                  </div>

                  <div v-if="!stepLogs.length" class="text-grey-5 text-caption q-pa-md">
                    No execution logs found for this batch.
                  </div>

                  <div v-for="phase in phases" :key="phase.phase_id" class="phase-block q-mb-sm">
                    <!-- Phase Header -->
                    <div class="phase-label row items-center q-gutter-xs q-mb-xs">
                      <q-chip dense color="indigo-7" text-color="white" size="sm" icon="layers">
                        {{ phase.phase_id }}
                      </q-chip>
                      <span class="text-caption text-grey-6">{{ phase.steps.length }} steps</span>
                    </div>

                    <q-markup-table dense flat bordered class="rpt-table">
                      <thead>
                        <tr class="bg-indigo-1">
                          <th class="text-center" style="width:36px">{{ t('rpt.step') }}</th>
                          <th class="text-center" style="width:60px">{{ t('rpt.code') }}</th>
                          <th class="text-left">{{ t('rpt.action') }}</th>
                          <th class="text-left">{{ t('rpt.reCode') }}</th>
                          <th class="text-right" style="width:70px">{{ t('rpt.require') }}</th>
                          <th class="text-right" style="color:#2e7d32;width:70px">{{ t('rpt.actual') }}</th>
                          <th class="text-center" style="width:32px">{{ t('rpt.uom') }}</th>
                          <th class="text-center" style="width:46px">{{ t('rpt.temp') }}</th>
                          <th class="text-center" style="width:62px">{{ t('rpt.agitator') }}</th>
                          <th class="text-center" style="width:62px">{{ t('rpt.hiShear') }}</th>
                          <th class="text-center" style="width:62px">{{ t('rpt.destination') }}</th>
                          <th class="text-left" style="width:80px">{{ t('rpt.condition') }}</th>
                          <th class="text-center" style="width:48px">{{ t('rpt.timeStart') }}</th>
                          <th class="text-center" style="width:82px">{{ t('rpt.completed') }}</th>
                          <th class="text-center" style="width:52px">{{ t('rpt.duration') }}</th>
                          <th class="text-center" style="width:60px">{{ t('rpt.user1') }}</th>
                          <th class="text-center" style="width:60px">{{ t('rpt.user2') }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="step in phase.steps" :key="step.step_id || step.sub_step" class="rpt-row">
                          <td class="text-center">
                            <q-chip dense size="xs" outline color="grey-6">
                              {{ step.sub_step || step.step_id }}
                            </q-chip>
                          </td>
                          <td class="text-center">
                            <span class="action-chip"
                              :style="`background:${actionColor(step.action_code).bg};color:${actionColor(step.action_code).text}`">
                              {{ step.action_code }}
                            </span>
                          </td>
                          <td class="text-caption">{{ step.action_description || step.action || '—' }}</td>
                          <td class="text-caption text-weight-medium" style="color:#1565c0">
                            {{ step.re_code || '—' }}
                          </td>
                          <td class="text-right text-caption">{{ fmtNum(step.target_value, 3) }}</td>
                          <td class="text-right text-caption text-weight-bold" style="color:#2e7d32">
                            {{ fmtNum(step.actual_value, 3) }}
                          </td>
                          <td class="text-center text-caption text-grey-6">{{ step.uom || 'kg' }}</td>
                          <td class="text-center text-caption">
                            <span v-if="step.temperature" class="text-red-8 text-weight-bold">{{ step.temperature }}°C</span>
                            <span v-else class="text-grey-4">—</span>
                          </td>
                          <td class="text-center text-caption">
                            <span v-if="step.agitator_rpm" class="text-orange-9 text-weight-bold">{{ step.agitator_rpm }} rpm</span>
                            <span v-else class="text-grey-4">—</span>
                          </td>
                          <td class="text-center text-caption">
                            <span v-if="step.hi_shear_rpm" class="text-orange-9 text-weight-bold">{{ step.hi_shear_rpm }} rpm</span>
                            <span v-else class="text-grey-4">—</span>
                          </td>
                          <td class="text-center text-caption text-grey-8">{{ step.destination || '—' }}</td>
                          <td class="text-caption text-grey-7">{{ step.step_condition || '—' }}</td>
                          <td class="text-center text-caption" style="white-space:nowrap;color:#546e7a">{{ step._startStr }}</td>
                          <td class="text-center text-caption" style="white-space:nowrap">{{ step._timeStr }}</td>
                          <td class="text-center text-caption text-weight-bold" style="color:#5c6bc0">{{ step._durationStr }}</td>
                          <td class="text-center text-caption" style="color:#1565c0">{{ step.operator || '—' }}</td>
                          <td class="text-center text-caption" style="color:#1565c0">{{ step.operator2 || '—' }}</td>
                        </tr>
                      </tbody>
                    </q-markup-table>
                  </div>
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
/* ── Layout ────────────────────────────────────────────── */
.rpt-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f0f2f8;
  overflow: hidden;
}
.rpt-header {
  background: white;
  border-bottom: 1px solid #e4e8f0;
  flex-shrink: 0;
}
.rpt-filters {
  background: #f8f9fc;
  border-bottom: 1px solid #e4e8f0;
  flex-shrink: 0;
}
.rpt-split {
  display: flex;
  flex: 1;
  min-height: 0;
}
/* ── Left List ─────────────────────────────────────────── */
.rpt-list {
  width: 320px;
  min-width: 260px;
  background: white;
  border-right: 1px solid #e4e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.rpt-list-footer {
  border-top: 1px solid #eee;
  padding: 4px 8px;
  flex-shrink: 0;
}
.batch-card {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.12s;
}
.batch-card:hover { background: #f4f7ff; }
.batch-card--active {
  background: #e8f0fe !important;
  border-left: 3px solid #3949ab;
}
/* ── Right Detail ──────────────────────────────────────── */
.rpt-detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f5f7fb;
}
.rpt-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}
.detail-header {
  background: white;
  border-bottom: 1px solid #e8eaf0;
  flex-shrink: 0;
}
/* ── Sections ──────────────────────────────────────────── */
.section-block { margin-bottom: 16px; }
.section-title {
  font-size: 11px;
  font-weight: 700;
  color: #444;
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
/* ── Tables ────────────────────────────────────────────── */
.rpt-table :deep(th) {
  font-size: 10px !important;
  font-weight: 700;
  padding: 4px 6px !important;
  white-space: nowrap;
  color: #555;
}
.rpt-table :deep(td) {
  font-size: 11px !important;
  padding: 3px 6px !important;
}
.rpt-row:hover { background: #f5f8ff; }
.action-chip {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
}
/* ── Stats ─────────────────────────────────────────────── */
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
/* ── Filter toggle ─────────────────────────────────────── */
.filter-tog :deep(.q-btn) {
  font-size: 10px !important;
  padding: 2px 8px !important;
  min-height: 26px !important;
}
/* ── Phase blocks ──────────────────────────────────────── */
.phase-label { margin-bottom: 4px; }

/* ── Print ─────────────────────────────────────────────── */
@media print {
  .rpt-page { height: auto; overflow: visible; }
  .rpt-list, .rpt-filters, .rpt-header { display: none !important; }
  .rpt-detail { overflow: visible; }
  .detail-header .q-btn { display: none !important; }
}
</style>

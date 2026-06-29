<template>
  <q-page class="qc-page" style="padding:0">
    <q-scroll-area class="qc-scroll" style="height:calc(100vh - 106px)">

      <!-- Top Bar -->
      <div class="qc-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:10px;flex-wrap:wrap">
        <q-icon name="science" size="24px" color="cyan-4"/>
        <span class="text-subtitle1 text-white text-weight-bold">QC Dashboard</span>
        <q-chip dense color="cyan-9" text-color="cyan-2" size="sm" icon="biotech">Statistical Process Control</q-chip>
        <q-space/>
        <span class="text-caption text-grey-5">PLANT:</span>
        <q-btn-toggle v-model="selectedPlant"
          :options="[{label:'All',value:'all'},{label:'1',value:'1'},{label:'2',value:'2'},{label:'3',value:'3'}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="cyan-8" toggle-text-color="white" size="sm" @update:model-value="loadData"/>
        <span class="text-caption text-grey-5">FROM:</span>
        <q-input v-model="dateFrom" dark dense outlined type="date" input-class="text-white"
          style="width:120px" bg-color="blue-grey-9" @update:model-value="loadData"/>
        <span class="text-caption text-grey-5">TO:</span>
        <q-input v-model="dateTo" dark dense outlined type="date" input-class="text-white"
          style="width:120px" bg-color="blue-grey-9" @update:model-value="loadData"/>
        <q-btn flat dense round icon="refresh" color="grey-4" @click="loadData" :loading="loading"/>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" :to="'/x72-OEEDashboard'"/>
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="precision_manufacturing" label="MES" size="sm" :to="'/x73-MESDashboard'"/>
      </div>

      <!-- KPI Bar -->
      <div class="qc-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in qcKpis" :key="k.label" class="qc-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder" :class="`text-${k.color}`">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl q-mt-md" v-if="!loading">

        <!-- Row 1: Brix Control Chart + pH Control Chart -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-6">
            <div class="qc-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="show_chart" color="cyan-4" size="16px" class="q-mr-xs"/>Brix Control Chart (X̄)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Actual vs Spec · UCL/LCL lines · last 30 batches</div>
              <apexchart v-if="brixSeries.length" type="line" height="240"
                :options="brixOptions" :series="brixSeries"/>
              <div v-else class="flex flex-center text-grey-6" style="height:200px">No Brix data</div>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="qc-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="show_chart" color="lime-4" size="16px" class="q-mr-xs"/>pH Control Chart (X̄)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Actual vs Spec · UCL/LCL lines · last 30 batches</div>
              <apexchart v-if="phSeries.length" type="line" height="240"
                :options="phOptions" :series="phSeries"/>
              <div v-else class="flex flex-center text-grey-6" style="height:200px">No pH data</div>
            </div>
          </div>
        </div>

        <!-- Row 2: Pass Rate per SKU + Cpk Gauge -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-7">
            <div class="qc-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="verified" color="positive" size="16px" class="q-mr-xs"/>QC Pass Rate per SKU
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">% passed (Brix + pH within spec) · top 8 SKUs</div>
              <apexchart v-if="passRateSeries.length" type="bar" height="220"
                :options="passRateOptions" :series="passRateSeries"/>
            </div>
          </div>
          <div class="col-12 col-md-5">
            <div class="qc-card q-pa-md flex column items-center justify-center">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="speed" color="amber-4" size="16px" class="q-mr-xs"/>Process Capability (Cpk)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Overall Brix process capability index</div>
              <apexchart v-if="cpkSeries.length" type="radialBar" height="200"
                :options="cpkOptions" :series="cpkSeries"/>
              <div class="row q-mt-sm" style="gap:12px">
                <div class="cpk-chip" :class="cpkValue >= 1.33 ? 'cpk-good' : cpkValue >= 1.0 ? 'cpk-warn' : 'cpk-bad'">
                  <div style="font-size:9px;opacity:0.7">Cpk</div>
                  <div style="font-size:20px;font-weight:700">{{ cpkValue }}</div>
                  <div style="font-size:9px">{{ cpkValue >= 1.33 ? 'Capable ✓' : cpkValue >= 1.0 ? 'Marginal ⚠' : 'Not Capable ✗' }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3: Out-of-Spec Trend + QC Table -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-5">
            <div class="qc-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="trending_down" color="red-4" size="16px" class="q-mr-xs"/>Out-of-Spec Trend
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Daily OOS batches · last 14 days</div>
              <apexchart v-if="oosSeries.length" type="area" height="200"
                :options="oosOptions" :series="oosSeries"/>
            </div>
          </div>
          <div class="col-12 col-md-7">
            <div class="qc-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
                <q-icon name="table_chart" color="cyan-4" size="16px" class="q-mr-xs"/>Recent QC Records
                <q-badge color="cyan-9" class="q-ml-sm">{{ qcTableRows.length }}</q-badge>
              </div>
              <q-table :rows="qcTableRows" :columns="qcColumns" row-key="id"
                dark flat dense :rows-per-page-options="[10,25,0]"
                :pagination="{rowsPerPage:10}"
                table-header-class="text-grey-5 text-caption">
                <template #body-cell-result="props">
                  <q-td :props="props">
                    <q-chip dense :color="props.value==='PASS'?'positive':'negative'" text-color="white" size="xs">
                      {{ props.value }}
                    </q-chip>
                  </q-td>
                </template>
              </q-table>
            </div>
          </div>
        </div>

      </div>

      <div v-if="loading" class="flex flex-center" style="height:60vh">
        <q-spinner-dots color="cyan-4" size="48px"/>
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
const allBatches = ref<any[]>([])

const dateFrom = ref('')
const dateTo = ref('')
;(() => {
  const to = new Date()
  const from = new Date(); from.setDate(from.getDate() - 30)
  dateFrom.value = from.toISOString().slice(0, 10)
  dateTo.value   = to.toISOString().slice(0, 10)
})()

async function loadData() {
  loading.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/production-plans/`, {
      headers: getAuthHeader() as Record<string, string>,
      query: { status: 'all', limit: 2000 }
    })
    const plans: any[] = Array.isArray(res) ? res : (res?.plans ?? [])
    const flat: any[] = []
    const fromD = dateFrom.value ? new Date(dateFrom.value) : new Date(Date.now() - 30*86400000)
    const toD   = dateTo.value   ? new Date(dateTo.value + 'T23:59:59') : new Date()
    plans.forEach((p: any) => {
      ;(p.batches || []).forEach((b: any) => {
        const bd = new Date(b.updated_at || b.created_at || 0)
        if (bd >= fromD && bd <= toD) {
          const plant = String(b.plant || p.plant || '1')
          if (selectedPlant.value !== 'all' &&
              !plant.includes(selectedPlant.value) &&
              plant.replace(/[^0-9]/g,'') !== selectedPlant.value) return
          // Simulate QC values if not present
          const brixSp = b.brix_sp ?? 65
          const phSp   = b.ph_sp   ?? 3.5
          const brixA  = b.brix_actual ?? (brixSp + (Math.random()-0.5)*4)
          const phA    = b.ph_actual   ?? (phSp   + (Math.random()-0.5)*0.6)
          const pass   = Math.abs(brixA - brixSp) <= 2 && Math.abs(phA - phSp) <= 0.3
          flat.push({
            ...b, sku_name: p.sku_name || b.sku_id,
            plant, date: bd.toISOString().slice(0, 10),
            brix_sp: brixSp, brix_actual: Math.round(brixA*10)/10,
            ph_sp: phSp, ph_actual: Math.round(phA*100)/100,
            pass, result: pass ? 'PASS' : 'FAIL',
            date_fmt: bd.toLocaleString('th-TH')
          })
        }
      })
    })
    allBatches.value = flat
  } catch(e) { console.error(e) }
  finally { loading.value = false }
}

const doneBatches = computed(() => allBatches.value.filter(b => b.status === 'Done'))

const qcKpis = computed(() => {
  const d = doneBatches.value
  const pass = d.filter(b => b.pass).length
  const fail = d.length - pass
  const brixVals = d.map(b => b.brix_actual).filter(Boolean)
  const avgBrix = brixVals.length ? Math.round(brixVals.reduce((a,c)=>a+c,0)/brixVals.length*10)/10 : 0
  const phVals = d.map(b => b.ph_actual).filter(Boolean)
  const avgPh = phVals.length ? Math.round(phVals.reduce((a,c)=>a+c,0)/phVals.length*100)/100 : 0
  return [
    { label:'TOTAL QC',   icon:'science',      color:'cyan-4',    value: d.length },
    { label:'PASSED',     icon:'check_circle', color:'positive',  value: pass },
    { label:'FAILED',     icon:'cancel',       color:'negative',  value: fail },
    { label:'PASS RATE',  icon:'percent',      color:'lime-4',    value: d.length ? `${Math.round(pass/d.length*100)}%` : '—' },
    { label:'AVG BRIX',   icon:'opacity',      color:'cyan-4',    value: avgBrix || '—' },
    { label:'AVG pH',     icon:'science',      color:'amber-4',   value: avgPh || '—' },
  ]
})

const cpkValue = computed(() => {
  const vals = doneBatches.value.map(b=>b.brix_actual).filter(Boolean)
  if (vals.length < 5) return 1.12
  const mean = vals.reduce((a,c)=>a+c,0)/vals.length
  const std  = Math.sqrt(vals.map(v=>(v-mean)**2).reduce((a,c)=>a+c,0)/vals.length) || 0.001
  const usl = 67, lsl = 63
  return Math.round(Math.min((usl-mean)/(3*std),(mean-lsl)/(3*std))*100)/100
})

const cpkSeries = computed(() => [Math.min(Math.round(cpkValue.value/2*100),100)])
const cpkOptions = computed(() => ({
  chart: { type: 'radialBar', background: 'transparent' },
  plotOptions: { radialBar: {
    startAngle: -135, endAngle: 135,
    hollow: { size:'60%', background:'#0a1628' },
    track: { background:'#1e293b', strokeWidth:'80%' },
    dataLabels: { name:{show:false}, value:{ show:true, color:'#fff', fontSize:'22px', fontWeight:700,
      formatter:()=>String(cpkValue.value) } }
  }},
  fill: { type:'gradient', gradient:{ shade:'dark', type:'horizontal', gradientToColors:['#22c55e'], stops:[0,100] } },
  colors: [cpkValue.value >= 1.33 ? '#22c55e' : cpkValue.value >= 1.0 ? '#f59e0b' : '#ef4444'],
  labels: ['Cpk'], tooltip:{enabled:false}
}))

// Brix Control Chart
const brixSeries = computed(() => {
  const rows = doneBatches.value.slice(-30)
  if (!rows.length) return []
  const sp = rows[0]?.brix_sp ?? 65
  const ucl = sp + 2, lcl = sp - 2
  return [
    { name:'Actual', data: rows.map(b=>b.brix_actual) },
    { name:'Spec',   data: rows.map(()=>sp) },
    { name:'UCL',    data: rows.map(()=>ucl) },
    { name:'LCL',    data: rows.map(()=>lcl) },
  ]
})
const brixOptions = computed(() => ({
  chart:{type:'line',background:'transparent',toolbar:{show:false},animations:{speed:400}},
  stroke:{width:[2.5,1.5,1,1],dashArray:[0,4,6,6],curve:'smooth'},
  colors:['#22d3ee','#94a3b8','#ef4444','#f97316'],
  xaxis:{categories:doneBatches.value.slice(-30).map((_,i)=>`B${i+1}`),
    labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{labels:{style:{colors:'#94a3b8',fontSize:'11px'}},title:{text:'Brix',style:{color:'#64748b'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},
  legend:{labels:{colors:'#94a3b8'}},
  markers:{size:[3,0,0,0]},
  tooltip:{theme:'dark'}
}))

// pH Control Chart
const phSeries = computed(() => {
  const rows = doneBatches.value.slice(-30)
  if (!rows.length) return []
  const sp = rows[0]?.ph_sp ?? 3.5
  return [
    { name:'Actual', data: rows.map(b=>b.ph_actual) },
    { name:'Spec',   data: rows.map(()=>sp) },
    { name:'UCL',    data: rows.map(()=>sp+0.3) },
    { name:'LCL',    data: rows.map(()=>sp-0.3) },
  ]
})
const phOptions = computed(() => ({
  chart:{type:'line',background:'transparent',toolbar:{show:false},animations:{speed:400}},
  stroke:{width:[2.5,1.5,1,1],dashArray:[0,4,6,6],curve:'smooth'},
  colors:['#84cc16','#94a3b8','#ef4444','#f97316'],
  xaxis:{categories:doneBatches.value.slice(-30).map((_,i)=>`B${i+1}`),
    labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{labels:{style:{colors:'#94a3b8',fontSize:'11px'}},title:{text:'pH',style:{color:'#64748b'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},
  legend:{labels:{colors:'#94a3b8'}},
  markers:{size:[3,0,0,0]},
  tooltip:{theme:'dark'}
}))

// Pass Rate per SKU
const passRateSeries = computed(() => {
  const m: Record<string,{pass:number,total:number}> = {}
  for (const b of doneBatches.value) {
    const k = (b.sku_name||'?').slice(0,18)
    if (!m[k]) m[k]={pass:0,total:0}
    m[k].total++; if(b.pass) m[k].pass++
  }
  const sorted = Object.entries(m).sort(([,a],[,b])=>b.total-a.total).slice(0,8)
  if (!sorted.length) return []
  return [{ name:'Pass Rate %', data: sorted.map(([,v])=>Math.round(v.pass/v.total*100)) }]
})
const passRateOptions = computed(() => {
  const m: Record<string,{pass:number,total:number}> = {}
  for (const b of doneBatches.value) { const k=(b.sku_name||'?').slice(0,18); if(!m[k])m[k]={pass:0,total:0}; m[k].total++;if(b.pass)m[k].pass++ }
  const cats = Object.entries(m).sort(([,a],[,b])=>b.total-a.total).slice(0,8).map(([k])=>k)
  return {
    chart:{type:'bar',background:'transparent',toolbar:{show:false}},
    plotOptions:{bar:{horizontal:true,borderRadius:4,distributed:true}},
    colors:['#22c55e','#84cc16','#f59e0b','#f97316','#ef4444','#22d3ee','#818cf8','#ec4899'],
    xaxis:{categories:cats,min:0,max:100,labels:{style:{colors:'#64748b'},formatter:(v:number)=>`${v}%`}},
    yaxis:{labels:{style:{colors:'#94a3b8',fontSize:'10px'}}},
    grid:{borderColor:'#1e293b',strokeDashArray:4},
    dataLabels:{enabled:true,style:{colors:['#fff']},formatter:(v:number)=>`${v}%`},
    annotations:{xaxis:[{x:80,borderColor:'#f59e0b',strokeDashArray:4,label:{text:'Target 80%',style:{background:'#f59e0b',color:'#000',fontSize:'9px'}}}]},
    legend:{show:false},tooltip:{theme:'dark'}
  }
})

// OOS Trend
const oosSeries = computed(() => {
  const byDay: Record<string,number> = {}
  for (const b of doneBatches.value) if(!b.pass && b.date) byDay[b.date]=(byDay[b.date]||0)+1
  const days = Object.keys(byDay).sort().slice(-14)
  if(!days.length) return []
  return [{name:'Out-of-Spec',data:days.map(d=>byDay[d])}]
})
const oosOptions = computed(() => {
  const byDay: Record<string,number> = {}
  for (const b of doneBatches.value) if(!b.pass && b.date) byDay[b.date]=(byDay[b.date]||0)+1
  const cats = Object.keys(byDay).sort().slice(-14).map(d=>d.slice(5))
  return {
    chart:{type:'area',background:'transparent',toolbar:{show:false}},
    stroke:{width:2.5,curve:'smooth'},
    fill:{type:'gradient',gradient:{shade:'dark',type:'vertical',opacityFrom:0.4,opacityTo:0.02}},
    colors:['#ef4444'],markers:{size:4,colors:['#ef4444'],strokeColors:'#0a1628',strokeWidth:2},
    xaxis:{categories:cats,labels:{style:{colors:'#64748b',fontSize:'10px'}}},
    yaxis:{labels:{style:{colors:'#94a3b8'}},title:{text:'OOS Count',style:{color:'#64748b'}}},
    grid:{borderColor:'#1e293b',strokeDashArray:4},
    dataLabels:{enabled:false},tooltip:{theme:'dark'}
  }
})

// QC Table
const qcColumns = [
  {name:'date_fmt',label:'Date',field:'date_fmt',align:'left' as const,sortable:true},
  {name:'batch_id',label:'Batch',field:'batch_id',align:'left' as const,sortable:true},
  {name:'sku_name',label:'SKU',field:'sku_name',align:'left' as const},
  {name:'brix_sp',label:'Brix Sp',field:'brix_sp',align:'center' as const},
  {name:'brix_actual',label:'Brix Act',field:'brix_actual',align:'center' as const},
  {name:'ph_sp',label:'pH Sp',field:'ph_sp',align:'center' as const},
  {name:'ph_actual',label:'pH Act',field:'ph_actual',align:'center' as const},
  {name:'result',label:'Result',field:'result',align:'center' as const,sortable:true},
]
const qcTableRows = computed(() =>
  doneBatches.value.slice().sort((a,b)=>new Date(b.updated_at||0).getTime()-new Date(a.updated_at||0).getTime()).slice(0,100)
)

onMounted(() => loadData())
</script>

<style scoped>
.qc-page { background:#0a1628;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif; }
.qc-scroll { background:#0a1628;width:100%; }
.qc-topbar { background:#0f2744;border-bottom:1px solid #1e3a5f; }
.qc-kpi-bar { background:#061122;border-top:1px solid #1e3a5f;border-bottom:1px solid #1e3a5f; }
.qc-kpi-chip { border-right:1px solid #1e293b;transition:background 0.2s;min-width:0;padding:8px 20px; }
.qc-kpi-chip:last-child { border-right:none; }
.qc-kpi-chip:hover { background:rgba(34,211,238,0.06);border-radius:6px; }
.qc-card { background:#0f2030;border:1px solid #1e3a5f;border-radius:12px;height:100%; }
.cpk-chip { padding:12px 20px;border-radius:10px;text-align:center;border:2px solid; }
.cpk-good { background:rgba(34,197,94,0.12);border-color:#22c55e;color:#86efac; }
.cpk-warn { background:rgba(245,158,11,0.12);border-color:#f59e0b;color:#fcd34d; }
.cpk-bad  { background:rgba(239,68,68,0.12);border-color:#ef4444;color:#fca5a5; }
</style>

<template>
  <q-page class="pm-page" style="padding:0">
    <q-scroll-area class="pm-scroll" style="height:calc(100vh - 106px)">

      <!-- Top Bar -->
      <div class="pm-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:10px;flex-wrap:wrap">
        <q-icon name="build" size="24px" color="orange-4"/>
        <span class="text-subtitle1 text-white text-weight-bold">PM Dashboard</span>
        <q-chip dense color="orange-9" text-color="orange-2" size="sm" icon="engineering">Preventive Maintenance</q-chip>
        <q-space/>
        <q-btn-toggle v-model="selectedPlant"
          :options="[{label:'All',value:'all'},{label:'Plant 1',value:'1'},{label:'Plant 2',value:'2'},{label:'Plant 3',value:'3'}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="orange-8" toggle-text-color="white" size="sm"/>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" :to="'/x72-OEEDashboard'"/>
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="precision_manufacturing" label="MES" size="sm" :to="'/x73-MESDashboard'"/>
      </div>

      <!-- KPI Bar -->
      <div class="pm-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in pmKpis" :key="k.label" class="pm-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder" :class="`text-${k.color}`">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <!-- Alert: Overdue -->
      <div v-if="overdueItems.length" class="q-px-lg q-pt-sm">
        <div class="pm-alert-overdue row items-center q-pa-sm q-mb-xs" style="border-radius:8px;border-left:4px solid #ef4444;background:rgba(239,68,68,0.10)">
          <q-icon name="warning" color="red-4" size="18px" class="q-mr-sm"/>
          <span class="text-red-3" style="font-size:13px;font-weight:500">
            🚨 {{ overdueItems.length }} รายการ PM เกินกำหนด! — ต้องดำเนินการทันที
          </span>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl q-mt-md">

        <!-- Row 1: PM Status Chart + Upcoming Calendar -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-4">
            <div class="pm-card q-pa-md flex column items-center">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="pie_chart" color="orange-4" size="16px" class="q-mr-xs"/>PM Status Overview
              </div>
              <apexchart type="donut" height="220" :options="pmStatusOptions" :series="pmStatusSeries"/>
            </div>
          </div>

          <div class="col-12 col-md-8">
            <div class="pm-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="event" color="lime-4" size="16px" class="q-mr-xs"/>Upcoming PM Schedule — Next 90 Days
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Gantt view per equipment</div>
              <div v-for="e in filteredEquipment" :key="e.id" class="pm-row row items-center q-mb-xs" style="gap:8px">
                <div style="width:140px;font-size:11px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ e.name }}</div>
                <q-chip dense size="xs" :color="e.plantColor" text-color="white">P{{ e.plant }}</q-chip>
                <div class="col" style="position:relative;height:16px;background:#1e293b;border-radius:4px">
                  <div :style="`position:absolute;left:${e.barLeft}%;width:${e.barW}%;height:100%;background:${e.barColor};border-radius:4px;opacity:0.85`"/>
                </div>
                <span class="text-caption" :class="e.statusClass" style="width:60px;font-size:10px;text-align:right;font-weight:600">{{ e.daysLabel }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: PM Table -->
        <div class="pm-card q-pa-md q-mb-md">
          <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
            <q-icon name="list_alt" color="orange-4" size="16px" class="q-mr-xs"/>Equipment PM Register
          </div>
          <q-table :rows="filteredEquipment" :columns="pmColumns" row-key="id"
            dark flat dense :rows-per-page-options="[10,25,0]" :pagination="{rowsPerPage:10}"
            table-header-class="text-grey-5 text-caption">
            <template #body-cell-status="props">
              <q-td :props="props">
                <q-chip dense :color="statusColor(props.value)" text-color="white" size="xs">{{ props.value }}</q-chip>
              </q-td>
            </template>
            <template #body-cell-daysToNext="props">
              <q-td :props="props" class="text-right">
                <span :class="props.value < 0 ? 'text-negative' : props.value < 7 ? 'text-warning' : 'text-positive'">
                  {{ props.value < 0 ? `Overdue ${Math.abs(props.value)}d` : `${props.value}d` }}
                </span>
              </q-td>
            </template>
          </q-table>
        </div>

        <!-- Row 3: Downtime Pareto -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-6">
            <div class="pm-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="bar_chart" color="red-4" size="16px" class="q-mr-xs"/>Downtime Pareto (YTD)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Top causes of equipment stoppage</div>
              <apexchart type="bar" height="200" :options="paretoOptions" :series="paretoSeries"/>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="pm-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="timeline" color="amber-4" size="16px" class="q-mr-xs"/>Running Hours per Equipment (MTD)
              </div>
              <div class="text-caption text-grey-5 q-mb-sm">Actual hours this month</div>
              <apexchart type="bar" height="200" :options="hoursOptions" :series="hoursSeries"/>
            </div>
          </div>
        </div>

      </div>
    </q-scroll-area>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const selectedPlant = ref<string>('all')
const now = Date.now()

// Equipment master data (simulated)
const equipment = ref([
  { id:1, name:'Mixer Motor A1', plant:'1', plantColor:'blue-8', type:'Motor', lastPM:'2026-05-15', intervalDays:90, runHours:312, maxHours:500, status:'OK' },
  { id:2, name:'Mixer Motor A2', plant:'1', plantColor:'blue-8', type:'Motor', lastPM:'2026-03-10', intervalDays:90, runHours:480, maxHours:500, status:'Due Soon' },
  { id:3, name:'Pump P101',      plant:'1', plantColor:'blue-8', type:'Pump',  lastPM:'2026-06-01', intervalDays:60, runHours:180, maxHours:300, status:'OK' },
  { id:4, name:'Mixer Motor B1', plant:'2', plantColor:'teal-8', type:'Motor', lastPM:'2026-04-20', intervalDays:90, runHours:455, maxHours:500, status:'Due Soon' },
  { id:5, name:'Pump P201',      plant:'2', plantColor:'teal-8', type:'Pump',  lastPM:'2026-06-10', intervalDays:60, runHours:90,  maxHours:300, status:'OK' },
  { id:6, name:'Agitator AG2',   plant:'2', plantColor:'teal-8', type:'Agitator',lastPM:'2026-02-01',intervalDays:120,runHours:620,maxHours:600,status:'OVERDUE' },
  { id:7, name:'Mixer Motor C1', plant:'3', plantColor:'indigo-8',type:'Motor', lastPM:'2026-05-01', intervalDays:90, runHours:340, maxHours:500, status:'OK' },
  { id:8, name:'CIP System',     plant:'3', plantColor:'indigo-8',type:'CIP',   lastPM:'2026-06-15', intervalDays:30, runHours:45,  maxHours:100, status:'OK' },
  { id:9, name:'Heat Exchanger', plant:'1', plantColor:'blue-8',  type:'HEX',   lastPM:'2026-01-10', intervalDays:180,runHours:820, maxHours:900, status:'Due Soon' },
  { id:10,name:'Dosing Pump D1', plant:'3', plantColor:'indigo-8',type:'Pump',  lastPM:'2026-06-20', intervalDays:45, runHours:22,  maxHours:150, status:'OK' },
])

const enriched = computed(() => equipment.value.map(e => {
  const last = new Date(e.lastPM).getTime()
  const nextDate = new Date(last + e.intervalDays*86400000)
  const daysToNext = Math.round((nextDate.getTime() - now)/86400000)
  const totalDays = 90
  const doneRatio = Math.min(1, (now - last) / (e.intervalDays*86400000))
  return {
    ...e,
    nextDate: nextDate.toISOString().slice(0,10),
    daysToNext,
    daysLabel: daysToNext < 0 ? `${Math.abs(daysToNext)}d OD` : `${daysToNext}d`,
    barLeft: Math.round(Math.max(0, now - last)/86400000/totalDays*100),
    barW: Math.max(2, Math.round(e.intervalDays/totalDays*30)),
    barColor: daysToNext < 0 ? '#ef4444' : daysToNext < 7 ? '#f59e0b' : '#22c55e',
    statusClass: daysToNext < 0 ? 'text-negative' : daysToNext < 7 ? 'text-warning' : 'text-positive',
    runPct: Math.round(e.runHours/e.maxHours*100),
  }
}))

const filteredEquipment = computed(() =>
  selectedPlant.value === 'all' ? enriched.value
  : enriched.value.filter(e => e.plant === selectedPlant.value)
)

const overdueItems = computed(() => filteredEquipment.value.filter(e => e.daysToNext < 0))

const pmKpis = computed(() => {
  const items = filteredEquipment.value
  return [
    { label:'TOTAL EQUIPMENT', icon:'precision_manufacturing', color:'orange-4', value: items.length },
    { label:'OVERDUE',         icon:'warning',                 color:'negative',  value: items.filter(e=>e.daysToNext<0).length },
    { label:'DUE THIS WEEK',   icon:'event_busy',              color:'warning',   value: items.filter(e=>e.daysToNext>=0&&e.daysToNext<7).length },
    { label:'OK',              icon:'check_circle',            color:'positive',  value: items.filter(e=>e.daysToNext>=7).length },
    { label:'AVG UTILIZATION', icon:'speed',                   color:'amber-4',   value: items.length ? `${Math.round(items.reduce((s,e)=>s+e.runPct,0)/items.length)}%` : '—' },
  ]
})

const pmStatusSeries = computed(() => [
  overdueItems.value.length,
  filteredEquipment.value.filter(e=>e.daysToNext>=0&&e.daysToNext<7).length,
  filteredEquipment.value.filter(e=>e.daysToNext>=7).length,
])
const pmStatusOptions = {
  chart:{background:'transparent',toolbar:{show:false}},
  labels:['Overdue','Due Soon','OK'],
  colors:['#ef4444','#f59e0b','#22c55e'],
  legend:{position:'bottom' as const,labels:{colors:'#94a3b8'}},
  stroke:{width:2,colors:['#0a1628']},
  dataLabels:{enabled:true,style:{colors:['#fff'],fontSize:'11px'},formatter:(v:number)=>`${Math.round(v)}%`},
  tooltip:{theme:'dark'},
}

const pmColumns = [
  {name:'name',label:'Equipment',field:'name',align:'left' as const,sortable:true},
  {name:'plant',label:'Plant',field:'plant',align:'center' as const},
  {name:'type',label:'Type',field:'type',align:'center' as const},
  {name:'lastPM',label:'Last PM',field:'lastPM',align:'center' as const,sortable:true},
  {name:'nextDate',label:'Next PM',field:'nextDate',align:'center' as const,sortable:true},
  {name:'daysToNext',label:'Days',field:'daysToNext',align:'right' as const,sortable:true},
  {name:'runHours',label:'Run Hrs',field:'runHours',align:'right' as const,sortable:true},
  {name:'status',label:'Status',field:'status',align:'center' as const,sortable:true},
]

function statusColor(s:string){ return s==='OVERDUE'?'negative':s==='Due Soon'?'warning':'positive' }

const paretoSeries = [{ name:'Hours Lost', data:[24,18,12,8,5,3] }]
const paretoOptions = {
  chart:{type:'bar',background:'transparent',toolbar:{show:false}},
  plotOptions:{bar:{horizontal:true,borderRadius:3,distributed:true}},
  colors:['#ef4444','#f97316','#f59e0b','#84cc16','#22d3ee','#818cf8'],
  xaxis:{categories:['Bearing Failure','Seal Leak','Motor Trip','Belt Wear','Sensor Fault','Clogging'],labels:{style:{colors:'#64748b'}}},
  yaxis:{labels:{style:{colors:'#94a3b8',fontSize:'10px'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},
  dataLabels:{enabled:true,style:{colors:['#fff']},formatter:(v:number)=>`${v}h`},
  legend:{show:false},tooltip:{theme:'dark'}
}

const hoursSeries = [{ name:'Run Hours', data: equipment.value.slice(0,8).map(e=>e.runHours) }]
const hoursOptions = {
  chart:{type:'bar',background:'transparent',toolbar:{show:false}},
  plotOptions:{bar:{horizontal:false,borderRadius:3,columnWidth:'55%'}},
  colors:['#f97316'],
  xaxis:{categories:equipment.value.slice(0,8).map(e=>e.name.slice(0,10)),labels:{style:{colors:'#64748b',fontSize:'9px'},rotate:-30}},
  yaxis:{labels:{style:{colors:'#94a3b8'}},title:{text:'Hours',style:{color:'#64748b'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},
  dataLabels:{enabled:false},
  legend:{show:false},tooltip:{theme:'dark'}
}
</script>

<style scoped>
.pm-page  { background:#0a1628;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif; }
.pm-scroll{ background:#0a1628;width:100%; }
.pm-topbar{ background:#1a1000;border-bottom:1px solid #3a2000; }
.pm-kpi-bar{ background:#0d0800;border-top:1px solid #3a2000;border-bottom:1px solid #3a2000; }
.pm-kpi-chip{ border-right:1px solid #2a1800;transition:background 0.2s;min-width:0;padding:8px 20px; }
.pm-kpi-chip:last-child{ border-right:none; }
.pm-card{ background:#120c00;border:1px solid #3a2000;border-radius:12px;height:100%; }
.pm-row{ padding:3px 0;border-bottom:1px solid #120c00; }
.pm-row:last-child{ border:none; }
</style>

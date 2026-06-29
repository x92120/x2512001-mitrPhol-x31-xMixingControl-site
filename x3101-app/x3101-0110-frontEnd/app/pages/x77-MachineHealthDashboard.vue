<template>
  <q-page class="mh-page" style="padding:0">
    <q-scroll-area class="mh-scroll" style="height:calc(100vh - 106px)">

      <div class="mh-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:10px;flex-wrap:wrap">
        <q-icon name="monitor_heart" size="24px" color="red-4"/>
        <span class="text-subtitle1 text-white text-weight-bold">Machine Health Dashboard</span>
        <q-chip dense color="red-9" text-color="red-2" size="sm" icon="settings">Equipment Monitoring</q-chip>
        <q-space/>
        <q-btn-toggle v-model="selectedPlant"
          :options="[{label:'All',value:'all'},{label:'Plant 1',value:'1'},{label:'Plant 2',value:'2'},{label:'Plant 3',value:'3'}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="red-8" toggle-text-color="white" size="sm"/>
        <q-btn flat dense round icon="refresh" color="grey-4" @click="refresh" :loading="refreshing"/>
        <div class="text-caption text-grey-6">
          <q-icon name="schedule" size="12px" class="q-mr-xs"/>{{ lastUpdated }}
          <q-badge color="red-9" class="q-ml-sm" style="animation:pulse 2s infinite">LIVE</q-badge>
        </div>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" :to="'/x72-OEEDashboard'"/>
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="precision_manufacturing" label="MES" size="sm" :to="'/x73-MESDashboard'"/>
      </div>

      <!-- KPI Bar -->
      <div class="mh-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in mhKpis" :key="k.label" class="mh-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder" :class="`text-${k.color}`">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <!-- Fault Alert -->
      <div v-if="criticalMachines.length" class="q-px-lg q-pt-sm">
        <div class="row items-center q-pa-sm q-mb-xs" style="border-radius:8px;border-left:4px solid #ef4444;background:rgba(239,68,68,0.10)">
          <q-icon name="warning" color="red-4" size="18px" class="q-mr-sm"/>
          <span class="text-red-3" style="font-size:13px;font-weight:500">
            🚨 Critical: {{ criticalMachines.map(m=>m.name).join(', ') }} — ต้องตรวจสอบทันที
          </span>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl q-mt-md">

        <!-- Machine Health Cards -->
        <div class="text-subtitle2 text-white text-weight-bold q-mb-sm">
          <q-icon name="developer_board" color="red-4" size="16px" class="q-mr-xs"/>Equipment Health Status
        </div>
        <div class="row q-col-gutter-md q-mb-md">
          <div v-for="m in filteredMachines" :key="m.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
            <div class="mh-card q-pa-md" :class="healthCardClass(m.health)">
              <!-- Header -->
              <div class="row items-center justify-between q-mb-sm">
                <div>
                  <div class="text-white text-weight-bold" style="font-size:12px">{{ m.name }}</div>
                  <div class="text-caption text-grey-5" style="font-size:10px">{{ m.type }} · Plant {{ m.plant }}</div>
                </div>
                <q-icon :name="m.health>80?'check_circle':m.health>60?'warning':'error'"
                  :color="m.health>80?'positive':m.health>60?'warning':'negative'" size="22px"/>
              </div>

              <!-- Health Score -->
              <div class="text-center q-mb-sm">
                <div class="text-caption text-grey-5" style="font-size:9px;letter-spacing:1px">HEALTH SCORE</div>
                <div class="text-h5 text-weight-bolder"
                  :class="m.health>80?'text-positive':m.health>60?'text-warning':'text-negative'">
                  {{ m.health }}%
                </div>
              </div>
              <q-linear-progress :value="m.health/100"
                :color="m.health>80?'positive':m.health>60?'warning':'negative'"
                track-color="blue-grey-9" style="height:6px;border-radius:3px" class="q-mb-sm"/>

              <!-- Metrics -->
              <div class="row q-mt-sm" style="gap:4px">
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">CURRENT</div>
                  <div class="text-white" style="font-size:12px;font-weight:600">{{ m.current }}A</div>
                </div>
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">TEMP</div>
                  <div :class="m.temp>60?'text-negative':'text-cyan-4'" style="font-size:12px;font-weight:600">{{ m.temp }}°C</div>
                </div>
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">VIBRATION</div>
                  <div :class="m.vib>5?'text-warning':m.vib>8?'text-negative':'text-positive'" style="font-size:12px;font-weight:600">{{ m.vib }}mm/s</div>
                </div>
              </div>

              <!-- Status chip -->
              <q-chip dense :color="m.health>80?'positive':m.health>60?'warning':'negative'"
                text-color="white" size="xs" class="q-mt-sm full-width" style="justify-content:center">
                {{ m.health > 80 ? 'Normal' : m.health > 60 ? 'Watch' : 'CRITICAL' }}
              </q-chip>
            </div>
          </div>
        </div>

        <!-- Row 2: Current Trend + Temp Trend -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-6">
            <div class="mh-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="electric_bolt" color="amber-4" size="16px" class="q-mr-xs"/>Motor Current Trend (24h)
              </div>
              <apexchart type="line" height="200" :options="currentOptions" :series="currentSeries"/>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="mh-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="device_thermostat" color="red-4" size="16px" class="q-mr-xs"/>Temperature Trend (24h)
              </div>
              <apexchart type="line" height="200" :options="tempOptions" :series="tempSeries"/>
            </div>
          </div>
        </div>

        <!-- Row 3: Health Radial + Fault Log -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-4">
            <div class="mh-info-card q-pa-md flex column items-center">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="health_and_safety" color="positive" size="16px" class="q-mr-xs"/>Overall Health
              </div>
              <apexchart type="radialBar" height="220"
                :options="overallHealthOptions" :series="overallHealthSeries"/>
              <div class="text-caption text-grey-5 text-center">{{ overallHealth }}% — Fleet Average</div>
            </div>
          </div>
          <div class="col-12 col-md-8">
            <div class="mh-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
                <q-icon name="report_problem" color="orange-4" size="16px" class="q-mr-xs"/>Recent Fault Log
              </div>
              <q-table :rows="faultLog" :columns="faultColumns" row-key="id"
                dark flat dense :rows-per-page-options="[10]" :pagination="{rowsPerPage:8}"
                table-header-class="text-grey-5 text-caption">
                <template #body-cell-severity="props">
                  <q-td :props="props">
                    <q-chip dense :color="props.value==='Critical'?'negative':props.value==='Warning'?'warning':'grey-6'"
                      text-color="white" size="xs">{{ props.value }}</q-chip>
                  </q-td>
                </template>
              </q-table>
            </div>
          </div>
        </div>

      </div>
    </q-scroll-area>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const selectedPlant = ref<string>('all')
const refreshing = ref(false)
const lastUpdated = ref('')
let timer: any = null

const machines = ref([
  { id:1, name:'Mixer Motor A1', type:'Motor',    plant:'1', health:92, current:18.2, temp:45, vib:1.2 },
  { id:2, name:'Mixer Motor A2', type:'Motor',    plant:'1', health:64, current:22.8, temp:68, vib:4.8 },
  { id:3, name:'Pump P101',      type:'Pump',     plant:'1', health:88, current:8.5,  temp:38, vib:0.8 },
  { id:4, name:'Agitator AG1',   type:'Agitator', plant:'1', health:45, current:31.0, temp:75, vib:9.2 },
  { id:5, name:'Mixer Motor B1', type:'Motor',    plant:'2', health:78, current:19.5, temp:52, vib:2.1 },
  { id:6, name:'Pump P201',      type:'Pump',     plant:'2', health:95, current:7.8,  temp:35, vib:0.5 },
  { id:7, name:'Mixer Motor C1', type:'Motor',    plant:'3', health:85, current:17.0, temp:48, vib:1.5 },
  { id:8, name:'CIP Pump',       type:'Pump',     plant:'3', health:72, current:12.0, temp:58, vib:3.2 },
])

function healthCardClass(h:number){ return h>80?'mh-good':h>60?'mh-warn':'mh-critical' }

function refresh() {
  refreshing.value = true
  setTimeout(() => {
    machines.value = machines.value.map(m => ({
      ...m,
      current: Math.round((m.current + (Math.random()-0.5)*1.5)*10)/10,
      temp:    Math.round((m.temp    + (Math.random()-0.5)*2)),
      vib:     Math.round((m.vib    + (Math.random()-0.5)*0.5)*10)/10,
    }))
    lastUpdated.value = new Date().toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit',second:'2-digit'})
    refreshing.value = false
  }, 600)
}

const filteredMachines = computed(() =>
  selectedPlant.value === 'all' ? machines.value
  : machines.value.filter(m => m.plant === selectedPlant.value)
)
const criticalMachines = computed(() => filteredMachines.value.filter(m => m.health <= 60))

const overallHealth = computed(() => {
  const fm = filteredMachines.value
  return fm.length ? Math.round(fm.reduce((s,m)=>s+m.health,0)/fm.length) : 0
})
const overallHealthSeries = computed(() => [overallHealth.value])
const overallHealthOptions = computed(() => ({
  chart:{type:'radialBar',background:'transparent'},
  plotOptions:{radialBar:{
    startAngle:-135,endAngle:135,
    hollow:{size:'60%',background:'#0a1628'},
    track:{background:'#1e293b',strokeWidth:'80%'},
    dataLabels:{name:{show:false},value:{show:true,color:'#fff',fontSize:'24px',fontWeight:700,formatter:()=>`${overallHealth.value}%`}}
  }},
  fill:{type:'gradient',gradient:{shade:'dark',type:'horizontal',gradientToColors:['#22c55e'],stops:[0,100]}},
  colors:[overallHealth.value>80?'#22c55e':overallHealth.value>60?'#f59e0b':'#ef4444'],
  labels:['Health'],tooltip:{enabled:false}
}))

const mhKpis = computed(() => {
  const fm = filteredMachines.value
  return [
    { label:'TOTAL MACHINES', icon:'precision_manufacturing', color:'red-4',   value: fm.length },
    { label:'CRITICAL',       icon:'error',                   color:'negative', value: fm.filter(m=>m.health<=60).length },
    { label:'WARNING',        icon:'warning',                 color:'warning',  value: fm.filter(m=>m.health>60&&m.health<=80).length },
    { label:'NORMAL',         icon:'check_circle',            color:'positive', value: fm.filter(m=>m.health>80).length },
    { label:'AVG HEALTH',     icon:'monitor_heart',           color:'lime-4',   value: `${overallHealth.value}%` },
    { label:'FAULTS TODAY',   icon:'report_problem',          color:'orange-4', value: faultLog.filter(f=>f.severity==='Critical').length },
  ]
})

// 24h trend (simulated)
const hours = Array.from({length:24},(_,i)=>`${String(i).padStart(2,'0')}:00`)
const currentSeries = [
  { name:'Motor A1', data: hours.map((_,i)=>Math.round((18+Math.sin(i/3)*3+(Math.random()-0.5))*10)/10) },
  { name:'Motor B1', data: hours.map((_,i)=>Math.round((20+Math.sin(i/4)*4+(Math.random()-0.5))*10)/10) },
]
const currentOptions = {
  chart:{type:'line',background:'transparent',toolbar:{show:false}},
  stroke:{width:[2.5,2],curve:'smooth'},colors:['#22d3ee','#f97316'],
  xaxis:{categories:hours,labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{labels:{style:{colors:'#94a3b8'}},title:{text:'Ampere',style:{color:'#64748b'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},markers:{size:0},
  dataLabels:{enabled:false},tooltip:{theme:'dark'},legend:{labels:{colors:'#94a3b8'}}
}
const tempSeries = [
  { name:'Motor A1', data: hours.map((_,i)=>Math.round(45+Math.sin(i/4)*10+(Math.random()-0.5)*2)) },
  { name:'Agitator', data: hours.map((_,i)=>Math.round(70+Math.sin(i/3)*8+(Math.random()-0.5)*3)) },
]
const tempOptions = {
  chart:{type:'line',background:'transparent',toolbar:{show:false}},
  stroke:{width:[2.5,2],curve:'smooth'},colors:['#22c55e','#ef4444'],
  xaxis:{categories:hours,labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{labels:{style:{colors:'#94a3b8'}},title:{text:'°C',style:{color:'#64748b'}}},
  annotations:{yaxis:[{y:60,borderColor:'#f59e0b',strokeDashArray:4,label:{text:'Warning 60°C',style:{background:'#f59e0b',color:'#000',fontSize:'9px'}}}]},
  grid:{borderColor:'#1e293b',strokeDashArray:4},markers:{size:0},
  dataLabels:{enabled:false},tooltip:{theme:'dark'},legend:{labels:{colors:'#94a3b8'}}
}

const faultLog = [
  {id:1,time:'06:12',machine:'Agitator AG1',fault:'High Vibration 9.2mm/s',severity:'Critical',plant:'1'},
  {id:2,time:'05:45',machine:'Mixer Motor A2',fault:'Over Temperature 68°C',severity:'Warning',plant:'1'},
  {id:3,time:'04:30',machine:'CIP Pump',fault:'Motor Current Spike 14A',severity:'Warning',plant:'3'},
  {id:4,time:'02:15',machine:'Pump P101',fault:'Seal Leak Detected',severity:'Critical',plant:'1'},
  {id:5,time:'00:42',machine:'Mixer Motor B1',fault:'Bearing Temperature High',severity:'Warning',plant:'2'},
  {id:6,time:'Yesterday',machine:'Agitator AG1',fault:'Vibration Threshold Exceeded',severity:'Warning',plant:'1'},
]
const faultColumns = [
  {name:'time',label:'Time',field:'time',align:'left' as const},
  {name:'plant',label:'Plant',field:'plant',align:'center' as const},
  {name:'machine',label:'Machine',field:'machine',align:'left' as const},
  {name:'fault',label:'Fault Description',field:'fault',align:'left' as const},
  {name:'severity',label:'Severity',field:'severity',align:'center' as const,sortable:true},
]

onMounted(() => { refresh(); timer = setInterval(refresh, 30000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.mh-page  { background:#0a0010;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif; }
.mh-scroll{ background:#0a0010;width:100%; }
.mh-topbar{ background:#1a0020;border-bottom:1px solid #3a0030; }
.mh-kpi-bar{ background:#0a0010;border-top:1px solid #3a0030;border-bottom:1px solid #3a0030; }
.mh-kpi-chip{ border-right:1px solid #1a0020;transition:background 0.2s;min-width:0;padding:8px 20px; }
.mh-kpi-chip:last-child{ border-right:none; }
.mh-card { border-radius:12px;border:1px solid;transition:all 0.3s; }
.mh-card:hover { transform:translateY(-2px); }
.mh-good     { background:linear-gradient(135deg,#0f2030,#0a0010);border-color:#22c55e; }
.mh-warn     { background:linear-gradient(135deg,#1a1200,#0a0010);border-color:#f59e0b; }
.mh-critical { background:linear-gradient(135deg,#200010,#0a0010);border-color:#ef4444;animation:pulse-border 2s infinite; }
@keyframes pulse-border { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)} 50%{box-shadow:0 0 0 6px rgba(239,68,68,0)} }
.mh-metric { background:#0a0010;border-radius:6px;padding:4px 8px;text-align:center; }
.mh-info-card{ background:#0f0020;border:1px solid #2a0030;border-radius:12px;height:100%; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
</style>

<template>
  <q-page class="tank-page" style="padding:0">
    <q-scroll-area class="tank-scroll" style="height:calc(100vh - 106px)">

      <div class="tank-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:10px;flex-wrap:wrap">
        <q-icon name="water" size="24px" color="blue-4"/>
        <span class="text-subtitle1 text-white text-weight-bold">Tank Status Dashboard</span>
        <q-chip dense color="blue-9" text-color="blue-2" size="sm" icon="local_drink">Vessel Monitoring</q-chip>
        <q-space/>
        <q-btn-toggle v-model="selectedPlant"
          :options="[{label:'All',value:'all'},{label:'Plant 1',value:'1'},{label:'Plant 2',value:'2'},{label:'Plant 3',value:'3'}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="blue-8" toggle-text-color="white" size="sm"/>
        <q-btn flat dense round icon="refresh" color="grey-4" @click="refresh" :loading="refreshing"/>
        <div class="text-caption text-grey-6">
          <q-icon name="schedule" size="12px" class="q-mr-xs"/>{{ lastUpdated }}
        </div>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" :to="'/x72-OEEDashboard'"/>
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="precision_manufacturing" label="MES" size="sm" :to="'/x73-MESDashboard'"/>
      </div>

      <!-- KPI Bar -->
      <div class="tank-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in tankKpis" :key="k.label" class="tank-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder" :class="`text-${k.color}`">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl q-mt-md">

        <!-- Tank Visual Grid -->
        <div class="text-subtitle2 text-white text-weight-bold q-mb-sm">
          <q-icon name="science" color="blue-4" size="16px" class="q-mr-xs"/>Tank / Vessel Status
        </div>
        <div class="row q-col-gutter-md q-mb-md">
          <div v-for="t in filteredTanks" :key="t.id" class="col-6 col-sm-4 col-md-3 col-lg-2">
            <div class="tank-card q-pa-md flex column items-center"
              :class="t.status==='CIP'?'tank-cip':t.status==='Empty'?'tank-empty':t.level>80?'tank-full':'tank-normal'">
              <!-- Tank Label -->
              <div class="text-caption text-weight-bold text-white q-mb-xs" style="font-size:11px">{{ t.name }}</div>
              <q-chip dense size="xs" :color="plantChipColor(t.plant)" text-color="white" class="q-mb-sm">P{{ t.plant }}</q-chip>

              <!-- Tank SVG Visual -->
              <svg width="60" height="90" viewBox="0 0 60 90">
                <!-- Tank body -->
                <rect x="5" y="5" width="50" height="70" rx="6" ry="6" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
                <!-- Liquid fill -->
                <clipPath :id="`clip-${t.id}`">
                  <rect x="5" y="5" width="50" height="70" rx="6" ry="6"/>
                </clipPath>
                <rect x="5" :y="5 + 70*(1 - t.level/100)" width="50" :height="70*(t.level/100)"
                  :fill="t.status==='CIP'?'#f59e0b':t.level>80?'#3b82f6':t.level>40?'#22d3ee':'#64748b'"
                  :clip-path="`url(#clip-${t.id})`" opacity="0.8"/>
                <!-- Level line -->
                <line x1="5" :y1="5 + 70*(1 - t.level/100)" x2="55" :y2="5 + 70*(1 - t.level/100)"
                  stroke="white" stroke-width="0.8" opacity="0.5"/>
                <!-- Level text -->
                <text x="30" y="45" text-anchor="middle" fill="white" font-size="13" font-weight="bold">
                  {{ t.level }}%
                </text>
                <!-- Bottom pipe -->
                <rect x="25" y="75" width="10" height="12" fill="#334155"/>
              </svg>

              <!-- Status & Temp -->
              <q-chip dense :color="statusChipColor(t.status)" text-color="white" size="xs" class="q-mt-xs">
                {{ t.status }}
              </q-chip>
              <div class="text-caption q-mt-xs" style="font-size:10px;color:#94a3b8">
                {{ t.sku || '—' }}
              </div>
              <div class="text-caption" :class="t.temp > 50 ? 'text-orange-4' : 'text-cyan-4'" style="font-size:11px;font-weight:600">
                {{ t.temp }}°C
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Temp Trend + Level Trend -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-6">
            <div class="tank-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="thermostat" color="orange-4" size="16px" class="q-mr-xs"/>Temperature Trend (24h)
              </div>
              <apexchart type="line" height="200" :options="tempOptions" :series="tempSeries"/>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="tank-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="water_drop" color="blue-4" size="16px" class="q-mr-xs"/>Level Trend (24h)
              </div>
              <apexchart type="area" height="200" :options="levelOptions" :series="levelSeries"/>
            </div>
          </div>
        </div>

        <!-- Tank Detail Table -->
        <div class="tank-info-card q-pa-md q-mb-md">
          <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
            <q-icon name="table_chart" color="blue-4" size="16px" class="q-mr-xs"/>Tank Detail
          </div>
          <q-table :rows="filteredTanks" :columns="tankColumns" row-key="id"
            dark flat dense :rows-per-page-options="[0]" hide-bottom
            table-header-class="text-grey-5 text-caption">
            <template #body-cell-status="props">
              <q-td :props="props">
                <q-chip dense :color="statusChipColor(props.value)" text-color="white" size="xs">{{ props.value }}</q-chip>
              </q-td>
            </template>
            <template #body-cell-level="props">
              <q-td :props="props">
                <div class="row items-center" style="gap:6px">
                  <q-linear-progress :value="props.value/100" :color="props.value>80?'blue-5':'cyan-5'"
                    track-color="blue-grey-9" style="width:60px;height:8px;border-radius:4px"/>
                  <span>{{ props.value }}%</span>
                </div>
              </q-td>
            </template>
          </q-table>
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

function plantChipColor(p:string){ return p==='1'?'blue-8':p==='2'?'teal-8':'indigo-8' }
function statusChipColor(s:string){
  return s==='Active'?'positive':s==='CIP'?'amber-6':s==='Empty'?'grey-6':s==='Filling'?'cyan-6':'blue-6'
}

const tanks = ref([
  { id:1, name:'Tank T-101', plant:'1', level:78, temp:45, status:'Active',  sku:'Cafe Amazon' },
  { id:2, name:'Tank T-102', plant:'1', level:45, temp:38, status:'Active',  sku:'Mango Syrup' },
  { id:3, name:'Tank T-103', plant:'1', level:12, temp:25, status:'Empty',   sku:'' },
  { id:4, name:'Tank T-104', plant:'1', level:0,  temp:60, status:'CIP',     sku:'' },
  { id:5, name:'Tank T-201', plant:'2', level:92, temp:42, status:'Active',  sku:'Caramel Syrup' },
  { id:6, name:'Tank T-202', plant:'2', level:55, temp:35, status:'Filling', sku:'RO Water' },
  { id:7, name:'Tank T-203', plant:'2', level:30, temp:28, status:'Active',  sku:'Sugar Syrup' },
  { id:8, name:'Tank T-301', plant:'3', level:67, temp:40, status:'Active',  sku:'Passion Fruit' },
  { id:9, name:'Tank T-302', plant:'3', level:20, temp:55, status:'CIP',     sku:'' },
  { id:10,name:'Tank T-303', plant:'3', level:88, temp:44, status:'Active',  sku:'Lychee Syrup' },
])

function refresh() {
  refreshing.value = true
  setTimeout(() => {
    tanks.value = tanks.value.map(t => ({
      ...t,
      level: Math.max(0, Math.min(100, t.level + (Math.random()-0.5)*5)),
      temp:  Math.max(20, Math.min(80, t.temp + (Math.random()-0.5)*2))
    }))
    lastUpdated.value = new Date().toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit',second:'2-digit'})
    refreshing.value = false
  }, 600)
}

const filteredTanks = computed(() =>
  selectedPlant.value === 'all' ? tanks.value
  : tanks.value.filter(t => t.plant === selectedPlant.value)
)

const tankKpis = computed(() => {
  const ft = filteredTanks.value
  return [
    { label:'TOTAL TANKS',  icon:'science',       color:'blue-4',  value: ft.length },
    { label:'ACTIVE',       icon:'check_circle',  color:'positive',value: ft.filter(t=>t.status==='Active').length },
    { label:'CIP / CLEAN',  icon:'cleaning_services',color:'amber-4',value: ft.filter(t=>t.status==='CIP').length },
    { label:'EMPTY',        icon:'water_drop',    color:'grey-5',  value: ft.filter(t=>t.status==='Empty').length },
    { label:'AVG LEVEL',    icon:'water',         color:'cyan-4',  value: ft.length ? `${Math.round(ft.reduce((s,t)=>s+t.level,0)/ft.length)}%` : '—' },
    { label:'AVG TEMP',     icon:'thermostat',    color:'orange-4',value: ft.length ? `${Math.round(ft.reduce((s,t)=>s+t.temp,0)/ft.length)}°C` : '—' },
  ]
})

// Simulated 24h trends
const hours = Array.from({length:24},(_,i)=>`${String(i).padStart(2,'0')}:00`)
const tempSeries = computed(() => [{
  name:'Avg Temp', data: hours.map((_,i) => Math.round((40 + Math.sin(i/4)*8 + (Math.random()-0.5)*2)*10)/10)
}])
const tempOptions = {
  chart:{type:'line',background:'transparent',toolbar:{show:false}},
  stroke:{width:2.5,curve:'smooth'},colors:['#f97316'],
  xaxis:{categories:hours,labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{labels:{style:{colors:'#94a3b8'}},title:{text:'°C',style:{color:'#64748b'}}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},markers:{size:0},
  dataLabels:{enabled:false},tooltip:{theme:'dark'},legend:{labels:{colors:'#94a3b8'}}
}
const levelSeries = computed(() => [{
  name:'Avg Level %', data: hours.map((_,i)=>Math.max(10,Math.min(95, 60 + Math.sin(i/3)*20 + (Math.random()-0.5)*5)))
}])
const levelOptions = {
  chart:{type:'area',background:'transparent',toolbar:{show:false}},
  stroke:{width:2.5,curve:'smooth'},
  fill:{type:'gradient',gradient:{shade:'dark',type:'vertical',opacityFrom:0.4,opacityTo:0.02}},
  colors:['#22d3ee'],
  xaxis:{categories:hours,labels:{style:{colors:'#64748b',fontSize:'9px'}}},
  yaxis:{min:0,max:100,labels:{style:{colors:'#94a3b8'},formatter:(v:number)=>`${v}%`}},
  grid:{borderColor:'#1e293b',strokeDashArray:4},markers:{size:0},
  dataLabels:{enabled:false},tooltip:{theme:'dark'},legend:{labels:{colors:'#94a3b8'}}
}

const tankColumns = [
  {name:'name',label:'Tank',field:'name',align:'left' as const,sortable:true},
  {name:'plant',label:'Plant',field:'plant',align:'center' as const},
  {name:'sku',label:'Current SKU',field:'sku',align:'left' as const},
  {name:'level',label:'Level',field:'level',align:'left' as const,sortable:true},
  {name:'temp',label:'Temp (°C)',field:'temp',align:'center' as const,sortable:true},
  {name:'status',label:'Status',field:'status',align:'center' as const,sortable:true},
]

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 30000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.tank-page  { background:#020c1b;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif; }
.tank-scroll{ background:#020c1b;width:100%; }
.tank-topbar{ background:#021830;border-bottom:1px solid #0d3a5f; }
.tank-kpi-bar{ background:#010e1f;border-top:1px solid #0d3a5f;border-bottom:1px solid #0d3a5f; }
.tank-kpi-chip{ border-right:1px solid #0d2a3f;transition:background 0.2s;min-width:0;padding:8px 20px; }
.tank-kpi-chip:last-child{ border-right:none; }
.tank-card { border-radius:12px;border:1px solid #1e3a5f;transition:all 0.3s; }
.tank-card:hover { transform:translateY(-2px); box-shadow:0 4px 20px rgba(34,211,238,0.15); }
.tank-normal{ background:linear-gradient(135deg,#0f2030,#021830); }
.tank-full  { background:linear-gradient(135deg,#0f2744,#021830);border-color:#3b82f6 !important; }
.tank-empty { background:linear-gradient(135deg,#1a1a2e,#021830);border-color:#475569 !important; }
.tank-cip   { background:linear-gradient(135deg,#1a1200,#021830);border-color:#f59e0b !important; }
.tank-info-card{ background:#0f2030;border:1px solid #1e3a5f;border-radius:12px;height:100%; }
</style>

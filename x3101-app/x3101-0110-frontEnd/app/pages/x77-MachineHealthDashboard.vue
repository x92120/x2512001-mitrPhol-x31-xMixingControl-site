<template>
  <q-page class="mh-page" style="padding:0">
    <q-scroll-area class="mh-scroll" style="height:calc(100vh - 106px)">

      <!-- Top Bar -->
      <div class="mh-topbar row items-center q-px-lg q-py-sm no-wrap" style="gap:10px;flex-wrap:wrap">
        <q-icon name="monitor_heart" size="24px" color="red-4"/>
        <span class="text-subtitle1 text-white text-weight-bold">Drive Health Dashboard</span>
        <q-chip dense color="red-9" text-color="red-2" size="sm" icon="electric_bolt">G120C PROFINET</q-chip>
        <q-chip v-if="!plcOk" dense color="orange-9" text-color="orange-2" size="sm" icon="warning">
          DB100 ยังไม่มีข้อมูล — รอ TIA Portal
        </q-chip>
        <q-space/>
        <q-btn-toggle v-model="filterMix"
          :options="[{label:'All',value:0},{label:'MIX1',value:1},{label:'MIX2',value:2},{label:'MIX3',value:3}]"
          dense unelevated rounded color="blue-grey-8" text-color="grey-4"
          toggle-color="red-8" toggle-text-color="white" size="sm"/>
        <q-btn flat dense round icon="refresh" color="grey-4" @click="fetchData" :loading="loading"/>
        <div class="text-caption text-grey-6">
          <q-icon name="schedule" size="12px" class="q-mr-xs"/>{{ lastUpdated }}
          <q-badge :color="plcOk?'positive':'orange-9'" class="q-ml-sm" style="animation:pulse 2s infinite">
            {{ plcOk ? 'LIVE' : 'PENDING' }}
          </q-badge>
        </div>
        <q-btn unelevated dense rounded color="deep-purple-9" text-color="purple-2"
          icon="analytics" label="OEE" size="sm" to="/x72-OEEDashboard"/>
        <q-btn unelevated dense rounded color="teal-9" text-color="teal-2"
          icon="precision_manufacturing" label="MES" size="sm" to="/x73-MESDashboard"/>
      </div>

      <!-- KPI Bar -->
      <div class="mh-kpi-bar row items-stretch q-px-lg q-py-sm" style="gap:1px">
        <div v-for="k in kpis" :key="k.label" class="mh-kpi-chip col row items-center" style="gap:10px;padding:8px 20px">
          <q-icon :name="k.icon" :color="k.color" size="20px"/>
          <div>
            <div class="text-caption text-grey-5" style="font-size:10px;letter-spacing:1px">{{ k.label }}</div>
            <span class="text-subtitle1 text-weight-bolder" :class="`text-${k.color}`">{{ k.value }}</span>
          </div>
        </div>
      </div>

      <!-- Fault Alert -->
      <div v-if="faultDrives.length" class="q-px-lg q-pt-sm">
        <div class="row items-center q-pa-sm q-mb-xs"
          style="border-radius:8px;border-left:4px solid #ef4444;background:rgba(239,68,68,0.10)">
          <q-icon name="warning" color="red-4" size="18px" class="q-mr-sm"/>
          <span class="text-red-3" style="font-size:13px;font-weight:500">
            🚨 FAULT: {{ faultDrives.map(d=>d.name).join(', ') }}
          </span>
        </div>
      </div>

      <div class="q-px-lg q-pb-xl q-mt-md">

        <!-- Drive Cards -->
        <div class="text-subtitle2 text-white text-weight-bold q-mb-sm">
          <q-icon name="developer_board" color="red-4" size="16px" class="q-mr-xs"/>G120C Drive Status
        </div>
        <div class="row q-col-gutter-md q-mb-md">
          <div v-for="d in filteredDrives" :key="d.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
            <div class="mh-card q-pa-md" :class="cardClass(d)">
              <!-- Header -->
              <div class="row items-center justify-between q-mb-xs">
                <div>
                  <div class="text-white text-weight-bold" style="font-size:12px">{{ d.name }}</div>
                  <div class="text-caption text-grey-5" style="font-size:10px">{{ d.type }} · MIX{{ d.mix }}</div>
                </div>
                <q-icon :name="statusIcon(d)" :color="statusColor(d)" size="22px"/>
              </div>

              <!-- IP -->
              <div class="text-caption text-grey-6 q-mb-sm" style="font-size:9px;font-family:monospace">
                {{ d.ip }}
              </div>

              <!-- Health Score -->
              <div class="text-center q-mb-xs">
                <div class="text-caption text-grey-5" style="font-size:9px;letter-spacing:1px">HEALTH SCORE</div>
                <div class="text-h5 text-weight-bolder" :class="healthColor(d.health)">
                  {{ d.health }}%
                </div>
              </div>
              <q-linear-progress :value="d.health/100"
                :color="d.health>80?'positive':d.health>60?'warning':'negative'"
                track-color="blue-grey-9" style="height:6px;border-radius:3px" class="q-mb-sm"/>

              <!-- Metrics -->
              <div class="row q-mt-xs" style="gap:4px">
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">CURRENT (A)</div>
                  <div :class="d.current_pct>15?'text-negative':d.current_pct>10?'text-warning':'text-cyan-4'"
                    style="font-size:12px;font-weight:600">
                    {{ d.data_valid ? d.current_pct+'A' : '--' }}
                  </div>
                </div>
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">TEMP</div>
                  <div :class="d.temperature>80?'text-negative':d.temperature>60?'text-warning':'text-cyan-4'"
                    style="font-size:12px;font-weight:600">
                    {{ d.data_valid ? d.temperature+'°C' : '--' }}
                  </div>
                </div>
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">SPEED</div>
                  <div class="text-lime-4" style="font-size:12px;font-weight:600">
                    {{ d.data_valid ? d.speed_pct+'%' : '--' }}
                  </div>
                </div>
              </div>

              <!-- DC Voltage & Op Hours -->
              <div class="row q-mt-xs" style="gap:4px" v-if="d.data_valid">
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">DC BUS</div>
                  <div class="text-blue-4" style="font-size:11px;font-weight:600">{{ d.dc_voltage }}V</div>
                </div>
                <div class="mh-metric col">
                  <div class="text-caption text-grey-5" style="font-size:9px">OP HOURS</div>
                  <div class="text-grey-4" style="font-size:11px;font-weight:600">{{ d.op_hours }}h</div>
                </div>
              </div>

              <!-- Status chip + History button -->
              <div class="row items-center justify-between q-mt-sm">
                <q-chip dense :color="statusChipColor(d)" text-color="white" size="xs"
                  style="min-width:80px;justify-content:center">
                  {{ d.status }}
                </q-chip>
                <div v-if="d.fault_code>0" class="text-red-4" style="font-size:9px">
                  F{{ String(d.fault_code).padStart(5,'0') }}
                </div>
                <div v-if="d.rdrec_error && !d.fault_code" class="text-orange-4" style="font-size:9px">
                  RDREC ERR
                </div>
                <!-- Fault History Button -->
                <q-btn flat dense round icon="history" size="xs" color="grey-5"
                  @click.stop="openFaultHistory(d)"
                  style="margin-left:auto">
                  <q-tooltip>Fault History</q-tooltip>
                </q-btn>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Fault History Dialog ───────────────────────────────────────────── -->
        <q-dialog v-model="historyDialog" maximized transition-show="slide-up" transition-hide="slide-down">
          <q-card class="mh-page" style="display:flex;flex-direction:column">
            <!-- Dialog Header -->
            <q-toolbar style="background:#1a0020;border-bottom:1px solid #3a0030">
              <q-icon name="history" color="amber-4" size="22px" class="q-mr-sm"/>
              <q-toolbar-title class="text-white text-weight-bold" style="font-size:14px">
                Fault History — {{ historyDrive?.name }}
                <span class="text-grey-5 text-caption q-ml-sm">{{ historyDrive?.ip }}</span>
              </q-toolbar-title>
              <q-spinner v-if="historyLoading" color="amber" size="20px" class="q-mr-md"/>
              <q-btn flat dense round icon="close" color="grey-4" v-close-popup/>
            </q-toolbar>

            <div class="row" style="flex:1;overflow:hidden">
              <!-- Event List -->
              <div style="width:55%;overflow-y:auto;border-right:1px solid #2a0030">
                <div class="text-caption text-grey-5 q-pa-md" style="font-size:10px;letter-spacing:1px">
                  FAULT EVENTS ({{ faultEvents.length }}) — คลิกเพื่อดูวิธีแก้ไข
                </div>
                <div v-if="faultEvents.length===0" class="text-center text-grey-6 q-pa-xl">
                  <q-icon name="check_circle" color="positive" size="40px"/><br>
                  <span class="text-caption">ไม่มี Fault Event ใน session นี้</span>
                </div>
                <q-list dense separator dark>
                  <q-item v-for="(ev,i) in faultEvents" :key="i" clickable
                    :active="selectedEvent===i" active-class="mh-selected-event"
                    @click="selectedEvent=i" style="border-bottom:1px solid #1a0020">
                    <q-item-section avatar style="min-width:36px">
                      <q-icon
                        :name="ev.event==='FAULT_CLEARED'?'check_circle':'error'"
                        :color="ev.event==='FAULT_CLEARED'?'positive':'negative'"
                        size="18px"/>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label style="font-size:11px;font-weight:600"
                        :class="ev.event==='FAULT_CLEARED'?'text-positive':'text-red-3'">
                        {{ ev.event==='FAULT_CLEARED' ? '✅ Fault Cleared' : `F${String(ev.fault_code).padStart(5,'0')}` }}
                      </q-item-label>
                      <q-item-label caption style="font-size:10px;color:#94a3b8">
                        {{ ev.fault_desc }}
                      </q-item-label>
                      <q-item-label caption style="font-size:9px;color:#64748b">
                        {{ formatTs(ev.ts) }} &nbsp;|&nbsp; {{ ev.temperature }}°C &nbsp;|&nbsp; {{ ev.current_pct }}A
                      </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-badge
                        :color="ev.fault_sev==='critical'?'negative':ev.fault_sev==='ok'?'positive':'warning'"
                        style="font-size:9px">
                        {{ ev.fault_sev }}
                      </q-badge>
                    </q-item-section>
                  </q-item>
                </q-list>
              </div>

              <!-- Remedy Panel -->
              <div style="width:45%;overflow-y:auto;padding:20px">
                <div v-if="selectedEvent===null" class="text-center text-grey-6 q-pa-xl">
                  <q-icon name="touch_app" size="40px" color="grey-7"/><br>
                  <span class="text-caption">คลิก fault event เพื่อดูวิธีแก้ไข</span>
                </div>
                <div v-else-if="faultEvents[selectedEvent]">
                  <div class="text-white text-weight-bold q-mb-sm" style="font-size:13px">
                    <q-icon name="build_circle" color="amber-4" size="18px" class="q-mr-xs"/>
                    วิธีแก้ไข
                  </div>

                  <!-- Fault info -->
                  <div class="q-mb-md" style="background:#1a0020;border-radius:8px;padding:12px;border-left:3px solid"
                    :style="{borderColor: faultEvents[selectedEvent].fault_sev==='critical'?'#ef4444':'#f59e0b'}">
                    <div class="text-caption text-grey-5" style="font-size:9px;letter-spacing:1px">FAULT CODE</div>
                    <div class="text-white text-weight-bold" style="font-size:16px">
                      F{{ String(faultEvents[selectedEvent].fault_code).padStart(5,'0') }}
                    </div>
                    <div class="text-grey-4" style="font-size:11px;margin-top:4px">
                      {{ faultEvents[selectedEvent].fault_desc }}
                    </div>
                    <div class="text-grey-6" style="font-size:10px;margin-top:6px">
                      🕐 {{ formatTs(faultEvents[selectedEvent].ts) }}
                      &nbsp;·&nbsp; 🌡 {{ faultEvents[selectedEvent].temperature }}°C
                      &nbsp;·&nbsp; ⚡ {{ faultEvents[selectedEvent].current_pct }}A
                    </div>
                  </div>

                  <!-- Remedy steps -->
                  <div v-if="faultEvents[selectedEvent].fault_remedy && faultEvents[selectedEvent].fault_remedy !== '-'">
                    <div class="text-amber-5 text-weight-bold q-mb-xs" style="font-size:11px">
                      📋 ขั้นตอนการแก้ไข:
                    </div>
                    <div style="background:#0f1a10;border-radius:8px;padding:12px;border:1px solid #2a4a2a">
                      <div class="text-grey-3" style="font-size:11px;line-height:1.8;white-space:pre-line">
                        {{ faultEvents[selectedEvent].fault_remedy?.replace(/\. /g,'\n• ') }}
                      </div>
                    </div>
                  </div>

                  <!-- Siemens reference -->
                  <div class="q-mt-md text-grey-6" style="font-size:10px">
                    <q-icon name="info" size="12px" class="q-mr-xs"/>
                    อ้างอิง: SINAMICS G120C List Manual — ตรวจสอบ r0947/r0949 บน BOP/IOP
                  </div>
                </div>
              </div>
            </div>
          </q-card>
        </q-dialog>

        <!-- Charts Row -->
        <div class="row q-col-gutter-md q-mb-md">
          <!-- Current Trend -->
          <div class="col-12 col-md-6">
            <div class="mh-info-card q-pa-md">
              <div class="row items-center justify-between q-mb-xs">
                <div class="text-subtitle2 text-white text-weight-bold">
                  <q-icon name="electric_bolt" color="amber-4" size="16px" class="q-mr-xs"/>Motor Current (%)
                </div>
                <q-select v-model="chartDrive" :options="driveOptions" dense dark outlined
                  option-value="id" option-label="name" emit-value map-options
                  style="min-width:130px;font-size:11px" class="text-white"/>
              </div>
              <apexchart type="line" height="180" :options="trendOptions('Current %','#22d3ee')" :series="currentSeries"/>
            </div>
          </div>
          <!-- Temp Trend -->
          <div class="col-12 col-md-6">
            <div class="mh-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="device_thermostat" color="red-4" size="16px" class="q-mr-xs"/>Temperature (°C)
              </div>
              <apexchart type="line" height="180" :options="trendOptions('°C','#f97316',[60])" :series="tempSeries"/>
            </div>
          </div>
        </div>

        <!-- Overall Health + Fault Log -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-4">
            <div class="mh-info-card q-pa-md flex column items-center">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-xs">
                <q-icon name="health_and_safety" color="positive" size="16px" class="q-mr-xs"/>Overall Health
              </div>
              <apexchart type="radialBar" height="220" :options="radialOpts" :series="[avgHealth]"/>
              <div class="text-caption text-grey-5 text-center">{{ avgHealth }}% — Fleet Average</div>
            </div>
          </div>
          <div class="col-12 col-md-8">
            <div class="mh-info-card q-pa-md">
              <div class="text-subtitle2 text-white text-weight-bold q-mb-md">
                <q-icon name="report_problem" color="orange-4" size="16px" class="q-mr-xs"/>Active Fault Log
              </div>
              <div v-if="activeFaults.length === 0" class="text-grey-6 text-caption text-center q-py-lg">
                <q-icon name="check_circle" color="positive" size="32px" class="q-mb-sm"/><br>
                ไม่มี Fault ที่ Active อยู่ในขณะนี้
              </div>
              <q-table v-else :rows="activeFaults" :columns="faultCols" row-key="drive_id"
                dark flat dense :rows-per-page-options="[8]" :pagination="{rowsPerPage:8}"
                table-header-class="text-grey-5 text-caption">
                <template #body="props">
                  <q-tr :props="props">
                    <q-td v-for="col in props.cols" :key="col.name" :props="props">
                      <!-- Severity chip -->
                      <q-chip v-if="col.name==='severity'" dense
                        :color="props.row.fault_sev==='critical'?'negative':'warning'"
                        text-color="white" size="xs">
                        {{ props.row.fault_sev === 'critical' ? 'Critical' : 'Warning' }}
                      </q-chip>
                      <!-- Description with remedy tooltip -->
                      <span v-else-if="col.name==='description'">
                        <span class="text-amber-3" style="font-size:11px">{{ props.row.description }}</span>
                        <q-tooltip v-if="props.row.remedy && props.row.remedy !== '-'"
                          anchor="bottom left" self="top left" max-width="340px"
                          class="bg-grey-10 text-white" style="font-size:11px;padding:10px 14px">
                          <div class="text-amber-4 text-weight-bold q-mb-xs">
                            <q-icon name="build" size="12px" class="q-mr-xs"/>วิธีแก้ไข
                          </div>
                          {{ props.row.remedy }}
                        </q-tooltip>
                      </span>
                      <span v-else style="font-size:11px">{{ col.value }}</span>
                    </q-td>
                  </q-tr>
                  <!-- Remedy row (always visible) -->
                  <q-tr v-if="props.row.remedy && props.row.remedy !== '-'" :props="props"
                    style="background:rgba(245,158,11,0.06)">
                    <q-td colspan="100%" style="padding:4px 16px 8px">
                      <div class="row items-start" style="gap:6px">
                        <q-icon name="build_circle" color="amber-5" size="14px" style="margin-top:2px"/>
                        <div class="text-grey-4" style="font-size:10px;line-height:1.6">
                          <span class="text-amber-5 text-weight-bold">วิธีแก้ไข: </span>
                          {{ props.row.remedy }}
                        </div>
                      </div>
                    </q-td>
                  </q-tr>
                </template>
              </q-table>
            </div>
          </div>
        </div>

        <!-- TIA Portal Guide (shown when DB100 not ready) -->
        <div v-if="!plcOk" class="mh-info-card q-pa-lg q-mb-md">
          <div class="text-subtitle2 text-amber-4 text-weight-bold q-mb-md">
            <q-icon name="construction" size="16px" class="q-mr-xs"/>ขั้นตอนต่อไป — TIA Portal Setup
          </div>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <div class="text-caption text-grey-4 q-mb-xs" style="font-size:11px">
                1. สร้าง <span class="text-amber-4">UDT_DriveHealth</span> ใน PLC Data Types<br>
                2. สร้าง <span class="text-amber-4">DB100</span> (Global DB) — ปิด Optimized Access<br>
                3. สร้าง <span class="text-amber-4">FB100</span> และเรียกใน OB30 (1000ms)<br>
                4. Download Program (ไม่ใช่ HW Config)<br>
                5. กด Refresh — ข้อมูลจะแสดงทันที
              </div>
            </div>
            <div class="col-12 col-md-6">
              <div class="text-caption text-grey-4" style="font-size:11px">
                <span class="text-cyan-4">Drive → DB100 Index:</span><br>
                <span v-for="d in allDrives" :key="d.id" class="block">
                  [{{ d.id }}] {{ d.name }} ({{ d.ip }})
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </q-scroll-area>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const baseUrl = typeof window !== 'undefined'
  ? `http://${window.location.hostname}:8031`
  : 'http://192.168.21.210:8031'

const loading    = ref(false)
const plcOk      = ref(false)
const lastUpdated= ref('--:--:--')
const allDrives  = ref<any[]>([])
const history    = ref<Record<number,any[]>>({})
const filterMix  = ref(0)
const chartDrive = ref(0)
let   timer: any = null

// ─── Fault History Dialog ─────────────────────────────────────────────────────
const historyDialog  = ref(false)
const historyDrive   = ref<any>(null)
const historyLoading = ref(false)
const faultEvents    = ref<any[]>([])
const selectedEvent  = ref<number|null>(null)

async function openFaultHistory(drive: any) {
  historyDrive.value  = drive
  historyDialog.value = true
  selectedEvent.value = null
  faultEvents.value   = []
  historyLoading.value = true
  try {
    const res  = await fetch(`${baseUrl}/api/drive-health/fault-history/${drive.id}?limit=100`)
    const data = await res.json()
    faultEvents.value = data.events || []
  } catch(e) {
    console.error('fault-history fetch error:', e)
  } finally {
    historyLoading.value = false
  }
}

function formatTs(ts: string) {
  if (!ts) return '--'
  const d = new Date(ts)
  return d.toLocaleTimeString('th-TH', { hour:'2-digit', minute:'2-digit', second:'2-digit' }) +
         ' ' + d.toLocaleDateString('th-TH', { day:'2-digit', month:'2-digit' })
}

// ─── Fetch ────────────────────────────────────────────────────────────────────
async function fetchData() {
  loading.value = true
  try {
    const res  = await fetch(`${baseUrl}/api/drive-health/all`)
    const data = await res.json()
    plcOk.value     = data.ok && data.drives?.some((d:any) => d.data_valid)
    allDrives.value = data.drives || []
    lastUpdated.value = new Date().toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit',second:'2-digit'})

    // Fetch history for selected chart drive
    await fetchHistory(chartDrive.value)
  } catch(e) {
    console.error('drive-health fetch error:', e)
  } finally {
    loading.value = false
  }
}

async function fetchHistory(driveId: number) {
  try {
    const res  = await fetch(`${baseUrl}/api/drive-health/history/${driveId}?points=60`)
    const data = await res.json()
    history.value[driveId] = data.history || []
  } catch(e) {}
}

// ─── Computed ────────────────────────────────────────────────────────────────
const filteredDrives = computed(() =>
  filterMix.value === 0 ? allDrives.value
  : allDrives.value.filter(d => d.mix === filterMix.value)
)

const faultDrives = computed(() => allDrives.value.filter(d => d.fault))

const avgHealth = computed(() => {
  const ds = filteredDrives.value
  return ds.length ? Math.round(ds.reduce((s,d)=>s+d.health,0)/ds.length) : 0
})

const kpis = computed(() => {
  const ds = filteredDrives.value
  return [
    { label:'TOTAL DRIVES',  icon:'electric_meter',    color:'red-4',   value: ds.length },
    { label:'RUNNING',       icon:'play_circle',        color:'positive',value: ds.filter(d=>d.running).length },
    { label:'FAULT',         icon:'error',              color:'negative', value: ds.filter(d=>d.fault).length },
    { label:'ALARM',         icon:'warning',            color:'warning',  value: ds.filter(d=>d.alarm).length },
    { label:'AVG HEALTH',    icon:'monitor_heart',      color:'lime-4',   value: `${avgHealth.value}%` },
    { label:'AVG TEMP',      icon:'device_thermostat',  color:'orange-4', value: `${Math.round(ds.reduce((s,d)=>s+d.temperature,0)/(ds.length||1))}°C` },
  ]
})

const activeFaults = computed(() =>
  allDrives.value
    .filter(d => d.fault)  // เฉพาะ fault จริง (ZSW1 bit3) — ไม่รวม r0945 history
    .map(d => ({
      drive_id:    d.id,
      drive_name:  d.name,
      fault_code:  `F${String(d.fault_code).padStart(5,'0')}`,
      description: d.fault_desc || `F${String(d.fault_code).padStart(5,'0')} - Fault Active`,
      remedy:      d.fault_remedy || 'Check r0949 on drive HMI. Refer to SINAMICS G120C List Manual.',
      fault_sev:   d.fault_sev   || 'warning',
      temperature: d.temperature+'°C',
      current:     d.current_pct+'A',
      time:        lastUpdated.value,
    }))
)

const faultCols = [
  {name:'drive_name',  label:'Drive',      field:'drive_name',  align:'left'   as const},
  {name:'fault_code',  label:'Code',       field:'fault_code',  align:'center' as const},
  {name:'description', label:'Description',field:'description', align:'left'   as const},
  {name:'temperature', label:'Temp',       field:'temperature', align:'center' as const},
  {name:'current',     label:'Current',    field:'current',     align:'center' as const},
  {name:'severity',    label:'Severity',   field:'fault_sev',   align:'center' as const},
]

const driveOptions = computed(() =>
  allDrives.value.map(d => ({ id: d.id, name: d.name }))
)

// ─── Chart Series ─────────────────────────────────────────────────────────────
const chartHistory = computed(() => history.value[chartDrive.value] || [])

const currentSeries = computed(() => [{
  name: allDrives.value[chartDrive.value]?.name || 'Drive',
  data: chartHistory.value.map((h:any) => h.current_pct),  // history still stored as current_pct
}])

const tempSeries = computed(() => [{
  name: allDrives.value[chartDrive.value]?.name || 'Drive',
  data: chartHistory.value.map((h:any) => h.temperature),
}])

function trendOptions(yTitle:string, color:string, warnings:number[]=[]) {
  const cats = chartHistory.value.map((_:any,i:number)=> i % 10 === 0 ? `-${(chartHistory.value.length-i)*5}s` : '')
  return {
    chart:{ type:'line', background:'transparent', toolbar:{show:false}, animations:{enabled:false} },
    stroke:{ width:2, curve:'smooth' },
    colors:[ color ],
    xaxis:{ categories: cats, labels:{ style:{colors:'#64748b',fontSize:'9px'} } },
    yaxis:{ labels:{ style:{colors:'#94a3b8'} }, title:{text:yTitle,style:{color:'#64748b'}} },
    annotations:{ yaxis: warnings.map(y=>({
      y, borderColor:'#f59e0b', strokeDashArray:4,
      label:{text:`${y}`,style:{background:'#f59e0b',color:'#000',fontSize:'9px'}}
    }))},
    grid:{ borderColor:'#1e293b', strokeDashArray:4 },
    markers:{ size:0 },
    dataLabels:{ enabled:false },
    tooltip:{ theme:'dark' },
    legend:{ labels:{ colors:'#94a3b8' } },
  }
}

const radialOpts = computed(() => ({
  chart:{ type:'radialBar', background:'transparent' },
  plotOptions:{ radialBar:{
    startAngle:-135, endAngle:135,
    hollow:{ size:'60%', background:'#0a1628' },
    track:{ background:'#1e293b', strokeWidth:'80%' },
    dataLabels:{ name:{show:false}, value:{show:true,color:'#fff',fontSize:'24px',fontWeight:700,formatter:()=>`${avgHealth.value}%`} }
  }},
  fill:{ type:'gradient', gradient:{shade:'dark',type:'horizontal',gradientToColors:['#22c55e'],stops:[0,100]} },
  colors:[ avgHealth.value>80?'#22c55e':avgHealth.value>60?'#f59e0b':'#ef4444' ],
  labels:['Health'], tooltip:{ enabled:false }
}))

// ─── Helpers ──────────────────────────────────────────────────────────────────
function cardClass(d:any) {
  if (d.fault)                      return 'mh-critical'
  // ถ้าไม่มีข้อมูล RDREC และไม่ได้ running → โชว์ offline (เทา/นิ่ง)
  if (!d.data_valid && !d.running)  return 'mh-offline'
  if (d.alarm)                      return 'mh-warn'
  if (d.health > 80)                return 'mh-good'
  if (d.health > 60)                return 'mh-warn'
  return 'mh-critical'
}

function statusIcon(d:any) {
  if (d.fault)       return 'error'
  if (d.alarm)       return 'warning'
  if (d.running)     return 'play_circle'
  if (d.ready)       return 'check_circle'
  return 'radio_button_unchecked'
}

function statusColor(d:any) {
  if (d.fault)   return 'negative'
  if (d.alarm)   return 'warning'
  if (d.running) return 'positive'
  if (d.ready)   return 'blue-4'
  return 'grey-6'
}

function healthColor(h:number) {
  return h > 80 ? 'text-positive' : h > 60 ? 'text-warning' : 'text-negative'
}

function statusChipColor(d:any) {
  const map:Record<string,string> = {
    FAULT:'negative', ALARM:'warning', RUNNING:'positive', READY:'blue-6', OFFLINE:'grey-7'
  }
  return map[d.status] || 'grey-7'
}

onMounted(() => { fetchData(); timer = setInterval(fetchData, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.mh-page    { background:#0a0010;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif; }
.mh-scroll  { background:#0a0010;width:100%; }
.mh-topbar  { background:#1a0020;border-bottom:1px solid #3a0030; }
.mh-kpi-bar { background:#0a0010;border-top:1px solid #3a0030;border-bottom:1px solid #3a0030; }
.mh-kpi-chip{ border-right:1px solid #1a0020;transition:background 0.2s;min-width:0;padding:8px 20px; }
.mh-kpi-chip:last-child{ border-right:none; }
.mh-card    { border-radius:12px;border:1px solid;transition:all 0.3s; }
.mh-card:hover { transform:translateY(-2px); }
.mh-good     { background:linear-gradient(135deg,#0f2030,#0a0010);border-color:#22c55e; }
.mh-warn     { background:linear-gradient(135deg,#1a1200,#0a0010);border-color:#f59e0b; }
.mh-critical { background:linear-gradient(135deg,#200010,#0a0010);border-color:#ef4444;animation:pulse-border 2s infinite; }
.mh-offline  { background:linear-gradient(135deg,#111,#0a0010);border-color:#475569; }
@keyframes pulse-border { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)} 50%{box-shadow:0 0 0 6px rgba(239,68,68,0)} }
.mh-metric  { background:#0a0010;border-radius:6px;padding:4px 8px;text-align:center; }
.mh-info-card{ background:#0f0020;border:1px solid #2a0030;border-radius:12px;height:100%; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.mh-selected-event { background:rgba(245,158,11,0.15) !important; border-left:3px solid #f59e0b; }
</style>

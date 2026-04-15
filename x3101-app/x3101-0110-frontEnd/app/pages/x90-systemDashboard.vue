<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
// import VueApexCharts from 'vue3-apexcharts'

const $q = useQuasar()
const { t } = useI18n()

const formatDate = (date: any) => {
  if (!date) return '-'
  const d = new Date(date)
  if (isNaN(d.getTime())) return date
  return d.toLocaleDateString('en-GB')
}

const formatDateTime = (date: any) => {
  if (!date) return '-'
  const d = new Date(date)
  if (isNaN(d.getTime())) return date
  return d.toLocaleString('en-GB')
}

// ── Active DB State ──
interface ActiveDbInfo {
  key: string
  label: string
  host: string
  icon: string
}
interface DbOption {
  key: string
  label: string
  host: string
  icon: string
  active: boolean
}
const activeDb = ref<ActiveDbInfo | null>(null)

const fetchActiveDb = async () => {
  try {
    const data = await $fetch<ActiveDbInfo>(`${appConfig.apiBaseUrl}/db-sync/active-db`)
    activeDb.value = data
  } catch (e) {
    console.error('Active DB fetch error:', e)
  }
}

// ── DB Sync State ──
const syncLoading = ref<string | null>(null) // 'cloud-to-remote' | 'remote-to-cloud' | null
const syncLog = ref<string[]>([])
const syncDialog = ref(false)
const dbStatus = ref<any>(null)
const dbStatusLoading = ref(false)

const fetchDbStatus = async () => {
  dbStatusLoading.value = true
  try {
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/db-sync/status`)
    dbStatus.value = data
  } catch (e) {
    console.error('DB status error:', e)
  } finally {
    dbStatusLoading.value = false
  }
}

const handleSync = async (direction: 'remote-to-cloud') => {
  const label = 'Remote → Cloud'

  $q.dialog({
    title: 'Confirm Database Sync',
    message: `Are you sure you want to sync <b>${label}</b>?<br><br>This will <b>overwrite all data</b> on the target database.`,
    html: true,
    cancel: true,
    persistent: true,
    ok: { label: 'Sync Now', color: 'negative', icon: 'sync' },
  }).onOk(async () => {
    syncLoading.value = direction
    syncLog.value = [`Starting sync: ${label}...`]
    syncDialog.value = true

    try {
      const data = await $fetch<any>(`${appConfig.apiBaseUrl}/db-sync/${direction}`, { method: 'POST', timeout: 120000 })
      syncLog.value = data.log || []
      syncLog.value.push(``, `══════════════════════════════`)
      syncLog.value.push(`✅ Sync complete: ${data.tables_synced} tables, ${data.views_synced} views, ${data.total_rows} rows`)

      $q.notify({ type: 'positive', message: `Sync complete: ${label}`, caption: `${data.tables_synced} tables, ${data.total_rows} rows` })
      fetchDbStatus()
    } catch (e: any) {
      syncLog.value.push(`❌ Error: ${e?.data?.detail || e?.message || 'Unknown error'}`)
      $q.notify({ type: 'negative', message: `Sync failed: ${label}`, caption: e?.data?.detail || e?.message })
    } finally {
      syncLoading.value = null
    }
  })
}

// ── Host Info & Connected Devices ──
interface HostInfo {
  hostname: string
  ip_addresses: string[]
  os_name: string
  os_version: string
  kernel: string
  architecture: string
  cpu_model: string
  total_ram: string
  username: string
  uptime: string
  boot_time_iso: string
}

interface ConnectedDevice {
  name: string
  type: string
  status: string
  details: string
  icon: string
}

interface ConnectedDevicesData {
  usb_devices: ConnectedDevice[]
  network_devices: ConnectedDevice[]
  serial_devices: ConnectedDevice[]
}

const hostInfo = ref<HostInfo | null>(null)
const connectedDevices = ref<ConnectedDevicesData | null>(null)

const fetchHostInfo = async () => {
  try {
    const data = await $fetch<HostInfo>(`${appConfig.apiBaseUrl}/host-info`)
    hostInfo.value = data
  } catch (e) {
    console.error('Host info fetch error:', e)
  }
}

const fetchConnectedDevices = async () => {
  try {
    const data = await $fetch<ConnectedDevicesData>(`${appConfig.apiBaseUrl}/connected-devices`)
    connectedDevices.value = data
  } catch (e) {
    console.error('Connected devices fetch error:', e)
  }
}

const allDevices = computed(() => {
  if (!connectedDevices.value) return []
  return [
    ...connectedDevices.value.usb_devices,
    ...connectedDevices.value.network_devices,
    ...connectedDevices.value.serial_devices,
  ]
})

const deviceStatusColor = (status: string) => {
  switch (status) {
    case 'connected': case 'up': return 'green'
    case 'available': return 'blue'
    case 'down': return 'red'
    default: return 'grey'
  }
}

onMounted(() => {
  fetchActiveDb()
  fetchDbStatus()
  fetchHostInfo()
  fetchConnectedDevices()
})

interface MetricPoint {
  timestamp: string
  value: number
}

interface ServerHistory {
  cpu: MetricPoint[]
  memory: MetricPoint[]
  disk: MetricPoint[]
  net_sent: MetricPoint[]
  net_recv: MetricPoint[]
}

interface ServerStatus {
  cpu_percent: number[]
  cpu_average: number
  cpu_count: number
  memory: {
    total: number
    available: number
    percent: number
    used: number
  }
  disk: {
    total: number
    used: number
    free: number
    percent: number
  }
  network: {
    bytes_sent: number
    bytes_recv: number
    packets_sent: number
    packets_recv: number
  }
  boot_time: number
  os: string
  python_version: string
  hostname: string
  local_ip: string
  cpu_model: string
  architecture: string
}

const status = ref<ServerStatus | null>(null)
const history = ref<ServerHistory | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let pollTimer: any = null
let historyTimer: any = null

const formatBytes = (bytes: number, decimals = 2) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

const fetchStatus = async () => {
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/server-status`)
    if (!response.ok) throw new Error('Failed to fetch server status')
    status.value = await response.json()
    error.value = null
  } catch (e) {
    console.error(e)
    error.value = (e as any).message
  } finally {
    loading.value = false
  }
}

const fetchHistory = async () => {
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/server-status/history`)
    if (!response.ok) throw new Error('Failed to fetch server history')
    history.value = await response.json()
  } catch (e) {
    console.error('History fetch error:', e)
  }
}

// Chart Options
const baseChartOptions = {
  chart: {
    type: 'line' as const,
    height: 250,
    animations: { enabled: false },
    toolbar: { show: false },
    zoom: { enabled: false }
  },
  stroke: { curve: 'smooth' as const, width: 2 },
  xaxis: {
    type: 'datetime' as const,
    labels: {
      datetimeUTC: false,
      format: 'HH:mm:ss'
    },
    tooltip: { enabled: false }
  },
  yaxis: {
    labels: { formatter: (val: number) => val.toFixed(1) }
  },
  legend: { position: 'top' as const },
  grid: {
    borderColor: '#f1f1f1',
    show: true
  }
}

const cpuSeries = computed(() => [
  {
    name: 'CPU Usage (%)',
    data: history.value?.cpu.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.value })) || []
  }
])

const memSeries = computed(() => [
  {
    name: 'Memory Usage (%)',
    data: history.value?.memory.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.value })) || []
  }
])

const diskSeries = computed(() => [
  {
    name: 'Disk Usage (%)',
    data: history.value?.disk.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.value })) || []
  }
])

const netSeries = computed(() => [
  {
    name: 'Sent (KB/s)',
    data: history.value?.net_sent.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.value / 1024 })) || []
  },
  {
    name: 'Received (KB/s)',
    data: history.value?.net_recv.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.value / 1024 })) || []
  }
])

// ── Remote Server Status ──
const remoteStatus = ref<ServerStatus | null>(null)
const remoteLoading = ref(true)
const remoteError = ref<string | null>(null)
let remotePollTimer: any = null

const fetchRemoteStatus = async () => {
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/remote-server/status`)
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || 'Failed to fetch remote server status')
    }
    remoteStatus.value = await response.json()
    remoteError.value = null
  } catch (e: any) {
    console.error('Remote server status error:', e)
    remoteError.value = e.message || 'Cannot connect'
  } finally {
    remoteLoading.value = false
  }
}

onMounted(() => {
  fetchStatus()
  fetchHistory()
  fetchRemoteStatus()
  pollTimer = setInterval(fetchStatus, 3000)
  historyTimer = setInterval(fetchHistory, 10000)
  remotePollTimer = setInterval(fetchRemoteStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (historyTimer) clearInterval(historyTimer)
  if (remotePollTimer) clearInterval(remotePollTimer)
})
</script>

<template>
  <q-page class="q-pa-md">
    <ClientOnly>
      <div v-if="status" class="row q-col-gutter-md">
        <div class="col-12">
          <div class="text-h5 flex items-center">
            <q-icon name="dns" class="q-mr-sm" color="primary" />
            {{ t('dashboard.title') }}
            <q-spacer />
            <q-chip color="primary" text-color="white" icon="info" dense>
              {{ status.os }}
            </q-chip>
            <q-chip color="secondary" text-color="white" icon="code" dense>
              Python {{ status.python_version }}
            </q-chip>
          </div>
        </div>

        <!-- Left Pane: PC Info and Uptime -->
        <div class="col-12 col-md-3">
          <div class="column q-gutter-md">
            <!-- Active Database Selector Card -->
            <q-card flat bordered class="active-db-card">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="storage" class="q-mr-xs" />
                  Active Database
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div v-if="activeDb">
                  <div class="row items-center q-mb-sm">
                    <q-icon name="dns" size="sm" class="q-mr-sm" color="green-4" />
                    <div>
                      <div class="text-subtitle2 text-weight-bold">{{ activeDb.label }}</div>
                      <div class="text-caption opacity-70">{{ activeDb.host }}</div>
                    </div>
                  </div>
                  <q-badge color="teal" text-color="black" class="q-px-sm">
                    <q-icon name="dns" size="xs" class="q-mr-xs" />
                    REMOTE
                  </q-badge>
                </div>
                <q-skeleton v-else type="rect" height="50px" />
              </q-card-section>
            </q-card>

            <!-- PC Info Card -->
            <q-card flat bordered class="bg-primary text-white">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="computer" class="q-mr-xs" />
                  {{ t('dashboard.pcInfo') }}
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="q-mb-sm">
                  <div class="text-caption opacity-70">{{ t('dashboard.hostname') }}</div>
                  <div class="text-subtitle2">{{ status.hostname }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-70">{{ t('dashboard.localIp') }}</div>
                  <div class="text-subtitle2">{{ status.local_ip }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-70">{{ t('dashboard.osKernel') }}</div>
                  <div class="text-subtitle2">{{ status.os }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-70">{{ t('dashboard.architecture') }}</div>
                  <div class="text-subtitle2">{{ status.architecture }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-70">{{ t('dashboard.cpuModel') }}</div>
                  <div class="text-subtitle2 text-italic" style="font-size: 0.8rem">
                    {{ status.cpu_model }}
                  </div>
                </div>
              </q-card-section>
            </q-card>

            <!-- System Uptime Card -->
            <q-card flat bordered class="bg-grey-9 text-white">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="history" class="q-mr-xs" />
                  {{ t('dashboard.systemUptime') }}
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-caption text-grey-5">{{ t('dashboard.bootTime') }}</div>
                <div class="text-subtitle2">
                  {{ formatDateTime(status.boot_time * 1000) }}
                </div>
                <q-btn 
                  icon="refresh" 
                  flat 
                  round 
                  dense 
                  @click="fetchStatus" 
                  :loading="loading" 
                  class="q-mt-md full-width"
                  :label="t('dashboard.refreshMetrics')"
                />
              </q-card-section>
            </q-card>

            <!-- Database Sync Card -->
            <q-card flat bordered class="bg-teal-9 text-white">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="sync" class="q-mr-xs" />
                  Database Sync
                  <q-spacer />
                  <q-btn flat round dense icon="refresh" size="sm" @click="fetchDbStatus" :loading="dbStatusLoading" />
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <!-- Connection Status -->
                <div v-if="dbStatus" class="q-mb-md">
                  <div class="row items-center">
                    <q-icon :name="dbStatus.remote?.status === 'connected' ? 'dns' : 'report_problem'" :color="dbStatus.remote?.status === 'connected' ? 'green-4' : 'red-4'" size="xs" class="q-mr-xs" />
                    <span class="text-caption">Remote ({{ dbStatus.remote?.host }})</span>
                    <q-spacer />
                    <q-badge :color="dbStatus.remote?.status === 'connected' ? 'green' : 'red'" :label="dbStatus.remote?.status === 'connected' ? `${dbStatus.remote.tables} tables` : 'offline'" />
                  </div>
                </div>

                <!-- Sync Button (Backup to Cloud) -->
                <q-btn
                  icon="cloud_upload"
                  label="Backup to Cloud"
                  color="amber-8"
                  class="full-width"
                  dense
                  no-caps
                  :loading="syncLoading === 'remote-to-cloud'"
                  :disable="!!syncLoading"
                  @click="handleSync('remote-to-cloud')"
                />
              </q-card-section>
            </q-card>

            <!-- Host Info Card -->
            <q-card flat bordered class="bg-indigo-9 text-white">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="info" class="q-mr-xs" />
                  Host Information
                  <q-spacer />
                  <q-btn flat round dense icon="refresh" size="sm" @click="fetchHostInfo" />
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <template v-if="hostInfo">
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">Username</div>
                    <div class="text-subtitle2">{{ hostInfo.username }}</div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">OS</div>
                    <div class="text-subtitle2">{{ hostInfo.os_name }} {{ hostInfo.os_version }}</div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">Kernel</div>
                    <div class="text-subtitle2" style="font-size: 0.75rem;">{{ hostInfo.kernel }}</div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">CPU</div>
                    <div class="text-subtitle2" style="font-size: 0.75rem;">{{ hostInfo.cpu_model }}</div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">Total RAM</div>
                    <div class="text-subtitle2">{{ hostInfo.total_ram }}</div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">IP Addresses</div>
                    <div class="text-subtitle2">
                      <q-badge v-for="(ip, idx) in hostInfo.ip_addresses" :key="idx" color="indigo-6" class="q-mr-xs q-mb-xs">{{ ip }}</q-badge>
                    </div>
                  </div>
                  <div class="q-mb-xs">
                    <div class="text-caption opacity-70">Uptime</div>
                    <div class="text-subtitle2">
                      <q-icon name="schedule" size="xs" class="q-mr-xs" />{{ hostInfo.uptime }}
                    </div>
                  </div>
                </template>
                <q-skeleton v-else type="text" :count="5" />
              </q-card-section>
            </q-card>

            <!-- Connected Devices Card -->
            <q-card flat bordered class="bg-deep-purple-9 text-white">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="devices" class="q-mr-xs" />
                  Connected Devices
                  <q-spacer />
                  <q-badge color="deep-purple-4" text-color="white">
                    {{ allDevices.length }}
                  </q-badge>
                  <q-btn flat round dense icon="refresh" size="sm" class="q-ml-xs" @click="fetchConnectedDevices" />
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <template v-if="connectedDevices">
                  <!-- USB Devices -->
                  <div v-if="connectedDevices.usb_devices.length" class="q-mb-sm">
                    <div class="text-caption text-deep-purple-3 q-mb-xs">USB Devices</div>
                    <div v-for="(dev, i) in connectedDevices.usb_devices" :key="'usb-'+i" class="row items-center q-mb-xs">
                      <q-icon :name="dev.icon" size="xs" class="q-mr-xs" />
                      <span class="text-caption ellipsis" style="flex: 1;">{{ dev.name }}</span>
                      <q-badge :color="deviceStatusColor(dev.status)" size="xs">{{ dev.status }}</q-badge>
                    </div>
                  </div>

                  <!-- Network Interfaces -->
                  <div v-if="connectedDevices.network_devices.length" class="q-mb-sm">
                    <div class="text-caption text-deep-purple-3 q-mb-xs">Network Interfaces</div>
                    <div v-for="(dev, i) in connectedDevices.network_devices" :key="'net-'+i" class="row items-center q-mb-xs">
                      <q-icon :name="dev.icon" size="xs" class="q-mr-xs" />
                      <div style="flex: 1;">
                        <div class="text-caption">{{ dev.name }}</div>
                        <div class="text-caption opacity-70" style="font-size: 0.65rem;">{{ dev.details }}</div>
                      </div>
                      <q-badge :color="deviceStatusColor(dev.status)" size="xs">{{ dev.status }}</q-badge>
                    </div>
                  </div>

                  <!-- Serial Ports -->
                  <div v-if="connectedDevices.serial_devices.length">
                    <div class="text-caption text-deep-purple-3 q-mb-xs">Serial Ports</div>
                    <div v-for="(dev, i) in connectedDevices.serial_devices" :key="'serial-'+i" class="row items-center q-mb-xs">
                      <q-icon :name="dev.icon" size="xs" class="q-mr-xs" />
                      <span class="text-caption" style="flex: 1;">{{ dev.name }}</span>
                      <q-badge :color="deviceStatusColor(dev.status)" size="xs">{{ dev.status }}</q-badge>
                    </div>
                  </div>

                  <div v-if="allDevices.length === 0" class="text-caption text-center opacity-70 q-pa-sm">
                    No devices detected
                  </div>
                </template>
                <q-skeleton v-else type="text" :count="3" />
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Sync Log Dialog -->
        <q-dialog v-model="syncDialog" persistent>
          <q-card style="min-width: 500px; max-width: 700px;">
            <q-card-section class="row items-center q-pb-none">
              <div class="text-h6">
                <q-icon name="sync" class="q-mr-xs" />
                Sync Log
              </div>
              <q-spacer />
              <q-btn v-if="!syncLoading" icon="close" flat round dense v-close-popup />
            </q-card-section>
            <q-card-section>
              <q-linear-progress v-if="syncLoading" indeterminate color="primary" class="q-mb-md" />
              <div class="bg-grey-10 text-green-4 q-pa-md rounded-borders" style="font-family: monospace; font-size: 0.8rem; max-height: 400px; overflow-y: auto;">
                <div v-for="(line, i) in syncLog" :key="i" :class="{ 'text-red-4': line.startsWith('✗') || line.startsWith('❌'), 'text-green-4': line.startsWith('✓') || line.startsWith('✅') }">
                  {{ line }}
                </div>
              </div>
            </q-card-section>
            <q-card-actions align="right" v-if="!syncLoading">
              <q-btn flat label="Close" color="primary" v-close-popup />
            </q-card-actions>
          </q-card>
        </q-dialog>

        <!-- Right Content: Metrics and Charts -->
        <div class="col-12 col-md-9">
          <div class="row q-col-gutter-md">
            <!-- CPU Usage -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="memory" class="q-mr-xs" color="orange" />
                    CPU ({{ status.cpu_count }} Cores)
                  </div>
                </q-card-section>
                <q-card-section class="flex flex-center">
                  <q-circular-progress
                    show-value
                    font-size="16px"
                    :value="status.cpu_average"
                    size="120px"
                    :thickness="0.2"
                    color="orange"
                    track-color="orange-1"
                  >
                    <div class="column items-center">
                      <span class="text-h5 text-weight-bold">{{ status.cpu_average.toFixed(1) }}%</span>
                      <span class="text-caption">Avg</span>
                    </div>
                  </q-circular-progress>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div v-for="(p, i) in status.cpu_percent.slice(0, 4)" :key="i" class="q-mb-xs">
                    <div class="row justify-between text-caption">
                      <span>Core {{ i }}</span>
                      <span>{{ p.toFixed(1) }}%</span>
                    </div>
                    <q-linear-progress :value="p / 100" color="orange" rounded />
                  </div>
                  <div v-if="status.cpu_count > 4" class="text-center text-caption text-grey italic q-mt-xs">
                    + {{ status.cpu_count - 4 }} more cores
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- Memory Usage -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="ram" class="q-mr-xs" color="blue" />
                    {{ t('dashboard.memoryRam') }}
                  </div>
                </q-card-section>
                <q-card-section class="flex flex-center">
                  <q-circular-progress
                    show-value
                    font-size="16px"
                    :value="status.memory.percent"
                    size="120px"
                    :thickness="0.2"
                    color="blue"
                    track-color="blue-1"
                  >
                    <div class="column items-center">
                      <span class="text-h5 text-weight-bold">{{ status.memory.percent.toFixed(1) }}%</span>
                      <span class="text-caption">Used</span>
                    </div>
                  </q-circular-progress>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="column q-gutter-xs">
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Used:</span>
                      <span class="text-weight-bold text-blue">{{ formatBytes(status.memory.used) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Total:</span>
                      <span>{{ formatBytes(status.memory.total) }}</span>
                    </div>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- Disk Usage -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="storage" class="q-mr-xs" color="purple" />
                    {{ t('dashboard.storageDisk') }}
                  </div>
                </q-card-section>
                <q-card-section class="flex flex-center">
                  <q-circular-progress
                    show-value
                    font-size="16px"
                    :value="status.disk.percent"
                    size="120px"
                    :thickness="0.2"
                    color="purple"
                    track-color="purple-1"
                  >
                    <div class="column items-center">
                      <span class="text-h5 text-weight-bold">{{ status.disk.percent.toFixed(1) }}%</span>
                      <span class="text-caption">Filled</span>
                    </div>
                  </q-circular-progress>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="column q-gutter-xs">
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Free:</span>
                      <span class="text-weight-bold text-purple">{{ formatBytes(status.disk.free) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Total:</span>
                      <span>{{ formatBytes(status.disk.total) }}</span>
                    </div>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- Network Traffic -->
            <div class="col-12">
              <q-card flat bordered>
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="swap_calls" class="q-mr-xs" color="green" />
                    {{ t('dashboard.networkTraffic') }}
                  </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="row q-col-gutter-sm">
                    <div class="col-6 col-md-3">
                      <div class="bg-green-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">{{ t('dashboard.sent') }}</div>
                        <div class="text-subtitle1 text-weight-bold">{{ formatBytes(status.network.bytes_sent) }}</div>
                      </div>
                    </div>
                    <div class="col-6 col-md-3">
                      <div class="bg-green-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">{{ t('dashboard.received') }}</div>
                        <div class="text-subtitle1 text-weight-bold">{{ formatBytes(status.network.bytes_recv) }}</div>
                      </div>
                    </div>
                    <div class="col-6 col-md-3">
                      <div class="bg-blue-grey-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">Pkts Sent</div>
                        <div class="text-subtitle1">{{ status.network.packets_sent.toLocaleString() }}</div>
                      </div>
                    </div>
                    <div class="col-6 col-md-3">
                      <div class="bg-blue-grey-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">Pkts Recv</div>
                        <div class="text-subtitle1">{{ status.network.packets_recv.toLocaleString() }}</div>
                      </div>
                    </div>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- History Charts -->
            <div class="col-12 col-md-6">
              <q-card flat bordered>
                <q-card-section class="q-pb-none">
                  <div class="text-subtitle2 text-weight-bold">{{ t('dashboard.cpuHistory') }}</div>
                </q-card-section>
                <q-card-section>
                  <apexchart height="200" :options="baseChartOptions" :series="cpuSeries" />
                </q-card-section>
              </q-card>
            </div>

            <div class="col-12 col-md-6">
              <q-card flat bordered>
                <q-card-section class="q-pb-none">
                  <div class="text-subtitle2 text-weight-bold">{{ t('dashboard.memHistory') }}</div>
                </q-card-section>
                <q-card-section>
                  <apexchart height="200" :options="baseChartOptions" :series="memSeries" />
                </q-card-section>
              </q-card>
            </div>

            <!-- Disk History Chart -->
            <div class="col-12 col-md-6">
              <q-card flat bordered>
                <q-card-section class="q-pb-none">
                  <div class="text-subtitle2 text-weight-bold">
                    <q-icon name="storage" size="xs" class="q-mr-xs" color="purple" />
                    Disk History (1h)
                  </div>
                </q-card-section>
                <q-card-section>
                  <apexchart height="200" :options="baseChartOptions" :series="diskSeries" />
                </q-card-section>
              </q-card>
            </div>

            <!-- Network History Chart -->
            <div class="col-12 col-md-6">
              <q-card flat bordered>
                <q-card-section class="q-pb-none">
                  <div class="text-subtitle2 text-weight-bold">
                    <q-icon name="swap_calls" size="xs" class="q-mr-xs" color="green" />
                    Network History (1h)
                  </div>
                </q-card-section>
                <q-card-section>
                  <apexchart height="200" :options="baseChartOptions" :series="netSeries" />
                </q-card-section>
              </q-card>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════ -->
      <!-- REMOTE SERVER DASHBOARD (192.168.121.11) -->
      <!-- ═══════════════════════════════════════════════════════ -->
      <div class="row q-col-gutter-md q-mt-md">
        <div class="col-12">
          <div class="text-h5 flex items-center">
            <q-icon name="dns" class="q-mr-sm" color="cyan" />
            Remote Server Dashboard
            <q-spacer />
            <q-chip color="cyan-8" text-color="white" icon="router" dense>
              192.168.121.11
            </q-chip>
            <q-btn
              flat round dense
              icon="refresh"
              color="cyan"
              class="q-ml-sm"
              :loading="remoteLoading"
              @click="fetchRemoteStatus"
            />
          </div>
        </div>

        <!-- Remote Server Error -->
        <div v-if="remoteError" class="col-12">
          <q-banner class="bg-red-1 text-red-8 rounded-borders">
            <template v-slot:avatar>
              <q-icon name="warning" color="red" />
            </template>
            <strong>Cannot connect to remote server:</strong> {{ remoteError }}
            <template v-slot:action>
              <q-btn flat label="Retry" color="red" @click="fetchRemoteStatus" />
            </template>
          </q-banner>
        </div>

        <!-- Remote Server Loading -->
        <template v-if="remoteLoading && !remoteStatus && !remoteError">
          <div class="col-12 col-md-4" v-for="n in 3" :key="'rskel-'+n">
            <q-card flat bordered class="full-height">
              <q-card-section>
                <q-skeleton type="text" width="60%" />
              </q-card-section>
              <q-card-section class="flex flex-center">
                <q-skeleton type="circle" size="120px" />
              </q-card-section>
              <q-card-section>
                <q-skeleton type="text" :count="3" />
              </q-card-section>
            </q-card>
          </div>
        </template>

        <template v-if="remoteStatus">
          <!-- Remote PC Info -->
          <div class="col-12 col-md-3">
            <q-card flat bordered class="remote-info-card full-height">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="computer" class="q-mr-xs" />
                  Server Info
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">Hostname</div>
                  <div class="text-subtitle2">{{ remoteStatus.hostname }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">IP Address</div>
                  <div class="text-subtitle2">{{ remoteStatus.local_ip }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">OS</div>
                  <div class="text-subtitle2">{{ remoteStatus.os }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">Architecture</div>
                  <div class="text-subtitle2">{{ remoteStatus.architecture }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">CPU Model</div>
                  <div class="text-subtitle2" style="font-size: 0.75rem;">{{ remoteStatus.cpu_model }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">Python</div>
                  <div class="text-subtitle2">{{ remoteStatus.python_version }}</div>
                </div>
                <div class="q-mb-xs">
                  <div class="text-caption opacity-70">Boot Time</div>
                  <div class="text-subtitle2">{{ formatDateTime(remoteStatus.boot_time * 1000) }}</div>
                </div>
              </q-card-section>
            </q-card>
          </div>

          <!-- Remote Metrics -->
          <div class="col-12 col-md-9">
            <div class="row q-col-gutter-md">
              <!-- Remote CPU Usage -->
              <div class="col-12 col-md-4">
                <q-card flat bordered class="full-height">
                  <q-card-section>
                    <div class="text-subtitle1 text-weight-bold flex items-center">
                      <q-icon name="memory" class="q-mr-xs" color="cyan" />
                      CPU ({{ remoteStatus.cpu_count }} Cores)
                    </div>
                  </q-card-section>
                  <q-card-section class="flex flex-center">
                    <q-circular-progress
                      show-value
                      font-size="16px"
                      :value="remoteStatus.cpu_average"
                      size="120px"
                      :thickness="0.2"
                      color="cyan"
                      track-color="cyan-1"
                    >
                      <div class="column items-center">
                        <span class="text-h5 text-weight-bold">{{ remoteStatus.cpu_average.toFixed(1) }}%</span>
                        <span class="text-caption">Avg</span>
                      </div>
                    </q-circular-progress>
                  </q-card-section>
                  <q-card-section class="q-pt-none">
                    <div v-for="(p, i) in remoteStatus.cpu_percent.slice(0, 4)" :key="'rc-'+i" class="q-mb-xs">
                      <div class="row justify-between text-caption">
                        <span>Core {{ i }}</span>
                        <span>{{ p.toFixed(1) }}%</span>
                      </div>
                      <q-linear-progress :value="p / 100" color="cyan" rounded />
                    </div>
                    <div v-if="remoteStatus.cpu_count > 4" class="text-center text-caption text-grey italic q-mt-xs">
                      + {{ remoteStatus.cpu_count - 4 }} more cores
                    </div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- Remote Memory Usage -->
              <div class="col-12 col-md-4">
                <q-card flat bordered class="full-height">
                  <q-card-section>
                    <div class="text-subtitle1 text-weight-bold flex items-center">
                      <q-icon name="memory" class="q-mr-xs" color="light-blue" />
                      Memory (RAM)
                    </div>
                  </q-card-section>
                  <q-card-section class="flex flex-center">
                    <q-circular-progress
                      show-value
                      font-size="16px"
                      :value="remoteStatus.memory.percent"
                      size="120px"
                      :thickness="0.2"
                      color="light-blue"
                      track-color="light-blue-1"
                    >
                      <div class="column items-center">
                        <span class="text-h5 text-weight-bold">{{ remoteStatus.memory.percent.toFixed(1) }}%</span>
                        <span class="text-caption">Used</span>
                      </div>
                    </q-circular-progress>
                  </q-card-section>
                  <q-card-section class="q-pt-none">
                    <div class="column q-gutter-xs">
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Used:</span>
                        <span class="text-weight-bold text-light-blue">{{ formatBytes(remoteStatus.memory.used) }}</span>
                      </div>
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Available:</span>
                        <span>{{ formatBytes(remoteStatus.memory.available) }}</span>
                      </div>
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Total:</span>
                        <span>{{ formatBytes(remoteStatus.memory.total) }}</span>
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- Remote Disk Usage -->
              <div class="col-12 col-md-4">
                <q-card flat bordered class="full-height">
                  <q-card-section>
                    <div class="text-subtitle1 text-weight-bold flex items-center">
                      <q-icon name="storage" class="q-mr-xs" color="deep-purple" />
                      Storage (Disk)
                    </div>
                  </q-card-section>
                  <q-card-section class="flex flex-center">
                    <q-circular-progress
                      show-value
                      font-size="16px"
                      :value="remoteStatus.disk.percent"
                      size="120px"
                      :thickness="0.2"
                      color="deep-purple"
                      track-color="deep-purple-1"
                    >
                      <div class="column items-center">
                        <span class="text-h5 text-weight-bold">{{ remoteStatus.disk.percent.toFixed(1) }}%</span>
                        <span class="text-caption">Filled</span>
                      </div>
                    </q-circular-progress>
                  </q-card-section>
                  <q-card-section class="q-pt-none">
                    <div class="column q-gutter-xs">
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Free:</span>
                        <span class="text-weight-bold text-deep-purple">{{ formatBytes(remoteStatus.disk.free) }}</span>
                      </div>
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Used:</span>
                        <span>{{ formatBytes(remoteStatus.disk.used) }}</span>
                      </div>
                      <div class="row justify-between text-caption">
                        <span class="text-grey-7">Total:</span>
                        <span>{{ formatBytes(remoteStatus.disk.total) }}</span>
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- Remote Network Traffic -->
              <div class="col-12">
                <q-card flat bordered>
                  <q-card-section>
                    <div class="text-subtitle1 text-weight-bold flex items-center">
                      <q-icon name="swap_calls" class="q-mr-xs" color="teal" />
                      Network Traffic
                    </div>
                  </q-card-section>
                  <q-card-section class="q-pt-none">
                    <div class="row q-col-gutter-sm">
                      <div class="col-6 col-md-3">
                        <div class="bg-teal-1 q-pa-sm rounded-borders">
                          <div class="text-caption text-grey-7">Sent</div>
                          <div class="text-subtitle1 text-weight-bold">{{ formatBytes(remoteStatus.network.bytes_sent) }}</div>
                        </div>
                      </div>
                      <div class="col-6 col-md-3">
                        <div class="bg-teal-1 q-pa-sm rounded-borders">
                          <div class="text-caption text-grey-7">Received</div>
                          <div class="text-subtitle1 text-weight-bold">{{ formatBytes(remoteStatus.network.bytes_recv) }}</div>
                        </div>
                      </div>
                      <div class="col-6 col-md-3">
                        <div class="bg-blue-grey-1 q-pa-sm rounded-borders">
                          <div class="text-caption text-grey-7">Pkts Sent</div>
                          <div class="text-subtitle1">{{ remoteStatus.network.packets_sent.toLocaleString() }}</div>
                        </div>
                      </div>
                      <div class="col-6 col-md-3">
                        <div class="bg-blue-grey-1 q-pa-sm rounded-borders">
                          <div class="text-caption text-grey-7">Pkts Recv</div>
                          <div class="text-subtitle1">{{ remoteStatus.network.packets_recv.toLocaleString() }}</div>
                        </div>
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Placeholder content during server render -->
      <template #fallback>
        <div class="flex flex-center" style="height: 80vh">
          <q-spinner-gears size="100px" color="primary" />
          <div class="text-h6 q-ml-md">{{ t('dashboard.loadingMetrics') }}</div>
        </div>
      </template>
    </ClientOnly>
    
    <div v-if="error" class="q-pa-md text-red text-center">
      <q-icon name="error" size="lg" />
      <div class="text-h6">{{ t('dashboard.errorConnecting') }}</div>
      <p>{{ error }}</p>
      <q-btn :label="t('dashboard.retry')" color="primary" @click="fetchStatus" />
    </div>
  </q-page>
</template>

<style scoped>
.full-height {
  height: 100%;
}
.opacity-70 {
  opacity: 0.7;
}
.active-db-card {
  background: linear-gradient(135deg, #1a237e 0%, #0d47a1 50%, #01579b 100%);
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
.active-db-card .q-btn--outline {
  border-color: rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.7);
}
.active-db-card .q-btn--outline:hover {
  border-color: rgba(255, 255, 255, 0.6);
  color: white;
  background: rgba(255, 255, 255, 0.1);
}
.remote-info-card {
  background: linear-gradient(135deg, #004d40 0%, #00695c 50%, #00897b 100%);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.12);
}
</style>

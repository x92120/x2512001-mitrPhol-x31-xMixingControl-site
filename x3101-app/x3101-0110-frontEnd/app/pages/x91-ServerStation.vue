<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'

const $q = useQuasar()
const { t } = useI18n()
const DB_NAME = 'xMixingControl'

interface StationStatus {
  host: string
  ping: {
    reachable: boolean
    packet_loss: string
    latency: { min: number; avg: number; max: number } | null
  }
  mysql: {
    connected: boolean
    connect_time_ms?: number
    version?: string
    uptime?: string
    uptime_seconds?: number
    connections?: {
      current: number
      max: number
      sleeping: number
      active_queries: number
      total_connections: number
      aborted_connects: number
    }
    queries?: {
      total: number
      selects: number
      inserts: number
      updates: number
      deletes: number
      slow_queries: number
    }
    traffic?: {
      bytes_received: number
      bytes_sent: number
    }
    innodb?: {
      buffer_pool_size: number
      buffer_pool_reads: number
      buffer_pool_read_requests: number
      row_lock_waits: number
    }
    databases?: any[]
    top_tables?: any[]
    error?: string
  }
}

const status = ref<StationStatus | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let pollTimer: any = null

const formatBytes = (bytes: number, decimals = 2) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

const formatNumber = (n: number | undefined) => {
  if (!n) return '0'
  return n.toLocaleString()
}

const connectionPercent = computed(() => {
  if (!status.value?.mysql?.connections) return 0
  const { current, max } = status.value.mysql.connections
  return max > 0 ? Math.round((current / max) * 100) : 0
})

const bufferHitRate = computed(() => {
  if (!status.value?.mysql?.innodb) return 0
  const { buffer_pool_reads, buffer_pool_read_requests } = status.value.mysql.innodb
  if (buffer_pool_read_requests === 0) return 100
  return Math.round((1 - buffer_pool_reads / buffer_pool_read_requests) * 10000) / 100
})

const fetchStatus = async () => {
  try {
    const data = await $fetch<StationStatus>(`${appConfig.apiBaseUrl}/server-station/status`)
    status.value = data
    error.value = null
  } catch (e: any) {
    error.value = e?.message || 'Failed to fetch'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <q-page class="q-pa-md">
    <ClientOnly>
      <!-- Header -->
      <div class="row items-center q-mb-md">
        <q-icon name="dns" size="md" color="teal" class="q-mr-sm" />
        <div class="text-h5">Server Station Monitor</div>
        <q-spacer />
        <q-chip v-if="status?.host" dense icon="location_on" color="teal" text-color="white">
          {{ status.host }}
        </q-chip>
        <q-btn flat round icon="refresh" @click="fetchStatus" :loading="loading" class="q-ml-sm" />
      </div>

      <div v-if="loading && !status" class="flex flex-center" style="height: 60vh;">
        <q-spinner-gears size="80px" color="teal" />
        <div class="text-h6 q-ml-md">Connecting to server station...</div>
      </div>

      <div v-else-if="status" class="row q-col-gutter-md">

        <!-- ═══ Left Column: Connection & MySQL Info ═══ -->
        <div class="col-12 col-md-3">
          <div class="column q-gutter-md">

            <!-- Network Status -->
            <q-card flat bordered :class="status.ping.reachable ? 'bg-green-9 text-white' : 'bg-red-9 text-white'">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon :name="status.ping.reachable ? 'wifi' : 'wifi_off'" class="q-mr-xs" />
                  Network Status
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="row justify-between q-mb-xs">
                  <span class="text-caption opacity-80">Status</span>
                  <q-badge :color="status.ping.reachable ? 'green-13' : 'red-13'" :label="status.ping.reachable ? 'ONLINE' : 'OFFLINE'" />
                </div>
                <div class="row justify-between q-mb-xs">
                  <span class="text-caption opacity-80">Packet Loss</span>
                  <span class="text-subtitle2">{{ status.ping.packet_loss }}</span>
                </div>
                <div v-if="status.ping.latency" class="row justify-between q-mb-xs">
                  <span class="text-caption opacity-80">Latency (avg)</span>
                  <span class="text-subtitle2">{{ status.ping.latency.avg.toFixed(1) }} ms</span>
                </div>
                <div v-if="status.ping.latency" class="row justify-between">
                  <span class="text-caption opacity-80">Min / Max</span>
                  <span class="text-caption">{{ status.ping.latency.min.toFixed(1) }} / {{ status.ping.latency.max.toFixed(1) }} ms</span>
                </div>
              </q-card-section>
            </q-card>

            <!-- MySQL Status -->
            <q-card flat bordered :class="status.mysql.connected ? 'bg-blue-9 text-white' : 'bg-grey-7 text-white'">
              <q-card-section>
                <div class="text-subtitle1 text-weight-bold flex items-center">
                  <q-icon name="storage" class="q-mr-xs" />
                  MySQL Server
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none" v-if="status.mysql.connected">
                <div class="q-mb-sm">
                  <div class="text-caption opacity-80">Version</div>
                  <div class="text-subtitle2">{{ status.mysql.version }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-80">Uptime</div>
                  <div class="text-subtitle2">{{ status.mysql.uptime }}</div>
                </div>
                <div class="q-mb-sm">
                  <div class="text-caption opacity-80">Connect Time</div>
                  <div class="text-subtitle2">{{ status.mysql.connect_time_ms }} ms</div>
                </div>
              </q-card-section>
              <q-card-section class="q-pt-none" v-else>
                <div class="text-center">
                  <q-icon name="error" size="xl" />
                  <div class="text-caption q-mt-sm">{{ status.mysql.error }}</div>
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- ═══ Right Column: Metrics ═══ -->
        <div class="col-12 col-md-9" v-if="status.mysql.connected">
          <div class="row q-col-gutter-md">

            <!-- Connections Gauge -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="people" class="q-mr-xs" color="orange" />
                    Connections
                  </div>
                </q-card-section>
                <q-card-section class="flex flex-center">
                  <q-circular-progress
                    show-value font-size="14px"
                    :value="connectionPercent" size="110px" :thickness="0.2"
                    color="orange" track-color="orange-1"
                  >
                    <div class="column items-center">
                      <span class="text-h5 text-weight-bold">{{ status.mysql.connections?.current }}</span>
                      <span class="text-caption">/ {{ status.mysql.connections?.max }}</span>
                    </div>
                  </q-circular-progress>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Active Queries</span>
                    <span class="text-weight-bold text-orange">{{ status.mysql.connections?.active_queries }}</span>
                  </div>
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Sleeping</span>
                    <span>{{ status.mysql.connections?.sleeping }}</span>
                  </div>
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Total (since boot)</span>
                    <span>{{ formatNumber(status.mysql.connections?.total_connections) }}</span>
                  </div>
                  <div class="row justify-between text-caption">
                    <span class="text-grey-7">Aborted</span>
                    <span :class="(status.mysql.connections?.aborted_connects || 0) > 0 ? 'text-red' : ''">{{ status.mysql.connections?.aborted_connects }}</span>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- InnoDB Buffer Hit Rate -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="speed" class="q-mr-xs" color="green" />
                    InnoDB Performance
                  </div>
                </q-card-section>
                <q-card-section class="flex flex-center">
                  <q-circular-progress
                    show-value font-size="14px"
                    :value="bufferHitRate" size="110px" :thickness="0.2"
                    :color="bufferHitRate > 99 ? 'green' : bufferHitRate > 95 ? 'orange' : 'red'"
                    track-color="green-1"
                  >
                    <div class="column items-center">
                      <span class="text-h5 text-weight-bold">{{ bufferHitRate }}%</span>
                      <span class="text-caption">Hit Rate</span>
                    </div>
                  </q-circular-progress>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Buffer Pool</span>
                    <span class="text-weight-bold">{{ formatBytes(status.mysql.innodb?.buffer_pool_size || 0) }}</span>
                  </div>
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Read Requests</span>
                    <span>{{ formatNumber(status.mysql.innodb?.buffer_pool_read_requests) }}</span>
                  </div>
                  <div class="row justify-between text-caption q-mb-xs">
                    <span class="text-grey-7">Disk Reads</span>
                    <span>{{ formatNumber(status.mysql.innodb?.buffer_pool_reads) }}</span>
                  </div>
                  <div class="row justify-between text-caption">
                    <span class="text-grey-7">Row Lock Waits</span>
                    <span :class="(status.mysql.innodb?.row_lock_waits || 0) > 0 ? 'text-orange' : ''">{{ status.mysql.innodb?.row_lock_waits }}</span>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- Query Stats -->
            <div class="col-12 col-md-4">
              <q-card flat bordered class="full-height">
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="query_stats" class="q-mr-xs" color="purple" />
                    Query Stats
                  </div>
                </q-card-section>
                <q-card-section>
                  <div class="column q-gutter-sm">
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Total Queries</span>
                      <span class="text-weight-bold text-purple">{{ formatNumber(status.mysql.queries?.total) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">SELECT</span>
                      <span>{{ formatNumber(status.mysql.queries?.selects) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">INSERT</span>
                      <span>{{ formatNumber(status.mysql.queries?.inserts) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">UPDATE</span>
                      <span>{{ formatNumber(status.mysql.queries?.updates) }}</span>
                    </div>
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">DELETE</span>
                      <span>{{ formatNumber(status.mysql.queries?.deletes) }}</span>
                    </div>
                    <q-separator />
                    <div class="row justify-between text-caption">
                      <span class="text-grey-7">Slow Queries</span>
                      <span :class="(status.mysql.queries?.slow_queries || 0) > 0 ? 'text-red text-weight-bold' : ''">{{ status.mysql.queries?.slow_queries }}</span>
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
                    <q-icon name="swap_calls" class="q-mr-xs" color="cyan" />
                    MySQL Traffic (since boot)
                  </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="row q-col-gutter-sm">
                    <div class="col-6">
                      <div class="bg-cyan-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">Received</div>
                        <div class="text-subtitle1 text-weight-bold">{{ formatBytes(status.mysql.traffic?.bytes_received || 0) }}</div>
                      </div>
                    </div>
                    <div class="col-6">
                      <div class="bg-cyan-1 q-pa-sm rounded-borders">
                        <div class="text-caption text-grey-7">Sent</div>
                        <div class="text-subtitle1 text-weight-bold">{{ formatBytes(status.mysql.traffic?.bytes_sent || 0) }}</div>
                      </div>
                    </div>
                  </div>
                </q-card-section>
              </q-card>
            </div>

            <!-- Database Sizes -->
            <div class="col-12 col-md-5" v-if="status.mysql.databases?.length">
              <q-card flat bordered>
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="database" class="q-mr-xs" color="indigo" />
                    Databases
                  </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <q-list dense separator>
                    <q-item v-for="db in status.mysql.databases" :key="db.db_name">
                      <q-item-section>
                        <q-item-label class="text-weight-bold">{{ db.db_name }}</q-item-label>
                        <q-item-label caption>{{ db.table_count }} tables · {{ formatNumber(db.total_rows) }} rows</q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <q-badge color="indigo" :label="`${db.size_mb} MB`" />
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-card-section>
              </q-card>
            </div>

            <!-- Top Tables -->
            <div class="col-12 col-md-7" v-if="status.mysql.top_tables?.length">
              <q-card flat bordered>
                <q-card-section>
                  <div class="text-subtitle1 text-weight-bold flex items-center">
                    <q-icon name="table_chart" class="q-mr-xs" color="teal" />
                    Top Tables ({{ DB_NAME }})
                  </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <q-markup-table dense flat separator="horizontal" class="text-caption">
                    <thead>
                      <tr>
                        <th class="text-left">Table</th>
                        <th class="text-right">Rows</th>
                        <th class="text-right">Size</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="tbl in status.mysql.top_tables" :key="tbl.table_name">
                        <td class="text-left text-weight-medium">{{ tbl.table_name }}</td>
                        <td class="text-right">{{ formatNumber(tbl.table_rows) }}</td>
                        <td class="text-right">{{ tbl.size_mb }} MB</td>
                      </tr>
                    </tbody>
                  </q-markup-table>
                </q-card-section>
              </q-card>
            </div>

          </div>
        </div>
      </div>

      <!-- Error State -->
      <div v-if="error && !status" class="q-pa-lg text-center">
        <q-icon name="error_outline" size="64px" color="red" />
        <div class="text-h6 q-mt-md">Cannot connect to Server Station</div>
        <div class="text-grey q-mt-sm">{{ error }}</div>
        <q-btn label="Retry" color="primary" class="q-mt-md" @click="fetchStatus" />
      </div>

      <template #fallback>
        <div class="flex flex-center" style="height: 60vh;">
          <q-spinner-gears size="80px" color="teal" />
          <div class="text-h6 q-ml-md">Loading server monitor...</div>
        </div>
      </template>
    </ClientOnly>
  </q-page>
</template>


<style scoped>
.full-height { height: 100%; }
</style>

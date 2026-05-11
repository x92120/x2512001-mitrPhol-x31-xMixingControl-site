<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { appConfig } from '~/appConfig/config'

const $q = useQuasar()
const { getAuthHeader } = useAuth()

// State
const loading = ref(false)
const batches = ref<any[]>([])
const selectedBatch = ref<any>(null)
const stepLogs = ref<any[]>([])

// Filters
const filterDate = ref('')
const filterStatus = ref('All')

// Table columns
const columns = [
  { name: 'batch_id', label: 'Batch ID', align: 'left', field: 'batch_id', sortable: true },
  { name: 'sku_name', label: 'Product Name', align: 'left', field: 'sku_name', sortable: true },
  { name: 'plan_id', label: 'Plan ID', align: 'left', field: 'plan_id' },
  { name: 'batch_size', label: 'Target Weight (kg)', align: 'right', field: 'batch_size' },
  { name: 'status', label: 'Status', align: 'center', field: 'status' },
  { name: 'actions', label: 'View Record', align: 'center' }
]

const loadBatches = async () => {
  loading.value = true
  try {
    const remoteApiBaseUrl = appConfig.apiBaseUrl
    // For now, load from production plan to simulate the batch history
    const res = await $fetch<any[]>(`${remoteApiBaseUrl}/production-plans`, {
      headers: getAuthHeader() as Record<string, string>
    })
    
    // Flatten batches from plans for display
    const flatBatches: any[] = []
    res.forEach(plan => {
      if (plan.batches) {
        plan.batches.forEach((b: any) => {
          flatBatches.push({
            ...b,
            sku_name: plan.sku_name || 'Unknown SKU',
            plan_id: plan.plan_id
          })
        })
      }
    })
    batches.value = flatBatches
  } catch (e) {
    console.error('Failed to load batches', e)
    $q.notify({ type: 'negative', message: 'Failed to load batch data' })
  } finally {
    loading.value = false
  }
}

const viewBatchRecord = async (batch: any) => {
  selectedBatch.value = batch
  loading.value = true
  
    // Fetch the real logs from backend
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        const logRes = await $fetch<any>(`${remoteApiBaseUrl}/production-batches/${batch.batch_id}/logs`, {
            headers: getAuthHeader() as Record<string, string>
        })
        
        // Merge logs and qc_records for display
        const qcMap: Record<number, any> = {}
        if (logRes.qc_records) {
            logRes.qc_records.forEach((qc: any) => {
                qcMap[qc.step_id] = qc
            })
        }
        
        stepLogs.value = (logRes.logs || []).map((s: any) => {
            const date = new Date(s.completed_at)
            const qc = qcMap[s.step_id]
            return {
                phase_number: s.phase_id,
                sub_step: s.step_id,
                action: `Action ${s.action_code || '-'}`,
                action_code: s.action_code,
                re_code: s.re_code,
                require: s.target_value,
                temperature: '-',
                actual_temp: s.actual_value,
                operator: s.operator || 'operator',
                timestamp: date.toLocaleTimeString(),
                brix: qc ? qc.brix_actual : undefined,
                ph: qc ? qc.ph_actual : undefined
            }
        })
        
    } catch(e) {
        console.error('Failed to load batch logs', e)
    } finally {
        loading.value = false
    }
}

const closeRecord = () => {
  selectedBatch.value = null
  stepLogs.value = []
}

onMounted(() => {
  loadBatches()
})

</script>

<template>
  <q-page padding class="bg-grey-2" style="font-family: 'Inter', sans-serif;">
    <div class="row items-center q-mb-md">
      <q-icon name="assessment" size="40px" color="indigo-8" class="q-mr-sm" />
      <div>
        <h4 class="text-h5 text-weight-bolder text-indigo-10 q-my-none">Production Batch Records</h4>
        <div class="text-caption text-grey-7">View historical execution logs and quality reports</div>
      </div>
      <q-space />
      <q-btn color="primary" icon="refresh" label="Refresh" unelevated @click="loadBatches" />
    </div>

    <!-- MAIN BATCH LIST -->
    <q-card v-if="!selectedBatch" class="shadow-2" style="border-radius: 12px;">
      <q-table
        :rows="batches"
        :columns="columns"
        row-key="batch_id"
        :loading="loading"
        flat
        :pagination="{ rowsPerPage: 15 }"
        table-header-class="bg-indigo-1 text-indigo-10 text-weight-bold"
      >
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-chip 
              dense 
              :color="props.row.status === 'Completed' ? 'positive' : props.row.status === 'In Progress' ? 'warning' : 'grey'" 
              text-color="white"
            >
              {{ props.row.status || 'Pending' }}
            </q-chip>
          </q-td>
        </template>
        
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
            <q-btn dense outline color="primary" icon="visibility" label="View Record" @click="viewBatchRecord(props.row)" />
          </q-td>
        </template>
      </q-table>
    </q-card>

    <!-- BATCH RECORD DETAIL VIEW -->
    <q-card v-else class="shadow-2" style="border-radius: 12px; overflow: hidden;">
      <div class="bg-indigo-9 text-white q-pa-md row items-center">
        <q-btn flat round dense icon="arrow_back" color="white" @click="closeRecord" class="q-mr-md" />
        <div>
          <div class="text-h6 text-weight-bold">Batch Record: {{ selectedBatch.batch_id }}</div>
          <div class="text-caption text-indigo-2">{{ selectedBatch.sku_name }} • Plan: {{ selectedBatch.plan_id }}</div>
        </div>
        <q-space />
        <q-btn outline color="white" icon="print" label="Print Report" class="q-mr-sm" @click="() => window.print()" />
        <q-btn color="green-13" text-color="black" icon="download" label="Export PDF" unelevated />
      </div>

      <q-card-section class="bg-indigo-1">
        <div class="row q-col-gutter-md">
           <div class="col-3">
             <div class="text-caption text-indigo-8 text-weight-bold">Target Weight</div>
             <div class="text-h6">{{ selectedBatch.batch_size }} kg</div>
           </div>
           <div class="col-3">
             <div class="text-caption text-indigo-8 text-weight-bold">Date Executed</div>
             <div class="text-h6">{{ new Date().toLocaleDateString() }}</div>
           </div>
           <div class="col-3">
             <div class="text-caption text-indigo-8 text-weight-bold">Plant Line</div>
             <div class="text-h6">MIX-1</div>
           </div>
           <div class="col-3">
             <div class="text-caption text-indigo-8 text-weight-bold">Final Status</div>
             <q-chip color="positive" text-color="white" icon="check_circle">Verified</q-chip>
           </div>
        </div>
      </q-card-section>

      <q-separator />

      <div class="q-pa-md">
        <div class="text-subtitle1 text-weight-bold q-mb-sm text-grey-8">Execution Trace Log</div>
        <q-markup-table flat bordered class="rounded-borders">
          <thead class="bg-grey-2">
            <tr>
              <th class="text-left">Phase/Step</th>
              <th class="text-left">Action</th>
              <th class="text-left">Material / Target</th>
              <th class="text-center">Set Temp (°C)</th>
              <th class="text-center text-green-8">Act Temp (°C)</th>
              <th class="text-center">Operator</th>
              <th class="text-center">QC (Brix / pH)</th>
              <th class="text-center">Timestamp</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(step, i) in stepLogs" :key="i">
              <td class="text-left">
                <div class="text-weight-bold">P{{ step.phase_number }}</div>
                <div class="text-caption text-grey">S{{ step.sub_step }}</div>
              </td>
              <td class="text-left">
                <q-badge :color="step.action_code == 21010 ? 'orange' : 'primary'">{{ step.action }}</q-badge>
              </td>
              <td class="text-left">
                <div v-if="step.re_code" class="text-weight-bold">{{ step.re_code }}</div>
                <div v-if="step.require">{{ step.require }} kg</div>
                <div v-else-if="!step.re_code" class="text-caption text-grey">Process Only</div>
              </td>
              <td class="text-center">{{ step.temperature || '-' }}</td>
              <td class="text-center text-weight-bold text-green-8">{{ step.actual_temp }}</td>
              <td class="text-center">
                <q-chip dense size="sm" icon="person">{{ step.operator }}</q-chip>
              </td>
              <td class="text-center">
                <div v-if="step.brix !== undefined" class="text-indigo-8 text-weight-bold">Brix: {{ step.brix }}</div>
                <div v-if="step.ph !== undefined" class="text-indigo-8 text-weight-bold">pH: {{ step.ph }}</div>
                <div v-if="step.brix === undefined && step.ph === undefined" class="text-grey">-</div>
              </td>
              <td class="text-center text-mono text-grey-8">{{ step.timestamp }}</td>
            </tr>
          </tbody>
        </q-markup-table>
      </div>

    </q-card>
  </q-page>
</template>

<style scoped>
@media print {
  .q-page { padding: 0 !important; }
  .bg-indigo-9 { background: white !important; color: black !important; border-bottom: 2px solid black; }
  .q-btn { display: none !important; }
  .shadow-2 { box-shadow: none !important; border: 1px solid #ccc; }
}
</style>

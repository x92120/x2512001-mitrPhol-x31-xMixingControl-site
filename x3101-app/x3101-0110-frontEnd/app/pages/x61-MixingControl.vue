<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useRoute, useRouter } from 'vue-router'
import { useMQTT } from '~/composables/useMQTT'

const route = useRoute()
const router = useRouter()

// ── PLC Connection via Shared MQTT Composable ──
const { connect, disconnect, publishMessage, isConnected: plcConnectedGlobal, plantsData, onMessage, offMessage } = useMQTT()
const { getAuthHeader, user } = useAuth()
const $q = useQuasar()

// ── State ──
const selectedBatchId = ref<string | null>(null)
const selectedSkuId = ref<string | null>(null)
const batchInfo = ref<any>(null)
const skuSteps = ref<any[]>([])
const loading = ref(false)

const activePlantId = computed(() => {
    let plantStr = '1';
    if (batchInfo.value && batchInfo.value.plant) {
        plantStr = String(batchInfo.value.plant).replace(/\D/g, '') || '1'
    } else if (route.query.plant) {
        plantStr = (route.query.plant as string)?.replace(/\D/g, '') || '1'
    }
    return String(Number(plantStr))
})
const plantData = computed(() => (plantsData.value[activePlantId.value] || {}) as any)

const actualAgitatorRpm = computed(() => plantData.value.MixingTank?.['Agitator Speed'] || plantData.value.MixingTank_Agitator_Speed || 0)
const actualHighShearRpm = computed(() => plantData.value.HighShare?.Speed || plantData.value.HighShare_Speed || 0)
const actualHighShearTemp = computed(() => plantData.value.HighShare?.Temperature || plantData.value.HighShare_Temperature || plantData.value.actual_high_shear_temp || 0)
const actualTankWeight = computed(() => plantData.value.MixingTank?.Scale || plantData.value.Mixing_Tank_Weight || plantData.value.Mixing_Tank_Volume || 0)
const actualHopperWeight = computed(() => plantData.value.HopperScale || plantData.value.Hopper_Weight || plantData.value.actual_hopper_weight || 0)
const actualCirculationSpeed = computed(() => plantData.value.Circulation?.['Pump Speed'] || plantData.value.Circulation_Speed || plantData.value.actual_circulation_speed || 0)
const actualFlowRate = computed(() => plantData.value.Circulation?.FlowRate || plantData.value.Flow_Rate || plantData.value.actual_flow_rate || 0)
const actualCirculationTemp = computed(() => plantData.value.Circulation?.TemPerature || plantData.value.Circulation_Temperature || plantData.value.actual_circulation_temp || 0)
const actualTankTemp = computed(() => plantData.value.MixingTank?.Temperature || plantData.value.Mixing_Tank_Temperature || 0)
const watchdog = computed(() => plantData.value['Watch-Dog'] || plantData.value.watchdog || 0)
const isPlcConnected = computed(() => plcConnectedGlobal.value && !!plantData.value.last_update)

// ── Fetch Batch Info from Edge Buffer ──
const fetchBatchInfo = async () => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl || 'http://127.0.0.1:8001'
        const data = await $fetch<any>(`${remoteApiBaseUrl}/edge/active-batch`, {
             headers: getAuthHeader() as Record<string, string>
        })
        if (data) {
            batchInfo.value = { 
                batch_id: data.batch_id,
                plan_id: data.plan_id || '-', 
                sku_id: data.sku_code, 
                sku_name: data.sku_name || '-', 
                plant: '0' + data.plant_id,
                batch_size: data.target_total_weight
            }
            selectedBatchId.value = data.batch_id
            selectedSkuId.value = data.sku_code
            fetchSkuSteps(data.sku_code)
            fetchSkuSteps(data.sku_code)
        } else {
            throw new Error("No edge batch data")
        }
    } catch (e) {
        console.warn('Could not fetch from edge API, falling back to query params.')
        const qBatchId = route.query.batch_id as string
        const qSkuId = route.query.sku_id as string
        if (qBatchId && qSkuId) {
            batchInfo.value = { 
                batch_id: qBatchId,
                plan_id: '-', 
                sku_id: qSkuId, 
                sku_name: 'Fallback Simulator Mode', 
                plant: '01',
                batch_size: 1000
            }
            selectedBatchId.value = qBatchId
            selectedSkuId.value = qSkuId
            fetchSkuSteps(qSkuId)
        } else {
            batchInfo.value = null
            selectedBatchId.value = null
            skuSteps.value = []
        }
    } finally {
        loading.value = false
    }
}

// ── Fetch SKU steps ──
const fetchSkuSteps = async (skuId: string) => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl || 'http://127.0.0.1:8001'
        // Fallback to central API directly since Edge buffer is failing
        const endpoint = `${remoteApiBaseUrl}/sku-steps/?sku_id=${skuId}`
        const data = await $fetch<any[]>(endpoint, {
            headers: getAuthHeader() as Record<string, string>
        })
        // Sort steps globally by phase then sub-step so the index matches the visual order
        const sortedSteps = (data || []).sort((a: any, b: any) => {
            const phA = String(a.phase_number || '0')
            const phB = String(b.phase_number || '0')
            const phCompare = phA.localeCompare(phB, undefined, { numeric: true })
            if (phCompare !== 0) return phCompare
            return (a.sub_step || 0) - (b.sub_step || 0)
        })
        skuSteps.value = sortedSteps
    } catch { skuSteps.value = [] }
    finally { loading.value = false }
}

// ── Group steps by phase ──
const skuStepsByPhase = computed(() => {
    const groups: Record<string, { phase: string, phase_id: string, steps: any[] }> = {}
    for (const step of skuSteps.value) {
        const ph = step.phase_number || '0'
        if (!groups[ph]) groups[ph] = { phase: ph, phase_id: step.phase_id || '', steps: [] }
        groups[ph].steps.push(step)
    }
    const sorted = Object.values(groups).sort((a, b) =>
        String(a.phase).localeCompare(String(b.phase), undefined, { numeric: true })
    )
    for (const g of sorted) g.steps.sort((a: any, b: any) => (a.sub_step || 0) - (b.sub_step || 0))
    return sorted
})

const totalSteps = computed(() => skuSteps.value.length)

// ── Current Operation (simulated) ──
// Helper: find step index exactly matching PLC Step_No (which corresponds to Step Requirement tracking)
const currentStepIndex = computed(() => Math.max(0, Number(plantData.value.Step_No || plantData.value.Step_no || 0) - 1))
let stepInterval: ReturnType<typeof setInterval> | null = null

const currentStep = computed(() => {
    if (skuSteps.value.length === 0) return null
    return skuSteps.value[currentStepIndex.value % skuSteps.value.length] || null
})

const currentPhaseGroup = computed(() => {
    if (!currentStep.value) return null
    return skuStepsByPhase.value.find(g => g.phase === (currentStep.value?.phase_number || '0')) || null
})

const stepProgress = computed(() => {
    if (skuSteps.value.length === 0) return 0
    return (currentStepIndex.value + 1) / skuSteps.value.length
})

const expandedPhases = ref<Record<string, boolean>>({})
const togglePhase = (phase: string) => {
    expandedPhases.value[phase] = expandedPhases.value[phase] === false ? true : false
}
const isPhaseExpanded = (phase: string) => {
    return expandedPhases.value[phase] !== false
}

// ── QC Trap Logic ──
const qcDialog = ref(false)
const pendingQcStep = ref<any | null>(null)

const handlePlcMessage = (topic: string, payload: any) => {
    // Listen for step complete confirmation
    if (topic === `mixing/plant/${activePlantId.value}/status` && payload.status === 'STEP_COMPLETE') {
        if (!batchRunning.value) return; // If aborted/stopped, ignore

        $q.notify({ type: 'info', message: `Step ${payload.step_no} completed.`, position: 'top', timeout: 1000 })
        
        const completedIndex = Number(payload.step_no) - 1;
        const currentCompletedStep = skuSteps.value[completedIndex];

        // Check if the COMPLETED step required a QC record BEFORE advancing
        if (currentCompletedStep && (
            currentCompletedStep.operation_brix_record || 
            currentCompletedStep.operation_ph_record || 
            currentCompletedStep.record_ctw
        )) {
            // STOP auto-advancing, trap out to QC dialog
            batchRunning.value = false;
            pendingQcStep.value = currentCompletedStep;
            localStepIndex.value = completedIndex + 1; // Stage the next step
            qcDialog.value = true;
            $q.notify({ type: 'warning', message: 'QC Data Required! Please fill in Brix/pH', position: 'center', timeout: 0 })
            return;
        }

        // Normal Auto-Advance
        localStepIndex.value = completedIndex + 1 // Advance to next
        if (localStepIndex.value < skuSteps.value.length) {
            setTimeout(() => sendStepToPLC(localStepIndex.value), 500)
        } else {
            batchRunning.value = false
            $q.notify({ type: 'positive', message: `🎉 BATCH COMPLETE!`, position: 'center', timeout: 4000 })
        }
    }
}

const confirmQcCheck = () => {
    if (pendingQcStep.value?.operation_brix_record && !actualBrix.value) {
        $q.notify({ type: 'warning', message: 'Please input Actual Brix' }); return;
    }
    if (pendingQcStep.value?.operation_ph_record && !actualPh.value) {
        $q.notify({ type: 'warning', message: 'Please input Actual pH' }); return;
    }

    // TODO: POST to Backend here: { batch_id: selectedBatchId.value, step_id: pendingQcStep.value.id, brix: actualBrix.value, ph: actualPh.value }

    $q.notify({ type: 'positive', message: 'QC Data Recorded Successfully!', icon: 'check', timeout: 2000 })
    
    qcDialog.value = false;
    pendingQcStep.value = null;
    batchRunning.value = true;
    
    // Resume auto-advance
    if (localStepIndex.value < skuSteps.value.length) {
        setTimeout(() => sendStepToPLC(localStepIndex.value), 500)
        $q.notify({ type: 'info', message: `Resuming: Advanced to Step ${localStepIndex.value + 1}`, position: 'top', timeout: 1000 })
    } else {
        batchRunning.value = false
        $q.notify({ type: 'positive', message: `🎉 BATCH COMPLETE!`, position: 'center', timeout: 4000 })
    }
}

const sendStepToPLC = (index: number) => {
    const s = skuSteps.value[index]
    if (!s) return;
    
    const topic = `mixing/plant/${activePlantId.value}/step_cmd`
    const payload = {
        // --- DB100 IDENTIFIERS ---
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Plan_ID: batchInfo.value?.plan_id || '-',
        Batch_ID: selectedBatchId.value || '-',
        SKU_Name: batchInfo.value?.sku_name || '-',
        Phase_ID: String(s.phase_number || ''),
        Step_ID: Number(s.sub_step || 0),
        
        // --- SETPOINTS ---
        Step_Time_SP: Number(s.step_time || 0) * 60, // Conv to seconds
        Step_Status: 1, // 1=Active
        Material_ID: s.mat_sap_code || '',
        Re_Code_ID: s.re_code || '',
        Req_Qty: Number(s.require || 0),
        
        // Profiles & Speeds
        TT_SP: [Number(s.temperature || 0)], // Array fallback
        Agitator_Speed: Number(s.agitator_rpm || 0),
        High_Shear_SP: Number(s.high_shear_rpm || 0),
        PH_Target: Number(s.ph_sp || 0),
        Brix_Target: Number(s.brix_sp || 0),
        
        // Command Flags
        HMI_Command: 1, // 1=START
        Cmd_NewStep: true,
        
        timestamp: new Date().toISOString()
    }
    
    publishMessage(topic, payload)
    console.log('PLC DB100 Command Sent:', payload)
}

// ── PLC Commands ──
const sendCommand = async (cmd: 'START' | 'PAUSE' | 'ABORT' | 'NEXT_STEP') => {
    if (!isPlcConnected.value) {
        $q.notify({ type: 'negative', message: 'PLC is offline! Cannot send command.', position: 'top' })
        return
    }

    if (cmd === 'START') {
        if (skuSteps.value.length === 0) {
            $q.notify({ type: 'warning', message: 'No SKU steps found.', position: 'top' })
            return
        }
        batchRunning.value = true
        // Resume from where we were, or start from 0
        const currentIndex = Math.max(0, Number(plantData.value.Step_No || 0) - 1)
        localStepIndex.value = currentIndex >= skuSteps.value.length ? 0 : currentIndex
        sendStepToPLC(localStepIndex.value)
        $q.notify({ type: 'positive', icon: 'settings_remote', message: `STARTED at Step ${localStepIndex.value + 1}`, position: 'top', timeout: 1500 })
        // Also send START state
        publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { command: 'START' })
        return
    } else if (cmd === 'ABORT') {
        batchRunning.value = false
        publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { command: 'ABORT' })
        return
    } else if (cmd === 'NEXT_STEP') {
        batchRunning.value = true
        localStepIndex.value = Math.max(0, Number(plantData.value.Step_No || 0))
        if(localStepIndex.value < skuSteps.value.length) {
            sendStepToPLC(localStepIndex.value)
        }
        return
    } else if (cmd === 'PAUSE') {
        batchRunning.value = false
        publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { command: 'PAUSE' })
        return
    }
}

const goBack = () => {
    router.push('/x60-CheckForProduction')
}

const printProduction = () => {
    // Expand all phases before printing
    for (const phaseGroup of skuStepsByPhase.value) {
        expandedPhases.value[phaseGroup.phase] = true
    }
    setTimeout(() => {
        window.print()
    }, 100)
}

const isLastStep = computed(() => currentStepIndex.value >= skuSteps.value.length - 1)

// ── Passive Tracking State ──
const currentElapsed = computed(() => Number(plantData.value.Step_Timer || 0))
const actualBrix = ref<string | number>('')
const actualPh = ref<string | number>('')

watch(() => plantData.value.Brix, (val) => {
    if (val !== undefined && val !== null) actualBrix.value = val
}, { immediate: true })

watch(() => plantData.value.PH, (val) => {
    if (val !== undefined && val !== null) actualPh.value = val
}, { immediate: true })

const formatDuration = (sec: number) => {
    if (!sec && sec !== 0) return '-'
    const mins = Math.floor(sec / 60)
    const secs = sec % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Ensure active step expands
watch(currentStepIndex, (newIdx) => {
    if (newIdx < skuSteps.value.length) {
        const step = skuSteps.value[newIdx]
        if (step) {
            const phase = step.phase_number || '0'
            expandedPhases.value[phase] = true
        }
        nextTick(() => {
            const el = document.querySelector('.active-step')
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        })
    }
}, { immediate: true })

// ── Weight Totals ──
const totalRequireWeight = computed(() => {
    return skuSteps.value.reduce((sum, s) => sum + (Number(s.require) || 0), 0)
})

// Total actual weight = sum of require for completed steps (up to currentStepIndex)
const totalActualWeight = computed(() => {
    return skuSteps.value
        .slice(0, currentStepIndex.value)
        .reduce((sum, s) => sum + (Number(s.require) || 0), 0)
})

const currentStepWeight = computed(() => {
    return Number(currentStep.value?.require) || 0
})

const weightProgress = computed(() => {
    if (totalRequireWeight.value === 0) return 0
    return totalActualWeight.value / totalRequireWeight.value
})

onMounted(() => {
    // Always prioritize pulling from the local edge buffer to continue process on reload
    fetchBatchInfo();

    connect() // Shared MQTT composable connects here
    onMessage(handlePlcMessage)
})

onUnmounted(() => {
    offMessage(handlePlcMessage)
    disconnect()
})
</script>

<template>
  <q-page class="q-pa-sm" style="height: calc(100vh - 56px); overflow: hidden;">

    <!-- ═══ PAGE HEADER ═══ -->
    <div class="bg-deep-purple-9 text-white q-pa-sm rounded-borders q-mb-sm shadow-2">
      <div class="row justify-between items-center">
        <div class="row items-center q-gutter-sm">
          <q-btn flat round dense icon="arrow_back" color="white" @click="goBack" class="no-print" />
          <q-icon name="precision_manufacturing" size="sm" />
          <div class="text-h6 text-weight-bolder">Mixing-Control 01</div>
        </div>
        <div class="row items-center q-gutter-sm">
          <template v-if="batchInfo">
            <q-badge color="white" text-color="deep-purple-9" class="q-pa-xs q-px-sm text-weight-bold" style="font-size: 14px;">
              <q-icon name="factory" size="16px" class="q-mr-xs" />{{ batchInfo.plant || '-' }}
            </q-badge>
            <q-badge color="white" text-color="deep-purple-9" class="q-pa-xs q-px-sm text-weight-bold" style="font-size: 14px;">
              <q-icon name="assignment" size="16px" class="q-mr-xs" />{{ batchInfo.plan_id }}
            </q-badge>
            <q-badge color="white" text-color="deep-purple-9" class="q-pa-xs q-px-sm text-weight-bold" style="font-size: 14px;">
              <q-icon name="science" size="16px" class="q-mr-xs" />{{ selectedBatchId }}
            </q-badge>
            <q-badge color="amber-4" text-color="grey-10" class="q-pa-xs q-px-sm text-weight-bold" style="font-size: 14px;">
              {{ (batchInfo.batch_size || 0).toFixed(1) }} kg
            </q-badge>
            <q-badge :color="isPlcConnected ? 'positive' : 'negative'" text-color="white" class="q-pa-xs q-px-sm text-weight-bold" style="font-size: 14px; margin-left:8px;">
               <q-icon :name="isPlcConnected ? 'wifi' : 'wifi_off'" size="16px" class="q-mr-xs" />
               PLC {{ isPlcConnected ? 'Connected' : 'Offline' }}
               <q-linear-progress v-if="isPlcConnected" :value="watchdog / 100" color="white" style="width: 40px; margin-left: 6px; border-radius: 4px;" />
            </q-badge>
          </template>
          <div v-else class="text-caption text-deep-purple-2">No Batch Selected</div>
          <q-btn flat round dense icon="print" color="white" @click="printProduction" v-if="skuStepsByPhase.length > 0" class="no-print">
            <q-tooltip>Print PDF</q-tooltip>
          </q-btn>
        </div>
      </div>
    </div>

    <!-- ═══ PAGE LAYOUT ROW ═══ -->
    <div class="row q-col-gutter-sm" style="flex: 1; min-height: 0;">
      <!-- ═══ MAIN PANE: PRODUCTION CONTROL ═══ -->
      <div class="col-12" style="display: flex; flex-direction: column; overflow: hidden; min-height: 0;">

    <!-- ═══ TOP CARD: PLANT 1 LIVE DATA (FETCH DATA FROM PLANT 1) ═══ -->
    <q-card flat bordered class="shadow-1 q-mb-sm bg-white" style="height: 260px; flex-shrink: 0; overflow: hidden; width: 100%;">
      <div class="row full-height">
        <!-- left block: PLC status + Master Info -->
        <div class="col-3 column justify-center items-center q-pa-sm" style="background: linear-gradient(135deg, #1a237e 0%, #283593 100%); color: white;">
           <div class="text-weight-bolder" style="font-size: 28px;">PLANT <span class="text-amber-4">{{ activePlantId.padStart(2, '0') }}</span></div>
           <div class="text-caption text-weight-bold" style="opacity: 0.8; letter-spacing: 1px;">LIVE TELEMETRY</div>
           
           <div class="row items-center justify-center q-mt-md q-pa-sm bg-deep-purple-9 rounded-borders shadow-1 full-width" style="max-width: 200px;">
             <q-icon :name="isPlcConnected ? 'wifi' : 'wifi_off'" size="24px" :color="isPlcConnected ? 'positive' : 'red-4'" class="q-mr-sm" />
             <span class="text-weight-bold" :class="isPlcConnected ? 'text-positive' : 'text-red-4'" style="font-size: 16px;">
               PLC {{ isPlcConnected ? 'CONNECTED' : 'OFFLINE' }}
             </span>
           </div>
           
           <div v-if="isPlcConnected" class="row items-center q-mt-sm q-gutter-x-sm justify-center full-width">
                 <q-icon name="favorite" size="18px" color="red-4" class="heartbeat-icon" />
                 <span class="text-caption text-white text-weight-bold" style="font-family: monospace; font-size: 14px;">WATCHDOG {{ watchdog }}</span>
            </div>
        </div>

        <!-- right block: actual telemetry gauges/Readouts -->
        <div class="col column q-pa-sm" style="overflow-y: hidden;">
           <div class="text-subtitle2 text-grey-8 q-mb-xs text-weight-bold row items-center">
             <q-icon name="precision_manufacturing" class="q-mr-xs" size="18px" /> FETCH DATA FROM PLANT {{ activePlantId }}
             <q-space />
             <div v-if="currentStep" class="row q-gutter-x-md text-indigo-9 text-weight-bold bg-indigo-1 q-px-md q-py-xs rounded-borders items-center" style="font-size: 14px;">
                 <div>STEP ID: <span class="text-indigo-10">{{ (plantData.Step_no ?? plantData.Step_No) !== undefined ? (plantData.Step_no ?? plantData.Step_No) : '-' }}</span></div>
                 <div>TIMER (REQ/ACT): <span class="text-deep-purple">{{ currentStep?.step_time ? currentStep.step_time + ':00' : '-' }}</span> / <span class="text-deep-orange-9">{{ plantData.Step_Timer ?? 0 }}s</span></div>
                 <div>pH (ACT/SP): <span class="text-teal-9">{{ actualPh || '-' }}</span> / {{ currentStep?.ph_sp || '-' }}</div>
                 <div>BRIX (ACT/SP): <span class="text-teal-9">{{ actualBrix || '-' }}</span> / {{ currentStep?.brix_sp || '-' }}</div>
             </div>
           </div>
           
          <!-- 4-Column Granular Telemetry Layout -->
          <div class="row q-col-gutter-sm" style="flex: 1; padding-top: 4px;">
            <!-- Column 1: Hopper Scale Weight -->
            <div class="col-2">
              <div class="req-act-card" style="border-left: 4px solid #795548; height: 100%;">
                <div class="text-grey-7 text-weight-bold" style="font-size: 16px;">🌾 HOPPER SCALE</div>
                <div class="column justify-center items-center full-height q-pb-md">
                   <div class="text-grey-5 text-weight-bold" style="font-size: 14px;">WEIGHT</div>
                   <div class="text-weight-bolder text-brown-8" style="font-size: 38px; line-height: 1;">{{ actualHopperWeight }} <span style="font-size: 16px;">kg</span></div>
                   <div v-if="currentStep?.require" class="text-grey-6 q-mt-xs" style="font-size: 12px;">
                     SP: <span class="text-weight-bold">{{ Number(currentStep.require).toFixed(2) }}</span> kg
                   </div>
                </div>
              </div>
            </div>
            <!-- Column 2: Mixing Tank -->
            <div class="col-4">
              <div class="req-act-card" style="border-left: 4px solid #00796b; height: 100%;">
                <div class="text-grey-7 text-weight-bold" style="font-size: 16px;">💧 MIXING TANK</div>
                <div class="column q-gutter-y-sm q-mt-xs">
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Scale Wt.</div>
                      <div class="text-weight-bold text-teal-9" style="font-size: 20px;">{{ actualTankWeight }} <span style="font-size: 14px; color: #999;">kg</span></div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Temperature</div>
                      <div>
                        <span class="text-weight-bold" :class="currentStep?.temperature && Math.abs(actualTankTemp - currentStep.temperature) <= 5 ? 'text-green-8' : 'text-deep-orange-8'" style="font-size: 20px;">{{ actualTankTemp }}</span>
                        <span style="font-size: 14px; color: #999;">°C</span>
                        <span v-if="currentStep?.temperature" class="text-grey-6 q-ml-sm" style="font-size: 12px;">SP: {{ currentStep.temperature }}°C</span>
                      </div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Agitator Speed</div>
                      <div>
                        <span class="text-weight-bold text-teal-8" style="font-size: 20px;">{{ actualAgitatorRpm }}</span>
                        <span style="font-size: 14px; color: #999;">RPM</span>
                        <span v-if="currentStep?.agitator_rpm" class="text-grey-6 q-ml-sm" style="font-size: 12px;">SP: {{ currentStep.agitator_rpm }}</span>
                      </div>
                   </div>
                </div>
              </div>
            </div>
            <!-- Column 3: High Shear -->
            <div class="col-3">
              <div class="req-act-card" style="border-left: 4px solid #7b1fa2; height: 100%;">
                <div class="text-grey-7 text-weight-bold row items-center" style="font-size: 16px;">
                  ⚡ HIGH SHEAR
                  <q-badge v-if="currentStep?.high_shear_rpm > 0" color="purple" class="q-ml-sm" style="font-size: 10px;">ACTIVE</q-badge>
                  <q-badge v-else color="grey-4" text-color="grey-7" class="q-ml-sm" style="font-size: 10px;">OFF</q-badge>
                </div>
                <div class="column justify-center q-gutter-y-md q-mt-md">
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Speed</div>
                      <div>
                        <span class="text-weight-bold text-purple-9" style="font-size: 26px;">{{ actualHighShearRpm }}</span>
                        <span style="font-size: 14px; color: #999;">RPM</span>
                        <div v-if="currentStep?.high_shear_rpm" class="text-grey-6 text-right" style="font-size: 11px;">SP: {{ currentStep.high_shear_rpm }}</div>
                      </div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Temperature</div>
                      <div class="text-weight-bold text-deep-orange-8" style="font-size: 26px;">{{ actualHighShearTemp }} <span style="font-size: 14px; color: #999;">°C</span></div>
                   </div>
                </div>
              </div>
            </div>
            <!-- Column 4: Circulation -->
            <div class="col-3">
              <div class="req-act-card" style="border-left: 4px solid #1565c0; height: 100%;">
                <div class="text-grey-7 text-weight-bold row items-center" style="font-size: 16px;">
                  🔄 CIRCULATION
                  <q-badge v-if="currentStep?.operation_brix_record || currentStep?.operation_ph_record" color="amber-8" class="q-ml-sm" style="font-size: 10px;">QC CHECK</q-badge>
                </div>
                <div class="column q-gutter-y-sm q-mt-xs">
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Speed</div>
                      <div class="text-weight-bold text-blue-9" style="font-size: 20px;">{{ actualCirculationSpeed }} <span style="font-size: 14px; color: #999;">RPM</span></div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Flow Rate</div>
                      <div class="text-weight-bold text-light-blue-9" style="font-size: 20px;">{{ actualFlowRate }} <span style="font-size: 14px; color: #999;">L/h</span></div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Temperature</div>
                      <div class="text-weight-bold text-deep-orange-8" style="font-size: 20px;">{{ actualCirculationTemp }} <span style="font-size: 14px; color: #999;">°C</span></div>
                   </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </q-card>

    <!-- ═══ BOTTOM CARD: SKU PROCESS AND STEP LIST ═══ -->
    <div style="height: calc(100% - 268px); display: flex; flex-direction: column;">
      <q-card flat bordered class="shadow-1" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
        <template v-if="!selectedBatchId">
          <div class="column items-center justify-center" style="flex: 1;">
             <q-icon name="arrow_back" size="80px" color="grey-4" class="q-mb-md" />
             <div class="text-h6 text-grey-5">Please start production from the "Check for Production" page.</div>
             <q-btn outline color="deep-purple" label="Go to Check for Production" icon="fact_check" class="q-mt-md" @click="goBack" />
          </div>
        </template>
        
        <template v-else>
          <!-- SKU DETAIL TITLE & CURRENT STEP INFO -->
          <div class="bg-teal-7 text-white q-pa-sm shadow-1" style="flex-shrink: 0; z-index: 2;">
            <div class="row items-center">
              <q-icon name="inventory_2" size="24px" class="q-mr-sm" />
              <div>
                <div class="text-subtitle1 text-weight-bold" style="line-height: 1.2;">
                  {{ batchInfo?.sku_id }} — {{ batchInfo?.sku_name }}
                </div>
                <div class="text-caption text-teal-1" style="font-size: 14px;">
                  Plan: {{ batchInfo?.plan_id }} · Batch: {{ selectedBatchId }} · {{ (batchInfo?.batch_size || 0).toFixed(1) }} kg
                </div>
              </div>
              <q-separator vertical dark class="q-mx-md" style="opacity: 0.3;" />
               <!-- Weights Info -->
              <div v-if="currentStep" class="row q-gutter-md items-center">
                 <div>
                    <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">CUR. STEP WT</div>
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ currentStepWeight.toFixed(3) }} kg</div>
                 </div>
                 <div>
                    <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">ACTUAL WT</div>
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ totalActualWeight.toFixed(3) }} kg</div>
                 </div>
                 <div>
                    <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">TOTAL WT</div>
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ totalRequireWeight.toFixed(3) }} kg</div>
                 </div>
              </div>
              <q-separator vertical dark class="q-mx-md" style="opacity: 0.3;" />
              <!-- Inputs -->
              <div v-if="currentStep?.brix_sp" class="row items-center q-mr-sm">
                 <div style="font-size: 14px; margin-right: 8px;">BRIX (SP: {{ currentStep.brix_sp }})</div>
                 <q-input v-model="actualBrix" dense outlined placeholder="Actual" type="number" step="0.1" input-class="text-weight-bold bg-white q-px-sm" style="max-width: 90px; border-radius: 4px;" />
              </div>
              <div v-if="currentStep?.ph_sp" class="row items-center">
                 <div style="font-size: 14px; margin-right: 8px;">pH (SP: {{ currentStep.ph_sp }})</div>
                 <q-input v-model="actualPh" dense outlined placeholder="Actual" type="number" step="0.01" input-class="text-weight-bold bg-white q-px-sm" style="max-width: 90px; border-radius: 4px;" />
              </div>
              
              <q-space />
              
              <!-- COMMAND CENTER -->
              <div class="row q-gutter-sm items-center q-mr-md bg-white q-pa-xs rounded-borders shadow-1">
                 <q-btn flat dense icon="play_arrow" :color="batchRunning ? 'grey' : 'positive'" @click="sendCommand('START')"><q-tooltip>Start Batch</q-tooltip></q-btn>
                 <q-btn flat dense icon="pause" :color="!batchRunning ? 'grey' : 'warning'" @click="sendCommand('PAUSE')"><q-tooltip>Pause Batch</q-tooltip></q-btn>
                 <q-btn flat dense icon="skip_next" color="primary" @click="sendCommand('NEXT_STEP')"><q-tooltip>Force Next Step</q-tooltip></q-btn>
                 <q-separator vertical class="q-mx-xs" />
                 <q-btn flat dense icon="stop" color="negative" @click="sendCommand('ABORT')"><q-tooltip>Emergency Stop / Abort</q-tooltip></q-btn>
              </div>

              <div v-if="currentStep" class="text-right q-mr-md">
                 <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">PHASE {{ currentStep.phase_number || '-' }} | STEP {{ currentStep.sub_step }}</div>
                 <q-linear-progress :value="stepProgress" color="amber-4" track-color="teal-9" style="height: 6px; border-radius: 3px; width: 140px; margin-top: 4px;" />
              </div>
              
              <q-badge color="teal-9" text-color="white" class="q-pa-sm text-weight-bold" style="font-size: 15px;">
                 {{ totalSteps }} steps | {{ skuStepsByPhase.length }} phases
              </q-badge>
            </div>
          </div>

          <q-card-section class="q-pt-sm q-pb-none col" style="overflow: hidden; display: flex; flex-direction: column;">
            <q-inner-loading :showing="loading" />
            <div v-if="skuStepsByPhase.length === 0 && !loading" class="text-center text-grey q-pa-md">
              No details available for this SKU
            </div>
            
            <q-markup-table v-if="skuStepsByPhase.length > 0" flat bordered dense separator="cell" style="font-size: 16px; flex: 1; overflow: auto;" class="full-width production-table sticky-header-table">
              <thead class="bg-grey-3 text-grey-9">
                <tr>
                  <th class="text-center text-weight-bold" style="width: 50px;">Phase</th>
                  <th class="text-center text-weight-bold" style="width: 40px;">Step</th>
                  <th class="text-left text-weight-bold" style="width: 80px;">Action</th>
                  <th class="text-left text-weight-bold">Description</th>
                  <th class="text-left text-weight-bold">RE Code</th>
                  <th class="text-left text-weight-bold">Dest</th>
                  <th class="text-right text-weight-bold">Require<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Temp<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Agitator<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">HighShear<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Brix<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">pH<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Timer<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-center text-weight-bold" style="width: 150px;">Stamp Time</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="phaseGroup in skuStepsByPhase" :key="phaseGroup.phase">
                  <tr class="bg-teal-1 cursor-pointer" @click="togglePhase(phaseGroup.phase)">
                    <td colspan="14" class="text-weight-bold text-teal-10" style="padding: 6px 12px; font-size: 14px; user-select: none;">
                      <q-icon :name="isPhaseExpanded(phaseGroup.phase) ? 'expand_more' : 'chevron_right'" size="18px" class="q-mr-xs" />
                      Process Phase {{ phaseGroup.phase }}
                      <span v-if="phaseGroup.phase_id" class="text-grey-7 q-ml-sm" style="font-size: 14px;">({{ phaseGroup.phase_id }})</span>
                      <q-badge color="teal-6" class="q-ml-sm" style="font-size: 14px;">{{ phaseGroup.steps.length }} steps</q-badge>
                    </td>
                  </tr>
                  <template v-for="step in phaseGroup.steps" :key="step.id">
                    <tr v-show="isPhaseExpanded(phaseGroup.phase)"
                      :class="['step-row', { 'active-step': currentStep && step.id === currentStep.id }]">
                      <td class="text-center" :class="currentStep && step.id === currentStep.id ? 'text-weight-bolder' : 'text-grey-6'">{{ phaseGroup.phase }}</td>
                      <td class="text-center text-weight-bold" style="color: #424242;">{{ step.sub_step }}</td>
                      <td class="text-weight-bold">{{ step.action_code || '-' }}</td>
                      <td>{{ step.action_description || step.action || '-' }}</td>
                      <td class="text-weight-bold text-indigo">{{ step.re_code || '-' }}</td>
                      <td>{{ step.destination || '-' }}</td>
                      <td class="text-right">
                        <span class="act-num">{{ step.actual_volume != null ? Number(step.actual_volume).toFixed(1) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.require ? Number(step.require).toFixed(3) : '-' }}</span>
                      </td>
                      <td class="text-right">
                        <span class="act-num" style="color: #e65100;">{{ step.actual_temp ?? '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.temperature || '-' }}</span>
                      </td>
                      <td class="text-right">
                        <span class="act-num" style="color: #00796b;">{{ step.actual_agitator ?? '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.agitator_rpm || '-' }}</span>
                      </td>
                      <td class="text-right">
                        <span class="act-num" style="color: #7b1fa2;">{{ step.actual_high_shear ?? '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.high_shear_rpm || '-' }}</span>
                      </td>
                      <td class="text-right">
                        <span class="act-num" style="color: #e65100;">{{ step.actual_brix || '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.brix_sp || '-' }}</span>
                      </td>
                      <td class="text-right">
                        <span class="act-num" style="color: #7b1fa2;">{{ step.actual_ph || '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.ph_sp || '-' }}</span>
                      </td>
                      <td class="text-right">
                        <template v-if="currentStep && step.id === currentStep.id">
                           <span class="act-num text-deep-purple">{{ formatDuration(currentElapsed) }}</span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? `${step.step_time}:00` : '-' }}</span>
                        </template>
                        <template v-else-if="step.stamp_time">
                           <span class="act-num text-grey-8">{{ formatDuration(step.duration_sec) }}</span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? `${step.step_time}:00` : '-' }}</span>
                        </template>
                        <template v-else>
                           <span class="act-num">-</span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? `${step.step_time}:00` : '-' }}</span>
                        </template>
                      </td>
                      <td class="text-center">{{ step.stamp_time || '-' }}</td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </q-markup-table>
          </q-card-section>
        </template>
      </q-card>
    </div>
      </div> <!-- /col-9 -->
    </div> <!-- /row -->

    <!-- THE QC TRAP DIALOG -->
    <q-dialog v-model="qcDialog" persistent backdrop-filter="blur(4px)">
      <q-card style="width: 400px; max-width: 90vw; border-radius: 12px; border: 2px solid orange;">
        <q-card-section class="bg-orange-1 text-orange-10 row items-center">
          <q-icon name="warning" size="2rem" class="q-mr-sm"/>
          <div class="text-h6 text-weight-bold">QC Record Required</div>
        </q-card-section>

        <q-separator />

        <q-card-section class="q-pa-md">
          <div class="text-subtitle1 q-mb-md">Phase: <strong>{{ pendingQcStep?.phase_number }} ({{ pendingQcStep?.phase_id }})</strong></div>
          <p class="text-grey-8">Please record the actual QC values before continuing to the next step.</p>
          
          <div v-if="pendingQcStep?.operation_brix_record" class="q-mt-sm">
             <div class="text-weight-bold">Target Brix: <span class="text-indigo">{{ pendingQcStep?.brix_sp }}</span></div>
             <q-input v-model="actualBrix" outlined dense autofocus placeholder="Enter Actual Brix" type="number" step="0.1" class="q-mt-xs">
                <template v-slot:append><div style="font-size: 14px;">Brix</div></template>
             </q-input>
          </div>

          <div v-if="pendingQcStep?.operation_ph_record" class="q-mt-md">
             <div class="text-weight-bold">Target pH: <span class="text-indigo">{{ pendingQcStep?.ph_sp }}</span></div>
             <q-input v-model="actualPh" outlined dense placeholder="Enter Actual pH" type="number" step="0.01" class="q-mt-xs">
                <template v-slot:append><div style="font-size: 14px;">pH</div></template>
             </q-input>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="bg-grey-1 q-pa-md">
          <q-btn flat label="Pause Batch" color="grey-8" @click="() => { qcDialog = false; sendCommand('PAUSE'); }" />
          <q-btn label="Confirm & Continuing" color="positive" icon="check_circle" @click="confirmQcCheck" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<style scoped>
.heartbeat-icon {
  animation: heartbeat 1s ease-in-out infinite;
}
@keyframes heartbeat {
  0%, 100% { transform: scale(1); opacity: 0.8; }
  25% { transform: scale(1.3); opacity: 1; }
  50% { transform: scale(1); opacity: 0.8; }
  75% { transform: scale(1.15); opacity: 1; }
}
.active-step {
  background: #fff8e1 !important;
  border-left: 4px solid #ff8f00;
  animation: pulse-bg 2s ease-in-out infinite;
}
.active-step td {
  font-weight: 700 !important;
}
@keyframes pulse-bg {
  0%, 100% { background: #fff8e1; }
  50% { background: #ffecb3; }
}

.actual-row {
  background: #f5f5f5;
  border-top: 1px dashed #e0e0e0;
}
.actual-row td {
  padding-top: 2px !important;
  padding-bottom: 2px !important;
  font-size: 14px;
}
.active-step-actual {
  background: #fff3e0 !important;
}

.act-num {
  font-weight: 700;
}
.req-num {
  color: #999;
  font-weight: 400;
}
.slash {
  color: #bbb;
  margin: 0 1px;
}

.sticky-header-table thead tr th {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #eeeeee !important;
  box-shadow: 0 1px 0 #ccc;
}
/* Ensure the table itself doesn't hide the sticky header */
.sticky-header-table table {
  border-collapse: separate;
  border-spacing: 0;
}

.step-row:hover {
  background: #e8f5e9 !important;
}

.req-act-card {
  background: #fafafa;
  border-radius: 4px;
  padding: 6px 8px;
  height: 100%;
  transition: background 0.2s;
}
.req-act-card:hover {
  background: #f0f0f0;
}

.production-table th {
  font-size: 14px !important;
  position: sticky;
  top: 0;
  z-index: 1;
}

.actual-metric {
  transition: background 0.2s ease;
  padding: 8px;
}
.actual-metric:hover {
  background: #f5f5f5;
}

.spinning-icon {
  animation: spin 2s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.text-h4 {
  transition: all 0.3s ease;
}

@media print {
  :global(.q-header) {
    display: none !important;
  }
  :global(.q-drawer) {
    display: none !important;
  }
  :global(.q-page-container) {
    padding-top: 0 !important;
    padding-left: 0 !important;
  }
  .q-page {
    padding: 0 !important;
    min-height: auto !important;
    height: auto !important;
  }
  .no-print {
    display: none !important;
  }
  .q-card {
    border: none !important;
    overflow: visible !important;
    height: auto !important;
  }
  .q-card-section {
    overflow: visible !important;
  }
  .production-table {
    font-size: 11px !important;
  }
}
</style>

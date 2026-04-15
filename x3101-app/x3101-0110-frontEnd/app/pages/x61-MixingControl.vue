<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useRoute, useRouter } from 'vue-router'
import { useMQTT } from '~/composables/useMQTT'

const route = useRoute()
const router = useRouter()

// ── PLC Connection via Shared MQTT Composable ──
const { connect, disconnect, publishMessage, isConnected: plcConnectedGlobal, plantsData } = useMQTT()
const { getAuthHeader, user } = useAuth()
const $q = useQuasar()

// ── State ──
const selectedBatchId = ref<string | null>(null)
const selectedSkuId = ref<string | null>(null)
const batchInfo = ref<any>(null)
const skuSteps = ref<any[]>([])
const loading = ref(false)

// Fetch the targeted plant ID dynamically (defaults to '1')
const activePlantId = computed(() => {
    if (batchInfo.value && batchInfo.value.plant) {
        return String(batchInfo.value.plant).replace(/\D/g, '') || '1'
    }
    return (route.query.plant as string)?.replace(/\D/g, '') || '1'
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
        } else {
            batchInfo.value = null
            selectedBatchId.value = null
            skuSteps.value = []
        }
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// ── Fetch SKU steps ──
const fetchSkuSteps = async (skuId: string) => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl || 'http://127.0.0.1:8001'
        const data = await $fetch<any[]>(`${remoteApiBaseUrl}/edge/sku-steps/${skuId}`, {
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

// ── PLC Commands ──
const sendCommand = (cmd: 'START' | 'PAUSE' | 'ABORT' | 'NEXT_STEP') => {
    if (!isPlcConnected.value) {
        $q.notify({ type: 'negative', message: 'PLC is offline! Cannot send command.', position: 'top' })
        return
    }
    // E.g., mixing/plant/1/cmd
    const topic = `mixing/plant/${activePlantId.value}/cmd`
    const payload = {
        command: cmd,
        batch_id: selectedBatchId.value,
        timestamp: new Date().toISOString(),
        operator: user?.value?.username || 'Operator'
    }
    
    // Add specific payload requirements for Node-RED or PLC simulator
    const success = publishMessage(topic, payload)
    if (success) {
        $q.notify({ type: 'positive', icon: 'settings_remote', message: `CMD: [${cmd}] Sent to Plant ${activePlantId.value}`, position: 'top', timeout: 1500 })
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
})

onUnmounted(() => {
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
                      <div class="text-weight-bold text-deep-orange-8" style="font-size: 20px;">{{ actualTankTemp }} <span style="font-size: 14px; color: #999;">°C</span></div>
                   </div>
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Agitator Speed</div>
                      <div class="text-weight-bold text-teal-8" style="font-size: 20px;">{{ actualAgitatorRpm }} <span style="font-size: 14px; color: #999;">RPM</span></div>
                   </div>
                </div>
              </div>
            </div>
            <!-- Column 3: High Shear -->
            <div class="col-3">
              <div class="req-act-card" style="border-left: 4px solid #7b1fa2; height: 100%;">
                <div class="text-grey-7 text-weight-bold" style="font-size: 16px;">⚡ HIGH SHEAR</div>
                <div class="column justify-center q-gutter-y-md q-mt-md">
                   <div class="row justify-between items-center">
                      <div class="text-grey-6 text-weight-bold" style="font-size: 14px;">Speed</div>
                      <div class="text-weight-bold text-purple-9" style="font-size: 26px;">{{ actualHighShearRpm }} <span style="font-size: 14px; color: #999;">RPM</span></div>
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
                <div class="text-grey-7 text-weight-bold" style="font-size: 16px;">🔄 CIRCULATION</div>
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
                 <q-btn flat dense icon="play_arrow" color="positive" @click="sendCommand('START')"><q-tooltip>Start Batch</q-tooltip></q-btn>
                 <q-btn flat dense icon="pause" color="warning" @click="sendCommand('PAUSE')"><q-tooltip>Pause Batch</q-tooltip></q-btn>
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
  </q-page>
</template>

<style scoped>
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

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useRoute, useRouter } from 'vue-router'
import { useMQTT } from '~/composables/useMQTT'

// ── PLC Step Descriptions ──
const plcStepDescriptions: Record<number, string> = {
  0: "Stand By",
  2: "Start Program",
  4: "Fill Major Ingredient",
  6: "Fill Major Done",
  8: "Preblending",
  10: "First Confirm",
  12: "Pre Heats",
  14: "Fill Minor Ingredient",
  16: "Second Heat",
  18: "Fill Third Ingredient",
  20: "Pasteurizer",
  22: "QC Confirm",
  24: "Ready To Transfer",
  26: "Transferring",
  28: "End STEP"
}

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
const batchRunning = ref(false)
const dbPhaseMap = ref<Record<string, string>>({})

// ── PLC Handshake Verification ──
const lastSentPayload = ref<Record<string, any>>({})
const plcReadback = ref<Record<string, any>>({})
const handshakeDialog = ref(false)
const handshakeFields = ['watch_dog', 'batch_id', 'sku_name']
const handshakeStatus = computed(() => {
    const sent = lastSentPayload.value
    const read = plcReadback.value
    if (!sent || !read || Object.keys(read).length === 0) return { ok: false, fields: [], noData: true }
    const fields = handshakeFields.map(f => {
        const s = String(sent[f] ?? '').replace(/\0/g, '').trim()
        const r = String(read[f] ?? '').replace(/\0/g, '').trim()
        return { field: f, sent: s, received: r, match: s === r }
    })
    return { ok: fields.every(f => f.match), fields, noData: false }
})

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

const plcActiveBatchId = computed(() => {
    const raw = plantData.value.Batch_ID || plantData.value.Batch_id || plantData.value.batch_id || ''
    return String(raw).replace(/\0/g, '').trim()
})
const hasPlcActiveBatch = computed(() => {
    const id = plcActiveBatchId.value
    return id && id !== '-' && id !== '0'
})
const plcActivePlanId = computed(() => {
    const raw = plantData.value.Plan_ID || plantData.value.Plan_id || plantData.value.plan_id || ''
    return String(raw).replace(/\0/g, '').trim()
})
const plcActiveSkuName = computed(() => {
    const raw = plantData.value.SKU_Name || plantData.value.SKU_name || plantData.value.sku_name || ''
    return String(raw).replace(/\0/g, '').trim()
})
const plcActivePhaseId = computed(() => {
    return String(plantData.value.Phase_ID || plantData.value.Phase_id || plantData.value.phase_id || 0).replace(/\0/g, '').trim()
})
const plcActiveStepId = computed(() => {
    return Number(plantData.value.Step_ID || plantData.value.Step_id || plantData.value.step_id || 0)
})

const actualAgitatorRpm = computed(() => plantData.value.MixingTank_Agitator_Speed ?? 0)
const actualHighShearRpm = computed(() => plantData.value.HighShare_Speed ?? 0)
const actualHighShearTemp = computed(() => plantData.value.HighShare_Temperature ?? 0)
const actualTankWeight = computed(() => plantData.value.Mixing_Tank_Volume ?? 0)
const actualHopperWeight = computed(() => plantData.value.Hopper_Weight ?? 0)
const actualCirculationSpeed = computed(() => plantData.value.Circulation_Speed ?? 0)
const actualFlowRate = computed(() => plantData.value.Flow_Rate ?? 0)

// ── PLC Error State ──
const isPlcInError = computed(() => {
    const state = plantData.value?.PLC_State
    return state === 6 || state === 9
})
const actualCirculationTemp = computed(() => plantData.value.Circulation_Temperature ?? 0)
const actualTankTemp = computed(() => plantData.value.Mixing_Tank_Temperature ?? 0)
const watchdog = computed(() => plantData.value.watchdog ?? 0)
const isPlcConnected = computed(() => plcConnectedGlobal.value && !!plantData.value.last_update)

// ── Refresh Batch from DB1511 ──
const refreshFromDB1511 = async () => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        const plcStatus = await $fetch<any>(`${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/recipe-status`, {
            headers: getAuthHeader() as Record<string, string>
        })
        if (plcStatus.status === 'success') {
            if (plcStatus.batch_id && plcStatus.batch_id !== '-' && plcStatus.batch_id !== '0') {
                restoreBatchFromPlc(plcStatus.batch_id)
                return
            } else {
                $q.notify({ type: 'warning', message: `No active batch in PLC DB15${activePlantId.value}1.` })
            }
        } else {
            if (route.query.batch_id) {
                $q.notify({ type: 'warning', message: `Failed to read PLC DB15${activePlantId.value}1 or no data.` })
            }
        }
    } catch (e) {
        $q.notify({ type: 'negative', message: 'Error connecting to PLC API.' })
        console.error(e)
    } finally {
        loading.value = false
    }
}

// ── Fetch Batch Info from Edge Buffer ──
const fetchBatchInfo = async () => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        
        // --- 1. Check PLC DB151x First (After Computer Restart Recovery) ---
        try {
            const plcStatus = await $fetch<any>(`${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/recipe-status`, {
                headers: getAuthHeader() as Record<string, string>
            })
            if (plcStatus?.success && plcStatus.target?.batch_id) {
                const plcBatchId = String(plcStatus.target.batch_id).replace(/\0/g, '').trim()
                if (plcBatchId && plcBatchId !== '-' && plcBatchId !== '0') {
                    console.log('[Recovery] Found active batch directly from PLC DB1511:', plcBatchId)
                    await restoreBatchFromPlc(plcBatchId)
                    return // Stop further fetching, we have restored from PLC
                }
            }
        } catch (plcErr) {
            console.warn('[Recovery] Could not read active batch from PLC, falling back to edge...', plcErr)
        }

        // --- 2. Fallback to Edge API ---
        const data = await $fetch<any>(`${remoteApiBaseUrl}/edge/active-batch`, {
             headers: getAuthHeader() as Record<string, string>
        })
        if (data) {
            if (String(data.plant_id).replace(/\D/g, '') !== activePlantId.value) {
                console.warn(`Edge active batch is for plant ${data.plant_id}, but we are viewing plant ${activePlantId.value}. Ignoring.`);
                throw new Error("Edge batch belongs to a different plant");
            }
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
            fetchPrebatchWeights(data.batch_id)
        } else {
            throw new Error("No edge batch data")
        }
    } catch (e) {
        console.warn('Could not fetch from edge API, falling back to query params.')
        const qBatchId = route.query.batch_id as string
        const qSkuId = route.query.sku_id as string
        const qPlanId = route.query.plan_id as string
        const qSkuName = route.query.sku_name as string
        const qBatchSize = parseFloat(route.query.batch_size as string) || 0
        const qPlant = (route.query.plant as string)?.replace(/\D/g, '') || '1'
        if (qBatchId && qSkuId) {
            batchInfo.value = { 
                batch_id: qBatchId,
                plan_id: qPlanId || '-', 
                sku_id: qSkuId, 
                sku_name: qSkuName || '-', 
                plant: 'Mixing ' + qPlant,
                batch_size: qBatchSize
            }
            selectedBatchId.value = qBatchId
            selectedSkuId.value = qSkuId
            fetchSkuSteps(qSkuId)
            fetchPrebatchWeights(qBatchId)
        } else {
            batchInfo.value = null
            selectedBatchId.value = null
            skuSteps.value = []
        }
    } finally {
        loading.value = false
    }
}

// ── Fetch SKU steps from PLC (DB1511) ──
const fetchSkuSteps = async (skuId: string) => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        // Read directly from the new Python snap7 DB API!
        const endpoint = `${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/recipe-status`
        const data = await $fetch<any>(endpoint, {
            headers: getAuthHeader() as Record<string, string>
        })
        
        if (data && data.success && data.target && data.target.steps) {
            // Map the PLC DB1511 step struct to the Vue UI expected fields
            const mappedSteps = data.target.steps.map((s: any, idx: number) => {
                const act = data.actual?.steps?.[idx] || {}
                return {
                    id: s.seq || (idx + 1), // Prevent undefined === undefined bug
                    phase_number: 'p' + String(s.phase_no).padStart(3, '0'),
                    phase_id: s.phase_id,
                    sub_step: s.sub_step,
                    action_code: s.action_code,
                    action_description: dbActionMap.value[s.action_code] || '',
                    re_code: s.re_code,
                    require: s.target_weight,
                    temperature: s.temp_sp,
                    temp_low: s.temp_low,
                    temp_high: s.temp_high,
                    agitator_rpm: s.agitator_sp,
                    high_shear_rpm: s.highshear_sp,
                    step_time: s.step_time,
                    // DB1517 Actuals
                    actual_volume: act.target_weight != null && act.target_weight > 0 ? act.target_weight : null,
                    actual_temp: act.temp_sp != null && act.temp_sp > 0 ? act.temp_sp : null,
                    actual_agitator: act.agitator_sp != null && act.agitator_sp > 0 ? act.agitator_sp : null,
                    actual_high_shear: act.highshear_sp != null && act.highshear_sp > 0 ? act.highshear_sp : null,
                    actual_brix: act.temp_low != null && act.temp_low > 0 ? act.temp_low : null,
                    actual_ph: act.temp_high != null && act.temp_high > 0 ? act.temp_high : null,
                    duration_sec: act.step_time != null && act.step_time > 0 ? act.step_time : null
                }
            })
            skuSteps.value = mappedSteps
            console.log('[PLC Sync] Loaded UI from DB1511 and DB1517:', skuSteps.value)
        } else {
            skuSteps.value = []
        }
    } catch { skuSteps.value = [] }
    finally { loading.value = false }
}

// ── Fetch dynamic phase map from DB ──
const dbActionMap = ref<Record<string, string>>({})

const fetchActionMap = async () => {
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        const data = await $fetch<any[]>(`${remoteApiBaseUrl}/sku-actions/`, {
            headers: getAuthHeader() as Record<string, string>
        })
        const map: Record<string, string> = {}
        for (const act of (data || [])) {
            if (act.action_code) {
                map[act.action_code] = act.action_description
            }
        }
        dbActionMap.value = map
    } catch (e) {
        console.warn('Failed to fetch action map from DB', e)
    }
}

const fetchPhaseMap = async () => {
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        const data = await $fetch<any[]>(`${remoteApiBaseUrl}/sku-phases/`, {
            headers: getAuthHeader() as Record<string, string>
        })
        const map: Record<string, string> = {}
        for (const p of (data || [])) {
            if (p.phase_code) {
                map[p.phase_code] = p.phase_description
            }
        }
        dbPhaseMap.value = map
    } catch (e) {
        console.warn('Failed to fetch phase map from DB', e)
    }
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
// Helper: find step index exactly matching PLC Phase_ID and Step_ID (fallback to local tracker)
const currentStepIndex = computed(() => {
    const pPhase = plantData.value.Phase_ID || plantData.value.Phase_id || plantData.value.phase_id
    const pStep = Number(plantData.value.Step_ID || plantData.value.Step_id || plantData.value.step_id || 0)

    if (pPhase && pStep && skuSteps.value.length > 0) {
        const cleanPPhase = String(pPhase).replace(/\0/g, '').trim()
        const idx = skuSteps.value.findIndex(s => {
            const cleanSPhase = String(s.phase_number || s.phase).trim()
            return cleanSPhase === cleanPPhase && Number(s.sub_step) === pStep
        })
        if (idx !== -1) return idx
    }
    return localStepIndex.value
})
let stepInterval: ReturnType<typeof setInterval> | null = null

const currentStep = computed(() => {
    if (skuSteps.value.length === 0) return null
    return skuSteps.value[currentStepIndex.value] || null
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
const localStepIndex = ref(0)

// ── Confirm Start Production Dialog ──
const confirmStartDialog = ref(false)
const startConfirmed = ref(false)

// ── PLC Data Block Inspection ──
const showPlcDataBlock = ref(false)
const lastPlcPayload = ref<any | null>(null)
const plcCmdLog = ref<Array<{ time: string, topic: string, payload: any }>>([]) // last 10

const buildCurrentStepPayload = () => {
    const s = skuSteps.value[localStepIndex.value] || currentStep.value
    if (!s) return null
    return {
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Plan_ID: batchInfo.value?.plan_id || '-',
        Batch_ID: selectedBatchId.value || '-',
        SKU_Name: batchInfo.value?.sku_name || '-',
        Phase_ID: String(s.phase_number || ''),
        Step_ID: Number(s.sub_step || 0),
        Step_Time_SP: Number(s.step_time || 0) * 60,
        Step_Status: 1,
        Material_ID: s.mat_sap_code || '',
        Re_Code_ID: s.re_code || '',
        Req_Qty: productionRequire(s),
        TT_SP: [Number(s.temperature || 0)],
        Agitator_Speed: Number(s.agitator_rpm || 0),
        High_Shear_SP: Number(s.high_shear_rpm || 0),
        PH_Target: Number(s.ph_sp || 0),
        Brix_Target: Number(s.brix_sp || 0),
        HMI_Command: 1,
        Cmd_NewStep: true,
        timestamp: new Date().toISOString()
    }
}

const openPlcDataBlock = () => {
    // Show last sent, or preview of current step if nothing sent yet
    if (!lastPlcPayload.value) {
        lastPlcPayload.value = buildCurrentStepPayload()
    }
    showPlcDataBlock.value = true
}

const copyPayloadToClipboard = () => {
    const text = JSON.stringify(lastPlcPayload.value, null, 2)
    navigator.clipboard?.writeText(text).then(() => {
        $q.notify({ type: 'positive', message: 'Copied to clipboard!', position: 'top', timeout: 1500 })
    })
}

const confirmStartProduction = () => {
    startConfirmed.value = true
    confirmStartDialog.value = false

    const plantId = activePlantId.value || '1'
    const topic = `mixing/plant/${plantId}/cmd`
    
    // Send final start=1 command to PLC via MQTT
    publishMessage(topic, {
        command: 'START',
        start: 1,
        batch_id: selectedBatchId.value || '',
        sku_id: selectedSkuId.value || '',
        timestamp: new Date().toISOString()
    })

    // Send Batch number to PLC (DB5001, dbb24 String [20])
    const db5001Payload = {
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Plan_ID: batchInfo.value?.plan_id || '-',
        Batch_ID: selectedBatchId.value || '',
        SKU_Name: batchInfo.value?.sku_name || '-',
        Phase_ID: '-',
        Step_ID: 0,
        Address: "DB5001,S24.20", // Correct S7-comm string syntax
        Value: selectedBatchId.value || '',
        datatype: "String [20]",
        timestamp: new Date().toISOString()
    }
    const writeTopic = `mixing/plant/${plantId}/write`
    // The S7-comm node expects a raw string payload to write into the DB, not a JSON object
    publishMessage(writeTopic, selectedBatchId.value || '')
    
    lastPlcPayload.value = db5001Payload
    plcCmdLog.value.unshift({ time: new Date().toLocaleTimeString(), topic: writeTopic, payload: db5001Payload })
    if (plcCmdLog.value.length > 10) plcCmdLog.value.pop()

    $q.notify({
        type: 'positive',
        icon: 'rocket_launch',
        message: '🚀 Production STARTED!',
        caption: `Batch: ${selectedBatchId.value} is now active`,
        position: 'center',
        timeout: 3000,
        classes: 'text-h6 shadow-10'
    })
}

const cancelStartProduction = () => {
    confirmStartDialog.value = false
    router.push('/x60-CheckForProduction')
}

// Show confirm dialog on load when coming from Check-for-Production page
const checkShowConfirmDialog = () => {
    if (route.query.from_check === '1' && selectedBatchId.value && !startConfirmed.value) {
        confirmStartDialog.value = true
    }
}

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

    // Listen for PLC readback data for handshake verification
    const plantId = activePlantId.value || '1'
    const formattedPlantId = String(plantId).padStart(2, '0')
    if (topic === `MIX-${formattedPlantId}-READ`) {
        try {
            const data = typeof payload === 'string' ? JSON.parse(payload) : payload
            plcReadback.value = data
        } catch (e) {
            console.warn('[Handshake] Failed to parse readback:', e)
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

    // If an API endpoint for QC data exists, this is where you would sync it.

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
        Req_Qty: productionRequire(s),
        
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
    
    // ─ Track last sent payload + command log ─
    lastPlcPayload.value = payload
    plcCmdLog.value.unshift({ time: new Date().toLocaleTimeString(), topic, payload: { ...payload } })
    if (plcCmdLog.value.length > 10) plcCmdLog.value.pop()
    
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
        // Resume from where we were (PLC feedback), or start from 0
        localStepIndex.value = currentStepIndex.value >= skuSteps.value.length ? 0 : currentStepIndex.value
        sendStepToPLC(localStepIndex.value)
        $q.notify({ type: 'positive', icon: 'settings_remote', message: `STARTED at Step ${localStepIndex.value + 1}`, position: 'top', timeout: 1500 })
        // Also send START state
        publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { 
            command: 'START',
            Batch_ID: selectedBatchId.value || '-'
        })
        return
    } else if (cmd === 'ABORT') {
        batchRunning.value = false
        publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { command: 'ABORT' })
        return
    } else if (cmd === 'NEXT_STEP') {
        batchRunning.value = true
        localStepIndex.value = currentStepIndex.value + 1
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

const killBatch = () => {
    $q.dialog({
        title: 'Confirm Kill Batch',
        message: `Are you sure you want to completely clear the PLC memory for Plant ${activePlantId.value} and force all data to 0? This cannot be undone.`,
        cancel: true,
        persistent: true,
        color: 'negative'
    }).onOk(async () => {
        try {
            $q.loading.show()
            await $fetch<any>(`${appConfig.apiBaseUrl}/plc/plant/${activePlantId.value}/clear-recipe`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>
            })
            
            // Send ABORT just to be safe
            publishMessage(`mixing/plant/${activePlantId.value}/cmd`, { command: 'ABORT' })
            batchRunning.value = false
            
            // Reset the frontend state
            batchInfo.value = null
            selectedBatchId.value = null
            selectedSkuId.value = null
            skuSteps.value = []
            startConfirmed.value = false
            
            // Remove query parameters
            const { batch_id, sku_id, plan_id, sku_name, batch_size, ...newQuery } = route.query;
            router.replace({ query: newQuery })
            
            $q.notify({ type: 'positive', message: `Batch Killed. PLC memory cleared for Plant ${activePlantId.value}.` })
        } catch (e: any) {
            console.error('Failed to kill batch:', e)
            $q.notify({ type: 'negative', message: 'Failed to clear PLC recipe data.' })
        } finally {
            $q.loading.hide()
        }
    })
}

const goBack = () => {
    router.push('/x60-CheckForProduction')
}

const switchPlant = (plantId: number) => {
    // If the currently loaded batch belongs to a different plant, clear it
    if (batchInfo.value && String(batchInfo.value.plant).replace(/\D/g, '') !== String(plantId)) {
        batchInfo.value = null
        selectedBatchId.value = null
        selectedSkuId.value = null
        skuSteps.value = []
        startConfirmed.value = false
    }
    // Remove query params related to the old batch so we don't accidentally load it
    const { batch_id, sku_id, plan_id, sku_name, batch_size, ...newQuery } = route.query;
    newQuery.plant = String(plantId);

    // Update the URL and refresh the page data
    router.replace({ query: newQuery }).then(() => {
        fetchBatchInfo()
    })
}

const openInNewWindow = (plantId: number) => {
    // Open the Mixing Control page for the specified plant in a new browser tab/window
    const url = router.resolve({ path: '/x61-MixingControl', query: { plant: String(plantId) } }).href
    window.open(url, '_blank')
}

const isWeightInTolerance = (step: any, actualWeight: number) => {
    const requiredWeight = productionRequire(step)
    if (requiredWeight <= 0) return true
    
    const tolHigh = Number(step.high_tol || (requiredWeight * 0.02))
    const tolLow = Number(step.low_tol || (requiredWeight * 0.02))
    const minW = requiredWeight - tolLow
    const maxW = requiredWeight + tolHigh
    
    return actualWeight >= minW && actualWeight <= maxW
}

const confirmStepFromRow = (step: any, skipToleranceCheck: boolean = false) => {
    if (!isPlcConnected.value) {
        $q.notify({ type: 'negative', message: 'PLC is offline!', position: 'top' })
        return
    }
    
    // Weight Tolerance Check for Manual Add Steps
    const aCode = String(step.action_code || '')
    if (!skipToleranceCheck && (aCode.startsWith('2') || aCode.startsWith('3'))) {
        const requiredWeight = productionRequire(step)
        if (requiredWeight > 0) {
            const actualWeight = actualHopperWeight.value
            if (!isWeightInTolerance(step, actualWeight)) {
                $q.notify({ 
                    type: 'negative', 
                    message: 'Weight out of tolerance!', 
                    caption: `Req: ${requiredWeight.toFixed(2)} | Act: ${actualWeight.toFixed(2)}. Adjust weight or use Override.`, 
                    position: 'center',
                    icon: 'scale',
                    timeout: 4000
                })
                return // BLOCK ADVANCE!
            }
        }
    }
    
    const topic = `mixing/plant/${activePlantId.value}/step_cmd`
    const payload = {
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Batch_ID: selectedBatchId.value || '-',
        Phase_ID: String(step.phase_number || ''),
        Step_ID: Number(step.sub_step || 0),
        Confirm_Phase: String(step.phase_number || ''),
        Confirm_Step: Number(step.sub_step || 0),
        Cmd_StartTimer: step.step_time ? 1 : 0,
        HMI_Command: 2 // 2 for Next/Confirm
    }
    
    publishMessage(topic, payload)
    
    plcCmdLog.value.unshift({ time: new Date().toLocaleTimeString(), topic, payload })
    if (plcCmdLog.value.length > 10) plcCmdLog.value.pop()
    
    $q.notify({ type: 'positive', message: `Confirmed Step ${step.sub_step}`, position: 'top', timeout: 1500 })
}

// ── Manual Override ──
const manualPassDialog = ref(false)
const manualPassReason = ref('')
const manualPassStepTarget = ref<any>(null)

const promptManualPass = (step: any) => {
    manualPassStepTarget.value = step
    manualPassReason.value = ''
    manualPassDialog.value = true
}

const submitManualPass = () => {
    if (!manualPassReason.value.trim()) {
        $q.notify({ type: 'warning', message: 'Please provide a reason to override.' })
        return
    }
    
    console.log(`[Manual Override] Step ${manualPassStepTarget.value?.sub_step} bypassed. Reason: ${manualPassReason.value}`)
    $q.notify({ type: 'warning', message: `Manual Override applied: ${manualPassReason.value}`, position: 'top' })
    
    confirmStepFromRow(manualPassStepTarget.value, true)
    
    manualPassDialog.value = false
    manualPassStepTarget.value = null
    manualPassReason.value = ''
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

// ── Production Weights from Batch Data ──
// Prebatch items contain the actual production weights (required_volume)
// which are already calculated for the specific batch size.
const prebatchWeightMap = ref<Record<string, number>>({})
const prebatchIdMap = ref<Record<string, string>>({})
const prebatchWhMap = ref<Record<string, string>>({})

const fetchPrebatchWeights = async (batchId: string) => {
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        const data = await $fetch<any[]>(`${remoteApiBaseUrl}/prebatch-items/by-batch/${batchId}`, {
            headers: getAuthHeader() as Record<string, string>
        })
        const map: Record<string, number> = {}
        const idMap: Record<string, string> = {}
        const whMap: Record<string, string> = {}
        for (const item of (data || [])) {
            const rc = (item.re_code || '').trim()
            if (rc) {
                // Sum volumes if same re_code appears multiple times
                map[rc] = (map[rc] || 0) + (Number(item.required_volume) || 0)
                if (item.batch_record_id) {
                    if (idMap[rc] && !idMap[rc].includes(item.batch_record_id)) {
                        idMap[rc] += `, ${item.batch_record_id}`
                    } else {
                        idMap[rc] = item.batch_record_id
                    }
                }
                if (item.wh) {
                    if (whMap[rc] && !whMap[rc].includes(item.wh)) {
                        whMap[rc] += `, ${item.wh}`
                    } else {
                        whMap[rc] = item.wh
                    }
                }
            }
        }
        prebatchWeightMap.value = map
        prebatchIdMap.value = idMap
        prebatchWhMap.value = whMap
        console.log('[Production Weights] Loaded from batch data:', map)
    } catch (e) {
        console.warn('[Production Weights] Could not fetch prebatch items, using standard recipe weights', e)
        prebatchWeightMap.value = {}
        prebatchIdMap.value = {}
        prebatchWhMap.value = {}
    }
}

// ── Restore Batch from PLC ──
const restoreBatchFromPlc = async (batchId: string) => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        let data = null
        try {
            data = await $fetch<any>(`${remoteApiBaseUrl}/production-batches/by-batch-id/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            })
        } catch (dbErr) {
            console.warn('[Recovery] DB fetch failed, falling back to basic info:', dbErr)
        }

        if (data) {
            const rawSkuName = String(plantData.value.SKU_Name || '').replace(/\0/g, '').trim()
            let skuName = data.sku_name || '-'
            let skuId = data.sku_id || '-'
            
            if (rawSkuName && rawSkuName !== '-') {
                if (rawSkuName.includes('-')) {
                   const parts = rawSkuName.split('-')
                   skuId = parts[0]
                   skuName = parts.slice(1).join('-')
                } else {
                   skuName = rawSkuName
                }
            }

            batchInfo.value = { 
                batch_id: data.batch_id,
                plan_id: data.plan_id || '-', 
                sku_id: data.sku_id || skuId, 
                sku_name: skuName, 
                plant: '0' + activePlantId.value,
                batch_size: data.batch_size
            }
            selectedBatchId.value = data.batch_id
            selectedSkuId.value = data.sku_id || skuId
        } else {
            // Fallback if DB fetch fails
            const rawSkuName = String(plantData.value.SKU_Name || '').replace(/\0/g, '').trim()
            let skuName = '-'
            let skuId = '-'
            if (rawSkuName && rawSkuName !== '-') {
                if (rawSkuName.includes('-')) {
                   const parts = rawSkuName.split('-')
                   skuId = parts[0]
                   skuName = parts.slice(1).join('-')
                } else {
                   skuName = rawSkuName
                }
            }
            const rawPlanId = String(plantData.value.Plan_ID || plantData.value.Plan_id || plantData.value.plan_id || '').replace(/\0/g, '').trim()
            batchInfo.value = {
                batch_id: batchId,
                plan_id: rawPlanId && rawPlanId !== '-' && rawPlanId !== '0' ? rawPlanId : '-',
                sku_id: skuId,
                sku_name: skuName,
                plant: '0' + activePlantId.value,
                batch_size: 0
            }
            selectedBatchId.value = batchId
            selectedSkuId.value = skuId
        }
            
        await fetchSkuSteps(selectedSkuId.value)
        await fetchPrebatchWeights(batchId)
        
        startConfirmed.value = true
        batchRunning.value = true
        
        const pPhase = String(plantData.value.Phase_ID || plantData.value.Phase_id || plantData.value.phase_id || '').replace(/\0/g, '').trim()
        const pStep = Number(plantData.value.Step_ID || plantData.value.Step_id || plantData.value.step_id || 0)
        
        if (pPhase && pStep && skuSteps.value.length > 0) {
            const idx = skuSteps.value.findIndex(s => {
                const cleanSPhase = String(s.phase_number || s.phase).trim()
                return cleanSPhase === pPhase && Number(s.sub_step) === pStep
            })
            if (idx !== -1) {
                localStepIndex.value = idx
                expandedPhases.value[pPhase] = true
            }
        }
        $q.notify({ type: 'info', message: `Restored active batch ${batchId} from PLC.`, position: 'top', icon: 'settings_backup_restore' })
    } catch (e) {
        console.warn('Failed to restore batch from PLC:', e)
    } finally {
        loading.value = false
    }
}

watch([plcActiveBatchId, () => loading.value], ([plcBatchId, newLoading]) => {
    if (!selectedBatchId.value && !newLoading) {
        if (plcBatchId && plcBatchId !== '-' && plcBatchId !== '0') {
            console.log('Detected active batch on PLC, restoring:', plcBatchId)
            restoreBatchFromPlc(plcBatchId)
        }
    }
}, { immediate: true })

// ── Standard Recipe Weights ──
const standardRecipeTotal = computed(() => {
    return skuSteps.value.reduce((sum, s) => sum + (Number(s.require) || 0), 0)
})

const batchSize = computed(() => Number(batchInfo.value?.batch_size) || standardRecipeTotal.value)

const skuStandardRequireSum = computed(() => {
    const map: Record<string, number> = {}
    for (const s of skuSteps.value) {
        const rc = (s.re_code || '').trim()
        if (rc) {
            map[rc] = (map[rc] || 0) + (Number(s.require) || 0)
        }
    }
    return map
})

/** Get the production weight for a step: uses batch data if available, falls back to standard recipe scaled to batch size */
const productionRequire = (step: any): number => {
    if (!step) return 0
    const rc = (step.re_code || '').trim()
    const stdReq = Number(step.require) || 0
    
    // 1. If it's an ingredient we have exact prebatch volumes for:
    // Distribute the exact prebatch total proportionally to this step's standard requirement.
    if (rc && prebatchWeightMap.value[rc] !== undefined) {
        const totalPrebatch = prebatchWeightMap.value[rc]
        const totalStd = skuStandardRequireSum.value[rc] || 0
        if (totalStd > 0) {
            return totalPrebatch * (stdReq / totalStd)
        }
        return totalPrebatch // Fallback if standard sum is 0 but prebatch exists
    }
    
    // 2. Fallback: scale the standard requirement by the overall batch size ratio!
    if (standardRecipeTotal.value > 0) {
        return stdReq * (batchSize.value / standardRecipeTotal.value)
    }
    
    return stdReq
}

// ── Weight Totals (using actual production weights from batch data) ──
const totalRequireWeight = computed(() => {
    return skuSteps.value.reduce((sum, s) => sum + productionRequire(s), 0)
})

// Total actual weight = sum of production require for completed steps (up to currentStepIndex)
const totalActualWeight = computed(() => {
    return skuSteps.value
        .slice(0, currentStepIndex.value)
        .reduce((sum, s) => sum + productionRequire(s), 0)
})

const currentStepWeight = computed(() => {
    return productionRequire(currentStep.value)
})

const weightProgress = computed(() => {
    if (totalRequireWeight.value === 0) return 0
    return totalActualWeight.value / totalRequireWeight.value
})

let heartbeatInterval: ReturnType<typeof setInterval> | null = null

// ── Barcode Scanning Logic ──
const scanBuffer = ref('')
let scanTimeout: any = null

const handleScan = (scannedText: string) => {
    const s = currentStep.value
    if (!s) return

    const aCode = String(s.action_code || '')
    // Only apply logic if the current step action code requires scanning
    if (aCode.startsWith('2') || aCode.startsWith('3')) {
        const expectedIds = prebatchIdMap.value[s.re_code] || ''
        
        // Match the barcode: either exact match or contained inside the string of IDs
        if (expectedIds.includes(scannedText)) {
            $q.notify({
                type: 'positive',
                message: `Scan Matched: ${scannedText}. Advancing step...`,
                position: 'top',
                icon: 'check_circle'
            })
            confirmStepFromRow(s, false)
        } else {
            $q.notify({
                type: 'negative',
                message: `Invalid Barcode Scan: ${scannedText}`,
                position: 'top',
                caption: `Expected one of: ${expectedIds || 'None'}`,
                icon: 'warning'
            })
        }
    } else {
        $q.notify({
            type: 'info',
            message: `Scanned: ${scannedText}`,
            position: 'top',
            caption: 'Current step does not require scanning.'
        })
    }
}

const handleGlobalKeydown = (e: KeyboardEvent) => {
    // Ignore keydown if the user is typing in an input field or textarea
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

    if (e.key === 'Enter') {
        if (scanBuffer.value.length > 3) { // Ensure it's a barcode, not an accidental Enter
            handleScan(scanBuffer.value.trim())
        }
        scanBuffer.value = ''
    } else if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
        scanBuffer.value += e.key
        if (scanTimeout) clearTimeout(scanTimeout)
        // Scanners act like fast typing. If >150ms between keystrokes, reset the buffer.
        scanTimeout = setTimeout(() => { scanBuffer.value = '' }, 150)
    }
}

// ── Automatic Batch Completion ──
watch(() => plantData.value.PLC_State, async (newVal, oldVal) => {
    // If the PLC explicitly enters state 4 (DONE)
    if (newVal === 4 && oldVal !== 4 && batchRunning.value) {
        batchRunning.value = false
        $q.notify({ type: 'positive', message: '🎉 PLC REPORTS BATCH COMPLETE!', position: 'center', timeout: 5000 })
        
        // Sync with Backend database
        if (batchInfo.value && batchInfo.value.id) {
            try {
                const remoteApiBaseUrl = appConfig.apiBaseUrl
                await $fetch(`${remoteApiBaseUrl}/production-batches/${batchInfo.value.id}/status?status=Done`, {
                    method: 'PATCH',
                    headers: getAuthHeader() as Record<string, string>
                })
                $q.notify({ type: 'info', message: 'Batch marked as Done in MES.', position: 'top-right' })
                
                // Refresh local status
                batchInfo.value.status = 'Done'
                batchInfo.value.done = true
            } catch (e) {
                console.error('[Batch Complete] Failed to sync status to MES:', e)
            }
        }
    }
})

onMounted(async () => {
    Promise.all([
        fetchPhaseMap(),
        fetchActionMap(),
        fetchBatchInfo()
    ]).finally(() => {
        checkShowConfirmDialog()
    })

    window.addEventListener('keydown', handleGlobalKeydown)

    connect() // Shared MQTT composable connects here
    onMessage(handlePlcMessage)
    let watchdog_val = 0
    // Publish Plan_ID, Batch_ID, SKU Name, and Phase_ID every 2 seconds (2000ms)
    heartbeatInterval = setInterval(() => {
        // Only publish if production has started and a batch is loaded
        if (selectedBatchId.value && batchInfo.value) {
            const plantId = activePlantId.value || '1'
            const formattedPlantId = String(plantId).padStart(2, '0') // "01"
            
            const s = currentStep.value || {}
            const pNum = s.phase_number || ''
            const pCode = s.phase_id || ''
            const pDesc = dbPhaseMap.value[pCode] || ''
            
            const parts = [pNum, pCode, pDesc].filter(Boolean)
            const phaseStr = parts.length > 0 ? parts.join('-') : '-'
            
            // Build the 50-character SKU combined string
            const sId = String(batchInfo.value?.sku_id || selectedSkuId.value || '-')
            const sName = String(batchInfo.value?.sku_name || '').replace(/^-$/, '').trim()
            const combinedSku = sName ? `${sId}-${sName}` : sId

            // Only publish if a batch is active AND the user has clicked "Confirm Start"
            if (startConfirmed.value) {
                publishMessage(`MIX-${formattedPlantId}-PUT`, {
                    watch_dog: watchdog_val,
                    plan_id: String(batchInfo.value?.plan_id || '-').substring(0, 50),
                    batch_id: String(selectedBatchId.value || '-').substring(0, 20),
                    sku_id: sId.substring(0, 20),
                    sku_name: combinedSku.substring(0, 50),
                    phase_id: String(phaseStr).substring(0, 50),
                    
                    // Step-level execution parameters using exact DB column names
                    sub_step: Number(s.sub_step || 0),
                    action_code: Number(s.action_code || 0),
                    step_time: Number(s.step_time || 0) * 60,
                    material_code: String(s.mat_sap_code || '').substring(0, 20),
                    re_code: String(s.re_code || '').substring(0, 20),
                    require: productionRequire(s),
                    temperature: Number(s.temperature || 0),
                    agitator_rpm: Number(s.agitator_rpm || 0),
                    high_shear_rpm: Number(s.high_shear_rpm || 0),
                    ph_sp: Number(s.ph_sp || 0),
                    brix_sp: Number(s.brix_sp || 0),
                    hmi_command: 1,
                    next_step_cmd: 0
                })
                // Store last sent payload for handshake comparison
                lastSentPayload.value = {
                    watch_dog: watchdog_val,
                    batch_id: String(selectedBatchId.value || '-').substring(0, 20),
                    sku_name: combinedSku.substring(0, 50)
                }
            }
            
            watchdog_val = (watchdog_val >= 100) ? 0 : watchdog_val + 1
        }
    }, 2000)
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleGlobalKeydown)
    if (heartbeatInterval) clearInterval(heartbeatInterval)
    offMessage(handlePlcMessage)
    disconnect()
})
</script>

<template>
  <q-page class="q-pa-sm" style="height: calc(100vh - 56px); overflow: hidden;">

    <!-- ═══ PAGE HEADER ═══ -->
    <div class="bg-deep-purple-10 text-white q-pa-sm rounded-borders q-mb-sm shadow-2 row items-center justify-between no-wrap">
       <!-- LEFT: Branding & Plant Selection -->
       <div class="row items-center q-gutter-x-sm" style="flex-shrink: 0;">
          <q-btn flat round dense icon="arrow_back" color="white" @click="goBack" class="no-print" />
          <q-icon name="precision_manufacturing" size="28px" color="amber-3" />
          <div class="text-h6 text-weight-bolder q-mr-sm" style="letter-spacing: 0.5px; line-height: 1.2;">Mixing-Control</div>
          
          <q-separator vertical dark class="q-mx-xs" style="opacity: 0.3;" />
          
          <div class="row items-center q-gutter-x-xs">
               <q-btn v-for="p in [1, 2, 3]" :key="p"
                      :color="String(activePlantId) === String(p) ? 'white' : 'transparent'"
                      :text-color="String(activePlantId) === String(p) ? 'deep-purple-10' : 'white'"
                      :outline="String(activePlantId) !== String(p)"
                      dense
                      :icon-right="String(activePlantId) === String(p) ? 'check_circle' : 'open_in_new'"
                      :label="`Plant ${p}`"
                      class="text-weight-bold"
                      style="height: 28px; font-size: 12px; margin: 2px; border-radius: 6px;"
                      @click="String(activePlantId) !== String(p) ? openInNewWindow(p) : null">
                  <q-tooltip v-if="String(activePlantId) !== String(p)">Open Plant {{ p }} in a New Window</q-tooltip>
                  <q-tooltip v-else>Active Window</q-tooltip>
               </q-btn>
          </div>
       </div>

       <!-- CENTER: Controls & PLC Status -->
       <div class="row items-center q-gutter-x-md" style="flex-shrink: 0;">
          
          <!-- Command Center -->
          <div class="row items-center bg-white q-pa-xs rounded-borders shadow-1" style="height: 36px;">
             <q-btn flat dense icon="play_arrow" :color="batchRunning ? 'grey-4' : 'positive'" @click="sendCommand('START')"><q-tooltip>Start Batch</q-tooltip></q-btn>
             <q-btn flat dense icon="pause" :color="!batchRunning ? 'grey-4' : 'warning'" @click="sendCommand('PAUSE')"><q-tooltip>Pause Batch</q-tooltip></q-btn>
             <q-btn flat dense icon="skip_next" color="primary" @click="sendCommand('NEXT_STEP')"><q-tooltip>Force Next Step</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" />
             <q-btn flat dense icon="stop" color="negative" @click="sendCommand('ABORT')"><q-tooltip>Emergency Stop / Abort</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" />
             <q-btn flat dense icon="developer_board" color="indigo-7" @click="openPlcDataBlock">
               <q-badge v-if="plcCmdLog.length > 0" color="indigo-9" floating style="font-size: 9px;">{{ plcCmdLog.length }}</q-badge>
               <q-tooltip>View PLC Data Block (DB100)</q-tooltip>
             </q-btn>
             <q-separator vertical class="q-mx-xs" />
             <q-btn flat dense icon="print" color="grey-8" @click="printProduction" v-if="skuStepsByPhase.length > 0" class="no-print"><q-tooltip>Print Production PDF</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" v-if="skuStepsByPhase.length > 0" />
             <q-btn flat dense icon="refresh" color="teal-8" @click="refreshFromDB1511"><q-tooltip>Refresh Batch from PLC</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" />
             <q-btn flat dense icon="delete_forever" color="red-9" @click="killBatch"><q-tooltip>Kill Batch (Clear to 0)</q-tooltip></q-btn>
          </div>
          
          <q-separator vertical dark class="q-mx-xs" style="opacity: 0.3;" />

          <!-- PLC Status Tags -->
          <div class="column justify-center q-gutter-y-xs" style="min-width: 140px;">
             <div class="row items-center q-gutter-x-xs">
                 <q-badge :color="isPlcConnected ? 'green-5' : 'red-5'" text-color="dark" class="text-weight-bold shadow-1" style="padding: 4px 6px; font-size: 11px;">
                    <q-icon :name="isPlcConnected ? 'wifi' : 'wifi_off'" size="12px" class="q-mr-xs" />
                    {{ isPlcConnected ? 'ONLINE' : 'OFFLINE' }}
                 </q-badge>
                 <q-badge color="cyan-3" text-color="deep-purple-10" class="text-weight-bold shadow-1" style="padding: 4px 6px; font-size: 11px;">
                    State: {{ plantData?.PLC_State || 0 }}
                 </q-badge>
             </div>
             <q-badge color="green-3" text-color="green-10" class="text-weight-bold shadow-1 ellipsis" style="padding: 4px 6px; font-size: 11px; max-width: 220px;">
                <q-icon name="play_arrow" size="12px" class="q-mr-xs" />Step: {{ plantData?.Current_Step || 0 }} &rarr; {{ plcStepDescriptions[plantData?.Current_Step] || 'Unknown' }}
             </q-badge>
          </div>
       </div>

       <!-- RIGHT: Batch Info -->
       <div class="row items-center q-gutter-x-sm" style="flex-shrink: 1; justify-content: flex-end; min-width: 280px;">
          <q-separator vertical dark class="q-mx-xs" style="opacity: 0.3;" />
          <template v-if="batchInfo">
             <div class="column q-gutter-y-xs text-right">
                <div class="row justify-end q-gutter-x-xs">
                   <q-badge color="white" text-color="deep-purple-9" class="text-weight-bold" style="padding: 4px 6px; font-size: 12px;">
                      <q-icon name="factory" size="12px" class="q-mr-xs" />{{ batchInfo.plant || '-' }}
                   </q-badge>
                   <q-badge color="white" text-color="deep-purple-9" class="text-weight-bold" style="padding: 4px 6px; font-size: 12px; max-width: 180px;">
                      <q-icon name="assignment" size="12px" class="q-mr-xs" />Plan: {{ batchInfo.plan_id }}
                   </q-badge>
                </div>
                <div class="row justify-end q-gutter-x-xs">
                   <q-badge color="amber-4" text-color="grey-10" class="text-weight-bold" style="padding: 4px 6px; font-size: 12px;">
                      {{ (batchInfo.batch_size || 0).toFixed(1) }} kg
                   </q-badge>
                   <q-badge
                     :color="handshakeStatus.noData ? 'grey-6' : (handshakeStatus.ok ? 'green-8' : 'red-8')"
                     text-color="white"
                     class="text-weight-bold cursor-pointer"
                     style="padding: 4px 6px; font-size: 12px;"
                     @click="handshakeDialog = true"
                   >
                     <q-icon :name="handshakeStatus.noData ? 'sync_disabled' : (handshakeStatus.ok ? 'verified' : 'error')" size="12px" class="q-mr-xs" />
                     {{ handshakeStatus.noData ? 'No Readback' : (handshakeStatus.ok ? 'PLC Verified' : 'PLC Mismatch!') }}
                     <q-tooltip>Click to see PLC Handshake Details</q-tooltip>
                   </q-badge>
                </div>
             </div>
          </template>
          <template v-else>
             <div class="column q-gutter-y-xs text-right">
                <q-badge color="deep-purple-7" text-color="white" class="text-weight-bold" style="padding: 4px 6px; font-size: 12px;" v-if="plcActivePlanId && plcActivePlanId !== '-'">
                  <q-icon name="assignment" size="12px" class="q-mr-xs" />Plan: {{ plcActivePlanId }}
                </q-badge>
                <q-badge color="deep-purple-7" text-color="white" class="text-weight-bold" style="padding: 4px 6px; font-size: 12px;" v-if="hasPlcActiveBatch">
                  <q-icon name="science" size="12px" class="q-mr-xs" />Batch: {{ plcActiveBatchId }}
                </q-badge>
                <div class="text-caption text-deep-purple-2 q-ml-sm" v-if="!hasPlcActiveBatch" style="font-size: 13px;">No Batch Selected</div>
             </div>
          </template>
       </div>
    </div>

    <!-- ═══ PAGE LAYOUT ROW ═══ -->
    <div class="row q-col-gutter-sm" style="flex: 1; min-height: 0;">
      <!-- ═══ MAIN PANE: PRODUCTION CONTROL ═══ -->
      <div class="col-12" style="display: flex; flex-direction: column; overflow: hidden; min-height: 0;">


    <!-- ═══ BOTTOM CARD: SKU PROCESS AND STEP LIST ═══ -->
    <div style="height: 100%; display: flex; flex-direction: column;">
      <q-card flat bordered class="shadow-1" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
        <template v-if="!selectedBatchId">
          <div class="column items-center justify-center" style="flex: 1;">
             <q-icon name="precision_manufacturing" size="80px" color="teal-3" class="q-mb-md" />
             <div class="text-h6 text-grey-7 text-weight-bold">Mixing Control Interface</div>
             
             <!-- ACTIVE PRODUCTION BANNER -->
             <div v-if="hasPlcActiveBatch" class="q-mt-md bg-teal-1 q-pa-md rounded-borders shadow-2" style="border: 2px solid #009688; width: 600px; text-align: center;">
                 <div class="text-teal-9 text-subtitle1 text-weight-bolder q-mb-sm"><q-icon name="sync" class="q-mr-xs"/>ACTIVE PRODUCTION DETECTED ON PLC</div>
                 <div class="row q-gutter-md justify-center q-mb-md">
                    <q-badge color="teal-7" class="text-subtitle2 q-pa-sm" v-if="plcActivePlanId">Plan: {{ plcActivePlanId }}</q-badge>
                    <q-badge color="teal-7" class="text-subtitle2 q-pa-sm">Batch: {{ plcActiveBatchId }}</q-badge>
                    <q-badge color="teal-7" class="text-subtitle2 q-pa-sm" v-if="plcActiveSkuName">SKU: {{ plcActiveSkuName }}</q-badge>
                    <q-badge color="teal-9" class="text-subtitle2 q-pa-sm">Step: {{ plcActivePhaseId }} / {{ plcActiveStepId }}</q-badge>
                 </div>
                 <div class="text-caption text-grey-8 q-mb-sm">The PLC is currently running a batch. Restoring session...</div>
                 <q-btn color="teal-8" label="Force Restore Session" icon="settings_backup_restore" size="md" class="text-weight-bold" @click="restoreBatchFromPlc(plcActiveBatchId)" :loading="loading" />
             </div>
             
             <div v-else class="text-subtitle1 text-grey-5 q-mt-sm">Please start production from the "Check for Production" page.</div>
             
             <q-btn v-if="!hasPlcActiveBatch" outline color="deep-purple" label="Go to Check for Production" icon="fact_check" class="q-mt-xl" @click="goBack" />
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
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ currentStepWeight.toFixed(2) }} kg</div>
                 </div>
                 <div>
                    <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">ACTUAL WT</div>
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ totalActualWeight.toFixed(2) }} kg</div>
                 </div>
                 <div>
                    <div style="font-size: 14px; color: #b2dfdb;" class="text-weight-bold">TOTAL WT</div>
                    <div class="text-weight-bold text-amber-2" style="font-size: 16px;">{{ totalRequireWeight.toFixed(2) }} kg</div>
                 </div>
              </div>
              <q-separator vertical dark class="q-mx-md" style="opacity: 0.3;" />
               <!-- ── PLC Live Phase/Step ── -->
               <div class="column items-start justify-center q-px-sm" style="min-width: 80px;">
                  <div style="font-size: 11px; color: #b2dfdb; letter-spacing: 1px; margin-left: 12px;" class="text-weight-bold">PROCESS / STEP</div>
                  <div class="row items-center q-gutter-x-xs">
                    <span v-if="isPlcConnected" style="width:8px;height:8px;border-radius:50%;background:#69f0ae;display:inline-block;" class="plc-heartbeat-dot"></span>
                    <span v-else style="width:8px;height:8px;border-radius:50%;background:#ef5350;display:inline-block;"></span>
                    <div class="row items-center q-gutter-x-xs q-ml-xs">
                      <div class="text-weight-bolder text-amber-3" style="font-size: 18px; line-height: 1; font-family: monospace; white-space: nowrap;">
                        {{ String(plantData.Phase_ID || plantData.Phase_id || plantData.phase_id || currentStep?.phase_number || '—').replace(/\0/g, '').trim() }} 
                        <span class="text-amber-1" style="font-size: 16px; font-weight: 600; font-family: inherit;">
                          --> {{ String(plantData.Step_ID || plantData.Step_id || plantData.step_id || currentStep?.sub_step || '—').replace(/\0/g, '').trim() }}
                        </span>
                      </div>
                    </div>
                  </div>
               </div>
               
               <q-separator vertical dark class="q-mx-md" style="opacity: 0.3;" />

               <!-- ── PLC Live Machine State ── -->
               <div class="column items-start justify-center q-px-sm" style="min-width: 80px;">
                  <div style="font-size: 11px; color: #b2dfdb; letter-spacing: 1px;" class="text-weight-bold">PLC STATE</div>
                  <div class="row items-center q-gutter-x-xs">
                    <div class="row items-center q-gutter-x-xs">
                      <div class="text-weight-bolder text-green-3" style="font-size: 18px; line-height: 1; font-family: monospace; white-space: nowrap;">
                        {{ (plantData.Step_no ?? plantData.Step_No ?? 0) || '—' }} 
                        <span v-if="plcStepDescriptions[(plantData.Step_no ?? plantData.Step_No ?? 0)]" class="text-green-1" style="font-size: 14px; font-weight: 600; font-family: inherit;">
                          --> {{ plcStepDescriptions[(plantData.Step_no ?? plantData.Step_No ?? 0)] }}
                        </span>
                      </div>
                    </div>
                  </div>
               </div>

              <!-- Inputs -->
              <div v-if="currentStep?.brix_sp" class="row items-center q-mr-sm">
                 <div style="font-size: 14px; margin-right: 8px;">BRIX (SP: {{ currentStep.brix_sp }})</div>
                 <q-input v-model="actualBrix" dense outlined placeholder="Actual" type="number" step="0.1" input-class="text-weight-bold bg-white q-px-sm" style="max-width: 90px; border-radius: 4px;" />
              </div>
              <div v-if="currentStep?.ph_sp" class="row items-center">
                 <div style="font-size: 14px; margin-right: 8px;">pH (SP: {{ currentStep.ph_sp }})</div>
                 <q-input v-model="actualPh" dense outlined placeholder="Actual" type="number" step="0.01" input-class="text-weight-bold bg-white q-px-sm" style="max-width: 90px; border-radius: 4px;" />
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

          <q-card-section class="q-pt-sm q-pb-none col" style="display: flex; flex-direction: column; overflow: hidden;">
            <q-inner-loading :showing="loading" />
            <div v-if="skuStepsByPhase.length === 0 && !loading" class="text-center text-grey q-pa-md">
              No details available for this SKU
            </div>
            
            <div v-if="skuStepsByPhase.length > 0" class="scroll" style="flex: 1; min-height: 0;">
              <q-markup-table flat bordered dense separator="cell" style="font-size: 16px;" class="full-width production-table sticky-header-table">
              <thead class="bg-grey-3 text-grey-9">
                <tr>
                  <th class="text-center text-weight-bold" style="width: 50px;">Phase</th>
                  <th class="text-center text-weight-bold" style="width: 40px;">Step</th>
                  <th class="text-left text-weight-bold" style="width: 80px;">Action</th>
                  <th class="text-left text-weight-bold">Description</th>
                  <th class="text-left text-weight-bold">RE Code</th>
                  <th class="text-left text-weight-bold" style="width: 140px;">Prebatch ID</th>
                  <th class="text-center text-weight-bold">WH</th>
                  <th class="text-left text-weight-bold">Dest</th>
                  <th class="text-right text-weight-bold">Require<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Temp<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Agitator<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">HighShear<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Brix<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">pH<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-right text-weight-bold">Timer<br><span style="font-size:14px;color:#999;">act/req</span></th>
                  <th class="text-center text-weight-bold" style="width: 150px;">Stamp Time</th>
                  <th class="text-center text-weight-bold" style="width: 60px;"><q-icon name="settings" size="1.2em" /></th>
                </tr>
              </thead>
              <tbody>
                <template v-for="phaseGroup in skuStepsByPhase" :key="phaseGroup.phase">
                  <tr class="bg-teal-1 cursor-pointer" @click="togglePhase(phaseGroup.phase)">
                    <td colspan="17" class="text-weight-bold text-teal-10" style="padding: 6px 12px; font-size: 14px; user-select: none;">
                      <q-icon :name="isPhaseExpanded(phaseGroup.phase) ? 'expand_more' : 'chevron_right'" size="18px" class="q-mr-xs" />
                      Process Phase {{ phaseGroup.phase }}
                      <span v-if="phaseGroup.phase_id" class="text-grey-7 q-ml-sm" style="font-size: 14px;">({{ phaseGroup.phase_id }})</span>
                      <q-badge color="teal-6" class="q-ml-sm" style="font-size: 14px;">{{ phaseGroup.steps.length }} steps</q-badge>
                    </td>
                  </tr>
                  <template v-for="step in phaseGroup.steps" :key="step.id">
                    <tr v-show="isPhaseExpanded(phaseGroup.phase)"
                      :class="['step-row', { 'active-step': currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) }]">
                      <td class="text-center" :class="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) ? 'text-weight-bolder' : 'text-grey-6'">{{ phaseGroup.phase }}</td>
                      <td class="text-center text-weight-bold" style="color: #424242;">{{ step.sub_step }}</td>
                      <td class="text-weight-bold">
                        <div class="row items-center no-wrap">
                          <q-icon v-if="String(step.action_code).startsWith('2') || String(step.action_code).startsWith('3')" 
                                  name="qr_code_scanner" 
                                  size="16px" 
                                  color="deep-purple-8" 
                                  class="q-mr-xs" 
                                  title="Scan Required" />
                          {{ step.action_code || '-' }}
                        </div>
                      </td>
                      <td>{{ dbActionMap[step.action_code] || step.action_description || step.action || '-' }}</td>
                      <td class="text-weight-bold text-indigo">{{ step.re_code || '-' }}</td>
                      <td class="text-caption text-grey-8" style="font-family: monospace;">{{ prebatchIdMap[step.re_code] || '-' }}</td>
                      <td class="text-center">
                        <q-badge v-if="prebatchWhMap[step.re_code]" :color="prebatchWhMap[step.re_code] === 'FH' ? 'amber-9' : prebatchWhMap[step.re_code] === 'SPP' ? 'blue-8' : 'green-8'">{{ prebatchWhMap[step.re_code] }}</q-badge>
                        <span v-else>-</span>
                      </td>
                      <td>{{ step.destination || '-' }}</td>
                      <!-- Require / Volume -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                          <!-- LIVE: Hopper actual vs required -->
                          <span class="act-num" :class="productionRequire(step) && isWeightInTolerance(step, actualHopperWeight) ? 'text-green-8' : 'text-deep-orange-9'">{{ actualHopperWeight !== 0 ? Number(actualHopperWeight).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ productionRequire(step) ? productionRequire(step).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num">{{ step.actual_volume != null ? Number(step.actual_volume).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ productionRequire(step) ? productionRequire(step).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <!-- Temperature -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                          <span class="act-num" :class="step.temperature && Math.abs(actualTankTemp - step.temperature) <= 5 ? 'text-green-8' : 'text-deep-orange-8'" style="font-weight:800;">{{ actualTankTemp !== 0 ? Number(actualTankTemp).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ step.temperature ? Number(step.temperature).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #e65100;">{{ step.actual_temp != null ? Number(step.actual_temp).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.temperature ? Number(step.temperature).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <!-- Agitator -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                          <span class="act-num text-teal-8" style="font-weight:800;">{{ actualAgitatorRpm !== 0 ? Number(actualAgitatorRpm).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ step.agitator_rpm ? Number(step.agitator_rpm).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #00796b;">{{ step.actual_agitator != null ? Number(step.actual_agitator).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.agitator_rpm ? Number(step.agitator_rpm).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <!-- High Shear -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                          <span class="act-num" :class="actualHighShearRpm > 0 ? 'text-purple-8' : 'text-grey-5'" style="font-weight:800;">{{ actualHighShearRpm !== 0 ? Number(actualHighShearRpm).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ step.high_shear_rpm ? Number(step.high_shear_rpm).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #7b1fa2;">{{ step.actual_high_shear != null ? Number(step.actual_high_shear).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.high_shear_rpm ? Number(step.high_shear_rpm).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <!-- Brix -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) && step.brix_sp">
                          <span class="act-num text-deep-orange-8" style="font-weight:800;">{{ actualBrix ? Number(actualBrix).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ step.brix_sp ? Number(step.brix_sp).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #e65100;">{{ step.actual_brix != null ? Number(step.actual_brix).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.brix_sp ? Number(step.brix_sp).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <!-- pH -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) && step.ph_sp">
                          <span class="act-num text-purple-8" style="font-weight:800;">{{ actualPh ? Number(actualPh).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ step.ph_sp ? Number(step.ph_sp).toFixed(2) : '-' }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #7b1fa2;">{{ step.actual_ph != null ? Number(step.actual_ph).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ step.ph_sp ? Number(step.ph_sp).toFixed(2) : '-' }}</span>
                        </template>
                      </td>
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
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
                      <td class="text-center q-pa-none">
                        <q-btn v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))"
                               dense flat color="primary" icon="skip_next"
                               @click.stop="confirmStepFromRow(step)"
                               >
                               <q-tooltip>Confirm & Next Step (or Start Timer)</q-tooltip>
                        </q-btn>
                        <q-btn v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) && (String(step.action_code).startsWith('2') || String(step.action_code).startsWith('3'))"
                               dense flat color="orange-9" icon="warning"
                               @click.stop="promptManualPass(step)"
                               >
                               <q-tooltip>Manual Override (Provide Reason)</q-tooltip>
                        </q-btn>
                      </td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </q-markup-table>
            </div>
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

    <!-- ═══ CONFIRM START PRODUCTION DIALOG ═══ -->
    <q-dialog v-model="confirmStartDialog" persistent backdrop-filter="blur(6px)">
      <q-card style="width: 520px; max-width: 95vw; border-radius: 16px; border: 3px solid #7b1fa2; overflow: hidden;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #4a148c 0%, #7b1fa2 100%); padding: 20px 24px; color: white;">
          <div class="row items-center q-gutter-sm">
            <q-icon name="rocket_launch" size="36px" color="amber-3" />
            <div>
              <div class="text-h5 text-weight-bolder">Confirm Production Start</div>
              <div class="text-caption text-purple-2" style="opacity: 0.85;">All pre-pack ingredients verified — ready to mix</div>
            </div>
          </div>
        </div>

        <q-separator />

        <!-- Batch Details -->
        <q-card-section class="q-pa-lg">
          <div class="column q-gutter-md">

            <!-- Status Badge -->
            <div class="row items-center justify-center">
              <q-chip color="green-8" text-color="white" icon="check_circle" size="lg" class="text-weight-bolder q-px-lg">
                ALL PREPACK VERIFIED ✅
              </q-chip>
            </div>

            <!-- Batch Info Grid -->
            <div class="row q-col-gutter-sm">
              <div class="col-6">
                <div class="rounded-borders q-pa-sm bg-purple-1 text-purple-10">
                  <div class="text-caption text-weight-bold text-purple-7">BATCH ID</div>
                  <div class="text-subtitle1 text-weight-bolder">{{ batchInfo?.batch_id || selectedBatchId || '-' }}</div>
                </div>
              </div>
              <div class="col-6">
                <div class="rounded-borders q-pa-sm bg-teal-1 text-teal-10">
                  <div class="text-caption text-weight-bold text-teal-7">SKU</div>
                  <div class="text-subtitle1 text-weight-bolder">{{ batchInfo?.sku_id || selectedSkuId || '-' }}</div>
                </div>
              </div>
              <div class="col-8">
                <div class="rounded-borders q-pa-sm bg-indigo-1 text-indigo-10">
                  <div class="text-caption text-weight-bold text-indigo-7">PRODUCT NAME</div>
                  <div class="text-subtitle1 text-weight-bolder">{{ batchInfo?.sku_name || '-' }}</div>
                </div>
              </div>
              <div class="col-4">
                <div class="rounded-borders q-pa-sm bg-amber-1 text-amber-10">
                  <div class="text-caption text-weight-bold text-amber-8">BATCH SIZE</div>
                  <div class="text-subtitle1 text-weight-bolder">{{ (batchInfo?.batch_size || 0).toFixed(1) }} kg</div>
                </div>
              </div>
            </div>

            <!-- Warning -->
            <div class="row items-center q-pa-sm bg-orange-1 rounded-borders text-orange-10" style="border: 1px solid #ffb300;">
              <q-icon name="warning" size="20px" class="q-mr-sm" color="orange-9" />
              <div class="text-body2">
                Pressing <strong>CONFIRM START</strong> will send <code>start=1</code> to PLC Plant {{ activePlantId.padStart(2,'0') }} and begin the mixing process.
              </div>
            </div>

          </div>
        </q-card-section>

        <q-separator />

        <!-- Actions -->
        <q-card-actions align="right" class="bg-grey-1 q-pa-md">
          <q-btn
            flat
            label="Cancel — Go Back"
            color="grey-7"
            icon="arrow_back"
            @click="cancelStartProduction"
          />
          <q-btn
            label="CONFIRM START PRODUCTION"
            color="deep-purple-9"
            icon="rocket_launch"
            size="md"
            unelevated
            class="text-weight-bolder q-px-lg"
            @click="confirmStartProduction"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ═══ PLC DATA BLOCK INSPECTOR DIALOG ═══ -->
    <q-dialog v-model="showPlcDataBlock" maximized>
      <q-card style="display: flex; flex-direction: column; background: #0d1117;">

        <!-- Header -->
        <div style="background: linear-gradient(90deg, #1a237e 0%, #283593 100%); padding: 12px 20px; flex-shrink: 0;">
          <div class="row items-center">
            <q-icon name="developer_board" size="28px" color="cyan-4" class="q-mr-sm" />
            <div>
              <div class="text-h6 text-white text-weight-bolder" style="line-height: 1.1;">PLC Data Block — DB100</div>
              <div class="text-caption text-blue-3" style="opacity: 0.8;">HMI → PLC Step Command Interface</div>
            </div>
            <q-space />
            <q-badge color="cyan-9" text-color="cyan-2" class="q-mr-md q-px-sm q-py-xs">
              <q-icon name="send" size="12px" class="q-mr-xs" />
              {{ plcCmdLog.length }} sent this session
            </q-badge>
            <q-btn flat round dense icon="content_copy" color="cyan-4" @click="copyPayloadToClipboard">
              <q-tooltip>Copy JSON to clipboard</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="close" color="white" v-close-popup />
          </div>
        </div>

        <!-- Topic Bar -->
        <div style="background: #161b22; padding: 6px 20px; border-bottom: 1px solid #30363d; flex-shrink: 0;">
          <span class="text-caption text-grey-5">MQTT TOPIC: </span>
          <span class="text-caption text-cyan-4 text-weight-bold">
            mixing/plant/{{ activePlantId }}/step_cmd
          </span>
          <span class="text-caption text-grey-6 q-ml-md">
            Last sent: {{ plcCmdLog[0]?.time || '—' }}
          </span>
        </div>

        <!-- Main body: two columns -->
        <div class="row" style="flex: 1; overflow: hidden;">

          <!-- LEFT: Current payload grouped -->
          <div style="flex: 1; overflow-y: auto; padding: 16px 20px; border-right: 1px solid #21262d;" v-if="lastPlcPayload">

            <!-- Section: Identifiers -->
            <div class="q-mb-md">
              <div class="row items-center q-mb-sm">
                <q-icon name="fingerprint" color="cyan-4" size="16px" class="q-mr-xs" />
                <span class="text-caption text-cyan-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">DB100 — Identifiers</span>
              </div>
              <table style="width: 100%; border-collapse: collapse; font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px;">
                <tr v-for="key in ['Watch_Doc','Plan_ID','Batch_ID','SKU_Name','Phase_ID','Step_ID']" :key="key"
                  style="border-bottom: 1px solid #21262d;">
                  <td style="color: #7ee787; padding: 4px 8px; width: 160px; white-space: nowrap;">{{ key }}</td>
                  <td style="color: #e6edf3; padding: 4px 8px;">{{ lastPlcPayload[key] ?? '—' }}</td>
                </tr>
              </table>
            </div>

            <!-- Section: Setpoints -->
            <div class="q-mb-md">
              <div class="row items-center q-mb-sm">
                <q-icon name="tune" color="amber-4" size="16px" class="q-mr-xs" />
                <span class="text-caption text-amber-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">Setpoints</span>
              </div>
              <table style="width: 100%; border-collapse: collapse; font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px;">
                <tr v-for="key in ['Step_Time_SP','Step_Status','Material_ID','Re_Code_ID','Req_Qty']" :key="key"
                  style="border-bottom: 1px solid #21262d;">
                  <td style="color: #7ee787; padding: 4px 8px; width: 160px; white-space: nowrap;">{{ key }}</td>
                  <td style="color: #e6edf3; padding: 4px 8px;">
                    {{ lastPlcPayload[key] ?? '—' }}
                    <span v-if="key === 'Step_Time_SP'" style="color: #8b949e; font-size: 11px;"> s (= {{ (lastPlcPayload[key] / 60).toFixed(1) }} min)</span>
                  </td>
                </tr>
              </table>
            </div>

            <!-- Section: Profiles & Speeds -->
            <div class="q-mb-md">
              <div class="row items-center q-mb-sm">
                <q-icon name="speed" color="orange-4" size="16px" class="q-mr-xs" />
                <span class="text-caption text-orange-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">Profiles &amp; Speeds</span>
              </div>
              <table style="width: 100%; border-collapse: collapse; font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px;">
                <tr v-for="key in ['TT_SP','Agitator_Speed','High_Shear_SP','PH_Target','Brix_Target']" :key="key"
                  style="border-bottom: 1px solid #21262d;">
                  <td style="color: #7ee787; padding: 4px 8px; width: 160px; white-space: nowrap;">{{ key }}</td>
                  <td style="color: #e6edf3; padding: 4px 8px;">{{ lastPlcPayload[key] ?? '—' }}</td>
                </tr>
              </table>
            </div>

            <!-- Section: Command Flags -->
            <div class="q-mb-md">
              <div class="row items-center q-mb-sm">
                <q-icon name="flag" color="red-4" size="16px" class="q-mr-xs" />
                <span class="text-caption text-red-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">Command Flags</span>
              </div>
              <table style="width: 100%; border-collapse: collapse; font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px;">
                <tr v-for="key in ['HMI_Command','Cmd_NewStep','Address','Value','timestamp']" :key="key"
                  style="border-bottom: 1px solid #21262d;">
                  <td style="color: #7ee787; padding: 4px 8px; width: 160px; white-space: nowrap;">{{ key }}</td>
                  <td :style="{ color: key === 'HMI_Command' ? '#ff7b72' : '#e6edf3', padding: '4px 8px' }">
                    {{ lastPlcPayload[key] ?? '—' }}
                    <q-badge v-if="key === 'HMI_Command'" color="red-9" text-color="red-2" class="q-ml-sm" style="font-size: 10px;">
                      1 = START / New Step
                    </q-badge>
                  </td>
                </tr>
              </table>
            </div>

            <!-- Raw JSON -->
            <div>
              <div class="row items-center q-mb-sm">
                <q-icon name="data_object" color="purple-4" size="16px" class="q-mr-xs" />
                <span class="text-caption text-purple-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">Raw JSON Payload</span>
              </div>
              <pre style="background: #161b22; color: #a5d6ff; border: 1px solid #30363d; border-radius: 6px; padding: 12px; font-size: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-word;">{{ JSON.stringify(lastPlcPayload, null, 2) }}</pre>
            </div>
          </div>

          <!-- LEFT empty state -->
          <div v-else style="flex: 1; display: flex; align-items: center; justify-content: center; flex-direction: column; color: #8b949e;">
            <q-icon name="developer_board" size="64px" style="opacity: 0.3;" />
            <div class="q-mt-md text-body1">No payload sent yet this session</div>
            <div class="text-caption q-mt-xs">Press START to send the first step command</div>
          </div>

          <!-- RIGHT: Command Log -->
          <div style="width: 360px; overflow-y: auto; padding: 16px; background: #0d1117; flex-shrink: 0;">
            <div class="row items-center q-mb-sm">
              <q-icon name="history" color="green-4" size="16px" class="q-mr-xs" />
              <span class="text-caption text-green-4 text-weight-bolder" style="letter-spacing: 1px; text-transform: uppercase;">Command Log (last 10)</span>
            </div>

            <div v-if="plcCmdLog.length === 0" class="text-caption text-grey-6 q-mt-md">No commands sent yet.</div>

            <div v-for="(entry, i) in plcCmdLog" :key="i"
              class="q-mb-sm"
              style="border: 1px solid #21262d; border-radius: 6px; overflow: hidden; cursor: pointer;"
              @click="lastPlcPayload = entry.payload"
            >
              <div style="background: #161b22; padding: 4px 10px;" class="row items-center">
                <q-badge :color="i === 0 ? 'green-8' : 'grey-8'" style="font-size: 9px;" class="q-mr-xs">
                  {{ i === 0 ? 'LATEST' : `#${plcCmdLog.length - i}` }}
                </q-badge>
                <span style="color: #58a6ff; font-size: 11px; font-family: monospace;">{{ entry.time }}</span>
                <q-space />
                <span style="color: #7ee787; font-size: 10px;">Ph{{ entry.payload.Phase_ID }}-Stp{{ entry.payload.Step_ID }}</span>
              </div>
              <div style="padding: 6px 10px; font-family: monospace; font-size: 11px; color: #8b949e;">
                <div><span style="color: #7ee787;">Batch:</span> {{ entry.payload.Batch_ID }}</div>
                <div><span style="color: #7ee787;">ReCode:</span> {{ entry.payload.Re_Code_ID || '—' }} | <span style="color: #7ee787;">Qty:</span> {{ entry.payload.Req_Qty }}</div>
                <div><span style="color: #7ee787;">Agit:</span> {{ entry.payload.Agitator_Speed }} rpm | <span style="color: #7ee787;">Temp:</span> {{ entry.payload.TT_SP?.[0] ?? 0 }}°C</div>
              </div>
            </div>
          </div>

        </div>
      </q-card>
    </q-dialog>


    <!-- ═══ PLC HANDSHAKE VERIFICATION DIALOG ═══ -->
    <q-dialog v-model="handshakeDialog" backdrop-filter="blur(4px)">
      <q-card style="width: 600px; max-width: 95vw; border-radius: 14px; overflow: hidden;">
        <div :style="`background: linear-gradient(135deg, ${handshakeStatus.ok ? '#1b5e20' : '#b71c1c'} 0%, ${handshakeStatus.ok ? '#388e3c' : '#e53935'} 100%); padding: 16px 20px; color: white;`">
          <div class="row items-center q-gutter-sm">
            <q-icon :name="handshakeStatus.ok ? 'verified' : 'error'" size="32px" />
            <div>
              <div class="text-h6 text-weight-bolder">PLC Handshake {{ handshakeStatus.ok ? 'VERIFIED ✅' : 'MISMATCH ❌' }}</div>
              <div class="text-caption" style="opacity: 0.85;">Comparing SENT values vs READ-BACK from PLC DB5001</div>
            </div>
          </div>
        </div>
        <q-card-section class="q-pa-md">
          <div v-if="handshakeStatus.noData" class="text-center q-pa-lg">
            <q-icon name="sync_disabled" size="60px" color="grey-5" />
            <div class="text-subtitle1 text-grey-6 q-mt-md">No readback data received from PLC yet.</div>
            <div class="text-caption text-grey-5">Make sure the Node-RED Read-back flow is active.</div>
          </div>
          <q-markup-table v-else flat bordered separator="cell" class="q-mt-sm" style="font-size: 13px;">
            <thead>
              <tr class="bg-grey-2">
                <th style="width: 30%;">Field</th>
                <th style="width: 30%;">Sent</th>
                <th style="width: 30%;">PLC Read</th>
                <th style="width: 10%;">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in handshakeStatus.fields" :key="f.field" :class="f.match ? '' : 'bg-red-1'">
                <td class="text-weight-bold">{{ f.field }}</td>
                <td><code>{{ f.sent }}</code></td>
                <td><code>{{ f.received }}</code></td>
                <td class="text-center">
                  <q-icon :name="f.match ? 'check_circle' : 'cancel'" :color="f.match ? 'green' : 'red'" size="20px" />
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Close" color="grey-7" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ═══ MANUAL PASS DIALOG ═══ -->
    <q-dialog v-model="manualPassDialog" persistent>
      <q-card style="min-width: 400px">
        <q-card-section class="bg-orange-8 text-white row items-center">
          <q-icon name="warning" size="24px" class="q-mr-sm" />
          <div class="text-h6">Manual Step Override</div>
        </q-card-section>

        <q-card-section class="q-pt-md">
          <div class="text-body1 q-mb-md">
            You are bypassing the barcode verification for Step <strong>{{ manualPassStepTarget?.sub_step }}</strong>.
          </div>
          <q-input
            v-model="manualPassReason"
            filled
            type="textarea"
            label="Reason for Override *"
            hint="e.g. Barcode label missing, scanner broken"
            :rules="[val => !!val || 'Reason is required']"
            autofocus
          />
        </q-card-section>

        <q-card-actions align="right" class="text-primary">
          <q-btn flat label="Cancel" v-close-popup color="grey-8" />
          <q-btn flat label="Confirm Override" color="orange-9" text-color="white" class="bg-orange-1 q-px-sm" @click="submitManualPass" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ═══ PLC ALARM OVERLAY ═══ -->
    <q-dialog v-model="isPlcInError" maximized persistent transition-show="fade" transition-hide="fade">
      <q-card class="bg-red-10 text-white flex flex-center column">
        <q-icon name="report" size="120px" class="q-mb-md" />
        <div class="text-h2 text-weight-bolder q-mb-sm text-center" style="letter-spacing: 2px;">CRITICAL PLC ALARM</div>
        <div class="text-h5 text-center q-mb-xl text-red-2" style="max-width: 800px; line-height: 1.4;">
          The PLC has encountered a severe fault or emergency stop.<br>
          All software operations are halted until the physical fault is cleared on the shop floor.
        </div>
        
        <div class="bg-red-9 q-pa-xl rounded-borders text-center shadow-10" style="border: 2px solid #ff5252; min-width: 500px;">
          <div class="text-overline text-red-2" style="font-size: 16px;">Error State Code</div>
          <div class="text-h3 text-weight-bold q-mb-md">{{ plantData?.PLC_State }}</div>
          
          <div v-if="plantData?.Error_Code">
             <q-separator dark class="q-my-md" style="opacity: 0.3;" />
             <div class="text-overline text-red-2" style="font-size: 16px;">Fault Code</div>
             <div class="text-h3 text-weight-bold">{{ plantData?.Error_Code }}</div>
          </div>
        </div>
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
  background: #e3f2fd !important;
  border-left: 4px solid #1976d2;
  animation: pulse-bg 2s ease-in-out infinite;
}
.active-step td {
  font-weight: 700 !important;
}
@keyframes pulse-bg {
  0%, 100% { background: #e3f2fd; }
  50% { background: #bbdefb; }
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

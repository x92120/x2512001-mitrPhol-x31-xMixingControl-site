<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useRoute, useRouter } from 'vue-router'
import { useMQTT } from '~/composables/useMQTT'

// ── PLC Step Descriptions ──
const plcStepDescriptions: Record<number, string> = {
  0: "Stand By",
  1: "Starting Program",
  2: "Start Program",
  3: "Filling Major Ingredient",
  4: "Fill Major Ingredient",
  5: "Filling Major Done",
  6: "Fill Major Done",
  7: "Preblending",
  8: "Preblending",
  9: "Waiting First Confirm",
  10: "First Confirm",
  11: "Pre Heating",
  12: "Pre Heats",
  13: "Filling Minor Ingredient",
  14: "Fill Minor Ingredient",
  15: "Second Heating",
  16: "Second Heat",
  17: "Filling Third Ingredient",
  18: "Fill Third Ingredient",
  19: "Pasteurizing",
  20: "Pasteurizer",
  21: "Waiting QC Confirm",
  22: "QC Confirm",
  23: "Preparing Transfer",
  24: "Ready To Transfer",
  25: "Transferring",
  26: "Transferring",
  27: "Ending STEP",
  28: "End STEP"
}

const route = useRoute()
const router = useRouter()

// ── PLC Connection via Shared MQTT Composable ──
const { connect, disconnect, publishMessage, isConnected: plcConnectedGlobal, plantsData, onMessage, offMessage } = useMQTT()

// ── SIM-Aware MQTT Topic Helper ─────────────────────────────────────────────
// In SIM mode (VITE_SIM_MODE=true), use VITE_PLANT{N}_CMD / sim/plant/{N}/...
// In Production mode, use the standard mixing/plant/{N}/... topics
// This prevents SIM frontend from writing to the real Production PLC.
const isSimMode = import.meta.env.VITE_SIM_MODE === 'true'

// Returns the correct MQTT topic prefix for a given plant ID
// e.g. simCmdTopic(1, 'step_cmd') → 'sim/plant/1/step_cmd'  (SIM)
//                                  → 'mixing/plant/1/step_cmd' (Prod)
const simCmdTopic = (plantId: string | number, suffix: string): string => {
    if (isSimMode) {
        // Use VITE_PLANT{N}_CMD if available, else fall back to sim/plant/{N}/...
        const envKey = `VITE_PLANT${plantId}_CMD` as keyof ImportMeta['env']
        const base = import.meta.env[envKey] || `sim/plant/${plantId}/step_cmd`
        // base = 'sim/plant/1/step_cmd' — replace last segment with suffix
        const baseParts = base.split('/')
        baseParts[baseParts.length - 1] = suffix
        return baseParts.join('/')
    }
    return `mixing/plant/${plantId}/${suffix}`
}
const { getAuthHeader, user, switchStationUser } = useAuth()

// ── Operator Scan State ─────────────────────────────────────────────────
// User 1: เท (Pour operator) — auto from login, scannable
const pourScanInput = ref('')
const pourScanLoading = ref(false)
const pourOperator = ref<{ username: string; full_name: string } | null>(null)

// User 2: ต้ม (Cook operator) — secondary operator, scannable
const cookScanInput = ref('')
const cookScanLoading = ref(false)
const cookOperator = ref<{ username: string; full_name: string } | null>(null)

// currentOperator = pour operator (primary) for all step records
const currentMixOperator = computed(() =>
    pourOperator.value?.username || user.value?.username || 'unknown'
)

/** Resolve a scanned QR value against /users/ → set operator ref + beep/alarm */
async function resolveOperatorScan(
    rawVal: string,
    targetRef: typeof pourOperator,
    loadingRef: typeof pourScanLoading,
    inputRef: typeof pourScanInput,
    isPrimary: boolean
) {
    const val = rawVal.trim()
    if (!val) return
    inputRef.value = ''
    loadingRef.value = true
    try {
        const res = await $fetch<any[]>(`${appConfig.apiBaseUrl}/users/`, {
            headers: getAuthHeader() as Record<string, string>
        })
        const found = res.find((u: any) => u.username.toLowerCase() === val.toLowerCase())
        if (found) {
            targetRef.value = { username: found.username, full_name: found.full_name || found.username }
            if (isPrimary) {
                switchStationUser(found)
                try {
                    await $fetch(`${appConfig.apiBaseUrl}/auth/switch-operator/${found.username}`, {
                        method: 'POST',
                        headers: getAuthHeader() as Record<string, string>
                    })
                } catch (e) {
                    console.error('Failed to sync switched operator to backend:', e)
                }
            }
            // success beep
            try {
                const ctx = new AudioContext()
                const osc = ctx.createOscillator(); const g = ctx.createGain()
                osc.connect(g); g.connect(ctx.destination)
                osc.frequency.value = 880; g.gain.value = 0.3
                osc.start(); osc.stop(ctx.currentTime + 0.12)
            } catch {}
            $q.notify({ type: 'positive', icon: 'how_to_reg', message: `✅ ${isPrimary ? '🫗 เท' : '🍳 ต้ม'}: ${found.full_name || found.username}`, position: 'top-right', timeout: 1800 })
        } else {
            // error alarm
            try {
                const ctx = new AudioContext()
                const osc = ctx.createOscillator(); const g = ctx.createGain()
                osc.connect(g); g.connect(ctx.destination)
                osc.type = 'sawtooth'; osc.frequency.value = 220; g.gain.value = 0.4
                osc.start(); osc.stop(ctx.currentTime + 0.5)
            } catch {}
            $q.notify({ type: 'negative', icon: 'person_off', message: `❌ User "${val}" not found`, caption: 'QR Badge not registered', position: 'top', timeout: 4000 })
        }
    } catch {
        $q.notify({ type: 'negative', icon: 'wifi_off', message: 'Cannot reach server', position: 'top', timeout: 3000 })
    } finally {
        loadingRef.value = false
    }
}

// Debounce watchers — auto-submit when scanner stops
let _pourDbx: ReturnType<typeof setTimeout> | null = null
let _cookDbx: ReturnType<typeof setTimeout> | null = null
watch(pourScanInput, (v) => {
    if (!v) return
    if (_pourDbx) clearTimeout(_pourDbx)
    _pourDbx = setTimeout(() => { if (pourScanInput.value.trim()) resolveOperatorScan(pourScanInput.value, pourOperator, pourScanLoading, pourScanInput, true) }, 150)
})
watch(cookScanInput, (v) => {
    if (!v) return
    if (_cookDbx) clearTimeout(_cookDbx)
    _cookDbx = setTimeout(() => { if (cookScanInput.value.trim()) resolveOperatorScan(cookScanInput.value, cookOperator, cookScanLoading, cookScanInput, false) }, 150)
})
const $q = useQuasar()

// ── State ──
const selectedBatchId = ref<string | null>(null)
const selectedSkuId = ref<string | null>(null)
const batchInfo = ref<any>(null)
const skuSteps = ref<any[]>([])
const loading = ref(false)
const batchRunning = ref(false)
const pendingWeightApproval = ref(false)   // set when PLC step-done fires but weight is still out of tolerance
// plcHmiCommand: tracks the desired HMI state sent to DB1510
//   0 = Idle/Abort (batch not started or killed)
//   1 = Run (batch running, all conditions green)
//   2 = Hold (PAUSE pressed, or app conditions not met)
const plcHmiCommand = ref(0)  // start as 0 (idle) until operator clicks START
const hasConfirmedCurrentStep = ref(false)
const currentStepBypassed = ref(false)
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
            fetchSkuSteps(data.sku_code, data.batch_id)
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
            fetchSkuSteps(qSkuId, qBatchId)
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
const fetchSkuSteps = async (skuId: string, batchId?: string) => {
    loading.value = true
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        // Read directly from the new Python snap7 DB API!
        const endpoint = `${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/recipe-status`
        const data = await $fetch<any>(endpoint, {
            headers: getAuthHeader() as Record<string, string>
        })
        
        if (data && data.success && data.target && data.target.steps) {
            // Build a lookup map from DB1517: step_index (1-based seq) → actual row
            // DB1517 skips steps where step_idx=0, so direct [idx] mapping is WRONG.
            // Must match by step_index === s.seq to get the right actual row.
            const actualBySeq: Record<number, any> = {}
            if (data.actual?.steps) {
                for (const a of data.actual.steps) {
                    const si = a.step_index
                    if (si && si > 0) actualBySeq[si] = a
                }
            }

            // Map the PLC DB1511 step struct to the Vue UI expected fields
            const mappedSteps = data.target.steps.map((s: any, idx: number) => {
                const seq = s.seq || (idx + 1)
                const act = actualBySeq[seq] || {}   // ← match by seq, not by array index
                return {
                    id: seq, // Prevent undefined === undefined bug
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
                    // DB1517 Actuals — now correctly matched by step_index (seq)
                    actual_volume: act.actual_weight != null && act.actual_weight > 0 ? act.actual_weight : null,
                    actual_temp: act.actual_temp != null && act.actual_temp > 0 ? act.actual_temp : null,
                    actual_agitator: act.actual_agitator != null && act.actual_agitator > 0 ? act.actual_agitator : null,
                    actual_high_shear: act.actual_highshear != null && act.actual_highshear > 0 ? act.actual_highshear : null,
                    actual_brix: act.actual_brix != null && act.actual_brix > 0 ? act.actual_brix : null,
                    actual_ph: act.actual_ph != null && act.actual_ph > 0 ? act.actual_ph : null,
                    duration_sec: act.duration_sec != null && act.duration_sec > 0 ? act.duration_sec : null
                }
            })
            skuSteps.value = mappedSteps
            console.log('[PLC Sync] actualBySeq:', actualBySeq, '| mapped steps:', skuSteps.value.map((s: any) => ({ seq: s.id, act: s.actual_volume })))

            // ── Merge brix_sp/ph_sp from SKU DB (not in PLC DB1511) ──────────────
            // PLC stores temp/agitator/weight but NOT Brix/pH setpoints.
            // Fetch them from the MySQL sku_steps table and merge by phase+sub_step.
            if (skuId) {
                try {
                    const skuData = await $fetch<any>(
                        `${remoteApiBaseUrl}/sku-steps/?sku_id=${encodeURIComponent(skuId)}&limit=200`,
                        { headers: getAuthHeader() as Record<string, string> }
                    )
                    const dbSteps: any[] = Array.isArray(skuData) ? skuData : (skuData?.sku_steps || [])

                    // Build lookup: "p010__10" → { brix_sp, ph_sp, operation_brix_record, operation_ph_record }
                    const brixPhMap: Record<string, any> = {}
                    for (const ds of dbSteps) {
                        // DB stores 'p0080', PLC step uses 'p080' — normalize by removing ONE leading zero
                        const pnum = String(ds.phase_number || '').replace(/^p0/, 'p')  // p0080 → p080
                        const key = `${pnum}__${ds.sub_step}`
                        brixPhMap[key] = { brix_sp: ds.brix_sp, ph_sp: ds.ph_sp,
                                           operation_brix_record: ds.operation_brix_record,
                                           operation_ph_record: ds.operation_ph_record }
                    }
                    skuSteps.value = skuSteps.value.map((s: any) => {
                        const key = `${s.phase_number}__${s.sub_step}`
                        const extra = brixPhMap[key] || {}
                        return { ...s, ...extra }  // merge brix_sp/ph_sp into step
                    })
                    const stepKeysSample = skuSteps.value.slice(0, 5).map((s: any) => `${s.phase_number}__${s.sub_step}`)
                    console.log('[brixPh] brixPhMap keys:', Object.keys(brixPhMap).join(', '))
                    console.log('[brixPh] step keys (sample):', stepKeysSample.join(', '))
                    console.log('[brixPh] p080 brix_sp check:', skuSteps.value.find((s: any) => s.phase_number === 'p080')?.brix_sp)

                } catch (e) {
                    console.warn('[fetchSkuSteps] Could not fetch brix/pH from SKU DB:', e)
                }
            }



        } else {
            skuSteps.value = []
        }
    } catch { skuSteps.value = [] }
    finally {
        loading.value = false
        // Merge stamp times from DB after steps are loaded
        const targetBatch = batchId || selectedBatchId.value
        if (targetBatch) {
            fetchStampTimes(targetBatch)
        }
    }
}

// ── Fetch stamp times from production_step_logs and merge into skuSteps ──
const fetchStampTimes = async (batchId: string) => {
    if (!batchId) return
    try {
        const res = await $fetch<any>(`${appConfig.apiBaseUrl}/production-batches/${batchId}/logs`, {
            headers: getAuthHeader() as Record<string, string>
        })
        const logs: any[] = res?.logs || []
        // Build lookup: MUST match by phase_id + step_id to avoid
        // cross-phase contamination (many phases share the same sub_step number)
        const stampByKey: Record<string, string> = {}    // `${phase_id}__${step_id}` → latest ts
        const actualByKey: Record<string, number | null> = {}  // same key → actual_value (weight)
        const normPnum = (s: string) => s ? s.replace(/^(p)(0+)/, (_: any, p: string) => p) : s

        for (const log of logs) {
            const ts = log.completed_at
            if (!ts) continue
            const sid = Number(log.sub_step != null ? log.sub_step : log.step_id)
            if (isNaN(sid)) continue
            
            // Index by both the stored phase_id AND the phase_number format (p010-style)
            const keys = [
                `${log.phase_id || ''}__${sid}`,          // e.g. A1010__10 or p010__10
                `${log.phase_number || ''}__${sid}`,        // e.g. p010__10
                `${normPnum(log.phase_id || '')}__${sid}` // e.g. p10__10
            ]
            for (const k of keys) {
                if (!k || k.startsWith('__') || k.startsWith('undefined__')) continue
                // Keep the latest entry (most recent completed_at)
                if (!stampByKey[k] || new Date(ts) > new Date(stampByKey[k])) {
                    stampByKey[k] = ts
                    // actual_value = weight recorded by worker_handshake at step completion
                    actualByKey[k] = log.actual_value != null ? Number(log.actual_value) : null
                }
            }
        }

        // Build QC records map
        const qcByStep: Record<number, { brix?: number | null, ph?: number | null }> = {}
        const qcRecords = res?.qc_records || []
        for (const qc of qcRecords) {
            const sid = Number(qc.step_id)
            if (!isNaN(sid)) {
                qcByStep[sid] = {
                    brix: qc.brix_actual,
                    ph: qc.ph_actual
                }
            }
        }

        // Merge into skuSteps — match by phase_id (from PLC) or phase_number
        skuSteps.value = skuSteps.value.map(step => {
            const sid = step.sub_step
            const key1 = `${step.phase_id || ''}__${sid}`              // "A1010__10"
            const key2 = `${step.phase_number || ''}__${sid}`          // "p010__10" (raw)
            const key2n = `${normPnum(step.phase_number || '')}__${sid}` // "p10__10" (normalized)
            const ts = stampByKey[key1] || stampByKey[key2] || stampByKey[key2n]
            
            const qc = qcByStep[sid] || {}
            
            if (ts) {
                const d = new Date(ts)
                const matchKey = stampByKey[key1] ? key1 : (stampByKey[key2] ? key2 : key2n)
                const logActual = actualByKey[matchKey]
                return {
                    ...step,
                    stamp_time: d.toLocaleString('th-TH', {
                        day: '2-digit', month: '2-digit', year: '2-digit',
                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                        hour12: false
                    }),
                    // Merge actual_value from DB logs — this is the persistent source of truth.
                    // PLC DB15x7 is cleared on reset; DB logs survive reset.
                    actual_volume: logActual != null ? logActual : step.actual_volume,
                    actual_brix: qc.brix !== undefined ? qc.brix : step.actual_brix,
                    actual_ph: qc.ph !== undefined ? qc.ph : step.actual_ph,
                }
            } else {
                // If there's no log entry for this step, clear any stamped completion values
                return {
                    ...step,
                    stamp_time: undefined
                }
            }
        })
        console.log('[StampTime] Keys in DB:', Object.keys(stampByKey), '| Actuals:', actualByKey)
    } catch (e) {
        console.warn('[StampTime] Failed to fetch step logs:', e)
    }
}

// Auto-refresh stamp times every 30s while batch is active
let _stampRefreshTimer: ReturnType<typeof setInterval> | null = null
const startStampRefresh = () => {
    if (_stampRefreshTimer) clearInterval(_stampRefreshTimer)
    _stampRefreshTimer = setInterval(() => {
        if (selectedBatchId.value) fetchStampTimes(selectedBatchId.value)
    }, 30_000)
}
const stopStampRefresh = () => {
    if (_stampRefreshTimer) { clearInterval(_stampRefreshTimer); _stampRefreshTimer = null }
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

    // Guard: only trust MQTT Phase_ID/Step_ID if PLC Batch_ID matches selected batch
    const plcBatchId = String(plantData.value.Batch_ID || plantData.value.batch_id || '').replace(/\0/g, '').trim()
    const mqttBatchOk = selectedBatchId.value && plcBatchId && plcBatchId !== '-' && plcBatchId !== '0'
        && plcBatchId === selectedBatchId.value

    // App override: P30 scan complete — hold UI at the next phase until PLC catches up
    // Cleared in watch(Phase_ID) ONLY when mqttBatchOk is confirmed and PLC phase >= override phase
    if (appOverrideStepIndex.value >= 0) {
        return appOverrideStepIndex.value  // pure read — never mutate here
    }

    // Primary: Phase_ID + Step_ID from MQTT — but NEVER go backwards from localStepIndex.
    // MQTT shows the LAST CONFIRMED step (e.g. p010/10), not the next PENDING step.
    // localStepIndex is advanced by confirmStepFromRow after each confirmation.
    // → Use Math.max so UI always shows the furthest step the operator has reached.
    if (mqttBatchOk && pPhase && pStep && skuSteps.value.length > 0) {
        const rawPhase = String(pPhase).replace(/\0/g, '').trim()
        const cleanPPhase = rawPhase.match(/^(p\d+)/i)?.[1]?.toLowerCase() || rawPhase.toLowerCase()
        const mqttIdx = skuSteps.value.findIndex(s => {
            const cleanSPhase = String(s.phase_number || s.phase).trim().toLowerCase()
            return cleanSPhase === cleanPPhase && Number(s.sub_step) === pStep
        })
        if (mqttIdx !== -1) {
            // Take the HIGHER of MQTT index and localStepIndex — UI must not step backwards
            return Math.max(mqttIdx, localStepIndex.value)
        }
    }

    // NOTE: Current_Step (1-based seq) fallback is intentionally removed here because
    // Current_Step from PLC is a sequential counter that does NOT map directly to
    // skuSteps array index — using it causes wrong step highlights (e.g. seq=20 → index=19=RO-Water).
    // localStepIndex is always the safe fallback.
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

// ── QC Trap Logic (REQ-8: Brix/pH input during production) ──
const qcDialog = ref(false)
const pendingQcStep = ref<any | null>(null)
const localStepIndex = ref(0)
// When app auto-advances (e.g. P30 scan complete), override the PLC-reported step
// so the UI highlights the correct next step immediately.
// Reset to -1 when PLC MQTT catches up naturally.
const appOverrideStepIndex = ref(-1)
const qcSaving   = ref(false)  // REQ-8: loading state for QC API save

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
        Step_Time_SP: Number(s.step_time || 0),
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
    batchRunning.value = true      // ← CRITICAL: enables STEP_COMPLETE handler
    plcHmiCommand.value = 1        // ← Set HMI Command = 1 (Run) immediately
    setTimeout(() => { plcHmiCommand.value = 2 }, 3000)  // ← Reset to HOLD(2) after 3s pulse
    confirmStartDialog.value = false

    const plantId = activePlantId.value || '1'
    const topic = simCmdTopic(plantId, 'cmd')

    // Send START command to PLC via MQTT (interlock signal)
    publishMessage(topic, {
        command: 'START',
        start: 1,
        batch_id: selectedBatchId.value || '',
        sku_id: selectedSkuId.value || '',
        timestamp: new Date().toISOString()
    })

    // ── CRITICAL FIX: sendStepToPLC writes HMI_Command=1 + step setpoints ──
    // Without this, DB1510 HMI_Command stays at 0 and PLC remains in Stand-By.
    // Must call AFTER publishMessage so the START interlock reaches DB1510 first.
    localStepIndex.value = currentStepIndex.value >= skuSteps.value.length ? 0 : currentStepIndex.value
    setTimeout(() => {
        sendStepToPLC(localStepIndex.value)
        console.log('[ConfirmStart] sendStepToPLC sent at index', localStepIndex.value, 'HMI_Command=1')
    }, 300)

    // Send Batch number to PLC (DB5001)
    const db5001Payload = {
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Plan_ID: batchInfo.value?.plan_id || '-',
        Batch_ID: selectedBatchId.value || '',
        SKU_Name: batchInfo.value?.sku_name || '-',
        Phase_ID: '-',
        Step_ID: 0,
        Address: "DB5001,S24.20",
        Value: selectedBatchId.value || '',
        datatype: "String [20]",
        timestamp: new Date().toISOString()
    }
    const writeTopic = simCmdTopic(plantId, 'write')
    publishMessage(writeTopic, selectedBatchId.value || '')

    lastPlcPayload.value = db5001Payload
    plcCmdLog.value.unshift({ time: new Date().toLocaleTimeString(), topic: writeTopic, payload: db5001Payload })
    if (plcCmdLog.value.length > 10) plcCmdLog.value.pop()

    $q.notify({
        type: 'positive',
        icon: 'rocket_launch',
        message: '🚀 Production STARTED!',
        caption: `Batch: ${selectedBatchId.value} — HMI Command = 1 (Run)`,
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

        // Refresh stamp times immediately from DB
        if (selectedBatchId.value) {
            setTimeout(() => fetchStampTimes(selectedBatchId.value!), 1000)
        }

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

        // ── Software Interlock: validate weight BEFORE auto-advancing ────────────
        // Even if the PLC (or simulator) fires STEP_COMPLETE, the app must verify
        // that weight-based steps are within tolerance. If not → block & alert.
        const aCode = String(currentCompletedStep?.action_code || '')
        const isWeightStep = aCode.startsWith('2') || aCode.startsWith('3')
        if (isWeightStep && currentCompletedStep) {
            const rc = (currentCompletedStep.re_code || '').trim()
            const requiredWeight = productionRequire(currentCompletedStep)
            if (requiredWeight > 0) {
                // Prefer scanned volume (SPP/FH), then live step scale weight
                const scannedVol = scannedVolumeMap.value[rc]
                const actualWeight = scannedVol != null
                    ? scannedVol
                    : getStepLiveWeight(currentCompletedStep)

                if (actualWeight > 0 && !isWeightInTolerance(currentCompletedStep, actualWeight)) {
                    // ⛔ INTERLOCK: weight out of tolerance — block advance
                    batchRunning.value = false
                    const tolHigh = Number(currentCompletedStep.high_tol || (requiredWeight * 0.02))
                    const tolLow  = Number(currentCompletedStep.low_tol  || (requiredWeight * 0.02))
                    $q.notify({
                        type: 'negative',
                        icon: 'lock',
                        message: `⛔ INTERLOCK — Step ${payload.step_no} blocked!`,
                        caption: `Weight out of tolerance. Req: ${requiredWeight.toFixed(3)} kg | Act: ${actualWeight.toFixed(3)} kg | Range: ${(requiredWeight - tolLow).toFixed(3)}–${(requiredWeight + tolHigh).toFixed(3)} kg. Correct weight then confirm manually.`,
                        position: 'center',
                        timeout: 0,  // stays until dismissed
                        actions: [{ label: 'OK', color: 'white' }]
                    })
                    console.warn(`[INTERLOCK] Step ${payload.step_no} (${rc}) blocked — weight ${actualWeight} out of tolerance [${requiredWeight - tolLow}, ${requiredWeight + tolHigh}]`)
                    return // ⛔ DO NOT advance
                }
            }
        }
        // ─────────────────────────────────────────────────────────────────────────

        // Normal Auto-Advance (display only — PLC drives each step via FC1517)
        // Never go backwards: p030 free-scan may have already moved localStepIndex to p040
        const newIdx = completedIndex + 1
        if (newIdx > localStepIndex.value) {
            localStepIndex.value = newIdx
        }
        if (localStepIndex.value < skuSteps.value.length) {
            // [PLC-DRIVE MODE] App does not send step cmd back — PLC fires next step itself
            // setTimeout(() => sendStepToPLC(localStepIndex.value), 500)
        } else {
            batchRunning.value = false
            $q.notify({ type: 'positive', message: `🎉 BATCH COMPLETE!`, position: 'center', timeout: 4000 })
            // Navigate to Production Report automatically
            setTimeout(() => {
                router.push({ path: '/x70-ProductionReport', query: { batch_id: selectedBatchId.value || '' } })
            }, 3500)
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

const confirmQcCheck = async () => {
    if (pendingQcStep.value?.operation_brix_record && !actualBrix.value) {
        $q.notify({ type: 'warning', message: 'Please input Actual Brix' }); return;
    }
    if (pendingQcStep.value?.operation_ph_record && !actualPh.value) {
        $q.notify({ type: 'warning', message: 'Please input Actual pH' }); return;
    }

    // REQ-8: Save to production_qc_records via API
    qcSaving.value = true
    let qcSaveOk = false
    try {
        const step = pendingQcStep.value
        await $fetch<any>(`${appConfig.apiBaseUrl}/production-batches/${selectedBatchId.value}/qc-record`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>,
            body: {
                step_id: step?.sub_step ?? null,
                brix_target: parseSP(step?.brix_sp) > 0 ? parseSP(step.brix_sp) : null,
                brix_actual: actualBrix.value !== '' ? Number(actualBrix.value) : null,
                ph_target:   parseSP(step?.ph_sp) > 0 ? parseSP(step.ph_sp) : null,
                ph_actual:   actualPh.value !== '' ? Number(actualPh.value) : null,
                operator: currentMixOperator.value, operator2: cookOperator.value?.username || null
            }
        })
        $q.notify({ type: 'positive', message: '✅ QC Data Saved!', icon: 'check_circle', timeout: 2000 })
        qcSaveOk = true
    } catch (e: any) {
        console.error('[QC] Save failed:', e)
        // e.data may be a Pydantic validation error object or array — extract readable message
        const detail = e?.data?.detail
        const errMsg = Array.isArray(detail)
            ? detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', ')
            : (typeof detail === 'string' ? detail : (e.message || 'Unknown error'))
        $q.notify({ type: 'negative', message: `QC save failed: ${errMsg}`, timeout: 5000 })
        // Don't block production even if save fails — just log it
    } finally {
        qcSaving.value = false
    }

    // ── "Confirm & Continue" = QC recorded + step confirmed ──────────────────
    // Close dialog FIRST, then advance step with current actualBrix/actualPh still set.
    // skipToleranceCheck=true because QC dialog IS the interlock gate for Brix/pH steps.
    const stepToConfirm = pendingQcStep.value
    qcDialog.value = false
    pendingQcStep.value = null
    batchRunning.value = true
    if (plcHmiCommand.value === 0) plcHmiCommand.value = 2  // ensure HOLD not Abort

    if (stepToConfirm) {
        // Advance step — skip tolerance checks (weight was already confirmed before QC dialog)
        confirmStepFromRow(stepToConfirm, true)  // true = skipToleranceCheck
    }

    // Reset QC values after step has been advanced
    actualBrix.value = ''
    actualPh.value   = ''


    

    // Resume after QC (display only — PLC drives itself)
    if (localStepIndex.value < skuSteps.value.length) {
        // [PLC-DRIVE MODE] App does not send step cmd back — PLC fires next step itself
        // setTimeout(() => sendStepToPLC(localStepIndex.value), 500)
        $q.notify({ type: 'info', message: `Resuming: Step ${localStepIndex.value + 1} active on PLC`, position: 'top', timeout: 1000 })
    } else {
        batchRunning.value = false
        $q.notify({ type: 'positive', message: `🎉 BATCH COMPLETE!`, position: 'center', timeout: 4000 })
        setTimeout(() => {
            router.push({ path: '/x70-ProductionReport', query: { batch_id: selectedBatchId.value || '' } })
        }, 2000)
    }
}

const sendStepToPLC = (index: number) => {
    const s = skuSteps.value[index]
    if (!s) return;
    
    const topic = simCmdTopic(activePlantId.value, 'step_cmd')
    const payload = {
        // --- DB100 IDENTIFIERS ---
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Plan_ID: batchInfo.value?.plan_id || '-',
        Batch_ID: selectedBatchId.value || '-',
        SKU_Name: batchInfo.value?.sku_name || '-',
        Phase_ID: String(s.phase_number || ''),
        Step_ID: Number(s.sub_step || 0),
        
        // --- SETPOINTS ---
        Step_Time_SP: Number(s.step_time || 0), // Conv to seconds
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

// ── Recipe Transfer State & Function ──
const downloadProgress = ref(0)
const downloadDialog = ref(false)
const downloadPhases = ref<any[]>([])
const downloadVerification = ref<any>(null)
const downloadError = ref('')

const closeDownloadDialog = () => {
    downloadDialog.value = false
}

const downloadRecipeToPlc = async (batchId: string) => {
    downloadDialog.value = true
    downloadProgress.value = 0
    downloadPhases.value = []
    downloadVerification.value = null
    downloadError.value = ''
    
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        
        // Stage 1: PREPARE
        downloadProgress.value = 10
        
        // Stage 2: TRANSFER + Stage 3: VERIFY
        const plantId = activePlantId.value || '1'
        const res = await $fetch<any>(`${remoteApiBaseUrl}/plc/send-recipe/${batchId}?plant_id=${Number(plantId)}`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>
        })
        
        downloadProgress.value = 60
        console.log('PLC Recipe Response:', res)
        
        // Show phase-by-phase progress
        if (res.transfer?.phases) {
            for (let i = 0; i < res.transfer.phases.length; i++) {
                downloadPhases.value.push({ ...res.transfer.phases[i], status: 'done' })
                downloadProgress.value = 60 + ((i + 1) / res.transfer.phases.length) * 30
                await new Promise(r => setTimeout(r, 150)) // Visual delay per phase
            }
        }
        
        // Stage 4: VERIFY — show CRC result
        downloadProgress.value = 95
        downloadVerification.value = res.verification
        
        await new Promise(r => setTimeout(r, 500))
        downloadProgress.value = 100
        
        $q.notify({ 
            type: 'positive', 
            icon: 'verified',
            message: `✅ Recipe Downloaded — ${res.transfer?.totalSteps} steps, CRC: ${res.verification?.crcHex}`,
            position: 'top', 
            timeout: 3000 
        })
        
    } catch (e: any) {
        console.error('Failed to download recipe to PLC', e)
        downloadError.value = e?.message || 'Transfer failed'
        $q.notify({ 
            type: 'negative', 
            message: 'Failed to download recipe to PLC', 
            position: 'top' 
        })
    }
}

// ── PLC Commands ──
const sendCommand = async (cmd: 'START' | 'PAUSE' | 'ABORT' | 'NEXT_STEP') => {
    // PAUSE and ABORT are safety-critical — always publish interlock signal
    // even if PLC is offline (backend will write to DB1510 regardless)
    if (cmd === 'ABORT') {
        batchRunning.value = false
        plcHmiCommand.value = 0   // ← Abort/Idle
        publishMessage(simCmdTopic(activePlantId.value, 'cmd'), { command: 'ABORT' })
        return
    } else if (cmd === 'PAUSE') {
        batchRunning.value = false
        plcHmiCommand.value = 2   // ← Hold/Pause
        publishMessage(simCmdTopic(activePlantId.value, 'cmd'), { command: 'PAUSE' })
        return
    }

    // START and NEXT_STEP require PLC to be online
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
        plcHmiCommand.value = 1   // ← Run
        setTimeout(() => { plcHmiCommand.value = 2 }, 3000)  // ← Reset to HOLD(2) after 3s pulse
        // Resume from where we were (PLC feedback), or start from 0
        localStepIndex.value = currentStepIndex.value >= skuSteps.value.length ? 0 : currentStepIndex.value
        
        // --- ADDED CRC CHECKSUM DOWNLOAD DIALOG LOGIC ---
        if (batchInfo.value && batchInfo.value.batch_id) {
            await downloadRecipeToPlc(batchInfo.value.batch_id)
        }
        
        sendStepToPLC(localStepIndex.value)
        $q.notify({ type: 'positive', icon: 'settings_remote', message: `STARTED at Step ${localStepIndex.value + 1}`, position: 'top', timeout: 1500 })
        // Also send START state
        publishMessage(simCmdTopic(activePlantId.value, 'cmd'), { 
            command: 'START',
            Batch_ID: selectedBatchId.value || '-'
        })
        return
    } else if (cmd === 'NEXT_STEP') {
        batchRunning.value = true
        // If we are already ahead (e.g. from P30 override), do not snap back
        if (localStepIndex.value <= currentStepIndex.value) {
            localStepIndex.value = currentStepIndex.value + 1
        }
        if (isPlcConnected.value && localStepIndex.value < skuSteps.value.length) {
            sendStepToPLC(localStepIndex.value)
        }
        return
    }
}


// ── Clear QC Records for a batch (called on Soft Reset / Kill Batch) ──────────
// Removes all Brix/pH QC records from the previous run so they do not
// appear as "ghost" values when the same batch_id is replayed.
const clearQcRecords = async (batchId: string) => {
    if (!batchId) return
    try {
        await $fetch(`${appConfig.apiBaseUrl}/production-batches/${batchId}/qc-records`, {
            method: 'DELETE',
            headers: getAuthHeader() as Record<string, string>
        })
        console.log(`[QC] Cleared QC records for batch ${batchId}`)
    } catch (e) {
        console.warn('[QC] Could not clear QC records:', e)
        // Non-fatal — do not block the reset flow
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
        const batchId = selectedBatchId.value
        try {
            $q.loading.show()
            // Clear QC records first (non-fatal)
            if (batchId) await clearQcRecords(batchId)
            await $fetch<any>(`${appConfig.apiBaseUrl}/plc/plant/${activePlantId.value}/clear-recipe`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>
            })
            
            // Send ABORT just to be safe
            publishMessage(simCmdTopic(activePlantId.value, 'cmd'), { command: 'ABORT' })
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

const softResetBatch = () => {
    if (!selectedBatchId.value) {
        $q.notify({ type: 'warning', message: 'No batch selected to reset.' })
        return
    }
    $q.dialog({
        title: 'Confirm Reset Batch',
        message: `Are you sure you want to soft-reset batch ${selectedBatchId.value}? This will clear DB15x0 (Step CMD), DB15x1 (Recipe), DB15x7 (Actuals), delete all step logs in database, QC records (Brix/pH), and reset status back to Pending.`,
        cancel: true,
        persistent: true,
        color: 'warning'
    }).onOk(async () => {
        const batchId = selectedBatchId.value
        try {
            $q.loading.show()
            // Clear QC records first (non-fatal)
            if (batchId) await clearQcRecords(batchId)
            const remoteApiBaseUrl = appConfig.apiBaseUrl
            const res = await $fetch<any>(`${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/reset-batch/${selectedBatchId.value}`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>
            })
            
            if (res && (res.status === 'success' || res.status === 'partial')) {
                $q.notify({ type: 'positive', message: 'Batch soft reset completed. PLC memory, step logs, and QC records cleared.' })
                
                // Reset ALL step-tracking state before navigating away
                localStepIndex.value = 0
                batchRunning.value = false
                batchInfo.value = null
                selectedBatchId.value = null
                selectedSkuId.value = null
                skuSteps.value = []
                startConfirmed.value = false

                // ── Clear stale MQTT telemetry immediately ──────────────────────────────
                const pid = activePlantId.value
                if (plantsData.value[pid]) {
                    plantsData.value[pid] = {
                        ...plantsData.value[pid],
                        Phase_ID: '', Phase_id: '', phase_id: '',
                        Step_ID: 0,  Step_id: 0,  step_id: 0,
                        Batch_ID: '-', batch_id: '-',
                        Current_Step: 0, current_step: 0,
                    }
                }
                
                const { batch_id, sku_id, plan_id, sku_name, batch_size, ...newQuery } = route.query;
                router.replace({ query: newQuery })
                router.push('/x60-CheckForProduction')
            } else {
                $q.notify({ type: 'negative', message: res?.message || 'Failed to soft reset batch.' })
            }
        } catch (e: any) {
            console.error('Failed to soft reset batch:', e)
            $q.notify({ type: 'negative', message: 'Error calling soft-reset API.' })
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

const getStepLiveWeight = (step: any) => {
    if (!step) return 0
    
    // 1. If we have a scanned volume from the QR label, ALWAYS use it!
    const rc = String(step.re_code || '').trim()
    if (scannedVolumeMap.value[rc] != null) {
        return scannedVolumeMap.value[rc]
    }
    
    // 2. Fallback to live PLC scales
    const whType = prebatchWhMap.value[step.re_code] || ''
    if (whType === 'SPP' || whType === 'FH') {
        return actualHopperWeight.value
    } else {
        return actualTankWeight.value
    }
}

// ── Process Interlock: ALL setpoints must be green before step can advance ──
// Returns { ok: boolean, failed: string[] } — failed lists what's out of range.
// ── Brix/pH SP parser — handles both "65" (number) and "65-67" (range string) ──
const parseSP = (val: any): number => {
    if (!val && val !== 0) return 0
    const s = String(val).trim()
    if (s.includes('-') && s.split('-').length === 2) {
        const parts = s.split('-').map(Number)
        if (!isNaN(parts[0]) && !isNaN(parts[1])) return (parts[0] + parts[1]) / 2  // midpoint
    }
    const n = Number(s)
    return isNaN(n) ? 0 : n
}
// Display: show original range string if range, else formatted number, '-' if empty
const formatSP = (val: any, decimals = 2): string => {
    if (!val && val !== 0) return '-'
    const s = String(val).trim()
    if (!s || s === '0') return '-'
    if (s.includes('-')) return s  // show range as-is e.g. "65-67"
    const n = Number(s)
    return isNaN(n) ? s : n.toFixed(decimals)
}

const isStepAllGreen = (step: any): { ok: boolean; failed: string[] } => {

    const failed: string[] = []

    // 1. Temperature ±5°C (only if SP is set)
    const tempSP = Number(step.temperature || 0)
    if (tempSP > 0) {
        const tempTol = 5  // ±5°C
        if (Math.abs(actualTankTemp.value - tempSP) > tempTol) {
            failed.push(`Temp: ${actualTankTemp.value.toFixed(1)}°C ≠ SP ${tempSP}°C (±${tempTol})`)
        }
    }

    // 2. Agitator RPM ±10% of SP (only if SP is set)
    const agitSP = Number(step.agitator_rpm || 0)
    if (agitSP > 0) {
        const agitTol = agitSP * 0.10
        if (Math.abs(actualAgitatorRpm.value - agitSP) > agitTol) {
            failed.push(`Agitator: ${actualAgitatorRpm.value.toFixed(0)} RPM ≠ SP ${agitSP} RPM (±10%)`)
        }
    }

    // 3. High Shear RPM ±10% of SP (only if SP is set)
    const hsSP = Number(step.high_shear_rpm || 0)
    if (hsSP > 0) {
        const hsTol = hsSP * 0.10
        if (Math.abs(actualHighShearRpm.value - hsSP) > hsTol) {
            failed.push(`High Shear: ${actualHighShearRpm.value.toFixed(0)} RPM ≠ SP ${hsSP} RPM (±10%)`)
        }
    }

    // 4. Brix — manual lab input, only check if step requires QC Brix record
    //    operation_brix_record=1 → lab must input actualBrix before confirm
    if (step.operation_brix_record && parseSP(step.brix_sp) > 0) {
        const brixSP  = parseSP(step.brix_sp)
        const brixTol = brixSP * 0.05
        const brixAct = Number(actualBrix.value || 0)
        if (brixAct <= 0) {
            failed.push(`Brix: not recorded — lab must enter Brix before confirming`)
        } else if (Math.abs(brixAct - brixSP) > brixTol) {
            failed.push(`Brix: ${brixAct.toFixed(2)} ≠ SP ${formatSP(step.brix_sp)} (±5%)`)
        }
    }

    // 5. pH — manual lab input, only check if step requires QC pH record
    //    operation_ph_record=1 → lab must input actualPh before confirm
    if (step.operation_ph_record && parseSP(step.ph_sp) > 0) {
        const phSP  = parseSP(step.ph_sp)
        const phTol = 0.3
        const phAct = Number(actualPh.value || 0)
        if (phAct <= 0) {
            failed.push(`pH: not recorded — lab must enter pH before confirming`)
        } else if (Math.abs(phAct - phSP) > phTol) {
            failed.push(`pH: ${phAct.toFixed(2)} ≠ SP ${formatSP(step.ph_sp)} (±${phTol})`)
        }
    }

    // 6. Timer — PLC Step_Timer is COUNTDOWN (stepTimeSec → 0). Done when remaining == 0.
    //    step_time is in SECONDS (DB). currentRemaining = seconds left from PLC.
    const stepTimeSec = Number(step.step_time || 0)
    if (stepTimeSec > 0) {
        const remaining = currentRemaining.value   // countdown from PLC: 240→0
        if (remaining > 0) {
            const remMin = Math.floor(remaining / 60)
            const remSec = Math.floor(remaining % 60)
            failed.push(`Timer: ${remMin}m ${remSec}s remaining / ${formatDuration(stepTimeSec)} total`)
        }
    }

    // 7. QR Scan Requirement check
    const isFree = isFreeScanPhase(step.phase_number)
    const stepIsScanning = (String(step.action_code || '').startsWith('2') || String(step.action_code || '').startsWith('3')) &&
        step.re_code && step.re_code !== '-' && step.re_code.trim() !== '' &&
        (prebatchWhMap.value[step.re_code] === 'SPP' || prebatchWhMap.value[step.re_code] === 'FH')
    const hasScanSteps = skuSteps.value.some((s: any) =>
        s.phase_number === step.phase_number &&
        (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
        s.re_code && s.re_code !== '-' && s.re_code.trim() !== '' &&
        (prebatchWhMap.value[s.re_code] === 'SPP' || prebatchWhMap.value[s.re_code] === 'FH')
    )
    if (isFree && hasScanSteps && stepIsScanning) {
        // FREE-SCAN Phase: only check scan-completion for steps that ARE scan steps.
        // Non-scan steps (RO-Water, Mixing, etc.) in the same phase proceed normally.
        const matchedPhase = step.phase_number
        const allFreeScan = skuSteps.value.filter((s: any) =>
            s.phase_number === matchedPhase &&
            (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
            s.re_code && s.re_code !== '-' && s.re_code.trim() !== '' &&
            (prebatchWhMap.value[s.re_code] === 'SPP' || prebatchWhMap.value[s.re_code] === 'FH')
        )
        const scannedCount = allFreeScan.filter((s: any) => {
            return (scannedVolumeMap.value[s.re_code] != null) || (s.stamp_time != null && s.stamp_time !== '-')
        }).length
        if (scannedCount < allFreeScan.length) {
            failed.push(`${matchedPhase} QR: only ${scannedCount}/${allFreeScan.length} ingredients scanned`)
        }
    } else if (!isFree || !hasScanSteps) {
        // Standard (non-free-scan) steps: check this specific step's ingredient only
        const hasReCode = step.re_code && step.re_code !== '-' && step.re_code.trim() !== ''
        if (hasReCode) {
            const whType = prebatchWhMap.value[step.re_code] || ''
            if (whType === 'SPP' || whType === 'FH') {
                const isScanned = (scannedVolumeMap.value[step.re_code] != null) || (step.stamp_time != null && step.stamp_time !== '-')
                if (!isScanned) {
                    failed.push(`Barcode: Ingredient ${step.re_code} must be scanned`)
                }
            }
        }
    }

    // 8. Weight (Require) tolerance check
    const requiredWeight = productionRequire(step)
    if (requiredWeight > 0) {
        const liveWt = getStepLiveWeight(step)
        if (liveWt <= 0 || !isWeightInTolerance(step, liveWt)) {
            const tolHigh = Number(step.high_tol || (requiredWeight * 0.02))
            const tolLow  = Number(step.low_tol  || (requiredWeight * 0.02))
            failed.push(`Weight: ${liveWt.toFixed(2)} kg ≠ SP ${requiredWeight.toFixed(2)} kg (range: ${(requiredWeight - tolLow).toFixed(2)}–${(requiredWeight + tolHigh).toFixed(2)})`)
        }
    }

    return { ok: failed.length === 0, failed }
}

const confirmStepFromRow = (step: any, skipToleranceCheck: boolean = false) => {
    if (!isPlcConnected.value) {
        $q.notify({ type: 'negative', message: 'PLC is offline!', position: 'top' })
        return
    }
    
    let isInterlockFailed = false
    const aCode = String(step.action_code || '')
    const rc = (step.re_code || '').trim()

    // ── Case 1: SPP/FH — volume confirmed from QR scan ──────────────────────────
    // Even though we trust the QR label, the scanned volume must still be within
    // tolerance. If not green, set isInterlockFailed = true but allow confirmation.
    const scannedVol = scannedVolumeMap.value[rc]
    if (scannedVol != null && (aCode.startsWith('2') || aCode.startsWith('3'))) {
        const requiredWeight = productionRequire(step)
        if (requiredWeight > 0 && !isWeightInTolerance(step, scannedVol)) {
            const tolHigh = Number(step.high_tol || (requiredWeight * 0.02))
            const tolLow  = Number(step.low_tol  || (requiredWeight * 0.02))
            isInterlockFailed = true
            $q.notify({
                type: 'warning',
                icon: 'scale',
                message: '⚠️ Scanned volume out of tolerance!',
                caption: `Req: ${requiredWeight.toFixed(3)} kg | Scanned: ${scannedVol.toFixed(3)} kg | Range: ${(requiredWeight - tolLow).toFixed(3)}–${(requiredWeight + tolHigh).toFixed(3)} kg — Confirmed without Auto Next.`,
                position: 'center',
                timeout: 5000,
                actions: [{ label: 'OK', color: 'white' }]
            })
        }
    }

    // ── Weight Check: ALL steps with require > 0 ────────────────────────────────
    // Applies to 1x (LS/RO Batching), 2x/3x (manual add) — any step with a target weight.
    // SPP/FH scan steps use scannedVol (already checked in Case 1 above).
    if (!skipToleranceCheck) {
        const requiredWeight = productionRequire(step)
        if (requiredWeight > 0) {
            const liveWt = scannedVolumeMap.value[rc] != null
                ? scannedVolumeMap.value[rc]   // scanned vol takes priority
                : getStepLiveWeight(step)       // tank/hopper scale
            if (liveWt > 0 && !isWeightInTolerance(step, liveWt)) {
                const tolHigh = Number(step.high_tol || (requiredWeight * 0.02))
                const tolLow  = Number(step.low_tol  || (requiredWeight * 0.02))
                isInterlockFailed = true
                $q.notify({
                    type: 'warning',
                    icon: 'scale',
                    message: '⚠️ Weight (Require) not in range!',
                    caption: `Req: ${requiredWeight.toFixed(2)} kg | Act: ${liveWt.toFixed(2)} kg | Range: ${(requiredWeight - tolLow).toFixed(2)}–${(requiredWeight + tolHigh).toFixed(2)} kg — Confirmed without Auto Next.`,
                    position: 'center',
                    timeout: 5000,
                    actions: [{ label: 'OK', color: 'white' }]
                })
            }
        }
    }

    // ── Process Interlock: Temp / Agitator / HighShear / Brix / pH ────────────
    if (!skipToleranceCheck) {
        const { ok, failed } = isStepAllGreen(step)
        if (!ok) {
            isInterlockFailed = true
            $q.notify({
                type: 'warning',
                icon: 'warning',
                message: '⚠️ Process parameters out of tolerance (Software Interlock)',
                caption: failed.join(' | ') + ' — Confirmed step without Auto Next.',
                position: 'center',
                timeout: 5000,
                actions: [{ label: 'OK', color: 'white' }]
            })
        }
    }
    
    hasConfirmedCurrentStep.value = true
    currentStepBypassed.value = skipToleranceCheck
    
    const { ok: interlocksOk } = isStepAllGreen(step)
    const naturalGreen = interlocksOk && isAppReady.value
    
    let immediateHmiCommand = 2
    if (currentStepBypassed.value) {
        immediateHmiCommand = 5
    } else if (naturalGreen) {
        immediateHmiCommand = 4
    } else {
        immediateHmiCommand = 1
    }
    
    const topic = simCmdTopic(activePlantId.value, 'step_cmd')
    const payload = {
        Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
        Batch_ID: selectedBatchId.value || '-',
        Phase_ID: String(step.phase_number || ''),
        Step_ID: Number(step.sub_step || 0),
        Confirm_Phase: String(step.phase_number || ''),
        Confirm_Step: Number(step.sub_step || 0),
        Cmd_StartTimer: step.step_time ? 1 : 0,
        HMI_Command: immediateHmiCommand,
        // --- Setpoints ---
        Step_Time_SP: Number(step.step_time || 0),
        Step_Status: 1,
        Material_ID: step.mat_sap_code || '',
        Re_Code_ID: step.re_code || '',
        Req_Qty: productionRequire(step),
        TT_SP: [Number(step.temperature || 0)],
        Agitator_Speed: Number(step.agitator_rpm || 0),
        High_Shear_SP: Number(step.high_shear_rpm || 0),
        PH_Target: Number(step.ph_sp || 0),
        Brix_Target: Number(step.brix_sp || 0),
        Cmd_NewStep: true
    }
    
    publishMessage(topic, payload)
    
    plcHmiCommand.value = immediateHmiCommand
    if (immediateHmiCommand === 1) {
        setTimeout(() => {
            if (plcHmiCommand.value === 1) {
                plcHmiCommand.value = 2
            }
        }, 3000)
    }
    
    // DO NOT optimistically advance localStepIndex here.
    // The UI must wait for the PLC status telemetry (MQTT) to update and change currentStepIndex,
    // which will then update localStepIndex via the watch(currentStepIndex) observer.
    console.log(`[Confirm] Step ${step.sub_step} confirmed. Waiting for PLC telemetry to advance.`)
    
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

// ── QR Scan Dialog (SPP / FH steps) ──
const qrScanDialog = ref(false)
const qrScanBuffer = ref('')
const qrScanStep = ref<any>(null)

const openQrScanDialog = (step: any) => {
    qrScanStep.value = step
    qrScanBuffer.value = ''
    _qrAccum   = ''   // clear non-reactive accumulators
    _scanAccum = ''
    scanBuffer.value = ''
    if (scanTimeout) { clearTimeout(scanTimeout); scanTimeout = null }
    qrScanDialog.value = true
}

const onQrScanInput = (val: string) => {
    if (val && val.trim().length > 3) {
        qrScanDialog.value = false
        handleScan(val.trim())
        qrScanBuffer.value = ''
    }
}

// ── Fault Alarm (wrong QR scan) ──
const faultAlarmDialog = ref(false)
const faultAlarmInfo = ref({ scanned: '', expected: '', stepName: '', re_code: '' })

const playAlarmBeep = () => {
    try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const playTone = (freq: number, start: number, duration: number) => {
            const osc = ctx.createOscillator()
            const gain = ctx.createGain()
            osc.connect(gain)
            gain.connect(ctx.destination)
            osc.frequency.value = freq
            osc.type = 'square'
            gain.gain.setValueAtTime(0.3, ctx.currentTime + start)
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration)
            osc.start(ctx.currentTime + start)
            osc.stop(ctx.currentTime + start + duration)
        }
        playTone(880, 0, 0.15)
        playTone(660, 0.2, 0.15)
        playTone(440, 0.4, 0.3)
    } catch { /* audio not supported */ }
}

const triggerFaultAlarm = (scanned: string, expected: string, step: any) => {
    faultAlarmInfo.value = {
        scanned,
        expected: expected || 'None',
        stepName: step?.re_code || step?.description || '',
        re_code: step?.re_code || ''
    }
    faultAlarmDialog.value = true
    qrScanDialog.value = false
    // ── Clear ALL accumulators (reactive + non-reactive) ──
    scanBuffer.value = ''
    qrScanBuffer.value = ''
    _scanAccum = ''
    _qrAccum   = ''
    if (scanTimeout) { clearTimeout(scanTimeout); scanTimeout = null }
    playAlarmBeep()
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

// All steps completed = localStepIndex has moved past the last step
const allStepsDone = computed(() =>
    skuSteps.value.length > 0 && (localStepIndex.value ?? 0) >= skuSteps.value.length
)

// ── markBatchDone: call backend to set status = Done ──────────────────────────
// Uses selectedBatchId (string) with the /complete/ endpoint.
// Guards against double-calls via batchInfo.value.status check.
async function markBatchDone(trigger: string = 'auto') {
    const batchIdStr = selectedBatchId.value
    if (!batchIdStr) return
    if (batchInfo.value?.status === 'Done') return  // already done
    try {
        const remoteApiBaseUrl = appConfig.apiBaseUrl
        await $fetch(`${remoteApiBaseUrl}/production-batches/complete/${batchIdStr}`, {
            method: 'PATCH',
            headers: getAuthHeader() as Record<string, string>,
            body: { completed_by: `operator [${trigger}]` }
        })
        $q.notify({ type: 'positive', icon: 'check_circle', message: '✅ Batch marked as Done', position: 'top-right', timeout: 4000 })
        if (batchInfo.value) {
            batchInfo.value.status = 'Done'
            batchInfo.value.done = true
        }
        console.log(`[Batch Done] ${batchIdStr} → Done (triggered by: ${trigger})`)
    } catch (e: any) {
        // 400 "already Done" is OK — just log it
        const msg = e?.data?.detail || String(e)
        if (msg.includes('already')) {
            console.log(`[Batch Done] ${batchIdStr} already Done`)
            if (batchInfo.value) batchInfo.value.status = 'Done'
        } else {
            console.error('[Batch Done] Failed:', e)
            $q.notify({ type: 'warning', message: 'ไม่สามารถอัปเดต Batch Done ได้ — ตรวจสอบ API', position: 'top-right' })
        }
    }
}

// Auto-trigger Done when all steps are done AND PLC is in Stand By (offline scenario)
watch(allStepsDone, async (done) => {
    if (!done) return
    if (batchInfo.value?.status === 'Done') return
    // Wait a short moment to ensure the last step stamp_time is written
    await new Promise(r => setTimeout(r, 1500))
    await markBatchDone('all-steps-completed')
})

// ── Passive Tracking State ──
// PLC Step_Timer is a COUNTDOWN: starts at step_time setpoint and decrements to 0.
// 'remaining' = seconds left on the timer (0 = timer done).
const currentRemaining = computed(() => Number(plantData.value.Step_Timer || 0))
const currentElapsed = currentRemaining  // alias kept for legacy references
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

// Scroll active step row into view within the Quasar scroll container
const stepTableScroll = ref<HTMLElement | null>(null)

const scrollToActiveStep = async () => {
    // Wait 2 ticks for Vue reactive + DOM render to complete
    await nextTick()
    await nextTick()
    const el = document.querySelector('.active-step') as HTMLElement | null
    if (!el) {
        // Retry once more after short delay in case data is still rendering
        setTimeout(async () => {
            await nextTick()
            const el2 = document.querySelector('.active-step') as HTMLElement | null
            if (el2) doScroll(el2)
        }, 500)
        return
    }
    doScroll(el)
}

const doScroll = (el: HTMLElement) => {
    const cont = stepTableScroll.value || (el.closest('.scroll') as HTMLElement)
    if (cont && cont.scrollHeight > cont.clientHeight) {
        // Use getBoundingClientRect — correctly relative to viewport regardless of offsetParent chain
        const containerRect = cont.getBoundingClientRect()
        const elRect = el.getBoundingClientRect()
        // Position of element relative to the top of the scroll container
        const relTop = elRect.top - containerRect.top
        // Desired scrollTop to center the active row
        const newScrollTop = cont.scrollTop + relTop - cont.clientHeight / 2 + elRect.height / 2
        cont.scrollTop = Math.max(0, newScrollTop)
        console.log('[Scroll] ✅ scrollTop set to:', Math.max(0, newScrollTop),
            '| relTop:', relTop, '| cont.scrollTop was:', cont.scrollTop,
            '| scrollHeight:', cont.scrollHeight, '| clientHeight:', cont.clientHeight)
    } else {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        console.log('[Scroll] fallback scrollIntoView — no overflow')
    }
}

// Ensure active step expands and scrolls into view when currentStepIndex changes
watch(currentStepIndex, (newIdx, oldIdx) => {
    // Skip if no data loaded yet (fires immediately on mount when skuSteps is empty)
    if (skuSteps.value.length === 0) return
    if (newIdx < skuSteps.value.length) {
        // Sync localStepIndex with the active step index driven by PLC telemetry
        localStepIndex.value = newIdx
        const step = skuSteps.value[newIdx]
        if (step) expandedPhases.value[step.phase_number || '0'] = true
        if (newIdx !== oldIdx || oldIdx === undefined) scrollToActiveStep()
        
        // Reset confirm/bypass flags and pulse run command (1) for 3 seconds when step index advances
        if (oldIdx !== undefined && newIdx > oldIdx) {
            plcHmiCommand.value = 1
            setTimeout(() => { plcHmiCommand.value = 2 }, 3000)
            hasConfirmedCurrentStep.value = false
            currentStepBypassed.value = false
        }
    }
}, { immediate: true })

// Trigger scroll when skuSteps first loads (restore case where currentStepIndex
// stays at the same value so watch above doesn't fire again)
watch(() => skuSteps.value.length, (newLen, oldLen) => {
    if (newLen > 0 && oldLen === 0) {
        const idx = currentStepIndex.value
        if (idx < newLen) {
            const step = skuSteps.value[idx]
            if (step) expandedPhases.value[step.phase_number || '0'] = true
        }
        scrollToActiveStep()
    }
})

// ── Rinse Step Notification ──────────────────────────────────────────────────
// Notify operator when the active step is a manual MIX/rinse step (e.g. กลั้วภาชนะด้วย RO water)
// These steps have no SPP/FH scan requirement → operator must press ▶ manually to advance.
watch(currentStep, (step) => {
    if (!step) return
    const aCode = String(step.action_code || '')
    const reCode = String(step.re_code || '').toLowerCase()
    // Only notify for explicit rinse steps: action_code 20020 + re_code contains 'RO-Water'
    const isRinseStep = aCode === '20020' && reCode.includes('ro-water')
    if (!isRinseStep) return
    $q.notify({
        type: 'info',
        icon: 'water_drop',
        color: 'cyan-8',
        message: `🪣 กลั้วสารด้วย RO water`,
        caption: `Phase ${step.phase_number} Step ${step.sub_step} — ดำเนินการเสร็จแล้วกด ▶ เพื่อไปขั้นตอนต่อไป`,
        position: 'top-right',
        timeout: 6000,
        actions: [{ label: 'เข้าใจแล้ว', color: 'white', handler: () => {} }]
    })
}, { immediate: false })

// the overridden phase. Requires mqttBatchOk to prevent false clears when Batch_ID
// doesn't match (which would snap back to the wrong step via localStepIndex fallback).
watch(() => ({
    phase: plantData.value.Phase_ID || plantData.value.Phase_id || plantData.value.phase_id,
    batchId: plantData.value.Batch_ID || plantData.value.batch_id || ''
}), ({ phase: plcPhaseRaw, batchId }) => {
    if (appOverrideStepIndex.value < 0) return  // nothing to clear

    // Require Batch_ID to match before trusting PLC phase data
    const plcBatchId = String(batchId).replace(/\0/g, '').trim()
    const batchOk = selectedBatchId.value && plcBatchId && plcBatchId !== '-' && plcBatchId !== '0'
        && plcBatchId === selectedBatchId.value
    if (!batchOk) return  // keep override until Batch_ID is confirmed

    const overridePhase = skuSteps.value[appOverrideStepIndex.value]?.phase_number
    if (!overridePhase) return
    const plcPhase = String(plcPhaseRaw || '').replace(/\0/g, '').trim().toLowerCase().match(/^(p\d+)/i)?.[1]?.toLowerCase()
    const plcNum = plcPhase ? parseInt(plcPhase.replace(/\D/g, ''), 10) : 0
    const overrideNum = parseInt(overridePhase.replace(/\D/g, ''), 10)
    if (plcNum > 0 && plcNum >= overrideNum) {
        appOverrideStepIndex.value = -1
    }
}, { deep: true })



// ── Production Weights from Batch Data ──
// Prebatch items contain the actual production weights (required_volume)
// which are already calculated for the specific batch size.
const prebatchWeightMap = ref<Record<string, number>>({})
const prebatchIdMap = ref<Record<string, string>>({})
const prebatchWhMap = ref<Record<string, string>>({})
const scannedVolumeMap = ref<Record<string, number>>({}) // volume confirmed from QR scan per re_code

// ── App → PLC Interlock: isAppReady ───────────────────────────────────────
// Returns true only when operator-side conditions are met.
// Heartbeat sends hmi_command=2 (HOLD) while false.
//
// ⚠️ IMPORTANT: Process parameters (Temp / Agitator / HighShear) are controlled
// BY the PLC AFTER it receives HMI_Command=1. We must NOT block HMI=1 waiting
// for those params — that creates a deadlock (PLC can't ramp agitator without Run).
// isStepAllGreen() is kept for UI indicators + confirm warnings, NOT for this interlock.
const isAppReady = computed(() => {
    if (!batchRunning.value) return true  // batch not started → don't block PLC
    const step = currentStep.value
    if (!step) return true               // no active step → don't block

    const aCode = String(step.action_code || '')
    const hasReCode = step.re_code && step.re_code !== '-' && step.re_code.trim() !== ''
    const isManualScanStep = (aCode.startsWith('2') || aCode.startsWith('3')) && hasReCode

    // Only block for manual scan steps where operator hasn't scanned yet.
    // Weight check also only relevant here (after scan, before confirm).
    if (isManualScanStep) {
        const isScanned = scannedVolumeMap.value[step.re_code] != null
        if (!isScanned) return false   // ← HOLD: scan not done yet

        // Weight in tolerance after scan
        const liveWt = getStepLiveWeight(step)
        if (productionRequire(step) > 0 && !isWeightInTolerance(step, liveWt)) return false
    }

    // ✅ All operator-side conditions met — PLC may run.
    // Process params (temp, agitator) are PLC's responsibility after HMI=1.
    return true
})


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
        // Build whMap with BOTH original and lowercase-normalized keys for robust lookup
        const whMapFinal: Record<string, string> = {}
        for (const [k, v] of Object.entries(whMap)) {
            whMapFinal[k] = v as string
            whMapFinal[k.toLowerCase()] = v as string  // fallback for case-insensitive match
        }
        prebatchWhMap.value = whMapFinal
        console.log('[Production Weights] Loaded weights:', map)
        console.log('[Production Weights] WH map:', whMapFinal)
        console.log('[Production Weights] ID map:', idMap)
    } catch (e) {
        console.warn('[Production Weights] Could not fetch prebatch items, using standard recipe weights', e)
        prebatchWeightMap.value = {}
        prebatchIdMap.value = {}
        prebatchWhMap.value = {}
    }
}

/** Lookup WH for a step with case-insensitive + alphanumeric-normalized fallback.
 * Handles re_code mismatches like "Kelcogel (Gellan Gum" vs "Kelcogel (Gellan Gum)" */
const getStepWh = (step: any): string => {
    const rc = (step.re_code || '').trim()
    if (!rc) return ''
    // 1. Exact match
    if (prebatchWhMap.value[rc]) return prebatchWhMap.value[rc]
    // 2. Case-insensitive match (also catches lowercase keys stored in whMapFinal)
    const lower = rc.toLowerCase()
    if (prebatchWhMap.value[lower]) return prebatchWhMap.value[lower]
    // 3. Alphanumeric-normalized match: strips ALL non-alphanum chars
    //    catches "Kelcogel (Gellan Gum" vs "Kelcogel (Gellan Gum)" (missing closing paren)
    const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')
    const rcNorm = norm(rc)
    const key = Object.keys(prebatchWhMap.value).find(k => norm(k) === rcNorm)
    return key ? prebatchWhMap.value[key] : ''
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
                   skuId = parts[0] || '-'
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
            
        await fetchSkuSteps(selectedSkuId.value || '-', batchId)
        await fetchPrebatchWeights(batchId)
        
        startConfirmed.value = true
        batchRunning.value = true
        // When restoring a running batch, default HMI to HOLD(2) not Abort(0).
        // Operator must press Confirm to send 1 (advance) or Pause/Start to reset.
        if (plcHmiCommand.value === 0) plcHmiCommand.value = 2

        // Strategy: use target.active_step from DB1511 as primary source (most reliable — it's
        // what the PLC actually has as its running step, not the last completed step).
        // Fallback chain: DB1511 active_step → MQTT Phase_ID/Step_ID → DB1517 actual phase_id/step_id
        let restoredIdx = -1

        try {
            const remoteApiBaseUrl = appConfig.apiBaseUrl
            const statusData = await $fetch<any>(`${remoteApiBaseUrl}/plc/plant/${activePlantId.value}/recipe-status`, {
                headers: getAuthHeader() as Record<string, string>
            })

            // PRIMARY: DB1511 target.active_step (sequence number of currently running step)
            const activeSeq = Number(statusData?.target?.active_step ?? 0)
            if (activeSeq > 0 && skuSteps.value.length > 0) {
                const idx = skuSteps.value.findIndex(s => Number(s.id) === activeSeq)
                if (idx !== -1) {
                    restoredIdx = idx
                    console.log(`[Restore] ✅ PRIMARY: Restored via DB1511 active_step=${activeSeq} → index ${idx}`)
                }
            }

            // SECONDARY: DB1517 actual phase_id + step_id (last completed step → use next one)
            if (restoredIdx === -1) {
                const actual = statusData?.actual
                const aPhase = actual?.phase_id ? String(actual.phase_id).replace(/\0/g, '').trim() : ''
                const aStep = actual?.step_id ? Number(actual.step_id) : 0
                if (aPhase && aStep && skuSteps.value.length > 0) {
                    const completedIdx = skuSteps.value.findIndex(s => {
                        const cleanSPhase = String(s.phase_number || s.phase).trim()
                        return cleanSPhase === aPhase && Number(s.sub_step) === aStep
                    })
                    // Use the NEXT step after the last completed one
                    if (completedIdx !== -1 && completedIdx + 1 < skuSteps.value.length) {
                        restoredIdx = completedIdx + 1
                        console.log(`[Restore] ✅ SECONDARY: Restored via DB1517 last completed (${aPhase}/${aStep}) → next index ${restoredIdx}`)
                    }
                }
            }
        } catch (apiErr) {
            console.warn('[Restore] Could not fetch recipe-status from REST API:', apiErr)
        }

        // TERTIARY: MQTT Phase_ID/Step_ID (only if REST API failed AND PLC batch_id matches)
        // Guard: if PLC was reset, Batch_ID in MQTT becomes '-' → don't trust Phase_ID/Step_ID
        if (restoredIdx === -1) {
            const plcBatchId = String(plantData.value.Batch_ID || plantData.value.batch_id || '').replace(/\0/g, '').trim()
            const batchIdMatches = plcBatchId && plcBatchId !== '-' && plcBatchId !== '0' && plcBatchId === batchId
            if (batchIdMatches) {
                const pPhase = String(plantData.value.Phase_ID || plantData.value.Phase_id || plantData.value.phase_id || '').replace(/\0/g, '').trim()
                const pStep = Number(plantData.value.Step_ID || plantData.value.Step_id || plantData.value.step_id || 0)
                if (pPhase && pStep && skuSteps.value.length > 0) {
                    restoredIdx = skuSteps.value.findIndex(s => {
                        const cleanSPhase = String(s.phase_number || s.phase).trim()
                        return cleanSPhase === pPhase && Number(s.sub_step) === pStep
                    })
                    if (restoredIdx !== -1) {
                        console.log(`[Restore] ✅ TERTIARY: Restored via MQTT (${pPhase}/${pStep}) → index ${restoredIdx}`)
                    }
                }
            } else {
                console.log(`[Restore] ⚠️ TERTIARY skipped — PLC batch_id '${plcBatchId}' ≠ '${batchId}' (PLC was reset or different batch)`)
            }
        }

        // QUATERNARY: production_step_logs from MySQL (survives PLC reset — most reliable source)
        // Find the last completed step from DB logs, then advance to next pending step.
        // This handles PLC reset scenarios where all PLC data sources show wrong seq.
        if (restoredIdx === -1 || restoredIdx === 0) {
            try {
                const remoteApiBaseUrl = appConfig.apiBaseUrl
                const logsData = await $fetch<any>(
                    `${remoteApiBaseUrl}/production-batches/${batchId}/logs`,
                    { headers: getAuthHeader() as Record<string, string> }
                )
                const logs: any[] = Array.isArray(logsData) ? logsData : (logsData?.logs || [])
                if (logs.length > 0 && skuSteps.value.length > 0) {
                    // Find the last completed step log (highest completed_at)
                    const sorted = [...logs].sort((a, b) =>
                        new Date(b.completed_at || 0).getTime() - new Date(a.completed_at || 0).getTime()
                    )
                    // Build set of completed (phase_id, step_id) combos — normalized phase key
                    const normP = (s: string) => s ? s.replace(/^(p)(0+)/, (_: any, p: string) => p) : s
                    // Find the LAST step in skuSteps order that has a completed log
                    let lastCompletedSkuIdx = -1
                    for (let i = skuSteps.value.length - 1; i >= 0; i--) {
                        const s = skuSteps.value[i]
                        const pn = normP(s.phase_number || '')
                        const matched = logs.find(lg => {
                            const lp = normP(String(lg.phase_id || ''))
                            return lp === pn && Number(lg.step_id) === Number(s.sub_step)
                        })
                        if (matched) {
                            lastCompletedSkuIdx = i
                            break
                        }
                    }
                    if (lastCompletedSkuIdx !== -1) {
                        const nextIdx = lastCompletedSkuIdx + 1
                        // Only update if this gives a HIGHER index than current (never go backwards)
                        if (nextIdx > restoredIdx && nextIdx < skuSteps.value.length) {
                            restoredIdx = nextIdx
                            const lc = skuSteps.value[lastCompletedSkuIdx]
                            console.log(`[Restore] ✅ QUATERNARY: DB logs last completed (${lc?.phase_number}/${lc?.sub_step}) → next index ${restoredIdx}`)
                        } else if (nextIdx >= skuSteps.value.length) {
                            restoredIdx = skuSteps.value.length - 1
                            console.log(`[Restore] ✅ QUATERNARY: All steps completed → last index ${restoredIdx}`)
                        }
                    }
                }
            } catch (logErr) {
                console.warn('[Restore] QUATERNARY: Could not fetch step logs:', logErr)
            }
        }

        if (restoredIdx !== -1) {
            localStepIndex.value = restoredIdx
            const restoredStep = skuSteps.value[restoredIdx]
            if (restoredStep) expandedPhases.value[restoredStep.phase_number || '0'] = true
            // Scroll after DOM update — use 600ms to wait for all async renders (brix/pH fetch etc)
            await nextTick()
            setTimeout(() => scrollToActiveStep(), 600)
        } else {
            console.warn('[Restore] ⚠️ Could not determine current step from any source. Defaulting to step 0.')
        }
        $q.notify({ type: 'info', message: `Restored active batch ${batchId} from PLC.`, position: 'top', icon: 'settings_backup_restore' })
    } catch (e) {
        console.warn('Failed to restore batch from PLC:', e)
    } finally {
        loading.value = false
    }
}

watch([plcActiveBatchId, () => loading.value], async ([plcBatchId, newLoading]) => {
    if (newLoading) return
    
    if (!selectedBatchId.value) {
        if (plcBatchId && plcBatchId !== '-' && plcBatchId !== '0') {
            console.log('Detected active batch on PLC, restoring:', plcBatchId)
            restoreBatchFromPlc(plcBatchId)
        }
    } else {
        // If a batch is currently selected, but PLC active batch ID has changed or been cleared
        if (plcBatchId !== selectedBatchId.value) {
            console.log(`PLC active batch ID (${plcBatchId}) differs from selected (${selectedBatchId.value})`)
            // Fetch status of the selected batch from DB to see if it was reset
            try {
                const remoteApiBaseUrl = appConfig.apiBaseUrl
                const batch = await $fetch<any>(`${remoteApiBaseUrl}/production-batches/${selectedBatchId.value}`, {
                    headers: getAuthHeader() as Record<string, string>
                })
                if (batch && (batch.status === 'Pending' || plcBatchId === '-' || plcBatchId === '')) {
                    $q.notify({
                        type: 'warning',
                        message: 'PLC batch was cleared or reset. Returning to production check screen.',
                        position: 'top'
                    })
                    // Clear local states
                    localStepIndex.value = 0
                    batchRunning.value = false
                    batchInfo.value = null
                    selectedBatchId.value = null
                    selectedSkuId.value = null
                    skuSteps.value = []
                    startConfirmed.value = false
                 scannedVolumeMap.value = {}
                    
                    // Remove query parameters and redirect
                    const { batch_id, sku_id, plan_id, sku_name, batch_size, ...newQuery } = route.query
                    router.replace({ query: newQuery })
                    router.push('/x60-CheckForProduction')
                }
            } catch (err) {
                console.warn('Failed to fetch batch status in watch:', err)
            }
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

const isFreeScanPhase = (phaseNumber: any) => {
    if (!phaseNumber) return false
    const norm = String(phaseNumber).toLowerCase().replace(/[^0-9]/g, '')
    const num = parseInt(norm, 10)
    if (isNaN(num)) return false
    // p010–p069: free-scan zone (any order within phase_number)
    // p050–p069 = สารละลาย (solution) phases — need free scan same as p010–p049
    // hasScanSteps filter ensures phases without SPP/FH scan steps fall through to normal flow.
    return num >= 10 && num <= 69
}

const handleScan = (scannedText: string) => {
    // ── Parse QR JSON — strip newlines/CR that scanners may inject mid-data ──
    const cleanText = scannedText.replace(/[\r\n]/g, '').trim()
    let qrData: any = null
    try { qrData = JSON.parse(cleanText) } catch { /* plain barcode */ }

    // Extract ID: if JSON use 'b' field, otherwise use raw text
    const barcodeId = qrData?.b ?? cleanText

    const normalize = (str: string) => str.toLowerCase().replace(/[^a-z0-9]/g, '')
    const barcodeNorm = normalize(barcodeId)
    // Extract just the ingredient part of barcode (strip batch_id prefix) for reverse-match
    // e.g. "P260622-01-02-001-NFC Yuzu" → strip "p2606220102001" → "nfcyuzu"
    // e.g. plain-text "P260622-01-02-001-NFC Yuzu 1216450241000077" → "nfcyuzu1216450241000077"
    const batchPrefixNorm = normalize(selectedBatchId.value || '')
    const barcodeIngredientNorm = barcodeNorm.startsWith(batchPrefixNorm) && batchPrefixNorm.length > 0
        ? barcodeNorm.slice(batchPrefixNorm.length)
        : barcodeNorm
    // Also strip digits (SAP codes appended after ingredient name in plain-text labels)
    // e.g. "nfcyuzu1216450241000077" → "nfcyuzu" to match "nfcyuzudksh"
    const barcodeIngredientAlphaNorm = barcodeIngredientNorm.replace(/[0-9]/g, '')

    let matchedStep: any = null

    // ── FREE-SCAN: any ingredient in a free-scan phase can be scanned in any order ─────────
    // Uses localStepIndex to advance the UI — works even when PLC is OFFLINE.
    // Groups by phase_number — ALL SPP/FH scan steps must be scanned before advancing.
    //
    // ⚠️ PHASE GUARD: Only accept scans for the CURRENTLY ACTIVE free-scan phase.
    // Scanning an ingredient from a different phase → alarm, do NOT record.
    const activeFreeScanPhase: string | null = (() => {
        const cur = currentStep.value
        if (cur && isFreeScanPhase(cur.phase_number)) return String(cur.phase_number)
        // Fallback: look forward from localStepIndex for first free-scan step
        const idx = localStepIndex.value ?? 0
        for (let i = idx; i < skuSteps.value.length; i++) {
            const s = skuSteps.value[i]
            if (s && isFreeScanPhase(s.phase_number)) return String(s.phase_number)
        }
        return null
    })()

    for (const step of skuSteps.value) {
        const isFree = isFreeScanPhase(step.phase_number)
        const hasScanSteps = skuSteps.value.some((s: any) =>
            s.phase_number === step.phase_number &&
            (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
            s.re_code && s.re_code !== '-' && s.re_code.trim() !== '' &&
            (getStepWh(s) === 'SPP' || getStepWh(s) === 'FH')
        )
        if (!(isFree && hasScanSteps)) continue
        const aCode = String(step.action_code || '')
        if (!aCode.startsWith('2') && !aCode.startsWith('3')) continue

        const expectedIds = prebatchIdMap.value[step.re_code] || ''
        const expectedNorm = normalize(step.re_code || '')
        const isExactMatch = expectedIds && expectedIds.includes(barcodeId)
        // isNameMatch checks in order:
        // 1. barcodeNorm includes full expectedNorm (standard exact-ish match)
        // 2. expectedNorm starts with barcodeIngredientNorm (JSON short-name barcode: "NFC Yuzu")
        // 3. expectedNorm starts with barcodeIngredientAlphaNorm (plain-text label: "NFC Yuzu 1216450241000077" → alpha: "nfcyuzu")
        const isNameMatch = expectedNorm && (
            barcodeNorm.includes(expectedNorm) ||
            (barcodeIngredientNorm.length >= 4 && expectedNorm.startsWith(barcodeIngredientNorm)) ||
            (barcodeIngredientAlphaNorm.length >= 4 && expectedNorm.startsWith(barcodeIngredientAlphaNorm))
        )

        if (isExactMatch || isNameMatch) {
            // ⛔ PHASE GUARD: only allow scan if ingredient belongs to the CURRENT active free-scan phase
            const wrongPhase = !activeFreeScanPhase || step.phase_number !== activeFreeScanPhase
            if (wrongPhase) {
                // 🔄 CROSS-PHASE RE-CODE CHECK:
                // Some SKUs reuse the same ingredient (re_code) across multiple phases.
                // If the matched step is in a different phase, check whether the SAME re_code
                // also exists as a scan step in the currently active phase.
                // If yes → redirect the match to that step (no alarm).
                // If no  → this is a genuine cross-phase error → alarm.
                if (activeFreeScanPhase) {
                    const sameReInActivePhase = skuSteps.value.find((s: any) =>
                        s.phase_number === activeFreeScanPhase &&
                        (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
                        s.re_code && s.re_code !== '-' && s.re_code.trim() !== '' &&
                        normalize(s.re_code) === normalize(step.re_code) &&
                        (getStepWh(s) === 'SPP' || getStepWh(s) === 'FH')
                    )
                    if (sameReInActivePhase) {
                        // Redirect: treat this scan as if it matched the active-phase step
                        // Continue loop with the active-phase step by overriding `step` is not possible
                        // — so we fall-through by replacing the matched `step` reference via a local var
                        // and jumping directly to the processing block below using the redirected step.
                        const redirectedStep = sameReInActivePhase

                        const rawVol2 = qrData?.r ?? qrData?.n ?? null
                        const matchedPhase2 = redirectedStep.phase_number
                        if (rawVol2 == null) {
                            $q.notify({
                                type: 'warning', icon: 'qr_code',
                                message: `${matchedPhase2} Scan — no volume: ${redirectedStep.re_code}`,
                                caption: 'Scan again slowly to capture the volume field.',
                                position: 'top', timeout: 4000
                            })
                            return
                        }

                        const scannedVol2 = Number(rawVol2)
                        const redirectScanKey = `${redirectedStep.phase_number}|${redirectedStep.re_code}`
                        prebatchWeightMap.value = { ...prebatchWeightMap.value, [redirectedStep.re_code]: scannedVol2 }
                        scannedVolumeMap.value  = { ...scannedVolumeMap.value, [redirectScanKey]: scannedVol2 }

                        const logTopic2 = simCmdTopic(activePlantId.value, 'step_cmd')
                        const logPayload2 = {
                            Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
                            Confirm_Phase: String(redirectedStep.phase_number || ''),
                            Confirm_Step: Number(redirectedStep.sub_step || 0),
                            Batch_ID: selectedBatchId.value || '-',
                            Phase_ID: String(redirectedStep.phase_number || ''),
                            Step_ID: Number(redirectedStep.sub_step || 0),
                            Cmd_StartTimer: 0,
                            HMI_Command: 5,
                            Step_Time_SP: 0,
                            Step_Status: 2,
                            Material_ID: redirectedStep.mat_sap_code || '',
                            Re_Code_ID: redirectedStep.re_code || '',
                            Req_Qty: productionRequire(redirectedStep),
                            Actual_Qty: scannedVol2,
                            Cmd_NewStep: false
                        }
                        publishMessage(logTopic2, logPayload2)

                        setTimeout(() => {
                            if (selectedBatchId.value) fetchStampTimes(selectedBatchId.value)
                        }, 1000)

                        // ✅ Same logic as primary free-scan block (keep in sync!)
                        const allFreeScanSteps2 = skuSteps.value.filter((s: any) =>
                            s.phase_number === matchedPhase2 &&
                            (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
                            s.re_code && s.re_code !== '-' && s.re_code.trim() !== ''
                        )
                        const scannedCount2 = allFreeScanSteps2.filter((s: any) => {
                            // Phase-scoped key — no stamp_time to avoid cross-phase/historical contamination
                            const phaseScanKey2 = `${s.phase_number}|${s.re_code}`
                            return scannedVolumeMap.value[phaseScanKey2] != null
                        }).length
                        const allScanned2 = scannedCount2 >= allFreeScanSteps2.length && allFreeScanSteps2.length > 0
                        console.log(`[FreeScan2] Phase ${matchedPhase2}: ${scannedCount2}/${allFreeScanSteps2.length} scanned | allScanned2=${allScanned2}`,
                            allFreeScanSteps2.map((s: any) => {
                                const k = `${s.phase_number}|${s.re_code}`
                                return `${s.re_code.trim()}(scanned:${scannedVolumeMap.value[k] != null})`
                            }))

                        $q.notify({
                            type: 'positive',
                            message: `✅ ${matchedPhase2}: ${redirectedStep.re_code} — ${scannedCount2}/${allFreeScanSteps2.length} done`,
                            caption: `Volume: ${scannedVol2.toFixed(5)} kg | Bag: ${barcodeId}${allScanned2 ? ' | 🎉 All done!' : ''}`,
                            position: 'top', icon: 'inventory_2', timeout: 3000
                        })

                        if (allScanned2) {
                            const scannedIdxList2 = allFreeScanSteps2.map((s: any) =>
                                skuSteps.value.findIndex((sk: any) => Number(sk.id) === Number(s.id))
                            ).filter((i: number) => i >= 0)
                            const stepIdx2 = skuSteps.value.findIndex((s: any) => Number(s.id) === Number(redirectedStep.id))
                            const maxScannedIdx2 = scannedIdxList2.length > 0 ? Math.max(...scannedIdxList2) : stepIdx2
                            const nextIdx2 = maxScannedIdx2 + 1
                            localStepIndex.value = nextIdx2
                            appOverrideStepIndex.value = nextIdx2

                            if (nextIdx2 < skuSteps.value.length) {
                                const nextStep2 = skuSteps.value[nextIdx2]
                                if (nextStep2) {
                                    const nextPhase2 = nextStep2.phase_number || '0'
                                    const isSamePhase2 = nextPhase2 === matchedPhase2
                                    expandedPhases.value[nextPhase2] = true
                                    $q.notify({
                                        type: 'positive', icon: 'rocket_launch',
                                        message: `🎉 ${matchedPhase2} สแกนครบ! → ${isSamePhase2 ? 'ต่อ' : 'ข้ามไป'} ${nextPhase2}`,
                                        caption: `Phase ${nextPhase2} Step ${nextStep2.sub_step} - กรุณาดำเนินการต่อ`,
                                        position: 'center', timeout: 3500
                                    });
                                    (async () => { await nextTick(); scrollToActiveStep() })()
                                }
                            }

                            if (isPlcConnected.value && nextIdx2 < skuSteps.value.length) {
                                setTimeout(() => { sendStepToPLC(nextIdx2) }, 600)
                            }
                        }

                        return
                    }
                }

                // Genuine cross-phase error — re_code does NOT exist in the active phase
                const expectedPhaseMsg = activeFreeScanPhase
                    ? `ขณะนี้กำลังทำ Phase ${activeFreeScanPhase} อยู่`
                    : `ขณะนี้ไม่ได้อยู่ใน Phase สแกนอิสระ`
                $q.notify({
                    type: 'negative',
                    icon: 'block',
                    message: `⛔ สแกนผิด Phase!`,
                    caption: `"${step.re_code}" อยู่ใน Phase ${step.phase_number} — ${expectedPhaseMsg}`,
                    position: 'center',
                    timeout: 5000,
                })
                return
            }

            const rawVol = qrData?.r ?? qrData?.n ?? null
            const matchedPhase = step.phase_number
            if (rawVol == null) {
                $q.notify({
                    type: 'warning', icon: 'qr_code',
                    message: `${matchedPhase} Scan — no volume: ${step.re_code}`,
                    caption: 'Scan again slowly to capture the volume field.',
                    position: 'top', timeout: 4000
                })
                return
            }

            // 1. Record the scanned volume
            //    Key = "phase_number|re_code" to prevent cross-phase contamination
            //    (e.g. W100 CG scanned in p015 must NOT count as scanned in p020)
            const scannedVol = Number(rawVol)
            const scanKey = `${step.phase_number}|${step.re_code}`
            prebatchWeightMap.value = { ...prebatchWeightMap.value, [step.re_code]: scannedVol }
            scannedVolumeMap.value  = { ...scannedVolumeMap.value, [scanKey]: scannedVol }

            // Log this scanned step to the database by publishing step_cmd MQTT message with Actual_Qty
            const logTopic = simCmdTopic(activePlantId.value, 'step_cmd')
            const logPayload = {
                Watch_Doc: Math.floor(Date.now() / 1000) % 32767,
                Confirm_Phase: String(step.phase_number || ''),
                Confirm_Step: Number(step.sub_step || 0),
                Batch_ID: selectedBatchId.value || '-',
                Phase_ID: String(step.phase_number || ''),
                Step_ID: Number(step.sub_step || 0),
                Cmd_StartTimer: 0,
                HMI_Command: 5, // Bypass/Complete
                Step_Time_SP: 0,
                Step_Status: 2, // Completed
                Material_ID: step.mat_sap_code || '',
                Re_Code_ID: step.re_code || '',
                Req_Qty: productionRequire(step),
                Actual_Qty: scannedVol, // Send the actual scanned volume
                Cmd_NewStep: false
            }
            publishMessage(logTopic, logPayload)

            // Auto-fetch stamp times after database update (approx 1s delay)
            setTimeout(() => {
                if (selectedBatchId.value) {
                    fetchStampTimes(selectedBatchId.value)
                }
            }, 1000)

            // 2. All SPP/FH manual-scan steps in this phase (WH-based — correct business logic)
            //    Now that backend returns correct WH from Ingredient master, this is reliable.
            //    MIX ingredients use action_code 1x → excluded by action_code check above.
            const allFreeScanSteps = skuSteps.value.filter((s: any) => {
                if (s.phase_number !== matchedPhase) return false
                const aCode = String(s.action_code || '')
                if (!aCode.startsWith('2') && !aCode.startsWith('3')) return false
                if (!s.re_code || s.re_code === '-' || !s.re_code.trim()) return false
                const wh = getStepWh(s)
                return wh === 'SPP' || wh === 'FH'
            })
            const scannedCount = allFreeScanSteps.filter((s: any) => {
                // Phase-scoped key: phase_number|re_code prevents cross-phase false-positives
                const phaseScanKey = `${s.phase_number}|${s.re_code}`
                return scannedVolumeMap.value[phaseScanKey] != null
            }).length
            const allScanned = scannedCount >= allFreeScanSteps.length && allFreeScanSteps.length > 0
            console.log(`[FreeScan] Phase ${matchedPhase}: ${scannedCount}/${allFreeScanSteps.length} scanned | allScanned=${allScanned}`,
                allFreeScanSteps.map((s: any) => {
                    const k = `${s.phase_number}|${s.re_code}`
                    return `${s.re_code.trim()}(scanned:${scannedVolumeMap.value[k] != null})`
                }))



            $q.notify({
                type: 'positive',
                message: `✅ ${matchedPhase}: ${step.re_code} — ${scannedCount}/${allFreeScanSteps.length} done`,
                caption: `Volume: ${scannedVol.toFixed(5)} kg | Bag: ${barcodeId}${allScanned ? ' | 🎉 All done!' : ''}`,
                position: 'top', icon: 'inventory_2', timeout: 3000
            })

            // 3. Find this step's index in skuSteps
            const stepIdx = skuSteps.value.findIndex((s: any) => Number(s.id) === Number(step.id))

            if (allScanned) {
                // All SPP/FH scan steps in this phase are done.
                // Advance to AFTER the highest-indexed scan step in the phase
                // (not just stepIdx+1) because steps may have been scanned out of order.
                // Example: Kelcogel(sub40) scanned before CPK(sub20) →
                //   stepIdx = CPK index, but we must advance past Kelcogel(sub40), not back to W100(sub30)
                const scannedIdxList = allFreeScanSteps.map((s: any) =>
                    skuSteps.value.findIndex((sk: any) => Number(sk.id) === Number(s.id))
                ).filter((i: number) => i >= 0)
                const maxScannedIdx = scannedIdxList.length > 0
                    ? Math.max(...scannedIdxList)
                    : stepIdx
                let nextIdx = maxScannedIdx + 1
                // Skip over steps in the SAME phase that are already completed (have stamp_time)
                // e.g. Frozen Dice Orange Peel (sub130) was scanned earlier but isn't in allFreeScanSteps
                // → advance past it to p040 instead of stopping there
                while (nextIdx < skuSteps.value.length) {
                    const candidateStep = skuSteps.value[nextIdx]
                    if (!candidateStep) break
                    if (candidateStep.phase_number !== matchedPhase) break  // reached new phase → stop
                    const isAlreadyDone = (candidateStep.stamp_time != null && candidateStep.stamp_time !== '-') ||
                        scannedVolumeMap.value[`${candidateStep.phase_number}|${candidateStep.re_code}`] != null
                    if (!isAlreadyDone) break  // not done yet → stop here for user to handle
                    nextIdx++  // already done → skip forward
                }
                localStepIndex.value = nextIdx
                appOverrideStepIndex.value = nextIdx  // ← force UI past PLC telemetry

                // Auto-expand the next phase and scroll after DOM update
                if (nextIdx < skuSteps.value.length) {
                    const nextStep = skuSteps.value[nextIdx]
                    if (nextStep) {
                        const nextPhase = nextStep.phase_number || '0'
                        const isSamePhase = nextPhase === matchedPhase
                        expandedPhases.value[nextPhase] = true
                        $q.notify({
                            type: 'positive', icon: 'rocket_launch',
                            message: `🎉 ${matchedPhase} สแกนครบ! → ${isSamePhase ? 'ต่อ' : 'ข้ามไป'} ${nextPhase}`,
                            caption: `Phase ${nextPhase} Step ${nextStep.sub_step} - กรุณาดำเนินการต่อ`,
                            position: 'center', timeout: 3500
                        })
                        // Wait 2 ticks: 1st for reactive update, 2nd for DOM render
                        ;(async () => {
                            await nextTick()
                            scrollToActiveStep()
                        })()
                    }
                }
                
                // RESTORE OLD FUNCTION: send NEXT_STEP/next step setpoints to PLC
                if (isPlcConnected.value && nextIdx < skuSteps.value.length) {
                    setTimeout(() => {
                        sendStepToPLC(nextIdx)
                    }, 600)
                }
            }

            return
        }
    }

    // ── NORMAL FLOW: active-step priority then SPP fallback ───────────────────
    // 1. Try matching the current step first (priority to active step)
    const activeS = currentStep.value
    if (activeS && (String(activeS.action_code || '').startsWith('2') || String(activeS.action_code || '').startsWith('3'))) {
        const expectedIds = prebatchIdMap.value[activeS.re_code] || ''
        const expectedNorm = normalize(activeS.re_code || '')

        const isExactMatch = expectedIds && expectedIds.includes(barcodeId)
        const isNameMatch = expectedNorm && barcodeNorm.includes(expectedNorm)

        if (isExactMatch || isNameMatch) {
            matchedStep = activeS
        }
    }

    // 2. Fallback: search SPP steps (non-free-scan) for out-of-order scan
    if (!matchedStep) {
        for (const step of skuSteps.value) {
            const isFree = isFreeScanPhase(step.phase_number)
            const hasScanSteps = skuSteps.value.some((s: any) =>
                s.phase_number === step.phase_number &&
                (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3')) &&
                s.re_code && s.re_code !== '-' && s.re_code.trim() !== '' &&
                (prebatchWhMap.value[s.re_code] === 'SPP' || prebatchWhMap.value[s.re_code] === 'FH')
            )
            if (isFree && hasScanSteps) continue  // already handled above
            const aCode = String(step.action_code || '')
            if (!aCode.startsWith('2') && !aCode.startsWith('3')) continue
            const whType = prebatchWhMap.value[step.re_code] || ''
            if (whType !== 'SPP') continue

            const expectedIds = prebatchIdMap.value[step.re_code] || ''
            const expectedNorm = normalize(step.re_code || '')
            const isExactMatch = expectedIds && expectedIds.includes(barcodeId)
            const isNameMatch = expectedNorm && barcodeNorm.includes(expectedNorm)

            if (isExactMatch || isNameMatch) {
                matchedStep = step
                break
            }
        }
    }

    // 3. Handle the match (normal steps — sends PLC command when active)
    if (matchedStep) {
        const whType = prebatchWhMap.value[matchedStep.re_code] || ''
        const expectedIds = prebatchIdMap.value[matchedStep.re_code] || ''
        const rawVol = qrData?.r ?? qrData?.n ?? null

        if ((whType === 'FH' || whType === 'SPP') && rawVol != null) {
            const scannedVol = Number(rawVol)
            // Save the scanned volume — use phase-scoped key to align with scannedCount check
            const normalScanKey = `${matchedStep.phase_number}|${matchedStep.re_code}`
            prebatchWeightMap.value = { ...prebatchWeightMap.value, [matchedStep.re_code]: scannedVol }
            scannedVolumeMap.value = { ...scannedVolumeMap.value, [normalScanKey]: scannedVol }

            $q.notify({
                type: 'positive',
                message: `Scan Accepted: ${matchedStep.re_code} (Step ${matchedStep.sub_step})`,
                caption: `Volume: ${scannedVol.toFixed(5)} kg | Bag: ${barcodeId}`,
                position: 'top',
                icon: 'check_circle',
                timeout: 3000
            })

            // If the matched step is the current active step, auto-advance it
            if (currentStep.value && Number(currentStep.value.id) === Number(matchedStep.id)) {
                confirmStepFromRow(matchedStep, true)
                // User requested immediate auto-step upon correct scan
                setTimeout(() => sendCommand('NEXT_STEP'), 500)
            }
        } else if (rawVol == null && (whType === 'FH' || whType === 'SPP')) {
            $q.notify({
                type: 'warning',
                icon: 'qr_code',
                message: 'Could not read volume from scan',
                caption: 'Scanner may have split the QR. Please scan again slowly.',
                position: 'top',
                timeout: 4000
            })
        } else {
            // Standard scan (not FH/SPP)
            // Auto-fill the required weight to bypass scale tolerance, as requested by the user.
            const reqVol = productionRequire(matchedStep)
            prebatchWeightMap.value = { ...prebatchWeightMap.value, [matchedStep.re_code]: reqVol }
            scannedVolumeMap.value = { ...scannedVolumeMap.value, [matchedStep.re_code]: reqVol }
            
            $q.notify({
                type: 'positive',
                message: `Scan Matched: ${barcodeId} (Step ${matchedStep.sub_step})`,
                caption: `Auto-filled required weight: ${reqVol.toFixed(2)} kg`,
                position: 'top',
                icon: 'check_circle'
            })
            if (currentStep.value && Number(currentStep.value.id) === Number(matchedStep.id)) {
                confirmStepFromRow(matchedStep, true)
                // User requested immediate auto-step upon correct scan
                setTimeout(() => sendCommand('NEXT_STEP'), 500)
            }
        }
    } else {
        // No match found anywhere
        const s = currentStep.value
        const hasReCode = s && s.re_code && s.re_code !== '-' && s.re_code.trim() !== ''
        const activeRequiresScan = s && hasReCode && (String(s.action_code || '').startsWith('2') || String(s.action_code || '').startsWith('3'))
        
        if (activeRequiresScan) {
            // Active step requires scan -> wrong barcode, trigger fault alarm
            const expectedIds = prebatchIdMap.value[s.re_code] || s.re_code || ''
            triggerFaultAlarm(barcodeId, expectedIds, s)
        } else {
            // Active step does not require scan -> just show general info
            $q.notify({
                type: 'info',
                message: `Scanned: ${scannedText}`,
                position: 'top',
                caption: 'Current step does not require scanning.'
            })
        }
    }
}

// ── Non-reactive scan accumulators ───────────────────────────────────────────
// Plain JS strings — no Vue reactivity per keystroke (avoids ~60 DOM re-renders
// per QR scan). Reactive refs are only written ONCE on Enter (scan complete).
let _scanAccum  = ''   // global background buffer (no dialog)
let _qrAccum    = ''   // buffer when QR scan dialog is open

// ── Physical key → ASCII mapper (layout-agnostic) ───────────────────────────
// Barcode scanners emulate keyboard input. When OS layout is Thai (or any
// non-Latin layout), e.key returns Thai characters. Using e.code (physical
// key position) lets us always derive the intended ASCII character correctly.
const physicalKeyToAscii = (e: KeyboardEvent): string => {
    const s = e.shiftKey
    const c = e.code

    // Digit row: 0-9 and their shifted symbols
    if (c.startsWith('Digit')) {
        const d = c[5]                                   // '0'–'9'
        return s ? '!@#$%^&*()'['0123456789'.indexOf(d)] ?? d : d
    }
    // Letter keys: always produce Latin a-z / A-Z
    if (c.startsWith('Key')) {
        const letter = c[3]                              // 'A'–'Z'
        return s ? letter.toUpperCase() : letter.toLowerCase()
    }
    // Numpad
    if (c.startsWith('Numpad')) {
        const numMap: Record<string, string> = {
            Numpad0: '0', Numpad1: '1', Numpad2: '2', Numpad3: '3', Numpad4: '4',
            Numpad5: '5', Numpad6: '6', Numpad7: '7', Numpad8: '8', Numpad9: '9',
            NumpadDecimal: '.', NumpadDivide: '/', NumpadMultiply: '*',
            NumpadSubtract: '-', NumpadAdd: '+'
        }
        return numMap[c] ?? ''
    }
    // Punctuation & symbols (standard US layout positions — same physical location on all keyboards)
    const puncMap: Record<string, [string, string]> = {  // [normal, shifted]
        Minus:        ['-', '_'],
        Equal:        ['=', '+'],
        BracketLeft:  ['[', '{'],
        BracketRight: [']', '}'],
        Backslash:    ['\\', '|'],
        Semicolon:    [';', ':'],
        Quote:        ["'", '"'],
        Comma:        [',', '<'],
        Period:       ['.', '>'],
        Slash:        ['/', '?'],
        Backquote:    ['`', '~'],
        Space:        [' ', ' '],
    }
    const pair = puncMap[c]
    if (pair) return s ? pair[1] : pair[0]

    return '' // Unknown / non-printable key
}

const handleGlobalKeydown = (e: KeyboardEvent) => {
    // Ignore keydown if the user is typing in an input field or textarea
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
    if (e.ctrlKey || e.altKey || e.metaKey) return
    // ── Block all scanner input while fault alarm is showing ──────────────────
    if (faultAlarmDialog.value) return

    if (e.code === 'Enter' || e.key === 'Enter') {
        if (qrScanDialog.value) {
            // ── Dialog open: scanner finished → write to ref ONCE then process ──
            const finalQr = _qrAccum.trim()
            _qrAccum = ''
            if (finalQr.length > 3) {
                qrScanBuffer.value = finalQr   // single reactive write → 1 DOM update
                onQrScanInput(finalQr)
            }
        } else {
            // ── Background scan (no dialog) ──
            const finalScan = _scanAccum.trim()
            _scanAccum = ''
            scanBuffer.value = ''
            if (finalScan.length > 3) handleScan(finalScan)
        }
        if (scanTimeout) { clearTimeout(scanTimeout); scanTimeout = null }
    } else {
        // ── Accumulate into plain string (zero Vue reactivity overhead) ──
        const char = physicalKeyToAscii(e)
        if (char) {
            if (qrScanDialog.value) {
                _qrAccum += char
            } else {
                _scanAccum += char
            }
            if (scanTimeout) clearTimeout(scanTimeout)
            // Reset buffer if scanner stops sending (>150ms gap = not a scanner)
            scanTimeout = setTimeout(() => {
                _scanAccum = ''
                if (!qrScanDialog.value) _qrAccum = ''
            }, 150)
        }
    }
}

// ── Automatic Batch Completion & Auto Step ──
watch(() => plantData.value.PLC_State, async (newVal, oldVal) => {
    
    // Legacy Auto Step: Keep for fallback if PLC_State ever becomes 5
    if (newVal === 5 && oldVal !== 5 && batchRunning.value) {
        setTimeout(async () => {
            const step = currentStep.value
            if (!step) return
            
            if (String(step.action_code || '').startsWith('2') || String(step.action_code || '').startsWith('3')) return
            
            const liveWt = getStepLiveWeight(step)
            if (productionRequire(step) > 0 && !isWeightInTolerance(step, liveWt)) return
            
            $q.notify({ type: 'positive', message: 'Auto-Stepping to next step (Legacy)', position: 'top', timeout: 1000 })
            await sendCommand('NEXT_STEP')
        }, 1000)
    }
})

// ── AUTO STEP: triggered by PLC Current_Step change ──
// Current_Step is a counter that increments by 1 (or a bit toggle) each time PLC finishes a step.
// Protocol: ANY change in value = "step done" signal from PLC.
// Do NOT use even/odd check — counter goes 1→2→3→4... missing every alternate step.
watch(() => plantData.value?.Current_Step, async (newVal, oldVal) => {
    // Only auto-step if batch is actually running
    if (!batchRunning.value) return;

    // NOTE: batch Done is now handled by the allStepsDone watcher (frontend-aware),
    // which covers PLC steps + FreeScan steps + manual rinse (กลั้วภาชนะ) steps.
    // The PLC step_done signal here only advances the UI — NOT marks batch Done.

    // Guard: value must actually change (not just re-render)
    // Any change (bit toggle 0→1 or counter 1→2→3...) = PLC step done
    if (newVal === undefined || newVal === null) return;
    if (newVal === oldVal) return;

        setTimeout(async () => {
            const step = currentStep.value
            if (!step) return
            
            // If it's a manual add step (2xxxx or 3xxxx), DO NOT auto-step (needs scan/manual acknowledge)
            const aCode = String(step.action_code || '')
            const hasReCode = step.re_code && step.re_code !== '-' && step.re_code.trim() !== ''
            if ((aCode.startsWith('2') || aCode.startsWith('3')) && hasReCode) {
                console.log('Auto-Step BLOCKED: Manual step detected with ingredient', aCode, step.re_code)
                return
            }
            
            // For MANUAL SCAN steps (2x/3x): check weight tolerance before auto-stepping.
            // Process steps (1x = LS, heating) must NOT be blocked by weight:
            //   - Scale reads CUR.STEP WT (tray weight), not batch total
            //   - Agitator vibrates platform → weight reading unreliable
            const isManualScanAutoStep = (aCode.startsWith('2') || aCode.startsWith('3')) && hasReCode
            if (isManualScanAutoStep) {
                const liveWt = getStepLiveWeight(step)
                if (productionRequire(step) > 0 && !isWeightInTolerance(step, liveWt)) {
                    console.log('Auto-Step BLOCKED: Weight out of tolerance — setting pendingWeightApproval')
                    pendingWeightApproval.value = true
                    $q.notify({
                        type: 'warning', icon: 'scale',
                        message: '⚠️ Weight out of tolerance — Auto-Step pending',
                        caption: `Adjust weight to target. System will auto-step once weight is OK. Req: ${productionRequire(step).toFixed(3)} kg | Act: ${liveWt.toFixed(3)} kg`,
                        position: 'center', timeout: 0,
                        actions: [{ label: 'Dismiss', color: 'white' }]
                    })
                    return
                }
            }
            
            pendingWeightApproval.value = false
            // If automated step and weight is good, confirm automatically
            console.log(`Auto-Stepping triggered by Green State: ${newVal}`)
            
            // ** BATCH COMPLETE CHECK **
            if (isLastStep.value) {
                batchRunning.value = false
                $q.notify({ type: 'positive', message: '🎉 BATCH COMPLETE!', position: 'center', timeout: 5000 })
                await markBatchDone('PLC step_done')
                // Navigate to report
                setTimeout(() => {
                    router.push({ path: '/x70-ProductionReport', query: { batch_id: selectedBatchId.value || '' } })
                }, 2000)
            } else {
                $q.notify({ type: 'positive', message: `PLC Finished Phase (State ${newVal}) - Auto Stepping`, position: 'top', timeout: 2000 })
                // Pulse HMI=1 for 3s, send next step, advance index
                plcHmiCommand.value = 1
                setTimeout(() => { plcHmiCommand.value = 2 }, 3000)
                const nextIdx = currentStepIndex.value + 1
                if (nextIdx < skuSteps.value.length) sendStepToPLC(nextIdx)
                await sendCommand('NEXT_STEP')
            }

            
        }, 1000)
})

// ── Weight Recovery Watcher: auto-step when weight comes back into tolerance ──
// Handles the case where PLC sent step_done but weight was not in tolerance.
// When operator corrects the weight, this fires and resumes the auto-step.
const _doWeightRecoveryStep = async () => {
    if (!pendingWeightApproval.value) return
    if (!batchRunning.value) return
    const step = currentStep.value
    if (!step) return
    const aCode = String(step.action_code || '')
    const hasReCode = step.re_code && step.re_code !== '-' && step.re_code.trim() !== ''
    if ((aCode.startsWith('2') || aCode.startsWith('3')) && hasReCode) return  // still manual, don't auto-step
    const liveWt = getStepLiveWeight(step)
    if (!isWeightInTolerance(step, liveWt)) return  // still not in range
    // Weight is now OK — fire the pending step!
    pendingWeightApproval.value = false
    console.log('[Weight Recovery] Weight OK — auto-stepping now')
    $q.notify({ type: 'positive', icon: 'check_circle', message: '✅ Weight OK — Auto-Stepping', position: 'top', timeout: 2000 })
    if (isLastStep.value) {
        batchRunning.value = false
        $q.notify({ type: 'positive', message: '🎉 BATCH COMPLETE!', position: 'center', timeout: 5000 })
        if (batchInfo.value?.id) {
            try {
                await $fetch(`${appConfig.apiBaseUrl}/production-batches/${batchInfo.value.id}/status?status=Done`, {
                    method: 'PATCH',
                    headers: getAuthHeader() as Record<string, string>
                })
                batchInfo.value.status = 'Done'
                batchInfo.value.done = true
            } catch (e) { console.error('[Batch Complete]', e) }
        }
        setTimeout(() => {
            router.push({ path: '/x70-ProductionReport', query: { batch_id: selectedBatchId.value || '' } })
        }, 2000)
    } else {
        await sendCommand('NEXT_STEP')
    }
}
watch(actualTankWeight,   () => _doWeightRecoveryStep())
watch(actualHopperWeight, () => _doWeightRecoveryStep())

onMounted(async () => {
    // Auto-fill pour operator from login user
    if (user.value) {
        pourOperator.value = {
            username: user.value.username || '',
            full_name: (user.value as any).full_name || user.value.username || ''
        }
    }
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
                    step_time: Number(s.step_time || 0),
                    material_code: String(s.mat_sap_code || '').substring(0, 20),
                    re_code: String(s.re_code || '').substring(0, 20),
                    require: productionRequire(s),
                    temperature: Number(s.temperature || 0),
                    agitator_rpm: Number(s.agitator_rpm || 0),
                    high_shear_rpm: Number(s.high_shear_rpm || 0),
                    ph_sp: Number(s.ph_sp || 0),
                    brix_sp: Number(s.brix_sp || 0),
                    // ── Interlock signals → DB1510/DB1511 via backend snap7 ──
                    // HMI Command design:
                    //   0 = Abort   (ABORT button only)
                    //   1 = Confirm pulse (3s, sent on step advance to start next step)
                    //   2 = HOLD    (default resting state — PLC waits between steps)
                    //   4 = Step complete (sent when confirmed AND all interlocks are green naturally)
                    //   5 = Bypass/Force complete (sent when confirmed AND bypassed/forced next step)
                    hmi_command: (() => {
                        const { ok: interlocksOk } = isStepAllGreen(s)
                        const naturalGreen = interlocksOk && isAppReady.value
                        if (plcHmiCommand.value === 0) return 0
                        if (hasConfirmedCurrentStep.value) {
                            if (currentStepBypassed.value) return 5
                            if (naturalGreen) return 4
                        }
                        if (plcHmiCommand.value === 1) return 1
                        return plcHmiCommand.value || 2
                    })(),
                    next_step_cmd: (() => {
                        const { ok: interlocksOk } = isStepAllGreen(s)
                        const naturalGreen = interlocksOk && isAppReady.value
                        if (plcHmiCommand.value === 0) return 0
                        if (hasConfirmedCurrentStep.value && (currentStepBypassed.value || naturalGreen)) return 1
                        if (plcHmiCommand.value === 1 && (currentStepBypassed.value || naturalGreen)) return 1
                        return 0
                    })()
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

// Auto-fetch stamp times whenever batch changes
watch(selectedBatchId, (newBatchId) => {
    scannedVolumeMap.value = {} // Clear local scan cache for new batch
    if (newBatchId) {
        fetchStampTimes(newBatchId)
        startStampRefresh()
    } else {
        stopStampRefresh()
    }
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleGlobalKeydown)
    if (heartbeatInterval) clearInterval(heartbeatInterval)
    offMessage(handlePlcMessage)
    stopStampRefresh()
    disconnect()
})
</script>

<template>
  <q-page class="q-pa-xs column no-wrap" style="height: calc(100vh - 105px) !important; min-height: calc(100vh - 105px) !important; max-height: calc(100vh - 105px) !important; overflow: hidden !important;">

    <!-- ═══ PAGE HEADER ═══ -->
    <div class="bg-deep-purple-10 text-white q-pa-sm rounded-borders q-mb-sm shadow-2 row items-center justify-between no-wrap" style="flex-shrink: 0; min-height: 60px; z-index: 50; position: sticky; top: 0;">
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
             <q-btn flat dense icon="settings_backup_restore" color="orange-9" @click="softResetBatch"><q-tooltip>Reset Batch (Soft Reset & Clear PLC)</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" />
             <q-btn flat dense icon="delete_forever" color="red-9" @click="killBatch"><q-tooltip>Kill Batch (Clear to 0)</q-tooltip></q-btn>
             <q-separator vertical class="q-mx-xs" v-if="selectedBatchId" />
             <!-- View Report: direct link to production report for current batch -->
             <q-btn v-if="selectedBatchId" flat dense icon="assessment" color="cyan-5"
                    @click="router.push({ path: '/x70-ProductionReport', query: { batch_id: selectedBatchId || '' } })">
               <q-tooltip>View Production Report ({{ selectedBatchId }})</q-tooltip>
             </q-btn>
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
                <q-icon name="play_arrow" size="12px" class="q-mr-xs" />State: {{ plantData?.Current_Step || 0 }} &rarr; {{ plcStepDescriptions[plantData?.Current_Step] || 'Unknown' }}
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

       <!-- ── Pour/Cook Operator Row (inside header) ── -->
       <q-separator vertical dark class="q-mx-sm" style="opacity: 0.3;" />
       <div class="row items-center no-wrap q-gutter-xs">
         <q-icon name="badge" color="teal-3" size="16px" />
         <span class="mix-op-label" style="color:#b2dfdb;">Pour/Cook:</span>
         <div class="mix-op-badge row items-center no-wrap q-gutter-xs" style="background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3);">
           <q-icon name="how_to_reg" color="teal-3" size="14px" />
           <span class="mix-op-value" style="color:#e0f2f1;">{{ pourOperator?.full_name || user?.username || '-' }}</span>
           <q-badge outline color="teal-3" style="font-size:10px;">@{{ pourOperator?.username || user?.username }}</q-badge>
         </div>
         <q-input
           v-model="pourScanInput"
           outlined dense dark
           placeholder="Scan QR to change..."
           @keyup.enter="resolveOperatorScan(pourScanInput, pourOperator, pourScanLoading, pourScanInput, true)"
           :loading="pourScanLoading"
           style="font-size:12px; width:180px;"
         >
           <template v-slot:prepend><q-icon name="qr_code_scanner" color="teal-3" size="xs" /></template>
           <template v-slot:append>
             <q-btn v-if="pourOperator?.username !== user?.username"
               flat round dense icon="restart_alt" size="xs" color="teal-3"
               @click="pourOperator = user.value ? { username: user.value.username, full_name: (user.value as any).full_name || user.value.username } : null">
               <q-tooltip>Reset to login user</q-tooltip>
             </q-btn>
           </template>
         </q-input>
       </div>
    </div>

    <!-- ═══ PAGE LAYOUT ROW ═══ -->
    <div class="row q-col-gutter-sm" style="flex: 1; min-height: 0;">
      <!-- ═══ MAIN PANE: PRODUCTION CONTROL ═══ -->
      <div class="col-12" style="display: flex; flex-direction: column; overflow: hidden; min-height: 0; height: 100%;">


    <!-- ═══ BOTTOM CARD: SKU PROCESS AND STEP LIST ═══ -->
    <div style="height: 100%; flex: 1; display: flex; flex-direction: column;">
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
          <div class="bg-teal-7 text-white q-pa-sm shadow-1" style="flex-shrink: 0; min-height: 60px; z-index: 2;">
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
            


            <div v-if="skuStepsByPhase.length > 0" ref="stepTableScroll" class="scroll" style="flex: 1; min-height: 0;">
              <q-markup-table flat bordered dense separator="cell" style="font-size: 16px;" class="full-width production-table sticky-header-table">

              <thead class="bg-red-5 text-white">
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
                          <q-icon v-if="(String(step.action_code).startsWith('2') || String(step.action_code).startsWith('3')) && step.re_code && step.re_code !== '-'" 
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
                        <q-badge v-if="getStepWh(step)" :color="getStepWh(step) === 'FH' ? 'amber-9' : getStepWh(step) === 'SPP' ? 'blue-8' : 'green-8'">{{ getStepWh(step) }}</q-badge>
                        <span v-else>-</span>
                      </td>
                      <td>{{ step.destination || '-' }}</td>
                      <!-- Require / Volume -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                          <!-- SPP/FH with confirmed scan: show scan volume, not load cell -->
                          <template v-if="(getStepWh(step) === 'SPP' || getStepWh(step) === 'FH') && scannedVolumeMap[`${step.phase_number}|${step.re_code}`] != null">
                            <span class="act-num text-green-8" title="Volume confirmed from scan">✔ {{ Number(scannedVolumeMap[`${step.phase_number}|${step.re_code}`]).toFixed(3) }}</span>
                            <span class="slash">/</span>
                            <span class="req-num">{{ productionRequire(step) != null ? Number(productionRequire(step)).toFixed(3) : '-' }}</span>
                          </template>
                          <!-- Default: LIVE Hopper scale vs required -->
                          <template v-else>
                            <span class="act-num" :class="productionRequire(step) > 0 ? (isWeightInTolerance(step, getStepLiveWeight(step)) ? 'text-green-8' : 'text-deep-orange-9') : ''">{{ getStepLiveWeight(step) !== 0 ? Number(getStepLiveWeight(step)).toFixed(2) : '-' }}</span>
                            <span class="slash">/</span>
                            <span class="req-num">{{ productionRequire(step) != null ? Number(productionRequire(step)).toFixed(2) : '-' }}</span>
                          </template>
                        </template>
                        <template v-else>
                          <span class="act-num">{{ step.actual_volume != null ? Number(step.actual_volume).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ productionRequire(step) != null ? Number(productionRequire(step)).toFixed(2) : '-' }}</span>
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
                          <span class="req-num">{{ formatSP(step.brix_sp) }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #e65100;">{{ step.actual_brix != null ? Number(step.actual_brix).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ formatSP(step.brix_sp) }}</span>
                        </template>
                      </td>
                      <!-- pH -->
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) && step.ph_sp">
                          <span class="act-num text-purple-8" style="font-weight:800;">{{ actualPh ? Number(actualPh).toFixed(2) : '-' }}</span>
                          <span class="slash">/</span>
                          <span class="req-num">{{ formatSP(step.ph_sp) }}</span>
                        </template>
                        <template v-else>
                          <span class="act-num" style="color: #7b1fa2;">{{ step.actual_ph != null ? Number(step.actual_ph).toFixed(2) : '-' }}</span><span class="slash">/</span><span class="req-num">{{ formatSP(step.ph_sp) }}</span>
                        </template>
                      </td>
                      <td class="text-right">
                        <template v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step))">
                           <!-- PLC countdown: starts at step_time → 0, purple→orange(≤30s)→green(done) -->
                           <span class="act-num"
                                 :class="currentRemaining === 0 ? 'text-positive' : currentRemaining <= 30 ? 'text-orange-8' : 'text-deep-purple'"
                                 :title="`Remaining: ${currentRemaining}s`">
                             {{ step.step_time ? formatDuration(currentRemaining) : '-' }}
                           </span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? formatDuration(Number(step.step_time)) : '-' }}</span>
                        </template>
                        <template v-else-if="step.stamp_time">
                           <span class="act-num text-grey-8">{{ formatDuration(step.duration_sec) }}</span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? formatDuration(Number(step.step_time)) : '-' }}</span>
                        </template>
                        <template v-else>
                           <span class="act-num">-</span>
                           <span class="slash">/</span>
                           <span class="req-num">{{ step.step_time ? formatDuration(Number(step.step_time)) : '-' }}</span>
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
                                dense flat color="blue-7" icon="qr_code_scanner"
                                @click.stop="openQrScanDialog(step)"
                                >
                                <q-tooltip>Scan FH/SPP Label</q-tooltip>
                         </q-btn>
                        <q-btn v-if="currentStep && (step.id === currentStep.id || (step.phase_number === currentStep.phase_number && step.sub_step === currentStep.sub_step)) && (String(step.action_code).startsWith('2') || String(step.action_code).startsWith('3'))"
                               dense flat color="orange-9" icon="warning"
                               @click.stop="promptManualPass(step)"
                               >
                               <q-tooltip>Manual Override (Provide Reason)</q-tooltip>
                        </q-btn>
                        <!-- QC Brix/pH Entry: shown on any step with brix_sp or ph_sp set -->
                        <q-btn v-if="step.brix_sp || step.ph_sp"
                               dense flat color="indigo-7" icon="science"
                               @click.stop="() => { pendingQcStep = step; actualBrix = step.actual_brix ?? ''; actualPh = step.actual_ph ?? ''; qcDialog = true; }"
                               >
                               <q-tooltip>Enter QC Brix / pH for this step</q-tooltip>
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

    <!-- ⚠️ FAULT ALARM DIALOG (Wrong QR Scan) -->
    <q-dialog v-model="faultAlarmDialog" persistent backdrop-filter="blur(6px)">
      <q-card style="width: 420px; max-width: 95vw; border-radius: 14px; border: 3px solid #c62828; animation: pulse-red 0.6s ease-in-out;">
        <q-card-section class="bg-red-9 text-white row items-center q-pb-sm">
          <q-icon name="gpp_bad" size="2.5rem" class="q-mr-sm" style="animation: blink 0.5s step-start infinite;"/>
          <div>
            <div class="text-h5 text-weight-bold">⚠ SCAN FAULT</div>
            <div class="text-caption" style="opacity:0.9;">Wrong barcode detected!</div>
          </div>
          <q-space/>
          <q-badge color="red-3" text-color="red-10" label="ALARM" class="text-weight-bold"/>
        </q-card-section>
        <q-separator color="red-4"/>
        <q-card-section class="q-pa-lg">
          <div class="text-subtitle2 text-grey-7 q-mb-xs">Step / Ingredient</div>
          <div class="text-h6 text-weight-bold text-red-9 q-mb-md">{{ faultAlarmInfo.stepName }}</div>

          <div class="row q-col-gutter-sm">
            <div class="col-12">
              <q-banner dense rounded class="bg-red-1 text-red-9 q-mb-sm" style="border: 1px solid #ef9a9a;">
                <template v-slot:avatar><q-icon name="qr_code" color="red-7"/></template>
                <div class="text-caption text-grey-6">Scanned</div>
                <div class="text-body2 text-weight-bold" style="word-break: break-all;">{{ faultAlarmInfo.scanned }}</div>
              </q-banner>
              <q-banner dense rounded class="bg-green-1 text-green-9" style="border: 1px solid #a5d6a7;">
                <template v-slot:avatar><q-icon name="check_circle" color="green-7"/></template>
                <div class="text-caption text-grey-6">Expected</div>
                <div class="text-body2 text-weight-bold" style="word-break: break-all;">{{ faultAlarmInfo.expected }}</div>
              </q-banner>
            </div>
          </div>
        </q-card-section>
        <q-card-actions align="center" class="q-pa-md bg-red-1">
          <q-btn unelevated size="lg" color="red-8" icon="close" label="Dismiss Alarm"
                 style="min-width: 180px;"
                 @click="faultAlarmDialog = false" />
        </q-card-actions>
      </q-card>
    </q-dialog>


    <!-- QR SCAN DIALOG (SPP / FH steps) -->
    <!-- Scanner input is routed here via handleGlobalKeydown when dialog is open -->
    <q-dialog v-model="qrScanDialog" backdrop-filter="blur(4px)" @hide="qrScanBuffer = ''">
      <q-card style="width: 360px; max-width: 90vw; border-radius: 14px; border: 2px solid #1565c0;">
        <q-card-section class="bg-blue-9 text-white row items-center q-pb-sm">
          <q-icon name="qr_code_scanner" size="2rem" class="q-mr-sm"/>
          <div>
            <div class="text-h6 text-weight-bold">Scan Label</div>
            <div class="text-caption" style="opacity:0.85;">
              {{ qrScanStep ? `${prebatchWhMap[qrScanStep.re_code] || 'WH'} — ${qrScanStep.re_code}` : '' }}
            </div>
          </div>
        </q-card-section>
        <q-card-section class="q-pa-lg text-center">
          <q-icon name="qr_code" size="4rem" color="blue-8" class="q-mb-md"/>
          <p class="text-grey-8 q-mb-md">Point scanner at the label QR code</p>
          <div class="text-caption text-grey-6 q-mt-sm">Or type manually and press Enter</div>
          <!-- Single input — scanner fills this via handleGlobalKeydown, no hidden ghost input needed -->
          <q-input
            v-model="qrScanBuffer"
            outlined dense
            placeholder="Manual Input..."
            class="q-mt-sm"
            @keyup.enter="onQrScanInput(qrScanBuffer)"
          />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Cancel" color="grey-7" v-close-popup />
          <q-btn unelevated label="Confirm" color="blue-8" @click="onQrScanInput(qrScanBuffer)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

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
          <q-btn flat label="Pause Batch" color="grey-8" @click="() => { qcDialog.value = false; sendCommand('PAUSE'); }" />
          <q-btn label="Confirm & Continue" color="positive" icon="check_circle" :loading="qcSaving" @click="confirmQcCheck" />
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

    <!-- ═══ RECIPE DOWNLOAD PROGRESS DIALOG ═══ -->
    <q-dialog v-model="downloadDialog" persistent backdrop-filter="blur(6px)">
      <q-card style="width: 560px; max-width: 95vw; border-radius: 16px; border: 3px solid #1565c0; overflow: hidden;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #0d47a1 0%, #1565c0 100%); padding: 20px 24px; color: white;">
          <div class="row items-center q-gutter-sm">
            <q-icon :name="downloadProgress >= 100 ? 'verified' : 'cloud_download'" size="36px" color="cyan-3" />
            <div>
              <div class="text-h5 text-weight-bolder">
                {{ downloadProgress >= 100 ? '✅ Recipe Downloaded' : '📥 Downloading Recipe to PLC...' }}
              </div>
              <div class="text-caption text-blue-2" style="opacity: 0.85;">
                4-Stage Transfer: PREPARE → TRANSFER → VERIFY → ACTIVATE
              </div>
            </div>
          </div>
        </div>

        <q-separator />

        <q-card-section class="q-pa-lg">
          <!-- Progress Bar -->
          <div class="q-mb-md">
            <q-linear-progress 
              :value="downloadProgress / 100" 
              size="24px" 
              rounded 
              :color="downloadError ? 'negative' : downloadProgress >= 100 ? 'positive' : 'primary'"
              track-color="blue-1"
              stripe
              :animation-speed="downloadProgress < 100 ? 800 : 0"
            >
              <div class="absolute-full flex flex-center">
                <span class="text-weight-bold text-white" style="font-size: 12px;">
                  {{ downloadProgress }}%
                </span>
              </div>
            </q-linear-progress>
          </div>

          <!-- Error -->
          <div v-if="downloadError" class="q-pa-sm bg-red-1 text-red-9 rounded-borders q-mb-md">
            <q-icon name="error" class="q-mr-xs" /> {{ downloadError }}
          </div>

          <!-- Phase-by-Phase Progress -->
          <div v-if="downloadPhases.length" class="q-mb-md">
            <div class="text-caption text-weight-bold text-grey-7 q-mb-xs">PHASES TRANSFERRED:</div>
            <div v-for="(p, i) in downloadPhases" :key="i" class="row items-center q-py-xs" style="border-bottom: 1px solid #e0e0e0;">
              <q-icon name="check_circle" color="positive" size="18px" class="q-mr-sm" />
              <div class="text-body2">
                Phase {{ p.processNo }} — {{ p.stepCount }} step{{ p.stepCount > 1 ? 's' : '' }}
              </div>
            </div>
          </div>

          <!-- Verification Results -->
          <div v-if="downloadVerification" class="q-pa-md bg-green-1 rounded-borders" style="border: 1px solid #66bb6a;">
            <div class="text-subtitle2 text-weight-bold text-green-9 q-mb-sm">
              <q-icon name="verified" class="q-mr-xs" /> Verification Passed
            </div>
            <div class="row q-col-gutter-sm">
              <div class="col-6">
                <div class="text-caption text-grey-7">CRC Checksum</div>
                <div class="text-weight-bold text-mono">{{ downloadVerification.crcHex }}</div>
              </div>
              <div class="col-3">
                <div class="text-caption text-grey-7">Phases</div>
                <div class="text-weight-bold">{{ downloadVerification.processCount }}</div>
              </div>
              <div class="col-3">
                <div class="text-caption text-grey-7">Steps</div>
                <div class="text-weight-bold">{{ downloadVerification.totalSteps }}</div>
              </div>
            </div>
            <div v-if="downloadVerification.firstStep" class="row q-col-gutter-sm q-mt-sm">
              <div class="col-6">
                <div class="text-caption text-grey-7">First Step</div>
                <div class="text-body2">P{{ downloadVerification.firstStep.processNo }}-S{{ downloadVerification.firstStep.stepNo }}</div>
              </div>
              <div class="col-6">
                <div class="text-caption text-grey-7">Last Step</div>
                <div class="text-body2">P{{ downloadVerification.lastStep?.processNo }}-S{{ downloadVerification.lastStep?.stepNo }}</div>
              </div>
            </div>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="bg-grey-1 q-pa-md">
          <q-btn
            v-if="downloadProgress >= 100"
            label="CLOSE — READY TO START"
            color="green-8"
            icon="check"
            unelevated
            class="text-weight-bolder q-px-lg"
            @click="closeDownloadDialog"
          />
          <q-btn v-else-if="downloadError" label="Close" flat color="grey-7" @click="closeDownloadDialog" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<style scoped>
.heartbeat-icon {
  animation: heartbeat 1s ease-in-out infinite;
}
@keyframes pulse-red {
  0%, 100% { box-shadow: 0 0 0 0 rgba(198,40,40,0.4); }
  50% { box-shadow: 0 0 0 12px rgba(198,40,40,0); }
}
@keyframes blink {
  50% { opacity: 0; }
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

:deep(.sticky-header-table thead tr th) {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #f44336 !important;
  color: white !important;
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

/* Operator bar — same compact style as Inspector in x60 */
.mix-op-badge {
  background: #e0f2f1;
  border-radius: 20px;
  padding: 3px 12px;
  border: 1px solid #80cbc4;
  white-space: nowrap;
}
.mix-op-label {
  font-size: 11px;
  font-weight: 700;
  color: #004d40;
  margin-right: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.mix-op-value {
  font-size: 13px;
  font-weight: 700;
  color: #00695c;
}
</style>

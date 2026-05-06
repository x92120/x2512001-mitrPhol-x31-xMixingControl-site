import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { generateQrDataUrl } from '~/composables/useQrCode'


const $q = useQuasar()
const { getAuthHeader, user } = useAuth()
const { t } = useI18n()

// --- MQTT Integration ---
const { connect, disconnect, onMessage, offMessage, publishMessage } = useMQTT()

// --- State ---
const boxId = ref('')
const boxDetails = ref<any>(null)
const loading = ref(false)

// ── Batch-level recheck ──
const recheckBatchId = ref('')
const batchRecheck = ref<any>(null)      // Response from /recheck-batch/{batch_id}
const recheckFH = computed(() => {
    if (!batchRecheck.value) return []
    return batchRecheck.value.checklist.filter((c: any) => {
        const wh = (c.wh || '').toUpperCase()
        return wh === 'FH' || wh === 'FLAVOUR HOUSE' || wh === 'MIX'
    })
})
const recheckSPP = computed(() => {
    if (!batchRecheck.value) return []
    return batchRecheck.value.checklist.filter((c: any) => {
        const wh = (c.wh || '').toUpperCase()
        return wh === 'SPP' || wh === 'SPECIALITY PREMIX'
    })
})
const allRecheckVerified = computed(() => {
    if (!batchRecheck.value) return false
    return batchRecheck.value.summary.all_ok
})

// ── Awaiting recheck list ──
const awaitingBatches = ref<any[]>([])
const fetchAwaitingBatches = async () => {
    try {
        awaitingBatches.value = await $fetch<any[]>(`${appConfig.apiBaseUrl}/production-batches/awaiting-recheck`, {
            headers: getAuthHeader() as Record<string, string>
        })
    } catch { /* ignore */ }
}

// ── Hold / Unhold ──────────────────────────────────────────────────────────
const holdDialog = ref(false)
const holdTarget = ref<any>(null)   // the batch object being acted on
const holdReason = ref('')
const holdLoading = ref(false)

const openHoldDialog = (batch: any, event: Event) => {
    event.stopPropagation()
    holdTarget.value = batch
    holdReason.value = ''
    holdDialog.value = true
}

const confirmHold = async () => {
    if (!holdTarget.value) return
    holdLoading.value = true
    const batchId = holdTarget.value.batch_id
    const isHeld = holdTarget.value.status === 'Hold'
    const endpoint = isHeld ? 'unhold' : 'hold'
    try {
        await $fetch(`${appConfig.apiBaseUrl}/production-batches/${endpoint}/${batchId}`, {
            method: 'PATCH',
            headers: { ...getAuthHeader() as Record<string, string>, 'Content-Type': 'application/json' },
            body: JSON.stringify({ held_by: user?.value?.username || 'operator', reason: holdReason.value || null })
        })
        $q.notify({
            type: isHeld ? 'positive' : 'warning',
            icon: isHeld ? 'play_circle' : 'pause_circle',
            message: isHeld
                ? `Batch ${batchId} released from Hold → In-Progress`
                : `Batch ${batchId} is now on Hold`,
            timeout: 3000, position: 'top'
        })
        holdDialog.value = false
        await fetchPlansAndBatches()
    } catch (err: any) {
        $q.notify({ type: 'negative', message: err?.data?.detail || 'Hold action failed', position: 'top' })
    } finally {
        holdLoading.value = false
    }
}

// Box scan input (top bar)
const boxScanInput = ref('')

// Bag scan input (above bag list)
const bagScanInput = ref('')
const bagScanRef = ref<any>(null)



// All available batches for the simulator
const allPlans = ref<any[]>([])
const allBatches = ref<any[]>([])

const rawPlans = ref<any[]>([])
const selectedPlantFilter = ref('All Plants')
const availablePlantOptions = computed(() => {
    const plants = new Set<string>()
    rawPlans.value.forEach(p => {
        if (p.plant) plants.add(p.plant)
    })
    return ['All Plants', ...Array.from(plants).sort()]
})

const applyPlantFilter = () => {
    let plans = rawPlans.value
    if (selectedPlantFilter.value !== 'All Plants') {
        plans = plans.filter((p: any) => p.plant === selectedPlantFilter.value)
    }
    allPlans.value = plans
    
    const batches: any[] = []
    plans.forEach((p: any) => {
        if (p.batches) {
            p.batches.forEach((b: any) => {
                batches.push({ ...b, plan_id: p.plan_id, sku_id: p.sku_id, sku_name: p.sku_name })
            })
        }
    })
    allBatches.value = batches
}

watch(selectedPlantFilter, () => {
    applyPlantFilter()
})



// ── Tree navigation state (Left Pane) ──

const selectedPlanId = ref<string | null>(null)
const selectedBatchId = ref<string | null>(null)
const treeSearch = ref('')

// Feedback overlay
const feedback = ref<{ show: boolean, type: 'success' | 'error' | 'warning', message: string, title: string }>({
    show: false,
    type: 'success',
    message: '',
    title: ''
})

// Wrong Box full-screen alert overlay
const wrongBoxAlert = ref<{ show: boolean, bagCode: string, expectedBox: string, newBatchId: string }>({ show: false, bagCode: '', expectedBox: '', newBatchId: '' })

// Sound Settings
const showSoundSettings = ref(false)
const successSoundPreset = ref(import.meta.client ? (localStorage.getItem('recheck_success_sound') || 'beep') : 'beep')
const errorSoundPreset = ref(import.meta.client ? (localStorage.getItem('recheck_error_sound') || 'siren') : 'siren')

const successSoundOptions = [
    { value: 'beep', labelKey: 'sound.shortBeep', icon: 'music_note' },
    { value: 'double_beep', labelKey: 'sound.doubleBeep', icon: 'music_note' },
    { value: 'chime', labelKey: 'sound.chime', icon: 'notifications' },
    { value: 'ding', labelKey: 'sound.ding', icon: 'campaign' },
]
const errorSoundOptions = [
    { value: 'buzzer', labelKey: 'sound.buzzer', icon: 'volume_up' },
    { value: 'siren', labelKey: 'sound.siren', icon: 'warning' },
    { value: 'horn', labelKey: 'sound.horn', icon: 'volume_up' },
    { value: 'alarm', labelKey: 'sound.alarm', icon: 'crisis_alert' },
]

const saveSoundSettings = () => {
    localStorage.setItem('recheck_success_sound', successSoundPreset.value)
    localStorage.setItem('recheck_error_sound', errorSoundPreset.value)
    showSoundSettings.value = false
    $q.notify({ type: 'positive', message: t('sound.saved'), position: 'top' })
}

// ── Scan Feedback ──
const lastScanResult = ref<'none' | 'success' | 'error'>('none')
const flashActive = ref(false)
const setScanFeedback = (result: 'success' | 'error') => {
    lastScanResult.value = result
    flashActive.value = true
    setTimeout(() => { flashActive.value = false }, 1500)
}
const clearScanFeedback = () => {
    lastScanResult.value = 'none'
    flashActive.value = false
}

// --- Computed ---
const scannedCount = computed(() => {
    if (!boxDetails.value) return 0
    return boxDetails.value.bags.filter((b: any) => b.status === 1).length
})

const errorCount = computed(() => {
    if (!boxDetails.value) return 0
    return boxDetails.value.bags.filter((b: any) => b.status === 2).length
})

const totalCount = computed(() => {
    if (!boxDetails.value) return 0
    return boxDetails.value.total_bags || 0
})

const progress = computed(() => {
    if (totalCount.value === 0) return 0
    return scannedCount.value / totalCount.value
})

const allVerified = computed(() => {
    if (!boxDetails.value || totalCount.value === 0) return false
    return boxDetails.value.bags.every((b: any) => b.status === 1)
})

const activeBatchForProduction = computed(() => recheckBatchId.value || selectedBatchId.value)

// --- Methods ---

// ── Tree Navigation computed ── (Plant → Plan → Batch)
const plantNameMap: Record<string, string> = { '01': 'Mixing 1', '02': 'Mixing 2', '03': 'Mixing 3' }

const extractPlantId = (planId: string): string => {
    // Plan_ID format: Pyymmdd-Batch_no-Plant_ID (e.g. P260311-02-01)
    const parts = (planId || '').split('-')
    return parts.length >= 3 ? parts[2]! : '??'
}

const getPlantName = (plantId: string) => plantNameMap[plantId] || `Plant ${plantId}`

const planTree = computed(() => {
    const needle = treeSearch.value.toLowerCase()
    let plans = allPlans.value
    if (needle) {
        plans = plans.filter((p: any) =>
            (p.plan_id || '').toLowerCase().includes(needle) ||
            (p.sku_name || '').toLowerCase().includes(needle) ||
            (p.sku_id || '').toLowerCase().includes(needle) ||
            (p.batches || []).some((b: any) => (b.batch_id || '').toLowerCase().includes(needle))
        )
    }
    return plans
})

// Group plans by plant -> SKU -> Plan for the tree
const plantGroups = computed(() => {
    const groups: Record<string, any> = {}
    for (const plan of planTree.value) {
        let pid: string = '??'
        if (plan.plant) {
            const m = plan.plant.match(/\d+/)
            pid = m ? m[0].padStart(2, '0') : (plan.plant === 'Line-3' ? '03' : plan.plant)
        } else {
            pid = extractPlantId(plan.plan_id)
        }

        if (!groups[pid]) groups[pid] = { plantId: pid, plantName: getPlantName(pid), skus: {} }
        
        const sid = plan.sku_id || '?'
        if (!groups[pid].skus[sid]) groups[pid].skus[sid] = { skuId: sid, skuName: plan.sku_name || sid, plans: [] }
        
        groups[pid].skus[sid].plans.push(plan)
    }
    
    return Object.values(groups)
        .sort((a, b) => a.plantId.localeCompare(b.plantId))
        .map(g => ({
            ...g,
            skus: Object.values(g.skus).sort((a: any, b: any) => a.skuId.localeCompare(b.skuId))
        }))
})

// FH/SPP status helpers for tree badges
const getTreeBatchFH = (batch: any) => {
    const aw = awaitingBatches.value.find((b: any) => b.batch_id === batch.batch_id)
    if (aw) return aw.fh_boxed
    return batch.fh_boxed_at || batch.fh_boxed || false
}
const getTreeBatchSPP = (batch: any) => {
    const aw = awaitingBatches.value.find((b: any) => b.batch_id === batch.batch_id)
    if (aw) return aw.spp_boxed
    return batch.spp_boxed_at || batch.spp_boxed || false
}

// ── FIFO (First In, First Out) Enforcement ──────────────────────────────────
// For each plan: the FIRST batch that is not Done/Cancelled is the ONLY active batch.
const fifoActiveBatchByPlan = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const plan of allPlans.value) {
        const sorted = [...(plan.batches || [])].sort((a: any, b: any) =>
            (a.batch_id || '').localeCompare(b.batch_id || '')
        )
        const active = sorted.find((b: any) =>
            !['Done', 'Cancelled'].includes(b.status || '')
        )
        if (active) map[plan.plan_id] = active.batch_id
    }
    return map
})

// Is this batch the FIFO-active batch for its plan?
const isFifoBatch = (batchId: string): boolean => {
    return Object.values(fifoActiveBatchByPlan.value).includes(batchId)
}

// Get the plan that contains a given batch
const getPlanForBatch = (batchId: string): any => {
    return allPlans.value.find((p: any) =>
        (p.batches || []).some((b: any) => b.batch_id === batchId)
    ) || null
}

// Get the FIFO-active batch blocking access to the given batch
const getFifoBlocker = (batchId: string): string | null => {
    const plan = getPlanForBatch(batchId)
    if (!plan) return null
    return fifoActiveBatchByPlan.value[plan.plan_id] || null
}


const selectBatchFromTree = (batch: any) => {
    selectedBatchId.value = batch.batch_id
    selectedPlanId.value = batch.plan_id || ''
    fetchBatchPreBatchData(batch.batch_id)
    // Auto-fetch SKU steps for detail table
    const plan = allPlans.value.find((p: any) => 
        (p.batches || []).some((b: any) => b.batch_id === batch.batch_id)
    )
    if (plan?.sku_id) fetchSkuSteps(plan.sku_id)
}

// ── PreBatch data for split card ──
const batchPreBatchItems = ref<any[]>([])   // Required items (from prebatch_items)
const batchPackedRecs = ref<any[]>([])       // Packed records (from prebatch_recs)
const prebatchLoading = ref(false)

const fetchBatchPreBatchData = async (batchId: string) => {
    prebatchLoading.value = true
    try {
        const [items, recs] = await Promise.all([
            $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            }).catch(() => []),
            $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            }).catch(() => [])
        ])
        batchPreBatchItems.value = items || []
        batchPackedRecs.value = recs || []
    } catch (e) {
        console.error('Error fetching prebatch data:', e)
    } finally {
        prebatchLoading.value = false
    }
}



// Toggle prebatch item status (Wait ↔ Check)
const toggleItemStatus = async (item: any) => {
    const newStatus = item.status >= 2 ? 0 : 2  // Toggle: 0=Wait, 2=Done(Check)
    try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${item.id}/status?status=${newStatus}`, {
            method: 'PUT',
            headers: getAuthHeader() as Record<string, string>
        })
        item.status = newStatus
        $q.notify({ type: 'positive', message: `Status → ${newStatus >= 2 ? 'Check ✅' : 'Wait ⏳'}`, position: 'top', timeout: 1000 })
    } catch (e) {
        $q.notify({ type: 'negative', message: 'Failed to update status', position: 'top' })
    }
}

// Toggle packed record recheck status
const toggleVerificationStatus = async (item: any) => {
    const newStatus = item.recheck_status === 1 ? 0 : 1
    // Try both prebatch-recs and prebatch-items endpoints based on which one is successful
    const endpoints = [
        `${appConfig.apiBaseUrl}/prebatch-recs/${item.id}/recheck-status?status=${newStatus}`,
        `${appConfig.apiBaseUrl}/prebatch-items/${item.id}/recheck-status?status=${newStatus}`
    ]
    
    let success = false
    for (const url of endpoints) {
        try {
            await $fetch(url, {
                method: 'PATCH',
                headers: getAuthHeader() as Record<string, string>
            })
            success = true
            break
        } catch (e) {
            // Keep trying next endpoint
        }
    }

    if (success) {
        item.recheck_status = newStatus
    } else {
        $q.notify({ type: 'negative', message: 'Failed to update status', position: 'top' })
    }
}

const quickCheckIngredient = async (ing: any) => {
    loading.value = true
    try {
        for (const item of ing.items) {
            if (item.recheck_status !== 1) {
                await toggleVerificationStatus(item)
            }
        }
        $q.notify({ type: 'positive', message: `${ing.re_code} verified`, position: 'top', timeout: 500 })
    } finally {
        loading.value = false
    }
}

// ── Production Process View (Right Pane) ──
const skuSteps = ref<any[]>([])
const skuStepsLoading = ref(false)

const fetchSkuSteps = async (skuId: string) => {
    skuStepsLoading.value = true
    try {
        const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/sku-steps/?sku_id=${skuId}`, {
            headers: getAuthHeader() as Record<string, string>
        })
        skuSteps.value = data || []
    } catch (e) {
        console.error('Error fetching SKU steps:', e)
        skuSteps.value = []
    } finally {
        skuStepsLoading.value = false
    }
}

const showSkuDetail = ref(false)
const openSkuDetail = async () => {
    if (selectedBatchInfo.value?.sku_id) {
        await fetchSkuSteps(selectedBatchInfo.value.sku_id)
        showSkuDetail.value = true
    }
}

const goToStartProduction = async () => {
    if (!selectedBatchId.value) return
    loading.value = true
    try {
        // 1. Call backend to prepare PLC recipe (DB1780)
        try {
            await $fetch(`${appConfig.apiBaseUrl}/plc/send-recipe/${selectedBatchId.value}`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>
            })
            console.log('[StartProd] PLC recipe prepared for:', selectedBatchId.value)
        } catch (e) {
            console.warn('[StartProd] PLC recipe endpoint unavailable, continuing anyway:', e)
        }

        // 2. Publish MQTT start=1 signal to the plant's command topic
        const plantId = (selectedBatchInfo.value?.plant || '01').replace(/\D/g, '') || '1'
        const topic = `mixing/plant/${Number(plantId)}/cmd`
        publishMessage(topic, {
            command: 'READY_TO_START',
            start: 1,
            batch_id: selectedBatchId.value,
            sku_id: selectedBatchInfo.value?.sku_id || '',
            plan_id: selectedBatchInfo.value?.plan_id || '',
            timestamp: new Date().toISOString()
        })
        console.log('[StartProd] MQTT start=1 sent to topic:', topic)

        $q.notify({
            type: 'positive',
            icon: 'rocket_launch',
            message: 'Production START signal sent!',
            caption: `Batch: ${selectedBatchId.value}`,
            position: 'top',
            timeout: 2000
        })

        // 3. Navigate to Mixing Control page — operator confirms there
        await useRouter().push(
            `/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}&from_check=1`
        )
    } catch (e: any) {
        console.error('[StartProd] Error:', e)
        $q.notify({ type: 'warning', message: 'Could not send start signal, navigating anyway.' })
        useRouter().push(`/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}&from_check=1`)
    } finally {
        loading.value = false
    }
}

const expandedPhases = ref<Record<string, boolean>>({})
const togglePhase = (phase: string) => {
    expandedPhases.value[phase] = expandedPhases.value[phase] === false ? true : false
}
const isPhaseExpanded = (phase: string) => {
    return expandedPhases.value[phase] !== false
}

// Group steps by phase_number for displaying process hierarchy
const skuStepsByPhase = computed(() => {
    const groups: Record<string, { phase: string, phase_id: string, steps: any[] }> = {}
    for (const step of skuSteps.value) {
        const ph = step.phase_number || '0'
        if (!groups[ph]) groups[ph] = { phase: ph, phase_id: step.phase_id || '', steps: [] }
        groups[ph].steps.push(step)
    }
    // Sort by phase number, then steps by sub_step
    const sorted = Object.values(groups).sort((a, b) => String(a.phase).localeCompare(String(b.phase), undefined, { numeric: true }))
    for (const g of sorted) g.steps.sort((a: any, b: any) => (a.sub_step || 0) - (b.sub_step || 0))
    return sorted
})

// Color palette for phase grouping
const phaseColors = ['bg-blue-1', 'bg-grey-2']
const phaseColorMap = computed(() => {
    const map: Record<string, string> = {}
    const uniquePhases = [...new Set(skuSteps.value.map((s: any) => s.phase_id || s.phase_number || '0'))]
    uniquePhases.forEach((ph, i) => {
        map[ph] = phaseColors[i % phaseColors.length]
    })
    return map
})
const getPhaseColor = (step: any) => {
    const key = step.phase_id || step.phase_number || '0'
    return phaseColorMap.value[key] || ''
}

const canStartProduction = computed(() => {
    if (!selectedBatchId.value) {
        console.debug('[canStart] ❌ No selectedBatchId')
        return false
    }
    
    // FIFO: must be the first active batch in its plan
    if (!isFifoBatch(selectedBatchId.value)) {
        console.debug('[canStart] ❌ Not FIFO batch. fifoMap:', JSON.stringify(fifoActiveBatchByPlan.value), 'selected:', selectedBatchId.value)
        return false
    }
    
const isAllPrepackVerified = computed(() => {
    const prePackGroups = prebatchByWarehouse.value.filter(
        (g: any) => g.warehouse === 'FH' || g.warehouse === 'SPP'
    )
    if (prePackGroups.length === 0) return false
    for (const group of prePackGroups) {
        if (!group.ingredients.every((ing: any) => ing.recheck_status === 1)) {
            return false
        }
    }
    return true
})

const canStartProduction = computed(() => {
    if (!selectedBatchId.value) {
        console.debug('[canStart] ❌ No selectedBatchId')
        return false
    }
    
    // FIFO: must be the first active batch in its plan
    if (!isFifoBatch(selectedBatchId.value)) {
        console.debug('[canStart] ❌ Not FIFO batch. fifoMap:', JSON.stringify(fifoActiveBatchByPlan.value), 'selected:', selectedBatchId.value)
        return false
    }
    
    if (!isAllPrepackVerified.value) {
        return false
    }
    
    console.debug('[canStart] ✅ All checks passed!')
    return true
})


// Info about the currently selected batch (from tree/loaded plan data)
const selectedBatchInfo = computed(() => {
    const bid = recheckBatchId.value || boxId.value || selectedBatchId.value
    if (!bid) return null
    for (const plan of allPlans.value) {
        for (const batch of (plan.batches || [])) {
            if (batch.batch_id === bid) {
                return {
                    plan_id: plan.plan_id,
                    sku_id: plan.sku_id,
                    sku_name: plan.sku_name,
                    plant: plan.plant,
                    batch_id: batch.batch_id,
                    batch_size: batch.batch_size,
                    fh_boxed: !!batch.fh_boxed_at,
                    spp_boxed: !!batch.spp_boxed_at,
                    fh_delivered: !!batch.fh_delivered_at,
                    spp_delivered: !!batch.spp_delivered_at,
                    status: batch.status,
                }
            }
        }
    }
    return null
})

// PreBatch items grouped by warehouse for middle pane
const prebatchByWarehouse = computed(() => {
    const groups: Record<string, any[]> = {}
    for (const item of batchPreBatchItems.value) {
        let wh = (item.wh || 'MIX').toUpperCase()
        if (wh === 'FLAVOUR HOUSE') wh = 'FH'
        if (wh === 'SPECIALITY PREMIX') wh = 'SPP'
        if (!groups[wh]) groups[wh] = []
        groups[wh].push(item)
    }
    
    const whOrder = ['MIX', 'FH', 'SPP']
    
    return Object.keys(groups).sort((a, b) => {
        let ia = whOrder.indexOf(a)
        let ib = whOrder.indexOf(b)
        if (ia === -1) ia = 99
        if (ib === -1) ib = 99
        if (ia !== ib) return ia - ib
        return a.localeCompare(b)
    }).map(wh => {
        const sortedItems = groups[wh]!.sort((a, b) => (a.re_code || '').localeCompare(b.re_code || ''))
        
        const reCodeGroups: Record<string, any[]> = {}
        for (const item of sortedItems) {
            const re = item.re_code || 'Unknown'
            if (!reCodeGroups[re]) reCodeGroups[re] = []
            reCodeGroups[re].push(item)
        }
        
        const summaryItems = Object.keys(reCodeGroups).map(re => {
            const reqItems = reCodeGroups[re]
            const totalVol = reqItems.reduce((sum, i) => sum + (i.required_volume || 0), 0)

            let displayItems = reqItems
            if (wh !== 'MIX') {
                const packed = batchPackedRecs.value.filter((r: any) => (r.re_code || '') === re)
                if (packed.length > 0) {
                    packed.sort((a: any, b: any) => (a.package_no || 0) - (b.package_no || 0))
                    displayItems = packed.map((p: any) => ({
                        ...p,
                        status: p.packing_status === 1 ? 2 : 0, 
                        required_volume: p.net_volume || 0
                    }))
                }
            }

            const allChecked = displayItems.length > 0 && displayItems.every((i: any) => i.recheck_status === 1)
            const anyFailed = displayItems.some((i: any) => i.recheck_status === 2)
            const recheck_status = anyFailed ? 2 : (allChecked ? 1 : 0)
            
            return {
                re_code: re,
                total_volume: totalVol,
                recheck_status: recheck_status,
                items: displayItems
            }
        })

        return {
            warehouse: wh,
            ingredients: summaryItems
        }
    })
})

const getWhTotalCount = (wh: string) => {
    const group = prebatchByWarehouse.value.find(g => g.warehouse === wh)
    return group ? group.ingredients.length : 0
}

const getWhCheckCount = (wh: string) => {
    const group = prebatchByWarehouse.value.find(g => g.warehouse === wh)
    if (!group) return 0
    return group.ingredients.filter((ing: any) => ing.recheck_status === 1).length
}

const getWhStatus = (wh: string) => {
    const total = getWhTotalCount(wh)
    if (total === 0) return -1 // Not applicable
    const checked = getWhCheckCount(wh)
    return checked >= total ? 1 : 0
}


const fetchPlansAndBatches = async () => {
    try {
        const resp = await $fetch<any>(`${appConfig.apiBaseUrl}/production-plans/?status=active`, {
            headers: getAuthHeader() as Record<string, string>
        })
        rawPlans.value = resp.plans || resp || []
        applyPlantFilter()
    } catch (err) {
        console.error('Error fetching batches:', err)
    }
}

const fetchBoxDetails = async (id: string) => {
    loading.value = true
    try {
        const data = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-box/${id}`, {
            headers: getAuthHeader() as Record<string, string>
        })
        boxDetails.value = data
        boxId.value = id
        showFeedback('success', `Box loaded: ${data.total_bags} bags found`, 'BOX SCANNED')
        
        // Extract the proper batch_id from the box barcode.
        // Box barcodes have format: {batch_id}-{re_code}-{pkg_no}
        // Batch IDs have format: P{date}-{line}-{seq} (e.g., P260321-02-02-001)
        // We detect by finding a match in allPlans' batch list
        let targetBatchId = id
        for (const plan of allPlans.value) {
            for (const batch of (plan.batches || [])) {
                if (id.startsWith(batch.batch_id)) {
                    targetBatchId = batch.batch_id
                    break
                }
            }
            if (targetBatchId !== id) break
        }
        fetchBatchPreBatchData(targetBatchId)
        // Auto-focus bag scan for immediate scanning
        nextTick(() => { bagScanRef.value?.focus() })
    } catch (error: any) {
        console.error('Error fetching box details:', error)
        const errMsg = error.data?.detail || ''
        if (errMsg.includes('Not Found') || error.response?.status === 404) {
            $q.notify({
                type: 'warning',
                message: 'No bags have been packed for this batch yet.',
                position: 'top'
            })
        } else {
            $q.notify({
                type: 'negative',
                message: errMsg || 'Box not found or no bags inside',
                position: 'top'
            })
        }
        boxDetails.value = null
    } finally {
        loading.value = false
    }
}

// ── Batch-level recheck fetch ──
const fetchBatchRecheck = async (batchId: string) => {
    loading.value = true
    try {
        const data = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-batch/${batchId}`, {
            headers: getAuthHeader() as Record<string, string>
        })
        batchRecheck.value = data
        recheckBatchId.value = batchId
        boxId.value = batchId
        boxDetails.value = null // Clear box-level data
        const s = data.summary
        showFeedback('success', `Batch loaded: ${s.total} items (${s.checked} checked, ${s.pending} pending)`, 'BATCH LOADED')
        
        // Refresh packed recs and items so canStartProduction reflects latest state
        fetchBatchPreBatchData(batchId)
        
        // --- NEW: POPUP PROMPT FOR BAG SCAN ---
        $q.notify({
            message: 'PLEASE SCAN PRE-BATCH LABELS',
            caption: `Batch: ${batchId} | Verified: ${s.checked}/${s.total}`,
            icon: 'qr_code_scanner',
            color: 'indigo-10',
            position: 'center',
            timeout: 3000,
            classes: 'text-h6 q-pa-md shadow-10'
        })

        playSound('success')
        setTimeout(() => { bagScanRef.value?.focus() }, 200)
    } catch (error: any) {
        console.error('Error fetching batch recheck:', error)
        batchRecheck.value = null
        // Fall back to box-level
        return false
    } finally {
        loading.value = false
    }
    return true
}

// ── Reset batch recheck ──
const resetBatchRecheck = async () => {
    if (!recheckBatchId.value) return
    loading.value = true
    try {
        await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/reset-batch/${recheckBatchId.value}`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>
        })
        
        showFeedback('success', `All checked status for batch ${recheckBatchId.value} has been reset.`, 'RESET SUCCESS')
        playSound('success')
        
        // Refresh batch recheck and prebatch items
        await fetchBatchRecheck(recheckBatchId.value)
    } catch (error: any) {
        console.error('Error resetting batch recheck:', error)
        showFeedback('error', 'Failed to reset batch checking status.', 'RESET ERROR')
    } finally {
        loading.value = false
    }
}

// ── Batch-level bag verify ──
const verifyBatchBag = async (bagBarcode: string) => {
    if (!recheckBatchId.value) return
    loading.value = true
    try {
        const response = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-bag`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>,
            body: {
                batch_id: recheckBatchId.value,
                bag_barcode: bagBarcode,
                operator: user.value?.username || 'Operator'
            }
        })

        if (response.status === 'OK') {
            showFeedback('success', `${response.bag.re_code} — ${response.bag.actual}kg ✓`, 'RE-CHECK OK')
            playSound('success')
            setScanFeedback('success')
        } else {
            showFeedback('error', `${response.bag.re_code}: Expected ${response.bag.target}kg, got ${response.bag.actual}kg`, 'WEIGHT MISMATCH')
            playSound('error')
            setScanFeedback('error')
        }

        // Refresh batch recheck
        await fetchBatchRecheck(recheckBatchId.value)
    } catch (error: any) {
        const detail = error.data?.detail || 'Verification failed'
        if (detail.includes('does not belong') || detail.includes('not found')) {
            // Extract the potential new batch ID from the bag barcode (e.g., P260420-02-02-014-CL009A-1 -> P260420-02-02-014)
            let parsedNewBatchId = ''
            if (bagBarcode.startsWith('P')) {
                const parts = bagBarcode.split('-')
                if (parts.length >= 4) {
                    parsedNewBatchId = parts.slice(0, 4).join('-')
                }
            }
            
            if (bagBarcode === recheckBatchId.value) {
                showFeedback('warning', 'You scanned the Batch Label! Please scan an Ingredient Bag instead.', 'BATCH LABEL SCANNED')
                playSound('error')
                setScanFeedback('error')
            } else if (parsedNewBatchId === recheckBatchId.value) {
                showFeedback('error', `Ingredient not found in batch recipe: ${bagBarcode}`, 'INVALID INGREDIENT')
                playSound('error')
                setScanFeedback('error')
            } else {
                wrongBoxAlert.value = { 
                    show: true, 
                    bagCode: bagBarcode, 
                    expectedBox: recheckBatchId.value || '', 
                    newBatchId: parsedNewBatchId 
                }
                playSound('wrong_box')
                showFeedback('error', `BAG [${bagBarcode}] does NOT belong to this batch!`, '⚠ WRONG BATCH ⚠')
            }
        } else {
            showFeedback('error', detail, 'ERROR')
            playSound('error')
        }
    } finally {
        loading.value = false
        bagScanInput.value = ''
        nextTick(() => { bagScanRef.value?.focus() })
    }
}

const handleWrongBoxSwitch = async () => {
    const newBatch = wrongBoxAlert.value.newBatchId
    const bagBarcode = wrongBoxAlert.value.bagCode
    wrongBoxAlert.value.show = false
    
    if (!newBatch) return
    
    // Simulate a unified scan to route to the new batch and verify the bag
    await parseAndHandleScan(bagBarcode, 'bag')
}

const startNewBatch = () => {
    selectedBatchId.value = null
    recheckBatchId.value = ''
    boxId.value = ''
    batchPreBatchItems.value = []
    batchPackedRecs.value = []
    batchRecheck.value = null
    wrongBoxAlert.value.show = false
    boxScanInput.value = ''
    bagScanInput.value = ''
    treeSearch.value = ''
}

const handleMqttBarcode = (topic: string, payload: any) => {
    // Topic can be 'Barcode' or contain 'barcode'
    if (topic === 'Barcode' || topic.toLowerCase().endsWith('/barcode')) {
        console.log('📡 [MQTT Barcode Received]', topic, payload)
        
        // Payload could be a JSON object or a raw string
        let barcodeStr = ''
        if (typeof payload === 'object' && payload !== null) {
            // If it's the standard scanner JSON: {"b":"...", "m":"...", ...}
            if (payload.b) {
                // Re-stringify to let parseAndHandleScan deal with its custom regex logic
                barcodeStr = JSON.stringify(payload)
            } else {
                // Fallback: use first string field or raw
                barcodeStr = payload.raw || JSON.stringify(payload)
            }
        } else {
            barcodeStr = String(payload)
        }

        if (barcodeStr) {
            // Determine context: if batch is loaded, it's a bag scan; otherwise it's a box/batch scan
            const context = (selectedBatchId.value && batchPreBatchItems.value.length > 0) ? 'bag' : 'box'
            parseAndHandleScan(barcodeStr, context)
        }
    }
}

const parseAndHandleScan = async (barcode: string, context: 'box' | 'bag') => {
    barcode = barcode.trim()
    
    let candidate = barcode
    let isJson = false

    // --- Smart parser: try standard JSON first, fallback to custom regex for malformed payloads ---
    let parsedOk = false
    let scanFields: Record<string, any> = {}
    
    if (barcode.startsWith('{')) {
        // 1) Try standard JSON.parse first (for valid JSON like the MQTT Barcode topic)
        try {
            scanFields = JSON.parse(barcode)
            parsedOk = true
        } catch {
            // 2) Fallback: Custom key:value parser for scanner's non-standard format
            // e.g. {"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}
            let inner = barcode.substring(1)
            if (inner.endsWith('}')) inner = inner.substring(0, inner.length - 1)
            
            const regex = /"?(\w+):([^,"}]*)"?/g
            let m
            while ((m = regex.exec(inner)) !== null) {
                const key = m[1]!
                let val: any = m[2]!.replace(/"/g, '')
                const num = Number(val)
                scanFields[key] = isNaN(num) || val === '' ? val : num
            }
            if (Object.keys(scanFields).length > 0) parsedOk = true
        }
        
        if (scanFields.b) {
            const batchRecordId = String(scanFields.b)
            // Batch ID extraction:
            // Full record format: PYYMMDD-Plan-Plant-Sequence-RECode-BagNo
            // e.g. P260420-02-02-014-FV039A-1 → Batch ID = P260420-02-02-014
            if (batchRecordId.toUpperCase().startsWith('P')) {
                const parts = batchRecordId.split('-')
                if (parts.length >= 4) {
                    // Full Batch ID: first 4 parts (PYYMMDD-Plan-Plant-Sequence)
                    candidate = parts.slice(0, 4).join('-')
                } else if (parts.length === 3) {
                    candidate = batchRecordId
                } else {
                    candidate = batchRecordId
                }
            } else {
                candidate = batchRecordId
            }
            barcode = batchRecordId  // Full record ID for bag verification
            isJson = true
            console.log('[Scanner Parse]', { candidate, batchRecordId, scanFields })
        }
    }

    if (!isJson) {
        // Clean up potentially wrapped quotes
        if (barcode.startsWith('"') && barcode.endsWith('"')) {
            barcode = barcode.substring(1, barcode.length - 1)
        }
        
        // Flexible split handling
        const parts = barcode.split(',')
        if (context === 'box') {
            if (parts.length >= 2) {
                candidate = parts[1]! // Assume comma format: TYPE,ID,...
            } else {
                candidate = barcode
            }
        } else {
            candidate = barcode
        }

        // Final check for Batch ID format in non-JSON strings
        if (candidate.startsWith('P')) {
            const dashParts = candidate.split('-')
            if (dashParts.length >= 4) {
                candidate = dashParts.slice(0, 4).join('-')
            }
        }
    }
 
    // ── WORKFLOW ROUTING ──
    const batchAlreadyLoaded = !!(selectedBatchId.value && batchPreBatchItems.value.length > 0)
    
    // If the scanned candidate is DIFFERENT from current batch, force reload new batch
    const isNewBatchScan = candidate.startsWith('P') && candidate !== selectedBatchId.value

    // ── FIFO GATE ──────────────────────────────────────────────────────────
    // Only allow scanning the FIRST non-Done batch in the plan (First In, First Out).
    // Check only when we have a recognised batch_id scan (starts with P and 4 parts).
    if (candidate.startsWith('P') && candidate.split('-').length >= 4) {
        const isKnownBatch = allBatches.value.some(b => b.batch_id === candidate)
        if (isKnownBatch && !isFifoBatch(candidate)) {
            const blocker = getFifoBlocker(candidate)
            showFeedback(
                'error',
                blocker
                    ? `FIFO: Complete batch "${blocker}" first before scanning "${candidate}"`
                    : `Batch "${candidate}" is not the active FIFO batch`,
                '⛔ OUT OF ORDER (FIFO)'
            )
            playSound('error')
            setScanFeedback('error')
            bagScanInput.value = ''
            boxScanInput.value = ''
            $q.notify({
                type: 'negative',
                icon: 'block',
                message: '⛔ FIFO ORDER VIOLATION',
                caption: blocker ? `Must complete: ${blocker}` : 'Batch not in FIFO order',
                position: 'center',
                timeout: 4000,
                classes: 'text-h6 q-pa-md shadow-10'
            })
            playSound('error')
            return
        }
    }
    // ───────────────────────────────────────────────────────────────────────

    if (!batchAlreadyLoaded || isNewBatchScan) {

        // ═══ STEP 1: LOAD BATCH ═══
        
        // Find matching batch
        const foundBatch = allBatches.value.find(b => b.batch_id === candidate) 
            || allBatches.value.find(b => b.batch_id.startsWith(candidate))
            || allBatches.value.find(b => candidate.startsWith(b.batch_id))
        
        if (foundBatch) {
            selectBatchFromTree(foundBatch)
            candidate = foundBatch.batch_id
            treeSearch.value = candidate  // Only set tree search on confirmed match
        } else {
            selectedBatchId.value = candidate
            treeSearch.value = candidate
            fetchBatchPreBatchData(candidate)
        }

        // Load verification data
        const success = await fetchBatchRecheck(candidate)
        
        if (success) {
            $q.notify({
                message: '📦 Batch Loaded — SCAN PREBATCH LABELS',
                caption: `Batch: ${candidate}`,
                icon: 'qr_code_scanner',
                color: 'indigo-10',
                position: 'center',
                timeout: 2000,
                classes: 'text-h6 q-pa-md shadow-10'
            })
        }
        
        // Reset inputs
        bagScanInput.value = ''
        boxScanInput.value = ''

        // --- NEW: If this scan was actually a BAG label, verify it immediately after loading ---
        // Wait a small bit for state to update (prebatchByWarehouse computed)
        setTimeout(async () => {
            await verifyBagContent(barcode, candidate, isJson, scanFields)
        }, 500)
        
        setTimeout(() => { bagScanRef.value?.focus() }, 300)
        
    } else {
        // ═══ STEP 2+: VERIFY PREBATCH LABEL (GREEN SPOT) ═══
        await verifyBagContent(barcode, candidate, isJson, scanFields)
    }
}

/**
 * Shared logic to verify a bag's content against the loaded batch.
 */
const verifyBagContent = async (barcode: string, batchId: string, isJson: boolean, scanFields: any) => {
    let reCodeFromScan = ''
    let fullRecordId = ''
    let matCodeFromScan = ''
    
    if (isJson && scanFields.b) {
        fullRecordId = String(scanFields.b)
        const parts = fullRecordId.split('-')
        if (parts.length >= 5) {
            // Batch: PYYMMDD-Plan-Plant-Seq, then RE code parts, then bag number
            // Extract RE code: everything between batch ID and the last segment (bag number)
            const batchParts = batchId.split('-').length  // e.g. 4 parts for P260420-02-02-014
            reCodeFromScan = parts.slice(batchParts, parts.length - 1).join('-')
        } else if (parts.length >= 4) {
            reCodeFromScan = fullRecordId.replace(batchId + '-', '').replace(/-\d+$/, '')
        }
        // Also use material code from scan for fallback matching
        if (scanFields.m) {
            matCodeFromScan = String(scanFields.m)
        }
    } else {
        fullRecordId = barcode
        const parts = barcode.split('-')
        if (parts.length > 3) {
            const batchParts = batchId.split('-').length
            reCodeFromScan = parts.slice(batchParts, parts.length - 1).join('-')
        }
    }
    
    console.log('[Verify Bag Content]', { fullRecordId, reCodeFromScan, matCodeFromScan, batchId, prebatchGroups: prebatchByWarehouse.value.length })
    
    // Find matching ingredient across all warehouse groups
    let matched = false
    for (const group of prebatchByWarehouse.value) {
        // Multi-strategy matching: RE code, material code, or partial match
        const ing = group.ingredients.find((i: any) => {
            const rc = (i.re_code || '').trim()
            const scan = reCodeFromScan.trim()
            // Exact RE code match
            if (rc === scan) return true
            // Case-insensitive match
            if (rc.toLowerCase() === scan.toLowerCase()) return true
            // RE code contained in full record ID
            if (fullRecordId.includes(rc)) return true
            // Material code match (fallback)
            if (matCodeFromScan && i.items?.some((it: any) => String(it.mat_sap_code) === matCodeFromScan || String(it.material_id) === matCodeFromScan)) return true
            return false
        })

        if (ing && ing.recheck_status !== 1) {
            // Try API verification first
            try {
                await quickCheckIngredient(ing)
            } catch (e) {
                console.warn('[Verify] API failed, setting local status', e)
            }
            // Ensure local state is updated regardless
            ing.recheck_status = 1
            for (const item of (ing.items || [])) {
                item.recheck_status = 1
            }
            setScanFeedback('success')
            playSound('success')
            showFeedback('success', `✅ ${ing.re_code} — Verified!`, 'PREBATCH OK')
            matched = true
            break
        } else if (ing && ing.recheck_status === 1) {
            setScanFeedback('success')
            showFeedback('warning', `${ing.re_code} already verified`, 'DUPLICATE SCAN')
            matched = true
            break
        }
    }
    
    if (!matched && fullRecordId.includes('-')) {
        if (batchRecheck.value && recheckBatchId.value) {
            await verifyBatchBag(fullRecordId)
        } else {
            setScanFeedback('error')
            playSound('error')
            showFeedback('error', `Ingredient "${reCodeFromScan || fullRecordId}" not found in batch`, 'NOT MATCHED')
            console.warn('[Verify] No match found. Available RE codes:', prebatchByWarehouse.value.flatMap(g => g.ingredients.map((i: any) => i.re_code)))
        }
    }
    
    if (canStartProduction.value) {
        $q.notify({
            message: '🎉 ALL INGREDIENTS VERIFIED!',
            caption: 'Ready to Start Production',
            icon: 'check_circle',
            color: 'green-9',
            position: 'center',
            timeout: 5000,
            classes: 'text-h5 q-pa-lg shadow-10'
        })
        playSound('success')
    }
    
    bagScanInput.value = ''
    boxScanInput.value = ''
    nextTick(() => { bagScanRef.value?.focus() })
}

const verifyBag = async (bagBarcode: string) => {
    if (!boxDetails.value) {
        $q.notify({ type: 'warning', message: 'Scan a Box first!' })
        return
    }

    loading.value = true
    try {
        const response = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-bag`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>,
            body: {
                box_id: boxId.value,
                bag_barcode: bagBarcode,
                operator: user.value?.username || 'Operator'
            }
        })

        if (response.status === 'OK') {
            showFeedback('success', `${response.bag.re_code} — ${response.bag.actual}kg ✓`, 'RE-CHECK OK')
            playSound('success')
            setScanFeedback('success')
        } else {
            showFeedback('error', `${response.bag.re_code}: Expected ${response.bag.target}kg, got ${response.bag.actual}kg (diff: ${response.bag.diff.toFixed(3)}kg)`, 'WEIGHT MISMATCH')
            playSound('error')
            setScanFeedback('error')
        }

        // Refresh box details
        await fetchBoxDetails(boxId.value)
    } catch (error: any) {
        const detail = error.data?.detail || 'Verification failed'
        // Detect "wrong box" type errors
        if (detail.includes('does not belong') || detail.includes('not found')) {
            // WRONG BOX! Show alarming full-screen alert
            wrongBoxAlert.value = { show: true, bagCode: bagBarcode, expectedBox: boxId.value }
            playSound('wrong_box')
            showFeedback('error', `BAG [${bagBarcode}] does NOT belong to this box!`, '⚠ WRONG BOX ⚠')
            setTimeout(() => { wrongBoxAlert.value.show = false }, 3500)
        } else {
            showFeedback('error', detail, 'ERROR')
            playSound('error')
        }
    } finally {
        loading.value = false
        bagScanInput.value = ''
        // Re-focus bag scan input for next scan
        nextTick(() => { bagScanRef.value?.focus() })
    }
}

const releaseBatch = async () => {
    const batchToRelease = activeBatchForProduction.value
    if (!batchToRelease) return
    
    loading.value = true
    try {
        await $fetch(`${appConfig.apiBaseUrl}/production-batches/${batchToRelease}/release`, {
            method: 'PATCH',
            headers: getAuthHeader() as Record<string, string>
        })
        
        showFeedback('success', 'Batch approved and released!', 'PRODUCTION READY')
        playSound('success')
        
        // Refresh UI state
        if (boxId.value) {
            await fetchBoxDetails(boxId.value)
        } else {
            await fetchAwaitingBatches()
        }
    } catch (error: any) {
        $q.notify({
            type: 'negative',
            message: error.data?.detail || 'Failed to release batch',
            position: 'top'
        })
    } finally {
        loading.value = false
    }
}

const resetBox = () => {
    boxDetails.value = null
    boxId.value = ''
    boxScanInput.value = ''
    bagScanInput.value = ''
}


const onBoxScanSubmit = () => {
    const val = boxScanInput.value.trim()
    if (val) {
        parseAndHandleScan(val, 'box')
        boxScanInput.value = ''
    }
}

const onBagScanSubmit = () => {
    const val = bagScanInput.value.trim()
    if (val) {
        parseAndHandleScan(val, 'bag')
        bagScanInput.value = ''
    }
}

// ── Unified scan handler (single input for everything) ──
const onUnifiedScanSubmit = () => {
    const val = boxScanInput.value.trim()
    if (!val) return
    // Auto-detect context: if a batch is already loaded, treat as bag scan
    const context = (selectedBatchId.value && batchPreBatchItems.value.length > 0) ? 'bag' : 'box'
    parseAndHandleScan(val, context)
    boxScanInput.value = ''
}

// Auto-submit debounce for unified scan input
let scanDebounce: ReturnType<typeof setTimeout> | null = null

watch(boxScanInput, (val) => {
    if (scanDebounce) clearTimeout(scanDebounce)
    if (!val?.trim()) return
    scanDebounce = setTimeout(() => { onUnifiedScanSubmit() }, 500)
})

// --- Helpers ---

const showFeedback = (type: 'success' | 'error' | 'warning', message: string, title: string) => {
    feedback.value = { show: true, type, message, title }
    setTimeout(() => { feedback.value.show = false }, 3500)
}

// --- Sound Engine ---
const playSoundPreset = (preset: string) => {
    try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const t = ctx.currentTime
        
        const tone = (freq: number, start: number, dur: number, vol: number, wave: OscillatorType = 'sine') => {
            const osc = ctx.createOscillator()
            const gain = ctx.createGain()
            osc.type = wave
            osc.connect(gain)
            gain.connect(ctx.destination)
            osc.frequency.setValueAtTime(freq, t + start)
            gain.gain.setValueAtTime(vol, t + start)
            gain.gain.exponentialRampToValueAtTime(0.01, t + start + dur)
            osc.start(t + start)
            osc.stop(t + start + dur)
        }

        switch (preset) {
            // === SUCCESS SOUNDS ===
            case 'beep':
                tone(880, 0, 0.2, 0.12)
                break
            case 'double_beep':
                tone(880, 0, 0.12, 0.12)
                tone(1100, 0.15, 0.12, 0.12)
                break
            case 'chime':
                tone(523, 0, 0.15, 0.1)
                tone(659, 0.12, 0.15, 0.1)
                tone(784, 0.24, 0.25, 0.12)
                break
            case 'ding':
                tone(1200, 0, 0.4, 0.1)
                tone(1200, 0, 0.4, 0.06, 'triangle')
                break

            // === ERROR SOUNDS ===
            case 'buzzer':
                for (let i = 0; i < 3; i++) tone(400 - i * 80, i * 0.18, 0.15, 0.18, 'square')
                break
            case 'siren':
                for (let i = 0; i < 6; i++) tone(i % 2 === 0 ? 800 : 400, i * 0.2, 0.18, 0.25, 'sawtooth')
                break
            case 'horn':
                tone(200, 0, 0.6, 0.25, 'sawtooth')
                tone(201, 0, 0.6, 0.15, 'square')
                break
            case 'alarm':
                for (let i = 0; i < 8; i++) tone(i % 2 === 0 ? 600 : 900, i * 0.12, 0.1, 0.2, 'square')
                break
        }
    } catch {}
}

const playSound = (type: 'success' | 'error' | 'wrong_box') => {
    if (type === 'success') {
        playSoundPreset(successSoundPreset.value)
    } else {
        playSoundPreset(errorSoundPreset.value)
    }
}

const getStatusIcon = (status: number) => {
    if (status === 1) return 'check_circle'
    if (status === 2) return 'error'
    return 'radio_button_unchecked'
}

const getStatusColor = (status: number) => {
    if (status === 1) return 'positive'
    if (status === 2) return 'negative'
    return 'grey-6'
}


// ── Print Batch Label Report (QR codes for all prebatch ingredients) ──
const printBatchLabelReport = async (batchId: string) => {
    // Find the batch and its parent plan
    let targetPlan: any = null
    let targetBatch: any = null
    for (const plan of allPlans.value) {
        const batch = (plan.batches || []).find((b: any) => b.batch_id === batchId)
        if (batch) {
            targetPlan = plan
            targetBatch = batch
            break
        }
    }
    if (!targetPlan) {
        $q.notify({ type: 'warning', message: `Batch ${batchId} not found` })
        return
    }

    const ingredients = targetPlan.ingredients || []
    if (ingredients.length === 0) {
        $q.notify({ type: 'warning', message: 'No ingredients found for this batch\'s SKU recipe.' })
        return
    }

    $q.notify({ type: 'info', message: 'Generating label report...', timeout: 1500, position: 'top' })

    const now = new Date().toLocaleString('en-GB')
    const batchSize = targetBatch.batch_size || 0

    // Generate QR code for each ingredient
    const labelCards: string[] = []
    for (const ing of ingredients) {
        const volPerBatch = ing.vol_per_batch || 0
        // Build the barcode payload: {b, m, p, n, t}
        const barcodePayload = JSON.stringify({
            b: `${batchId}-${ing.re_code}-1`,
            m: ing.mat_sap_code || '',
            p: '1/1',
            n: Math.round(volPerBatch * 100000) / 100000,
            t: Math.round(volPerBatch * 100000) / 100000
        })
        const qrDataUrl = await generateQrDataUrl(barcodePayload, 200)

        const whColor = (ing.wh || '').toUpperCase() === 'FH' ? '#6a1b9a' : (ing.wh || '').toUpperCase() === 'SPP' ? '#e65100' : '#0277bd'
        
        labelCards.push(`
            <div class="label-card">
                <div class="label-header" style="background:${whColor};">
                    <span class="wh-badge">${(ing.wh || 'MIX').toUpperCase()}</span>
                    <span class="re-code">${ing.re_code}</span>
                </div>
                <div class="label-body">
                    <div class="qr-section">
                        <img src="${qrDataUrl}" class="qr-img" />
                    </div>
                    <div class="info-section">
                        <div class="info-row"><span class="lbl">Batch</span><span class="val text-bold">${batchId}</span></div>
                        <div class="info-row"><span class="lbl">Material</span><span class="val">${ing.mat_sap_code || '-'}</span></div>
                        <div class="info-row"><span class="lbl">Name</span><span class="val name-text">${ing.name || ing.re_code}</span></div>
                        <div class="info-row"><span class="lbl">Volume</span><span class="val text-bold">${volPerBatch.toFixed(5)} kg</span></div>
                        <div class="info-row"><span class="lbl">Phase</span><span class="val">${ing.phases || '-'}</span></div>
                    </div>
                </div>
                <div class="label-footer">
                    <span style="font-size:8px;color:#999;word-break:break-all;">${barcodePayload}</span>
                </div>
            </div>
        `)
    }

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Batch Labels - ${batchId}</title>
    <style>
        @page { size: A4 portrait; margin: 8mm; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #222; }
        .report-header { background: linear-gradient(135deg, #1565c0, #0d47a1); color: #fff; padding: 12px 18px; border-radius: 6px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .report-header h1 { font-size: 18px; margin: 0; }
        .info-strip { display: flex; gap: 12px; margin-bottom: 10px; font-size: 12px; flex-wrap: wrap; }
        .info-strip .chip { background: #e3f2fd; color: #1565c0; padding: 4px 10px; border-radius: 4px; font-weight: bold; }
        .labels-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        .label-card { border: 2px solid #bbb; border-radius: 8px; overflow: hidden; break-inside: avoid; page-break-inside: avoid; }
        .label-header { color: #fff; padding: 6px 10px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; font-size: 13px; }
        .wh-badge { background: rgba(255,255,255,0.3); padding: 2px 8px; border-radius: 3px; font-size: 11px; }
        .re-code { font-size: 16px; letter-spacing: 1px; }
        .label-body { display: flex; padding: 8px; gap: 10px; }
        .qr-section { flex-shrink: 0; display: flex; align-items: center; }
        .qr-img { width: 120px; height: 120px; }
        .info-section { flex: 1; display: flex; flex-direction: column; gap: 3px; }
        .info-row { display: flex; gap: 6px; font-size: 11px; }
        .info-row .lbl { color: #888; min-width: 55px; font-size: 10px; text-transform: uppercase; }
        .info-row .val { font-weight: 500; color: #333; }
        .text-bold { font-weight: bold !important; color: #1565c0 !important; }
        .name-text { font-size: 10px; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .label-footer { padding: 3px 8px; background: #f9f9f9; border-top: 1px solid #eee; }
        .footer { border-top: 2px solid #1565c0; font-size: 9px; color: #999; padding: 6px 0; margin-top: 12px; display: flex; justify-content: space-between; }
        @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
    </style></head><body>
    <div class="report-header">
        <div>
            <h1>🏷️ PreBatch Ingredient Labels</h1>
            <div style="font-size:10px;margin-top:2px;opacity:.85;">QR Code Labels for Scanner Verification</div>
        </div>
        <div style="font-size:11px;text-align:right;opacity:.9;">Generated: ${now}</div>
    </div>
    <div class="info-strip">
        <div class="chip">🧪 Batch: ${batchId}</div>
        <div class="chip">📦 SKU: ${targetPlan.sku_id}</div>
        <div class="chip">${targetPlan.sku_name || '-'}</div>
        <div class="chip">⚖️ ${batchSize.toFixed(1)} kg</div>
        <div class="chip">📋 ${ingredients.length} Ingredients</div>
        <div class="chip">Plant: ${targetPlan.plant || '-'}</div>
    </div>
    <div class="labels-grid">
        ${labelCards.join('')}
    </div>
    <div class="footer">
        <span>xMixingControl-01 | xMix.co.th</span>
        <span>Batch Ingredient Labels — ${batchId}</span>
        <span>Printed: ${now}</span>
    </div>
    </body></html>`

    const printWindow = window.open('', '_blank')
    if (!printWindow) return
    printWindow.document.open()
    printWindow.document.write(html)
    printWindow.document.close()
    setTimeout(() => { printWindow.print() }, 600)
}

// ── Quality Check Report ──────────────
const showQCReportDialog = ref(false)
const qcReportFromDate = ref('')
const qcReportToDate = ref(new Date().toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }))
const qcReportLoading = ref(false)

const formatDateToApiQC = (val: string) => {
  if (!val) return null
  const parts = val.split('/')
  if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`
  return null
}

// ── Print Batch Summary Ingredient Report (A4) ──
const printBatchIngredientReport = async () => {
    if (!selectedBatchInfo.value || prebatchByWarehouse.value.length === 0) {
        $q.notify({ type: 'warning', message: 'No batch selected or no ingredient data.' })
        return
    }

    const batch = selectedBatchInfo.value
    const now = new Date().toLocaleString('en-GB')
    const totalIngredients = prebatchByWarehouse.value.reduce((sum, g) => sum + g.ingredients.length, 0)
    const checkedIngredients = prebatchByWarehouse.value.reduce((sum, g) => sum + g.ingredients.filter((i: any) => i.recheck_status === 1).length, 0)

    // Generate QR codes for all ingredients
    const qrMap: Record<string, string> = {}
    for (const group of prebatchByWarehouse.value) {
        for (const ing of group.ingredients) {
            const qrText = JSON.stringify({ b: `${batch.batch_id}-${ing.re_code}`, m: ing.items?.[0]?.mat_sap_code || '', wh: group.warehouse })
            qrMap[`${group.warehouse}-${ing.re_code}`] = await generateQrDataUrl(qrText, 120)
        }
    }

    // Build warehouse sections
    const warehouseSections = prebatchByWarehouse.value.map(group => {
        const whChecked = group.ingredients.filter((i: any) => i.recheck_status === 1).length
        const whColor = group.warehouse === 'MIX' ? '#0277bd' : group.warehouse === 'FH' ? '#6a1b9a' : '#e65100'
        
        const rows = group.ingredients.map((ing: any, idx: number) => {
            const qrSrc = qrMap[`${group.warehouse}-${ing.re_code}`] || ''
            const statusIcon = ing.recheck_status === 1 ? '✅' : (ing.recheck_status === 2 ? '❌' : '⏳')
            const statusBg = ing.recheck_status === 1 ? '#e8f5e9' : (ing.recheck_status === 2 ? '#ffebee' : '#fff')
            const matCode = ing.items?.[0]?.mat_sap_code || ing.items?.[0]?.material_id || '-'
            const bagCount = ing.items?.length || 1
            const totalVol = ing.total_volume ? Number(ing.total_volume).toFixed(3) : '-'
            const phase = ing.items?.[0]?.phases || ing.items?.[0]?.phase || '-'
            
            return `<tr style="background:${statusBg}">
                <td class="tc" style="width:30px;">${idx + 1}</td>
                <td style="width:90px;"><img src="${qrSrc}" style="width:80px;height:80px;" /></td>
                <td class="fw">${ing.re_code}</td>
                <td>${matCode}</td>
                <td class="tr">${totalVol}</td>
                <td class="tc">${bagCount}</td>
                <td>${phase}</td>
                <td class="tc" style="font-size:18px;">${statusIcon}</td>
            </tr>`
        }).join('')

        return `
            <div style="margin-bottom:12px;">
                <div style="background:${whColor};color:#fff;padding:6px 12px;border-radius:4px;font-size:14px;font-weight:bold;display:flex;justify-content:space-between;align-items:center;">
                    <span>📦 ${group.warehouse} Warehouse</span>
                    <span>${whChecked} / ${group.ingredients.length} verified</span>
                </div>
                <table class="dt">
                    <thead><tr>
                        <th class="tc" style="width:30px;">#</th>
                        <th style="width:90px;">QR Code</th>
                        <th>RE Code</th>
                        <th>SAP Material</th>
                        <th class="tr">Volume (kg)</th>
                        <th class="tc">Bags</th>
                        <th>Phase</th>
                        <th class="tc">Status</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`
    }).join('')

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Batch Ingredient Report - ${batch.batch_id}</title>
    <style>
        @page { size: A4 portrait; margin: 10mm 12mm; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #222; line-height: 1.4; }
        .header { background: linear-gradient(135deg, #1565c0, #0d47a1); color: #fff; padding: 14px 20px; border-radius: 6px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 20px; margin: 0; }
        .info-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
        .info-box { background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px 12px; }
        .info-box .label { font-size: 10px; color: #888; text-transform: uppercase; font-weight: bold; }
        .info-box .value { font-size: 16px; font-weight: bold; color: #1565c0; margin-top: 2px; }
        table.dt { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 4px; }
        table.dt th { background: #455a64; color: #fff; padding: 5px 8px; text-align: left; font-size: 10px; text-transform: uppercase; }
        table.dt td { padding: 6px 8px; border-bottom: 1px solid #e0e0e0; vertical-align: middle; }
        .tc { text-align: center; }
        .tr { text-align: right; }
        .fw { font-weight: bold; }
        .summary-bar { background: #1565c0; color: #fff; padding: 10px 16px; border-radius: 4px; font-size: 14px; margin-top: 14px; display: flex; justify-content: space-between; align-items: center; }
        .footer { border-top: 2px solid #1565c0; font-size: 9px; color: #999; padding: 6px 0; margin-top: 12px; display: flex; justify-content: space-between; }
        @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
    </style></head><body>
    <div class="header">
        <div>
            <h1>📋 Batch Ingredient Report</h1>
            <div style="font-size:11px;margin-top:3px;opacity:.85;">PreBatch Verification Summary</div>
        </div>
        <div style="font-size:11px;text-align:right;opacity:.9;">Generated: ${now}</div>
    </div>

    <div class="info-grid">
        <div class="info-box"><div class="label">Batch ID</div><div class="value">${batch.batch_id}</div></div>
        <div class="info-box"><div class="label">SKU</div><div class="value">${batch.sku_id}</div></div>
        <div class="info-box"><div class="label">SKU Name</div><div class="value" style="font-size:12px;">${batch.sku_name || '-'}</div></div>
        <div class="info-box"><div class="label">Batch Size</div><div class="value">${batch.batch_size ? Number(batch.batch_size).toFixed(1) : '-'} kg</div></div>
        <div class="info-box"><div class="label">Plan ID</div><div class="value">${batch.plan_id || '-'}</div></div>
        <div class="info-box"><div class="label">Plant</div><div class="value">${batch.plant || '-'}</div></div>
        <div class="info-box"><div class="label">FH Status</div><div class="value" style="color:${batch.fh_boxed ? 'green' : '#888'};">${batch.fh_boxed ? '✅ Boxed' : '⏳ Pending'}</div></div>
        <div class="info-box"><div class="label">SPP Status</div><div class="value" style="color:${batch.spp_boxed ? 'green' : '#888'};">${batch.spp_boxed ? '✅ Boxed' : '⏳ Pending'}</div></div>
    </div>

    ${warehouseSections}

    <div class="summary-bar">
        <span>📊 Total Ingredients: ${totalIngredients}</span>
        <span>✅ ${checkedIngredients} / ${totalIngredients} Verified (${totalIngredients > 0 ? ((checkedIngredients / totalIngredients) * 100).toFixed(0) : 0}%)</span>
        <span>${checkedIngredients === totalIngredients ? '🟢 READY FOR PRODUCTION' : '🟡 VERIFICATION PENDING'}</span>
    </div>

    <div class="footer">
        <span>xMixingControl-01 | xMix.co.th</span>
        <span>Batch Ingredient Report — ${batch.batch_id}</span>
        <span>Printed: ${now}</span>
    </div>
    </body></html>`

    const printWindow = window.open('', '_blank')
    if (!printWindow) return
    printWindow.document.open()
    printWindow.document.write(html)
    printWindow.document.close()
    setTimeout(() => { printWindow.print() }, 500)
}

const printQCReport = async () => {
  qcReportLoading.value = true
  const printWindow = window.open('', '_blank')
  if (!printWindow) { qcReportLoading.value = false; return }
  printWindow.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Loading...</h2></body></html>')
  try {
    let url = `${appConfig.apiBaseUrl}/reports/quality-check`
    const p: string[] = []
    const f = formatDateToApiQC(qcReportFromDate.value)
    const t2 = formatDateToApiQC(qcReportToDate.value)
    if (f) p.push(`from_date=${f}`)
    if (t2) p.push(`to_date=${t2}`)
    if (p.length) url += '?' + p.join('&')
    const data = await $fetch<any>(url)
    const now = new Date().toLocaleString('en-GB')

    const itemRows = (data.items || []).map((r: any, i: number) => `
      <tr class="${r.recheck_status === 1 ? 'bg-ok' : (r.recheck_status === 2 ? 'bg-err' : '')}"><td class="tc">${i+1}</td><td>${r.batch_record_id}</td><td>${r.plan_id || '-'}</td><td>${r.mat_sap_code || '-'}</td><td>${r.re_code || '-'}</td><td class="tc">${r.package_no || '-'}</td><td class="tc">${r.recheck_status === 1 ? '✅ Pass' : '❌ Fail'}</td><td>${r.recheck_by || '-'}</td><td class="tc">${r.recheck_at ? new Date(r.recheck_at).toLocaleString('en-GB') : '-'}</td></tr>
    `).join('')

    const s = data.summary || {}
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Quality Check Report</title>
    <style>@page{size:A4 landscape;margin:8mm 10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222;line-height:1.4}.header{background:#1565c0;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:8px}.header h1{font-size:22px;margin:0}.info-bar{background:#e3f2fd;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#1565c0;font-weight:bold}table.dt{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}table.dt th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.dt td{padding:4px 8px;border-bottom:1px solid #e0e0e0;overflow:hidden;text-overflow:ellipsis}.bg-ok{background:#e8f5e9}.bg-err{background:#ffebee}.grand{background:#1565c0;color:#fff;padding:12px 18px;border-radius:4px;font-size:14px;margin-top:10px;display:flex;justify-content:space-between}.footer{border-top:2px solid #1565c0;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.tr{text-align:right}.tc{text-align:center}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head><body>
    <div class="header"><div><h1>✅ Quality Check Report</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing Control System</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div>
    <div class="info-bar">📅 Period: ${qcReportFromDate.value || 'All'} — ${qcReportToDate.value || 'All'} | Checked: ${s.total_checked || 0} | ✅ Passed: ${s.passed || 0} | ❌ Failed: ${s.failed || 0}</div>
    <table class="dt"><thead><tr><th style="width:3%">#</th><th>Batch Record ID</th><th>Plan ID</th><th>Mat SAP Code</th><th>RE Code</th><th class="tc">Pkg</th><th class="tc">Result</th><th>Checked By</th><th class="tc">Date</th></tr></thead>
    <tbody>${itemRows || '<tr><td colspan="9" class="tc">No records</td></tr>'}</tbody></table>
    <div class="grand"><span>Total Checked: ${s.total_checked || 0}</span><span>✅ ${s.passed || 0} Passed | ❌ ${s.failed || 0} Failed (${s.total_checked ? ((s.passed / s.total_checked) * 100).toFixed(1) : 0}% pass rate)</span></div>
    <div class="footer"><span>xMixingControl-01 | xMix.co.th</span><span>Quality Check Report</span></div>
    </body></html>`
    printWindow.document.open(); printWindow.document.write(html); printWindow.document.close()
    showQCReportDialog.value = false
  } catch (e) { console.error(e); printWindow.close(); $q.notify({ type: 'negative', message: 'Failed' }) }
  finally { qcReportLoading.value = false }
}

const isRecheckInProgress = computed(() => {
    return recheckBatchId.value 
        && batchRecheck.value?.summary?.checked > 0 
        && !isAllPrepackVerified.value;
})

const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    if (isRecheckInProgress.value) {
        const message = 'All pre-batches must be re-checked in one session; leaving or refreshing this page will trigger a full reset.'
        e.returnValue = message
        return message
    }
}

const handleUnload = () => {
    if (isRecheckInProgress.value) {
        navigator.sendBeacon(`${appConfig.apiBaseUrl}/prebatch-recs/reset-batch/${recheckBatchId.value}`)
    }
}

onBeforeRouteLeave((to, from, next) => {
    if (isRecheckInProgress.value) {
        $q.dialog({
            title: 'Warning',
            message: 'All pre-batches must be re-checked in one session; leaving or refreshing this page will trigger a full reset. Do you want to proceed?',
            cancel: true,
            persistent: true
        }).onOk(async () => {
            await resetBatchRecheck()
            next()
        }).onCancel(() => {
            next(false)
        })
    } else {
        next()
    }
})

onMounted(() => {
    fetchPlansAndBatches()
    fetchAwaitingBatches()
    
    // Connect to MQTT and listen for barcodes
    connect()
    onMessage(handleMqttBarcode)
    
    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('unload', handleUnload)
})

onUnmounted(() => {
    offMessage(handleMqttBarcode)
    disconnect()
    window.removeEventListener('beforeunload', handleBeforeUnload)
    window.removeEventListener('unload', handleUnload)
})

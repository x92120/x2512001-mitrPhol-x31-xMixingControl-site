<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'


const $q = useQuasar()
const { getAuthHeader, user } = useAuth()

const { t } = useI18n()

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
const wrongBoxAlert = ref<{ show: boolean, bagCode: string, expectedBox: string }>({ show: false, bagCode: '', expectedBox: '' })

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
    if (selectedBatchId.value) {
        loading.value = true
        try {
            // [Bypassed for testing]
            useRouter().push(`/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}`)
        } catch (e: any) {
            console.error('Edge buffer sync err:', e)
            $q.notify({ type: 'warning', message: 'Edge Buffer Bypassed' })
            useRouter().push(`/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}`)
        } finally {
            loading.value = false
        }
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
    if (!selectedBatchId.value) return false
    
    // EVERY ingredient in EVERY warehouse group MUST be verified (recheck_status === 1)
    for (const group of prebatchByWarehouse.value) {
        if (!group.ingredients.every((ing: any) => ing.recheck_status === 1)) {
            return false
        }
    }
    
    // Ensure we actually have items to check (avoid enabling on empty batches)
    return prebatchByWarehouse.value.length > 0
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
        fetchBatchPreBatchData(id)
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
            wrongBoxAlert.value = { show: true, bagCode: bagBarcode, expectedBox: recheckBatchId.value }
            playSound('wrong_box')
            showFeedback('error', `BAG [${bagBarcode}] does NOT belong to this batch!`, '⚠ WRONG BATCH ⚠')
            setTimeout(() => { wrongBoxAlert.value.show = false }, 3500)
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

const parseAndHandleScan = async (barcode: string, context: 'box' | 'bag') => {
    barcode = barcode.trim()
    
    let candidate = barcode
    let isJson = false

    // --- Custom parser for scanner's non-standard format ---
    // Scanner sends: {"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}
    // This is NOT valid JSON. Keys and values are merged inside quotes as "key:value"
    let parsedOk = false
    let scanFields: Record<string, any> = {}
    
    if (barcode.startsWith('{')) {
        // Custom key:value parser using regex
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
        
        if (scanFields.b) {
            const batchRecordId = String(scanFields.b)
            // Batch ID = first 14 characters (e.g. P260411-021-05)
            // RE Code  = after char 14 (e.g. FV045A-1)
            if (batchRecordId.toUpperCase().startsWith('P') && batchRecordId.length >= 14) {
                candidate = batchRecordId.substring(0, 14)
            } else {
                const parts = batchRecordId.split('-')
                candidate = parts.length >= 3 ? parts.slice(0, 3).join('-') : batchRecordId
            }
            barcode = batchRecordId  // Full record ID for bag verification
            isJson = true
            parsedOk = true
            console.log('[Scanner Parse]', { candidate, batchRecordId, scanFields })
        }
    }

    if (!isJson) {
        // Clean up potentially wrapped quotes
        if (barcode.startsWith('"') && barcode.endsWith('"')) {
            barcode = barcode.substring(1, barcode.length - 1)
        }
        
        // Legacy split handling (Comma separated)
        const parts = barcode.split(',')
        if (context === 'box') {
            if (parts.length >= 3 && parts[2] === 'BOX') {
                candidate = parts[1]!
            } else if (parts.length >= 4 && parts[2] !== 'BOX') {
                const batchRecordId = parts[1]!
                const dashParts = batchRecordId.split('-')
                candidate = dashParts.length >= 4 ? dashParts.slice(0, 4).join('-') : batchRecordId
            } else {
                candidate = barcode
            }
        } else {
            candidate = parts.length >= 4 && parts[2] !== 'BOX' ? parts[1]! : barcode
        }
    }
 
    // ── WORKFLOW ROUTING ──
    // Step 1: If NO batch loaded yet → Load the batch (from any scan type)
    // Step 2+: If batch IS loaded → Verify the scanned preBatch label (green spot)
    
    const batchAlreadyLoaded = !!(selectedBatchId.value && batchPreBatchItems.value.length > 0)
    
    if (!batchAlreadyLoaded) {
        // ═══ STEP 1: LOAD BATCH ═══
        // First scan — extract Batch ID and load all data
        treeSearch.value = candidate
        
        // Flexible batch matching: exact → startsWith → contains
        const foundBatch = allBatches.value.find(b => b.batch_id === candidate) 
            || allBatches.value.find(b => b.batch_id.startsWith(candidate))
            || allBatches.value.find(b => candidate.startsWith(b.batch_id))
        
        if (foundBatch) {
            selectBatchFromTree(foundBatch)
            // Use the actual batch_id from the tree (canonical form)
            candidate = foundBatch.batch_id
            treeSearch.value = candidate
        } else {
            selectedBatchId.value = candidate
            fetchBatchPreBatchData(candidate)
        }

        // Try recheck data
        await fetchBatchRecheck(candidate)
        
        // Show popup: "SCAN PREBATCH LABELS"
        $q.notify({
            message: '📦 Batch Loaded — SCAN PREBATCH LABELS',
            caption: `Batch: ${candidate}`,
            icon: 'qr_code_scanner',
            color: 'indigo-10',
            position: 'center',
            timeout: 3000,
            classes: 'text-h6 q-pa-md shadow-10'
        })
        
        // Focus to bag scan input
        setTimeout(() => { bagScanRef.value?.focus() }, 300)
        
    } else {
        // ═══ STEP 2+: VERIFY PREBATCH LABEL (GREEN SPOT) ═══
        // Batch is loaded — scan is a preBatch bag label
        // Extract RE Code from the scanned data and match against ingredients
        
        let reCodeFromScan = ''
        let fullRecordId = ''
        
        if (isJson && scanFields.b) {
            fullRecordId = String(scanFields.b)
            // RE Code = everything after the 14-char Batch ID, minus bag number
            if (fullRecordId.length > 14) {
                reCodeFromScan = fullRecordId.substring(14).replace(/-\d+$/, '')
            }
        } else {
            fullRecordId = barcode
            // Try to extract RE code from plain text (last segment before bag number)
            const parts = barcode.split('-')
            if (parts.length > 3) {
                reCodeFromScan = parts.slice(3).join('-').replace(/-\d+$/, '')
            }
        }
        
        console.log('[Verify Scan]', { fullRecordId, reCodeFromScan, candidate })
        
        // Find matching ingredient in prebatchByWarehouse
        let matched = false
        for (const group of prebatchByWarehouse.value) {
            const ing = group.ingredients.find((i: any) => 
                i.re_code === reCodeFromScan || 
                i.re_code === fullRecordId
            )
            if (ing && ing.recheck_status !== 1) {
                // Mark this ingredient as verified (GREEN SPOT)
                await quickCheckIngredient(ing)
                setScanFeedback('success')
                playSound('success')
                showFeedback('success', `✅ ${ing.re_code} — Verified!`, 'PREBATCH OK')
                matched = true
                break
            } else if (ing && ing.recheck_status === 1) {
                // Already verified
                setScanFeedback('success')
                showFeedback('warning', `${ing.re_code} already verified`, 'DUPLICATE SCAN')
                matched = true
                break
            }
        }
        
        if (!matched) {
            // Not found in current batch — try backend verification as fallback
            if (batchRecheck.value && recheckBatchId.value) {
                await verifyBatchBag(fullRecordId)
            } else {
                setScanFeedback('error')
                playSound('error')
                showFeedback('error', `RE Code "${reCodeFromScan || fullRecordId}" not found in this batch`, 'NOT MATCHED')
            }
        }
        
        // Check if ALL done → show "READY" message
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
        
        // Re-focus for next scan
        bagScanInput.value = ''
        boxScanInput.value = ''
        nextTick(() => { bagScanRef.value?.focus() })
    }
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

// Auto-search debounce timers
let boxDebounce: ReturnType<typeof setTimeout> | null = null
let bagDebounce: ReturnType<typeof setTimeout> | null = null

watch(boxScanInput, (val) => {
    if (boxDebounce) clearTimeout(boxDebounce)
    if (!val?.trim()) return
    boxDebounce = setTimeout(() => { onBoxScanSubmit() }, 500)
})

watch(bagScanInput, (val) => {
    if (bagDebounce) clearTimeout(bagDebounce)
    if (!val?.trim()) return
    bagDebounce = setTimeout(() => { onBagScanSubmit() }, 500)
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

onMounted(() => {
    fetchPlansAndBatches()
    fetchAwaitingBatches()
})
</script>

<template>
  <q-page class="q-pa-sm" style="height: calc(100vh - 56px);">

    <!-- ===== PAGE HEADER ===== -->
    <div class="bg-blue-9 text-white q-pa-sm rounded-borders q-mb-sm shadow-2">
      <div class="row justify-between items-center">
        <div class="row items-center q-gutter-sm">
          <q-icon name="fact_check" size="sm" />
          <div class="text-h6 text-weight-bolder">Check for Production</div>
        </div>
        <div class="row items-center q-gutter-sm">
          <div class="text-caption text-blue-2">{{ t('recheck.subtitle') }}</div>
          <q-btn flat round dense icon="assessment" color="white" @click="showQCReportDialog = true"><q-tooltip>QC Report</q-tooltip></q-btn>
          <q-btn flat round dense icon="volume_up" color="white" @click="showSoundSettings = true"><q-tooltip>{{ t('sound.title') }}</q-tooltip></q-btn>
        </div>
      </div>
    </div>

    <!-- ===== FULL-WIDTH LAYOUT ===== -->
    <div style="height: calc(100% - 60px); display: flex; flex-direction: column; gap: 8px;">

      <!-- ── SCAN PACKING BOX ── -->
      <q-card flat bordered class="shadow-1" style="flex-shrink: 0;">
        <q-card-section class="q-py-xs bg-blue-grey-1 row items-center q-gutter-xs">
          <q-icon name="qr_code" color="blue-9" size="xs" />
          <span class="text-subtitle2 text-weight-bold text-blue-9">{{ t('recheck.scanPackingBox') }}</span>
        </q-card-section>
        <q-card-section class="q-py-xs">
          <div class="row q-col-gutter-xs items-center">
            <div class="col">
              <q-input v-model="boxScanInput" outlined dense :placeholder="t('recheck.scanBoxPlaceholder')" @keyup.enter="onBoxScanSubmit" autofocus bg-color="white" style="font-size: 12px;">
                <template v-slot:prepend><q-icon name="inbox" color="blue-9" size="xs" /></template>
              </q-input>
            </div>
          </div>
        </q-card-section>
      </q-card>

      <!-- ── INFO ROW: Batch-level (visible after batch scan) ── -->
      <div v-if="batchRecheck" class="row items-center q-gutter-sm q-px-xs" style="flex-shrink: 0;">
        <q-badge color="green-8" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="inventory_2" size="14px" class="q-mr-xs" />SKU: {{ batchRecheck.sku_id }}
        </q-badge>
        <q-badge color="teal-7" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="assignment" size="14px" class="q-mr-xs" />Plan: {{ batchRecheck.plan_id }}
        </q-badge>
        <q-badge color="indigo-10" class="q-pa-xs q-px-md shadow-2" style="font-size: 16px; border: 1px solid white;">
          <q-icon name="science" size="18px" class="q-mr-xs" />
          <span class="text-weight-bolder">BATCH: {{ recheckBatchId }}</span>
        </q-badge>
        <q-badge v-if="batchRecheck.box_ids?.length" color="deep-purple-6" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="inbox" size="14px" class="q-mr-xs" />📦 {{ batchRecheck.box_ids.join(', ') }}
        </q-badge>
        <q-badge :color="batchRecheck.fh_boxed_at ? 'green' : 'grey'" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="check_box" size="14px" class="q-mr-xs" />FH {{ batchRecheck.fh_boxed_at ? '✅' : '⏳' }}
        </q-badge>
        <q-badge :color="batchRecheck.spp_boxed_at ? 'green' : 'grey'" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="check_box" size="14px" class="q-mr-xs" />SPP {{ batchRecheck.spp_boxed_at ? '✅' : '⏳' }}
        </q-badge>
        <q-space />
        <q-badge :color="allRecheckVerified ? 'green' : 'orange'" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon :name="allRecheckVerified ? 'verified' : 'hourglass_top'" size="14px" class="q-mr-xs" />
          ✅ {{ batchRecheck.summary.checked }} / {{ batchRecheck.summary.total }}
          <template v-if="batchRecheck.summary.errors > 0"> · ❌ {{ batchRecheck.summary.errors }}</template>
        </q-badge>
      </div>
 
      <!-- ── DEDICATED BAG SCAN (Next Step) ── -->
      <div v-if="batchRecheck" class="q-px-xs" style="flex-shrink: 0;">
        <q-card flat bordered :class="'shadow-2 ' + (lastScanResult === 'success' && flashActive ? 'bg-green-1' : (lastScanResult === 'error' && flashActive ? 'bg-red-1' : 'bg-white'))" style="border: 2px solid #ccc; border-radius: 12px; transition: background 0.3s;">
          <q-card-section class="q-pa-sm">
            <div class="row items-center q-gutter-md">
              <div class="col" style="position: relative;">
                <q-input 
                  v-model="bagScanInput" 
                  ref="bagScanRef"
                  outlined 
                  placeholder="SCAN NEXT BAG..." 
                  @keyup.enter="onBagScanSubmit"
                  style="font-size: 16px;"
                >
                  <template v-slot:prepend>
                    <q-icon name="qr_code_scanner" :color="lastScanResult === 'success' ? 'green' : (lastScanResult === 'error' ? 'red' : 'primary')" size="md" />
                  </template>
                  <template v-slot:append>
                    <!-- "Green Spot" indicator -->
                    <div v-if="lastScanResult !== 'none'" 
                      :class="['status-spot', `bg-${lastScanResult === 'success' ? 'green' : 'red'}`, flashActive ? 'flash-active' : '']"
                    >
                      <q-icon :name="lastScanResult === 'success' ? 'check' : 'close'" color="white" size="20px" />
                    </div>
                  </template>
                </q-input>
              </div>
              <div class="col-auto">
                <div class="text-subtitle1 text-grey-8 text-weight-bold">
                   {{ lastScanResult === 'success' ? 'OK! SCAN NEXT...' : (lastScanResult === 'error' ? 'ERROR! CHECK AGAIN' : 'WAIT FOR SCAN...') }}
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- ===== UNIFIED 3-PANE LAYOUT ===== -->
      <q-card flat bordered class="shadow-1" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
        <div class="row" style="flex: 1; overflow: hidden;">

          <!-- ═══ LEFT PANE: Production Plan Tree ═══ -->
          <div class="col-4" style="height: 100%; overflow: auto; border-right: 1px solid #e0e0e0;">
            <div class="q-pa-xs bg-indigo-1 text-indigo-9 text-weight-bold row items-center q-gutter-xs" style="font-size: 12px; position: sticky; top: 0; z-index: 2;">
              <q-icon name="account_tree" size="xs" />
              <span>📋 Production Plans</span>
              <q-space />
              <q-btn flat round dense icon="refresh" size="xs" color="indigo-9" @click="fetchPlansAndBatches(); fetchAwaitingBatches()" />
            </div>
            <div class="q-pa-xs row q-gutter-x-sm" style="position: sticky; top: 28px; z-index: 1; background: white; border-bottom: 1px solid #e0e0e0;">
              <q-select v-model="selectedPlantFilter" :options="availablePlantOptions" dense outlined bg-color="white" style="font-size: 12px; flex: 1;" label="Filter Plant" options-dense />
              <q-input v-model="treeSearch" outlined dense placeholder="Search plan / batch..." bg-color="white" style="font-size: 12px; flex: 1;" clearable>
                <template v-slot:prepend><q-icon name="search" size="xs" /></template>
              </q-input>
            </div>

            <q-list dense class="q-pt-none">
              <template v-for="plant in plantGroups" :key="plant.plantId">
                <q-expansion-item dense dense-toggle switch-toggle-side default-opened header-class="q-py-none bg-blue-grey-1" header-style="padding-left: 4px;" style="font-size: 12px;">
                  <template v-slot:header>
                    <q-item-section avatar style="min-width: 24px;"><q-icon name="factory" size="16px" color="blue-grey-7" /></q-item-section>
                    <q-item-section><q-item-label class="text-weight-bold text-blue-grey-9">{{ plant.plantName }}</q-item-label></q-item-section>
                    <q-item-section side><q-badge color="blue-grey-6">{{ plant.skus.length }}-SKU</q-badge></q-item-section>
                  </template>

                  <!-- SKU Level -->
                  <template v-for="sku in plant.skus" :key="sku.skuId">
                    <q-expansion-item dense dense-toggle switch-toggle-side header-class="q-py-none bg-grey-1" header-style="padding-left: 24px;" style="font-size: 12px;">
                      <template v-slot:header>
                        <q-item-section avatar style="min-width: 20px;"><q-icon name="inventory_2" size="14px" color="indigo-7" /></q-item-section>
                        <q-item-section><q-item-label class="text-weight-bold text-indigo-9 ellipsis">{{ sku.skuId }} · {{ sku.skuName }}</q-item-label></q-item-section>
                        <q-item-section side><q-badge color="indigo-5" outline>{{ sku.plans.length }}-Plan</q-badge></q-item-section>
                      </template>

                      <!-- Plan Level -->
                      <template v-for="plan in sku.plans" :key="plan.plan_id">
                        <q-expansion-item dense dense-toggle switch-toggle-side :default-opened="selectedPlanId === plan.plan_id" header-class="q-py-none" header-style="padding-left: 44px;" style="font-size: 12px;">
                          <template v-slot:header>
                            <q-item-section avatar style="min-width: 20px;"><q-icon name="assignment" size="14px" color="teal-7" /></q-item-section>
                            <q-item-section><q-item-label class="text-weight-bold text-teal-9">{{ plan.plan_id }}</q-item-label></q-item-section>
                            <q-item-section side><q-badge color="teal-3" text-color="teal-10">{{ (plan.batches || []).length }} Batch</q-badge></q-item-section>
                          </template>

                          <!-- Batch Level -->
                          <q-list dense>
                            <q-item v-for="batch in (plan.batches || [])" :key="batch.batch_id" clickable dense
                              :active="recheckBatchId === batch.batch_id || boxId === batch.batch_id || selectedBatchId === batch.batch_id"
                              active-class="bg-blue-1" @click="boxScanInput = batch.batch_id; selectBatchFromTree(batch); onBoxScanSubmit()"
                              style="min-height: 28px; padding-left: 64px;">
                              <q-item-section avatar style="min-width: 18px;"><q-icon name="science" size="12px" color="indigo" /></q-item-section>
                              <q-item-section><q-item-label class="text-weight-bold ellipsis">{{ batch.batch_id }} · {{ (batch.batch_size || 0).toFixed(1) }}kg</q-item-label></q-item-section>
                              <q-item-section side>
                                <div class="row q-gutter-xs">
                                  <q-badge :color="getTreeBatchFH(batch) ? 'green' : 'grey-4'" style="font-size: 10px; padding: 1px 3px;">FH</q-badge>
                                  <q-badge :color="getTreeBatchSPP(batch) ? 'green' : 'grey-4'" style="font-size: 10px; padding: 1px 3px;">SPP</q-badge>
                                </div>
                              </q-item-section>
                            </q-item>
                          </q-list>
                        </q-expansion-item>
                      </template>
                    </q-expansion-item>
                  </template>
                </q-expansion-item>
              </template>

              <div v-if="plantGroups.length === 0" class="text-center q-pa-md text-grey-5">
                <q-icon name="inbox" size="30px" /><br>
                <span class="text-caption">No plans found</span>
              </div>
            </q-list>
          </div>

          <!-- ═══ RIGHT PANE (Expanded): Detail List ═══ -->
          <div class="col-8" style="height: 100%; overflow: auto; border-right: 1px solid #e0e0e0;">

            <!-- When batch is selected -->
            <template v-if="selectedBatchInfo">
              <!-- Plan + SKU Header -->
              <div class="q-pa-sm bg-teal-1 text-teal-9 text-weight-bold row items-center" style="font-size: 12px; position: sticky; top: 0; z-index: 1;">
                <q-icon name="assignment" size="18px" class="q-mr-xs" />
                <span>{{ selectedBatchInfo.plan_id }} · {{ selectedBatchInfo.sku_name }}</span>
                <q-space />
                <q-btn v-if="selectedBatchId" :disable="!canStartProduction" dense push color="deep-purple-9" text-color="white" icon="rocket_launch" label="Start Production" @click="goToStartProduction" class="q-mr-sm text-weight-bold" style="font-size: 12px; padding: 2px 8px;">
                  <q-tooltip v-if="!canStartProduction">Check all ingredients first</q-tooltip>
                </q-btn>
                <div v-if="canStartProduction" class="row items-center q-mr-md bg-green-2 text-green-10 q-px-sm rounded-borders text-weight-bolder shadow-1 pulse-ready">
                   <q-icon name="check_circle" class="q-mr-xs" /> READY FOR PRODUCTION
                </div>
                <q-btn dense flat color="teal-9" icon="visibility" label="Check for Production Detail" @click="openSkuDetail" class="q-mr-sm" style="font-size: 12px;" />
                <q-badge :color="selectedBatchInfo.fh_boxed ? 'green' : 'grey-4'" class="q-mr-xs" style="font-size: 12px;">FH</q-badge>
                <q-badge :color="selectedBatchInfo.spp_boxed ? 'green' : 'grey-4'" style="font-size: 12px;">SPP</q-badge>
              </div>

              <!-- Batch Info -->
              <div class="q-pa-sm bg-blue-grey-1 row items-center" style="font-size: 12px; border-bottom: 1px solid #e0e0e0;">
                <q-icon name="science" size="16px" color="indigo" class="q-mr-xs" />
                <span class="text-weight-bold">{{ selectedBatchInfo.batch_id }}</span>
                <q-space />
                <span class="text-grey-7">{{ (selectedBatchInfo.batch_size || 0).toFixed(1) }} kg</span>
                <q-badge :color="selectedBatchInfo.status === 'Done' ? 'green' : (selectedBatchInfo.status === 'Cancelled' ? 'red' : 'blue')" class="q-ml-sm" style="font-size: 12px;">{{ selectedBatchInfo.status || '-' }}</q-badge>
              </div>

              <!-- ── BATCH VERIFICATION PLATE ── -->
              <div class="q-px-sm q-pt-sm">
                <div class="row q-col-gutter-sm">
                  <div class="col-4" v-for="wh in ['MIX', 'FH', 'SPP']" :key="'plate-'+wh">
                    <q-card flat bordered :class="['plate-card', getWhStatus(wh) === 1 ? 'bg-green-1' : 'bg-white']">
                      <div class="column items-center q-pa-xs">
                        <div class="text-overline text-weight-bolder" style="font-size: 10px; line-height: 1;">{{ wh }} STATUS</div>
                        <div class="row items-center q-gutter-x-xs">
                          <q-icon :name="getWhStatus(wh) === 1 ? 'check_circle' : 'hourglass_bottom'" :color="getWhStatus(wh) === 1 ? 'green' : 'orange'" size="xs" />
                          <div class="text-weight-bolder" style="font-size: 14px;">{{ getWhCheckCount(wh) }} / {{ getWhTotalCount(wh) }}</div>
                        </div>
                        <q-linear-progress :value="getWhTotalCount(wh) ? getWhCheckCount(wh)/getWhTotalCount(wh) : 0" :color="getWhStatus(wh) === 1 ? 'green' : 'orange'" style="height: 4px; border-radius: 2px; margin-top: 2px;" />
                      </div>
                    </q-card>
                  </div>
                </div>
              </div>

              <!-- PreBatch Items Grouped By Warehouse -->
              <div v-for="group in prebatchByWarehouse" :key="group.warehouse" class="q-mt-sm">
                <q-expansion-item
                  dense
                  dense-toggle
                  switch-toggle-side
                  default-opened
                  :icon="group.warehouse === 'FH' || group.warehouse === 'FLAVOUR HOUSE' ? 'science' : 'blender'"
                  :label="`🧪 ${group.warehouse} (${group.ingredients.length})`"
                  header-class="q-pa-xs bg-blue-1 text-blue-9 text-weight-bold"
                  style="border: 1px solid #bbdefb; border-radius: 4px; font-size: 12px;"
                >
                  <q-list dense class="bg-white">
                    <q-expansion-item
                      v-for="ing in group.ingredients" :key="ing.re_code"
                      dense dense-toggle switch-toggle-side
                      header-class="bg-grey-1"
                      style="border-top: 1px solid #e0e0e0; font-size: 12px;"
                    >
                      <template v-slot:header>
                        <q-item-section>
                          <div class="row full-width items-center q-pr-sm">
                            <span class="text-weight-bold" style="flex: 1; min-width: 60px; color: #1565c0;">{{ ing.re_code }}</span>
                            <span style="width: 60px;"></span>
                            <span class="text-right text-weight-bold" style="width: 60px;">{{ ing.total_volume.toFixed(3) }}</span>
                            <div class="row items-center justify-end" style="width: 100px;">
                              <template v-if="group.warehouse !== 'MIX'">
                                <q-badge :color="ing.recheck_status === 1 ? 'green' : (ing.recheck_status === 2 ? 'red' : 'grey')" class="q-mr-xs" style="font-size: 10px; width: 35px; justify-content: center;">
                                    {{ ing.recheck_status === 1 ? 'OK' : 'WAIT' }}
                                </q-badge>
                                <q-icon :name="ing.recheck_status === 1 ? 'check_circle' : (ing.recheck_status === 2 ? 'error' : 'radio_button_unchecked')"
                                  :color="ing.recheck_status === 1 ? 'green' : (ing.recheck_status === 2 ? 'red' : 'grey')" size="16px" class="q-mr-xs" />
                                <q-btn flat round dense icon="qr_code_scanner" size="xs" color="blue-9" @click.stop="quickCheckIngredient(ing)" style="width: 24px;" />
                              </template>
                            </div>
                          </div>
                        </q-item-section>
                      </template>
                      
                      <!-- Individual Bags -->
                      <div style="background: #f8fdff; border-top: 1px solid #e0e0e0; font-size: 11px;">
                        <div v-for="(pb, index) in ing.items" :key="'pb-' + index" 
                          class="row full-width items-center q-py-xs q-pr-sm"
                          :class="{ 'bg-green-1': pb.recheck_status === 1, 'bg-red-1': pb.recheck_status === 2 }"
                          style="border-bottom: 1px solid #f0f0f0;">
                          <span class="text-weight-medium text-grey-8 ellipsis" style="flex: 1; min-width: 60px; padding-left: 48px; font-size: 10px;" 
                            :title="`${selectedBatchInfo.batch_id}-${pb.re_code}-${pb.package_no || (index + 1)}/${pb.total_packages || ing.items.length}`">
                            {{ selectedBatchInfo.batch_id }}-{{ pb.re_code }}-{{ pb.package_no || (index + 1) }}/{{ pb.total_packages || ing.items.length }}
                          </span>
                          <span class="text-grey-7" style="width: 60px;">{{ pb.package_no || (index + 1) }}/{{ pb.total_packages || ing.items.length }}</span>
                          <span class="text-right text-weight-medium text-grey-8" style="width: 60px;">{{ (pb.required_volume || 0).toFixed(3) }}</span>
                          <div class="row justify-end items-center" style="width: 100px;">
                            <template v-if="group.warehouse !== 'MIX'">
                              <q-badge :color="pb.status >= 2 ? 'green' : (pb.status === 1 ? 'orange' : 'grey')" class="q-mr-xs" style="font-size: 10px; width: 35px; justify-content: center;">
                                {{ pb.status >= 2 ? 'OK' : (pb.status === 1 ? 'Prep' : 'Wait') }}
                              </q-badge>
                              <q-icon :name="pb.recheck_status === 1 ? 'check_circle' : (pb.recheck_status === 2 ? 'error' : 'radio_button_unchecked')"
                                :color="pb.recheck_status === 1 ? 'green' : (pb.recheck_status === 2 ? 'red' : 'grey')" size="16px" class="q-mr-xs" />
                              <div style="width: 24px;"></div>
                            </template>
                          </div>
                        </div>
                      </div>
                    </q-expansion-item>
                  </q-list>
                </q-expansion-item>
              </div>
              <div v-if="prebatchByWarehouse.length === 0" class="text-center q-pa-sm text-grey-5" style="font-size: 12px;">No pre-batch items</div>

              <!-- SKU Steps Detail - Grouped by Phase -->
              <div style="margin: 4px;">
                <div class="q-pa-xs bg-deep-purple-1 text-deep-purple-9 text-weight-bold row items-center" style="font-size: 12px; border-radius: 4px 4px 0 0; border: 1px solid #d1c4e9;">
                  <q-icon name="list_alt" size="16px" class="q-mr-xs" />
                  <span>SKU Production Steps ({{ skuSteps.length }})</span>
                </div>
                <q-linear-progress v-if="skuStepsLoading" indeterminate color="deep-purple" />
                <template v-if="skuStepsByPhase.length > 0">
                  <q-expansion-item
                    v-for="(group, gi) in skuStepsByPhase" :key="group.phase"
                    dense dense-toggle switch-toggle-side default-opened
                    :header-class="'q-pa-xs text-weight-bold ' + (gi % 2 === 0 ? 'bg-blue-1 text-blue-9' : 'bg-grey-2 text-grey-9')"
                    style="border: 1px solid #e0e0e0; border-top: none; font-size: 12px;"
                  >
                    <template v-slot:header>
                      <q-item-section avatar style="min-width: 20px;"><q-icon name="settings" size="14px" /></q-item-section>
                      <q-item-section><q-item-label>Phase {{ group.phase }} · {{ group.phase_id }}</q-item-label></q-item-section>
                      <q-item-section side><q-badge :color="gi % 2 === 0 ? 'blue' : 'grey'" outline>{{ group.steps.length }} steps</q-badge></q-item-section>
                    </template>

                    <q-markup-table flat dense separator="cell" style="font-size: 11px;">
                      <thead :class="gi % 2 === 0 ? 'bg-blue-1' : 'bg-grey-3'">
                        <tr>
                          <th class="text-left" style="width: 35px;">Step</th>
                          <th class="text-left" style="width: 50px;">Action</th>
                          <th class="text-left">Description</th>
                          <th class="text-left">Ingredient</th>
                          <th class="text-right" style="width: 55px;">Qty</th>
                          <th class="text-center" style="width: 35px;">UOM</th>
                          <th class="text-center" style="width: 40px;">Time</th>
                          <th class="text-center" style="width: 40px;">Temp</th>
                          <th class="text-center" style="width: 40px;">RPM</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="step in group.steps" :key="step.id || step.sub_step" style="border-bottom: 1px solid #f0f0f0;">
                          <td>{{ step.sub_step || '-' }}</td>
                          <td class="text-grey-8">{{ step.action_code || '-' }}</td>
                          <td style="max-width: 160px; white-space: normal; line-height: 1.3;">
                            <span class="text-weight-medium">{{ step.action_description || '-' }}</span>
                          </td>
                          <td style="max-width: 160px; white-space: normal; line-height: 1.3;">
                            <span class="text-blue-9 text-weight-bold">{{ step.re_code || '-' }}</span>
                          </td>
                          <td class="text-right text-weight-bold">{{ step.require ? step.require.toFixed(2) : '-' }}</td>
                          <td class="text-center text-grey-7">{{ step.uom || '-' }}</td>
                          <td class="text-center">{{ step.step_time || '-' }}</td>
                          <td class="text-center">{{ step.temperature || '-' }}</td>
                          <td class="text-center">{{ step.agitator_rpm || '-' }}</td>
                        </tr>
                      </tbody>
                    </q-markup-table>
                  </q-expansion-item>
                </template>
                <div v-else-if="!skuStepsLoading" class="text-center q-pa-sm text-grey-5" style="font-size: 11px; border: 1px solid #e0e0e0; border-top: none;">No SKU steps found</div>
              </div>
            </template>

            <!-- No batch selected -->
            <template v-else>
              <div class="q-pa-xs bg-amber-1 text-amber-9 text-weight-bold row items-center q-gutter-xs" style="font-size: 12px; position: sticky; top: 0; z-index: 1;">
                <q-icon name="pending_actions" size="xs" />
                <span>📋 Awaiting Re-Check ({{ awaitingBatches.length }})</span>
                <q-space />
                <q-btn flat round dense icon="refresh" size="xs" color="amber-9" @click="fetchAwaitingBatches" />
              </div>
              <q-markup-table v-if="awaitingBatches.length > 0" flat dense separator="cell" style="font-size: 12px;">
                <thead class="bg-amber-1"><tr>
                  <th class="text-left">Batch</th>
                  <th class="text-left">SKU</th>
                  <th class="text-center">FH</th>
                  <th class="text-center">SPP</th>
                </tr></thead>
                <tbody>
                  <tr v-for="b in awaitingBatches" :key="b.batch_id"
                    class="cursor-pointer" style="transition: background .15s;"
                    @mouseover="($event.currentTarget as HTMLElement).style.background='#fff3e0'"
                    @mouseout="($event.currentTarget as HTMLElement).style.background=''"
                    @click="boxScanInput = b.batch_id; selectedBatchId = b.batch_id; onBoxScanSubmit()">
                    <td class="text-weight-bold text-blue-9">{{ b.batch_id }}</td>
                    <td style="max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ b.sku_id }}</td>
                    <td class="text-center"><q-icon :name="b.fh_boxed ? 'check_circle' : 'cancel'" :color="b.fh_boxed ? 'green' : 'grey-4'" size="16px" /></td>
                    <td class="text-center"><q-icon :name="b.spp_boxed ? 'check_circle' : 'cancel'" :color="b.spp_boxed ? 'green' : 'grey-4'" size="16px" /></td>
                  </tr>
                </tbody>
              </q-markup-table>
              <div v-else class="text-center q-pa-lg text-grey-5 column items-center">
                <q-icon name="check_circle" size="30px" color="green-3" /><br>
                <span class="text-caption">No batches awaiting re-check</span>
                
                <q-btn v-if="selectedBatchId" color="deep-purple-9" icon="rocket_launch" label="FORCE START PRODUCTION (BYPASS)" @click="goToStartProduction" size="lg" class="q-mt-xl text-weight-bold shadow-4" />
              </div>
            </template>
          </div>

        </div>

        <!-- Release to Production footer -->
        <q-card-section v-if="activeBatchForProduction" class="bg-green-1 q-py-sm text-center" style="flex-shrink: 0; border-top: 2px solid #4caf50;">
          <div class="row items-center justify-center q-gutter-sm">
            <q-icon name="verified" size="24px" color="green" />
            <span class="text-subtitle2 text-green-9 text-weight-bold">Assumed all items verified! Ready to release.</span>
            <q-btn color="positive" size="md" label="Release to Production" icon="rocket_launch" unelevated class="text-weight-bold q-ml-md" @click="releaseBatch" :loading="loading" />
          </div>
        </q-card-section>
      </q-card>
    </div>

    <!-- ===== SKU DETAIL DIALOG (Maximized Page View) ===== -->
    <q-dialog v-model="showSkuDetail" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card class="column bg-grey-1" style="width: 100vw; max-width: 100vw; height: 100vh; max-height: 100vh;">
        <q-card-section class="bg-teal text-white row items-center q-pb-sm" style="flex-shrink: 0;">
          <div class="text-h6">SKU Detail <span v-if="selectedBatchInfo" style="font-size: 14px; margin-left: 8px;">{{ selectedBatchInfo.sku_name }}</span></div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-card-section class="q-pt-sm col" style="overflow-y: auto;">
          <q-inner-loading :showing="skuStepsLoading" />
          <div v-if="skuStepsByPhase.length === 0 && !skuStepsLoading" class="text-center text-grey q-pa-md">
            No details available for this SKU
          </div>
          
          <q-markup-table v-if="skuStepsByPhase.length > 0" flat bordered dense separator="cell" style="font-size: 13px;" class="full-width">
            <thead class="bg-grey-3 text-grey-9">
              <tr>
                <th class="text-center text-weight-bold" style="width: 80px;">Process</th>
                <th class="text-center text-weight-bold" style="width: 60px;">Step</th>
                <th class="text-left text-weight-bold" style="width: 110px;">Action Code</th>
                <th class="text-left text-weight-bold">Action</th>
                <th class="text-left text-weight-bold">RE Code</th>
                <th class="text-right text-weight-bold">Require</th>
                <th class="text-left text-weight-bold">Dest</th>
                <th class="text-right text-weight-bold">Temp</th>
                <th class="text-right text-weight-bold">Agitator</th>
                <th class="text-right text-weight-bold">High Shear</th>
                <th class="text-right text-weight-bold">Brix</th>
                <th class="text-right text-weight-bold">pH</th>
                <th class="text-right text-weight-bold">Time</th>
                <th class="text-center text-weight-bold" style="width: 90px;">Stamp Time</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="phaseGroup in skuStepsByPhase" :key="phaseGroup.phase">
                <tr class="bg-teal-1 cursor-pointer" @click="togglePhase(phaseGroup.phase)">
                  <td colspan="14" class="text-weight-bold text-teal-10" style="padding: 6px 12px; font-size: 13px; user-select: none;">
                    <q-icon :name="isPhaseExpanded(phaseGroup.phase) ? 'expand_more' : 'chevron_right'" size="18px" class="q-mr-xs" />
                    Process Phase {{ phaseGroup.phase }}
                  </td>
                </tr>
                <tr v-show="isPhaseExpanded(phaseGroup.phase)" v-for="step in phaseGroup.steps" :key="step.id">
                  <td class="text-center text-grey-6">{{ phaseGroup.phase }}</td>
                  <td class="text-center text-weight-bold" style="color: #424242;">{{ step.sub_step }}</td>
                  <td class="text-weight-bold">{{ step.action_code || '-' }}</td>
                  <td>{{ step.action_description || step.action || '-' }}</td>
                  <td class="text-weight-bold text-indigo">{{ step.re_code || '-' }}</td>
                  <td class="text-right">{{ step.require ? step.require.toFixed(3) : '-' }}</td>
                  <td>{{ step.destination || '-' }}</td>
                  <td class="text-right">{{ step.temperature ? `${step.temperature}°C` : '-' }}</td>
                  <td class="text-right text-teal-8">{{ step.agitator_rpm ? `${step.agitator_rpm} RPM` : '-' }}</td>
                  <td class="text-right text-purple-8">{{ step.high_shear_rpm ? `${step.high_shear_rpm} RPM` : '-' }}</td>
                  <td class="text-right text-deep-orange-8">{{ step.brix_sp || '-' }}</td>
                  <td class="text-right text-purple-8">{{ step.ph_sp || '-' }}</td>
                  <td class="text-right">{{ step.step_time ? `${step.step_time}m` : '-' }}</td>
                  <td class="text-center">{{ step.stamp_time || '-' }}</td>
                </tr>
              </template>
            </tbody>
          </q-markup-table>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- ===== SOUND SETTINGS DIALOG ===== -->
    <q-dialog v-model="showSoundSettings">
      <q-card style="min-width: 420px" class="bg-grey-9 text-white">
        <q-bar class="bg-blue-9">
          <q-icon name="volume_up" />
          <div class="text-weight-bold q-ml-sm">{{ t('sound.title') }}</div>
          <q-space />
          <q-btn dense flat icon="close" v-close-popup />
        </q-bar>

        <q-card-section>
          <div class="text-overline text-green-4 q-mb-sm">✅ {{ t('sound.correctScan') }}</div>
          <q-list dark dense separator class="rounded-borders" style="background: rgba(255,255,255,0.05)">
            <q-item
              v-for="opt in successSoundOptions"
              :key="opt.value"
              tag="label"
              class="q-py-sm"
            >
              <q-item-section side>
                <q-radio v-model="successSoundPreset" :val="opt.value" color="green" dark />
              </q-item-section>
              <q-item-section>
                <q-item-label class="text-white">{{ t(opt.labelKey) }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round dense icon="play_arrow" color="green" @click.stop="playSoundPreset(opt.value)">
                  <q-tooltip>{{ t('sound.preview') }}</q-tooltip>
                </q-btn>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <q-separator dark />

        <q-card-section>
          <div class="text-overline text-red-4 q-mb-sm">❌ {{ t('sound.wrongScan') }}</div>
          <q-list dark dense separator class="rounded-borders" style="background: rgba(255,255,255,0.05)">
            <q-item
              v-for="opt in errorSoundOptions"
              :key="opt.value"
              tag="label"
              class="q-py-sm"
            >
              <q-item-section side>
                <q-radio v-model="errorSoundPreset" :val="opt.value" color="red" dark />
              </q-item-section>
              <q-item-section>
                <q-item-label class="text-white">{{ t(opt.labelKey) }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round dense icon="play_arrow" color="red" @click.stop="playSoundPreset(opt.value)">
                  <q-tooltip>{{ t('sound.preview') }}</q-tooltip>
                </q-btn>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat :label="t('common.cancel')" color="grey" v-close-popup />
          <q-btn unelevated :label="t('common.save')" color="blue-9" icon="save" @click="saveSoundSettings" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ===== FEEDBACK BANNER ===== -->
    <q-dialog v-model="feedback.show" position="top" seamless>
      <q-card class="feedback-card" :class="`feedback-${feedback.type}`">
        <q-card-section class="row items-center no-wrap q-pa-md">
          <q-icon
            :name="feedback.type === 'success' ? 'check_circle' : (feedback.type === 'warning' ? 'warning' : 'error')"
            size="36px" class="q-mr-md"
          />
          <div>
            <div class="text-subtitle1 text-weight-bold">{{ feedback.title }}</div>
            <div class="text-body2">{{ feedback.message }}</div>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- ===== WRONG BOX FULL-SCREEN ALERT ===== -->
    <Teleport to="body">
      <div v-if="wrongBoxAlert.show" class="wrong-box-overlay" @click="wrongBoxAlert.show = false">
        <div class="wrong-box-content">
          <q-icon name="gpp_bad" size="120px" color="white" />
          <div class="wrong-box-title">{{ t('wrongBox.title') }}</div>
          <div class="wrong-box-title-thai">{{ t('wrongBox.titleThai') }}</div>
          <div class="wrong-box-subtitle">{{ t('wrongBox.subtitle') }}</div>
          <div class="wrong-box-detail">
            {{ t('wrongBox.bag') }}: <strong>{{ wrongBoxAlert.bagCode }}</strong>
          </div>
          <div class="wrong-box-detail">
            {{ t('wrongBox.currentBox') }}: <strong>{{ wrongBoxAlert.expectedBox }}</strong>
          </div>
          <div class="wrong-box-instruction">{{ t('wrongBox.removeImmediately') }}</div>
        </div>
      </div>
    </Teleport>

    <!-- QC Report Dialog -->
    <q-dialog v-model="showQCReportDialog">
      <q-card style="min-width: 400px;">
        <q-card-section class="bg-primary text-white">
          <div class="text-h6"><q-icon name="assessment" class="q-mr-sm" />Quality Check Report</div>
          <div class="text-caption">Select date range for the report</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="qcReportFromDate" label="From Date" filled mask="##/##/####" fill-mask>
            <template #append><q-icon name="event" class="cursor-pointer"><q-popup-proxy cover><q-date v-model="qcReportFromDate" mask="DD/MM/YYYY" /></q-popup-proxy></q-icon></template>
          </q-input>
          <q-input v-model="qcReportToDate" label="To Date" filled mask="##/##/####" fill-mask>
            <template #append><q-icon name="event" class="cursor-pointer"><q-popup-proxy cover><q-date v-model="qcReportToDate" mask="DD/MM/YYYY" /></q-popup-proxy></q-icon></template>
          </q-input>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" icon="print" label="Generate Report" :loading="qcReportLoading" @click="printQCReport" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<style scoped>
/* Label previews in simulator */
.label-preview {
  background: white;
  border-radius: 6px;
  padding: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
  border: 1px solid #e0e0e0;
}

.status-spot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  transition: all 0.3s;
}

.flash-active {
  transform: scale(1.4);
  box-shadow: 0 0 20px currentColor;
  animation: spotPulse 0.4s ease-in-out infinite alternate;
}

@keyframes spotPulse {
  from { transform: scale(1.2); opacity: 0.8; }
  to { transform: scale(1.5); opacity: 1; }
}

.hover-highlight {
  padding: 6px;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  position: relative;
}
.hover-highlight:hover {
  border-color: #1565c0;
  box-shadow: 0 2px 12px rgba(21, 101, 192, 0.25);
  transform: scale(1.02);
}
.label-preview :deep(svg) {
  width: 100%;
  height: auto;
}
.box-label-preview {
  max-width: 380px;
}
.bag-label-scanned {
  border-color: #4caf50 !important;
  opacity: 0.55;
}
.scanned-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
}

/* Feedback banner */
.feedback-card {
  min-width: 400px;
  border-radius: 0 0 10px 10px;
  color: white;
}
.feedback-success { background: #2e7d32; }
.feedback-error   { background: #c62828; }
.feedback-warning { background: #e65100; }

/* Release button pulse */
.pulse-btn {
  animation: pulse-glow 1.5s infinite;
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 6px rgba(56, 142, 60, 0.4); }
  50%       { box-shadow: 0 0 18px rgba(56, 142, 60, 0.8); }
}

/* Wrong Bag label in simulator */
.wrong-bag-preview {
  border: 2px dashed #e53935 !important;
  position: relative;
  opacity: 0.85;
}
.wrong-bag-preview:hover {
  border-color: #ff1744 !important;
  box-shadow: 0 2px 16px rgba(229, 57, 53, 0.4);
  transform: scale(1.02);
  opacity: 1;
}
.wrong-bag-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #e53935;
  color: white;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* WRONG BOX full-screen overlay */
.wrong-box-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: wrongBoxFlash 0.4s ease-in-out infinite alternate;
  cursor: pointer;
}
@keyframes wrongBoxFlash {
  0%   { background: rgba(198, 40, 40, 0.92); }
  100% { background: rgba(255, 23, 68, 0.97); }
}
.wrong-box-content {
  text-align: center;
  color: white;
  animation: wrongBoxShake 0.15s ease-in-out infinite alternate;
}
@keyframes wrongBoxShake {
  0%   { transform: translateX(-4px); }
  100% { transform: translateX(4px); }
}
.wrong-box-title {
  font-size: 64px;
  font-weight: 900;
  letter-spacing: 4px;
  text-shadow: 0 4px 20px rgba(0,0,0,0.5);
  margin-top: 12px;
}
.wrong-box-title-thai {
  font-size: 48px;
  font-weight: 800;
  text-shadow: 0 4px 20px rgba(0,0,0,0.5);
  margin-top: 4px;
}
.wrong-box-subtitle {
  font-size: 24px;
  font-weight: 500;
  opacity: 0.9;
  margin-top: 8px;
}
.wrong-box-detail {
  font-size: 18px;
  margin-top: 8px;
  opacity: 0.85;
}
.wrong-box-instruction {
  font-size: 28px;
  font-weight: 800;
  margin-top: 24px;
  padding: 12px 32px;
  background: rgba(255,255,255,0.15);
  border-radius: 8px;
  border: 2px solid rgba(255,255,255,0.4);
  animation: pulseInstruction 0.8s ease-in-out infinite alternate;
}
@keyframes pulseInstruction {
  0%   { transform: scale(1); }
  100% { transform: scale(1.05); }
}

.pulse-ready {
  animation: pulse-ready-anim 1.5s ease-in-out infinite;
}
@keyframes pulse-ready-anim {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.03); opacity: 0.95; }
}
</style>

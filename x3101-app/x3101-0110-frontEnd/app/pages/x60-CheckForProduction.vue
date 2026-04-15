<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useLabelPrinter } from '../composables/useLabelPrinter'

const $q = useQuasar()
const { getAuthHeader, user } = useAuth()
const { generateLabelSvg, printLabel } = useLabelPrinter()
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

// Scanner Simulator Dialog
const showScannerDialog = ref(false)
const scannerMode = ref<'box' | 'bag'>('box')
const scannerLoading = ref(false)

// All available batches for the simulator
const allBatches = ref<any[]>([])
const allPlans = ref<any[]>([])

// Label preview in simulator
const previewLabelSvg = ref('')
const previewBagLabels = ref<{svg: string, batch_record_id: string, re_code: string}[]>([])
const selectedSimBatch = ref<any>(null)

// Bags from OTHER batches (for wrong-box simulation)
const otherBatchBagLabels = ref<{svg: string, batch_record_id: string, re_code: string, source_batch: string}[]>([])

// ── Tree navigation state (Left Pane) ──
const selectedSku = ref<string | null>(null)
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

const selectedPlanBatches = computed(() => {
    if (!selectedPlanId.value) return []
    const plan = planTree.value.find((p: any) => p.plan_id === selectedPlanId.value)
    return plan?.batches || []
})

const selectBatchFromTree = (batch: any) => {
    selectedBatchId.value = batch.batch_id
    selectedPlanId.value = batch.plan_id || ''
    fetchBatchPreBatchData(batch.batch_id)
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

// Packed items grouped by re_code
const packedByIngredient = computed(() => {
    const map: Record<string, { re_code: string, mat_sap_code: string, count: number, total_vol: number, records: any[] }> = {}
    for (const r of batchPackedRecs.value) {
        const code = r.re_code || '?'
        if (!map[code]) map[code] = { re_code: code, mat_sap_code: r.mat_sap_code || '-', count: 0, total_vol: 0, records: [] }
        map[code].count++
        map[code].total_vol += (r.net_volume || 0)
        map[code].records.push(r)
    }
    return Object.values(map).sort((a, b) => a.re_code.localeCompare(b.re_code))
})

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
const toggleRecStatus = async (rec: any) => {
    const newStatus = rec.recheck_status === 1 ? 0 : 1
    try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-recs/${rec.id}/packing-status`, {
            method: 'PATCH',
            headers: getAuthHeader() as Record<string, string>,
            body: { packing_status: newStatus, packed_by: user.value?.username || 'operator' }
        })
        rec.recheck_status = newStatus
    } catch (e) {
        $q.notify({ type: 'negative', message: 'Failed to update', position: 'top' })
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
            await $fetch<any>(`${appConfig.apiBaseUrl}/edge/start-batch/${selectedBatchId.value}`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>
            })
            useRouter().push(`/x61-MixingControl?batch_id=${selectedBatchId.value}`)
        } catch (e: any) {
            console.error('Edge buffer sync err:', e)
            $q.notify({ type: 'negative', message: 'Failed to sync to Edge Buffer!' })
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

// Info about the currently selected batch (from tree/loaded plan data)
const selectedBatchInfo = computed(() => {
    if (!recheckBatchId.value && !boxId.value) return null
    const bid = recheckBatchId.value || boxId.value
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


const fetchPlansAndBatches = async () => {
    try {
        const resp = await $fetch<any>(`${appConfig.apiBaseUrl}/production-plans/?status=active`, {
            headers: getAuthHeader() as Record<string, string>
        })
        let plans = resp.plans || resp || []
        plans = plans.filter((p: any) => {
            const plantStr = String(p.plant || '').toUpperCase()
            return plantStr.includes('1') || plantStr.includes('2') || plantStr.includes('3') || 
                   String(p.plan_id || '').includes('-01-') || String(p.plan_id || '').includes('-02-') || String(p.plan_id || '').includes('-03-')
        })
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
        } else {
            showFeedback('error', `${response.bag.re_code}: Expected ${response.bag.target}kg, got ${response.bag.actual}kg`, 'WEIGHT MISMATCH')
            playSound('error')
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
    if (!barcode) return

    // Parse QR code format: plan_id,batch_id,TYPE,extra...
    const parts = barcode.split(',')

    if (context === 'box') {
        let candidate = barcode

        if (parts.length >= 3 && parts[2] === 'BOX') {
            // Box QR: plan_id,batch_id,BOX,bag_count,total_vol
            candidate = parts[1]!
        } else if (parts.length >= 4 && parts[2] !== 'BOX') {
            // PreBatch bag QR: plan_id,batch_record_id,prebatch_id,re_code,volume
            // Extract batch_id from batch_record_id (e.g. P260311-02-02-003-FV044A-2 → P260311-02-02-003)
            const batchRecordId = parts[1]!
            const dashParts = batchRecordId.split('-')
            candidate = dashParts.length >= 4 ? dashParts.slice(0, 4).join('-') : batchRecordId
        }

        // Always try batch-level recheck first
        const ok = await fetchBatchRecheck(candidate)
        if (ok) return

        // Fallback: box-level
        fetchBoxDetails(candidate)
    } else {
        // Bag scan
        const bagBarcode = parts.length >= 4 && parts[2] !== 'BOX' ? parts[1]! : barcode

        // Use batch-level verify if we have batch recheck active
        if (batchRecheck.value && recheckBatchId.value) {
            verifyBatchBag(bagBarcode)
            return
        }

        // Fallback: box-level verify
        if (parts.length >= 4 && parts[2] !== 'BOX') {
            verifyBag(parts[1]!)
        } else {
            verifyBag(barcode)
        }
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
        } else {
            showFeedback('error', `${response.bag.re_code}: Expected ${response.bag.target}kg, got ${response.bag.actual}kg (diff: ${response.bag.diff.toFixed(3)}kg)`, 'WEIGHT MISMATCH')
            playSound('error')
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



const printScreen = () => {
    setTimeout(() => {
        window.print()
    }, 100)
}

// --- Scanner Simulator ---

const openScannerSimulator = (mode: 'box' | 'bag') => {
    scannerMode.value = mode
    showScannerDialog.value = true
    if (allBatches.value.length === 0) {
        scannerLoading.value = true
        fetchPlansAndBatches().then(() => { scannerLoading.value = false })
    }
}

const onSimSelectBatch = async (batch: any) => {
    selectedSimBatch.value = batch
    scannerLoading.value = true
    
    try {
        // Fetch all bag records for this batch
        const records = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${batch.batch_id}`, {
            headers: getAuthHeader() as Record<string, string>
        })
        
        // Generate the Box Label
        const summaryMap: Record<string, { re_code: string, weight: number, count: number }> = {}
        records.forEach((r: any) => {
            const code = (r.re_code || '---').trim()
            if (!summaryMap[code]) summaryMap[code] = { re_code: code, weight: 0, count: 0 }
            summaryMap[code].weight += (r.net_volume || 0)
            summaryMap[code].count++
        })
        const sortedSummary = Object.values(summaryMap).sort((a, b) => a.re_code.localeCompare(b.re_code))
        const ingredientsSvg = sortedSummary.map((s, idx) =>
            `<tspan x="25" dy="${idx === 0 ? '0' : '1.2em'}">${s.re_code.padEnd(10)} | ${s.weight.toFixed(3).padStart(8)} kg | ${s.count} packs</tspan>`
        ).join('')
        
        const totalVol = records.reduce((sum: number, r: any) => sum + (r.net_volume || 0), 0)
        
        const boxMapping = {
            BoxID: batch.batch_id,
            BatchID: batch.batch_id,
            BagCount: records.length,
            NetWeight: totalVol.toFixed(3),
            Operator: user.value?.username || 'Operator',
            Timestamp: new Date().toLocaleString('en-GB', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            }),
            BoxQRCode: `${batch.plan_id},${batch.batch_id},BOX,${records.length},${totalVol.toFixed(3)}`,
            prebatch_recs: ingredientsSvg,
            SKU: batch.sku_id,
            PlanID: batch.plan_id,
            WHManifest: '-'
        }
        
        const boxSvg = await generateLabelSvg('packingbox-label', boxMapping as any)
        previewLabelSvg.value = boxSvg || ''
        
        // Shared bag label mapping builder
        const buildBagLabelMapping = (b: any, r: any) => ({
            SKU: b.sku_id || '-',
            PlanId: b.plan_id || '-',
            BatchId: b.batch_id || '-',
            IngredientID: r.re_code || '-',
            Ingredient_ReCode: r.re_code || '-',
            mat_sap_code: r.mat_sap_code || '-',
            PlanStartDate: '-',
            PlanFinishDate: '-',
            PlantId: '-',
            PlantName: '-',
            Timestamp: new Date(r.created_at || Date.now()).toLocaleString('en-GB'),
            PackageSize: (r.net_volume || 0).toFixed(4),
            BatchRequireSize: (r.total_volume || 0).toFixed(4),
            PackageNo: `${r.package_no || 1}/${r.total_packages || 1}`,
            QRCode: `${b.plan_id},${r.batch_record_id},${r.re_code},${r.net_volume}`,
            Lot1: r.origins?.[0] ? `1. ${r.origins[0].intake_lot_id} / ${(r.origins[0].take_volume || 0).toFixed(4)} kg` : (r.intake_lot_id ? `1. ${r.intake_lot_id} / ${Number(r.net_volume).toFixed(4)} kg` : ''),
            Lot2: r.origins?.[1] ? `2. ${r.origins[1].intake_lot_id} / ${(r.origins[1].take_volume || 0).toFixed(4)} kg` : '',
        })

        // Generate individual bag labels
        const bagLabels: {svg: string, batch_record_id: string, re_code: string}[] = []
        for (const record of records) {
            const svg = await generateLabelSvg('prebatch-label', buildBagLabelMapping(batch, record) as any)
            if (svg) {
                bagLabels.push({ svg, batch_record_id: record.batch_record_id, re_code: record.re_code })
            }
        }
        previewBagLabels.value = bagLabels
        
        // Generate bag labels from OTHER batches (for wrong-box simulation)
        const otherLabels: {svg: string, batch_record_id: string, re_code: string, source_batch: string}[] = []
        const otherBatches = allBatches.value.filter(b => b.batch_id !== batch.batch_id).slice(0, 3)
        for (const otherBatch of otherBatches) {
            try {
                const otherRecords = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${otherBatch.batch_id}`, {
                    headers: getAuthHeader() as Record<string, string>
                })
                for (const record of otherRecords.slice(0, 2)) {
                    const svg = await generateLabelSvg('prebatch-label', buildBagLabelMapping(otherBatch, record) as any)
                    if (svg) {
                        otherLabels.push({
                            svg,
                            batch_record_id: record.batch_record_id,
                            re_code: record.re_code,
                            source_batch: otherBatch.batch_id
                        })
                    }
                }
            } catch { /* skip if error */ }
        }
        otherBatchBagLabels.value = otherLabels
    } catch (err: any) {
        console.error('Error generating labels:', err)
        const detail = err?.data?.detail || err?.message || String(err)
        $q.notify({ type: 'negative', message: `Error loading batch labels: ${detail}`, timeout: 5000 })
    } finally {
        scannerLoading.value = false
    }
}

const onClickBoxLabel = () => {
    if (!selectedSimBatch.value) return
    const batch = selectedSimBatch.value
    const records = previewBagLabels.value
    const totalVol = 0
    const qrData = `${batch.plan_id},${batch.batch_id},BOX,${records.length},${totalVol}`
    
    showScannerDialog.value = false
    parseAndHandleScan(qrData, 'box')
}

const onClickBagLabel = (bag: {batch_record_id: string, re_code: string}) => {
    const batch = selectedSimBatch.value
    if (!batch) return
    const qrData = `${batch.plan_id},${bag.batch_record_id},${bag.re_code},0`
    
    showScannerDialog.value = false
    parseAndHandleScan(qrData, 'bag')
}

// Simulate scanning a bag from the WRONG batch (wrong box)
const onClickWrongBagLabel = (bag: {batch_record_id: string, re_code: string, source_batch: string}) => {
    // The bag_barcode is the real batch_record_id from another batch
    // This will be rejected by the backend because it doesn't belong to current box
    showScannerDialog.value = false
    verifyBag(bag.batch_record_id)
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

const isBagScannedInBox = (batchRecordId: string) => {
    if (!boxDetails.value) return false
    const bag = boxDetails.value.bags.find((b: any) => b.batch_record_id === batchRecordId)
    return bag && bag.status === 1
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
        <q-badge color="indigo-7" class="q-pa-xs q-px-sm" style="font-size: 12px;">
          <q-icon name="science" size="14px" class="q-mr-xs" />Batch: {{ recheckBatchId }}
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
            <div class="q-pa-xs" style="position: sticky; top: 28px; z-index: 1; background: white;">
              <q-input v-model="treeSearch" outlined dense placeholder="Search plan / batch..." bg-color="white" style="font-size: 12px;" clearable>
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
                <q-btn v-if="selectedBatchId" dense push color="deep-purple-9" text-color="white" icon="rocket_launch" label="Start Production" @click="goToStartProduction" class="q-mr-sm text-weight-bold" style="font-size: 12px; padding: 2px 8px;" />
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
                                <q-btn flat round dense icon="qr_code_scanner" size="xs" color="blue-9" @click.stop="" style="width: 24px;" />
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
</style>

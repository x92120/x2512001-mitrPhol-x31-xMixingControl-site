<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { generateQrDataUrl } from '~/composables/useQrCode'


const $q = useQuasar()
const { getAuthHeader, user, switchStationUser } = useAuth()
const { t } = useI18n()

// --- MQTT Integration ---
const { connect, disconnect, onMessage, offMessage, publishMessage, plantsData } = useMQTT()

const activePlcBatches = computed(() => {
    if (!plantsData.value) return []
    const active = []
    for (const [plantId, data] of Object.entries(plantsData.value)) {
        const batchId = String((data as any).Batch_ID || (data as any).batch_id || '').replace(/\0/g, '').trim()
        if (batchId && batchId !== '-' && batchId !== '0') {
            active.push({
                plant: plantId,
                batch_id: batchId,
                sku_name: String((data as any).SKU_Name || '').replace(/\0/g, '').trim(),
                phase: (data as any).Phase_ID || 0,
                step: (data as any).Step_ID || 0
            })
        }
    }
    return active
})

// --- State ---
const boxId = ref('')
const boxDetails = ref<any>(null)
const loading = ref(false)

// ── Batch-level recheck ──
const recheckBatchId = ref<string | null>('')
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

// ── Inspector (User QR Scan) + Lot Scan ──────────────────────────────────
const userScanInput = ref('')
const scannedInspector = ref<{ username: string; full_name: string } | null>(null)
const userScanLoading = ref(false)
const lotScanInput = ref('')
const scannedLot = ref('')

/** Resolves scanned username against /users/ and sets scannedInspector */
const onUserScanSubmit = async () => {
  const val = userScanInput.value.trim()
  if (!val) return
  userScanLoading.value = true
  userScanInput.value = ''   // clear immediately so scanner is ready for next
  try {
    const res = await $fetch<any[]>(`${appConfig.apiBaseUrl}/users/`, {
      headers: getAuthHeader() as Record<string, string>
    })
    const found = res.find((u: any) => u.username.toLowerCase() === val.toLowerCase())
    if (found) {
      scannedInspector.value = { username: found.username, full_name: found.full_name || found.username }
      // Switch active station user → updates top-right display across the app
      switchStationUser(found)
      playSound('success')
      $q.notify({ type: 'positive', icon: 'how_to_reg', message: `✅ Inspector: ${found.full_name || found.username}`, position: 'top-right', timeout: 2000 })
    } else {
      // User not found → alarm!
      playSound('error')
      setScanFeedback('error')
      $q.notify({
        type: 'negative',
        icon: 'person_off',
        message: `❌ User "${val}" not found`,
        caption: 'QR Badge not registered in the system',
        position: 'top',
        timeout: 4000,
        actions: [{ label: 'OK', color: 'white' }]
      })
    }
  } catch (e) {
    playSound('error')
    $q.notify({ type: 'negative', icon: 'wifi_off', message: 'Cannot reach server to verify user', position: 'top', timeout: 3000 })
  } finally {
    userScanLoading.value = false
  }
}

// Auto-submit user scan via debounce (handles scanners that don't send Enter)
let _userScanDebounce: ReturnType<typeof setTimeout> | null = null
watch(userScanInput, (val) => {
  if (!val) return
  if (_userScanDebounce) clearTimeout(_userScanDebounce)
  _userScanDebounce = setTimeout(() => {
    if (userScanInput.value.trim()) onUserScanSubmit()
  }, 150)
})

const onLotScanSubmit = () => {
  const val = lotScanInput.value.trim()
  if (!val) return
  scannedLot.value = val
  lotScanInput.value = ''
  $q.notify({ type: 'info', icon: 'inventory_2', message: `Lot locked: ${val}`, position: 'top', timeout: 1200 })
}

// Snapshot of the original session user (before any badge switch)
const _sessionUser = import.meta.client
    ? (() => { try { return JSON.parse(sessionStorage.getItem('_originalUser') || 'null') } catch { return null } })()
    : null

const clearInspector = () => {
    // Restore original login user
    if (_sessionUser) {
        switchStationUser(_sessionUser)
        scannedInspector.value = { username: _sessionUser.username, full_name: _sessionUser.full_name || _sessionUser.username }
    } else {
        scannedInspector.value = user.value ? {
            username: user.value.username || '',
            full_name: (user.value as any).full_name || user.value.username || ''
        } : null
    }
}
const clearLot = () => { scannedLot.value = '' }

/** Active operator — prefers scanned inspector over logged-in user */
const currentOperator = computed(() =>
  scannedInspector.value?.username || currentOperator.value
)



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

// Lazy expansion tracking — prevents rendering 2000+ batch nodes at once
const expandedSkus = ref<Record<string, boolean>>({})
const expandedPlans = ref<Record<string, boolean>>({})

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
    if (batch.batch_id === selectedBatchId.value) return

    if (isRecheckInProgress.value) {
        $q.dialog({
            title: 'Warning',
            message: 'All pre-batches must be re-checked in one session; selecting another batch will trigger a full reset of the current batch. Do you want to proceed?',
            cancel: true,
            persistent: true
        }).onOk(async () => {
            await resetBatchRecheck()
            actuallySelectBatch(batch)
        })
        return
    }
    
    actuallySelectBatch(batch)
}

const actuallySelectBatch = (batch: any) => {
    recheckBatchId.value = null
    batchRecheck.value = null
    selectedBatchId.value = batch.batch_id
    selectedPlanId.value = batch.plan_id || ''
    fetchBatchPreBatchData(batch.batch_id)
    fetchSubBatches(batch.batch_id)  // REQ-1: load sub-batch runs
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
        // Fire reset in background (don't block UI) + fetch data in parallel
        const resetPromise = $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/reset-batch/${batchId}`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>
        }).catch(() => {})

        const [items, recs] = await Promise.all([
            $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            }).catch(() => []),
            $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            }).catch(() => [])
        ])

        const loadedItems = items || []
        // Set all statuses locally (instant UI, no DB round-trip dependency)
        for (const item of loadedItems) {
            const wh = (item.wh || '').toUpperCase()
            if (wh === 'MIX' || wh === 'MIXING') {
                item.recheck_status = 1  // Auto-verified (no scan needed)
            } else {
                item.recheck_status = 0  // Requires scanning
            }
        }
        // Also reset packed recs status locally
        const loadedRecs = recs || []
        for (const rec of loadedRecs) {
            rec.recheck_status = 0
        }
        batchPreBatchItems.value = loadedItems
        batchPackedRecs.value = loadedRecs
        // resetPromise runs in background (fire-and-forget, DB sync)
    } catch (e) {
        console.error('Error fetching prebatch data:', e)
    } finally {
        prebatchLoading.value = false
    }
}

// ── REQ-1: Sub-batch runs (A, B, C) ──────────────────────────────────────────
const subBatches = ref<any[]>([])
const subBatchSaving = ref(false)
const subBatchRunOptions = ['A', 'B', 'C', 'D', 'E']

const fetchSubBatches = async (batchId: string) => {
    try {
        const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/production-batches/${batchId}/sub-batches`, {
            headers: getAuthHeader() as Record<string, string>
        }).catch(() => [])
        subBatches.value = data || []
    } catch { subBatches.value = [] }
}

const saveSubBatch = async (sub: any) => {
    if (!selectedBatchId.value) return
    subBatchSaving.value = true
    try {
        await $fetch(`${appConfig.apiBaseUrl}/production-batches/${selectedBatchId.value}/sub-batches`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>,
            body: { ...sub, operator: sub.operator || currentOperator.value }
        })
        $q.notify({ type: 'positive', message: `Sub-batch ${sub.sub_run} saved`, position: 'top', timeout: 1000 })
    } catch(e: any) {
        $q.notify({ type: 'negative', message: e?.data?.detail || 'Save failed', position: 'top' })
    } finally {
        subBatchSaving.value = false
    }
}

const addSubBatch = () => {
    const usedRuns = new Set(subBatches.value.map((s: any) => s.sub_run))
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
    const next = letters.find(r => !usedRuns.has(r)) || `Run-${subBatches.value.length + 1}`
    subBatches.value.push({ sub_run: next, actual_volume: null, start_time: null, stop_time: null, remarks: '', operator: currentOperator.value })
}

const removeSubBatch = async (idx: number) => {
    const sub = subBatches.value[idx]
    if (!sub || !selectedBatchId.value) return
    if (sub.id) {
        try {
            await $fetch(`${appConfig.apiBaseUrl}/production-batches/${selectedBatchId.value}/sub-batches/${sub.sub_run}`, {
                method: 'DELETE',
                headers: getAuthHeader() as Record<string, string>
            })
        } catch { /* ignore */ }
    }
    subBatches.value.splice(idx, 1)
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
        await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/force-verify-ingredient`, {
            method: 'POST',
            headers: getAuthHeader() as Record<string, string>,
            body: {
                batch_id: selectedBatchId.value,
                bag_barcode: ing.re_code,
                operator: currentOperator.value
            }
        })
        
        // Update local state directly so UI reacts instantly
        ing.recheck_status = 1
        for (const item of (ing.items || [])) {
            item.recheck_status = 1
            item.status = 2 // OK
        }
        
        // Also update original refs just in case
        if (batchPreBatchItems.value) {
            batchPreBatchItems.value.forEach((i: any) => {
                if (i.re_code === ing.re_code) i.recheck_status = 1
            })
        }
        if (batchPackedRecs.value) {
            batchPackedRecs.value.forEach((r: any) => {
                if (r.re_code === ing.re_code) r.recheck_status = 1
            })
        }

        playSound('success')
        $q.notify({ type: 'positive', message: `✅ ${ing.re_code} verified`, position: 'top', timeout: 500 })
        
        // Refresh batchRecheck so Start Production button unlocks
        if (recheckBatchId.value) {
            try {
                const data = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-batch/${recheckBatchId.value}`, {
                    headers: getAuthHeader() as Record<string, string>
                })
                batchRecheck.value = data
            } catch (e) {
                console.error('Silent refresh failed:', e)
            }
        }

    } catch (e) {
        console.error('[Verify] Force verify API failed', e)
        playSound('error')
        $q.notify({ type: 'negative', message: `Failed to force verify ${ing.re_code}`, position: 'top' })
    } finally {
        loading.value = false
    }
}

// ── Mark All FH / SPP ingredients at once ──
const markAllWarehouseLoading = ref<Record<string, boolean>>({})
const markAllWarehouse = async (group: any) => {
    const wh = group.warehouse
    if (wh === 'MIX') return
    markAllWarehouseLoading.value[wh] = true
    const unverified = group.ingredients.filter((ing: any) => ing.recheck_status !== 1)
    let successCount = 0
    for (const ing of unverified) {
        try {
            await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/force-verify-ingredient`, {
                method: 'POST',
                headers: getAuthHeader() as Record<string, string>,
                body: {
                    batch_id: selectedBatchId.value,
                    bag_barcode: ing.re_code,
                    operator: currentOperator.value
                }
            })
            // Update local state instantly
            ing.recheck_status = 1
            for (const item of (ing.items || [])) {
                item.recheck_status = 1
                item.status = 2
            }
            batchPreBatchItems.value.forEach((i: any) => { if (i.re_code === ing.re_code) i.recheck_status = 1 })
            batchPackedRecs.value.forEach((r: any) => { if (r.re_code === ing.re_code) r.recheck_status = 1 })
            successCount++
        } catch (e) {
            console.error(`[MarkAll] Failed to verify ${ing.re_code}:`, e)
        }
    }
    // Refresh batchRecheck so Start Production button may unlock
    if (recheckBatchId.value) {
        try {
            const data = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-batch/${recheckBatchId.value}`, {
                headers: getAuthHeader() as Record<string, string>
            })
            batchRecheck.value = data
        } catch (e) { /* silent */ }
    }
    markAllWarehouseLoading.value[wh] = false
    if (successCount > 0) {
        playSound('success')
        $q.notify({ type: 'positive', icon: 'check_circle', message: `✅ ${wh}: ${successCount} ingredient(s) approved`, position: 'top', timeout: 2000 })
    } else {
        $q.notify({ type: 'info', message: `${wh}: All already verified`, position: 'top', timeout: 1500 })
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
    // Extract plant ID before try so it's available in catch
    // NOTE: plan.plant from DB is descriptive string like "Mixing 01000" or "01000"
    // We must extract only a single-digit plant number (1,2,3) from it
    let rawPlant = selectedBatchInfo.value?.plant || ''
    let extractedPlantId = ''

    // Strategy 1: Try to find a single digit 1-9 at the END of the plant string (e.g. "Mixing 01" → "1")
    const trailingDigit = rawPlant.trim().match(/([1-9])$/)
    if (trailingDigit) {
        extractedPlantId = trailingDigit[1]
    }

    // Strategy 2: If plant string has only digits and is 1-3, use it directly (e.g. "1", "2", "3")
    if (!extractedPlantId) {
        const allDigits = rawPlant.replace(/\D/g, '')
        if (allDigits && Number(allDigits) >= 1 && Number(allDigits) <= 9) {
            extractedPlantId = String(Number(allDigits))
        }
    }

    // Strategy 3: Fallback to plan_id segment (e.g. P260514-01-01-001 → parts[2]="01" → "1")
    if (!extractedPlantId && selectedBatchInfo.value?.plan_id) {
        const parts = selectedBatchInfo.value.plan_id.split('-')
        if (parts.length >= 3) {
            const seg = parts[2].replace(/\D/g, '')
            if (seg && Number(seg) >= 1 && Number(seg) <= 9) {
                extractedPlantId = String(Number(seg))
            }
        }
    }
    const plantId = extractedPlantId || '1'
    try {
        console.log(`[StartProd] Extracted plantId=${plantId} from rawPlant=${rawPlant}, plan_id=${selectedBatchInfo.value?.plan_id}`)

        // 1. Send all recipe Data to DB1511 and verify readback
        let recipeSent = false
        while (!recipeSent) {
            try {
                await $fetch(`${appConfig.apiBaseUrl}/plc/send-recipe/${selectedBatchId.value}?plant_id=${Number(plantId)}`, {
                    method: 'POST',
                    headers: getAuthHeader() as Record<string, string>
                })
                console.log('[StartProd] PLC recipe sent and verified for:', selectedBatchId.value)
                recipeSent = true
            } catch (e: any) {
                console.error('[StartProd] PLC recipe transfer failed:', e)
                const dbNum = 1500 + (Number(plantId) * 10) + 1
                const shouldRetry = await new Promise((resolve) => {
                    $q.dialog({
                        title: 'Transfer Error',
                        message: `Failed to verify recipe transfer to PLC (DB${dbNum}). Error: ${e?.data?.detail || e.message}. Do you want to try sending again?`,
                        color: 'negative',
                        cancel: 'Cancel Production',
                        ok: 'Resend Recipe',
                        persistent: true
                    }).onOk(() => resolve(true)).onCancel(() => resolve(false))
                })
                if (!shouldRetry) {
                    loading.value = false
                    return // Abort start production
                }
            }
        }

        // 2. Publish MQTT start=1 signal to the plant's command topic
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
            `/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}&plan_id=${selectedBatchInfo.value?.plan_id}&sku_name=${encodeURIComponent(selectedBatchInfo.value?.sku_name || '')}&batch_size=${selectedBatchInfo.value?.batch_size || 0}&plant=${plantId}&from_check=1`
        )
    } catch (e: any) {
        console.error('[StartProd] Error:', e)
        $q.notify({ type: 'warning', message: 'Could not send start signal, navigating anyway.' })
        useRouter().push(`/x61-MixingControl?batch_id=${selectedBatchId.value}&sku_id=${selectedBatchInfo.value?.sku_id}&plan_id=${selectedBatchInfo.value?.plan_id}&sku_name=${encodeURIComponent(selectedBatchInfo.value?.sku_name || '')}&batch_size=${selectedBatchInfo.value?.batch_size || 0}&plant=${plantId}&from_check=1`)
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
    const uniquePhases: string[] = [...new Set(skuSteps.value.map((s: any) => String(s.phase_id || s.phase_number || '0')))]
    uniquePhases.forEach((ph, i) => {
        map[ph] = phaseColors[i % phaseColors.length] || 'bg-grey-2'
    })
    return map
})
const getPhaseColor = (step: any) => {
    const key = step.phase_id || step.phase_number || '0'
    return phaseColorMap.value[key] || ''
}

const isAllPrepackVerified = computed(() => {
    if (!batchRecheck.value || !batchRecheck.value.summary) return false
    return batchRecheck.value.summary.all_ok
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
        groups[wh]!.push(item)
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
            const reqItems = reCodeGroups[re] || []
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
const confirmResetBatchRecheck = () => {
    $q.dialog({
        title: 'Confirm Reset',
        message: 'Are you sure you want to reset all re-check verification for this batch? You will have to re-scan everything.',
        cancel: true,
        persistent: true
    }).onOk(() => {
        resetBatchRecheck()
    })
}

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
                operator: currentOperator.value
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
            // Keys may be uppercase (B, M, P, N, T) or lowercase (b, m, p, n, t)
            if (payload.b || payload.B) {
                // Normalize keys to lowercase before re-stringify
                const normalized: Record<string, any> = {}
                for (const [k, v] of Object.entries(payload)) { normalized[k.toLowerCase()] = v }
                barcodeStr = JSON.stringify(normalized)
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
            const rawParsed = JSON.parse(barcode)
            // Normalize keys to lowercase so both {B:...} and {b:...} work
            scanFields = {}
            for (const [k, v] of Object.entries(rawParsed)) { scanFields[k.toLowerCase()] = v }
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
            // Normalize to uppercase to match database format (labels may use lowercase 'p')
            candidate = candidate.toUpperCase()
            barcode = batchRecordId.toUpperCase()  // Full record ID for bag verification
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
        fullRecordId = String(scanFields.b).toUpperCase()
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
            const extracted = parts.slice(batchParts, parts.length - 1).join('-')
            if (extracted) {
                reCodeFromScan = extracted
            } else {
                // Fallback: barcode doesn't contain the full batch prefix
                // Try last segment (before optional bag number), e.g. "01-01-001-FV045A" → "FV045A"
                const lastPart = parts[parts.length - 1] || ''
                const secondLast = parts.length >= 2 ? parts[parts.length - 2] || '' : ''
                // If last part looks like a bag number (pure digits), RE code is second-to-last
                if (/^\d+$/.test(lastPart) && secondLast) {
                    reCodeFromScan = secondLast
                } else {
                    reCodeFromScan = lastPart
                }
            }
        } else if (parts.length >= 2) {
            // Short barcode: last segment is likely the RE code
            const lastPart = parts[parts.length - 1] || ''
            const secondLast = parts.length >= 2 ? parts[parts.length - 2] || '' : ''
            if (/^\d+$/.test(lastPart) && secondLast) {
                reCodeFromScan = secondLast
            } else {
                reCodeFromScan = lastPart
            }
        }
    }
    
    console.log('[Verify Bag Content]', { fullRecordId, reCodeFromScan, matCodeFromScan, batchId, prebatchGroups: prebatchByWarehouse.value.length })
    
    // Find matching ingredient across all warehouse groups
    let matched = false
    const fullRecordIdUpper = fullRecordId.toUpperCase()
    for (const group of prebatchByWarehouse.value) {
        // Multi-strategy matching: RE code, material code, or partial match
        const ing = group.ingredients.find((i: any) => {
            const rc = (i.re_code || '').trim()
            const scan = reCodeFromScan.trim()
            // Exact RE code match
            if (rc === scan) return true
            // Case-insensitive match
            if (rc.toLowerCase() === scan.toLowerCase()) return true
            // RE code contained in full record ID (case-insensitive)
            if (fullRecordIdUpper.includes(rc.toUpperCase())) return true
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
            
            // Refresh batchRecheck so UI status badges and Start Production button are updated dynamically!
            if (recheckBatchId.value) {
                try {
                    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/recheck-batch/${recheckBatchId.value}`, {
                        headers: getAuthHeader() as Record<string, string>
                    })
                    batchRecheck.value = data
                } catch (e) {
                    console.error('Silent refresh failed:', e)
                }
            }
            
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
                operator: currentOperator.value
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
            wrongBoxAlert.value = { show: true, bagCode: bagBarcode, expectedBox: boxId.value, newBatchId: '' }
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
    
/* Inspector + Lot Bar — compact inline */
.inspector-login-badge {
  background: #ede7f6;
  border-radius: 20px;
  padding: 3px 12px;
  border: 1px solid #ce93d8;
  white-space: nowrap;
}
.inspector-label {
  font-size: 11px;
  font-weight: 700;
  color: #6a1b9a;
  margin-right: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.inspector-value {
  font-size: 13px;
  font-weight: 700;
  color: #4a148c;
}
.lot-inline-section {
  gap: 4px;
  white-space: nowrap;
}
.lot-chip-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #e0f2f1;
  border: 1px solid #80cbc4;
  border-radius: 16px;
  padding: 2px 10px;
  font-size: 13px;
  font-weight: 700;
  color: #004d40;
}
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

    // Save original session user snapshot for restore-on-clear
    if (import.meta.client && user.value) {
        const existing = sessionStorage.getItem('_originalUser')
        if (!existing) {
            sessionStorage.setItem('_originalUser', JSON.stringify(user.value))
        }
    }
    // Auto-fill inspector from logged-in user
    if (user.value) {
        scannedInspector.value = {
            username: user.value.username || '',
            full_name: (user.value as any).full_name || user.value.username || ''
        }
    }

    // Connect to MQTT and listen for barcodes
    connect()
    onMessage(handleMqttBarcode)

    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('unload', handleUnload)
})

// Keep inspector in sync if user changes (re-login)
watch(user, (newUser) => {
    if (newUser && !scannedInspector.value) {
        scannedInspector.value = {
            username: newUser.username || '',
            full_name: (newUser as any).full_name || newUser.username || ''
        }
    }
}, { immediate: false })

onUnmounted(() => {
    offMessage(handleMqttBarcode)
    disconnect()
    window.removeEventListener('beforeunload', handleBeforeUnload)
    window.removeEventListener('unload', handleUnload)
})
</script>

<template>
  <q-page class="q-pa-sm" style="height: calc(100vh - 56px);">

    <!-- ===== COMBINED HEADER + SCAN BAR ===== -->
    <div class="row items-center q-gutter-sm q-mb-sm" style="flex-shrink: 0;">
      <!-- Title -->
      <div class="bg-blue-9 text-white q-pa-sm rounded-borders shadow-2 row items-center q-gutter-xs" style="flex-shrink: 0;">
        <q-icon name="fact_check" size="sm" />
        <div class="text-subtitle1 text-weight-bolder" style="white-space: nowrap;">Check for Production</div>
      </div>

      <!-- PLC ACTIVE PRODUCTION BANNERS -->
      <div v-for="active in activePlcBatches" :key="active.plant" class="bg-cyan-1 border-cyan-3 rounded-borders q-px-sm q-py-xs row items-center q-gutter-x-sm shadow-1" style="border: 1px solid #4dd0e1; flex-shrink: 0;">
         <q-icon name="precision_manufacturing" color="cyan-9" size="xs" />
         <div class="text-cyan-10 text-weight-bold" style="font-size: 12px; line-height: 1;">PLC-{{active.plant}} RUNNING</div>
         <q-separator vertical color="cyan-3" />
         <q-badge color="cyan-8" style="font-size: 11px;">Batch: {{ active.batch_id }}</q-badge>
         <q-badge color="cyan-8" style="font-size: 11px;" v-if="active.sku_name">SKU: {{ active.sku_name }}</q-badge>
         <q-badge color="cyan-9" style="font-size: 11px;">Step: {{ active.phase }} / {{ active.step }}</q-badge>
      </div>

      <!-- Unified Scan Input -->
      <div class="col" :class="lastScanResult === 'success' && flashActive ? 'bg-green-1' : (lastScanResult === 'error' && flashActive ? 'bg-red-1' : '')" style="border-radius: 8px; transition: background 0.3s;">
        <q-input 
          v-model="boxScanInput" 
          ref="bagScanRef"
          outlined dense
          :placeholder="selectedBatchId ? 'SCAN NEXT PREBATCH LABEL...' : 'Scan Batch ID or Ingredient Label...'" 
          @keyup.enter="onUnifiedScanSubmit"
          autofocus
          bg-color="white"
          style="font-size: 14px;"
        >
          <template v-slot:prepend>
            <q-icon name="qr_code_scanner" :color="lastScanResult === 'success' ? 'green' : (lastScanResult === 'error' ? 'red' : 'primary')" size="sm" />
          </template>
          <template v-slot:append>
            <div v-if="lastScanResult !== 'none'" 
              :class="['status-spot', `bg-${lastScanResult === 'success' ? 'green' : 'red'}`, flashActive ? 'flash-active' : '']"
            >
              <q-icon :name="lastScanResult === 'success' ? 'check' : 'close'" color="white" size="18px" />
            </div>
          </template>
        </q-input>
      </div>

      <!-- Status text -->
      <div class="text-subtitle2 text-weight-bold" :class="lastScanResult === 'success' ? 'text-green' : (lastScanResult === 'error' ? 'text-red' : 'text-grey-6')" style="white-space: nowrap;">
        {{ lastScanResult === 'success' ? '✅ OK! SCAN NEXT...' : (lastScanResult === 'error' ? '❌ ERROR!' : 'WAIT FOR SCAN...') }}
      </div>

      <!-- Action buttons -->
      <q-btn flat dense icon="restart_alt" label="Re scan" color="warning" @click="confirmResetBatchRecheck" :disable="!recheckBatchId" class="q-mr-sm"><q-tooltip>Reset all re-check current and re new scan</q-tooltip></q-btn>
      <q-btn flat round dense icon="print" color="blue-9" @click="printBatchIngredientReport" :disable="!selectedBatchInfo"><q-tooltip>Print Batch Ingredient Report</q-tooltip></q-btn>
      <q-btn flat round dense icon="assessment" color="blue-9" @click="showQCReportDialog = true"><q-tooltip>QC Report</q-tooltip></q-btn>
      <q-btn flat round dense icon="volume_up" color="blue-9" @click="showSoundSettings = true"><q-tooltip>{{ t('sound.title') }}</q-tooltip></q-btn>
    </div>

    <!-- ===== INSPECTOR + LOT SCAN BAR ===== -->
    <div class="row items-center no-wrap q-gutter-sm q-mb-xs" style="flex-shrink: 0; min-height: 36px;">

      <!-- Inspector: auto badge + override scan -->
      <div class="row items-center no-wrap q-gutter-xs">
        <q-icon name="badge" color="deep-purple-8" size="18px" />
        <span class="inspector-label">Inspector:</span>

        <!-- Active inspector badge -->
        <div class="inspector-login-badge row items-center no-wrap q-gutter-xs">
          <q-icon name="how_to_reg" color="deep-purple-8" size="14px" />
          <span class="inspector-value">{{ scannedInspector?.full_name || user?.username || '-' }}</span>
          <q-badge outline color="deep-purple-7" style="font-size: 10px;">
            @{{ scannedInspector?.username || user?.username }}
          </q-badge>
        </div>

        <!-- Scan override input -->
        <q-input
          v-model="userScanInput"
          outlined dense
          placeholder="Scan QR to change..."
          @keyup.enter="onUserScanSubmit"
          :loading="userScanLoading"
          bg-color="white"
          style="font-size: 12px; width: 190px;"
        >
          <template v-slot:prepend>
            <q-icon name="qr_code_scanner" color="deep-purple-5" size="xs" />
          </template>
          <template v-slot:append>
            <q-btn
              v-if="scannedInspector?.username !== (user?.username)"
              flat round dense icon="restart_alt" size="xs" color="deep-purple-7"
              @click="clearInspector"
            >
              <q-tooltip>Reset to login user</q-tooltip>
            </q-btn>
          </template>
        </q-input>
      </div>

      <q-separator vertical inset color="grey-4" style="height: 24px; align-self: center;" />

      <!-- Lot Scan (compact inline) -->
      <div class="row items-center no-wrap lot-inline-section">
        <q-icon name="inventory_2" color="teal-8" size="18px" class="q-mr-xs" />
        <span class="inspector-label">Lot:</span>
        <div v-if="scannedLot" class="lot-chip-inline">
          <q-icon name="qr_code" size="14px" />
          <span>{{ scannedLot }}</span>
          <q-btn flat round dense icon="close" size="xs" color="teal-9" @click="clearLot">
            <q-tooltip>Clear Lot</q-tooltip>
          </q-btn>
        </div>
        <q-input
          v-else
          v-model="lotScanInput"
          outlined dense
          placeholder="Scan Lot..."
          @keyup.enter="onLotScanSubmit"
          bg-color="white"
          style="font-size: 12px; width: 180px;"
        >
          <template v-slot:prepend>
            <q-icon name="qr_code_scanner" color="teal-7" size="xs" />
          </template>
        </q-input>
      </div>
    </div>

      <!-- ===== UNIFIED 3-PANE LAYOUT ===== -->
      <q-card flat bordered class="shadow-1" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; height: calc(100% - 50px);">
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
                    <q-expansion-item v-model="expandedSkus[sku.skuId]" dense dense-toggle switch-toggle-side header-class="q-py-none bg-grey-1" header-style="padding-left: 24px;" style="font-size: 12px;">
                      <template v-slot:header>
                        <q-item-section avatar style="min-width: 20px;"><q-icon name="inventory_2" size="14px" color="indigo-7" /></q-item-section>
                        <q-item-section><q-item-label class="text-weight-bold text-indigo-9 ellipsis">{{ sku.skuId }} · {{ sku.skuName }}</q-item-label></q-item-section>
                        <q-item-section side><q-badge color="indigo-5" outline>{{ sku.plans.length }}-Plan</q-badge></q-item-section>
                      </template>

                      <!-- Plan Level -->
                      <template v-for="plan in sku.plans" :key="plan.plan_id">
                        <q-expansion-item v-model="expandedPlans[plan.plan_id]" expand-separator expand-icon="arrow_drop_down" dense dense-toggle switch-toggle-side :default-opened="selectedPlanId === plan.plan_id" header-class="q-py-none" header-style="padding-left: 44px;" style="font-size: 12px;">
                          <template v-slot:header>
                            <q-item-section avatar style="min-width: 20px;"><q-icon name="assignment" size="14px" color="teal-7" /></q-item-section>
                            <q-item-section><q-item-label class="text-weight-bold text-teal-9">{{ plan.plan_id }}</q-item-label></q-item-section>
                            <q-item-section side><q-badge color="teal-3" text-color="teal-10">{{ (plan.batches || []).length }} Batch</q-badge></q-item-section>
                          </template>

                          <!-- Batch Level (lazy: only render when plan is expanded) -->
                          <q-list v-if="expandedPlans[plan.plan_id]" dense>
                            <q-item
                              v-for="batch in (plan.batches || [])" :key="batch.batch_id"
                              clickable dense
                              :active="recheckBatchId === batch.batch_id || boxId === batch.batch_id || selectedBatchId === batch.batch_id"
                              active-class="bg-blue-1"
                              @click="
                                isFifoBatch(batch.batch_id)
                                  ? (boxScanInput = batch.batch_id, selectBatchFromTree(batch), onBoxScanSubmit())
                                  : $q.notify({ type: 'negative', icon: 'block', message: '⛔ FIFO: Not active batch', caption: `Complete ${getFifoBlocker(batch.batch_id)} first`, position: 'top', timeout: 3000 })
                              "
                              :class="[
                                batch.status === 'Hold' ? 'bg-amber-1' : '',
                                !isFifoBatch(batch.batch_id) && batch.status !== 'Hold' && batch.status !== 'Done' ? 'fifo-locked-item' : ''
                              ]"
                              style="min-height: 28px; padding-left: 64px;"
                              :style="isFifoBatch(batch.batch_id) ? 'border-left: 3px solid #2e7d32;' : (batch.status === 'Done' ? '' : 'border-left: 3px solid #e0e0e0; opacity: 0.7;')"
                            >
                              <q-item-section avatar style="min-width: 18px;">
                                <q-icon
                                  :name="batch.status === 'Hold' ? 'pause_circle' : (batch.status === 'Done' ? 'check_circle' : (isFifoBatch(batch.batch_id) ? 'play_circle' : 'lock'))"
                                  size="12px"
                                  :color="batch.status === 'Hold' ? 'amber-9' : (batch.status === 'Done' ? 'grey-4' : (isFifoBatch(batch.batch_id) ? 'green-8' : 'grey-5'))"
                                />
                              </q-item-section>
                              <q-item-section>
                                <q-item-label
                                  class="text-weight-bold ellipsis"
                                  :class="
                                    batch.status === 'Hold' ? 'text-amber-9' :
                                    batch.status === 'Done' ? 'text-grey-5' :
                                    isFifoBatch(batch.batch_id) ? 'text-green-9' : 'text-grey-6'
                                  "
                                >
                                  {{ batch.batch_id }} · {{ (batch.batch_size || 0).toFixed(1) }}kg
                                </q-item-label>
                              </q-item-section>
                              <q-item-section side>
                                <div class="row items-center q-gutter-xs">

                                  <!-- FIFO ACTIVE badge -->
                                  <q-badge
                                    v-if="isFifoBatch(batch.batch_id) && batch.status !== 'Hold'"
                                    color="green-8"
                                    style="font-size: 9px; padding: 1px 4px; letter-spacing: 0.5px;"
                                  >▶ ACTIVE</q-badge>

                                  <!-- FIFO QUEUED badge (locked) -->
                                  <q-badge
                                    v-else-if="!isFifoBatch(batch.batch_id) && batch.status !== 'Done' && batch.status !== 'Hold'"
                                    color="grey-4" text-color="grey-7"
                                    style="font-size: 9px; padding: 1px 4px;"
                                  >
                                    <q-icon name="lock" size="9px" class="q-mr-xs" />QUEUED
                                    <q-tooltip>FIFO: Complete {{ getFifoBlocker(batch.batch_id) }} first</q-tooltip>
                                  </q-badge>

                                  <!-- HOLD badge -->
                                  <q-badge v-else-if="batch.status === 'Hold'" color="amber-9" style="font-size: 10px; padding: 1px 5px; letter-spacing: 0.5px;">HOLD</q-badge>

                                  <!-- FH / SPP status (active or done only) -->
                                  <template v-if="isFifoBatch(batch.batch_id) || batch.status === 'Done'">
                                    <q-badge :color="getTreeBatchFH(batch) ? 'green' : 'grey-4'" style="font-size: 10px; padding: 1px 3px;">FH</q-badge>
                                    <q-badge :color="getTreeBatchSPP(batch) ? 'green' : 'grey-4'" style="font-size: 10px; padding: 1px 3px;">SPP</q-badge>
                                  </template>

                                  <!-- Hold/Unhold toggle button -->
                                  <q-btn
                                    flat round dense
                                    :icon="batch.status === 'Hold' ? 'play_circle' : 'pause_circle'"
                                    size="8px"
                                    :color="batch.status === 'Hold' ? 'positive' : 'amber-9'"
                                    @click.stop="openHoldDialog(batch, $event)"
                                    style="width: 20px; height: 20px;"
                                  >
                                    <q-tooltip>{{ batch.status === 'Hold' ? 'Unhold Batch' : 'Hold Batch' }}</q-tooltip>
                                  </q-btn>
                                  <q-btn flat round dense icon="print" size="8px" color="indigo-4" @click.stop="printBatchLabelReport(batch.batch_id)" style="width: 20px; height: 20px;"><q-tooltip>Print Labels</q-tooltip></q-btn>
                                </div>
                              </q-item-section>
                              <q-tooltip v-if="!isFifoBatch(batch.batch_id) && batch.status !== 'Done' && batch.status !== 'Hold'">
                                ⛔ FIFO LOCKED — Complete {{ getFifoBlocker(batch.batch_id) }} first
                              </q-tooltip>
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
                <div class="q-mr-sm bg-yellow text-black q-pa-xs rounded-borders" style="font-size:10px;">
                  allOk: {{ isAllPrepackVerified }}, fifo: {{ isFifoBatch(selectedBatchId || '') }}
                </div>
                <q-btn
                  v-if="selectedBatchId"
                  dense push
                  icon="rocket_launch"
                  label="START PRODUCTION"
                  @click="goToStartProduction"
                  :loading="loading"
                  class="q-mr-sm text-weight-bolder start-prod-btn"
                  style="font-size: 12px; padding: 2px 12px; letter-spacing: 0.5px; transition: background 0.3s, box-shadow 0.3s;"
                  :style="canStartProduction
                    ? (loading
                        ? 'background:#2e7d32 !important; color:white !important; box-shadow: 0 0 12px rgba(46,125,50,0.6);'
                        : 'background:#1565c0 !important; color:white !important; box-shadow: 0 0 10px rgba(21,101,192,0.5);')
                    : 'background:#bdbdbd !important; color:#757575 !important; box-shadow:none; cursor:not-allowed;'"
                  :disable="!canStartProduction"
                >
                  <q-tooltip v-if="!canStartProduction">Verify all FH &amp; SPP ingredients first</q-tooltip>
                </q-btn>


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

              <!-- ── REQ-1: SUB-BATCH RUNS PANEL (A, B, C) ── -->
              <div class="q-px-sm q-pt-sm">
                <q-card flat bordered style="border-color: #9c27b0;">
                  <div class="row items-center q-px-sm q-py-xs bg-purple-1">
                    <q-icon name="splitscreen" color="purple-7" size="16px" class="q-mr-xs"/>
                    <span class="text-caption text-weight-bold text-purple-8">{{ t('rpt.subBatch') || 'Sub-Batch Runs' }}</span>
                    <q-space/>
                    <q-btn dense flat size="xs" icon="add_circle" color="purple-7" label="Add Run" @click="addSubBatch" />
                  </div>
                  <q-separator/>
                  <div v-if="subBatches.length === 0" class="text-center q-py-sm text-grey-5 text-caption">No sub-batch runs yet — click Add Run</div>
                  <q-list dense separator>
                    <q-item v-for="(sub, idx) in subBatches" :key="sub.sub_run" style="padding: 4px 8px;">
                      <q-item-section>
                        <div class="row q-gutter-xs items-center">
                          <q-input v-model="sub.sub_run" dense outlined placeholder="Run ID" style="width:70px" maxlength="10" class="text-caption text-weight-bold text-purple-9 text-uppercase" />
                          <q-input v-model="sub.operator" dense outlined placeholder="Operator" style="width:100px" class="text-caption"/>
                          <q-btn dense flat icon="save" color="purple-7" size="xs" :loading="subBatchSaving" @click="saveSubBatch(sub)"/>
                          <q-btn dense flat icon="delete" color="red-4" size="xs" @click="removeSubBatch(idx)"/>
                        </div>
                        <q-input v-model="sub.remarks" dense borderless placeholder="Remarks..." class="q-ml-xs text-caption text-grey-7" style="font-size:11px"/>
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-card>
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
                  <template v-slot:header>
                    <q-item-section avatar>
                      <q-icon :name="group.warehouse === 'FH' || group.warehouse === 'FLAVOUR HOUSE' ? 'science' : 'blender'" />
                    </q-item-section>
                    <q-item-section>
                      <span class="text-weight-bold">🧪 {{ group.warehouse }} ({{ group.ingredients.length }})</span>
                    </q-item-section>
                    <q-item-section side v-if="group.warehouse !== 'MIX'">
                      <q-btn
                        dense unelevated
                        :color="getWhStatus(group.warehouse) === 1 ? 'green-7' : 'orange-8'"
                        :icon="getWhStatus(group.warehouse) === 1 ? 'check_circle' : 'done_all'"
                        :label="getWhStatus(group.warehouse) === 1 ? 'All OK ✅' : 'Mark All ✅'"
                        size="xs"
                        :loading="markAllWarehouseLoading[group.warehouse]"
                        :disable="getWhStatus(group.warehouse) === 1"
                        @click.stop="markAllWarehouse(group)"
                        style="font-size: 10px; padding: 2px 8px; border-radius: 4px;"
                      >
                        <q-tooltip>Approve all {{ group.warehouse }} ingredients as delivered</q-tooltip>
                      </q-btn>
                    </q-item-section>
                  </template>
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
                            :title="`${selectedBatchInfo.batch_id}-${pb.re_code}-${pb.package_no || (index + 1)}/${pb.total_packages || ing.items?.length}`">
                            {{ selectedBatchInfo.batch_id }}-{{ pb.re_code }}-{{ pb.package_no || (index + 1) }}/{{ pb.total_packages || ing.items?.length }}
                          </span>
                          <span class="text-grey-7" style="width: 60px;">{{ pb.package_no || (index + 1) }}/{{ pb.total_packages || ing.items?.length }}</span>
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

            <!-- No batch selected placeholder -->
            <template v-else>
              <div class="column items-center justify-center full-height text-grey-4 q-pa-xl">
                <q-icon name="qr_code_scanner" size="120px" class="q-mb-md" style="opacity: 0.3;" />
                <div class="text-h5 text-weight-bold" style="letter-spacing: 2px; opacity: 0.5;">READY TO SCAN</div>
                <div class="text-subtitle1 text-center q-mt-sm" style="max-width: 400px; opacity: 0.6;">
                  Scan a <b>Batch ID</b> or an <b>Ingredient Bag</b> to load the production checklist.
                </div>
              </div>
            </template>
          </div>

        </div>

        <!-- Release to Production footer (Only show when ready) -->
        <q-card-section v-if="activeBatchForProduction && canStartProduction" class="bg-green-1 q-py-sm text-center" style="flex-shrink: 0; border-top: 2px solid #4caf50;">
          <div class="row items-center justify-center q-gutter-sm">
            <q-icon name="verified" size="24px" color="green" />
            <span class="text-subtitle2 text-green-9 text-weight-bold">All items verified! Ready to release.</span>
            <q-btn color="positive" size="md" label="Release to Production" icon="rocket_launch" unelevated class="text-weight-bold q-ml-md" @click="releaseBatch" :loading="loading" />
          </div>
        </q-card-section>
      </q-card>

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

    <!-- ===== HOLD / UNHOLD CONFIRM DIALOG ===== -->
    <q-dialog v-model="holdDialog" persistent>
      <q-card style="min-width: 360px; border-radius: 12px; overflow: hidden;">
        <!-- Header -->
        <div :class="holdTarget?.status === 'Hold' ? 'bg-positive' : 'bg-amber-9'" class="q-pa-md row items-center q-gutter-sm">
          <q-icon :name="holdTarget?.status === 'Hold' ? 'play_circle' : 'pause_circle'" size="28px" color="white" />
          <div class="text-white text-weight-bold text-subtitle1">
            {{ holdTarget?.status === 'Hold' ? 'Unhold Batch' : 'Hold Batch' }}
          </div>
        </div>

        <q-card-section class="q-pt-md">
          <!-- Batch Info -->
          <div class="q-mb-md row items-center q-gutter-sm">
            <q-icon name="science" color="indigo" />
            <span class="text-weight-bold text-indigo-9 text-subtitle2">{{ holdTarget?.batch_id }}</span>
            <q-badge :color="holdTarget?.status === 'Hold' ? 'amber-9' : 'blue'">
              {{ holdTarget?.status || '-' }}
            </q-badge>
          </div>

          <!-- Info message -->
          <q-banner v-if="holdTarget?.status !== 'Hold'" dense class="bg-amber-1 text-amber-10 rounded-borders q-mb-md" style="font-size: 12px;">
            <template v-slot:avatar><q-icon name="info" color="amber-9" /></template>
            This batch will be put on <b>Hold</b>. The next <b>In-Progress</b> batch in the queue (FIFO) will be processed first.
          </q-banner>
          <q-banner v-else dense class="bg-green-1 text-green-10 rounded-borders q-mb-md" style="font-size: 12px;">
            <template v-slot:avatar><q-icon name="info" color="green" /></template>
            Batch will be released from Hold and return to <b>In-Progress</b> status (re-enters FIFO queue).
          </q-banner>

          <!-- Reason input (only for Hold) -->
          <q-input
            v-if="holdTarget?.status !== 'Hold'"
            v-model="holdReason"
            outlined dense
            label="Reason (optional)"
            placeholder="e.g. Awaiting QC check, material shortage..."
            maxlength="100"
          />
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md q-pt-none">
          <q-btn flat label="Cancel" color="grey" v-close-popup :disable="holdLoading" />
          <q-btn
            unelevated
            :label="holdTarget?.status === 'Hold' ? 'Release (Unhold)' : 'Confirm Hold'"
            :icon="holdTarget?.status === 'Hold' ? 'play_circle' : 'pause_circle'"
            :color="holdTarget?.status === 'Hold' ? 'positive' : 'amber-9'"
            :loading="holdLoading"
            @click="confirmHold"
          />
        </q-card-actions>
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
      <div v-if="wrongBoxAlert.show" class="wrong-box-overlay">
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
          
          <div class="row q-gutter-md justify-center q-mt-xl">
            <q-btn 
              color="grey-9" 
              text-color="white" 
              size="lg" 
              icon="reply" 
              label="Continue Current Batch" 
              @click="wrongBoxAlert.show = false; bagScanRef?.focus()"
              class="q-px-xl q-py-md text-weight-bold"
              style="border: 2px solid rgba(255,255,255,0.4);"
            />
            
            <q-btn 
              v-if="wrongBoxAlert.newBatchId && wrongBoxAlert.newBatchId !== wrongBoxAlert.expectedBox"
              color="indigo-9" 
              text-color="white" 
              size="lg" 
              icon="switch_access_shortcut" 
              :label="'Switch to ' + wrongBoxAlert.newBatchId" 
              @click="handleWrongBoxSwitch"
              class="q-px-xl q-py-md text-weight-bold"
              style="border: 2px solid rgba(255,255,255,0.8);"
            />
            <q-btn 
              v-else
              color="negative" 
              text-color="white" 
              size="lg" 
              icon="restart_alt" 
              label="Start New Batch" 
              @click="startNewBatch"
              class="q-px-xl q-py-md text-weight-bold"
              style="border: 2px solid rgba(255,255,255,0.8);"
            />
          </div>
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

/* START PRODUCTION button — 3 states */
.start-prod-btn {
  border-radius: 6px !important;
  min-height: 30px !important;
  transition: background 0.3s ease, box-shadow 0.3s ease, transform 0.15s ease !important;
}
/* Enabled (blue) — subtle attention pulse */
.start-prod-btn:not([disabled]):not(.q-btn--loading) {
  animation: start-btn-pulse 2s ease-in-out infinite;
}
@keyframes start-btn-pulse {
  0%, 100% { box-shadow: 0 0 8px rgba(21,101,192,0.4); transform: scale(1); }
  50%       { box-shadow: 0 0 16px rgba(21,101,192,0.75); transform: scale(1.02); }
}
/* Click moment — grow slightly */
.start-prod-btn:not([disabled]):active {
  transform: scale(0.97) !important;
}

/* FIFO locked batch row */
.fifo-locked-item {
  background: repeating-linear-gradient(
    135deg,
    transparent,
    transparent 6px,
    rgba(0,0,0,0.02) 6px,
    rgba(0,0,0,0.02) 12px
  ) !important;
  cursor: not-allowed !important;
}
.fifo-locked-item:hover {
  background: #fafafa !important;
}
</style>

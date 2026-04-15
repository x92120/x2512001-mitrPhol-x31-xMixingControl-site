/**
 * usePreBatchWorkflow — 7-step guided workflow, tare/confirm popups, scan dialog, scan-full-lot
 */
import { ref, computed, watch, nextTick } from 'vue'
import { appConfig } from '~/appConfig/config'

export interface WorkflowDeps {
  $q: any
  getAuthHeader: () => Record<string, string>
  t: (key: string, params?: any) => string
  formatDate: (d: any) => string
  parseDateSafe: (d: any) => Date | null
  // Composable refs
  selectedReCode: any
  selectedIntakeLotId: any
  selectedInventoryItem: any
  requireVolume: any
  packageSize: any
  containerSize: any
  ingredients: any
  prebatchItems: any
  inventoryRows: any
  filteredInventory: any
  selectableIngredients: any
  selectedBatch: any
  selectedProductionPlan: any
  selectedPlanDetails: any
  currentPackageOrigins: any
  remainVolume: any
  actualScaleValue: any
  activeScale: any
  lastCapturedWeight: any
  batchedVolume: any
  completedCount: any
  nextPackageNo: any
  preBatchLogs: any
  selectedPreBatchLogs: any
  totalCompletedWeight: any
  productionPlans: any
  ingredientBatchDetail: any
  // Scale composable
  scalesComposable: any
  // Ingredient composable
  ingredientsComposable: any
  // Functions
  getPackagePlan: (batchId: string, reCode: string, requiredVolume: number) => any[]
  fetchPreBatchRecords: () => Promise<void>
  fetchPrebatchItems: (batchId: string) => Promise<void>
  fetchIngredientBatchDetail: (reCode: string) => Promise<void>
  updatePrebatchItemStatus: (batchId: string, reCode: string, status: number) => Promise<void>
  advanceToNextBatch: (batchId: string, reCode: string) => Promise<boolean>
  onPlanShow: (plan: any) => Promise<void>
  onBatchIngredientClick: (batch: any, req: any, plan: any) => Promise<void>
  onBatchExpand: (batch: any) => void
  requestBatch: any
  // Label functions
  buildLabelData: (data: any) => any
  generateLabelSvg: (template: string, data: any) => Promise<string>
  printLabel: (svg: string) => Promise<void>
  onDone: (autoPrint: boolean) => Promise<void>
}

export function usePreBatchWorkflow(deps: WorkflowDeps) {
  const { $q, getAuthHeader, t, formatDate, parseDateSafe } = deps

  // ─── Workflow State ───
  const workflowStep = ref(1)
  const pendingAdvance = ref<{ batchId: string; reCode: string } | null>(null)

  const workflowStatus = computed(() => {
    if (!deps.selectedReCode.value || !deps.selectedIntakeLotId.value) return { id: 2, msg: 'Scan Intake Lot ID', color: 'orange-10' }
    if (workflowStep.value === 3) return { id: 3, msg: 'Select Scale & Tare to 0.00 kg', color: 'blue-8' }
    if (workflowStep.value === 4) return { id: 6, msg: 'Batching in Progress', color: 'green-8' }
    if (workflowStep.value === 7) return { id: 7, msg: 'Done, Clear Scale -> Next', color: 'red-9' }
    return { id: 0, msg: 'Idle', color: 'grey' }
  })

  // ─── Tare / Confirm Popups ───
  const showTarePopup = ref(false)
  const selectedTareScale = ref(0)
  const showConfirmStartPopup = ref(false)
  let tarePopupTimer: ReturnType<typeof setTimeout> | null = null

  const getScaleCapacity = (scale: any): number => {
    const match = scale.label.match(/(\d+)\s*[Kk]g/)
    return match ? Number(match[1]) : 999
  }

  const autoSelectBestScale = () => {
    const target = deps.packageSize.value || deps.requireVolume.value || 0
    const sorted = [...deps.scalesComposable.scales.value]
      .filter((s: any) => !s.isError)
      .sort((a: any, b: any) => getScaleCapacity(a) - getScaleCapacity(b))
    const best = sorted.find((s: any) => getScaleCapacity(s) >= target) || sorted[sorted.length - 1]
    if (best) {
      selectedTareScale.value = best.id
      deps.scalesComposable.selectedScale.value = best.id
    }
  }

  const openTarePopup = () => {
    autoSelectBestScale()
    showTarePopup.value = true
    if (tarePopupTimer) clearTimeout(tarePopupTimer)
  }

  const closeTarePopupAndAdvance = () => {
    if (tarePopupTimer) clearTimeout(tarePopupTimer)
    showTarePopup.value = false
    deps.scalesComposable.selectedScale.value = selectedTareScale.value
  }

  const handleTareAndAdvance = () => {
    if (selectedTareScale.value) {
      deps.scalesComposable.selectedScale.value = selectedTareScale.value
      deps.scalesComposable.onTare(selectedTareScale.value)
    }
    closeTarePopupAndAdvance()
  }

  const confirmStartWeighing = () => {
    showConfirmStartPopup.value = false
    workflowStep.value = 4
  }

  const handleStartWeighting = () => {
    workflowStep.value = 4
  }

  const isScaleAtZero = computed(() => {
    const tolerance = deps.activeScale.value?.tolerance || 0.01
    return Math.abs(deps.actualScaleValue.value) <= tolerance * 2
  })

  // ─── Done / Step 7 ───
  const handleDoneClick = async () => {
    const currentBatchId = deps.selectedBatch.value?.batch_id
    const currentReCode = deps.selectedReCode.value
    deps.lastCapturedWeight.value = deps.actualScaleValue.value
    await deps.onDone(true)
    workflowStep.value = 7
    pendingAdvance.value = { batchId: currentBatchId, reCode: currentReCode }
  }

  const handleStep7Confirm = (manual = false) => {
    const packages = deps.getPackagePlan(deps.selectedBatch.value?.batch_id, deps.selectedReCode.value, deps.requireVolume.value)
    const isBatchFinished = deps.remainVolume.value <= 0.0001
    const hasMorePkgsInCurrentBatch = packages.some((p: any) => p.status === 'pending')

    if (!isBatchFinished && hasMorePkgsInCurrentBatch) {
      const completed = packages.filter((p: any) => p.status === 'completed').length
      const total = packages.length
      deps.currentPackageOrigins.value = []
      workflowStep.value = 3
      $q.notify({ type: 'info', message: `Package ${completed}/${total} done — ready for next`, position: 'top', timeout: 2000 })
    } else {
      handleAdvanceInternal()
    }
  }

  // ─── Stop / Advance ───
  const handleStopPreBatch = () => {
    $q.dialog({
      title: 'STOP PRE-BATCH',
      message: 'Are you sure you want to <b class="text-red-9">STOP</b> and reset?<br/>Any unprinted weights will be lost.',
      ok: { label: 'Yes, Stop & Reset', color: 'red-9', unelevated: true },
      cancel: { flat: true, color: 'grey-7' },
      html: true, persistent: true
    }).onOk(() => {
      workflowStep.value = 1
      deps.selectedReCode.value = ''
      deps.selectedIntakeLotId.value = ''
      deps.currentPackageOrigins.value = []
      $q.notify({ type: 'info', message: 'Workflow reset to Step 1', position: 'top' })
    })
  }

  const handleAdvanceInternal = async () => {
    if (!pendingAdvance.value) return
    const currentReCode = pendingAdvance.value.reCode
    const currentBatchId = pendingAdvance.value.batchId
    const nextBatchPromise = deps.advanceToNextBatch(currentBatchId, currentReCode)

    // Check if current lot can be reused
    const currentLot = deps.inventoryRows.value?.find((inv: any) => 
      inv.intake_lot_id === deps.selectedIntakeLotId.value &&
      inv.re_code === currentReCode
    )
    const canContinueWithSameLot = !!(currentLot && currentLot.remain_vol > 0 && currentLot.status === 'Active')

    if (canContinueWithSameLot) {
      // IMMEDIATE AUTO-CONTINUE (Bypass Dialog)
      const advanced = await nextBatchPromise
      deps.currentPackageOrigins.value = []
      
      if (advanced && deps.selectedReCode.value === currentReCode) {
         await fetchScanDialogItems()
         const pending = nextPendingItem.value
         if (pending) {
            $q.notify({ type: 'positive', message: `Continuing with Lot: ${deps.selectedIntakeLotId.value}`, position: 'top', timeout: 1500 })
            
            // Bypass Container Setup Dialog and go straight to Step 3
            deps.requireVolume.value = pending.required_volume || 0
            const ingInfo = deps.selectableIngredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
            const stdSize = ingInfo?.std_package_size || 0
            const contSize = stdSize > 0 ? Math.min(pending.required_volume, stdSize) : pending.required_volume
            
            deps.containerSize.value = contSize
            deps.packageSize.value = contSize

            const target = contSize || pending.required_volume || 0
            const sorted = [...deps.scalesComposable.scales.value].filter((s: any) => !s.isError).sort((a: any, b: any) => getScaleCapacity(a) - getScaleCapacity(b))
            const best = sorted.find((s: any) => getScaleCapacity(s) >= target) || sorted[sorted.length - 1]
            if (best?.id) deps.scalesComposable.selectedScale.value = best.id

            deps.onBatchIngredientClick({ batch_id: pending.batch_id }, { re_code: deps.selectedReCode.value, id: pending.req_id, required_volume: pending.required_volume, status: pending.status }, deps.selectedPlanDetails.value)
            
            workflowStep.value = 3
            pendingAdvance.value = null
            
            setTimeout(() => {
              const zeroThresh = (deps.activeScale.value?.tolerance || 0.01) * 2
              if (workflowStep.value === 3 && Math.abs(deps.actualScaleValue.value) <= zeroThresh) openTarePopup()
            }, 500)
            return
         }
      }
    }

    // fallback: dialog pops ONLY if out of powder
    $q.dialog({
      title: '✅ BATCH COMPLETE',
      message: `Batch <b>${currentBatchId}</b> — all packages done!<br/><br/>Next: <b>Re-scan intake lot</b> for ${currentReCode}<br/><span class="text-caption text-grey-7">(ensures correct & permissible lot is used)</span>`,
      ok: { label: 'Next Batch → Scan Lot', color: 'blue-10', unelevated: true },
      cancel: { label: 'Stop/Exit', flat: true, color: 'grey-7' },
      html: true, persistent: true
    }).onOk(async () => {
      const advanced = await nextBatchPromise
      deps.currentPackageOrigins.value = []
      
      deps.selectedIntakeLotId.value = ''
      if (deps.selectedReCode.value === currentReCode && advanced) {
        workflowStep.value = 2
        $q.notify({ type: 'warning', message: `Scan lot for: ${deps.selectedBatch.value?.batch_id}`, position: 'top' })
        setTimeout(() => openScanDialog(), 300)
      } else {
        workflowStep.value = deps.selectedReCode.value ? 2 : 1
      }
      pendingAdvance.value = null
    }).onCancel(() => {
      deps.selectedIntakeLotId.value = ''
      deps.selectedReCode.value = ''
      deps.currentPackageOrigins.value = []
      workflowStep.value = 1
      pendingAdvance.value = null
    })
  }

  const handleNextLot = () => {
    deps.scalesComposable.onAddLot(deps.selectedIntakeLotId, deps.selectableIngredients, deps.selectedInventoryItem)
    deps.selectedIntakeLotId.value = ''
    scanLotInput.value = ''
    scanLotValidated.value = false
    scanLotError.value = ''
    showScanDialog.value = true
    $q.notify({ type: 'info', message: 'Scan next intake lot to continue weighing', position: 'top', timeout: 2000 })
  }

  const onScaleSelect = (scale: any) => {
    const prev = deps.scalesComposable.selectedScale.value
    deps.scalesComposable.selectedScale.value = scale.id
    if (prev !== scale.id && workflowStep.value >= 3) {
      $q.notify({ type: 'warning', icon: 'scale', message: `⚖️ Switched to ${scale.label}`, caption: 'Please ensure the scale is tared', position: 'top', timeout: 4000, actions: [{ label: 'OK', color: 'white' }] })
    }
  }

  // ─── Scan Dialog ───
  const showScanDialog = ref(false)
  const mainLotInputRef = ref<any>(null)
  const scanDialogItems = ref<any[]>([])
  const scanDialogLoading = ref(false)
  const scanLotInput = ref('')
  const scanLotValidated = ref(false)
  const scanLotError = ref('')
  const dialogScanInputRef = ref<any>(null)

  // FIFO violation
  const showFifoViolationDialog = ref(false)
  const fifoViolationScannedLot = ref('')
  const fifoViolationExpectedLot = ref('')
  const fifoViolationExpectedExpiry = ref('')
  const fifoViolationScannedExpiry = ref('')

  // Container setup
  const showContainerSetupDialog = ref(false)
  const setupContainerSize = ref(0)
  const setupSelectedScale = ref(0)
  const setupMatchedIngredient = ref('')
  const setupMatchedLot = ref('')
  const setupPendingItem = ref<any>(null)
  const setupCalcPackages = computed(() => {
    if (setupContainerSize.value <= 0 || deps.requireVolume.value <= 0) return 0
    return Math.ceil(deps.requireVolume.value / setupContainerSize.value)
  })

  // Scan Full Lot
  const showScanFullLotDialog = ref(false)
  const scanFullLotPackageVol = ref(0)
  const scanFullLotInput = ref('')
  const scanFullLotScanned = ref<{ lot_id: string; volume: number; status: string; pkg_no: number }[]>([])
  const scanFullLotProcessing = ref(false)

  const scanFullLotCalc = computed(() => {
    const required = deps.remainVolume.value
    const pkgVol = scanFullLotPackageVol.value
    if (pkgVol <= 0 || required <= 0) return { fullPacks: 0, remainder: 0, totalFullVol: 0 }
    // Add small epsilon to prevent JS float precision from dropping a full pack (e.g. 0.609999 / 0.61)
    const fullPacks = Math.floor((required + 0.0001) / pkgVol)
    const totalFullVol = fullPacks * pkgVol
    const remainder = required - totalFullVol
    return { fullPacks, remainder: Math.round(remainder * 10000) / 10000, totalFullVol }
  })

  const scanFullLotRemaining = computed(() => {
    const scannedVol = scanFullLotScanned.value.reduce((s, o) => s + o.volume, 0)
    return Math.max(0, scanFullLotCalc.value.totalFullVol - scannedVol)
  })

  // Scan dialog tree & pagination
  const scanDialogTree = computed(() => {
    const grouped: Record<string, { plan_id: string; items: any[] }> = {}
    for (const item of scanDialogItems.value) {
      const pid = item.plan_id || '-'
      if (!grouped[pid]) grouped[pid] = { plan_id: pid, items: [] }
      grouped[pid].items.push(item)
    }
    return Object.values(grouped)
  })
  const scanDialogBatchPage = ref<Record<string, number>>({})
  const scanDialogBatchPerPage = 5
  const getScanDialogPage = (planId: string) => scanDialogBatchPage.value[planId] || 1
  const getScanDialogTotalPages = (items: any[]) => Math.ceil(items.length / scanDialogBatchPerPage) || 1
  const getPaginatedScanItems = (planId: string, items: any[]) => {
    const page = getScanDialogPage(planId)
    const start = (page - 1) * scanDialogBatchPerPage
    return items.slice(start, start + scanDialogBatchPerPage)
  }
  const setScanDialogPage = (planId: string, page: number) => {
    scanDialogBatchPage.value = { ...scanDialogBatchPage.value, [planId]: page }
  }

  const nextPendingItem = computed(() => scanDialogItems.value.find((item: any) => item.status !== 2))
  const scanProgress = computed(() => {
    const total = scanDialogItems.value.length
    const done = scanDialogItems.value.filter((i: any) => i.status === 2).length
    return { done, total }
  })
  const fifoRecommendedLot = computed(() => deps.filteredInventory.value.length === 0 ? null : deps.filteredInventory.value[0])

  const scanDialogIngInfo = computed(() => {
    if (!deps.selectedReCode.value) return null
    const ing = deps.ingredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
    const selIng = deps.selectableIngredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
    return {
      re_code: deps.selectedReCode.value,
      ingredient_name: selIng?.ingredient_name || ing?.name || deps.selectedReCode.value,
      mat_sap_code: ing?.mat_sap_code || '-',
      total_require: selIng?.batch_require || deps.requireVolume.value || 0,
    }
  })

  // ─── Sound ───
  const playSound = async (type: 'correct' | 'wrong') => {
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      await ctx.resume()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      if (type === 'correct') {
        osc.frequency.value = 880; osc.type = 'sine'; gain.gain.value = 0.1
        osc.start(); setTimeout(() => { osc.frequency.value = 1320 }, 100)
        setTimeout(() => { osc.stop(); ctx.close() }, 280)
      } else {
        osc.frequency.value = 200; osc.type = 'square'; gain.gain.value = 0.1
        osc.start(); setTimeout(() => { osc.frequency.value = 150 }, 150)
        setTimeout(() => { osc.stop(); ctx.close() }, 400)
      }
    } catch (e) { console.warn('Sound failed:', e) }
  }

  const handleScanError = (msg: string) => {
    scanLotError.value = msg; scanLotValidated.value = false; playSound('wrong')
    setTimeout(() => { scanLotInput.value = ''; scanLotError.value = '' }, 2000)
  }

  // ─── Fetch & Open ───
  const fetchScanDialogItems = async () => {
    if (!deps.selectedReCode.value || !deps.selectedProductionPlan.value) return
    scanDialogLoading.value = true
    try {
      const data = await $fetch<any[]>(
        `${appConfig.apiBaseUrl}/prebatch-items/batches-by-ingredient/${deps.selectedProductionPlan.value}/${encodeURIComponent(deps.selectedReCode.value)}`,
        { headers: getAuthHeader() }
      )
      scanDialogItems.value = data
    } catch (err) {
      console.error('Scan dialog fetch error:', err); scanDialogItems.value = []
    } finally { scanDialogLoading.value = false }
  }

  const startPreBatch = async (plan: any) => {
    await deps.onPlanShow(plan); await nextTick()
    deps.selectedReCode.value = ''; deps.selectedIntakeLotId.value = ''
    scanLotInput.value = ''; scanLotValidated.value = false; scanLotError.value = ''
    scanDialogItems.value = []; showScanDialog.value = true
  }

  const openScanDialog = async (ing?: any) => {
    if (ing) {
      if (deps.selectedIntakeLotId.value) deps.selectedIntakeLotId.value = ''
      deps.selectedReCode.value = ing.re_code
      deps.ingredientsComposable.onSelectIngredient(ing)
    }
    await fetchScanDialogItems()
    scanLotInput.value = ''; scanLotValidated.value = false; scanLotError.value = ''
    showScanDialog.value = true
  }

  const openScanFullLotDialog = () => {
    scanFullLotPackageVol.value = deps.packageSize.value || deps.containerSize.value || 0
    scanFullLotInput.value = ''; scanFullLotScanned.value = []; showScanFullLotDialog.value = true
  }

  // ─── Scan lot enter ───
  const onScanLotEnter = async () => {
    const scannedValue = scanLotInput.value.trim()
    if (!scannedValue || scanLotValidated.value) return

    const delimiter = scannedValue.includes('|') ? '|' : ','
    const parts = scannedValue.split(delimiter).map(p => p.trim()).filter(p => p.length > 0)
    if (parts.length < 2) return

    // Search inventory for this lot
    let matchedLot: any = null
    for (const part of parts) {
      const pUpper = part.toUpperCase()
      matchedLot = deps.inventoryRows.value.find((inv: any) =>
        inv.remain_vol > 0 && inv.status === 'Active' &&
        ((inv.intake_lot_id?.trim().toUpperCase() === pUpper) || (inv.lot_id?.trim().toUpperCase() === pUpper))
      )
      if (matchedLot) break
    }
    if (!matchedLot) {
      const scanDates = parts.filter(p => /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(p))
      if (scanDates.length > 0) {
        matchedLot = deps.inventoryRows.value.find((inv: any) =>
          inv.remain_vol > 0 && inv.status === 'Active' && scanDates.includes(formatDate(inv.expire_date))
        )
      }
    }
    if (!matchedLot) { handleScanError('Lot not found in inventory.'); return }

    // Validate ingredient is in plan
    const lotReCode = (matchedLot.re_code || '').trim().toUpperCase()
    const lotSapCode = (matchedLot.mat_sap_code || '').trim().toUpperCase()
    const matchedIngredient = deps.selectableIngredients.value.find((ing: any) => {
      const ingRe = (ing.re_code || '').trim().toUpperCase()
      const ingSap = (ing.mat_sap_code || '').trim().toUpperCase()
      return ingRe === lotReCode || (lotSapCode && ingSap === lotSapCode)
    })
    if (!matchedIngredient) { handleScanError(`"${matchedLot.re_code}" not required for this plan.`); return }

    const isNextLotMode = workflowStep.value === 4 && deps.selectedReCode.value
    if (isNextLotMode && matchedIngredient.re_code !== deps.selectedReCode.value) {
      handleScanError(`Wrong! Expected: ${deps.selectedReCode.value}, Got: ${matchedIngredient.re_code}`); return
    }
    if (!isNextLotMode && matchedIngredient.status === 2) {
      handleScanError(`"${matchedLot.re_code}" already completed.`); return
    }

    if (!isNextLotMode) {
      deps.selectedReCode.value = matchedIngredient.re_code
      deps.ingredientsComposable.onSelectIngredient(matchedIngredient)
      await nextTick()
    }

    // FIFO check
    const lotId = matchedLot.intake_lot_id
    if (matchedLot.status === 'Inactive' || matchedLot.status === 'Hold') {
      handleScanError(`Lot ${lotId} is ${matchedLot.status}.`); return
    }
    const usedLotIds = deps.currentPackageOrigins.value.map((o: any) => o.intake_lot_id.trim().toUpperCase())
    const fifoLots = deps.inventoryRows.value
      .filter((inv: any) => (inv.re_code || '').trim().toUpperCase() === lotReCode && inv.remain_vol > 0 && inv.status === 'Active')
      .filter((inv: any) => !usedLotIds.includes((inv.intake_lot_id || '').trim().toUpperCase()))
      .sort((a: any, b: any) => {
        const dA = parseDateSafe(a.expire_date)?.getTime() ?? Infinity
        const dB = parseDateSafe(b.expire_date)?.getTime() ?? Infinity
        if (dA !== dB) return dA - dB
        const iA = parseDateSafe(a.intake_at)?.getTime() ?? Infinity
        const iB = parseDateSafe(b.intake_at)?.getTime() ?? Infinity
        return iA !== iB ? iA - iB : (a.intake_lot_id || '').localeCompare(b.intake_lot_id || '')
      })

    if (fifoLots.length > 0 && lotId.trim().toUpperCase() !== fifoLots[0].intake_lot_id.trim().toUpperCase()) {
      fifoViolationScannedLot.value = lotId; fifoViolationScannedExpiry.value = formatDate(matchedLot.expire_date)
      fifoViolationExpectedLot.value = fifoLots[0].intake_lot_id; fifoViolationExpectedExpiry.value = formatDate(fifoLots[0].expire_date)
      showFifoViolationDialog.value = true; playSound('wrong')
      scanLotInput.value = ''; scanLotValidated.value = false
      setTimeout(() => { showFifoViolationDialog.value = false }, 5000)
      return
    }

    // Success
    scanLotError.value = ''; scanLotValidated.value = true
    deps.selectedIntakeLotId.value = lotId; deps.selectedInventoryItem.value = [matchedLot] as any
    playSound('correct')
    $q.notify({ type: 'positive', message: isNextLotMode ? `✅ Next lot: ${lotId}` : `✅ ${matchedIngredient.re_code} → ${lotId}`, position: 'top', timeout: 1500 })

    if (isNextLotMode) { showScanDialog.value = false; return }

    await fetchScanDialogItems()
    const pending = nextPendingItem.value
    if (pending) setTimeout(() => onScanItemSelect(pending), 400)
  }

  const onScanItemSelect = (item: any) => {
    if (item.status === 2) return
    showScanDialog.value = false
    deps.requireVolume.value = item.required_volume || 0
    const ingInfo = deps.selectableIngredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
    const stdSize = ingInfo?.std_package_size || 0

    setupMatchedIngredient.value = ingInfo?.ingredient_name || deps.selectedReCode.value
    setupMatchedLot.value = deps.selectedIntakeLotId.value
    setupPendingItem.value = item
    setupContainerSize.value = stdSize > 0 ? Math.min(item.required_volume, stdSize) : item.required_volume
    const target = setupContainerSize.value || item.required_volume || 0
    const sorted = [...deps.scalesComposable.scales.value].filter((s: any) => !s.isError).sort((a: any, b: any) => getScaleCapacity(a) - getScaleCapacity(b))
    const best = sorted.find((s: any) => getScaleCapacity(s) >= target) || sorted[sorted.length - 1]
    setupSelectedScale.value = best?.id || deps.scalesComposable.scales.value[0]?.id || 0
    showContainerSetupDialog.value = true
  }

  const confirmContainerSetup = () => {
    if (setupContainerSize.value <= 0 || !setupPendingItem.value) return
    deps.containerSize.value = setupContainerSize.value
    deps.packageSize.value = setupContainerSize.value
    if (setupSelectedScale.value) deps.scalesComposable.selectedScale.value = setupSelectedScale.value
    showContainerSetupDialog.value = false
    const item = setupPendingItem.value
    deps.onBatchIngredientClick({ batch_id: item.batch_id }, { re_code: deps.selectedReCode.value, id: item.req_id, required_volume: item.required_volume, status: item.status }, deps.selectedPlanDetails.value)
    if (workflowStep.value < 3) workflowStep.value = 3
    $q.notify({ type: 'info', message: `Weighing: ${item.batch_id}`, position: 'top', timeout: 2000 })
    setupPendingItem.value = null
    setTimeout(() => {
      const zeroThreshold = (deps.activeScale.value?.tolerance || 0.01) * 2
      if (workflowStep.value === 3 && Math.abs(deps.actualScaleValue.value) <= zeroThreshold) openTarePopup()
    }, 500)
  }

  const onScanFullLotEnter = async () => {
    const lotId = scanFullLotInput.value.trim()
    scanFullLotInput.value = ''
    if (!lotId || scanFullLotProcessing.value) return
    if (scanFullLotScanned.value.some(s => s.lot_id === lotId)) { $q.notify({ type: 'warning', message: `${lotId} already scanned`, position: 'top' }); return }
    if (scanFullLotScanned.value.length >= scanFullLotCalc.value.fullPacks) { $q.notify({ type: 'warning', message: 'All full packs scanned!', position: 'top' }); return }

    scanFullLotProcessing.value = true
    try {
      const inv = deps.inventoryRows.value.find((r: any) => r.intake_lot_id?.trim().toUpperCase() === lotId.toUpperCase() && r.re_code === deps.selectedReCode.value)
      if (!inv) { $q.notify({ type: 'negative', message: `${lotId} not found for ${deps.selectedReCode.value}`, position: 'top' }); return }
      const pkgVol = scanFullLotPackageVol.value
      const pkgNo = (deps.completedCount.value || 0) + scanFullLotScanned.value.length + 1
      const totalPkgs = scanFullLotCalc.value.fullPacks + (scanFullLotCalc.value.remainder > 0 ? 1 : 0)
      const batchId = deps.selectedBatch.value?.batch_id || ''
      const batchRecordId = `${batchId}-${deps.selectedReCode.value}-${pkgNo}`
      const reqItem = deps.prebatchItems.value.find((it: any) => it.batch_id === batchId && it.re_code === deps.selectedReCode.value)
      if (!reqItem) { $q.notify({ type: 'negative', message: 'PreBatch item not found', position: 'top' }); return }

      await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${reqItem.id}/pack`, {
        method: 'PUT', headers: getAuthHeader(),
        body: { batch_record_id: batchRecordId, package_no: pkgNo, total_packages: totalPkgs, net_volume: pkgVol, intake_lot_id: lotId, mat_sap_code: inv.mat_sap_code || '', recode_batch_id: String(pkgNo), origins: [{ intake_lot_id: lotId, mat_sap_code: inv.mat_sap_code || '', take_volume: pkgVol }] }
      })
      scanFullLotScanned.value.push({ lot_id: lotId, volume: pkgVol, status: 'ok', pkg_no: pkgNo })

      // Print label
      try {
        const ing = deps.ingredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
        const labelData = deps.buildLabelData({
          batch: deps.selectedBatch.value, planId: deps.selectedProductionPlan.value, plan: deps.selectedPlanDetails.value,
          reCode: deps.selectedReCode.value, ingName: ing?.ingredient_name || ing?.name || deps.selectedReCode.value,
          matSapCode: inv.mat_sap_code || '-', containerType: ing?.package_container_type || 'Bag',
          netVol: pkgVol, totalVol: deps.requireVolume.value, pkgNo, totalPkgs,
          qrCode: JSON.stringify({ b: batchId, m: inv.mat_sap_code || '', p: `${pkgNo}/${totalPkgs}`, n: pkgVol, t: deps.requireVolume.value }),
          timestamp: new Date().toLocaleString('en-GB'), origins: [{ intake_lot_id: lotId, mat_sap_code: inv.mat_sap_code || '', take_volume: pkgVol }],
        })
        const svg = await deps.generateLabelSvg('prebatch-label_4x3', labelData)
        if (svg) await deps.printLabel(svg)
      } catch (e) { console.warn('Label print failed:', e) }

      await deps.fetchPreBatchRecords()
      await deps.fetchPrebatchItems(batchId)
      $q.notify({ type: 'positive', message: `Pkg #${pkgNo}: ${lotId} — ${pkgVol} kg ✓`, position: 'top', timeout: 2000 })

      if (scanFullLotScanned.value.length >= scanFullLotCalc.value.fullPacks) {
        setTimeout(() => {
          showScanFullLotDialog.value = false
          const msg = scanFullLotCalc.value.remainder > 0 ? `All full lots done! Remaining ${scanFullLotCalc.value.remainder} kg — weigh on scale` : 'All packages complete!'
          $q.notify({ type: scanFullLotCalc.value.remainder > 0 ? 'info' : 'positive', message: msg, position: 'top', timeout: 4000 })
        }, 500)
      }
    } catch (err: any) {
      console.error('Scan Full Lot error:', err)
      $q.notify({ type: 'negative', message: err?.data?.detail || 'Failed to save', position: 'top' })
    }
    scanFullLotProcessing.value = false
  }

  const refreshPlanData = async () => {
    if (deps.selectedProductionPlan.value) {
      $q.notify({ type: 'info', message: 'Refreshing...', position: 'top', timeout: 500 })
      try {
        const rawSummary = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/summary-by-plan/${deps.selectedProductionPlan.value}`, {
            headers: deps.getAuthHeader() as Record<string, string>
        })
        deps.prebatchItems.value = rawSummary.map((item: any) => ({
            id: item.id || null,
            re_code: item.re_code || '-',
            ingredient_name: item.ingredient_name || item.name || '-',
            total_require: item.total_required ?? item.required_volume ?? 0,
            total_packaged: item.total_packaged || 0,
            wh: item.wh || item.warehouse || '-',
            status: item.status ?? 0,
            batch_count: item.batch_count || 1,
            per_batch: item.per_batch || item.required_volume || 0,
            completed_batches: item.completed_batches || 0
        }))
      } catch (err) { console.error('Error refreshing summary:', err) }
      if (deps.selectedReCode.value) await deps.fetchIngredientBatchDetail(deps.selectedReCode.value)
      await deps.fetchPreBatchRecords()
    }
  }

  // ─── Auto-focus scan input ───
  let scanFocusInterval: ReturnType<typeof setInterval> | null = null
  const startScanFocusInterval = () => {
    if (scanFocusInterval) return
    scanFocusInterval = setInterval(() => {
      if (showScanDialog.value && dialogScanInputRef.value) { dialogScanInputRef.value.focus(); return }
      if (workflowStep.value === 2 && mainLotInputRef.value) mainLotInputRef.value.focus()
    }, 500)
  }
  const stopScanFocusInterval = () => { if (scanFocusInterval) { clearInterval(scanFocusInterval); scanFocusInterval = null } }

  // ─── Watchers ───
  // Auto-process scanner input
  watch(scanLotInput, (newVal) => {
    if (!newVal || scanLotValidated.value) return
    const hasDelim = newVal.includes('|') || newVal.includes(',')
    if (hasDelim) {
      const segCount = newVal.includes('|') ? newVal.split('|').length : newVal.split(',').length
      if (segCount >= 2) onScanLotEnter()
    }
  })

  // Auto-update scale when container size changes
  watch(setupContainerSize, (newSize) => {
    if (!showContainerSetupDialog.value || newSize <= 0) return
    const sorted = [...deps.scalesComposable.scales.value].filter((s: any) => !s.isError).sort((a: any, b: any) => getScaleCapacity(a) - getScaleCapacity(b))
    const best = sorted.find((s: any) => getScaleCapacity(s) >= newSize) || sorted[sorted.length - 1]
    if (best) setupSelectedScale.value = best.id
  })

  return {
    // Workflow state
    workflowStep, pendingAdvance, workflowStatus,
    // Tare / Confirm
    showTarePopup, selectedTareScale, showConfirmStartPopup,
    openTarePopup, closeTarePopupAndAdvance, handleTareAndAdvance, confirmStartWeighing,
    handleStartWeighting, isScaleAtZero, getScaleCapacity,
    // Actions
    handleDoneClick, handleStep7Confirm, handleStopPreBatch, handleNextLot, onScaleSelect,
    // Scan dialog
    showScanDialog, mainLotInputRef, scanDialogItems, scanDialogLoading,
    scanLotInput, scanLotValidated, scanLotError, dialogScanInputRef,
    scanDialogTree, scanDialogBatchPage, getScanDialogPage, getScanDialogTotalPages,
    getPaginatedScanItems, setScanDialogPage,
    nextPendingItem, scanProgress, fifoRecommendedLot, scanDialogIngInfo,
    startPreBatch, openScanDialog, onScanLotEnter, onScanItemSelect, fetchScanDialogItems,
    // FIFO violation
    showFifoViolationDialog, fifoViolationScannedLot, fifoViolationExpectedLot,
    fifoViolationExpectedExpiry, fifoViolationScannedExpiry,
    // Container setup
    showContainerSetupDialog, setupContainerSize, setupSelectedScale,
    setupMatchedIngredient, setupMatchedLot, setupPendingItem, setupCalcPackages,
    confirmContainerSetup,
    // Scan Full Lot
    showScanFullLotDialog, scanFullLotPackageVol, scanFullLotInput,
    scanFullLotScanned, scanFullLotProcessing, scanFullLotCalc, scanFullLotRemaining,
    openScanFullLotDialog, onScanFullLotEnter,
    // Utility
    playSound, handleScanError, refreshPlanData,
    startScanFocusInterval, stopScanFocusInterval,
  }
}

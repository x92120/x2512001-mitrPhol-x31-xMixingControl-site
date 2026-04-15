/**
 * Module tests for usePreBatchWorkflow
 *
 * Tests cover:
 *   1. Workflow state initialisation
 *   2. workflowStatus computed
 *   3. Scale capacity helper
 *   4. Auto-select best scale
 *   5. Tare popup open/close/advance
 *   6. Start weighing (confirmStartWeighing / handleStartWeighting)
 *   7. isScaleAtZero tolerance logic
 *   8. Done click → step 7 + pendingAdvance
 *   9. Step 7 confirm - continue packages
 *  10. Step 7 confirm - advance to next batch
 *  11. Stop pre-batch dialog
 *  12. Scan dialog open / fetch / tree grouping
 *  13. Scan lot validation & FIFO checks
 *  14. Container setup confirm
 *  15. Scan-full-lot calculations
 *  16. handleNextLot
 *  17. onScaleSelect with notification
 *  18. refreshPlanData
 *  19. Sound fallback (no AudioContext crash)
 *  20. handleScanError resets after timeout
 *  21. Scan dialog pagination helpers
 *  22. scanDialogIngInfo computed
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, computed, nextTick } from 'vue'

// ── Stub Nuxt's $fetch globally ──
const $fetchMock = vi.fn()
;(globalThis as any).$fetch = $fetchMock

// ── Stub appConfig ──
vi.mock('~/appConfig/config', () => ({
  appConfig: { apiBaseUrl: 'http://test:8001' },
}))

import { usePreBatchWorkflow, type WorkflowDeps } from './usePreBatchWorkflow'

// ─────────────────────────────────────────────────
// Helpers to build a fresh deps object per test
// ─────────────────────────────────────────────────
function createMockDeps(overrides: Partial<WorkflowDeps> = {}): WorkflowDeps {
  const scales = ref([
    { id: 1, label: 'Scale 1 (10 Kg)', value: 0, isError: false, tolerance: 0.02 },
    { id: 2, label: 'Scale 2 (30 Kg)', value: 0, isError: false, tolerance: 0.02 },
    { id: 3, label: 'Scale 3 (150 Kg)', value: 0, isError: false, tolerance: 0.02 },
  ])
  const selectedScale = ref(0)

  const notifySpy = vi.fn()
  const dialogOnOkCb = { onOk: vi.fn().mockReturnThis(), onCancel: vi.fn().mockReturnThis(), onDismiss: vi.fn().mockReturnThis() }
  const dialogSpy = vi.fn().mockReturnValue(dialogOnOkCb)

  return {
    $q: { notify: notifySpy, dialog: dialogSpy },
    getAuthHeader: () => ({ Authorization: 'Bearer test' }),
    t: (key: string) => key,
    formatDate: (d: any) => (d instanceof Date ? d.toISOString().slice(0, 10) : String(d)),
    parseDateSafe: (d: any) => (d ? new Date(d) : null),

    selectedReCode: ref(''),
    selectedIntakeLotId: ref(''),
    selectedInventoryItem: ref(null),
    requireVolume: ref(0),
    packageSize: ref(0),
    containerSize: ref(0),
    ingredients: ref([]),
    prebatchItems: ref([]),
    inventoryRows: ref([]),
    filteredInventory: ref([]),
    selectableIngredients: ref([]),
    selectedBatch: ref(null),
    selectedProductionPlan: ref(''),
    selectedPlanDetails: ref(null),
    currentPackageOrigins: ref([]),
    remainVolume: ref(0),
    actualScaleValue: ref(0),
    activeScale: ref({ tolerance: 0.02 }),
    lastCapturedWeight: ref(0),
    batchedVolume: ref(0),
    completedCount: ref(0),
    nextPackageNo: ref(1),
    preBatchLogs: ref([]),
    selectedPreBatchLogs: ref([]),
    totalCompletedWeight: ref(0),
    productionPlans: ref([]),
    ingredientBatchDetail: ref(null),

    scalesComposable: {
      scales,
      selectedScale,
      onTare: vi.fn(),
      onAddLot: vi.fn(),
    },
    ingredientsComposable: {
      onSelectIngredient: vi.fn(),
    },

    getPackagePlan: vi.fn().mockReturnValue([]),
    fetchPreBatchRecords: vi.fn().mockResolvedValue(undefined),
    fetchPrebatchItems: vi.fn().mockResolvedValue(undefined),
    fetchIngredientBatchDetail: vi.fn().mockResolvedValue(undefined),
    updatePrebatchItemStatus: vi.fn().mockResolvedValue(undefined),
    advanceToNextBatch: vi.fn().mockResolvedValue({ ok: true }),
    onPlanShow: vi.fn().mockResolvedValue(undefined),
    onBatchIngredientClick: vi.fn().mockResolvedValue(undefined),
    onBatchExpand: vi.fn(),
    requestBatch: ref(1),

    buildLabelData: vi.fn().mockReturnValue({}),
    generateLabelSvg: vi.fn().mockResolvedValue('<svg></svg>'),
    printLabel: vi.fn().mockResolvedValue(undefined),
    onDone: vi.fn().mockResolvedValue(undefined),

    ...overrides,
  }
}

// ══════════════════════════════════════════════════
//  TESTS
// ══════════════════════════════════════════════════

describe('usePreBatchWorkflow', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    $fetchMock.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  // ──────────────────────
  // 1. Initialisation
  // ──────────────────────
  describe('initialisation', () => {
    it('should initialise workflowStep to 1 and pendingAdvance to null', () => {
      const { workflowStep, pendingAdvance } = usePreBatchWorkflow(createMockDeps())
      expect(workflowStep.value).toBe(1)
      expect(pendingAdvance.value).toBeNull()
    })

    it('should return all expected keys', () => {
      const wf = usePreBatchWorkflow(createMockDeps())
      const expectedKeys = [
        'workflowStep', 'pendingAdvance', 'workflowStatus',
        'showTarePopup', 'selectedTareScale', 'showConfirmStartPopup',
        'openTarePopup', 'closeTarePopupAndAdvance', 'handleTareAndAdvance', 'confirmStartWeighing',
        'handleStartWeighting', 'isScaleAtZero', 'getScaleCapacity',
        'handleDoneClick', 'handleStep7Confirm', 'handleStopPreBatch', 'handleNextLot', 'onScaleSelect',
        'showScanDialog', 'mainLotInputRef', 'scanDialogItems', 'scanDialogLoading',
        'scanLotInput', 'scanLotValidated', 'scanLotError', 'dialogScanInputRef',
        'scanDialogTree', 'scanDialogBatchPage', 'getScanDialogPage', 'getScanDialogTotalPages',
        'getPaginatedScanItems', 'setScanDialogPage',
        'nextPendingItem', 'scanProgress', 'fifoRecommendedLot', 'scanDialogIngInfo',
        'startPreBatch', 'openScanDialog', 'onScanLotEnter', 'onScanItemSelect', 'fetchScanDialogItems',
        'showFifoViolationDialog', 'fifoViolationScannedLot', 'fifoViolationExpectedLot',
        'fifoViolationExpectedExpiry', 'fifoViolationScannedExpiry',
        'showContainerSetupDialog', 'setupContainerSize', 'setupSelectedScale',
        'setupMatchedIngredient', 'setupMatchedLot', 'setupPendingItem', 'setupCalcPackages',
        'confirmContainerSetup',
        'showScanFullLotDialog', 'scanFullLotPackageVol', 'scanFullLotInput',
        'scanFullLotScanned', 'scanFullLotProcessing', 'scanFullLotCalc', 'scanFullLotRemaining',
        'openScanFullLotDialog', 'onScanFullLotEnter',
        'playSound', 'handleScanError', 'refreshPlanData',
        'startScanFocusInterval', 'stopScanFocusInterval',
      ]
      for (const k of expectedKeys) {
        expect(wf).toHaveProperty(k)
      }
    })
  })

  // ──────────────────────
  // 2. workflowStatus computed
  // ──────────────────────
  describe('workflowStatus', () => {
    it('returns "Select Ingredient" when no reCode', () => {
      const deps = createMockDeps()
      const { workflowStatus } = usePreBatchWorkflow(deps)
      expect(workflowStatus.value.id).toBe(2)
      expect(workflowStatus.value.msg).toContain('Scan Intake Lot ID')
    })

    it('returns "Scan Intake Lot" when reCode set but no intakeLotId', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      const { workflowStatus } = usePreBatchWorkflow(deps)
      expect(workflowStatus.value.id).toBe(2)
      expect(workflowStatus.value.msg).toContain('Scan Intake Lot ID')
    })

    it('returns step 3 status when reCode + intakeLotId + step 3', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectedIntakeLotId.value = 'LOT-123'
      const { workflowStep, workflowStatus } = usePreBatchWorkflow(deps)
      workflowStep.value = 3
      expect(workflowStatus.value.id).toBe(3)
      expect(workflowStatus.value.msg).toContain('Select Scale & Tare to 0.00 kg')
    })

    it('returns step 4 "Manual Weighing in Progress"', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectedIntakeLotId.value = 'LOT-123'
      const { workflowStep, workflowStatus } = usePreBatchWorkflow(deps)
      workflowStep.value = 4
      expect(workflowStatus.value.id).toBe(6)
      expect(workflowStatus.value.msg).toContain('Batching in Progress')
    })

    it('returns step 7 "Package Complete - Clear Scale"', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectedIntakeLotId.value = 'LOT-123'
      const { workflowStep, workflowStatus } = usePreBatchWorkflow(deps)
      workflowStep.value = 7
      expect(workflowStatus.value.id).toBe(7)
      expect(workflowStatus.value.msg).toContain('Done, Clear Scale -> Next')
    })
  })

  // ──────────────────────
  // 3. getScaleCapacity
  // ──────────────────────
  describe('getScaleCapacity', () => {
    it('extracts numeric Kg capacity from label', () => {
      const { getScaleCapacity } = usePreBatchWorkflow(createMockDeps())
      expect(getScaleCapacity({ label: 'Scale 1 (10 Kg)' })).toBe(10)
      expect(getScaleCapacity({ label: 'Scale 2 (30 Kg)' })).toBe(30)
      expect(getScaleCapacity({ label: 'Scale 3 (150 Kg)' })).toBe(150)
    })

    it('parses lowercase kg', () => {
      const { getScaleCapacity } = usePreBatchWorkflow(createMockDeps())
      expect(getScaleCapacity({ label: 'Bench 5kg' })).toBe(5)
    })

    it('returns 999 when no kg pattern found', () => {
      const { getScaleCapacity } = usePreBatchWorkflow(createMockDeps())
      expect(getScaleCapacity({ label: 'Unknown scale' })).toBe(999)
    })
  })

  // ──────────────────────
  // 4. Auto-select best scale
  // ──────────────────────
  describe('autoSelectBestScale (via openTarePopup)', () => {
    it('selects the smallest suitable scale based on packageSize', () => {
      const deps = createMockDeps()
      deps.packageSize.value = 25
      const { openTarePopup, selectedTareScale } = usePreBatchWorkflow(deps)
      openTarePopup()
      // 30 Kg scale is the smallest that fits 25
      expect(selectedTareScale.value).toBe(2)
      expect(deps.scalesComposable.selectedScale.value).toBe(2)
    })

    it('falls back to the largest scale when none are big enough', () => {
      const deps = createMockDeps()
      deps.packageSize.value = 200
      const { openTarePopup, selectedTareScale } = usePreBatchWorkflow(deps)
      openTarePopup()
      expect(selectedTareScale.value).toBe(3) // 150 Kg is the largest
    })

    it('skips error scales', () => {
      const deps = createMockDeps()
      deps.packageSize.value = 5
      // Mark 10 Kg scale as error
      deps.scalesComposable.scales.value[0].isError = true
      const { openTarePopup, selectedTareScale } = usePreBatchWorkflow(deps)
      openTarePopup()
      // Next smallest non-error scale is 30 Kg
      expect(selectedTareScale.value).toBe(2)
    })
  })

  // ──────────────────────
  // 5. Tare popup lifecycle
  // ──────────────────────
  describe('tare popup lifecycle', () => {
    it('opens tare popup', () => {
      const deps = createMockDeps()
      const { openTarePopup, showTarePopup } = usePreBatchWorkflow(deps)
      openTarePopup()
      expect(showTarePopup.value).toBe(true)
    })

    it('closeTarePopupAndAdvance closes popup and sets selected scale', () => {
      const deps = createMockDeps()
      const { openTarePopup, closeTarePopupAndAdvance, showTarePopup, selectedTareScale } = usePreBatchWorkflow(deps)
      openTarePopup()
      selectedTareScale.value = 2
      closeTarePopupAndAdvance()
      expect(showTarePopup.value).toBe(false)
      expect(deps.scalesComposable.selectedScale.value).toBe(2)
    })

    it('handleTareAndAdvance calls onTare and closes', () => {
      const deps = createMockDeps()
      const { openTarePopup, handleTareAndAdvance, selectedTareScale, showTarePopup } = usePreBatchWorkflow(deps)
      openTarePopup()
      selectedTareScale.value = 1
      handleTareAndAdvance()
      expect(deps.scalesComposable.onTare).toHaveBeenCalledWith(1)
      expect(showTarePopup.value).toBe(false)
    })
  })

  // ──────────────────────
  // 6. Start weighing
  // ──────────────────────
  describe('start weighing', () => {
    it('confirmStartWeighing moves to step 4', () => {
      const { confirmStartWeighing, workflowStep, showConfirmStartPopup } = usePreBatchWorkflow(createMockDeps())
      showConfirmStartPopup.value = true
      confirmStartWeighing()
      expect(workflowStep.value).toBe(4)
      expect(showConfirmStartPopup.value).toBe(false)
    })

    it('handleStartWeighting directly sets step 4', () => {
      const { handleStartWeighting, workflowStep } = usePreBatchWorkflow(createMockDeps())
      handleStartWeighting()
      expect(workflowStep.value).toBe(4)
    })
  })

  // ──────────────────────
  // 7. isScaleAtZero
  // ──────────────────────
  describe('isScaleAtZero', () => {
    it('true when scale value is within 2x tolerance of zero', () => {
      const deps = createMockDeps()
      deps.activeScale.value = { tolerance: 0.01 }
      deps.actualScaleValue.value = 0.015
      const { isScaleAtZero } = usePreBatchWorkflow(deps)
      expect(isScaleAtZero.value).toBe(true) // 0.015 <= 0.02
    })

    it('false when scale value exceeds 2x tolerance', () => {
      const deps = createMockDeps()
      deps.activeScale.value = { tolerance: 0.01 }
      deps.actualScaleValue.value = 0.03
      const { isScaleAtZero } = usePreBatchWorkflow(deps)
      expect(isScaleAtZero.value).toBe(false) // 0.03 > 0.02
    })

    it('true for negative weights within tolerance', () => {
      const deps = createMockDeps()
      deps.activeScale.value = { tolerance: 0.02 }
      deps.actualScaleValue.value = -0.03
      const { isScaleAtZero } = usePreBatchWorkflow(deps)
      expect(isScaleAtZero.value).toBe(true) // abs(-0.03) = 0.03 <= 0.04
    })
  })

  // ──────────────────────
  // 8. handleDoneClick
  // ──────────────────────
  describe('handleDoneClick', () => {
    it('captures weight, calls onDone, sets step 7, stores pendingAdvance', async () => {
      const deps = createMockDeps()
      deps.actualScaleValue.value = 5.1234
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'FH-001'

      const { handleDoneClick, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      await handleDoneClick()

      expect(deps.lastCapturedWeight.value).toBe(5.1234)
      expect(deps.onDone).toHaveBeenCalledWith(true)
      expect(workflowStep.value).toBe(7)
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'FH-001' })
    })
  })

  // ──────────────────────
  // 9. Step 7 confirm – continue packages
  // ──────────────────────
  describe('handleStep7Confirm – continue packages', () => {
    it('returns to step 3 when batch has more pending packages', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 10 // not finished
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'FH-001'
      deps.requireVolume.value = 20
      ;(deps.getPackagePlan as any).mockReturnValue([
        { status: 'completed' },
        { status: 'pending' },
      ])

      const { handleStep7Confirm, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 7
      handleStep7Confirm()

      expect(workflowStep.value).toBe(3)
      expect(deps.currentPackageOrigins.value).toEqual([])
      expect(deps.$q.notify).toHaveBeenCalled()
    })
  })

  // ──────────────────────
  // 10. Step 7 confirm – advance to next batch
  // ──────────────────────
  describe('handleStep7Confirm – advance', () => {
    it('advances when batch finished (remainVolume ≈ 0)', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 0 // finished
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'FH-001'
      deps.requireVolume.value = 20
      ;(deps.getPackagePlan as any).mockReturnValue([
        { status: 'completed' },
      ])

      const { handleStep7Confirm, pendingAdvance, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 7
      pendingAdvance.value = { batchId: 'B-001', reCode: 'FH-001' }
      handleStep7Confirm()

      // Should open a dialog (advance internal path)
      expect(deps.$q.dialog).toHaveBeenCalled()
    })
  })

  // ──────────────────────
  // 11. Stop pre-batch
  // ──────────────────────
  describe('handleStopPreBatch', () => {
    it('opens a confirmation dialog', () => {
      const deps = createMockDeps()
      const { handleStopPreBatch } = usePreBatchWorkflow(deps)
      handleStopPreBatch()
      expect(deps.$q.dialog).toHaveBeenCalled()
      const dialogArg = (deps.$q.dialog as any).mock.calls[0][0]
      expect(dialogArg.title).toContain('STOP')
    })
  })

  // ──────────────────────
  // 12. Scan dialog tree & pagination
  // ──────────────────────
  describe('scan dialog tree and pagination', () => {
    it('groups items by plan_id', () => {
      const deps = createMockDeps()
      const { scanDialogItems, scanDialogTree } = usePreBatchWorkflow(deps)
      scanDialogItems.value = [
        { plan_id: 'P1', batch_id: 'B1' },
        { plan_id: 'P1', batch_id: 'B2' },
        { plan_id: 'P2', batch_id: 'B3' },
      ]
      expect(scanDialogTree.value).toHaveLength(2)
      expect(scanDialogTree.value[0].items).toHaveLength(2)
      expect(scanDialogTree.value[1].items).toHaveLength(1)
    })

    it('paginates items correctly', () => {
      const { scanDialogItems, getPaginatedScanItems, getScanDialogPage, getScanDialogTotalPages, setScanDialogPage } = usePreBatchWorkflow(createMockDeps())
      const items = Array.from({ length: 12 }, (_, i) => ({ plan_id: 'P1', batch_id: `B${i}` }))
      scanDialogItems.value = items

      expect(getScanDialogPage('P1')).toBe(1)
      expect(getScanDialogTotalPages(items)).toBe(3) // ceil(12/5)

      const page1 = getPaginatedScanItems('P1', items)
      expect(page1).toHaveLength(5)

      setScanDialogPage('P1', 3)
      const page3 = getPaginatedScanItems('P1', items)
      expect(page3).toHaveLength(2) // items 10-11
    })
  })

  // ──────────────────────
  // 13. Scan lot validation & FIFO
  // ──────────────────────
  describe('onScanLotEnter', () => {
    it('does nothing on empty input', async () => {
      const deps = createMockDeps()
      const { onScanLotEnter, scanLotInput } = usePreBatchWorkflow(deps)
      scanLotInput.value = ''
      await onScanLotEnter()
      expect(deps.$q.notify).not.toHaveBeenCalled()
    })

    it('does nothing when already validated', async () => {
      const deps = createMockDeps()
      const { onScanLotEnter, scanLotInput, scanLotValidated } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-1|DATA'
      scanLotValidated.value = true
      await onScanLotEnter()
      expect(deps.$q.notify).not.toHaveBeenCalled()
    })

    it('returns early if fewer than 2 parts', async () => {
      const deps = createMockDeps()
      const { onScanLotEnter, scanLotInput } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'SINGLEVALUE'
      await onScanLotEnter()
      expect(deps.$q.notify).not.toHaveBeenCalled()
    })

    it('shows error when lot not found in inventory', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [] // empty inventory
      const { onScanLotEnter, scanLotInput, scanLotError } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-999|SOME-DATA'
      await onScanLotEnter()
      // After handleScanError is called, scanLotError should be set
      expect(scanLotError.value).toContain('not found')
    })

    it('matches lot by intake_lot_id and validates ingredient in plan', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-001', lot_id: 'LTID-001', re_code: 'FH-001', mat_sap_code: 'SAP1', remain_vol: 100, status: 'Active', expire_date: '2026-12-31' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'FH-001', mat_sap_code: 'SAP1', ingredient_name: 'Test Ing', status: 0 },
      ]
      deps.selectedProductionPlan.value = 'PLAN-1'
      $fetchMock.mockResolvedValue([])

      const { onScanLotEnter, scanLotInput, scanLotValidated } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-001|FH-001'
      await onScanLotEnter()

      expect(scanLotValidated.value).toBe(true)
      expect(deps.selectedIntakeLotId.value).toBe('LOT-001')
      expect(deps.selectedReCode.value).toBe('FH-001')
    })

    it('detects FIFO violation when scanned lot is not the earliest expiry', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-OLD', re_code: 'FH-001', mat_sap_code: 'SAP1', remain_vol: 50, status: 'Active', expire_date: '2026-01-01' },
        { intake_lot_id: 'LOT-NEW', re_code: 'FH-001', mat_sap_code: 'SAP1', remain_vol: 50, status: 'Active', expire_date: '2026-12-31' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'FH-001', mat_sap_code: 'SAP1', ingredient_name: 'Test Ing', status: 0 },
      ]
      deps.currentPackageOrigins.value = []

      const { onScanLotEnter, scanLotInput, showFifoViolationDialog, fifoViolationExpectedLot, fifoViolationScannedLot } = usePreBatchWorkflow(deps)
      // Scan the NEWER lot (FIFO violation)
      scanLotInput.value = 'LOT-NEW|FH-001'
      await onScanLotEnter()

      expect(showFifoViolationDialog.value).toBe(true)
      expect(fifoViolationExpectedLot.value).toBe('LOT-OLD')
      expect(fifoViolationScannedLot.value).toBe('LOT-NEW')
    })

    it('rejects inactive/hold lots', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-HOLD', re_code: 'FH-001', mat_sap_code: 'SAP1', remain_vol: 50, status: 'Active', expire_date: '2026-06-01' },
      ]
      // Mark matching lot as Hold
      deps.inventoryRows.value[0].status = 'Hold'
      deps.selectableIngredients.value = [
        { re_code: 'FH-001', mat_sap_code: 'SAP1', ingredient_name: 'Test Ing', status: 0 },
      ]

      const { onScanLotEnter, scanLotInput, scanLotError } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-HOLD|FH-001'
      await onScanLotEnter()

      // lot is found, but status check still needs the Active match
      // Since inventory search requires status === 'Active', lot won't be found
      expect(scanLotError.value).toContain('not found')
    })

    it('rejects already-completed ingredient', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-DONE', re_code: 'FH-002', mat_sap_code: 'SAP2', remain_vol: 10, status: 'Active', expire_date: '2026-06-01' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'FH-002', mat_sap_code: 'SAP2', ingredient_name: 'Done Ing', status: 2 },
      ]

      const { onScanLotEnter, scanLotInput, scanLotError } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-DONE|FH-002'
      await onScanLotEnter()

      expect(scanLotError.value).toContain('already completed')
    })

    it('validates wrong ingredient in next-lot mode', async () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-OTHER', re_code: 'FH-999', mat_sap_code: 'SAP999', remain_vol: 10, status: 'Active', expire_date: '2026-06-01' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'FH-999', mat_sap_code: 'SAP999', ingredient_name: 'Wrong Ing', status: 0 },
      ]

      const { onScanLotEnter, scanLotInput, workflowStep, scanLotError } = usePreBatchWorkflow(deps)
      workflowStep.value = 4 // next-lot mode
      scanLotInput.value = 'LOT-OTHER|FH-999'
      await onScanLotEnter()

      expect(scanLotError.value).toContain('Wrong')
    })
  })

  // ──────────────────────
  // 14. Container setup
  // ──────────────────────
  describe('confirmContainerSetup', () => {
    it('does nothing when containerSize is 0', () => {
      const deps = createMockDeps()
      const { confirmContainerSetup, setupContainerSize, showContainerSetupDialog } = usePreBatchWorkflow(deps)
      setupContainerSize.value = 0
      showContainerSetupDialog.value = true
      confirmContainerSetup()
      expect(showContainerSetupDialog.value).toBe(true) // unchanged
    })

    it('sets containerSize, packageSize, selectedScale and closes dialog', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectableIngredients.value = [{ re_code: 'FH-001', ingredient_name: 'Test' }]
      deps.selectedPlanDetails.value = { plan_id: 'P1' }

      const { confirmContainerSetup, setupContainerSize, setupSelectedScale, showContainerSetupDialog, setupPendingItem, workflowStep } = usePreBatchWorkflow(deps)
      showContainerSetupDialog.value = true
      setupContainerSize.value = 5
      setupSelectedScale.value = 1
      setupPendingItem.value = { batch_id: 'B-001', req_id: 'R1', required_volume: 10, status: 0 }
      workflowStep.value = 2

      confirmContainerSetup()

      expect(showContainerSetupDialog.value).toBe(false)
      expect(deps.containerSize.value).toBe(5)
      expect(deps.packageSize.value).toBe(5)
      expect(deps.scalesComposable.selectedScale.value).toBe(1)
      expect(workflowStep.value).toBe(3)
      expect(deps.onBatchIngredientClick).toHaveBeenCalled()
    })
  })

  // ──────────────────────
  // 15. Scan Full Lot calculations
  // ──────────────────────
  describe('scan full lot', () => {
    it('calculates full packs and remainder', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 23
      deps.packageSize.value = 5

      const { openScanFullLotDialog, scanFullLotPackageVol, scanFullLotCalc } = usePreBatchWorkflow(deps)
      openScanFullLotDialog()
      expect(scanFullLotPackageVol.value).toBe(5)
      expect(scanFullLotCalc.value.fullPacks).toBe(4) // floor(23/5)
      expect(scanFullLotCalc.value.totalFullVol).toBe(20)
      expect(scanFullLotCalc.value.remainder).toBe(3)
    })

    it('remaining decreases as lots are scanned', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 10
      deps.packageSize.value = 5

      const { openScanFullLotDialog, scanFullLotScanned, scanFullLotRemaining, scanFullLotCalc } = usePreBatchWorkflow(deps)
      openScanFullLotDialog()
      // 2 full packs, totalFullVol = 10
      expect(scanFullLotCalc.value.fullPacks).toBe(2)
      expect(scanFullLotRemaining.value).toBe(10)

      scanFullLotScanned.value.push({ lot_id: 'L1', volume: 5, status: 'ok', pkg_no: 1 })
      expect(scanFullLotRemaining.value).toBe(5)

      scanFullLotScanned.value.push({ lot_id: 'L2', volume: 5, status: 'ok', pkg_no: 2 })
      expect(scanFullLotRemaining.value).toBe(0)
    })
  })

  // ──────────────────────
  // 16. setupCalcPackages
  // ──────────────────────
  describe('setupCalcPackages', () => {
    it('computes number of packages from containerSize and requireVolume', () => {
      const deps = createMockDeps()
      deps.requireVolume.value = 23

      const { setupCalcPackages, setupContainerSize } = usePreBatchWorkflow(deps)
      setupContainerSize.value = 5
      expect(setupCalcPackages.value).toBe(5) // ceil(23/5)
    })

    it('returns 0 when containerSize is 0', () => {
      const deps = createMockDeps()
      deps.requireVolume.value = 10

      const { setupCalcPackages, setupContainerSize } = usePreBatchWorkflow(deps)
      setupContainerSize.value = 0
      expect(setupCalcPackages.value).toBe(0)
    })
  })

  // ──────────────────────
  // 17. handleNextLot
  // ──────────────────────
  describe('handleNextLot', () => {
    it('calls onAddLot and resets scan state, opens scan dialog', () => {
      const deps = createMockDeps()
      const { handleNextLot, scanLotInput, scanLotValidated, scanLotError, showScanDialog } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'old-value'
      scanLotValidated.value = true
      scanLotError.value = 'old-error'

      handleNextLot()

      expect(deps.scalesComposable.onAddLot).toHaveBeenCalled()
      expect(deps.selectedIntakeLotId.value).toBe('')
      expect(scanLotInput.value).toBe('')
      expect(scanLotValidated.value).toBe(false)
      expect(scanLotError.value).toBe('')
      expect(showScanDialog.value).toBe(true)
    })
  })

  // ──────────────────────
  // 18. onScaleSelect
  // ──────────────────────
  describe('onScaleSelect', () => {
    it('updates selected scale and notifies when changing during workflow', () => {
      const deps = createMockDeps()
      deps.scalesComposable.selectedScale.value = 1

      const { onScaleSelect, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 4

      onScaleSelect({ id: 2, label: 'Scale 2 (30 Kg)' })

      expect(deps.scalesComposable.selectedScale.value).toBe(2)
      expect(deps.$q.notify).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'warning' })
      )
    })

    it('does NOT notify when selecting same scale', () => {
      const deps = createMockDeps()
      deps.scalesComposable.selectedScale.value = 1

      const { onScaleSelect, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 4
      onScaleSelect({ id: 1, label: 'Scale 1 (10 Kg)' })
      // prev was already set to 1 first line, then we set it to 1 again -> prev===scale.id -> no warning
      expect(deps.$q.notify).not.toHaveBeenCalled()
    })

    it('does NOT warn before step 3', () => {
      const deps = createMockDeps()
      deps.scalesComposable.selectedScale.value = 1

      const { onScaleSelect, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 1
      onScaleSelect({ id: 2, label: 'Scale 2' })
      expect(deps.$q.notify).not.toHaveBeenCalled()
    })
  })

  // ──────────────────────
  // 19. refreshPlanData
  // ──────────────────────
  describe('refreshPlanData', () => {
    it('calls fetch functions when plan is selected', async () => {
      const deps = createMockDeps()
      deps.selectedProductionPlan.value = 'PLAN-1'
      deps.selectedReCode.value = 'FH-001'

      const { refreshPlanData } = usePreBatchWorkflow(deps)
      await refreshPlanData()

      expect(deps.$q.notify).toHaveBeenCalledWith(expect.objectContaining({ message: 'Refreshing...' }))
      expect((global as any).$fetch).toHaveBeenCalledWith(expect.stringContaining('/prebatch-items/summary-by-plan/PLAN-1'), expect.anything())
      expect(deps.fetchIngredientBatchDetail).toHaveBeenCalledWith('FH-001')
      expect(deps.fetchPreBatchRecords).toHaveBeenCalled()
    })

    it('does nothing when no plan is selected', async () => {
      const deps = createMockDeps()
      deps.selectedProductionPlan.value = ''

      const { refreshPlanData } = usePreBatchWorkflow(deps)
      await refreshPlanData()

      expect(deps.fetchIngredientBatchDetail).not.toHaveBeenCalled()
    })
  })

  // ──────────────────────
  // 20. handleScanError
  // ──────────────────────
  describe('handleScanError', () => {
    it('sets error message and clears input after timeout', () => {
      const { handleScanError, scanLotError, scanLotInput, scanLotValidated } = usePreBatchWorkflow(createMockDeps())
      scanLotInput.value = 'BAD-SCAN'
      handleScanError('Something went wrong')

      expect(scanLotError.value).toBe('Something went wrong')
      expect(scanLotValidated.value).toBe(false)

      // After 2s timer
      vi.advanceTimersByTime(2000)
      expect(scanLotInput.value).toBe('')
      expect(scanLotError.value).toBe('')
    })
  })

  // ──────────────────────
  // 21. scanDialogIngInfo computed
  // ──────────────────────
  describe('scanDialogIngInfo', () => {
    it('returns null when no reCode selected', () => {
      const deps = createMockDeps()
      const { scanDialogIngInfo } = usePreBatchWorkflow(deps)
      expect(scanDialogIngInfo.value).toBeNull()
    })

    it('returns ingredient info when reCode is set', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.ingredients.value = [{ re_code: 'FH-001', name: 'Test Flour', mat_sap_code: 'SAP123' }]
      deps.selectableIngredients.value = [{ re_code: 'FH-001', ingredient_name: 'Test Flour', batch_require: 50 }]
      deps.requireVolume.value = 50

      const { scanDialogIngInfo } = usePreBatchWorkflow(deps)
      expect(scanDialogIngInfo.value).toEqual({
        re_code: 'FH-001',
        ingredient_name: 'Test Flour',
        mat_sap_code: 'SAP123',
        total_require: 50,
      })
    })
  })

  // ──────────────────────
  // 22. nextPendingItem & scanProgress
  // ──────────────────────
  describe('nextPendingItem & scanProgress', () => {
    it('returns the first non-completed item', () => {
      const { scanDialogItems, nextPendingItem, scanProgress } = usePreBatchWorkflow(createMockDeps())
      scanDialogItems.value = [
        { status: 2, batch_id: 'B1' },
        { status: 0, batch_id: 'B2' },
        { status: 0, batch_id: 'B3' },
      ]
      expect(nextPendingItem.value?.batch_id).toBe('B2')
      expect(scanProgress.value).toEqual({ done: 1, total: 3 })
    })

    it('returns undefined when all items completed', () => {
      const { scanDialogItems, nextPendingItem, scanProgress } = usePreBatchWorkflow(createMockDeps())
      scanDialogItems.value = [
        { status: 2, batch_id: 'B1' },
        { status: 2, batch_id: 'B2' },
      ]
      expect(nextPendingItem.value).toBeUndefined()
      expect(scanProgress.value).toEqual({ done: 2, total: 2 })
    })
  })

  // ──────────────────────
  // 23. fifoRecommendedLot
  // ──────────────────────
  describe('fifoRecommendedLot', () => {
    it('returns first item from filteredInventory', () => {
      const deps = createMockDeps()
      deps.filteredInventory.value = [
        { intake_lot_id: 'LOT-FIRST', expire_date: '2026-01-01' },
        { intake_lot_id: 'LOT-SECOND', expire_date: '2026-06-01' },
      ]
      const { fifoRecommendedLot } = usePreBatchWorkflow(deps)
      expect(fifoRecommendedLot.value?.intake_lot_id).toBe('LOT-FIRST')
    })

    it('returns null when filteredInventory is empty', () => {
      const deps = createMockDeps()
      deps.filteredInventory.value = []
      const { fifoRecommendedLot } = usePreBatchWorkflow(deps)
      expect(fifoRecommendedLot.value).toBeNull()
    })
  })

  // ──────────────────────
  // 24. startPreBatch
  // ──────────────────────
  describe('startPreBatch', () => {
    it('calls onPlanShow, resets state, opens scan dialog', async () => {
      const deps = createMockDeps()
      const plan = { plan_id: 'P1' }

      const { startPreBatch, showScanDialog, scanLotInput, scanLotValidated, scanLotError, scanDialogItems } = usePreBatchWorkflow(deps)
      await startPreBatch(plan)

      expect(deps.onPlanShow).toHaveBeenCalledWith(plan)
      expect(deps.selectedReCode.value).toBe('')
      expect(deps.selectedIntakeLotId.value).toBe('')
      expect(scanLotInput.value).toBe('')
      expect(scanLotValidated.value).toBe(false)
      expect(scanLotError.value).toBe('')
      expect(scanDialogItems.value).toEqual([])
      expect(showScanDialog.value).toBe(true)
    })
  })

  // ──────────────────────
  // 25. fetchScanDialogItems
  // ──────────────────────
  describe('fetchScanDialogItems', () => {
    it('fetches batch items from API when reCode and plan are set', async () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectedProductionPlan.value = 'PLAN-1'
      const mockData = [{ batch_id: 'B1', status: 0 }, { batch_id: 'B2', status: 0 }]
      $fetchMock.mockResolvedValue(mockData)

      const { fetchScanDialogItems, scanDialogItems, scanDialogLoading } = usePreBatchWorkflow(deps)
      await fetchScanDialogItems()

      expect($fetchMock).toHaveBeenCalledWith(
        'http://test:8001/prebatch-items/batches-by-ingredient/PLAN-1/FH-001',
        expect.objectContaining({ headers: { Authorization: 'Bearer test' } })
      )
      expect(scanDialogItems.value).toEqual(mockData)
      expect(scanDialogLoading.value).toBe(false)
    })

    it('does nothing when reCode or plan is empty', async () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = ''
      deps.selectedProductionPlan.value = ''

      const { fetchScanDialogItems } = usePreBatchWorkflow(deps)
      await fetchScanDialogItems()

      expect($fetchMock).not.toHaveBeenCalled()
    })

    it('handles API errors gracefully', async () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectedProductionPlan.value = 'PLAN-1'
      $fetchMock.mockRejectedValue(new Error('Network error'))

      const { fetchScanDialogItems, scanDialogItems, scanDialogLoading } = usePreBatchWorkflow(deps)
      await fetchScanDialogItems()

      expect(scanDialogItems.value).toEqual([])
      expect(scanDialogLoading.value).toBe(false)
    })
  })

  // ──────────────────────
  // 26. onScanItemSelect
  // ──────────────────────
  describe('onScanItemSelect', () => {
    it('does nothing for completed items', () => {
      const deps = createMockDeps()
      const { onScanItemSelect, showScanDialog } = usePreBatchWorkflow(deps)
      showScanDialog.value = true
      onScanItemSelect({ status: 2, required_volume: 10, batch_id: 'B1' })
      expect(showScanDialog.value).toBe(true) // unchanged
    })

    it('closes scan dialog and opens container setup', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'FH-001'
      deps.selectableIngredients.value = [
        { re_code: 'FH-001', ingredient_name: 'Test', std_package_size: 5 },
      ]
      deps.scalesComposable.scales.value = [
        { id: 1, label: 'Scale 1 (10 Kg)', isError: false },
      ]

      const { onScanItemSelect, showScanDialog, showContainerSetupDialog, setupContainerSize, setupPendingItem } = usePreBatchWorkflow(deps)
      showScanDialog.value = true

      onScanItemSelect({ status: 0, required_volume: 8, batch_id: 'B1', req_id: 'R1' })

      expect(showScanDialog.value).toBe(false)
      expect(showContainerSetupDialog.value).toBe(true)
      expect(setupContainerSize.value).toBe(5) // min(8, stdPkgSize=5) = 5
      expect(setupPendingItem.value).toBeTruthy()
    })
  })

  // ──────────────────────
  // 27. scan focus interval
  // ──────────────────────
  describe('scan focus interval', () => {
    it('starts and stops without error', () => {
      const { startScanFocusInterval, stopScanFocusInterval } = usePreBatchWorkflow(createMockDeps())
      startScanFocusInterval()
      // calling twice does nothing extra
      startScanFocusInterval()
      stopScanFocusInterval()
    })
  })

  // ──────────────────────
  // 28. Edge: pipe separator in scan input
  // ──────────────────────
  describe('scan lot delimiter handling', () => {
    it('handles pipe-delimited scans', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-PIPE', re_code: 'FH-001', mat_sap_code: 'SAP1', remain_vol: 100, status: 'Active', expire_date: '2026-12-31' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'FH-001', mat_sap_code: 'SAP1', ingredient_name: 'Test', status: 0 },
      ]
      deps.selectedProductionPlan.value = 'P1'
      $fetchMock.mockResolvedValue([])

      const { onScanLotEnter, scanLotInput, scanLotValidated } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-PIPE|EXTRA-DATA'
      await onScanLotEnter()

      expect(scanLotValidated.value).toBe(true)
      expect(deps.selectedIntakeLotId.value).toBe('LOT-PIPE')
    })

    it('handles comma-delimited scans', async () => {
      const deps = createMockDeps()
      deps.inventoryRows.value = [
        { intake_lot_id: 'LOT-COMMA', re_code: 'SP-001', mat_sap_code: 'SAP2', remain_vol: 50, status: 'Active', expire_date: '2026-06-15' },
      ]
      deps.selectableIngredients.value = [
        { re_code: 'SP-001', mat_sap_code: 'SAP2', ingredient_name: 'Sugar', status: 0 },
      ]
      deps.selectedProductionPlan.value = 'P1'
      $fetchMock.mockResolvedValue([])

      const { onScanLotEnter, scanLotInput, scanLotValidated } = usePreBatchWorkflow(deps)
      scanLotInput.value = 'LOT-COMMA,EXTRA'
      await onScanLotEnter()

      expect(scanLotValidated.value).toBe(true)
      expect(deps.selectedIntakeLotId.value).toBe('LOT-COMMA')
    })
  })

  // ──────────────────────
  // 29. Multi-package per batch workflow
  // ──────────────────────
  describe('multi-package per batch workflow', () => {

    // --- 29.1 handleDoneClick → Step 7 when more packages remain ---
    it('handleDoneClick goes to Step 7 when batch has remaining volume', async () => {
      const deps = createMockDeps()
      deps.actualScaleValue.value = 5.0
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15        // total 15kg needed
      deps.remainVolume.value = 10         // still 10kg remaining after 1st pkg
      deps.nextPackageNo.value = 1         // first package
      deps.requestBatch.value = 3          // 3 packages planned (15/5 = 3)

      const { handleDoneClick, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      await handleDoneClick()

      // Should go to Step 7 (Take Out) — NOT auto-advance
      expect(workflowStep.value).toBe(7)
      expect(deps.lastCapturedWeight.value).toBe(5.0)
      expect(deps.onDone).toHaveBeenCalledWith(true)
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'KCL-001' })
    })

    // --- 29.2 handleDoneClick always goes to Step 7 (composable behavior) ---
    it('handleDoneClick always sets Step 7 even when batch volume is fully consumed', async () => {
      const deps = createMockDeps()
      deps.actualScaleValue.value = 5.0
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15
      deps.remainVolume.value = 0.00001    // essentially zero → batch finished
      deps.nextPackageNo.value = 3
      deps.requestBatch.value = 3

      const { handleDoneClick, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      await handleDoneClick()

      // Composable handleDoneClick always sets Step 7 (auto-advance is page-level)
      expect(workflowStep.value).toBe(7)
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'KCL-001' })
    })

    // --- 29.3 handleDoneClick always Step 7 even when allPlannedPkgsDone ---
    it('handleDoneClick sets Step 7 even when nextPackageNo > requestBatch', async () => {
      const deps = createMockDeps()
      deps.actualScaleValue.value = 5.0
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15
      deps.remainVolume.value = 0.5
      deps.nextPackageNo.value = 4         // past the planned count
      deps.requestBatch.value = 3          // only 3 planned

      const { handleDoneClick, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      await handleDoneClick()

      // Composable always goes to Step 7
      expect(workflowStep.value).toBe(7)
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'KCL-001' })
    })

    // --- 29.4 handleStep7Confirm loops back to Step 3 for next package ---
    it('handleStep7Confirm returns to Step 3 when batch has pending packages', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 10         // 10kg left out of 15
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15
      deps.nextPackageNo.value = 2         // just finished pkg 1
      deps.requestBatch.value = 3
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'completed', target: 5 },
        { pkg_no: 2, status: 'pending', target: 5 },
        { pkg_no: 3, status: 'pending', target: 5 },
      ])

      const { handleStep7Confirm, workflowStep } = usePreBatchWorkflow(deps)
      workflowStep.value = 7
      handleStep7Confirm()

      // Should loop back to Step 3 for next package
      expect(workflowStep.value).toBe(3)
      expect(deps.currentPackageOrigins.value).toEqual([]) // reset for fresh container
      // Notify with progress info
      expect(deps.$q.notify).toHaveBeenCalledWith(
        expect.objectContaining({ message: expect.stringContaining('1/3') })
      )
    })

    // --- 29.5 handleStep7Confirm advances when all packages done ---
    it('handleStep7Confirm advances to next batch when all packages are completed', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 0          // all volume consumed
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15
      deps.nextPackageNo.value = 4         // past planned count
      deps.requestBatch.value = 3
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'done', target: 5 },
        { pkg_no: 2, status: 'done', target: 5 },
        { pkg_no: 3, status: 'done', target: 5 },
      ])

      const { handleStep7Confirm, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      workflowStep.value = 7
      pendingAdvance.value = { batchId: 'B-001', reCode: 'KCL-001' }
      handleStep7Confirm()

      // Should call dialog to advance to next batch
      expect(deps.$q.dialog).toHaveBeenCalled()
    })

    // --- 29.6 setupCalcPackages correctly splits multi-package ---
    it('setupCalcPackages computes correct number of packages for multi-pkg batch', () => {
      const deps = createMockDeps()
      deps.requireVolume.value = 15

      const { setupCalcPackages, setupContainerSize } = usePreBatchWorkflow(deps)
      
      // 15kg / 5kg per container = 3 packages
      setupContainerSize.value = 5
      expect(setupCalcPackages.value).toBe(3)

      // 15kg / 7.5kg per container = 2 packages
      setupContainerSize.value = 7.5
      expect(setupCalcPackages.value).toBe(2)

      // 15kg / 10kg per container = 2 packages (ceil)
      setupContainerSize.value = 10
      expect(setupCalcPackages.value).toBe(2)

      // 15kg / 15kg per container = 1 package (exact fit)
      setupContainerSize.value = 15
      expect(setupCalcPackages.value).toBe(1)

      // 15kg / 4kg per container = 4 packages (ceil(15/4) = 4)
      setupContainerSize.value = 4
      expect(setupCalcPackages.value).toBe(4)
    })

    // --- 29.7 onScanItemSelect uses std_package_size for container setup ---
    it('onScanItemSelect sets container size = min(required_volume, std_package_size)', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'KCL-001'
      deps.selectableIngredients.value = [
        { re_code: 'KCL-001', ingredient_name: 'KCl', std_package_size: 5 },
      ]
      deps.scalesComposable.scales.value = [
        { id: 1, label: 'Scale 1 (10 Kg)', isError: false },
      ]

      const { onScanItemSelect, showContainerSetupDialog, setupContainerSize } = usePreBatchWorkflow(deps)

      // required_volume=15, std_package_size=5 → container = min(15, 5) = 5
      onScanItemSelect({ status: 0, required_volume: 15, batch_id: 'B-001', req_id: 'R1' })

      expect(showContainerSetupDialog.value).toBe(true)
      expect(setupContainerSize.value).toBe(5)
      expect(deps.requireVolume.value).toBe(15) // full batch volume
    })

    // --- 29.8 onScanItemSelect when no std_package_size uses full volume ---
    it('onScanItemSelect uses full required_volume when std_package_size is 0', () => {
      const deps = createMockDeps()
      deps.selectedReCode.value = 'MISC-001'
      deps.selectableIngredients.value = [
        { re_code: 'MISC-001', ingredient_name: 'Misc', std_package_size: 0 },
      ]
      deps.scalesComposable.scales.value = [
        { id: 1, label: 'Scale 1 (10 Kg)', isError: false },
      ]

      const { onScanItemSelect, setupContainerSize } = usePreBatchWorkflow(deps)

      onScanItemSelect({ status: 0, required_volume: 7.5, batch_id: 'B-002', req_id: 'R2' })

      // No valid std_package_size → container = required_volume
      expect(setupContainerSize.value).toBe(7.5)
      expect(deps.requireVolume.value).toBe(7.5)
    })

    // --- 29.9 Full 3-package batch lifecycle simulation ---
    it('simulates full 3-package batch: pkg1 → Step7 → pkg2 → Step7 → pkg3 → Step7 → advance', async () => {
      const deps = createMockDeps()
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15

      const { handleDoneClick, handleStep7Confirm, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)

      // ═══ Package 1: weigh 5kg ═══
      deps.actualScaleValue.value = 5.0
      deps.remainVolume.value = 10       // 15 - 5 = 10 left
      deps.nextPackageNo.value = 1
      deps.requestBatch.value = 3

      await handleDoneClick()
      expect(workflowStep.value).toBe(7)  // Take Out
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'KCL-001' })

      // Operator removes package from scale → confirm step 7
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'completed', target: 5 },
        { pkg_no: 2, status: 'pending', target: 5 },
        { pkg_no: 3, status: 'pending', target: 5 },
      ])
      handleStep7Confirm()
      expect(workflowStep.value).toBe(3) // Back to Ready (next package)

      // ═══ Package 2: weigh 5kg ═══
      workflowStep.value = 4 // simulate tare and start weighing
      deps.actualScaleValue.value = 5.0
      deps.remainVolume.value = 5        // 15 - 10 = 5 left
      deps.nextPackageNo.value = 2

      await handleDoneClick()
      expect(workflowStep.value).toBe(7) // Take Out  

      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'completed', target: 5 },
        { pkg_no: 2, status: 'completed', target: 5 },
        { pkg_no: 3, status: 'pending', target: 5 },
      ])
      handleStep7Confirm()
      expect(workflowStep.value).toBe(3) // Back to Ready (last package)

      // ═══ Package 3: weigh 5kg ═══
      workflowStep.value = 4
      deps.actualScaleValue.value = 5.0
      deps.remainVolume.value = 0        // ALL done
      deps.nextPackageNo.value = 3

      await handleDoneClick()
      expect(workflowStep.value).toBe(7) // Composable always Step 7

      // Now confirm step 7 → all packages done, remainVolume ≈ 0 → advance  
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'completed', target: 5 },
        { pkg_no: 2, status: 'completed', target: 5 },
        { pkg_no: 3, status: 'completed', target: 5 },
      ])
      handleStep7Confirm()
      // isBatchFinished=true → advance via dialog
      expect(deps.$q.dialog).toHaveBeenCalled()
    })

    // --- 29.10 Irregular last package (required_volume not evenly divisible) ---
    it('handles irregular last package size correctly', () => {
      const deps = createMockDeps()
      deps.requireVolume.value = 7.5  // e.g. FV052A flavour

      const { setupCalcPackages, setupContainerSize } = usePreBatchWorkflow(deps)
      
      // 7.5kg / 2.5kg per container = 3 packages (exact)
      setupContainerSize.value = 2.5
      expect(setupCalcPackages.value).toBe(3)

      // 7.5kg / 4kg per container = 2 packages (ceil: 4 + 3.5)
      setupContainerSize.value = 4
      expect(setupCalcPackages.value).toBe(2)

      // 7.5kg / 3kg per container = 3 packages (ceil: 3 + 3 + 1.5)
      setupContainerSize.value = 3
      expect(setupCalcPackages.value).toBe(3)
    })

    // --- 29.11 handleStep7Confirm with remainVolume > 0 but no pending packages ---
    it('advances when remainVolume > 0 but allPlannedPkgsDone', () => {
      const deps = createMockDeps()
      deps.remainVolume.value = 0.3        // tiny remain due to tolerance
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'KCL-001'
      deps.requireVolume.value = 15
      deps.nextPackageNo.value = 4         // past planned count
      deps.requestBatch.value = 3
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'done', target: 5 },
        { pkg_no: 2, status: 'done', target: 5 },
        { pkg_no: 3, status: 'done', target: 5 },
      ])

      const { handleStep7Confirm, pendingAdvance } = usePreBatchWorkflow(deps)
      pendingAdvance.value = { batchId: 'B-001', reCode: 'KCL-001' }
      handleStep7Confirm()

      // allPlannedPkgsDone: nextPkgNo(4) > requestBatch(3) → advance  
      expect(deps.$q.dialog).toHaveBeenCalled()
    })

    // --- 29.12 Single package batch → Step 7 → Step7Confirm → advance ---
    it('single-package batch goes to Step 7 then advances via handleStep7Confirm', async () => {
      const deps = createMockDeps()
      deps.actualScaleValue.value = 7.5
      deps.selectedBatch.value = { batch_id: 'B-001' }
      deps.selectedReCode.value = 'FV052A'
      deps.requireVolume.value = 7.5
      deps.remainVolume.value = 0          // exact match → finished
      deps.nextPackageNo.value = 1
      deps.requestBatch.value = 1

      const { handleDoneClick, handleStep7Confirm, workflowStep, pendingAdvance } = usePreBatchWorkflow(deps)
      await handleDoneClick()

      // Composable always goes to Step 7
      expect(workflowStep.value).toBe(7)
      expect(pendingAdvance.value).toEqual({ batchId: 'B-001', reCode: 'FV052A' })

      // Then step7 confirm detects batch is finished → advance
      ;(deps.getPackagePlan as any).mockReturnValue([
        { pkg_no: 1, status: 'completed', target: 7.5 },
      ])
      handleStep7Confirm()
      expect(deps.$q.dialog).toHaveBeenCalled()
    })
  })
})

/**
 * usePreBatchInventory — Inventory, FIFO, warehouses, scanning
 */
import { ref, computed, watch, nextTick } from 'vue'
import { appConfig } from '~/appConfig/config'
import type { QTableColumn } from 'quasar'

/** Parse date safely — handles DD/MM/YYYY, YYYY-MM-DD, ISO, and Date objects */
const parseDateSafe = (date: any): Date | null => {
    if (!date) return null
    if (date instanceof Date) return isNaN(date.getTime()) ? null : date
    const s = String(date).trim()
    const slashMatch = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
    if (slashMatch) {
        const [, day, month, year] = slashMatch
        return new Date(Number(year), Number(month) - 1, Number(day))
    }
    const dashDMY = s.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/)
    if (dashDMY) {
        const [, day, month, year] = dashDMY
        return new Date(Number(year), Number(month) - 1, Number(day))
    }
    const d = new Date(s)
    return isNaN(d.getTime()) ? null : d
}

export interface InventoryItem {
    id: number
    intake_lot_id: string
    warehouse_location: string
    lot_id: string
    mat_sap_code: string
    re_code: string
    intake_vol: number
    remain_vol: number
    intake_package_vol: number
    package_intake: number
    expire_date: string
    manufacturing_date?: string
    material_description?: string
    uom?: string
    status: string
    intake_at?: string
}

export interface InventoryDeps {
    $q: any
    getAuthHeader: () => Record<string, string>
    t: (key: string, params?: any) => string
    formatDate: (date: any) => string
    selectedReCode: any
}

export function usePreBatchInventory(deps: InventoryDeps) {
    const { $q, getAuthHeader, t, formatDate } = deps

    // --- State ---
    const warehouses = ref<any[]>([])
    const selectedWarehouse = ref('All')
    const inventoryRows = ref<InventoryItem[]>([])
    const inventoryLoading = ref(false)
    const selectedInventoryItem = ref<InventoryItem[]>([])
    const selectedIntakeLotId = ref('')
    const showAllInventory = ref(false)
    const showHistoryDialog = ref(false)
    const showIntakeLabelDialog = ref(false)
    const selectedHistoryItem = ref<any>(null)
    const intakeLabelData = ref<any>(null)
    const selectedPrinter = ref('TSC_MB241')
    const intakeLotInputRef = ref<any>(null)

    // --- Functions ---
    const fetchWarehouses = async () => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/warehouses/`, {
                headers: getAuthHeader() as Record<string, string>
            })
            const mapped = data
                .filter(w => w.warehouse_id === 'FH' || w.warehouse_id === 'SPP')
                .map(w => ({
                    warehouse_id: w.warehouse_id,
                    name: w.name
                }))
            warehouses.value = [{ warehouse_id: 'All', name: 'All' }, ...mapped]

            // SPP: always default to 'All' — no department filtering
            selectedWarehouse.value = 'All'
        } catch (e) {
            console.error('Error fetching warehouses', e)
        }
    }

    const fetchInventory = async () => {
        try {
            inventoryLoading.value = true
            const data = await $fetch<InventoryItem[]>(`${appConfig.apiBaseUrl}/ingredient-intake-lists/`, {
                headers: getAuthHeader() as Record<string, string>
            })
            inventoryRows.value = data
        } catch (error) {
            console.error('Error fetching inventory:', error)
        } finally {
            inventoryLoading.value = false
        }
    }

    const updateInventoryStatus = async (item: InventoryItem, newStatus: string) => {
        try {
            await $fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/${item.id}`, {
                method: 'PUT',
                body: { ...item, status: newStatus },
                headers: getAuthHeader() as Record<string, string>
            })
            $q.notify({ type: 'positive', message: `Status updated to ${newStatus}`, position: 'top' })
            await fetchInventory()
        } catch (e) {
            console.error('Error updating status', e)
            $q.notify({ type: 'negative', message: 'Failed to update status', position: 'top' })
        }
    }

    const printIntakeLabel = () => {
        window.print()
    }

    const openIntakeLabelDialog = (item: any) => {
        const normalizedData = {
            intake_lot_id: item.intake_lot_id || item.IntakeLotId || item.intake_lot || '',
            lot_id: item.lot_id || item.LotId || item.supplier_lot || '',
            re_code: item.re_code || item.ReCode || item.material_code || '',
            mat_sap_code: item.mat_sap_code || item.MatSapCode || item.sap_code || '',
            intake_vol: Number(item.intake_vol ?? item.IntakeVol ?? item.intake_volume ?? item.remain_vol ?? 0),
            package_intake: Number(item.package_intake ?? item.PackageIntake ?? item.packages ?? 1),
            expire_date: item.expire_date || item.ExpireDate || '',
            material_description: item.material_description || item.MaterialDescription || item.description || ''
        }
        console.log('Mapping intake label data:', { source: item, mapped: normalizedData })
        intakeLabelData.value = normalizedData
        showIntakeLabelDialog.value = true
    }

    const onViewHistory = (item: any) => {
        selectedHistoryItem.value = item
        showHistoryDialog.value = true
    }

    const focusIntakeLotInput = () => {
        nextTick(() => {
            intakeLotInputRef.value?.focus()
        })
    }

    const onIntakeLotScanEnter = () => {
        // The watcher on selectedIntakeLotId already handles lookup/FIFO validation
    }

    // --- Computed ---
    const inventoryColumns = computed<QTableColumn[]>(() => [
        { name: 'intake_lot_id', align: 'left', label: t('preBatch.intakeLotId'), field: 'intake_lot_id', sortable: true },
        { name: 'mat_sap_code', align: 'left', label: t('ingredient.matSapCode'), field: 'mat_sap_code' },
        { name: 're_code', align: 'center', label: t('ingredient.reCode'), field: 're_code' },
        { name: 'material_description', align: 'left', label: t('common.description'), field: 'material_description' },
        { name: 'uom', align: 'center', label: t('ingredient.uom'), field: 'uom' },
        { name: 'intake_vol', align: 'right', label: t('ingredient.intakeVolume'), field: 'intake_vol' },
        { name: 'remain_vol', align: 'right', label: t('ingredient.remainVolume'), field: 'remain_vol', classes: 'text-red text-weight-bold' },
        { name: 'intake_package_vol', align: 'right', label: t('ingredient.pkgVol'), field: 'intake_package_vol' },
        { name: 'package_intake', align: 'center', label: t('ingredient.pkgs'), field: 'package_intake' },
        { name: 'expire_date', align: 'center', label: t('ingredient.expiryDate'), field: 'expire_date', format: (val: any) => formatDate(val) },
        { name: 'manufacturing_date', align: 'center', label: t('preBatch.mfgDate'), field: 'manufacturing_date', format: (val: any) => formatDate(val) },
        { name: 'status', align: 'center', label: t('common.status'), field: 'status' },
        { name: 'actions', align: 'center', label: t('common.actions'), field: 'id' }
    ])

    const filteredInventory = computed(() => {
        if (!deps.selectedReCode.value) return []
        return inventoryRows.value
            .filter(item => {
                const reMatch = (item.re_code || '').trim().toUpperCase() === deps.selectedReCode.value.trim().toUpperCase()
                const hasStock = item.remain_vol > 0
                const statusOk = showAllInventory.value || item.status === 'Active'
                return reMatch && hasStock && statusOk
            })
            .sort((a, b) => {
                const dateA = parseDateSafe(a.expire_date)?.getTime() ?? Infinity
                const dateB = parseDateSafe(b.expire_date)?.getTime() ?? Infinity
                if (dateA !== dateB) return dateA - dateB
                // Same expire date → sort by intake_at (earlier intake first)
                const intakeA = parseDateSafe(a.intake_at)?.getTime() ?? Infinity
                const intakeB = parseDateSafe(b.intake_at)?.getTime() ?? Infinity
                if (intakeA !== intakeB) return intakeA - intakeB
                return (a.intake_lot_id || '').localeCompare(b.intake_lot_id || '')
            })
    })

    const isFIFOCompliant = (item: InventoryItem) => {
        if (!item || !item.expire_date) return false
        const list = filteredInventory.value
        if (list.length === 0) return false
        const fifoItem = list[0]
        if (!fifoItem || !fifoItem.expire_date) return true

        const dateItem = parseDateSafe(item.expire_date)?.getTime() ?? Infinity
        const dateFifo = parseDateSafe(fifoItem.expire_date)?.getTime() ?? Infinity

        // If the scanned item's expiry is the same as or earlier than the FIFO item's expiry, it's compliant.
        return dateItem <= dateFifo
    }

    const sortedAllInventory = computed(() => {
        return [...inventoryRows.value]
            .filter(i => i.remain_vol > 0 && i.status === 'Active')
            .sort((a, b) => {
                const dateA = parseDateSafe(a.expire_date)?.getTime() ?? Infinity
                const dateB = parseDateSafe(b.expire_date)?.getTime() ?? Infinity
                if (dateA !== dateB) return dateA - dateB
                const intakeA = parseDateSafe(a.intake_at)?.getTime() ?? Infinity
                const intakeB = parseDateSafe(b.intake_at)?.getTime() ?? Infinity
                if (intakeA !== intakeB) return intakeA - intakeB
                return (a.intake_lot_id || '').localeCompare(b.intake_lot_id || '')
            })
    })

    const inventorySummary = computed(() => {
        const sum = { remain_vol: 0, pkgs: 0 }
        filteredInventory.value.forEach(item => {
            sum.remain_vol += Number(item.remain_vol) || 0
            sum.pkgs += Number(item.package_intake) || 0
        })
        return sum
    })

    const simulateScan = () => {
        if (filteredInventory.value.length > 0) {
            const item = filteredInventory.value[0]
            if (item) {
                selectedIntakeLotId.value = item.intake_lot_id
                selectedInventoryItem.value = [item]
                $q.notify({ type: 'positive', message: `Simulated Scan: Selected ${item.intake_lot_id} (FIFO)` })
            }
        } else {
            $q.notify({ type: 'warning', message: 'No inventory available to scan' })
        }
    }

    const onInventoryRowClick = (evt: any, row: InventoryItem) => {
        if (isFIFOCompliant(row)) {
            selectedInventoryItem.value = [row]
            selectedIntakeLotId.value = row.intake_lot_id
            $q.notify({ type: 'positive', message: `Selected: ${row.intake_lot_id}`, position: 'top', timeout: 1000 })
        } else {
            const fifoItem = filteredInventory.value[0]
            if (fifoItem) {
                $q.notify({
                    type: 'negative',
                    message: `FIFO Violation! Expected Lot: ${fifoItem.intake_lot_id} (Exp: ${formatDate(fifoItem.expire_date) || 'N/A'})`,
                    position: 'top',
                    timeout: 3000
                })
            }
        }
    }

    // --- Watchers ---
    watch(selectedIntakeLotId, (newVal) => {
        if (!newVal) {
            if (selectedInventoryItem.value.length > 0) {
                selectedInventoryItem.value = []
            }
            return
        }
        const match = filteredInventory.value.find(i =>
            i.intake_lot_id === newVal || i.intake_lot_id.toLowerCase() === newVal.toLowerCase()
        )
        if (match) {
            if (isFIFOCompliant(match)) {
                selectedInventoryItem.value = [match]
            } else {
                const fifoItem = filteredInventory.value[0]
                const expDate = formatDate(fifoItem?.expire_date) || 'N/A'
                const expectedLot = fifoItem ? fifoItem.intake_lot_id : 'Unknown'
                $q.notify({ type: 'negative', message: `FIFO Violation! Expected Lot: ${expectedLot} (Exp: ${expDate})`, position: 'top', timeout: 4000 })
                selectedInventoryItem.value = []
            }
        } else {
            selectedInventoryItem.value = []
        }
    })

    return {
        // State
        warehouses,
        selectedWarehouse,
        inventoryRows,
        inventoryLoading,
        selectedInventoryItem,
        selectedIntakeLotId,
        showAllInventory,
        showHistoryDialog,
        showIntakeLabelDialog,
        selectedHistoryItem,
        intakeLabelData,
        selectedPrinter,
        intakeLotInputRef,
        // Computed
        inventoryColumns,
        filteredInventory,
        sortedAllInventory,
        inventorySummary,
        // Functions
        fetchWarehouses,
        fetchInventory,
        updateInventoryStatus,
        printIntakeLabel,
        openIntakeLabelDialog,
        onViewHistory,
        focusIntakeLotInput,
        onIntakeLotScanEnter,
        isFIFOCompliant,
        simulateScan,
        onInventoryRowClick,
    }
}

/**
 * usePreBatchRecords — PreBatch CRUD, delete, auth
 */
import { ref, computed, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import type { QTableColumn } from 'quasar'

export interface RecordDeps {
    $q: any
    getAuthHeader: () => Record<string, string>
    t: (key: string, params?: any) => string
    user: any
    formatDate: (date: any) => string
    // Cross-composable refs
    selectedBatch: any
    selectedProductionPlan: any
    selectedReCode: any
    requireVolume: any
    selectableIngredients: any
    requestBatch: any
    // Functions
    fetchPrebatchItems: (batchId: string) => Promise<void>
    finalizeBatchPreparation: (batchId: number) => Promise<void>
}

export function usePreBatchRecords(deps: RecordDeps) {
    const { $q, getAuthHeader, t, formatDate } = deps

    // --- State ---
    const preBatchLogs = ref<any[]>([])
    const recordToDelete = ref<any>(null)
    const showDeleteDialog = ref(false)
    const deleteInput = ref('')
    const selectedPreBatchLogs = ref<any[]>([])

    // --- Columns ---
    const prebatchColumns: QTableColumn[] = [
        { name: 'batch_id', align: 'left', label: 'Batch ID', field: 'batch_record_id', format: (val: string) => val.split('-').slice(0, 6).join('-'), classes: 'text-caption' },
        { name: 're_code', align: 'left', label: 'Ingredient', field: 're_code', sortable: true },
        { name: 'package_no', align: 'center', label: 'Pkg', field: 'package_no' },
        { name: 'net_volume', align: 'right', label: 'Net (kg)', field: 'net_volume', format: (val: any) => Number(val).toFixed(4) },
        { name: 'intake_lot_id', align: 'left', label: 'Intake Lot', field: 'intake_lot_id', sortable: true },
        { name: 'reprint', align: 'center', label: 'Print', field: 'id' },
        { name: 'actions', align: 'center', label: '', field: 'id' }
    ]

    // --- Computed ---
    const filteredPreBatchLogs = computed(() => {
        if (!deps.selectedBatch.value) return preBatchLogs.value
        return preBatchLogs.value.filter(l => l.batch_record_id.startsWith(deps.selectedBatch.value.batch_id))
    })

    const totalCompletedWeight = computed(() => {
        if (!deps.selectedBatch.value || !deps.selectedReCode.value) return 0
        const currentBatchId = deps.selectedBatch.value.batch_id
        return preBatchLogs.value.reduce((sum, log) => {
            if (log.re_code === deps.selectedReCode.value && log.batch_record_id.startsWith(currentBatchId)) {
                return sum + (Number(log.net_volume) || 0)
            }
            return sum
        }, 0)
    })

    const completedCount = computed(() => {
        if (!deps.selectedBatch.value || !deps.selectedReCode.value) return 0
        const currentBatchId = deps.selectedBatch.value.batch_id
        return preBatchLogs.value.filter(log =>
            log.re_code === deps.selectedReCode.value && log.batch_record_id.startsWith(currentBatchId)
        ).length
    })

    const nextPackageNo = computed(() => {
        if (!deps.selectedBatch.value || !deps.selectedReCode.value) return 1
        const batchId = deps.selectedBatch.value.batch_id
        const existingNos = preBatchLogs.value
            .filter(log => log.re_code === deps.selectedReCode.value && log.batch_record_id.startsWith(batchId))
            .map(log => Number(log.package_no))
            .sort((a, b) => a - b)
        let next = 1
        while (existingNos.includes(next)) {
            next++
        }
        return next
    })

    const preBatchSummary = computed(() => {
        const logs = filteredPreBatchLogs.value
        const totalNetWeight = logs.reduce((sum, log) => sum + (Number(log.net_volume) || 0), 0)
        const count = logs.length
        const targetW = deps.requireVolume.value || 0
        const errorVol = totalNetWeight - targetW
        return {
            count,
            totalNetWeight: totalNetWeight.toFixed(4),
            targetCount: deps.requestBatch.value || 0,
            targetWeight: targetW.toFixed(4),
            errorVolume: errorVol.toFixed(4),
            errorColor: errorVol > 0 ? 'text-red' : (errorVol < 0 ? 'text-orange' : 'text-green')
        }
    })

    // --- Functions ---
    const fetchPreBatchRecords = async () => {
        if (!deps.selectedProductionPlan.value && !deps.selectedBatch.value) return
        try {
            const planId = deps.selectedProductionPlan.value || deps.selectedBatch.value.batch_id
            const endpoint = `${appConfig.apiBaseUrl}/prebatch-recs/by-plan/${planId}`

            const data = await $fetch<any[]>(endpoint, {
                headers: getAuthHeader() as Record<string, string>
            })
            preBatchLogs.value = data
        } catch (error) {
            console.error('Error fetching prebatch records:', error)
        }
    }

    const executeDeletion = async (record: any) => {
        try {
            // Use prebatch-recs endpoint for individual package records
            await $fetch(`${appConfig.apiBaseUrl}/prebatch-recs/${record.id}`, {
                method: 'DELETE',
                headers: getAuthHeader() as Record<string, string>
            })
            $q.notify({ type: 'positive', message: `Package #${record.package_no} cancelled. Inventory restored.`, icon: 'restore' })
            showDeleteDialog.value = false
            recordToDelete.value = null
            deleteInput.value = ''
            await fetchPreBatchRecords()
            if (deps.selectedBatch.value) {
                await deps.fetchPrebatchItems(deps.selectedBatch.value.batch_id)
            }
        } catch (err) {
            console.error('Error deleting record:', err)
            $q.notify({ type: 'negative', message: 'Failed to cancel record' })
        }
    }

    const onDeleteRecord = (record: any) => {
        recordToDelete.value = record
        deleteInput.value = ''
        showDeleteDialog.value = true
    }

    const onConfirmDeleteManual = async () => {
        if (!recordToDelete.value) return
        if (!deleteInput.value) {
            $q.notify({ type: 'warning', message: 'Please select a reason for cancellation.', position: 'top' })
            return
        }
        console.log(`Cancelling package #${recordToDelete.value.package_no}, reason: ${deleteInput.value}`)
        await executeDeletion(recordToDelete.value)
    }

    const onDeleteScanEnter = async () => {
        if (!showDeleteDialog.value || !recordToDelete.value) return
        if (deleteInput.value === recordToDelete.value.batch_record_id) {
            await executeDeletion(recordToDelete.value)
        } else {
            $q.notify({ type: 'negative', message: `Invalid code! Expected: ${recordToDelete.value.batch_record_id}`, position: 'top', timeout: 3000 })
        }
    }

    // --- Watchers ---
    watch([preBatchLogs, () => deps.selectedBatch.value, () => deps.selectableIngredients.value], ([logs, batch, ingredients]) => {
        if (!logs || !batch || !ingredients || ingredients.length === 0) {
            return
        }
        let allDone = true
        ingredients.forEach((ing: any) => {
            const ingLogs = (logs as any[]).filter(l => l.re_code === ing.re_code && l.batch_record_id.startsWith(batch.batch_id))
            if (ingLogs.length > 0) {
                const totalPackaged = ingLogs.reduce((acc, log) => acc + (Number(log.net_volume) || 0), 0)
                const required = Number(ing.batch_require || ing.required_volume || ing.per_batch || 0)

                // The request volume and weight volume must be the exact same (diff essentially 0)
                if (required > 0 && Math.abs(totalPackaged - required) <= 0.0001) {
                    ing.isDone = true
                } else {
                    ing.isDone = false
                    allDone = false
                }
            } else {
                ing.isDone = false
                allDone = false
            }
        })
        if (allDone && !batch.batch_prepare) {
            console.log(`[Records] Batch ${batch.batch_id} is complete. Finalizing...`)
            deps.finalizeBatchPreparation(batch.id)
        }
    }, { deep: true })

    const clearAllBatchRecords = async (batchIdStr: string) => {
        try {
            const result = await $fetch<any>(`${appConfig.apiBaseUrl}/prebatch-recs/clear-batch/${batchIdStr}`, {
                method: 'DELETE',
                headers: getAuthHeader() as Record<string, string>
            })
            $q.notify({ type: 'positive', message: result.message || 'All records cleared', icon: 'delete_sweep', position: 'top' })
            await fetchPreBatchRecords()
            if (deps.selectedBatch.value) {
                await deps.fetchPrebatchItems(deps.selectedBatch.value.batch_id)
            }
        } catch (err: any) {
            console.error('Error clearing batch records:', err)
            $q.notify({ type: 'negative', message: err?.data?.detail || 'Failed to clear records', position: 'top' })
        }
    }

    return {
        // State
        preBatchLogs,
        recordToDelete,
        showDeleteDialog,
        deleteInput,
        selectedPreBatchLogs,
        // Columns
        prebatchColumns,
        // Computed
        filteredPreBatchLogs,
        totalCompletedWeight,
        completedCount,
        nextPackageNo,
        preBatchSummary,
        // Functions
        fetchPreBatchRecords,
        executeDeletion,
        onDeleteRecord,
        onConfirmDeleteManual,
        onDeleteScanEnter,
        clearAllBatchRecords,
    }
}

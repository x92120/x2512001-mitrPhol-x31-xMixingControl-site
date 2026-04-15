/**
 * usePreBatchIngredients — Ingredient requirements, expand/collapse, package plan
 */
import { ref, computed, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import type { QTableColumn } from 'quasar'

export interface IngredientDeps {
    $q: any
    getAuthHeader: () => Record<string, string>
    t: (key: string, params?: any) => string
    // Cross-composable refs
    ingredients: any
    selectedProductionPlan: any
    selectedBatch: any
    selectedReCode: any
    selectedRequirementId: any
    selectedWarehouse: any
    isBatchSelected: any
    inventoryRows: any
    preBatchLogs: any
    requireVolume: any
    packageSize: any
    filteredInventory: any
    selectedInventoryItem: any
    selectedIntakeLotId: any
    // Functions from other composables
    updatePrebatchItemStatus: (batchId: string, reCode: string, status: number) => Promise<void>
    onBatchIngredientClick?: (batch: any, req: any, plan: any) => Promise<void>
}

export function usePreBatchIngredients(deps: IngredientDeps) {
    const { $q, getAuthHeader, t } = deps

    // --- State ---
    const prebatchItems = ref<any[]>([])
    const expandedIngredients = ref<string[]>([])
    const ingredientBatchDetail = ref<Record<string, any[]>>({})
    const expandedBatchRows = ref<string[]>([])

    // --- Functions ---
    const fetchPrebatchItems = async (batchId: string) => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batchId}`, {
                headers: getAuthHeader() as Record<string, string>
            })
            prebatchItems.value = data
        } catch (error) {
            console.error('Error fetching prebatch requirements:', error)
            prebatchItems.value = []
        }
    }

    const updatePrebatchItemStatus = async (batchId: string, reCode: string, status: number) => {
        try {
            // Find the correct PreBatchItem ID for this specific batch
            const details = ingredientBatchDetail.value[reCode] || []
            const bd = details.find((d: any) => d.batch_id === batchId)
            const itemId = bd?.req_id || deps.selectedRequirementId?.value

            if (!itemId) {
                console.warn(`[updatePrebatchItemStatus] Could not find item ID for ${batchId} / ${reCode}`)
                return
            }

            await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${itemId}/status?status=${status}`, {
                method: 'PUT',
                headers: getAuthHeader() as Record<string, string>
            })

            if (bd) bd.status = status // Update local immediately
            await fetchPrebatchItems(batchId)
        } catch (error) {
            console.error('Error updating prebatch requirement status:', error)
        }
    }

    // --- Computed ---
    const selectableIngredients = computed(() => {
        if (!prebatchItems.value || prebatchItems.value.length === 0) return []
        const invList = deps.inventoryRows.value || []

        const mapped = prebatchItems.value.map((task: any, index: number) => {
            const ingInfo = deps.ingredients.value.find((i: any) => i.re_code === task.re_code)
            const stock = invList.find((r: any) => r.re_code === task.re_code)
            const warehouse = (task.wh && task.wh !== '-' ? task.wh : (stock?.warehouse_location || '-')).toUpperCase()

            const batchReq = deps.isBatchSelected.value
                ? (task.required_volume || task.per_batch || task.total_require || 0)
                : (task.total_require || task.required_volume || 0)
            const perBatch = task.per_batch || task.required_volume || 0

            return {
                index: index + 1,
                re_code: task.re_code,
                ingredient_name: task.ingredient_name || ingInfo?.name || task.re_code,
                std_package_size: ingInfo?.std_package_size || 0,
                package_container_type: ingInfo?.package_container_type || 'Bag',
                batch_require: batchReq,
                per_batch: perBatch,
                total_require: task.total_require ?? task.required_volume,
                total_packaged: task.total_packaged || 0,
                batch_count: task.batch_count || 1,
                from_warehouse: warehouse,
                isDisabled: deps.selectedWarehouse.value !== 'All' && warehouse !== deps.selectedWarehouse.value.toUpperCase(),
                isDone: task.status === 2,
                status: task.status,
                req_id: task.id,
                mat_sap_code: ingInfo?.mat_sap_code || ''
            }
        })

        // Apply filter by warehouse if not 'All'
        let filtered = mapped
        if (deps.selectedWarehouse.value && deps.selectedWarehouse.value !== 'All') {
            const whTarget = deps.selectedWarehouse.value.toUpperCase()
            filtered = mapped.filter((ing: any) => ing.from_warehouse === whTarget)
        }

        return filtered
    })

    const ingredientsByWarehouse = computed(() => {
        const groups: Record<string, any[]> = {}
        for (const ing of selectableIngredients.value) {
            const wh = ing.from_warehouse || '-'
            if (!groups[wh]) groups[wh] = []
            groups[wh].push(ing)
        }
        return Object.entries(groups).sort((a, b) => {
            if (a[0] === '-') return 1
            if (b[0] === '-') return -1
            return a[0].localeCompare(b[0])
        })
    })

    // --- Expand/Collapse ---
    const toggleIngredientExpand = (reCode: string) => {
        const index = expandedIngredients.value.indexOf(reCode)
        if (index > -1) {
            expandedIngredients.value.splice(index, 1)
        } else {
            expandedIngredients.value.push(reCode)
            fetchIngredientBatchDetail(reCode)
        }
    }

    const isExpanded = (reCode: string) => expandedIngredients.value.includes(reCode)

    const fetchIngredientBatchDetail = async (reCode: string) => {
        if (!deps.selectedProductionPlan.value) return
        try {
            const data = await $fetch<any[]>(
                `${appConfig.apiBaseUrl}/prebatch-items/batches-by-ingredient/${deps.selectedProductionPlan.value}/${encodeURIComponent(reCode)}`,
                { headers: getAuthHeader() as Record<string, string> }
            )
            ingredientBatchDetail.value[reCode] = data
        } catch (error) {
            console.error('Error fetching ingredient batch detail:', error)
            ingredientBatchDetail.value[reCode] = []
        }
    }

    const toggleBatchRow = (key: string) => {
        const idx = expandedBatchRows.value.indexOf(key)
        if (idx >= 0) {
            expandedBatchRows.value.splice(idx, 1)
        } else {
            expandedBatchRows.value.push(key)
        }
    }

    const isBatchRowExpanded = (key: string) => expandedBatchRows.value.includes(key)

    const getPackagePlan = (batchId: string, reCode: string, requiredVolume: number) => {
        if (requiredVolume <= 0) return []

        // Find actual PreBatchRec records for this batch + ingredient
        const actuals = deps.preBatchLogs.value
            .filter((log: any) => log.re_code === reCode && log.batch_record_id.startsWith(batchId))
            .sort((a: any, b: any) => a.package_no - b.package_no)

        // If we have records from preBatchLogs, use them
        if (actuals.length > 0) {
            const totalPkgs = actuals[0]?.total_packages || actuals.length
            const packages: any[] = []
            for (let i = 1; i <= totalPkgs; i++) {
                const actual = actuals.find((a: any) => a.package_no === i)
                packages.push({
                    pkg_no: i,
                    target: actual?.net_volume || 0,
                    actual: actual?.net_volume || null,
                    status: actual ? 'done' : 'pending',
                    completed: actual ? 'completed' : 'pending',
                    log: actual || null
                })
            }
            return packages
        }

        // Check prebatch_items data (ingredientBatchDetail) for completed items
        const batchDetail = ingredientBatchDetail.value[reCode] || []
        const itemData = batchDetail.find((bd: any) => bd.batch_id === batchId)
        if (itemData && itemData.status === 2 && itemData.net_volume) {
            const totalPkgs = itemData.total_packages || 1
            const packages: any[] = []
            for (let i = 1; i <= totalPkgs; i++) {
                packages.push({
                    pkg_no: i,
                    target: itemData.net_volume,
                    actual: itemData.net_volume,
                    status: 'done',
                    completed: 'completed',
                    log: itemData
                })
            }
            return packages
        }

        // No records yet — fall back to calculation from packageSize
        const ingInfo = deps.ingredients.value.find((i: any) => i.re_code === reCode)
        let pkgSize = deps.packageSize.value || ingInfo?.std_package_size || 0
        if (pkgSize <= 0) pkgSize = requiredVolume
        const totalPkgs = Math.ceil(requiredVolume / pkgSize)
        const packages: any[] = []
        let remain = requiredVolume
        for (let i = 1; i <= totalPkgs; i++) {
            const target = Math.min(remain, pkgSize)
            remain -= target
            packages.push({
                pkg_no: i,
                target,
                actual: null,
                status: 'pending',
                completed: 'pending',
                log: null
            })
        }
        return packages
    }

    const getIngredientLogs = (reCode: string) => {
        if (!deps.selectedBatch.value) return []
        return deps.preBatchLogs.value
            .filter((log: any) => log.re_code === reCode && log.batch_record_id.startsWith(deps.selectedBatch.value.batch_id))
            .sort((a: any, b: any) => a.package_no - b.package_no)
    }

    const getIngredientRowClass = (ing: any) => {
        if (ing.isDisabled) return 'bg-grey-3 text-grey-5 cursor-not-allowed'
        if (deps.selectedReCode.value === ing.re_code) return 'bg-orange-2 text-deep-orange-9 text-weight-bold cursor-pointer'
        if (ing.status === 2) return 'bg-green-1 text-green-9 cursor-pointer'
        if (ing.status === 1) return 'bg-amber-1 text-amber-9 cursor-pointer'
        return 'hover-bg-grey-1 cursor-pointer'
    }

    // --- Selection ---
    const onSelectIngredient = async (ing: any) => {
        if (ing.isDisabled) return
        deps.selectedReCode.value = ing.re_code
        deps.selectedRequirementId.value = ing.req_id

        // Auto-expand ingredient to show batch breakdown
        if (!expandedIngredients.value.includes(ing.re_code)) {
            expandedIngredients.value.push(ing.re_code)
        }

        // Fetch batch detail for this ingredient
        await fetchIngredientBatchDetail(ing.re_code)

        // Auto-select first pending batch (status !== 2 = not done)
        const batches = ingredientBatchDetail.value[ing.re_code] || []
        const firstPending = batches.find((bd: any) => bd.status !== 2)
        if (firstPending) {
            if (deps.onBatchIngredientClick) {
                // Use the centralized click handler that updates index and records
                await deps.onBatchIngredientClick(
                    { batch_id: firstPending.batch_id },
                    { re_code: ing.re_code, id: firstPending.req_id || firstPending.id, required_volume: firstPending.required_volume, status: firstPending.status },
                    null
                )
            } else {
                // Fallback (older approach)
                const reqVol = firstPending.required_volume || 0
                deps.isBatchSelected.value = true
                deps.requireVolume.value = reqVol
                deps.selectedRequirementId.value = firstPending.req_id || firstPending.id || ing.req_id

                const stdSize = ing.std_package_size || 0
                if (stdSize > 0) {
                    deps.packageSize.value = Math.min(reqVol, stdSize)
                } else {
                    deps.packageSize.value = reqVol
                }
            }

            $q.notify({
                type: 'info',
                message: `Auto-selected batch: ${firstPending.batch_id}`,
                position: 'top',
                timeout: 1500
            })
        } else if (batches.length > 0) {
            $q.notify({
                type: 'positive',
                message: `All batches completed for ${ing.re_code}!`,
                position: 'top',
                timeout: 2000
            })
        }

        // Update status if first time
        if (ing.status === 0 && deps.selectedBatch.value) {
            await updatePrebatchItemStatus(deps.selectedBatch.value.batch_id, ing.re_code, 1)
        }
    }

    const updateRequireVolume = () => {
        if (deps.selectedReCode.value) {
            const ing = selectableIngredients.value.find(i => i.re_code === deps.selectedReCode.value)
            if (ing) {
                // Always use per_batch for scale target base reference
                const originalReqVol = ing.per_batch || ing.batch_require || 0
                let pkgSize = deps.packageSize.value

                // If no package size selected yet, try to set a sensible default
                if (pkgSize <= 0) {
                    const stdSize = ing.std_package_size || 0
                    if (stdSize > 0) {
                        pkgSize = Math.min(originalReqVol, stdSize)
                    } else {
                        pkgSize = originalReqVol
                    }
                    if (pkgSize !== deps.packageSize.value) {
                        deps.packageSize.value = pkgSize
                    }
                }

                // NEVER artificially inflate requireVolume based on container size!
                // A 7.5kg requirement with a 5kg container size does NOT mean we suddenly need 10kg!
                // It just means we need one 5kg bag and one 2.5kg bag.
                if (!deps.isBatchSelected.value) {
                    deps.requireVolume.value = originalReqVol
                }
            }
        } else {
            deps.requireVolume.value = 0
        }
    }

    watch(() => deps.packageSize.value, (newVal, oldVal) => {
        if (newVal !== oldVal && newVal > 0 && deps.selectedReCode.value) {
            updateRequireVolume()
        }
    })

    const onIngredientSelect = () => {
        if (deps.selectedReCode.value) {
            if (deps.filteredInventory.value.length > 0) {
                const firstItem = deps.filteredInventory.value[0]
                if (firstItem) {
                    deps.selectedInventoryItem.value = [firstItem]
                    deps.selectedIntakeLotId.value = firstItem.intake_lot_id
                    $q.notify({ type: 'positive', message: t('preBatch.autoSelectedFifo', { id: firstItem.intake_lot_id }), position: 'top', timeout: 1000 })
                }
            } else {
                deps.selectedInventoryItem.value = []
                deps.selectedIntakeLotId.value = ''
                $q.notify({ type: 'warning', message: t('preBatch.noInventoryFor', { id: deps.selectedReCode.value }), position: 'top', timeout: 1000 })
            }
        }
    }

    const onIngredientDoubleClick = (ingredient: any) => {
        if (ingredient && ingredient.total_require !== undefined) {
            deps.requireVolume.value = Number(ingredient.total_require.toFixed(3))
            if (ingredient.std_package_size) {
                deps.packageSize.value = Number(ingredient.std_package_size)
            }
            $q.notify({ type: 'positive', message: t('preBatch.initBatching', { id: ingredient.re_code }), position: 'top', timeout: 500 })
        }
    }

    // --- Watchers ---
    // Selection should be managed by the workflow, not side-effects of list updates
    /*
    watch(selectableIngredients, (newList) => {
        if (deps.selectedReCode.value && !newList.some(i => i.re_code === deps.selectedReCode.value)) {
            deps.selectedReCode.value = ''
        }
    })
    */

    return {
        // State
        prebatchItems,
        expandedIngredients,
        ingredientBatchDetail,
        expandedBatchRows,
        // Computed
        selectableIngredients,
        ingredientsByWarehouse,
        // Functions
        fetchPrebatchItems,
        updatePrebatchItemStatus,
        toggleIngredientExpand,
        isExpanded,
        fetchIngredientBatchDetail,
        toggleBatchRow,
        isBatchRowExpanded,
        getPackagePlan,
        getIngredientLogs,
        getIngredientRowClass,
        onSelectIngredient,
        updateRequireVolume,
        onIngredientSelect,
        onIngredientDoubleClick,
    }
}

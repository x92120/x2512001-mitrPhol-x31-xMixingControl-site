/**
 * usePreBatchProduction — Plan/batch selection, filtering, navigation
 */
import { ref, computed, watch } from 'vue'
import { appConfig } from '~/appConfig/config'

export interface ProductionDeps {
    $q: any
    getAuthHeader: () => Record<string, string>
    t: (key: string, params?: any) => string
    // Cross-composable refs (injected by page)
    ingredients: any
    prebatchItems: any
    inventoryRows: any
    requireVolume: any
    packageSize: any
    selectedReCode: any
    selectedRequirementId: any
    selectedIntakeLotId?: any
    isBatchSelected: any
    selectedWarehouse: any
    // Functions from other composables
    fetchPrebatchItems: (batchId: string) => Promise<void>
    fetchPreBatchRecords: () => Promise<void>
    updatePrebatchItemStatus: (batchId: string, reCode: string, status: number) => Promise<void>
    updateRequireVolume: () => void
    ingredientBatchDetail?: any
}

export function usePreBatchProduction(deps: ProductionDeps) {
    const { $q, getAuthHeader, t } = deps

    // --- State ---
    const selectedProductionPlan = ref('')
    const selectedBatchIndex = ref(0)
    const isLoading = ref(false)
    const productionPlans = ref<any[]>([])
    const planFilter = ref('All')
    const searchPlanId = ref('')
    const searchSkuName = ref('')
    const productionPlanOptions = computed(() => {
        const options = productionPlans.value.map((plan: any) => ({
            label: `${plan.plan_id} (${plan.sku_id || 'No SKU'})`,
            value: plan.plan_id
        }))
        return [{ label: 'All Plans', value: 'All' }, ...options]
    })

    const allBatches = ref<any[]>([])
    const filteredBatches = ref<any[]>([])
    const ingredientOptions = ref<{ label: string, value: string }[]>([])
    const batchIngredients = ref<Record<string, any[]>>({})

    const filteredProductionPlans = computed(() => {
        let base = productionPlans.value.filter((p: any) => p.status !== 'Cancelled')

        if (planFilter.value !== 'All') {
            base = base.filter((p: any) => p.plan_id === planFilter.value)
        }

        if (searchPlanId.value) {
            const search = searchPlanId.value.toLowerCase()
            base = base.filter((p: any) => p.plan_id.toLowerCase().includes(search))
        }

        if (searchSkuName.value) {
            const search = searchSkuName.value.toLowerCase()
            base = base.filter((p: any) => (p.sku_name || '').toLowerCase().includes(search) || (p.sku_id || '').toLowerCase().includes(search))
        }

        return base
    })

    const plansWithBatches = computed(() => {
        return filteredProductionPlans.value.map(plan => {
            // Use batches already embedded from production-plans API response
            const childBatches = (plan.batches || allBatches.value.filter((b: any) => b.batch_id?.includes(plan.plan_id)))
                .sort((a: any, b: any) => (a.batch_id || '').localeCompare(b.batch_id || ''))
            return { ...plan, batches: childBatches }
        })
    })

    const batchIds = computed(() => filteredBatches.value.map((b: any) => b.batch_id))

    const selectedBatch = computed(() => {
        if (selectedBatchIndex.value >= 0 && filteredBatches.value.length > 0) {
            return filteredBatches.value[selectedBatchIndex.value]
        }
        return null
    })

    const selectedPlanDetails = computed(() => {
        return productionPlans.value.find(p => p.plan_id === selectedProductionPlan.value)
    })

    const structuredSkuList = computed(() => {
        const groups: Record<string, any> = {}
        const activePlans = productionPlans.value.filter(p =>
            !p.status || ['Active', 'In Progress', 'Released', 'Planned'].includes(p.status)
        )
        activePlans.forEach(plan => {
            const sku = plan.sku_id || 'No SKU'
            if (!groups[sku]) {
                groups[sku] = { sku, plans: [] }
            }
            const childBatches = (plan.batches || [])
                .sort((a: any, b: any) => (a.batch_id || '').localeCompare(b.batch_id || ''))
            groups[sku].plans.push({ ...plan, batches: childBatches })
        })
        return Object.values(groups).sort((a: any, b: any) => a.sku.localeCompare(b.sku))
    })

    // --- Functions ---
    const fetchIngredients = async () => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/ingredients/`, {
                headers: getAuthHeader() as Record<string, string>
            })
            deps.ingredients.value = data
        } catch (e) {
            console.error('Error fetching ingredients', e)
        }
    }

    const fetchProductionPlans = async () => {
        try {
            isLoading.value = true
            const resp = await $fetch<any>(`${appConfig.apiBaseUrl}/production-plans/?status=active`, {
                headers: getAuthHeader() as Record<string, string>
            })
            const plans = resp.plans || resp || []
            productionPlans.value = plans
            // Also populate allBatches from embedded data to avoid separate fetch
            const embeddedBatches = plans.flatMap((p: any) => p.batches || [])
            if (embeddedBatches.length > 0) {
                allBatches.value = embeddedBatches
            }
        } catch (error) {
            console.error('Error fetching production plans:', error)
            $q.notify({ type: 'negative', message: t('preBatch.errorLoadingPlans'), position: 'top' })
        } finally {
            isLoading.value = false
        }
    }

    const fetchBatchIds = async () => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/production-batches/`, {
                headers: getAuthHeader() as Record<string, string>
            })
            allBatches.value = data
            filterBatchesByPlan()
        } catch (error) {
            console.error('Error fetching batch IDs:', error)
        }
    }

    const filterBatchesByPlan = async () => {
        if (!selectedProductionPlan.value) {
            filteredBatches.value = []
            ingredientOptions.value = []
            return
        }
        const plan = productionPlans.value.find(p => p.plan_id === selectedProductionPlan.value)
        if (plan) {
            filteredBatches.value = allBatches.value
                .filter(batch => batch.sku_id === plan.sku_id || batch.batch_id.includes(plan.plan_id))
                .sort((a, b) => a.batch_id.localeCompare(b.batch_id))
            if (selectedBatchIndex.value >= filteredBatches.value.length) {
                selectedBatchIndex.value = 0
            }
            deps.updateRequireVolume()
        }
    }

    const onPlanShow = async (plan: any) => {
        selectedProductionPlan.value = plan.plan_id
        deps.isBatchSelected.value = false
        deps.selectedReCode.value = ''
        deps.selectedRequirementId.value = null
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/summary-by-plan/${plan.plan_id}`, {
                headers: getAuthHeader() as Record<string, string>
            })
            deps.prebatchItems.value = data.map((item: any) => ({
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
        } catch (error) {
            console.error('Error fetching plan ingredient summary:', error)
            deps.prebatchItems.value = []
        }
        deps.fetchPreBatchRecords()
    }

    const onBatchSelect = async (plan: any, batch: any, index: number) => {
        selectedProductionPlan.value = plan.plan_id
        selectedBatchIndex.value = Number(index)
        deps.isBatchSelected.value = true
        filterBatchesByPlan()
        
        await deps.fetchPreBatchRecords()
    }

    const onBatchExpand = async (batch: any) => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batch.batch_id}`, {
                headers: getAuthHeader() as Record<string, string>
            })
            batchIngredients.value[batch.batch_id] = data.map((req: any) => {
                const ingInfo = deps.ingredients.value.find((i: any) => i.re_code === req.re_code)
                return {
                    ...req,
                    wh: ingInfo?.warehouse || req.wh || '-',
                    ingredient_name: req.ingredient_name || ingInfo?.name || req.re_code
                }
            })
        } catch (error) {
            console.error('Error fetching batch ingredients:', error)
            batchIngredients.value[batch.batch_id] = []
        }
    }

    const onBatchIngredientClick = async (batch: any, req: any, _plan: any) => {
        // Only send data to the weighing section (right pane)
        // Do NOT change the left monitor view (no onPlanShow / onBatchSelect)
        const reqVol = req.required_volume || 0
        deps.selectedReCode.value = req.re_code
        deps.selectedRequirementId.value = req.id
        deps.isBatchSelected.value = true
        deps.requireVolume.value = reqVol

        // Store batch_id for record fetching
        selectedBatchIndex.value = filteredBatches.value.findIndex(b => b.batch_id === batch.batch_id)

        const ingInfo = deps.ingredients.value.find((i: any) => i.re_code === req.re_code)
        const stdSize = ingInfo?.std_package_size || 0

        // Auto initial select container size from request volume (cap at standard size if set)
        if (stdSize > 0) {
            deps.packageSize.value = Math.min(reqVol, stdSize)
        } else {
            deps.packageSize.value = reqVol
        }

        await deps.fetchPreBatchRecords()
    }

    const advanceToNextBatch = async (currentBatchId: string, reCode: string) => {
        // Try using ingredientBatchDetail first (ingredient-driven workflow)
        const batchDetails = deps.ingredientBatchDetail?.value?.[reCode] || []
        if (batchDetails.length > 0) {
            // Find current index using fuzzy match for suffixes
            let currentIdx = batchDetails.findIndex((bd: any) => bd.batch_id === currentBatchId || currentBatchId.startsWith(bd.batch_id))

            // If still not found, try finding the first non-completed item as a safe fallback
            if (currentIdx === -1) {
                console.warn(`[Production] could not find EXACT match for ${currentBatchId} in details. Fallback to first.`)
                currentIdx = -1 // Start searching from beginning
            }

            for (let i = currentIdx + 1; i < batchDetails.length; i++) {
                const nextBd = batchDetails[i]
                if (nextBd.status !== 2) {
                    // Update global batch index so selectedBatch.value changes
                    const globalIdx = filteredBatches.value.findIndex(b => b.batch_id === nextBd.batch_id)
                    if (globalIdx !== -1) {
                        selectedBatchIndex.value = globalIdx
                    }

                    deps.selectedReCode.value = reCode
                    deps.selectedRequirementId.value = nextBd.req_id
                    deps.isBatchSelected.value = true
                    deps.requireVolume.value = nextBd.required_volume || 0

                    const ingInfo = deps.ingredients.value.find((i: any) => i.re_code === reCode)
                    if (ingInfo?.std_package_size && ingInfo.std_package_size > 0) {
                        deps.packageSize.value = ingInfo.std_package_size
                    }
                    await deps.fetchPreBatchRecords()
                    $q.notify({ type: 'info', message: `Next batch: ${nextBd.batch_id}`, position: 'top', timeout: 2000 })
                    return true
                }
            }
            if (deps.selectedIntakeLotId) deps.selectedIntakeLotId.value = ''
            $q.notify({ type: 'positive', message: `All batches completed for ${reCode}!`, position: 'top', timeout: 3000 })
            return false
        }

        // Fallback: use plan.batches
        const plan = productionPlans.value.find(p => p.plan_id === selectedProductionPlan.value)
        if (!plan || !plan.batches) return false

        // Fuzzy match for currentIdx
        let currentIdx = plan.batches.findIndex((b: any) => b.batch_id === currentBatchId || currentBatchId.startsWith(b.batch_id))

        for (let i = currentIdx + 1; i < plan.batches.length; i++) {
            const nextBatch = plan.batches[i]
            // CRITICAL: Even if marked Prepared, we should check if OUR ingredient is done.
            // Some batches are prematurely marked Prepared due to other ingredients being finished.

            if (!batchIngredients.value[nextBatch.batch_id]) {
                await onBatchExpand(nextBatch)
            }
            const nextReq = batchIngredients.value[nextBatch.batch_id]?.find((r: any) => r.re_code === reCode && r.status !== 2)
            if (nextReq) {
                await onBatchIngredientClick(nextBatch, nextReq, plan)
                $q.notify({ type: 'info', message: `Next batch: ${nextBatch.batch_id}`, position: 'top', timeout: 2000 })
                return true
            }
        }
        if (deps.selectedIntakeLotId) deps.selectedIntakeLotId.value = ''
        $q.notify({ type: 'positive', message: `All batches completed for ${reCode}!`, position: 'top', timeout: 3000 })
        return false
    }

    const finalizeBatchPreparation = async (batchId: number) => {
        try {
            await $fetch(`${appConfig.apiBaseUrl}/production-batches/${batchId}`, {
                method: 'PUT',
                body: { batch_prepare: true, status: 'Prepared' },
                headers: getAuthHeader() as Record<string, string>
            })
            $q.notify({ type: 'positive', message: t('preBatch.prepFinalized'), position: 'top' })
            await fetchBatchIds()
        } catch (e) {
            console.error('Failed to finalize batch preparation', e)
        }
    }

    const onSelectBatch = (index: number) => {
        selectedBatchIndex.value = index
    }

    // --- Watchers ---
    watch(selectedProductionPlan, () => {
        filterBatchesByPlan()
        deps.fetchPreBatchRecords()
    })

    watch(selectedBatchIndex, () => {
        deps.updateRequireVolume()
        deps.fetchPreBatchRecords()
    })

    return {
        // State
        selectedProductionPlan,
        selectedBatchIndex,
        isLoading,
        productionPlans,
        planFilter,
        productionPlanOptions,
        searchPlanId,
        searchSkuName,
        allBatches,
        filteredBatches,
        ingredientOptions,
        batchIngredients,
        // Computed
        filteredProductionPlans,
        plansWithBatches,
        batchIds,
        selectedBatch,
        selectedPlanDetails,
        structuredSkuList,
        // Functions
        fetchIngredients,
        fetchProductionPlans,
        fetchBatchIds,
        filterBatchesByPlan,
        onPlanShow,
        onBatchSelect,
        onBatchExpand,
        onBatchIngredientClick,
        advanceToNextBatch,
        finalizeBatchPreparation,
        onSelectBatch,
    }
}

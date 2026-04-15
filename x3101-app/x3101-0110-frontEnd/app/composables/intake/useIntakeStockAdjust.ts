/**
 * Composable: Stock Adjustment — form, submit, fetch, columns
 */
import { ref, computed, watch } from 'vue'
import type { QTableColumn } from 'quasar'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import { formatDateTime, type IngredientIntake } from '~/composables/intake/useIntakeHelpers'

export function useIntakeStockAdjust(
    rows: Ref<IngredientIntake[]>,
    fetchReceipts: () => Promise<void>,
) {
    const $q = useQuasar()
    const { user } = useAuth()

    const showAdjustDialog = ref(false)
    const adjReportFrom = ref('')
    const adjReportTo = ref('')
    const adjSelectedReCode = ref('')
    const adjSelectedLotId = ref('')
    const adjNewRemainVol = ref<number | null>(null)
    const adjReason = ref('')
    const adjRemark = ref('')
    const adjBy = ref(user.value?.username || 'operator')
    const adjSubmitting = ref(false)

    const adjReasonOptions = [
        'Physical Count', 'Spillage / Damage', 'Expired Write-off',
        'Quality Rejection', 'Receiving Correction', 'Transfer In', 'Transfer Out', 'Other',
    ]

    const activeReCodes = computed(() => {
        const codes = new Map<string, { re_code: string; material_description: string; mat_sap_code: string }>()
        rows.value.filter((r: any) => r.status === 'Active' && r.re_code)
            .forEach((r: any) => {
                if (!codes.has(r.re_code))
                    codes.set(r.re_code, { re_code: r.re_code, material_description: r.material_description || '', mat_sap_code: r.mat_sap_code || '' })
            })
        return Array.from(codes.values()).sort((a, b) => a.re_code.localeCompare(b.re_code))
    })

    const adjLotsForReCode = computed(() =>
        !adjSelectedReCode.value ? [] :
            rows.value.filter((r: any) => r.status === 'Active' && r.re_code === adjSelectedReCode.value).sort((a: any, b: any) => b.id - a.id)
    )

    const adjSelectedLot = computed(() =>
        !adjSelectedLotId.value ? null : rows.value.find((r: any) => r.intake_lot_id === adjSelectedLotId.value) || null
    )

    const adjTotalIntake = computed(() => adjSelectedLot.value?.intake_vol ?? 0)
    const adjRemaining = computed(() => adjSelectedLot.value?.remain_vol ?? 0)
    const adjComputedType = computed(() => adjNewRemainVol.value === null || !adjSelectedLot.value ? null : adjNewRemainVol.value >= adjRemaining.value ? 'increase' : 'decrease')
    const adjComputedQty = computed(() => adjNewRemainVol.value === null || !adjSelectedLot.value ? 0 : Math.abs(adjNewRemainVol.value - adjRemaining.value))

    const stockOverviewLots = computed(() =>
        !adjSelectedReCode.value ? [] :
            rows.value.filter((r: any) => r.status === 'Active' && r.re_code === adjSelectedReCode.value).sort((a: any, b: any) => b.id - a.id)
    )
    const stockOverviewSummary = computed(() => ({
        totalLots: stockOverviewLots.value.length,
        totalIntake: stockOverviewLots.value.reduce((s: number, r: any) => s + (r.intake_vol || 0), 0),
        totalRemaining: stockOverviewLots.value.reduce((s: number, r: any) => s + (r.remain_vol || 0), 0),
    }))

    const adjustments = ref<any[]>([])
    const adjColumnFilters = ref<Record<string, string>>({})
    const lotUsageMap = ref<Record<string, any[]>>({})

    const adjColumns = computed<QTableColumn[]>(() => [
        { name: 'adjusted_at', label: 'Date/Time', field: 'adjusted_at', align: 'center' as const, sortable: true, format: (val: any) => formatDateTime(val) },
        { name: 'intake_lot_id', label: 'Lot ID', field: 'intake_lot_id', align: 'left' as const, sortable: true },
        { name: 'mat_sap_code', label: 'SAP Code', field: 'mat_sap_code', align: 'left' as const, sortable: true },
        { name: 're_code', label: 'RE Code', field: 're_code', align: 'left' as const, sortable: true },
        { name: 'adjust_type', label: 'Type', field: 'adjust_type', align: 'center' as const, sortable: true },
        { name: 'adjust_qty', label: 'Qty', field: 'adjust_qty', align: 'right' as const, sortable: true },
        { name: 'prev_remain_vol', label: 'Before', field: 'prev_remain_vol', align: 'right' as const, sortable: true },
        { name: 'new_remain_vol', label: 'After', field: 'new_remain_vol', align: 'right' as const, sortable: true },
        { name: 'adjust_reason', label: 'Reason', field: 'adjust_reason', align: 'left' as const, sortable: true },
        { name: 'remark', label: 'Remark', field: 'remark', align: 'left' as const, sortable: true },
        { name: 'adjusted_by', label: 'By', field: 'adjusted_by', align: 'center' as const, sortable: true },
    ])

    const filteredAdjustments = computed(() => {
        let result = adjustments.value
        for (const [col, fv] of Object.entries(adjColumnFilters.value)) {
            if (!fv) continue
            const needle = fv.toLowerCase()
            result = result.filter((row: any) => {
                const v = col === 'adjusted_at' ? formatDateTime(row[col]) : String(row[col] ?? '')
                return v.toLowerCase().includes(needle)
            })
        }
        return result
    })

    const fetchAdjustments = async () => {
        try { adjustments.value = await $fetch<any[]>(`${appConfig.apiBaseUrl}/stock-adjustments/?limit=500`) }
        catch (e) { console.error('Failed to fetch adjustments:', e) }
    }

    const fetchLotUsage = async (lotId: string) => {
        try { lotUsageMap.value[lotId] = await $fetch<any[]>(`${appConfig.apiBaseUrl}/stock-adjustments/usage/${lotId}`) }
        catch (e) { lotUsageMap.value[lotId] = [] }
    }

    const resetAdjForm = () => { adjSelectedReCode.value = ''; adjSelectedLotId.value = ''; adjNewRemainVol.value = null; adjReason.value = ''; adjRemark.value = '' }

    const openStockAdjustDialog = (row: any) => {
        adjSelectedReCode.value = row.re_code; adjSelectedLotId.value = row.intake_lot_id
        adjNewRemainVol.value = null; adjReason.value = ''; adjRemark.value = ''
        adjBy.value = user.value?.username || 'operator'
        fetchAdjustments(); showAdjustDialog.value = true
    }

    const submitAdjustment = async () => {
        if (!adjSelectedLot.value || adjNewRemainVol.value === null || !adjReason.value) { $q.notify({ type: 'warning', message: 'Please fill all required fields' }); return }
        if (adjNewRemainVol.value < 0) { $q.notify({ type: 'negative', message: 'New value cannot be negative' }); return }
        const qty = adjComputedQty.value, type = adjComputedType.value
        if (qty === 0) { $q.notify({ type: 'info', message: 'No change' }); return }

        if (type === 'decrease') {
            const pct = (qty / (adjSelectedLot.value.remain_vol || 1)) * 100
            if (pct > 20) {
                const ok = await new Promise<boolean>(r => {
                    $q.dialog({ title: '⚠️ Large Adjustment', message: `Decrease by ${pct.toFixed(1)}%. Continue?`, cancel: true, persistent: true })
                        .onOk(() => r(true)).onCancel(() => r(false))
                })
                if (!ok) return
            }
        }

        adjSubmitting.value = true
        try {
            await $fetch(`${appConfig.apiBaseUrl}/stock-adjustments/`, { method: 'POST', body: { intake_lot_id: adjSelectedLotId.value, adjust_type: type, adjust_qty: qty, adjust_reason: adjReason.value, remark: adjRemark.value || null, adjusted_by: adjBy.value } })
            $q.notify({ type: 'positive', message: 'Stock adjusted successfully', icon: 'check_circle' })
            resetAdjForm(); fetchAdjustments(); fetchReceipts()
        } catch (e: any) { $q.notify({ type: 'negative', message: e.data?.detail || 'Adjustment failed' }) }
        finally { adjSubmitting.value = false }
    }

    watch(adjSelectedReCode, () => { adjSelectedLotId.value = ''; adjNewRemainVol.value = null })

    return {
        showAdjustDialog, adjReportFrom, adjReportTo,
        adjSelectedReCode, adjSelectedLotId, adjSelectedLot,
        adjNewRemainVol, adjReason, adjRemark, adjBy, adjSubmitting,
        adjReasonOptions, adjTotalIntake, adjRemaining,
        adjComputedType, adjComputedQty,
        activeReCodes, adjLotsForReCode, stockOverviewLots, stockOverviewSummary,
        adjustments, adjColumnFilters, adjColumns, filteredAdjustments,
        lotUsageMap, fetchLotUsage,
        fetchAdjustments, resetAdjForm, openStockAdjustDialog, submitAdjustment,
    }
}

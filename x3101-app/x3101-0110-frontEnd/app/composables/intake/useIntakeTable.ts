/**
 * Composable: Intake data table — columns, rows, filters, fetch, export/import
 */
import { ref, computed } from 'vue'
import type { QTableColumn } from 'quasar'
import { exportFile, useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import { formatDate, type IngredientIntake } from '~/composables/intake/useIntakeHelpers'

export function useIntakeTable(intakeMode?: Ref<'supplier' | 'internal'>) {
    const $q = useQuasar()
    const { getAuthHeader } = useAuth()
    const { t } = useI18n()

    const headers = () => getAuthHeader() as Record<string, string>

    // ── State ──
    const rows = ref<IngredientIntake[]>([])
    const isLoading = ref(false)
    const showAll = ref(false)
    const filters = ref<Record<string, string>>({})
    const showFilters = ref(false)
    const showDetailDialog = ref(false)
    const selectedRecord = ref<IngredientIntake | null>(null)
    const fileInput = ref<HTMLInputElement | null>(null)

    // ── Columns ──
    const columns = computed<QTableColumn[]>(() => [
        { name: 'expand', label: '', field: 'expand', align: 'center' },
        { name: 'intake_lot_id', align: 'center', label: t('ingredient.intakeLotId'), field: 'intake_lot_id', sortable: true },
        { name: 'intake_from', align: 'center', label: 'Intake From', field: 'intake_from', sortable: true },
        { name: 'intake_to', align: 'center', label: 'Intake To', field: 'intake_to', sortable: true },
        { name: 'mat_sap_code', align: 'center', label: t('ingredient.matSapCode'), field: 'mat_sap_code', sortable: true },
        { name: 're_code', align: 'center', label: t('ingredient.reCode'), field: 're_code', sortable: true },
        { name: 'material_description', align: 'left', label: t('ingredient.materialDesc'), field: 'material_description', sortable: true },
        { name: 'intake_vol', align: 'center', label: t('ingredient.intakeVolume'), field: 'intake_vol', sortable: true, format: (val: number) => val?.toFixed(4) || '-' },
        { name: 'package_intake', align: 'center', label: 'Package of Intake', field: 'package_intake', sortable: true },
        { name: 'manufacturing_date', align: 'center', label: t('ingredient.mfgDate'), field: 'manufacturing_date', sortable: true, format: (val: string) => formatDate(val) },
        { name: 'expire_date', align: 'center', label: t('ingredient.expiryDate'), field: 'expire_date', sortable: true, format: (val: string) => formatDate(val) },
        { name: 'xActions', align: 'center', label: t('common.actions'), field: 'xActions' },
    ])

    // ── Filtered Rows ──
    const filteredRows = computed(() => {
        let filtered = rows.value
        if (!showAll.value) {
            filtered = filtered.filter(row => row.status !== 'Cancelled' && row.status !== 'Reject')
        }
        // Warehouse Filter (FH or SPP)
        if (intakeMode?.value) {
            const targetWh = intakeMode.value === 'supplier' ? 'FH' : 'SPP'
            filtered = filtered.filter(row => row.intake_to === targetWh)
        }

        return filtered.filter(row =>
            Object.keys(filters.value).every(key => {
                const fv = filters.value[key]?.toLowerCase()
                if (!fv) return true
                return String((row as any)[key] || '').toLowerCase().includes(fv)
            })
        )
    })

    // ── Fetch ──
    const fetchReceipts = async (isBackground = false) => {
        if (!isBackground) isLoading.value = true
        try {
            const data = await $fetch<IngredientIntake[]>(`${appConfig.apiBaseUrl}/ingredient-intake-lists/`, { headers: headers() })
            if (JSON.stringify(data) !== JSON.stringify(rows.value)) rows.value = data
        } catch (e) { console.error('Failed to fetch history:', e) }
        finally { if (!isBackground) isLoading.value = false }
    }

    // ── Detail Dialog ──
    const openDetailDialog = (row: IngredientIntake) => {
        selectedRecord.value = row
        showDetailDialog.value = true
    }

    // ── Filters ──
    const resetFilters = () => { filters.value = {} }

    // ── CSV Export ──
    function wrapCsvValue(val: any, formatFn?: (v: any, r?: any) => string, row?: any, forceString = false) {
        let formatted = formatFn ? formatFn(val, row) : val
        formatted = formatted === void 0 || formatted === null ? '' : String(formatted)
        formatted = formatted.split('"').join('""')
        return forceString ? `="${formatted}"` : `"${formatted}"`
    }

    const exportTable = () => {
        const cols = columns.value.filter(c => c.name !== 'xActions')
        const stringCols = ['mat_sap_code', 're_code', 'intake_lot_id', 'po_number']
        const content = [cols.map(c => wrapCsvValue(c.label))]
            .concat(filteredRows.value.map(row =>
                cols.map(col =>
                    wrapCsvValue(
                        typeof col.field === 'function' ? col.field(row) : row[col.field as keyof IngredientIntake],
                        col.format, row, stringCols.includes(col.name),
                    )
                ).join(',')
            )).join('\r\n')

        const status = exportFile('ingredient-intake-export.csv', '\uFEFF' + content, 'text/csv')
        if (status !== true) {
            $q.notify({ message: t('ingredient.downloadDenied'), color: 'negative', icon: 'warning' })
        }
    }

    // ── CSV Import ──
    const importTable = () => { fileInput.value?.click() }

    const onFileSelected = async (event: Event) => {
        const target = event.target as HTMLInputElement
        const file = target.files?.[0]
        if (!file) return
        const formData = new FormData()
        formData.append('file', file)
        try {
            $q.loading.show({ message: t('ingredient.importingData') })
            const response = await fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/bulk-import`, {
                method: 'POST', headers: headers(), body: formData,
            })
            if (response.ok) {
                const result = await response.json()
                if (result.errors?.length) {
                    $q.notify({ type: 'warning', message: `Imported ${result.imported_count} records with some errors.`, caption: result.errors[0], timeout: 5000 })
                } else {
                    $q.notify({ type: 'positive', message: `Successfully imported ${result.imported_count} records.`, position: 'top' })
                }
                fetchReceipts()
            } else {
                const err = await response.json()
                throw new Error(err.detail || 'Import failed')
            }
        } catch (error: any) {
            console.error('Import error:', error)
            $q.notify({ type: 'negative', message: error.message || 'Failed to import CSV', position: 'top' })
        } finally {
            $q.loading.hide()
            target.value = ''
        }
    }

    return {
        rows, isLoading, showAll, filters, showFilters, columns, filteredRows,
        showDetailDialog, selectedRecord, openDetailDialog,
        fileInput, fetchReceipts, resetFilters, exportTable, importTable, onFileSelected,
    }
}

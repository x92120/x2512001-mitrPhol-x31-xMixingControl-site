/**
 * Composable: Intake form — fields, scanner, lookup, save, edit, reject, clear
 */
import { ref, watch, nextTick, computed } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import { formatDateForInput, formatDateToApi, type IngredientIntake } from '~/composables/intake/useIntakeHelpers'

export function useIntakeForm(
    rows: Ref<IngredientIntake[]>,
    fetchReceipts: () => Promise<void>,
    printLabel: (record: IngredientIntake) => Promise<void>,
    _intakeMode?: Ref<'supplier' | 'internal'>
) {
    const $q = useQuasar()
    const { getAuthHeader, user } = useAuth()
    const { t } = useI18n()

    const headers = () => getAuthHeader() as Record<string, string>
    const jsonHeaders = () => ({ ...headers(), 'Content-Type': 'application/json' })

    // ── Form Fields ──
    const ingredientCodeRef = ref<any>(null)
    const scannerReady = ref(true)
    const intakeFrom = ref('')
    const intakeTo = ref('')
    const manufacturingDate = ref('')
    const expireDate = ref('')
    const ingredientSearchQuery = ref('')
    const xIngredientName = ref('')
    const xMatSapCode = ref('')
    const xReCode = ref('')
    const intakeVol = ref('')
    const packageVol = ref('')
    const numberOfPackages = ref('')
    const intakeLotId = ref('')
    const showIngredientDialog = ref(false)
    const tempIngredientId = ref('')
    const isSaving = ref(false)

    // ── Intake Modes ──
    const intakeMode = _intakeMode || ref<'supplier' | 'internal'>('supplier')
    const showInternalScanDialog = ref(false)
    const internalScanBuffer = ref('')
    const isProcessingScan = ref(false)

    // ── Editing State ──
    const isEditing = ref(false)
    const editId = ref<string | null>(null)
    const originalRemainVol = ref<number | null>(null)
    const originalStatus = ref<string>('Active')

    // ── Batch Scan Buffer ──
    const scanBuffer = ref<any[]>([])
    const isAutoSaving = ref(false)
    let autoSaveTimer: any = null

    // ── Auto Save Watcher (Hands-Free) ──
    watch(scanBuffer, (newVal) => {
        if (newVal.length === 0) { isAutoSaving.value = false; return }
        if (autoSaveTimer) clearTimeout(autoSaveTimer)
        isAutoSaving.value = true

        autoSaveTimer = setTimeout(() => {
            saveAllInBuffer()
            isAutoSaving.value = false
        }, 1500) // 1.5 seconds of inactivity -> Auto Save
    }, { deep: true })

    // ── Ingredient Lookup ──
    const allIngredients = ref<any[]>([])
    const ingredientOptions = ref<any[]>([])

    const fetchAllIngredients = async () => {
        try {
            allIngredients.value = await $fetch<any[]>(`${appConfig.apiBaseUrl}/ingredients/`, { headers: headers() })
        } catch (e) { console.error('Failed to fetch all ingredients:', e) }
    }

    const filterIngredients = (val: string, update: (cb: () => void) => void) => {
        if (val === '') {
            update(() => { ingredientOptions.value = allIngredients.value })
            return
        }
        update(() => {
            const needle = val.toLowerCase()
            ingredientOptions.value = allIngredients.value.filter(v =>
                (v.name?.toLowerCase().includes(needle)) ||
                (String(v.mat_sap_code || '').toLowerCase().includes(needle)) ||
                (v.re_code?.toLowerCase().includes(needle))
            )
        })
    }

    const lookupIngredient = async (query: string, skipVolumes = false) => {
        if (!query || query.length < 3) {
            xIngredientName.value = xMatSapCode.value = xReCode.value = ''
            return
        }
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/ingredients/?lookup=${query}`, { headers: headers() })
            if (data.length > 0) {
                const ing = data[0]
                xIngredientName.value = ing.name
                xMatSapCode.value = ing.mat_sap_code
                xReCode.value = ing.re_code || ''
                if (ingredientSearchQuery.value !== ing.mat_sap_code) {
                    ingredientSearchQuery.value = ing.mat_sap_code
                    if (!skipVolumes) {
                        // Clear old data for new ingredient
                        expireDate.value = ''; manufacturingDate.value = ''
                        intakeVol.value = ''
                        intakeFrom.value = intakeMode.value === 'internal' ? 'Internal WH' : ''

                        packageVol.value = Number(ing.std_package_size || 25).toFixed(4)
                    }
                }
                $q.notify({ type: 'positive', message: `Found: ${ing.name}`, position: 'top', timeout: 1000 })
            } else {
                xIngredientName.value = xMatSapCode.value = xReCode.value = ''
            }
        } catch (e) { console.error('Lookup error:', e) }
    }

    // ── Auto-lookup on type/scan ──
    let lookupTimeout: any = null
    watch(ingredientSearchQuery, (newId) => {
        if (lookupTimeout) clearTimeout(lookupTimeout)
        lookupTimeout = setTimeout(() => {
            if (newId && !newId.includes('|')) {
                lookupIngredient(newId)
            }
        }, 500)
    })

    // ── Auto-calculate packages ──
    watch([intakeVol, packageVol], ([newVol, newPkg]) => {
        const vol = parseFloat(newVol)
        const pkg = parseFloat(newPkg)
        numberOfPackages.value = (!isNaN(vol) && !isNaN(pkg) && pkg > 0) ? Math.ceil(vol / pkg).toString() : ''
    })

    // ── Sync Vols for Internal Mode ──
    watch([intakeMode, intakeVol], ([mode, vol]) => {
        if (mode === 'internal' && vol) {
            packageVol.value = vol
        }
    })
    watch(packageVol, (pkg) => {
        if (intakeMode.value === 'internal' && pkg) {
            intakeVol.value = pkg
        }
    })

    // ── Reset on Tab Switch ──
    watch(intakeMode, () => {
        onClear()
    })

    // ── Auto-Process Internal Scan ──
    watch(internalScanBuffer, (val) => {
        if (isProcessingScan.value) return // Block if busy
        if (val && val.includes('|')) {
            const parts = val.split('|')
            // If it looks like a full scan (8+ pipes), wait tiny bit then process
            if (parts.length >= 9) {
                setTimeout(() => {
                    if (internalScanBuffer.value === val && !isProcessingScan.value) { // Ensure string hasn't changed & still not busy
                        processInternalScan()
                    }
                }, 100)
            }
        }
    })

    const parseDDMMMYYYY = (str: string | undefined | null) => {
        if (!str) return ''
        const cleaned = str.trim()
        const parts = cleaned.split('-')
        if (parts.length !== 3) return cleaned
        const months: Record<string, string> = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        const day = parts[0] || '01'
        const mmm = parts[1] || 'Jan'
        const year = parts[2] || '2025'
        const month = months[mmm.substring(0, 3)] || '01'
        return `${day.padStart(2, '0')}/${month}/${year}`
    }

    // ── Scanner ──
    const onScannerEnter = async () => {
        if (isProcessingScan.value) return
        const input = ingredientSearchQuery.value?.trim()
        if (!input) return

        isProcessingScan.value = true // LOCK

        try {
            // Pattern Check: Barcode scan with pipes |
            if (input.includes('|')) {
                ingredientSearchQuery.value = '' // Clear UI immediately for next scan
                const parts = input.split('|').map(p => p.trim())

                if (parts.length >= 8) {
                    const scannedIntakeId = parts[0]
                    const isDuplicate = rows.value.some(r => r.intake_lot_id === scannedIntakeId) || scanBuffer.value.some(b => b.intake_lot_id === scannedIntakeId)
                    if (isDuplicate) {
                        $q.notify({ type: 'negative', message: "Double Record!", position: 'top', timeout: 1500, icon: 'warning' })
                        return
                    }

                    const matSapCode = parts[1] || ''
                    await fetchAllIngredients()
                    const ingredient = allIngredients.value.find(i => i.mat_sap_code === matSapCode)

                    const expDateStr = parts[parts.length >= 9 ? 8 : 7] ?? ''
                    const mfgDateStr = parts[parts.length >= 9 ? 7 : 6] ?? ''

                    const entry = {
                        intake_lot_id: scannedIntakeId,
                        lot_id: parseDDMMMYYYY(parts[3] ?? ''),
                        mat_sap_code: matSapCode,
                        re_code: parts[2] || '',
                        material_description: ingredient?.name || parts[1] || '',
                        intake_vol: parseFloat(parts[4] ?? '0') || 0,
                        remain_vol: parseFloat(parts[4] ?? '0') || 0,
                        intake_package_vol: parseFloat(parts[4] ?? '0') || 0,
                        package_intake: 1,
                        expire_date: formatDateToApi(parseDDMMMYYYY(expDateStr)),
                        manufacturing_date: formatDateToApi(parseDDMMMYYYY(mfgDateStr)),
                        status: 'Active',
                        intake_by: user.value?.username || 'system',
                        intake_from: 'Internal WH',
                        intake_to: intakeMode.value === 'supplier' ? 'FH' : 'SPP'
                    }

                    scanBuffer.value.push(entry)
                    $q.notify({ type: 'positive', message: `Buffered: ${entry.material_description}`, position: 'top', timeout: 800 })
                    return
                }
            }

            // Fallback: Normal manual search by ID/Name/Code
            await lookupIngredient(input)

        } catch (error) {
            console.error('Scan error:', error)
            $q.notify({ type: 'negative', message: 'Error processing scan data' })
        } finally {
            // RELEASE LOCK after 500ms cooldown for next scan
            setTimeout(() => {
                isProcessingScan.value = false
            }, 500)
        }
    }

    const focusScannerInput = () => {
        nextTick(() => ingredientCodeRef.value?.focus())
    }

    // ── Generate Lot ID ──
    const generateIntakeLotId = async () => {
        try {
            const data = await $fetch<{ next_id: string }>(`${appConfig.apiBaseUrl}/ingredient-intake-next-id`)
            intakeLotId.value = data.next_id
        } catch (e: any) {
            console.error('Failed to generate ID', e)
            intakeLotId.value = 'Error: ' + e.message
        }
    }

    // ── Ingredient Dialog ──
    const openIngredientDialog = () => { tempIngredientId.value = ingredientSearchQuery.value; showIngredientDialog.value = true }
    const confirmIngredientCode = () => {
        const val = tempIngredientId.value
        if (val) { ingredientSearchQuery.value = val; showIngredientDialog.value = false; lookupIngredient(val) }
    }
    const cancelIngredientDialog = () => { tempIngredientId.value = ''; showIngredientDialog.value = false }

    // ── Status ──
    const statusOptions = ['Active', 'Hold', 'Reject']
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'Active': return 'positive'
            case 'Hold': return 'warning'
            case 'Reject': return 'negative'
            case 'Cancelled': return 'grey-7'
            default: return 'grey'
        }
    }

    const updateRecordStatus = async (row: IngredientIntake, newStatus: string) => {
        try {
            const response = await fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/${row.intake_lot_id}`, {
                method: 'PUT', headers: jsonHeaders(),
                body: JSON.stringify({ ...row, status: newStatus, edit_by: user.value?.username || 'system' }),
            })
            if (response.ok) {
                $q.notify({ type: 'positive', message: `${t('ingredient.statusUpdated')} ${newStatus}`, timeout: 1000 })
                row.status = newStatus
                fetchReceipts()
            } else { throw new Error('Failed to update status') }
        } catch (e) {
            console.error('Error updating status:', e)
            $q.notify({ type: 'negative', message: t('ingredient.statusUpdateFailed') })
        }
    }

    // ── Clear Form ──
    const onClear = () => {
        isEditing.value = false; editId.value = null
        ingredientSearchQuery.value = ''; expireDate.value = ''; manufacturingDate.value = ''
        xIngredientName.value = ''; xMatSapCode.value = ''; xReCode.value = ''
        intakeVol.value = ''; packageVol.value = ''; numberOfPackages.value = ''
        intakeFrom.value = ''; intakeTo.value = ''
        originalRemainVol.value = null; originalStatus.value = 'Active'
        generateIntakeLotId()
        focusScannerInput()
    }

    // ── Save (Create / Update) ──
    const onSave = async (silent = false) => {
        const missingFields: string[] = []
        if (!ingredientSearchQuery.value && !xMatSapCode.value) missingFields.push('Ingredient ID')
        if (!manufacturingDate.value) missingFields.push('MFG Date')
        if (!intakeFrom.value) missingFields.push('Intake From')
        if (!intakeVol.value) missingFields.push('Intake Volume')
        if (!expireDate.value) missingFields.push('Expire Date')

        if (missingFields.length) {
            $q.notify({ type: 'negative', message: `${t('ingredient.enterData')}: ${missingFields.join(', ')}`, position: 'top' })
            return
        }

        // Duplicate Check
        if (!isEditing.value) {
            const targetId = intakeLotId.value?.trim()
            const isDuplicate = rows.value.some(r => r.intake_lot_id?.trim() === targetId)
            if (isDuplicate) {
                $q.notify({
                    type: 'negative',
                    message: "Double Record!",
                    position: 'top',
                    icon: 'error',
                    timeout: 3000
                })
                return
            }
        }

        const rVol = parseFloat(intakeVol.value)
        if (isNaN(rVol) || rVol <= 0) {
            $q.notify({ type: 'negative', message: t('ingredient.volPositive'), position: 'top' })
            return
        }

        const proceedSave = async () => {
            isSaving.value = true
            const payload = {
                intake_lot_id: intakeLotId.value,
                intake_from: intakeFrom.value, intake_to: intakeTo.value,
                mat_sap_code: xMatSapCode.value, re_code: xReCode.value,
                material_description: xIngredientName.value, uom: 'kg',
                intake_vol: parseFloat(intakeVol.value),
                remain_vol: isEditing.value && originalRemainVol.value !== null ? originalRemainVol.value : parseFloat(intakeVol.value),
                intake_package_vol: packageVol.value ? parseFloat(packageVol.value) : null,
                package_intake: numberOfPackages.value ? parseInt(numberOfPackages.value) : null,
                expire_date: expireDate.value ? formatDateToApi(expireDate.value) : null,
                status: isEditing.value ? originalStatus.value : 'Active',
                intake_by: user.value?.username || 'cj',
                edit_by: user.value?.username || 'cj',
                manufacturing_date: manufacturingDate.value ? formatDateToApi(manufacturingDate.value) : null,
            }

            try {
                const url = isEditing.value && editId.value
                    ? `${appConfig.apiBaseUrl}/ingredient-intake-lists/${editId.value}`
                    : `${appConfig.apiBaseUrl}/ingredient-intake-lists/`
                const method = isEditing.value && editId.value ? 'PUT' : 'POST'
                const response = await fetch(url, { method, headers: jsonHeaders(), body: JSON.stringify(payload) })

                if (response.ok) {
                    const savedRecord = await response.json()
                    $q.notify({
                        type: 'positive', icon: 'check_circle', position: 'top',
                        message: isEditing.value ? t('ingredient.updatedSuccess') : t('ingredient.savedSuccess'),
                    })
                    if (!isEditing.value && intakeMode.value !== 'internal') printLabel(savedRecord)
                    onClear()
                    await fetchReceipts()
                } else {
                    const error = await response.json()
                    $q.notify({ type: 'negative', message: `${t('common.error')}: ${error.detail || t('ingredient.saveFailed')}`, position: 'top' })
                }
            } catch (e) {
                console.error('Save error:', e)
                $q.notify({ type: 'negative', message: t('ingredient.networkError'), position: 'top' })
            } finally { isSaving.value = false }
        }

        if (silent) {
            await proceedSave()
            return
        }

        $q.dialog({
            title: t('ingredient.confirmSave'),
            message: isEditing.value ? t('ingredient.confirmSaveUpdate') : t('ingredient.confirmSaveNew'),
            cancel: true, persistent: true,
        }).onOk(proceedSave)
    }

    // ── Edit ──
    const onEdit = (row: IngredientIntake) => {
        isEditing.value = true; editId.value = row.intake_lot_id
        intakeLotId.value = row.intake_lot_id;
        intakeFrom.value = row.intake_from || ''; intakeTo.value = row.intake_to || ''
        xMatSapCode.value = row.mat_sap_code; xReCode.value = row.re_code || ''
        intakeVol.value = row.intake_vol.toString()
        packageVol.value = row.intake_package_vol ? row.intake_package_vol.toString() : ''
        numberOfPackages.value = row.package_intake ? row.package_intake.toString() : ''
        expireDate.value = row.expire_date ? formatDateForInput(row.expire_date) : ''
        manufacturingDate.value = row.manufacturing_date ? formatDateForInput(row.manufacturing_date) : ''
        lookupIngredient(row.mat_sap_code)
        originalRemainVol.value = row.remain_vol; originalStatus.value = row.status
    }

    // ── Reject ──
    const onRejectIntake = (id: string) => {
        $q.dialog({
            title: t('common.confirm'),
            message: 'Are you sure you want to reject this intake record?',
            cancel: true,
            persistent: true,
            prompt: { model: '', type: 'text', label: t('ingredient.rejectReason'), outlined: true },
        }).onOk(async (remarks: string) => {
            try {
                // We fetch the row from local list to have full data for status update
                const row = rows.value.find(r => r.intake_lot_id === id)
                if (!row) return

                const response = await fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/${id}`, {
                    method: 'PUT', headers: jsonHeaders(),
                    body: JSON.stringify({ ...row, status: 'Reject', remarks: remarks || 'Rejected by user', edit_by: user.value?.username || 'system' }),
                })
                if (response.ok) {
                    $q.notify({ type: 'warning', message: t('ingredient.rejected') })
                    fetchReceipts()
                } else {
                    const err = await response.json()
                    $q.notify({ type: 'negative', message: `${t('ingredient.rejectFailed')}: ${err.detail || 'Unknown error'}` })
                }
            } catch (e) {
                console.error('Reject error:', e)
                $q.notify({ type: 'negative', message: t('ingredient.networkRejectError') })
            }
        })
    }

    // ── Delete ──
    const onDelete = (id: string) => {
        $q.dialog({
            title: 'Confirm Delete',
            message: 'Are you sure you want to PERMANENTLY delete this record? This action cannot be undone.',
            cancel: true,
            persistent: true,
            ok: {
                color: 'negative',
                label: 'Delete'
            }
        }).onOk(async () => {
            try {
                const response = await fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/${id}`, {
                    method: 'DELETE',
                    headers: jsonHeaders()
                })
                if (response.ok) {
                    $q.notify({ type: 'positive', message: 'Record deleted successfully' })
                    await fetchReceipts()
                } else {
                    $q.notify({ type: 'negative', message: 'Delete failed' })
                }
            } catch (e) {
                console.error('Delete error:', e)
                $q.notify({ type: 'negative', message: 'Network error during delete' })
            }
        })
    }

    const processInternalScan = async () => {
        if (isProcessingScan.value) return
        const input = internalScanBuffer.value?.trim()
        if (!input) return

        isProcessingScan.value = true
        try {
            if (input.includes('|')) {
                internalScanBuffer.value = ''
                const parts = input.split('|').map(p => p.trim())
                if (parts.length >= 8) {
                    const scannedIntakeId = parts[0]
                    const isDuplicate = rows.value.some(r => r.intake_lot_id === scannedIntakeId) || scanBuffer.value.some(b => b.intake_lot_id === scannedIntakeId)
                    if (isDuplicate) {
                        $q.notify({ type: 'negative', message: "Double Record!", position: 'top', timeout: 1000 })
                        return
                    }

                    const matSapCode = parts[1] || ''
                    await fetchAllIngredients()
                    const ingredient = allIngredients.value.find(i => i.mat_sap_code === matSapCode)

                    const mfgDateStr = parts[parts.length >= 9 ? 7 : 6] ?? ''
                    const expDateStr = parts[parts.length >= 9 ? 8 : 7] ?? ''

                    const entry = {
                        intake_lot_id: scannedIntakeId,
                        lot_id: parseDDMMMYYYY(parts[3] ?? ''),
                        mat_sap_code: matSapCode,
                        re_code: parts[2] || '',
                        material_description: ingredient?.name || parts[1] || '',
                        intake_vol: parseFloat(parts[4] ?? '0') || 0,
                        remain_vol: parseFloat(parts[4] ?? '0') || 0,
                        intake_package_vol: parseFloat(parts[4] ?? '0') || 0,
                        package_intake: 1,
                        expire_date: formatDateToApi(parseDDMMMYYYY(expDateStr)),
                        manufacturing_date: formatDateToApi(parseDDMMMYYYY(mfgDateStr)),
                        status: 'Active',
                        intake_by: user.value?.username || 'system',
                        intake_from: 'Internal WH',
                        intake_to: intakeMode.value === 'supplier' ? 'FH' : 'SPP'
                    }
                    scanBuffer.value.push(entry)
                    $q.notify({ type: 'positive', message: `Buffered: ${entry.material_description}`, position: 'top', timeout: 800 })
                    return
                }
            }
        } finally {
            setTimeout(() => { isProcessingScan.value = false }, 100)
        }
    }

    const saveAllInBuffer = async () => {
        if (scanBuffer.value.length === 0) return
        if (autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null }

        isSaving.value = true
        let successCount = 0
        try {
            for (const item of scanBuffer.value) {
                const response = await fetch(`${appConfig.apiBaseUrl}/ingredient-intake-lists/`, {
                    method: 'POST', headers: jsonHeaders(), body: JSON.stringify(item)
                })
                if (response.ok) successCount++
            }
            $q.notify({ type: 'positive', message: `Successfully saved ${successCount} records`, position: 'top' })
            scanBuffer.value = []
            await fetchReceipts()
        } catch (e) {
            console.error('Buffer save error', e)
        } finally {
            isSaving.value = false
        }
    }

    return {
        // Form fields
        ingredientCodeRef, scannerReady, intakeFrom, intakeTo, expireDate,
        ingredientSearchQuery, xIngredientName, xMatSapCode, xReCode,
        intakeVol, packageVol, numberOfPackages, manufacturingDate, intakeLotId,
        showIngredientDialog, tempIngredientId, isSaving,
        isEditing, editId,
        intakeMode, showInternalScanDialog, internalScanBuffer, isProcessingScan,
        // Ingredient lookup
        allIngredients, ingredientOptions, fetchAllIngredients, filterIngredients, lookupIngredient,
        // Actions
        onScannerEnter, focusScannerInput, generateIntakeLotId,
        openIngredientDialog, confirmIngredientCode, cancelIngredientDialog,
        statusOptions, getStatusColor, updateRecordStatus,
        onClear, onSave, onEdit, onRejectIntake, onDelete, processInternalScan,
        scanBuffer, saveAllInBuffer, isAutoSaving,
    }
}

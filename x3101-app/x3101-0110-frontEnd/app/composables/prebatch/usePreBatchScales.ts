/**
 * usePreBatchScales — Scale connections, weighing, tolerance checks
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

export interface ScaleDeps {
    $q: any
    t: (key: string, params?: any) => string
    selectedReCode: any
    requireVolume: any
    packageSize: any
    mqttClient?: any // Optional MQTT client for real-time updates
}

export function usePreBatchScales(deps: ScaleDeps) {
    const { $q, t, mqttClient } = deps

    // --- State ---
    const selectedScale = ref(0)
    const batchedVolume = ref(0)
    const currentPackageOrigins = ref<{ intake_lot_id: string, mat_sap_code: string | null, take_volume: number }[]>([])

    const scales = ref([
        {
            id: 1,
            label: 'Scale 1 (10 Kg +/- 0.02kg)',
            value: 0.0,
            displayValue: '0.0000',
            unit: 'kg',
            targetScaleId: 'scale-01',
            connected: false,
            tolerance: 0,
            precision: 4,
            isStable: true,
            isError: false
        },
        {
            id: 2,
            label: 'Scale 2 (30 Kg +/- 0.02kg)',
            value: 0.0,
            displayValue: '0.0000',
            unit: 'kg',
            targetScaleId: 'scale-02',
            connected: false,
            tolerance: 0,
            precision: 4,
            isStable: true,
            isError: false
        },
        {
            id: 3,
            label: 'Scale 3 (150 Kg +/- 0.02kg)',
            value: 0.0,
            displayValue: '0.000',
            unit: 'kg',
            targetScaleId: 'scale-03',
            connected: false,
            tolerance: 0,
            precision: 3,
            isStable: true,
            isError: false
        },
    ])

    const connectedScales = ref<Record<number, boolean>>({})
    const watchdogs: Record<string, any> = {}
    // Error counter per scale — only show error after ERROR_THRESHOLD consecutive errors
    const ERROR_THRESHOLD = 10
    const errorCounters: Record<string, number> = {}

    const resetWatchdog = (scaleId: string) => {
        if (watchdogs[scaleId]) clearTimeout(watchdogs[scaleId])
        watchdogs[scaleId] = setTimeout(() => {
            const scale = scales.value.find(s => s.targetScaleId === scaleId)
            if (scale) {
                // Watchdog timeout = connection lost, increment error counter
                errorCounters[scaleId] = (errorCounters[scaleId] || 0) + 1
                if (errorCounters[scaleId] >= ERROR_THRESHOLD) {
                    scale.isError = true
                    scale.displayValue = 'error!!!'
                }
            }
        }, 5000)
    }

    // --- Computed ---
    const activeScale = computed(() => scales.value.find(s => s.id === selectedScale.value))

    const actualScaleValue = computed(() => {
        return activeScale.value ? activeScale.value.value : 0
    })

    const remainVolume = computed(() => {
        // Total needed - (sum of previous packages) - (current scale value)
        return Math.max(0, deps.requireVolume.value - totalCompletedWeight.value - actualScaleValue.value)
    })

    const totalCompletedWeight = ref(0) // Set by records composable
    const completedCount = ref(0) // Set by records composable
    const nextPackageNo = ref(1) // Set by records composable
    // Used to freeze the value for Step 7 display so it doesn't show negative when bag is removed
    const lastCapturedWeight = ref(0)

    const targetWeight = computed(() => {
        if (deps.requireVolume.value <= 0 || deps.packageSize.value <= 0) return 0
        const remainForIngredient = Math.max(0, deps.requireVolume.value - totalCompletedWeight.value)
        return Math.min(remainForIngredient, deps.packageSize.value)
    })

    const requestBatch = computed(() => {
        const reqVol = deps.requireVolume.value || 0
        const pkgSize = deps.packageSize.value || 0
        if (reqVol <= 0 || pkgSize <= 0) return 1
        
        const tol = activeScale.value?.tolerance || 0.0001
        const unpackedVolume = Math.max(0, reqVol - totalCompletedWeight.value)
        
        if (unpackedVolume <= tol && completedCount.value > 0) {
            return completedCount.value
        }
        
        const needed = Math.ceil(Math.max(0, unpackedVolume - tol) / pkgSize)
        return Math.max(1, completedCount.value + needed)
    })

    const isToleranceExceeded = computed(() => {
        if (!activeScale.value) return false
        const diff = parseFloat(Math.abs(targetWeight.value - actualScaleValue.value).toFixed(4))
        return diff > activeScale.value.tolerance
    })

    const isPackagedVolumeInTol = computed(() => {
        if (!activeScale.value || deps.requireVolume.value <= 0) return false

        const totalReq = deps.requireVolume.value
        const currentSum = totalCompletedWeight.value + batchedVolume.value
        const tol = activeScale.value.tolerance

        const diff = parseFloat(Math.abs(totalReq - currentSum).toFixed(4))

        // Success if total reached within specific scale tolerance
        if (diff <= tol && currentSum > 0) return true

        // Check if current individual package matches target
        if (targetWeight.value > 0) {
            const pkgDiff = parseFloat(Math.abs(targetWeight.value - batchedVolume.value).toFixed(4))
            if (pkgDiff <= tol) return true
        }

        // Fallback: check current weight against packageSize (handles extra packages beyond requirement)
        if (batchedVolume.value > 0 && deps.packageSize.value > 0) {
            const pkgSizeDiff = parseFloat(Math.abs(deps.packageSize.value - batchedVolume.value).toFixed(4))
            if (pkgSizeDiff <= tol) return true
        }

        return false
    })

    const packagedVolumeBgColor = computed(() => {
        const totalReq = deps.requireVolume.value
        const currentSum = totalCompletedWeight.value + batchedVolume.value
        const tol = activeScale.value?.tolerance || 0.00001

        if (parseFloat(Math.abs(totalReq - currentSum).toFixed(4)) <= tol && currentSum > 0) return 'green-13'
        if (batchedVolume.value <= 0) return 'grey-2'
        return isPackagedVolumeInTol.value ? 'green-13' : 'yellow-13'
    })

    const preBatchSummary = computed(() => {
        return {
            count: 0,
            totalNetWeight: '0.0000',
            targetCount: requestBatch.value || 0,
            targetWeight: (deps.requireVolume.value || 0).toFixed(4),
            errorVolume: '0.0000',
            errorColor: 'text-green'
        }
    })

    // --- Actions ---
    const handleMqttMessage = (topic: string, message: any) => {
        if (!topic.startsWith('scale/')) return

        const scaleId = topic.split('/')[1] || ''
        const scaleIndex = scales.value.findIndex(s => s.targetScaleId === scaleId)
        if (scaleIndex === -1) return

        try {
            const data = JSON.parse(message.toString())
            const rawWeight = data.weight
            const rawUnit = data.unit || 'kg'

            // Normalize to KG for internal logic
            let weightKg = parseFloat(rawWeight) || 0
            if (rawUnit.toLowerCase() === 'g') {
                weightKg = weightKg / 1000
            }

            // Update scale object reactively
            const scale = scales.value[scaleIndex]
            if (scale) {
                // If no scale is selected yet, default to the one that first sends data
                if (selectedScale.value === 0) {
                    selectedScale.value = scale.id
                }

                scale.value = weightKg

                // Error threshold: count consecutive errors, only show error after 10+
                const hasError = data.error_msg === 'error!!!' || !!data.error_msg
                if (hasError) {
                    errorCounters[scaleId] = (errorCounters[scaleId] || 0) + 1
                    if (errorCounters[scaleId] >= ERROR_THRESHOLD) {
                        scale.displayValue = 'error!!!'
                        scale.isError = true
                    }
                    // Below threshold: keep last good value, don't change isError
                } else {
                    // Successful read — reset error counter and clear error state
                    errorCounters[scaleId] = 0
                    scale.displayValue = String(rawWeight)
                    scale.isError = false
                }

                scale.unit = rawUnit
                scale.isStable = data.stable !== undefined ? data.stable : true
                scale.connected = true
                connectedScales.value[scale.id] = true

                // Reset frontend-side watchdog
                resetWatchdog(scaleId)
            }
        } catch (e) {
            console.warn(`[Scale] Parse error for ${scaleId}:`, e)
        }
    }

    // --- Lifecycle ---
    const setupMqttListener = (client: any) => {
        if (!client) return
        client.on('message', handleMqttMessage)
        console.log('📡 usePreBatchScales: MQTT Listener Attached')
    }

    const removeMqttListener = (client: any) => {
        if (!client) return
        client.removeListener('message', handleMqttMessage)
        console.log('📡 usePreBatchScales: MQTT Listener Removed')
    }

    onMounted(() => {
        // Auto-connect all scales — monitor-only, no manual toggling needed
        for (const scale of scales.value) {
            scale.connected = true
            connectedScales.value[scale.id] = true
        }
        if (mqttClient.value) {
            setupMqttListener(mqttClient.value)
        }
    })

    onUnmounted(() => {
        if (mqttClient.value) {
            removeMqttListener(mqttClient.value)
        }
        // Clear all watchdogs
        Object.values(watchdogs).forEach(t => clearTimeout(t))
    })

    // Watch for late connection or client swap
    watch(mqttClient, (newClient, oldClient) => {
        if (oldClient) removeMqttListener(oldClient)
        if (newClient) setupMqttListener(newClient)
    })

    // --- Functions ---
    const onScaleInput = (scaleId: number, val: string) => {
        const scale = scales.value.find(s => s.id === scaleId)
        if (!scale) return
        const num = parseFloat(val) || 0
        scale.value = num
        scale.displayValue = num.toFixed(scale.precision)
    }

    const isScaleConnected = (id: number) => !!connectedScales.value[id]

    const toggleScaleConnection = (scaleId: number) => {
        const scale = scales.value.find((s) => s.id === scaleId)
        if (!scale) return
        connectedScales.value[scaleId] = !connectedScales.value[scaleId]
        scale.connected = connectedScales.value[scaleId]

        $q.notify({
            type: connectedScales.value[scaleId] ? 'positive' : 'info',
            message: connectedScales.value[scaleId] ? `${t('preBatch.connected')} ${scale.label}` : `${t('preBatch.disconnected')} ${scale.label}`,
            position: 'top',
            timeout: 500
        })
    }

    const getScaleClass = (scale: any) => {
        if (selectedScale.value !== scale.id) {
            return 'scale-card-border bg-grey-1'
        }
        return 'active-scale-border bg-white'
    }

    const getDisplayClass = (scale: any) => {
        if (scale.isError) return 'bg-red-blink text-white'
        if (selectedScale.value !== scale.id) return 'bg-grey-4 text-grey-6'
        const diff = parseFloat(Math.abs(targetWeight.value - scale.value).toFixed(4))
        if (targetWeight.value > 0 && diff <= scale.tolerance) return 'bg-green-6 text-white'
        return 'bg-yellow-13 text-black'
    }

    const onTare = (scaleId: number) => {
        $q.notify({ type: 'info', message: `Tare command sent to Scale ${scaleId}`, position: 'top', timeout: 1000 })
    }

    const getOriginDelta = () => {
        const reading = actualScaleValue.value
        const recorded = currentPackageOrigins.value.reduce((s, o) => s + o.take_volume, 0)
        return reading - recorded
    }

    const onAddLot = (selectedIntakeLotId: any, selectableIngredients: any, selectedInventoryItem: any) => {
        if (!selectedIntakeLotId.value) return
        const delta = getOriginDelta()
        if (delta <= 0.0001) {
            $q.notify({ type: 'warning', message: 'No new net volume to add since last lot' })
            return
        }
        const ing = selectableIngredients.value.find((i: any) => i.re_code === deps.selectedReCode.value)
        currentPackageOrigins.value.push({ intake_lot_id: selectedIntakeLotId.value, mat_sap_code: ing?.mat_sap_code || null, take_volume: delta })
        $q.notify({ type: 'positive', message: `Added ${delta.toFixed(4)}kg from lot ${selectedIntakeLotId.value}`, position: 'top' })
        selectedIntakeLotId.value = ''
        selectedInventoryItem.value = []
    }

    const onRemoveLot = (index: number) => {
        currentPackageOrigins.value.splice(index, 1)
    }

    // Scale selection is manual — operator clicks on a scale card to select it

    watch(actualScaleValue, (newVal) => {
        if (deps.selectedReCode.value) {
            // Keep actual value while weighing, but we'll show lastCapturedWeight in Step 7 UI
            batchedVolume.value = newVal
        } else {
            batchedVolume.value = 0
            lastCapturedWeight.value = 0
        }
    }, { immediate: true })

    watch(() => deps.selectedReCode.value, (newReCode) => {
        currentPackageOrigins.value = []
        if (newReCode) {
            batchedVolume.value = actualScaleValue.value
        } else {
            batchedVolume.value = 0
        }
    })

    return {
        // State
        selectedScale,
        scales,
        connectedScales,
        batchedVolume,
        currentPackageOrigins,
        totalCompletedWeight,
        completedCount,
        nextPackageNo,
        lastCapturedWeight,
        // Computed
        activeScale,
        actualScaleValue,
        remainVolume,
        targetWeight,
        requestBatch,
        isToleranceExceeded,
        isPackagedVolumeInTol,
        packagedVolumeBgColor,
        preBatchSummary,
        // Functions
        onScaleInput,
        isScaleConnected,
        toggleScaleConnection,
        getScaleClass,
        getDisplayClass,
        onTare,
        getOriginDelta,
        onAddLot,
        onRemoveLot,
    }
}

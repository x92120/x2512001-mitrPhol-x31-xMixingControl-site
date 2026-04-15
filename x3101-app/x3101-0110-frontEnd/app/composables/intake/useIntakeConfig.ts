/**
 * Composable: Intake From / Intake To (warehouse) config CRUD
 */
import { ref } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'

export function useIntakeConfig() {
    const { getAuthHeader } = useAuth()

    const intakeFromOptions = ref<{ label: string; value: string }[]>([])
    const intakeToOptions = ref<{ label: string; value: string }[]>([])
    const intakeFromList = ref<any[]>([])
    const intakeToList = ref<any[]>([])
    const newIntakeFromName = ref('')
    const newIntakeToId = ref('')
    const newIntakeToName = ref('')
    const showIntakeFromDialog = ref(false)
    const showIntakeToDialog = ref(false)

    const headers = () => getAuthHeader() as Record<string, string>
    const jsonHeaders = () => ({ ...headers(), 'Content-Type': 'application/json' })

    // ── Intake From ──
    const fetchIntakeFromOptions = async () => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/intake-from/`, { headers: headers() })
            intakeFromOptions.value = data.map(item => ({ label: item.name, value: item.name }))
            intakeFromList.value = data
        } catch (e) { console.error('Failed to fetch intake-from:', e) }
    }

    const addIntakeFrom = async () => {
        if (!newIntakeFromName.value) return
        try {
            const r = await fetch(`${appConfig.apiBaseUrl}/intake-from/`, {
                method: 'POST', headers: jsonHeaders(),
                body: JSON.stringify({ name: newIntakeFromName.value }),
            })
            if (r.ok) { newIntakeFromName.value = ''; await fetchIntakeFromOptions() }
        } catch (e) { console.error('Failed to add intake source:', e) }
    }

    const deleteIntakeFrom = async (id: number) => {
        try {
            const r = await fetch(`${appConfig.apiBaseUrl}/intake-from/${id}`, { method: 'DELETE', headers: headers() })
            if (r.ok) await fetchIntakeFromOptions()
        } catch (e) { console.error('Failed to delete intake source:', e) }
    }

    // ── Warehouse (Intake To) ──
    const fetchIntakeToOptions = async () => {
        try {
            const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/warehouses/`, { headers: headers() })
            intakeToOptions.value = data.map(item => ({
                label: `${item.warehouse_id} - ${item.name}`, value: item.warehouse_id,
            }))
            intakeToList.value = data
        } catch (e) { console.error('Failed to fetch warehouses:', e) }
    }

    const addWarehouse = async () => {
        if (!newIntakeToName.value || !newIntakeToId.value) return
        try {
            const r = await fetch(`${appConfig.apiBaseUrl}/warehouses/`, {
                method: 'POST', headers: jsonHeaders(),
                body: JSON.stringify({
                    warehouse_id: newIntakeToId.value.toUpperCase(),
                    name: newIntakeToName.value,
                    description: 'Added via Intake page',
                }),
            })
            if (r.ok) { newIntakeToName.value = ''; newIntakeToId.value = ''; await fetchIntakeToOptions() }
        } catch (e) { console.error('Failed to add warehouse:', e) }
    }

    const deleteWarehouse = async (id: string) => {
        try {
            const r = await fetch(`${appConfig.apiBaseUrl}/warehouses/${id}`, { method: 'DELETE', headers: headers() })
            if (r.ok) await fetchIntakeToOptions()
        } catch (e) { console.error('Failed to delete warehouse:', e) }
    }

    return {
        intakeFromOptions, intakeToOptions, intakeFromList, intakeToList,
        newIntakeFromName, newIntakeToId, newIntakeToName,
        showIntakeFromDialog, showIntakeToDialog,
        fetchIntakeFromOptions, addIntakeFrom, deleteIntakeFrom,
        fetchIntakeToOptions, addWarehouse, deleteWarehouse,
    }
}

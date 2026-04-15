/**
 * Shared helpers & types for Ingredient Intake page
 */

// ── Date Helpers ──
export const formatDate = (date: any) => {
    if (!date) return '-'
    const d = new Date(date)
    if (isNaN(d.getTime())) return date
    return d.toLocaleDateString('en-GB')
}

export const formatDateTime = (date: any) => {
    if (!date) return '-'
    const d = new Date(date)
    if (isNaN(d.getTime())) return date
    return d.toLocaleString('en-GB')
}

export const formatDateForInput = (date: any) => {
    if (!date) return ''
    const d = new Date(date)
    if (isNaN(d.getTime())) return ''
    const day = String(d.getDate()).padStart(2, '0')
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const year = d.getFullYear()
    return `${day}/${month}/${year}`
}

export const formatDateToApi = (val: string | null | undefined) => {
    if (!val) return null
    const cleaned = val.replace(/\//g, '')
    if (cleaned.length !== 8) return null
    const day = parseInt(cleaned.substring(0, 2))
    const month = parseInt(cleaned.substring(2, 4))
    const year = parseInt(cleaned.substring(4, 8))

    // Use Date.UTC to ensure the ISO string doesn't get shifted by local timezone
    const d = new Date(Date.UTC(year, month - 1, day, 0, 0, 0))
    if (isNaN(d.getTime())) return null
    return d.toISOString()
}

// ── Types ──
export interface IngredientIntakeHistory {
    id?: number
    intake_list_id: string
    action: string
    old_status?: string
    new_status?: string
    remarks?: string
    changed_by: string
    changed_at: string
}

export interface IngredientIntake {
    intake_lot_id: string
    intake_from: string
    intake_to: string
    blind_code: string | null
    mat_sap_code: string
    re_code: string
    material_description: string
    uom: string
    intake_vol: number
    remain_vol: number
    intake_package_vol: number | null
    package_intake: number | null
    expire_date: string | null
    status: string
    intake_by: string
    edit_by: string
    po_number: string | null
    manufacturing_date: string | null
    batch_prepare_vol: number | null
    std_package_size: number | null
    ext_date: string | null
    reserv_no: string | null
    stock_zone: string | null
    material_type: string | null
    intake_at: string
    edit_at: string
    history: IngredientIntakeHistory[]
    packages: { package_no: number; weight: number }[]
}

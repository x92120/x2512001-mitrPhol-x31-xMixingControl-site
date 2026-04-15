/**
 * Composable: Intake Reports — Summary, Expiry, Traceability, Movement
 */
import { ref } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import { formatDate, formatDateTime, formatDateForInput, formatDateToApi } from '~/composables/intake/useIntakeHelpers'

export function useIntakeReports() {
    const $q = useQuasar()
    const { getAuthHeader } = useAuth()
    const headers = () => getAuthHeader() as Record<string, string>

    // ── Traceability ──
    const showTraceDialog = ref(false)
    const traceSearchId = ref('')
    const traceLoading = ref(false)
    const traceOptions = ref<{ label: string; value: string; group: string }[]>([])
    const traceFilteredOptions = ref<{ label: string; value: string; group: string }[]>([])
    const traceOptionsLoading = ref(false)

    const fetchTraceOptions = async () => {
        traceOptionsLoading.value = true
        try {
            const [lotsRes, batchesRes] = await Promise.all([
                $fetch<any[]>(`${appConfig.apiBaseUrl}/ingredient-intake/?limit=500`, { headers: headers() }).catch(() => []),
                $fetch<any[]>(`${appConfig.apiBaseUrl}/production-batches/`, { headers: headers() }).catch(() => []),
            ])
            const opts: { label: string; value: string; group: string }[] = []
            const seenLots = new Set<string>()
            for (const lot of (lotsRes || [])) {
                if (lot.intake_lot_id && !seenLots.has(lot.intake_lot_id)) {
                    seenLots.add(lot.intake_lot_id)
                    opts.push({ label: `📦 ${lot.intake_lot_id} — ${lot.mat_sap_code || ''} (${lot.re_code || ''})`, value: lot.intake_lot_id, group: 'Intake Lots' })
                }
            }
            const seenBatches = new Set<string>()
            for (const b of (batchesRes || [])) {
                if (b.batch_id && !seenBatches.has(b.batch_id)) {
                    seenBatches.add(b.batch_id)
                    opts.push({ label: `🏭 ${b.batch_id} — ${b.sku_id || ''} (${b.status || ''})`, value: b.batch_id, group: 'Batches' })
                }
            }
            traceOptions.value = opts
            traceFilteredOptions.value = opts
        } catch (e) { console.error('Failed to fetch trace options:', e) }
        finally { traceOptionsLoading.value = false }
    }

    const onTraceFilter = (val: string, update: (fn: () => void) => void) => {
        update(() => {
            const q = (val || '').toLowerCase()
            traceFilteredOptions.value = q
                ? traceOptions.value.filter(o => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q))
                : traceOptions.value
        })
    }

    const onOpenTraceDialog = () => {
        showTraceDialog.value = true
        if (traceOptions.value.length === 0) fetchTraceOptions()
    }

    const printTraceReport = async () => {
        if (!traceSearchId.value.trim()) { $q.notify({ type: 'warning', message: 'Enter Lot ID or Batch ID' }); return }
        traceLoading.value = true
        const pw = window.open('', '_blank')
        if (!pw) { traceLoading.value = false; return }
        pw.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Tracing...</h2></body></html>')
        try {
            const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/traceability/${encodeURIComponent(traceSearchId.value.trim())}`)
            const now = new Date().toLocaleString('en-GB')
            let body = ''
            if (data.type === 'forward' && data.forward) {
                const lot = data.forward.lot, usages = data.forward.used_in || []
                const uRows = usages.map((u: any, i: number) => `<tr><td class="tc">${i + 1}</td><td>${u.batch_record_id}</td><td>${u.plan_id || '-'}</td><td>${u.re_code || '-'}</td><td class="tr">${(u.take_volume || 0).toFixed(4)}</td><td class="tc">${u.date ? new Date(u.date).toLocaleString('en-GB') : '-'}</td></tr>`).join('')
                body = `<div class="section-title">📦 Source Intake Lot</div><div class="info-card"><strong>${lot.intake_lot_id}</strong> | Mat SAP: ${lot.mat_sap_code || '-'} | RE: ${lot.re_code || '-'}<br>Intake: ${(lot.intake_vol || 0).toFixed(4)} kg | Remain: ${(lot.remain_vol || 0).toFixed(4)} kg</div><div class="section-title">🔗 Used In (${usages.length}) — Forward</div><table class="dt"><thead><tr><th>#</th><th>Batch Record</th><th>Plan</th><th>RE Code</th><th class="tr">Volume</th><th class="tc">Date</th></tr></thead><tbody>${uRows || '<tr><td colspan="6" class="tc">Not used</td></tr>'}</tbody></table>`
            } else if (data.type === 'backward' && data.backward) {
                const batch = data.backward.batch, ings = data.backward.ingredients || []
                const iRows = ings.map((ing: any, i: number) => {
                    const lr = (ing.lots_used || []).map((l: any) => `<tr class="bg-ok"><td></td><td>↳ ${l.intake_lot_id}</td><td>${l.mat_sap_code || '-'}</td><td class="tr">${(l.take_volume || 0).toFixed(4)}</td><td>${l.intake_from || '-'}</td></tr>`).join('')
                    return `<tr><td class="tc">${i + 1}</td><td class="tb">${ing.re_code}</td><td>${ing.ingredient_name || '-'}</td><td class="tr">${(ing.required_volume || 0).toFixed(4)}</td><td></td></tr>${lr}`
                }).join('')
                body = `<div class="section-title">🏭 Batch</div><div class="info-card"><strong>${batch.batch_id}</strong> | SKU: ${batch.sku_id} | Size: ${(batch.batch_size || 0).toFixed(4)} kg | Status: ${batch.status}<br>Plan: ${data.backward.plan.plan_id}</div><div class="section-title">🧪 Ingredients — Backward</div><table class="dt"><thead><tr><th>#</th><th>RE Code / Lot</th><th>Name / SAP</th><th class="tr">Volume</th><th>Source</th></tr></thead><tbody>${iRows}</tbody></table>`
            }
            const css = `@page{size:A4 portrait;margin:10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222}.header{background:#1565c0;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:8px}.header h1{font-size:22px}.info-bar{background:#e3f2fd;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#1565c0;font-weight:bold}.info-card{background:#f5f5f5;padding:10px 14px;border-left:4px solid #1565c0;border-radius:0 4px 4px 0;margin-bottom:10px;font-size:12px}.section-title{background:#37474f;color:#fff;padding:8px 14px;font-size:14px;font-weight:bold;border-radius:3px;margin:12px 0 4px}table.dt{width:100%;border-collapse:collapse;font-size:12px}table.dt th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.dt td{padding:4px 8px;border-bottom:1px solid #e0e0e0}.bg-ok{background:#f5f5f5}.grand{background:#1565c0;color:#fff;padding:12px 18px;border-radius:4px;margin-top:10px}.footer{border-top:2px solid #1565c0;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.tr{text-align:right}.tc{text-align:center}.tb{font-weight:bold}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}`
            const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Traceability</title><style>${css}</style></head><body><div class="header"><div><h1>🔗 Traceability Report</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div><div class="info-bar">🔍 Search: ${traceSearchId.value} | ${data.type === 'forward' ? '➡️ Forward' : '⬅️ Backward'}</div>${body}<div class="grand">Traceability — ${data.type} for: ${traceSearchId.value}</div><div class="footer"><span>xMixingControl-01</span><span>Traceability Report</span></div></body></html>`
            pw.document.open(); pw.document.write(html); pw.document.close()
            showTraceDialog.value = false
        } catch (e: any) { pw.close(); $q.notify({ type: 'negative', message: e?.data?.detail || 'Not found', position: 'top' }) }
        finally { traceLoading.value = false }
    }

    // ── Expiry Alert ──
    const printExpiryReport = async () => {
        const pw = window.open('', '_blank')
        if (!pw) return
        pw.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Loading...</h2></body></html>')
        try {
            const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/expiry-alert`)
            const now = new Date().toLocaleString('en-GB')
            const bld = (items: any[], bg: string) => (items || []).map((r: any, i: number) => `<tr class="${bg}"><td class="tc">${i + 1}</td><td class="tb">${r.mat_sap_code || '-'}</td><td>${r.re_code || '-'}</td><td>${r.intake_lot_id}</td><td class="tr">${(r.remain_vol || 0).toFixed(4)}</td><td>${r.intake_to || '-'}</td><td class="tc">${r.expire_date ? new Date(r.expire_date).toLocaleDateString('en-GB') : '-'}</td><td class="tc ${r.days_left != null && r.days_left < 0 ? 'text-red' : ''}">${r.days_left ?? '-'}</td></tr>`).join('')
            const s = data.summary || {}
            const thRow = '<tr><th style="width:3%">#</th><th>Mat SAP</th><th>RE Code</th><th>Intake Lot</th><th class="tr">Remain</th><th>Location</th><th class="tc">Expiry</th><th class="tc">Days</th></tr>'
            const css = `@page{size:A4 landscape;margin:8mm 10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222}.header{background:#c62828;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:8px}.header h1{font-size:22px}.info-bar{background:#ffebee;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#c62828;font-weight:bold}.section-title{padding:8px 14px;font-size:14px;font-weight:bold;border-radius:3px;margin:12px 0 4px;color:#fff}.sec-expired{background:#c62828}.sec-warning{background:#ef6c00}.sec-ok{background:#2e7d32}table.dt{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}table.dt th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.dt td{padding:4px 8px;border-bottom:1px solid #e0e0e0}.bg-exp{background:#ffebee}.bg-warn{background:#fff8e1}.bg-ok{background:#e8f5e9}.text-red{color:#c62828;font-weight:bold}.grand{background:#37474f;color:#fff;padding:12px 18px;border-radius:4px;margin-top:10px;display:flex;justify-content:space-between}.footer{border-top:2px solid #c62828;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.tr{text-align:right}.tc{text-align:center}.tb{font-weight:bold}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}`
            const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Expiry Alert</title><style>${css}</style></head><body><div class="header"><div><h1>⚠️ Ingredient Expiry Alert</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div><div class="info-bar">📦 Total: ${s.total_lots || 0} | 🔴 Expired: ${s.expired_count || 0} | 🟠 Warning: ${s.warning_count || 0} | 🟢 OK: ${s.ok_count || 0}</div>${(data.expired || []).length ? `<div class="section-title sec-expired">🔴 EXPIRED (${data.expired.length})</div><table class="dt"><thead>${thRow}</thead><tbody>${bld(data.expired, 'bg-exp')}</tbody></table>` : ''}${(data.warning || []).length ? `<div class="section-title sec-warning">🟠 EXPIRING SOON (${data.warning.length})</div><table class="dt"><thead>${thRow}</thead><tbody>${bld(data.warning, 'bg-warn')}</tbody></table>` : ''}<div class="section-title sec-ok">🟢 OK — ${(data.ok || []).length} lots</div><div class="grand"><span>Total: ${s.total_lots || 0} lots</span><span>🔴 ${s.expired_count || 0} | 🟠 ${s.warning_count || 0} | 🟢 ${s.ok_count || 0}</span></div><div class="footer"><span>xMixingControl-01</span><span>Expiry Alert</span></div></body></html>`
            pw.document.open(); pw.document.write(html); pw.document.close()
        } catch (e) { console.error(e); pw.close(); $q.notify({ type: 'negative', message: 'Failed', position: 'top' }) }
    }

    // ── Summary Report ──
    const showSummaryReport = ref(false)
    const summaryFromDate = ref(formatDateForInput(new Date()))
    const summaryToDate = ref(formatDateForInput(new Date()))
    const summaryLoading = ref(false)

    const printSummaryReport = async () => {
        summaryLoading.value = true
        const pw = window.open('', '_blank')
        if (!pw) { summaryLoading.value = false; return }
        pw.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Loading...</h2></body></html>')
        try {
            const fromApi = formatDateToApi(summaryFromDate.value)
            const toApi = formatDateToApi(summaryToDate.value)
            let url = `${appConfig.apiBaseUrl}/stock-adjustments/summary-report`
            const params: string[] = []
            if (fromApi) params.push(`from_date=${fromApi}`)
            if (toApi) params.push(`to_date=${toApi}`)
            if (params.length) url += '?' + params.join('&')

            const data = await $fetch<Record<string, any[]>>(url)
            const warehouses = Object.keys(data).sort()
            const now = new Date().toLocaleString('en-GB')
            const fromLabel = summaryFromDate.value || 'All'
            const toLabel = summaryToDate.value || 'All'

            const whSections = warehouses.map(wh => {
                const lots = data[wh] || []
                const ingMap = new Map<string, any[]>()
                for (const lot of lots) {
                    const key = `${lot.mat_sap_code || '-'}||${lot.re_code || '-'}`
                    if (!ingMap.has(key)) ingMap.set(key, [])
                    ingMap.get(key)!.push(lot)
                }
                const whTI = lots.reduce((s: number, l: any) => s + (l.intake_vol || 0), 0)
                const whTU = lots.reduce((s: number, l: any) => s + (l.used_vol || 0), 0)
                const whTA = lots.reduce((s: number, l: any) => s + (l.adj_total || 0), 0)
                const whTR = lots.reduce((s: number, l: any) => s + (l.remain_vol || 0), 0)

                const ingSections = Array.from(ingMap.entries()).map(([key, ingLots], idx) => {
                    const [matSap, reCode] = key.split('||')
                    const iI = ingLots.reduce((s: number, l: any) => s + (l.intake_vol || 0), 0)
                    const iU = ingLots.reduce((s: number, l: any) => s + (l.used_vol || 0), 0)
                    const iA = ingLots.reduce((s: number, l: any) => s + (l.adj_total || 0), 0)
                    const iR = ingLots.reduce((s: number, l: any) => s + (l.remain_vol || 0), 0)
                    const lotRows = ingLots.map((l: any, li: number) => `<tr class="lot-row"><td class="tc" style="color:#999">${li + 1}</td><td>${l.intake_lot_id}</td><td>${l.manufacturing_date ? new Date(l.manufacturing_date).toLocaleDateString('en-GB') : '-'}</td><td class="tr">${(l.intake_vol || 0).toFixed(4)}</td><td class="tr text-red">${(l.used_vol || 0).toFixed(4)}</td><td class="tr">${(l.adj_total || 0).toFixed(4)}</td><td class="tr text-green text-bold">${(l.remain_vol || 0).toFixed(4)}</td><td class="tc">${l.intake_at ? new Date(l.intake_at).toLocaleDateString('en-GB') : '-'}</td><td class="tc">${l.expire_date ? new Date(l.expire_date).toLocaleDateString('en-GB') : '-'}</td></tr>`).join('')
                    return `<div class="ing-header"><span class="ing-num">${idx + 1}.</span><span class="ing-sap">${matSap}</span><span class="ing-re">${reCode}</span><span class="ing-desc">${ingLots[0]?.material_description || ''}</span><span class="ing-count">${ingLots.length} lot${ingLots.length > 1 ? 's' : ''}</span></div><table class="lot-table"><thead><tr><th>#</th><th>Intake Lot</th><th>Mfg Date</th><th class="tr">Intake</th><th class="tr">Usage</th><th class="tr">Adjust</th><th class="tr">Remain</th><th class="tc">Intake Date</th><th class="tc">Expiry</th></tr></thead><tbody>${lotRows}<tr class="ing-summary-row"><td colspan="3" class="tr text-bold">Summary ${matSap} (${reCode}):</td><td class="tr text-bold">${iI.toFixed(4)}</td><td class="tr text-bold text-red">${iU.toFixed(4)}</td><td class="tr text-bold">${iA.toFixed(4)}</td><td class="tr text-bold text-green">${iR.toFixed(4)}</td><td colspan="2"></td></tr></tbody></table>`
                }).join('')

                return `<div class="location-section"><div class="location-header"><span class="loc-badge">${wh}</span><span>Location: ${wh}</span></div>${ingSections}<div class="location-total"><span>Total (${wh}) — ${lots.length} lots, ${ingMap.size} ingredients</span><span>Intake: <strong>${whTI.toFixed(4)}</strong> | Usage: <strong class="red">${whTU.toFixed(4)}</strong> | Adjust: <strong>${whTA.toFixed(4)}</strong> | Remain: <strong class="green">${whTR.toFixed(4)}</strong></span></div></div>`
            }).join('')

            const allLots = warehouses.flatMap(wh => data[wh] || [])
            const gI = allLots.reduce((s: number, l: any) => s + (l.intake_vol || 0), 0)
            const gU = allLots.reduce((s: number, l: any) => s + (l.used_vol || 0), 0)
            const gA = allLots.reduce((s: number, l: any) => s + (l.adj_total || 0), 0)
            const gR = allLots.reduce((s: number, l: any) => s + (l.remain_vol || 0), 0)
            const totalIng = warehouses.reduce((c, wh) => c + new Set((data[wh] || []).map((l: any) => `${l.mat_sap_code}||${l.re_code}`)).size, 0)

            const css = `@page{size:A4 landscape;margin:8mm 10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222;line-height:1.4}.report-header{background:#1565c0;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:6px}.report-header h1{font-size:22px}.date-bar{background:#e3f2fd;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#1565c0;font-weight:bold}.footer{border-top:2px solid #1565c0;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.location-section{margin-bottom:16px}.location-header{background:#263238;color:#fff;padding:10px 16px;font-size:16px;font-weight:bold;border-radius:3px;margin-bottom:6px}.loc-badge{background:#ffc107;color:#000;padding:3px 10px;border-radius:4px;font-size:13px;margin-right:8px;font-weight:bold}.location-total{background:#37474f;color:#fff;padding:8px 14px;border-radius:3px;margin-top:6px;font-size:13px;display:flex;justify-content:space-between}.location-total .red{color:#ef9a9a}.location-total .green{color:#a5d6a7}.ing-header{background:#e8eaf6;padding:7px 14px;margin-top:8px;margin-bottom:2px;border-left:4px solid #3f51b5;border-radius:2px;font-size:13px}.ing-num{color:#5c6bc0;font-weight:bold;margin-right:6px}.ing-sap{font-weight:bold;color:#1a237e;font-size:14px;margin-right:12px}.ing-re{background:#c8e6c9;color:#2e7d32;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:bold;margin-right:12px}.ing-desc{color:#666;font-size:12px}.ing-count{float:right;color:#5c6bc0;font-size:12px;font-weight:bold}table.lot-table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:2px;table-layout:fixed}table.lot-table th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.lot-table td{padding:4px 8px;border-bottom:1px solid #e0e0e0}.lot-row:nth-child(even) td{background:#fafafa}.ing-summary-row td{background:#e8eaf6!important;font-weight:bold;border-top:2px solid #3f51b5;border-bottom:2px solid #3f51b5}.tr{text-align:right}.tc{text-align:center}.text-bold{font-weight:bold}.text-red{color:#c62828}.text-green{color:#2e7d32}.grand-total{background:#1565c0;color:#fff;padding:12px 18px;border-radius:4px;margin-top:10px}.grand-total table{width:100%;margin-top:6px}.grand-total table td{padding:3px 8px;font-size:13px}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}`
            const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Stock Summary</title><style>${css}</style></head><body><div class="report-header"><div><h1>📦 Stock Summary Report</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing — Ingredient Inventory</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div><div class="date-bar">📅 ${fromLabel} — ${toLabel} | Locations: ${warehouses.join(', ')} | Ingredients: ${totalIng} | Lots: ${allLots.length}</div>${whSections}<div class="grand-total"><div style="display:flex;justify-content:space-between;align-items:center"><span><strong>Grand Total</strong> — ${allLots.length} lots, ${totalIng} ingredients, ${warehouses.length} locations</span></div><table><tr><td>Intake:</td><td class="tr"><strong>${gI.toFixed(4)}</strong> kg</td><td>Usage:</td><td class="tr"><strong>${gU.toFixed(4)}</strong> kg</td><td>Adjust:</td><td class="tr"><strong>${gA.toFixed(4)}</strong> kg</td><td>Remain:</td><td class="tr"><strong>${gR.toFixed(4)}</strong> kg</td></tr></table></div><div class="footer"><span>xMixingControl-01</span><span>Stock Summary — ${fromLabel} to ${toLabel}</span></div></body></html>`
            pw.document.open(); pw.document.write(html); pw.document.close()
            showSummaryReport.value = false
        } catch (e) { console.error(e); pw.close(); $q.notify({ type: 'negative', message: 'Failed to generate report', position: 'top' }) }
        finally { summaryLoading.value = false }
    }

    // ── Movement Report ──
    const printAdjustmentReport = async (adjReportFrom: string, adjReportTo: string, adjustments: any[]) => {
        const params = new URLSearchParams()
        if (adjReportFrom) params.set('date_from', adjReportFrom)
        if (adjReportTo) params.set('date_to', adjReportTo)
        let movements: any[] = []
        try {
            movements = await $fetch<any[]>(`${appConfig.apiBaseUrl}/stock-adjustments/movements/?${params.toString()}`)
        } catch {
            movements = adjustments.map((r: any) => ({ movement_type: 'adjustment', date: r.adjusted_at, intake_lot_id: r.intake_lot_id, mat_sap_code: r.mat_sap_code || '', re_code: r.re_code || '', direction: r.adjust_type, qty: r.adjust_qty, prev_vol: r.prev_remain_vol, new_vol: r.new_remain_vol, reason: r.adjust_reason || '', remark: r.remark || '', user: r.adjusted_by || '', reference: '' }))
        }
        const fromL = adjReportFrom || 'Beginning', toL = adjReportTo || 'Now'
        const tRows = movements.map((m: any) => `<tr><td>${m.date ? formatDateTime(m.date) : ''}</td><td><span class="badge ${m.movement_type === 'adjustment' ? 'badge-adj' : 'badge-pre'}">${m.movement_type === 'adjustment' ? 'ADJ' : 'PRE'}</span></td><td>${m.intake_lot_id || ''}</td><td>${m.mat_sap_code || ''}</td><td>${m.re_code || ''}</td><td class="${m.direction === 'increase' ? 'increase' : 'decrease'}">${m.direction === 'increase' ? '↑' : '↓'} ${m.direction}</td><td class="${m.direction === 'increase' ? 'increase' : 'decrease'}">${m.direction === 'increase' ? '+' : '−'}${m.qty?.toFixed(3) || '0.000'}</td><td>${m.prev_vol != null ? m.prev_vol.toFixed(3) : '-'}</td><td>${m.new_vol != null ? m.new_vol.toFixed(3) : '-'}</td><td>${m.reason || ''}</td><td style="font-size:10px">${m.reference || m.remark || ''}</td><td>${m.user || ''}</td></tr>`).join('')
        const css = `@page{size:landscape;margin:10mm}body{font-family:'Segoe UI',Arial,sans-serif;margin:16px;color:#333}h1{color:#1565c0;font-size:20px;margin-bottom:4px}.subtitle{color:#666;font-size:13px;margin-bottom:12px}table{width:100%;border-collapse:collapse;font-size:11px}th{background:#1565c0;color:#fff;padding:6px 5px;text-align:left;white-space:nowrap}td{padding:5px;border-bottom:1px solid #ddd}tr:nth-child(even){background:#f5f5f5}.increase{color:#2e7d32;font-weight:bold}.decrease{color:#c62828;font-weight:bold}.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:bold}.badge-adj{background:#f3e5f5;color:#6a1b9a}.badge-pre{background:#e3f2fd;color:#1565c0}.footer{margin-top:12px;font-size:10px;color:#999;text-align:right}.summary{display:flex;gap:24px;margin-bottom:12px;font-size:12px}.summary-item{padding:4px 12px;border-radius:4px;background:#f5f5f5}@media print{body{margin:8px}}`
        const html = `<html><head><title>Stock Movement</title><style>${css}</style></head><body><h1>📋 Stock Movement Report</h1><div class="subtitle">Period: ${fromL} — ${toL}</div><div class="summary"><div class="summary-item">Total: <strong>${movements.length}</strong></div><div class="summary-item"><span class="badge badge-adj">ADJ</span> ${movements.filter(m => m.movement_type === 'adjustment').length}</div><div class="summary-item"><span class="badge badge-pre">PRE</span> ${movements.filter(m => m.movement_type === 'prebatch').length}</div></div><table><thead><tr><th>Date</th><th>Source</th><th>Lot ID</th><th>SAP</th><th>RE</th><th>Dir</th><th>Qty</th><th>Before</th><th>After</th><th>Reason</th><th>Ref</th><th>By</th></tr></thead><tbody>${tRows}</tbody></table><div class="footer">Printed: ${new Date().toLocaleString('en-GB', { timeZone: 'Asia/Bangkok' })}</div></body></html>`
        const pw = window.open('', '_blank')
        if (pw) { pw.document.write(html); pw.document.close(); pw.focus(); setTimeout(() => pw.print(), 500) }
    }

    return {
        showTraceDialog, traceSearchId, traceLoading,
        traceOptions, traceFilteredOptions, traceOptionsLoading,
        fetchTraceOptions, onTraceFilter, onOpenTraceDialog, printTraceReport,
        printExpiryReport,
        showSummaryReport, summaryFromDate, summaryToDate, summaryLoading, printSummaryReport,
        printAdjustmentReport,
    }
}

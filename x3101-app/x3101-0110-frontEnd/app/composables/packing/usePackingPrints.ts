/**
 * usePackingPrints — All label/report print functions for the Packing List page
 * Extracted from x50-PackingList.vue to keep the page component focused on UI logic.
 */
import QRCode from 'qrcode'
import { useLabelPrinter } from '../useLabelPrinter'

export interface PackingPrintDeps {
    $q: any
    plans: any              // ref<any[]>
    selectedBatch: any      // ref
    batchInfo: any          // ref
    bagsByWarehouse: any    // ref<{ FH: any[], SPP: any[] }>
    allRecords: any         // ref<any[]>
    transferredBoxes: any   // ref<TransferredBox[]>
    selectedForTransfer: any // ref<string[]>
    showTransferDialog: any // ref<boolean>
    currentBoxScans: any    // ref<any[]>
    filteredBoxScans: any   // computed<any[]>
    batchRecords: any       // ref<any[]> — prebatch_recs (per-package)
}

export const usePackingPrints = (deps: PackingPrintDeps) => {
    const { generateLabelSvg, printLabel } = useLabelPrinter()

    // ── Helper: open A4 print window ──
    const openA4PrintWindow = (title: string, svgContent: string) => {
        const pw = Math.round(window.screen.width * 0.8)
        const ph = Math.round(window.screen.height * 0.8)
        const left = Math.round((window.screen.width - pw) / 2)
        const top = Math.round((window.screen.height - ph) / 2)
        const win = window.open('', '_blank', `width=${pw},height=${ph},left=${left},top=${top}`)
        if (!win) {
            deps.$q.notify({ type: 'warning', message: 'Popup blocked — allow popups and retry', position: 'top' })
            return null
        }
        win.document.write(`<!DOCTYPE html><html><head>
      <title>${title}</title>
      <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background:#888; display:flex; justify-content:center; align-items:flex-start; padding:20px; }
        .page { background:#fff; box-shadow:0 4px 20px rgba(0,0,0,.4); }
        @media print {
          body { background:white; padding:0; }
          .page { box-shadow:none; }
          @page { size: A4 portrait; margin:0; }
        }
      </style>
    </head><body>
      <div class="page">${svgContent}</div>
      <script>window.onload = () => { setTimeout(() => window.print(), 400) }<\/script>
    </body></html>`)
        win.document.close()
        return win
    }

    // ── Helper: open 4x3 print window ──
    const open4x3PrintWindow = (title: string, svgContent: string) => {
        // Use hidden iframe to print without opening a new window
        let iframe = document.getElementById('__print_iframe') as HTMLIFrameElement
        if (iframe) iframe.remove()
        iframe = document.createElement('iframe')
        iframe.id = '__print_iframe'
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:0;height:0;border:none;'
        document.body.appendChild(iframe)

        const doc = iframe.contentDocument || iframe.contentWindow?.document
        if (!doc) {
            deps.$q.notify({ type: 'warning', message: 'Print failed — cannot access iframe', position: 'top' })
            return null
        }
        doc.open()
        doc.write(`<!DOCTYPE html><html><head>
      <title>${title}</title>
      <style>
        @page { size: 4in 3in; margin: 0; }
        body  { margin: 0; padding: 0; background: #fff; display: flex; flex-direction: column; align-items: center; }
        svg   { display: block; width: 4in; height: 3in; page-break-after: always; break-after: page; }
        svg:last-of-type { page-break-after: auto; break-after: auto; }
        @media print {
            body { display: block; }
        }
      </style>
    </head><body>${svgContent}</body></html>`)
        doc.close()

        // Wait for content to render, then print
        setTimeout(() => {
            iframe.contentWindow?.print()
            // Refocus scan input after print dialog closes
            setTimeout(() => {
                const scanInput = document.querySelector('input[placeholder*="Scan"]') as HTMLInputElement
                if (scanInput) scanInput.focus()
                iframe.remove()
            }, 500)
        }, 300)
        return iframe
    }

    // ── Helper: generate report number ──
    const makeReportNo = (prefix: string) => {
        const now = new Date()
        return `${prefix}-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(Math.floor(Math.random() * 9000) + 1000)}`
    }

    // ═══════════════════════════════════════════════════════════════════
    // 1. PACKING BOX DETAIL REPORT (A4)
    // ═══════════════════════════════════════════════════════════════════
    const printPackingBoxReport = async (batchId: string, wh: 'FH' | 'SPP') => {
        const plan = deps.plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === batchId))
        const whBags = wh === 'FH' ? deps.bagsByWarehouse.value.FH : deps.bagsByWarehouse.value.SPP

        let bags = whBags.filter((b: any) => b.re_code)
        if (deps.selectedBatch.value?.batch_id !== batchId) {
            bags = deps.allRecords.value.filter((r: any) => {
                const matchBatch = r.plan_id === plan?.plan_id && r.batch_record_id?.startsWith(batchId)
                const matchWh = wh === 'FH'
                    ? ['FH', 'CL', 'FL'].some(p => (r.re_code || '').toUpperCase().startsWith(p))
                    : !['FH', 'CL', 'FL'].some(p => (r.re_code || '').toUpperCase().startsWith(p))
                return matchBatch && matchWh
            })
        }

        // Group strictly by prebatch_id as requested (or fallback to re_code if missing)
        type BagGroup = { id: string; req_vol: number; bags: any[]; is_recode: boolean }
        const grouped: BagGroup[] = []
        const seenIds = new Map<string, BagGroup>()

        for (const bag of bags) {
            const id = bag.prebatch_id || bag.batch_record_id || bag.re_code || '?'
            if (!seenIds.has(id)) {
                const g: BagGroup = {
                    id: id,
                    req_vol: bag.total_request_volume ?? bag.total_volume ?? 0,
                    bags: [],
                    is_recode: !bag.prebatch_id && !bag.batch_record_id
                }
                seenIds.set(id, g)
                grouped.push(g)
            }
            seenIds.get(id)!.bags.push(bag)
        }
        grouped.forEach(g => g.bags.sort((a: any, b: any) => (a.package_no ?? 0) - (b.package_no ?? 0)))

        const HDR_H = 16, PKG_H = 12, START_Y = 80, MAX_Y = 200

        let pages: string[] = []
        let curY = START_Y
        let currentRowsSvg = ''

        const pushPageAndReset = () => {
            pages.push(currentRowsSvg)
            currentRowsSvg = ''
            curY = START_Y
        }

        for (const grp of grouped) {
            // Check if header alone exceeds height
            if (curY + HDR_H > MAX_Y) {
                pushPageAndReset()
            }

            const title = grp.is_recode ? grp.id : grp.id
            currentRowsSvg += `
        <rect x="10" y="${curY}" width="370" height="${HDR_H}" fill="#f0f0f0"/>
        <text x="14" y="${curY + 11}" style="font-size:10px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${title}</text>
      `
            curY += HDR_H

            for (const bag of grp.bags) {
                if (curY + PKG_H > MAX_Y) {
                    pushPageAndReset()
                    // Re-print header on new page for context
                    currentRowsSvg += `
        <rect x="10" y="${curY}" width="370" height="${HDR_H}" fill="#f0f0f0"/>
        <text x="14" y="${curY + 11}" style="font-size:10px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${title} (cont.)</text>
      `
                    curY += HDR_H
                }

                const pkgLabel = `Pack ${bag.package_no ?? 1}/${bag.total_packages ?? 1} Volume`
                currentRowsSvg += `
          <rect x="10" y="${curY}" width="370" height="${PKG_H}" fill="#ffffff"/>
          <text x="24" y="${curY + 9}" style="font-size:9px;font-family:Arial,sans-serif;fill:#000000">${pkgLabel}</text>
          <text x="370" y="${curY + 9}" text-anchor="end" style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${(bag.net_volume ?? 0).toFixed(4)}</text>
        `
                currentRowsSvg += `<line x1="24" y1="${curY + PKG_H}" x2="376" y2="${curY + PKG_H}" stroke="#dddddd" stroke-width="0.5"/>`
                curY += PKG_H
            }
        }

        if (currentRowsSvg !== '') {
            pages.push(currentRowsSvg)
        }

        const totalWt = bags.reduce((s: number, b: any) => s + (b.net_volume || 0), 0)
        const now = new Date()
        const printDate = now.toLocaleDateString('en-GB') + ' ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

        try {
            const resp = await fetch('/labels/packingbox-label_4x3.svg')
            const templateSvg = await resp.text()

            let finalHtmlContent = ''
            const totalPages = pages.length

            for (let i = 0; i < totalPages; i++) {
                const boxNum = i + 1
                const boxIdVal = `${batchId}-${wh}-${boxNum}/${totalPages}`

                let pageSvg = templateSvg
                    .replaceAll('{{Warehouse}}', wh)
                    .replaceAll('{{PrintDate}}', printDate)
                    .replace('{{BoxId}}', boxIdVal)
                    .replace('{{Plant}}', plan?.plant || deps.selectedBatch.value?.plant || 'Line-1')
                    .replace('{{TotalNetWeight}}', totalWt.toFixed(4))
                    .replace('{{PreBatchRows}}', pages[i] || '')

                // QR Code now contains only the Box ID as requested
                const qrData = boxIdVal
                const qrDataUrl = await QRCode.toDataURL(qrData, { width: 72, margin: 1, color: { dark: '#000000', light: '#ffffff' } })
                pageSvg = pageSvg.replace('{{BoxQRCode}}', `<image x="0" y="0" width="72" height="72" href="${qrDataUrl}" />`)

                finalHtmlContent += pageSvg
            }

            open4x3PrintWindow(`Box Packing Label — ${batchId} [${wh}]`, finalHtmlContent)
        } catch (e) {
            console.error('Print error:', e)
            deps.$q.notify({ type: 'negative', message: 'Failed to load label template', position: 'top' })
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 2. TRANSFER REPORT (A4)
    // ═══════════════════════════════════════════════════════════════════
    const printTransferReport = async () => {
        const boxes = deps.transferredBoxes.value.filter((b: any) => deps.selectedForTransfer.value.includes(b.id))
        if (boxes.length === 0) return

        const now = new Date()
        const dateStr = now.toLocaleDateString('th-TH', { year: 'numeric', month: '2-digit', day: '2-digit' })
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        const reportNo = makeReportNo('TR')
        const whs = [...new Set(boxes.map((b: any) => b.wh))].join(' / ')
        const totalBags = boxes.reduce((s: number, b: any) => s + b.bagsCount, 0)

        const ROW_H = 26, START = 158
        let rowsSvg = ''
        boxes.forEach((box: any, i: number) => {
            const y = START + i * ROW_H
            const bg = i % 2 === 0 ? '#f2f2f2' : '#ffffff'
            const plan = deps.plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === box.batch_id))
            const sku = plan?.sku_name || plan?.sku_id || '-'
            rowsSvg += `
        <rect x="20" y="${y}" width="754" height="${ROW_H}" fill="${bg}"/>
        <line x1="20" y1="${y + ROW_H}" x2="774" y2="${y + ROW_H}" stroke="#cccccc" stroke-width="0.4"/>
        <text x="36"  y="${y + 16}" style="font-size:8px;font-family:Arial,sans-serif;fill:#555555">${i + 1}</text>
        <text x="60"  y="${y + 14}" style="font-size:8px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${box.batch_id}</text>
        <text x="60"  y="${y + 24}" style="font-size:7px;font-family:'Courier New',monospace;fill:#888888">${box.id.slice(0, 8)}</text>
        <text x="230" y="${y + 16}" style="font-size:8px;font-family:Arial,sans-serif;fill:#000000">${sku.length > 28 ? sku.slice(0, 28) + '…' : sku}</text>
        <rect x="424" y="${y + 5}" width="28" height="14" rx="3" fill="#333333"/>
        <text x="438" y="${y + 16}" text-anchor="middle" style="font-size:8px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">${box.wh}</text>
        <text x="478" y="${y + 16}" style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${box.bagsCount}</text>
        <text x="520" y="${y + 16}" style="font-size:8px;font-family:Arial,sans-serif;fill:#000000">${box.time}</text>
        <rect x="652" y="${y + 5}" width="56" height="14" rx="3" fill="#222222"/>
        <text x="680" y="${y + 16}" text-anchor="middle" style="font-size:7.5px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">TRANSFERRED</text>
      `;
            [52, 222, 422, 460, 512, 650].forEach(x => {
                rowsSvg += `<line x1="${x}" y1="${y}" x2="${x}" y2="${y + ROW_H}" stroke="#cccccc" stroke-width="0.4"/>`
            })
        })

        try {
            const resp = await fetch('/labels/report-transfer-a4.svg')
            let svgText = await resp.text()
            svgText = svgText
                .replace('{{ReportNo}}', reportNo)
                .replace('{{PrintDate}}', `${dateStr} ${timeStr}`)
                .replace('{{Warehouse}}', whs || 'FH / SPP')
                .replace('{{TransferDate}}', dateStr)
                .replace('{{TotalBoxes}}', String(boxes.length))
                .replace('{{TotalBags}}', String(totalBags))
                .replace('{{TransferRows}}', rowsSvg)
                .replace('{{ReportQR}}', '')
            openA4PrintWindow(`Transfer Report ${reportNo}`, svgText)
        } catch (e) {
            deps.$q.notify({ type: 'negative', message: 'Failed to load report template', position: 'top' })
        }
        deps.showTransferDialog.value = false
        deps.selectedForTransfer.value = []
    }

    // ═══════════════════════════════════════════════════════════════════
    // 3. BOX PACKING LABEL (4×3 inch)
    // ═══════════════════════════════════════════════════════════════════
    const printBoxLabel = async (wh: 'FH' | 'SPP', boxNum?: number, isLastBox?: boolean) => {
        if (!deps.selectedBatch.value || !deps.batchInfo.value) return

        const plan = deps.plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === deps.selectedBatch.value.batch_id))

        // Use batchRecords (prebatch_recs — per-package) as primary data source
        const isFH = (w: string) => w?.toUpperCase().includes('FH') || w?.toUpperCase().includes('FLAVOUR')
        const isSPP = (w: string) => w?.toUpperCase().includes('SPP')
        const whRecs = (deps.batchRecords?.value || []).filter((r: any) => {
            const rWh = r.wh || ''
            return wh === 'FH' ? isFH(rWh) : isSPP(rWh)
        })

        // Use per-package records → bagsByWarehouse → prebatch_items (fallback for SPP without recs)
        const bagsWh = wh === 'FH' ? deps.bagsByWarehouse.value.FH : deps.bagsByWarehouse.value.SPP
        const whFilter = (r: any) => {
            const rWh = r.wh || ''
            return wh === 'FH' ? isFH(rWh) : isSPP(rWh)
        }
        const reqsFallback = ((deps.selectedBatch.value.reqs || []) as any[]).filter(whFilter)
        // Merge: prebatch_recs (per-package) + prebatch_items for re_codes without recs
        const recCodes = new Set(whRecs.map((r: any) => r.re_code))
        const missingReqs = reqsFallback.filter((r: any) => !recCodes.has(r.re_code))
        const allItems = [...whRecs, ...missingReqs]
        // Only show items that are BOXED (packing_status === 1) on the label
        const items = allItems.filter((r: any) => r.packing_status === 1)

        // Build rows: each item = one row showing preBatch ID, re_code, volume
        const ROW_H = 14, START_Y = 0, MAX_Y = 118  // relative to the <g transform="translate(0,80)"> in template

        let pages: string[] = []
        let curY = START_Y
        let currentRowsSvg = ''

        const pushPageAndReset = () => {
            pages.push(currentRowsSvg)
            currentRowsSvg = ''
            curY = START_Y
        }

        for (let idx = 0; idx < items.length; idx++) {
            const item = items[idx]
            if (curY + ROW_H > MAX_Y) {
                pushPageAndReset()
            }

            const batchId = deps.selectedBatch.value.batch_id
            const preBatchId = item.batch_record_id || item.prebatch_id || (batchId ? `${batchId}-${item.re_code}` : item.re_code || '-')
            const reCode = item.re_code || '-'
            const volume = (item.net_volume ?? item.required_volume ?? item.total_packaged ?? 0).toFixed(4)
            const bg = idx % 2 === 0 ? '#f8f8f8' : '#ffffff'

            currentRowsSvg += `
        <rect x="10" y="${curY}" width="364" height="${ROW_H}" fill="${bg}"/>
        <text x="14" y="${curY + 10}" style="font-size:9px;font-family:'Courier New',monospace;font-weight:bold;fill:#000000">${preBatchId}</text>
        <text x="240" y="${curY + 10}" style="font-size:8px;font-family:Arial,sans-serif;fill:#555555">${reCode}</text>
        <text x="370" y="${curY + 10}" text-anchor="end" style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${volume}</text>
        <line x1="10" y1="${curY + ROW_H}" x2="374" y2="${curY + ROW_H}" stroke="#e0e0e0" stroke-width="0.5"/>`
            curY += ROW_H
        }

        if (currentRowsSvg !== '') {
            pages.push(currentRowsSvg)
        }

        // If no items at all, add one empty page
        if (pages.length === 0) {
            pages.push(`<text x="192" y="40" text-anchor="middle" style="font-size:12px;font-family:Arial,sans-serif;fill:#999999">No items in box</text>`)
        }

        const totalWt = items.reduce((s: number, b: any) => s + (b.net_volume || b.required_volume || b.total_packaged || 0), 0)
        const now = new Date()
        const printDate = now.toLocaleDateString('en-GB') + ' ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

        try {
            const resp = await fetch('/labels/packingbox-label_4x3.svg')
            const templateSvg = await resp.text()

            let finalHtmlContent = ''
            const totalPages = pages.length

            for (let i = 0; i < totalPages; i++) {
                const pageNum = i + 1
                let boxIdVal = totalPages > 1
                    ? `${deps.selectedBatch.value.batch_id}-${wh}-${pageNum}/${totalPages}`
                    : `${deps.selectedBatch.value.batch_id}-${wh}`

                // Add box number caption for multibox
                if (boxNum && boxNum > 0) {
                    boxIdVal += ` > Box ${boxNum}`
                    if (isLastBox) boxIdVal += ' Last Box'
                }

                let pageSvg = templateSvg
                    .replaceAll('{{Warehouse}}', wh)
                    .replaceAll('{{PrintDate}}', printDate)
                    .replace('{{BoxId}}', boxIdVal)
                    .replace('{{Plant}}', plan?.plant || deps.selectedBatch.value.plant || 'Line-1')
                    .replace('{{TotalNetWeight}}', totalWt.toFixed(4))
                    .replace('{{PreBatchRows}}', pages[i] || '')

                const qrData = boxIdVal
                const qrDataUrl = await QRCode.toDataURL(qrData, { width: 72, margin: 1, color: { dark: '#000000', light: '#ffffff' } })
                pageSvg = pageSvg.replace('{{BoxQRCode}}', `<image x="0" y="0" width="72" height="72" href="${qrDataUrl}" />`)

                finalHtmlContent += pageSvg
            }

            open4x3PrintWindow(`Box Packing Label — ${deps.selectedBatch.value.batch_id} [${wh}]`, finalHtmlContent)
        } catch (e) {
            console.error('Print error:', e)
            deps.$q.notify({ type: 'negative', message: 'Failed to load label template', position: 'top' })
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 4. PRE-BATCH BAG LABEL (4×3 inch)
    // ═══════════════════════════════════════════════════════════════════
    const printBagLabel = async (bag: any) => {
        if (!deps.selectedBatch.value || !deps.batchInfo.value) return
        const plan = deps.plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === deps.selectedBatch.value.batch_id))
        const data: Record<string, string | number> = {
            'SKU / SKU_Name': deps.batchInfo.value?.sku_name || '-',
            SkuName: plan?.sku_name || deps.batchInfo.value?.sku_name || '',
            PlanId: deps.batchInfo.value?.plan_id || '-',
            BatchId: deps.selectedBatch.value.batch_id || '-',
            'Batch_Number/No of Batch': `Batch ${deps.selectedBatch.value.batch_id?.split('-').pop() || '?'}`,
            IngredientID: bag.re_code || '-',
            Ingredient_ReCode: bag.re_code || '-',
            mat_sap_code: bag.mat_sap_code || '-',
            PlanStartDate: plan?.start_date ? new Date(plan.start_date).toLocaleDateString('en-GB') : '-',
            PlanFinishDate: plan?.finish_date ? new Date(plan.finish_date).toLocaleDateString('en-GB') : '-',
            PrepareDate: new Date().toLocaleDateString('en-GB'),
            PlantId: plan?.plant || deps.selectedBatch.value.plant || '-',
            PlantName: '-',
            Timestamp: new Date().toLocaleString('en-GB'),
            PackageSize: (bag.net_volume || 0).toFixed(4),
            BatchRequireSize: (bag.total_volume || bag.total_request_volume || 0).toFixed(4),
            PackageNo: `${bag.package_no || 1}/${bag.total_packages || 1}`,
            QRCode: `${deps.batchInfo.value?.plan_id || ''},${bag.batch_record_id},${bag.re_code},${bag.net_volume}`,
            Lot1: bag.origins?.[0] ? `${bag.origins[0].intake_lot_id} / ${(bag.origins[0].take_volume || 0).toFixed(4)} kg` : (bag.intake_lot_id ? `${bag.intake_lot_id} / ${Number(bag.net_volume).toFixed(4)} kg` : '-'),
            Lot2: bag.origins?.[1] ? `${bag.origins[1].intake_lot_id} / ${(bag.origins[1].take_volume || 0).toFixed(4)} kg` : '',
        }
        const svg = await generateLabelSvg('prebatch-label_4x3', data)
        if (svg) printLabel(svg)
    }

    return {
        printPackingBoxReport,
        printTransferReport,
        printBoxLabel,
        printBagLabel,
    }
}

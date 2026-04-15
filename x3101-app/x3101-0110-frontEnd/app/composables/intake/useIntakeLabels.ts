/**
 * Composable: Ingredient label printing (multi-package + single package)
 */
import { useAuth } from '~/composables/useAuth'
import { useQrCode } from '~/composables/useQrCode'
import { formatDate, type IngredientIntake } from '~/composables/intake/useIntakeHelpers'

const LABEL_CSS = `
  * { margin:0; padding:0; outline:0; border:0; box-sizing:border-box; }
  @page { size: 4in 3in; margin: 0 !important; }
  html, body { width: 4in; height: 3in; margin: 0; padding: 0; background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .label-wrapper { width: 4in; height: 3in; display: block; overflow: hidden; position: relative; page-break-after: always; margin: 0; padding: 0; box-sizing: border-box; }
  .label-wrapper:last-child { page-break-after: avoid; }
  .label-wrapper svg { width: 100%; height: 100%; display: block; object-fit: contain; }
  header, footer { display: none !important; }
`.trim()

function buildQrString(record: IngredientIntake, weight: number) {
    return `${record.intake_lot_id}|${record.mat_sap_code || ''}| |${formatDate(record.intake_at)}|${weight.toFixed(3)}|${record.uom || 'KG'}|${record.material_type || ''}|${formatDate(record.manufacturing_date)}|${formatDate(record.expire_date)}`
}

async function fillTemplate(templateStr: string, record: IngredientIntake, pkgNo: number, numPkgs: number, pkgWeight: number, qrDataUrl: string) {
    let svg = templateStr
        .replace(/\{\{IntakeLotId\}\}/g, record.intake_lot_id || '-')
        .replace(/\{\{ReCode\}\}/g, record.re_code || '-')
        .replace(/\{\{MatSapCode\}\}/g, record.mat_sap_code || '-')
        .replace(/\{\{Package\/Packages\}\}/g, `${pkgNo} / ${numPkgs}`)
        .replace(/\{\{MfgDate\}\}/g, formatDate(record.manufacturing_date))
        .replace(/\{\{ExpDate\}\}/g, formatDate(record.expire_date))
        .replace(/\{\{ExtDate\}\}/g, formatDate(record.ext_date))
        .replace(/\{\{PackageVol\}\}/g, pkgWeight.toFixed(4))
        .replace(/\{\{UOM\}\}/g, record.uom || 'kg')
        .replace(/\{\{LodNo\}\}/g, formatDate(record.manufacturing_date) || '-')
        .replace(/\{\{MaterialType\}\}/g, record.material_type || '-')
        .replace(/\{\{ReservNo\}\}/g, record.reserv_no || '-')
        .replace(/\{\{ReceiveDate\}\}/g, formatDate(record.intake_at))
        .replace(/\{\{StockZone\}\}/g, record.stock_zone || '-')
        .replace(/\{\{QRCode\}\}/g, `<image href="${qrDataUrl}" x="16.3" y="39.3" width="80" height="80" />`)

    // Make SVG responsive
    svg = svg.replace(/(<svg[\s\S]*?)width="[^"]*"/, '$1width="100%"')
        .replace(/(<svg[\s\S]*?)height="[^"]*"/, '$1height="100%"')
    if (!svg.includes('preserveAspectRatio')) {
        svg = svg.replace('<svg', '<svg preserveAspectRatio="xMidYMid meet"')
    }
    return svg
}

function printViaIframe(html: string, iframeId = 'print-iframe') {
    const existing = document.getElementById(iframeId)
    if (existing) document.body.removeChild(existing)

    const iframe = document.createElement('iframe')
    iframe.id = iframeId
    iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0.01'
    document.body.appendChild(iframe)

    iframe.onload = () => {
        setTimeout(() => {
            iframe.contentWindow?.focus()
            iframe.contentWindow?.print()
        }, 500)
    }

    const doc = iframe.contentWindow?.document
    if (doc) { doc.open(); doc.write(html); doc.close() }
}

export function useIntakeLabels() {
    const { user } = useAuth()
    const { generateQrDataUrl } = useQrCode()

    /** Print labels for all packages in a record */
    const printLabel = async (record: IngredientIntake) => {
        const templateStr = await (await fetch('/labels/ingredient_intake-label_4x3-r01.svg')).text()
        const numPkgs = record.package_intake || 1
        let labelsHtml = ''

        for (let i = 1; i <= numPkgs; i++) {
            let weight = record.intake_package_vol || 0
            if (record.packages?.length) {
                const pkgRec = record.packages.find(p => p.package_no === i)
                if (pkgRec) weight = pkgRec.weight
            } else if (i === numPkgs && record.intake_package_vol) {
                weight = record.intake_vol - (record.intake_package_vol * (numPkgs - 1))
            }

            const qr = await generateQrDataUrl(buildQrString(record, weight), 150)
            const svg = await fillTemplate(templateStr, record, i, numPkgs, weight, qr)
            labelsHtml += `<div class="label-wrapper">${svg}</div>`
        }

        const html = `<html><head><style>${LABEL_CSS}</style></head><body>${labelsHtml}</body></html>`.replace(/>\s+</g, '><').trim()
        printViaIframe(html)
    }

    /** Print a single package label from expanded list */
    const printSinglePackageLabel = async (record: IngredientIntake, pkg: { package_no: number; weight: number }) => {
        const templateStr = await (await fetch('/labels/ingredient_intake-label_4x3-r01.svg')).text()
        const numPkgs = record.package_intake || 1
        const qr = await generateQrDataUrl(buildQrString(record, pkg.weight), 150)
        const svg = await fillTemplate(templateStr, record, pkg.package_no, numPkgs, pkg.weight, qr)
        const labelsHtml = `<div class="label-wrapper">${svg}</div>`
        const html = `<html><head><style>${LABEL_CSS}</style></head><body>${labelsHtml}</body></html>`.replace(/>\s+</g, '><').trim()

        // Use a separate iframe that auto-cleans
        const iframe = document.createElement('iframe')
        iframe.style.display = 'none'
        document.body.appendChild(iframe)
        iframe.onload = () => {
            setTimeout(() => {
                iframe.contentWindow?.focus()
                iframe.contentWindow?.print()
                setTimeout(() => document.body.removeChild(iframe), 1000)
            }, 500)
        }
        const doc = iframe.contentWindow?.document
        if (doc) { doc.open(); doc.write(html); doc.close() }
    }

    /** Test print (1 page) */
    const testPrint1Page = () => {
        printLabel({
            intake_lot_id: 'TEST-1PG', mat_sap_code: 'MAT-1', re_code: 'RE-1',
            intake_at: new Date().toISOString(), expire_date: new Date().toISOString(),
            manufacturing_date: new Date().toISOString(), intake_vol: 10, package_intake: 1,
            intake_package_vol: 10, intake_by: 'tester',
        } as any)
    }

    /** Test print (2 pages) */
    const testPrint2Pages = () => {
        printLabel({
            intake_lot_id: 'FIX-TEST-001', mat_sap_code: 'MAT12345', re_code: 'RE-TEST',
            intake_at: new Date().toISOString(), expire_date: new Date().toISOString(),
            manufacturing_date: new Date().toISOString(), intake_vol: 50, package_intake: 2,
            intake_package_vol: 25, intake_by: user.value?.username || 'tester',
        } as any)
    }

    return { printLabel, printSinglePackageLabel, testPrint1Page, testPrint2Pages }
}

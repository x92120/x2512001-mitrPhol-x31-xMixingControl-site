/**
 * Module Test: Scanner Parser & Workflow Routing
 * for x60-CheckForProduction.vue
 * 
 * Run: npx vitest run --project unit tests/scannerParser.test.ts
 */

import { describe, it, expect } from 'vitest'

// ═══════════════════════════════════════════════════════════════════
// PURE FUNCTIONS (extracted from x60-CheckForProduction.vue)
// ═══════════════════════════════════════════════════════════════════

/**
 * Parse the non-standard scanner string into key:value pairs.
 * Format: {"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}
 */
function parseScannerString(raw: string): Record<string, any> {
    const result: Record<string, any> = {}
    if (!raw.startsWith('{')) return result

    let inner = raw.substring(1)
    if (inner.endsWith('}')) inner = inner.substring(0, inner.length - 1)

    const regex = /"?(\w+):([^,"}]*)"?/g
    let m
    while ((m = regex.exec(inner)) !== null) {
        const key = m[1]!
        let val: any = m[2]!.replace(/"/g, '')
        const num = Number(val)
        result[key] = isNaN(num) || val === '' ? val : num
    }
    return result
}

/**
 * Extract Batch ID (first 14 chars) from a batch_record_id.
 */
function extractBatchId(batchRecordId: string): string {
    if (batchRecordId.toUpperCase().startsWith('P') && batchRecordId.length >= 14) {
        return batchRecordId.substring(0, 14)
    }
    const parts = batchRecordId.split('-')
    return parts.length >= 3 ? parts.slice(0, 3).join('-') : batchRecordId
}

/**
 * Extract RE Code from batch_record_id (after 14-char Batch ID, minus bag number).
 */
function extractReCode(batchRecordId: string): string {
    if (batchRecordId.length <= 14) return ''
    const remainder = batchRecordId.substring(14)
    return remainder.replace(/-\d+$/, '')
}

/**
 * Full scan handler: parse raw string → extract all fields
 */
function handleScan(raw: string): {
    batchId: string
    batchRecordId: string
    reCode: string
    materialId: string | number
    netWeight: number
    isJson: boolean
    scanFields: Record<string, any>
} {
    const trimmed = raw.trim()

    if (trimmed.startsWith('{')) {
        const fields = parseScannerString(trimmed)
        if (fields.b) {
            const batchRecordId = String(fields.b)
            return {
                batchId: extractBatchId(batchRecordId),
                batchRecordId,
                reCode: extractReCode(batchRecordId),
                materialId: fields.m || '',
                netWeight: fields.n || 0,
                isJson: true,
                scanFields: fields,
            }
        }
    }

    // Legacy: plain text or comma-separated
    return {
        batchId: trimmed.length >= 14 ? trimmed.substring(0, 14) : trimmed,
        batchRecordId: trimmed,
        reCode: '',
        materialId: '',
        netWeight: 0,
        isJson: false,
        scanFields: {},
    }
}

/**
 * Workflow routing: decides whether to LOAD BATCH or VERIFY BAG
 */
type WorkflowAction = 
    | { action: 'LOAD_BATCH'; batchId: string; alsoVerify?: string }
    | { action: 'VERIFY_BAG'; reCode: string; fullRecordId: string }

function routeScan(raw: string, batchAlreadyLoaded: boolean): WorkflowAction {
    const scan = handleScan(raw)

    if (!batchAlreadyLoaded) {
        // Step 1: load batch
        return {
            action: 'LOAD_BATCH',
            batchId: scan.batchId,
        }
    } else {
        // Step 2+: verify bag (green spot)
        return {
            action: 'VERIFY_BAG',
            reCode: scan.reCode,
            fullRecordId: scan.batchRecordId,
        }
    }
}

/**
 * canStartProduction: ALL warehouses must have ALL ingredients verified
 */
function canStartProduction(groups: { warehouse: string; ingredients: { recheck_status: number }[] }[]): boolean {
    if (groups.length === 0) return false
    for (const group of groups) {
        if (!group.ingredients.every(ing => ing.recheck_status === 1)) {
            return false
        }
    }
    return true
}

/**
 * matchIngredient: find matching ingredient by RE Code in warehouse groups
 */
function matchIngredient(
    reCode: string,
    fullRecordId: string,
    groups: { warehouse: string; ingredients: { re_code: string; recheck_status: number }[] }[]
): { found: boolean; alreadyVerified: boolean; warehouse: string; reCode: string } {
    for (const group of groups) {
        const ing = group.ingredients.find(
            i => i.re_code === reCode || i.re_code === fullRecordId
        )
        if (ing) {
            return {
                found: true,
                alreadyVerified: ing.recheck_status === 1,
                warehouse: group.warehouse,
                reCode: ing.re_code,
            }
        }
    }
    return { found: false, alreadyVerified: false, warehouse: '', reCode: '' }
}


// ═══════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════

describe('parseScannerString', () => {
    it('parses the real scanner JSON format', () => {
        const raw = '{"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}'
        const result = parseScannerString(raw)
        expect(result.b).toBe('P260411-021-05FV045A-1')
        expect(result.m).toBe(126450241100026)
        expect(result.p).toBe('1/')
        expect(result.n).toBe(0.132)
        expect(result.t).toBe(0.132)
    })

    it('returns empty for non-JSON input', () => {
        expect(parseScannerString('P260411-021-05')).toEqual({})
    })

    it('returns empty for empty braces', () => {
        expect(parseScannerString('{}')).toEqual({})
    })

    it('handles different batch IDs and weights', () => {
        const raw = '{"b:P260301-010-03FV001B-3","m:987654321","n:1.500}'
        const result = parseScannerString(raw)
        expect(result.b).toBe('P260301-010-03FV001B-3')
        expect(result.n).toBe(1.5)
    })
})

describe('extractBatchId', () => {
    it('extracts 14-char batch ID from concatenated string', () => {
        expect(extractBatchId('P260411-021-05FV045A-1')).toBe('P260411-021-05')
    })

    it('extracts batch ID when exactly 14 chars', () => {
        expect(extractBatchId('P260411-021-05')).toBe('P260411-021-05')
    })

    it('handles short IDs by splitting on dashes', () => {
        expect(extractBatchId('P260411-021')).toBe('P260411-021')
    })

    it('handles different plant IDs', () => {
        expect(extractBatchId('P260301-010-03FV001B-3')).toBe('P260301-010-03')
    })
})

describe('extractReCode', () => {
    it('extracts FV045A from P260411-021-05FV045A-1', () => {
        expect(extractReCode('P260411-021-05FV045A-1')).toBe('FV045A')
    })

    it('returns empty for exactly 14-char batch ID', () => {
        expect(extractReCode('P260411-021-05')).toBe('')
    })

    it('handles multi-digit bag numbers', () => {
        expect(extractReCode('P260411-021-05FV045A-12')).toBe('FV045A')
    })

    it('handles RE codes without bag number', () => {
        expect(extractReCode('P260411-021-05RMSUG01')).toBe('RMSUG01')
    })
})

describe('handleScan (full pipeline)', () => {
    it('parses real scanner string end-to-end', () => {
        const raw = '{"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}'
        const result = handleScan(raw)
        expect(result.batchId).toBe('P260411-021-05')
        expect(result.batchRecordId).toBe('P260411-021-05FV045A-1')
        expect(result.reCode).toBe('FV045A')
        expect(result.materialId).toBe(126450241100026)
        expect(result.isJson).toBe(true)
    })

    it('handles plain batch ID input', () => {
        const result = handleScan('P260411-021-05')
        expect(result.batchId).toBe('P260411-021-05')
        expect(result.isJson).toBe(false)
        expect(result.reCode).toBe('')
    })

    it('handles packing box QR format', () => {
        const result = handleScan('P260411,P260411-021-05,BOX,12,25.5')
        expect(result.isJson).toBe(false)
    })
})

// ═══════════════════════════════════════════════════════════════════
// WORKFLOW ROUTING TESTS
// ═══════════════════════════════════════════════════════════════════

describe('routeScan (Workflow Routing)', () => {
    describe('Step 1: Load Batch (no batch loaded)', () => {
        it('routes PACKING BOX scan to LOAD_BATCH', () => {
            const result = routeScan('P260411,P260411-021-05,BOX,12,25.5', false)
            expect(result.action).toBe('LOAD_BATCH')
        })

        it('routes PREBATCH BAG JSON to LOAD_BATCH when no batch loaded', () => {
            const raw = '{"b:P260411-021-05FV045A-1","m:126450241100026","n:0.132}'
            const result = routeScan(raw, false)
            expect(result.action).toBe('LOAD_BATCH')
            if (result.action === 'LOAD_BATCH') {
                expect(result.batchId).toBe('P260411-021-05')
            }
        })

        it('routes PLAIN BATCH ID to LOAD_BATCH', () => {
            const result = routeScan('P260411-021-05', false)
            expect(result.action).toBe('LOAD_BATCH')
            if (result.action === 'LOAD_BATCH') {
                expect(result.batchId).toBe('P260411-021-05')
            }
        })
    })

    describe('Step 2+: Verify Bag (batch already loaded)', () => {
        it('routes PREBATCH BAG JSON to VERIFY_BAG', () => {
            const raw = '{"b:P260411-021-05FV045A-1","m:126450241100026","n:0.132}'
            const result = routeScan(raw, true)
            expect(result.action).toBe('VERIFY_BAG')
            if (result.action === 'VERIFY_BAG') {
                expect(result.reCode).toBe('FV045A')
                expect(result.fullRecordId).toBe('P260411-021-05FV045A-1')
            }
        })

        it('extracts correct RE Code for different ingredients', () => {
            const raw1 = '{"b:P260411-021-05RMSUG01-2","n:25.0}'
            const result1 = routeScan(raw1, true)
            if (result1.action === 'VERIFY_BAG') {
                expect(result1.reCode).toBe('RMSUG01')
            }

            const raw2 = '{"b:P260411-021-05ABC123-1","n:1.0}'
            const result2 = routeScan(raw2, true)
            if (result2.action === 'VERIFY_BAG') {
                expect(result2.reCode).toBe('ABC123')
            }
        })

        it('handles plain text scan as VERIFY_BAG when batch loaded', () => {
            const result = routeScan('P260411-021-05FV045A-1', true)
            expect(result.action).toBe('VERIFY_BAG')
        })
    })
})

// ═══════════════════════════════════════════════════════════════════
// INGREDIENT MATCHING TESTS
// ═══════════════════════════════════════════════════════════════════

describe('matchIngredient', () => {
    const mockGroups = [
        {
            warehouse: 'MIX',
            ingredients: [
                { re_code: 'WATER01', recheck_status: 1 },
                { re_code: 'SUGAR01', recheck_status: 0 },
            ]
        },
        {
            warehouse: 'FH',
            ingredients: [
                { re_code: 'FV045A', recheck_status: 0 },
                { re_code: 'FV180B', recheck_status: 1 },
            ]
        },
        {
            warehouse: 'SPP',
            ingredients: [
                { re_code: 'RMSUG01', recheck_status: 0 },
            ]
        }
    ]

    it('finds FV045A in FH warehouse', () => {
        const result = matchIngredient('FV045A', 'P260411-021-05FV045A-1', mockGroups)
        expect(result.found).toBe(true)
        expect(result.warehouse).toBe('FH')
        expect(result.reCode).toBe('FV045A')
        expect(result.alreadyVerified).toBe(false)
    })

    it('detects already-verified ingredient', () => {
        const result = matchIngredient('FV180B', 'P260411-021-05FV180B-1', mockGroups)
        expect(result.found).toBe(true)
        expect(result.alreadyVerified).toBe(true)
    })

    it('finds RMSUG01 in SPP warehouse', () => {
        const result = matchIngredient('RMSUG01', '', mockGroups)
        expect(result.found).toBe(true)
        expect(result.warehouse).toBe('SPP')
    })

    it('returns not found for unknown RE Code', () => {
        const result = matchIngredient('UNKNOWN', 'UNKNOWN-1', mockGroups)
        expect(result.found).toBe(false)
    })

    it('matches by fullRecordId as fallback', () => {
        // If re_code stored IS the full record ID
        const groups2 = [{
            warehouse: 'FH',
            ingredients: [{ re_code: 'P260411-021-05FV045A-1', recheck_status: 0 }]
        }]
        const result = matchIngredient('FV045A', 'P260411-021-05FV045A-1', groups2)
        expect(result.found).toBe(true)
    })
})

// ═══════════════════════════════════════════════════════════════════
// PRODUCTION READINESS TESTS
// ═══════════════════════════════════════════════════════════════════

describe('canStartProduction', () => {
    it('returns false when no groups exist', () => {
        expect(canStartProduction([])).toBe(false)
    })

    it('returns false when FH has unchecked items', () => {
        expect(canStartProduction([
            { warehouse: 'MIX', ingredients: [{ recheck_status: 1 }] },
            { warehouse: 'FH', ingredients: [{ recheck_status: 1 }, { recheck_status: 0 }] },
            { warehouse: 'SPP', ingredients: [{ recheck_status: 1 }] },
        ])).toBe(false)
    })

    it('returns true when ALL warehouses fully verified', () => {
        expect(canStartProduction([
            { warehouse: 'MIX', ingredients: [{ recheck_status: 1 }, { recheck_status: 1 }] },
            { warehouse: 'FH', ingredients: [{ recheck_status: 1 }] },
            { warehouse: 'SPP', ingredients: [{ recheck_status: 1 }, { recheck_status: 1 }] },
        ])).toBe(true)
    })

    it('returns false when MIX has unchecked (all warehouses enforced)', () => {
        expect(canStartProduction([
            { warehouse: 'MIX', ingredients: [{ recheck_status: 0 }] },
            { warehouse: 'FH', ingredients: [{ recheck_status: 1 }] },
        ])).toBe(false)
    })
})

// ═══════════════════════════════════════════════════════════════════
// FULL WORKFLOW SIMULATION
// ═══════════════════════════════════════════════════════════════════

describe('Full Workflow Simulation', () => {
    const mockIngredients = [
        { warehouse: 'FH', ingredients: [
            { re_code: 'FV045A', recheck_status: 0 },
            { re_code: 'FV180B', recheck_status: 0 },
        ]},
        { warehouse: 'SPP', ingredients: [
            { re_code: 'RMSUG01', recheck_status: 0 },
        ]},
    ]

    it('simulates complete scan-to-production workflow', () => {
        // STEP 1: First scan → Load Batch
        const scan1 = '{"b:P260411-021-05FV045A-1","m:126450241100026","n:0.132}'
        const route1 = routeScan(scan1, false)
        expect(route1.action).toBe('LOAD_BATCH')
        expect(canStartProduction(mockIngredients)).toBe(false)

        // STEP 2: Scan FV045A bag → Mark Green
        const scan2 = '{"b:P260411-021-05FV045A-1","m:126450241100026","n:0.132}'
        const route2 = routeScan(scan2, true)  // batch now loaded
        expect(route2.action).toBe('VERIFY_BAG')
        if (route2.action === 'VERIFY_BAG') {
            const match2 = matchIngredient(route2.reCode, route2.fullRecordId, mockIngredients)
            expect(match2.found).toBe(true)
            expect(match2.reCode).toBe('FV045A')
            // Simulate marking green
            mockIngredients[0].ingredients[0].recheck_status = 1
        }
        expect(canStartProduction(mockIngredients)).toBe(false)

        // STEP 3: Scan FV180B bag → Mark Green
        const scan3 = '{"b:P260411-021-05FV180B-2","n:0.5}'
        const route3 = routeScan(scan3, true)
        if (route3.action === 'VERIFY_BAG') {
            const match3 = matchIngredient(route3.reCode, route3.fullRecordId, mockIngredients)
            expect(match3.found).toBe(true)
            mockIngredients[0].ingredients[1].recheck_status = 1
        }
        expect(canStartProduction(mockIngredients)).toBe(false)

        // STEP 4: Scan RMSUG01 bag → Mark Green → ALL DONE
        const scan4 = '{"b:P260411-021-05RMSUG01-1","n:25.0}'
        const route4 = routeScan(scan4, true)
        if (route4.action === 'VERIFY_BAG') {
            const match4 = matchIngredient(route4.reCode, route4.fullRecordId, mockIngredients)
            expect(match4.found).toBe(true)
            expect(match4.warehouse).toBe('SPP')
            mockIngredients[1].ingredients[0].recheck_status = 1
        }

        // ALL VERIFIED → Production Ready!
        expect(canStartProduction(mockIngredients)).toBe(true)
    })

    it('detects duplicate scans correctly', () => {
        const verifiedGroups = [
            { warehouse: 'FH', ingredients: [
                { re_code: 'FV045A', recheck_status: 1 },
            ]},
        ]
        
        const scan = '{"b:P260411-021-05FV045A-1","n:0.132}'
        const route = routeScan(scan, true)
        if (route.action === 'VERIFY_BAG') {
            const match = matchIngredient(route.reCode, route.fullRecordId, verifiedGroups)
            expect(match.found).toBe(true)
            expect(match.alreadyVerified).toBe(true)  // Duplicate!
        }
    })

    it('detects wrong batch ingredient', () => {
        const groups = [
            { warehouse: 'FH', ingredients: [
                { re_code: 'FV045A', recheck_status: 0 },
            ]},
        ]
        
        // Scan a bag with different RE Code that doesn't exist
        const scan = '{"b:P260411-021-05XXXXXX-1","n:0.132}'
        const route = routeScan(scan, true)
        if (route.action === 'VERIFY_BAG') {
            const match = matchIngredient(route.reCode, route.fullRecordId, groups)
            expect(match.found).toBe(false)  // Not in this batch!
        }
    })
})

async function test() {
    const plansRes = await fetch("http://127.0.0.1:8001/production-plans/?status=active").then(r => r.json());
    const allPlans = plansRes.plans || plansRes || [];
    
    const itemsRes = await fetch("http://127.0.0.1:8001/prebatch-items/by-batch/P260321-02-02-002").then(r => r.json());
    const batchPreBatchItems = itemsRes || [];
    
    const recsRes = await fetch("http://127.0.0.1:8001/prebatch-recs/by-batch/P260321-02-02-002").then(r => r.json());
    const batchPackedRecs = recsRes || [];
    
    // Grouping
    const groups = {};
    for (const item of batchPreBatchItems) {
        let wh = (item.wh || 'MIX').toUpperCase();
        if (wh === 'FLAVOUR HOUSE') wh = 'FH';
        if (wh === 'SPECIALITY PREMIX') wh = 'SPP';
        if (!groups[wh]) groups[wh] = [];
        groups[wh].push(item);
    }
    
    const whOrder = ['MIX', 'FH', 'SPP'];
    const prebatchByWarehouse = Object.keys(groups).sort((a, b) => {
        let ia = whOrder.indexOf(a);
        let ib = whOrder.indexOf(b);
        if (ia === -1) ia = 99;
        if (ib === -1) ib = 99;
        if (ia !== ib) return ia - ib;
        return a.localeCompare(b);
    }).map(wh => {
        const sortedItems = groups[wh].sort((a, b) => (a.re_code || '').localeCompare(b.re_code || ''));
        const reCodeGroups = {};
        for (const item of sortedItems) {
            const re = item.re_code || 'Unknown';
            if (!reCodeGroups[re]) reCodeGroups[re] = [];
            reCodeGroups[re].push(item);
        }
        
        const summaryItems = Object.keys(reCodeGroups).map(re => {
            const reqItems = reCodeGroups[re];
            let displayItems = reqItems;
            if (wh !== 'MIX') {
                const packed = batchPackedRecs.filter(r => (r.re_code || '') === re);
                if (packed.length > 0) {
                    packed.sort((a, b) => (a.package_no || 0) - (b.package_no || 0));
                    displayItems = packed.map(p => ({
                        ...p,
                        status: p.packing_status === 1 ? 2 : 0, 
                        required_volume: p.net_volume || 0
                    }));
                }
            }

            const allChecked = displayItems.length > 0 && displayItems.every(i => i.recheck_status === 1);
            const anyFailed = displayItems.some(i => i.recheck_status === 2);
            const recheck_status = anyFailed ? 2 : (allChecked ? 1 : 0);
            
            return {
                re_code: re,
                recheck_status: recheck_status,
                items: displayItems
            }
        });

        return {
            warehouse: wh,
            ingredients: summaryItems
        }
    });
    
    const prePackGroups = prebatchByWarehouse.filter(
        g => g.warehouse === 'FH' || g.warehouse === 'SPP'
    );
    console.log("prePackGroups count:", prePackGroups.length);
    
    let canStart = true;
    for (const group of prePackGroups) {
        if (!group.ingredients.every(ing => ing.recheck_status === 1)) {
            console.log("Failed group:", group.warehouse);
            const failedIngs = group.ingredients.filter(ing => ing.recheck_status !== 1);
            console.log("Failed ings:", failedIngs.map(i => ({re_code: i.re_code, recheck_status: i.recheck_status})));
            canStart = false;
        }
    }
    console.log("canStartProduction:", canStart);
}

test().catch(console.error);

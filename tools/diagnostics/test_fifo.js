fetch("http://127.0.0.1:8001/production-plans/?status=active").then(r => r.json()).then(res => {
    const allPlans = res.plans || res || [];
    const fifoActiveBatchByPlan = {};
    for (const plan of allPlans) {
        const sorted = [...(plan.batches || [])].sort((a, b) =>
            (a.batch_id || '').localeCompare(b.batch_id || '')
        );
        const active = sorted.find(b =>
            !['Done', 'Cancelled'].includes(b.status || '')
        );
        if (active) fifoActiveBatchByPlan[plan.plan_id] = active.batch_id;
    }
    console.log("FIFO:", fifoActiveBatchByPlan);
});

import mqtt from 'mqtt'

console.log('🔌 Starting PLC Simulator for Plant 01...')

// Connect to local RabbitMQ MQTT (using ws because frontend uses WS)
const client = mqtt.connect('ws://localhost:15675/ws', { 
    username: 'xMixingNode-1',
    password: 'x123456'
})

let stepNo = 1
let stepTimer = 0
let watchdog = 0
let running = false
let paused = false

// Recipe storage (Step-by-Step approach)
let currentStep = null
let batchId = null
let stepDuration = 5 // simulated 5 seconds per step

client.on('connect', () => {
    console.log('✅ Connected to MQTT Broker! Pumping telemetry to mixing/plant/1')
    
    // Subscribe to commands
    client.subscribe('mixing/plant/1/cmd')
    client.subscribe('mixing/plant/1/step_cmd') // Receive step-by-step command

    setInterval(() => {
        watchdog = (watchdog + 1) % 100
        if (running && !paused) {
            stepTimer += 1

            // Auto-advance step when step_time is reached
            if (currentStep) {
                const targetTime = currentStep.step_time > 0 ? currentStep.step_time : stepDuration
                if (stepTimer >= targetTime) {
                    running = false // Stop running, wait for next step
                    console.log(`🎉 Step ${stepNo} COMPLETE! Waiting for next step from HMI...`)
                    client.publish('mixing/plant/1/status', JSON.stringify({
                        status: 'STEP_COMPLETE',
                        step_no: stepNo,
                        batch_id: batchId,
                        timestamp: new Date().toISOString()
                    }))
                }
            }
        }

        const rs = currentStep || {}

        const telemetry = {
            "Plant": 1,
            "Watch-Dog": watchdog,
            "Step_No": stepNo,
            "Step_Timer": stepTimer,
            "Status": running ? (paused ? 'PAUSED' : 'RUNNING') : (currentStep ? 'WAIT_NEXT_STEP' : 'IDLE'),
            "Batch_ID": batchId || '-',
            "Current_Phase": rs.phase || '-',
            "Current_Phase_ID": rs.phase_id || '-',
            "Current_Action": rs.action_description || '-',
            "Current_Ingredient": rs.re_code || '-',
            "Target_Weight": rs.require || 0,
            "HopperScale": parseFloat((Math.random() * 5 + (rs.require || 50)).toFixed(2)),
            "MixingTank": {
                "Scale": parseFloat((Math.random() * 10 + 500).toFixed(2)),
                "Temperature": parseFloat((Math.random() * 2 + (rs.temperature || 65)).toFixed(2)),
                "Agitator Speed": parseFloat((Math.random() * 5 + (rs.agitator_rpm || 40)).toFixed(2))
            },
            "HighShare": {
                "Speed": parseFloat((Math.random() * 50 + (rs.high_shear_rpm || 1400)).toFixed(2)),
                "Temperature": parseFloat((Math.random() * 2 + 70).toFixed(2))
            },
            "Circulation": {
                "Pump Speed": parseFloat((Math.random() * 5 + 30).toFixed(2)),
                "FlowRate": parseFloat((Math.random() * 20 + 200).toFixed(2)),
                "TemPerature": parseFloat((Math.random() * 2 + 60).toFixed(2))
            },
            "PH": parseFloat((Math.random() * 0.5 + 6.8).toFixed(2)),
            "Brix": parseFloat((Math.random() * 1 + 14).toFixed(2))
        }

        client.publish('mixing/plant/1/telemetry', JSON.stringify(telemetry))
        
    }, 1000) 
})

client.on('message', (topic, message) => {
    const payload = JSON.parse(message.toString())

    // ── Single Step Download (Step-by-Step Approach) ──
    if (topic.includes('/step_cmd')) {
        currentStep = payload
        batchId = payload.batch_id
        stepNo = payload.step_no
        stepTimer = 0
        running = true
        paused = false

        console.log(`\n📥 STEP SECURED! Executing Step ${stepNo}: [${payload.phase}/${payload.phase_id}] ${payload.re_code}`)
        console.log(`   Target Weight: ${payload.require} ${payload.uom} | Target Temp: ${payload.temperature}°C`)
        
        // Send ACK back
        client.publish('mixing/plant/1/ack', JSON.stringify({
            type: 'STEP_RECEIVED',
            step_no: stepNo,
            batch_id: batchId,
            timestamp: new Date().toISOString()
        }))
        return
    }

    // ── Commands ──
    if (topic.includes('/cmd')) {
        const cmd = payload.command
        console.log(`\n🔔 COMMAND: [${cmd}]`)

        if (cmd === 'PAUSE') {
            paused = !paused
            console.log(paused ? '⏸️ PLC PAUSED!' : '▶️ PLC RESUMED!')
        } else if (cmd === 'ABORT') {
            running = false
            paused = false
            currentStep = null
            console.log('🛑 PLC EMERGENCY STOP! (ABORT)')
        }
    }
})

client.on('error', (err) => console.error('Connection Error:', err))

import mqtt from 'mqtt'

console.log('🔌 Starting PLC Simulator for Plant 01...')

// Connect to local RabbitMQ MQTT (change to 192.168.121.11 / 31 if testing across network)
const client = mqtt.connect('ws://localhost:15675/ws', { // or mqtt://localhost:1883 if ws fails
    username: 'xMixingNode-1',
    password: 'x123456'
})

let stepNo = 1
let stepTimer = 0
let watchdog = 0

client.on('connect', () => {
    console.log('✅ Connected to MQTT Broker! Pumping telemetry to mixing/plant/1')
    
    // Subscribe to commands coming from the Web UI!
    client.subscribe('mixing/plant/1/cmd')

    setInterval(() => {
        watchdog = (watchdog + 1) % 100
        stepTimer += 1

        const dummyPayload = {
            "Plant": 1,
            "Watch-Dog": watchdog,
            "Step_No": stepNo,
            "Step_Timer": stepTimer,
            "HopperScale": parseFloat((Math.random() * 5 + 50).toFixed(2)),
            "MixingTank": {
                "Scale": parseFloat((Math.random() * 10 + 500).toFixed(2)),
                "Temperature": parseFloat((Math.random() * 2 + 65).toFixed(2)),
                "Agitator Speed": parseFloat((Math.random() * 5 + 40).toFixed(2))
            },
            "HighShare": {
                "Speed": parseFloat((Math.random() * 50 + 1400).toFixed(2)),
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

        // Send dummy data to TOPIC
        client.publish('mixing/plant/1/telemetry', JSON.stringify(dummyPayload))
        
    }, 1000) // Pump every 1 second
})

client.on('message', (topic, message) => {
    console.log(`\n🔔 COMMAND RECEIVED FROM WEB UI [${topic}]:`, JSON.parse(message.toString()))
    const cmd = JSON.parse(message.toString()).command
    if (cmd === 'NEXT_STEP') {
        stepNo += 1
        stepTimer = 0
        console.log(`➡️ PLC moving to Step ${stepNo} !`)
    } else if (cmd === 'ABORT') {
        console.log('🛑 PLC EMERGENCY STOPPING!')
    }
})

client.on('error', (err) => console.error('Connection Error:', err))

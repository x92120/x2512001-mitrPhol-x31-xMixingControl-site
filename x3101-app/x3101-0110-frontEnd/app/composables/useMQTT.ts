import { ref } from 'vue'
import mqtt from 'mqtt'

export interface PlantData {
    Step_no: number
    Step_Timer: number
    Mixing_Tank_Volume: number
    Mixing_Tank_Temperature: number
    MixingTank_Agitator_Speed: number
    HighShare_Speed: number
    Hopper_Weight?: number
    HighShare_Temperature?: number
    Circulation_Speed?: number
    Flow_Rate?: number
    Circulation_Temperature?: number
    watchdog?: number
    last_update?: string
}

const mqttClient = ref<mqtt.MqttClient | null>(null)
const isConnected = ref(false)
const connectionStatus = ref('Disconnected')

// State to hold data for the 3 plants
const plantsData = ref<Record<string, PlantData>>({
    '1': { Step_no: 0, Step_Timer: 0, Mixing_Tank_Volume: 0, Mixing_Tank_Temperature: 0, MixingTank_Agitator_Speed: 0, HighShare_Speed: 0, watchdog: 0, last_update: '' },
    '2': { Step_no: 0, Step_Timer: 0, Mixing_Tank_Volume: 0, Mixing_Tank_Temperature: 0, MixingTank_Agitator_Speed: 0, HighShare_Speed: 0, watchdog: 0, last_update: '' },
    '3': { Step_no: 0, Step_Timer: 0, Mixing_Tank_Volume: 0, Mixing_Tank_Temperature: 0, MixingTank_Agitator_Speed: 0, HighShare_Speed: 0, watchdog: 0, last_update: '' }
})

export function useMQTT() {
    const getBrokerUrl = () => {
        const hostname = (typeof window !== 'undefined' && window.location) ? window.location.hostname : 'localhost'
        return `ws://${hostname}:15675/ws`
    }

    const MQTT_BROKER = getBrokerUrl()
    const MQTT_USERNAME = 'xMixingNode-1'
    const MQTT_PASSWORD = 'x123456'

    const connect = () => {
        if (import.meta.server) return

        if (mqttClient.value?.connected || connectionStatus.value === 'Connecting...') {
            return
        }

        try {
            connectionStatus.value = 'Connecting...'
            const url = new URL(MQTT_BROKER)

            const options: any = {
                clientId: `xmixing-plants-${Math.random().toString(16).substring(2, 10)}`,
                username: MQTT_USERNAME,
                password: MQTT_PASSWORD,
                reconnectPeriod: 1000,
                clean: true,
                connectTimeout: 2000,
                protocolVersion: 4,
                protocol: url.protocol.replace(':', ''),
                host: url.hostname,
                port: parseInt(url.port),
                path: url.pathname,
                wsOptions: { protocols: ['mqtt'] }
            }

            mqttClient.value = mqtt.connect(options)

            mqttClient.value.on('connect', () => {
                isConnected.value = true
                connectionStatus.value = 'Connected'
                console.log('✅ MQTT Connected inside useMQTT.ts - Subscribing to #! catching ALL topic traffic!')
                mqttClient.value?.subscribe('#')
                console.log('✅ Connected to RabbitMQ for Plant Data')
            })

            mqttClient.value.on('message', (topic, message) => {
                try {
                    const payload = JSON.parse(message.toString())
                    console.log('📥 [useMQTT] Topic:', topic, 'Payload:', payload)
                    
                    let plantId = ''
                    if (topic.toUpperCase().includes('MIX-1') || topic.toUpperCase().includes('MIX-01') || topic.includes('mixing/plant/1')) plantId = '1'
                    if (topic.toUpperCase().includes('MIX-2') || topic.toUpperCase().includes('MIX-02') || topic.includes('mixing/plant/2')) plantId = '2'
                    if (topic.toUpperCase().includes('MIX-3') || topic.toUpperCase().includes('MIX-03') || topic.includes('mixing/plant/3')) plantId = '3'
                    
                    let actualPayload = payload
                    // Automatically unwrap if the data is nested inside "MIX-0X"
                    if (payload['MIX-01']) { plantId = '1'; actualPayload = payload['MIX-01'] }
                    else if (payload['MIX-02']) { plantId = '2'; actualPayload = payload['MIX-02'] }
                    else if (payload['MIX-03']) { plantId = '3'; actualPayload = payload['MIX-03'] }
                    
                    // Extremely aggressive fallback: check the payload itself for the plant ID!
                    if (actualPayload['MIX-01.WATCHDOG'] !== undefined || actualPayload['AGI301.CurSpeed'] !== undefined) plantId = '1'
                    if (actualPayload['MIX-02.WATCHDOG'] !== undefined || actualPayload['AGI302.CurSpeed'] !== undefined) plantId = '2'
                    if (actualPayload['MIX-03.WATCHDOG'] !== undefined || actualPayload['AGI303.CurSpeed'] !== undefined) plantId = '3'
                    
                    // Universal fallback for new JSON format if plantId is still empty
                    if (!plantId && (actualPayload['Watch-Dog'] !== undefined || actualPayload.Step_No !== undefined || actualPayload.MixingTank !== undefined)) {
                        plantId = '1' // Default to Plant 1 for unrecognized topics pushing the new schema
                    }

                    if (plantId) {
                        console.log(`📥 [Vue Dashboard] Valid payload parsed for Plant ${plantId} from topic "${topic}"`)
                        const prev = (plantsData.value[plantId] || {}) as Partial<PlantData>
                        
                        const round2 = (val: any) => {
                            if (val === undefined || val === null) return undefined;
                            const n = Number(val);
                            return isNaN(n) ? val : Number(n.toFixed(2));
                        }

                        plantsData.value = {
                            ...plantsData.value,
                            [plantId]: {
                                ...prev,
                                ...actualPayload,
                                Step_no: (actualPayload[`MIX0${plantId}.STEP_NO`] ?? actualPayload.Step_No ?? actualPayload.Step_no ?? prev.Step_no) || 0,
                                Step_Timer: (actualPayload[`MIX0${plantId}.STEP_TIMER`] ?? actualPayload.Step_Timer ?? prev.Step_Timer) || 0,
                                watchdog: actualPayload[`MIX0${plantId}.WATCHDOG`] ?? actualPayload['Watch-Dog'] ?? prev.watchdog,
                                Hopper_Weight: round2(actualPayload[`MIX0${plantId}.HOPPER.SCALE`] ?? prev.Hopper_Weight),
                                MixingTank_Agitator_Speed: round2(actualPayload[`MIX0${plantId}.MIXING.AJITATOR SPEED`] ?? prev.MixingTank_Agitator_Speed),
                                HighShare_Speed: round2(actualPayload[`MIX0${plantId}.HIGHSHARE.SPEED`] ?? prev.HighShare_Speed),
                                HighShare_Temperature: round2(actualPayload[`MIX0${plantId}.HIGHSHARE.TEMPERATURE`] ?? prev.HighShare_Temperature),
                                Mixing_Tank_Volume: round2(actualPayload[`MIX0${plantId}.MIXING.SCALE`] ?? prev.Mixing_Tank_Volume),
                                Mixing_Tank_Temperature: round2(actualPayload[`MIX0${plantId}.MIXING.TEMPERATURE`] ?? prev.Mixing_Tank_Temperature),
                                Circulation_Speed: round2(actualPayload[`MIX0${plantId}.CIRCULATION.PUMP SPEED`] ?? prev.Circulation_Speed),
                                Flow_Rate: round2(actualPayload[`MIX0${plantId}.CIRCULATION.FLOW RATE`] ?? prev.Flow_Rate),
                                Circulation_Temperature: round2(actualPayload[`MIX0${plantId}.CIRCULATION.TEMPERATURE`] ?? prev.Circulation_Temperature),
                                last_update: new Date().toLocaleTimeString()
                            }
                        }
                    }
                } catch (e) {
                    console.error('Error parsing plant MQTT message', e)
                }
            })

            mqttClient.value.on('error', (err) => {
                console.error('MQTT Error', err)
                connectionStatus.value = `Error: ${err.message}`
            })

            mqttClient.value.on('close', () => {
                isConnected.value = false
                connectionStatus.value = 'Disconnected'
            })
        } catch (error) {
            connectionStatus.value = `Failed: ${error && (error as any).message}`
        }
    }

    const disconnect = () => {
        if (mqttClient.value) {
            mqttClient.value.end()
            mqttClient.value = null
            isConnected.value = false
            connectionStatus.value = 'Disconnected'
        }
    }

    const publishMessage = (topic: string, payload: any) => {
        if (mqttClient.value && isConnected.value) {
            const messageStr = typeof payload === 'string' ? payload : JSON.stringify(payload)
            mqttClient.value.publish(topic, messageStr)
            console.log(`🚀 [useMQTT] Published to ${topic}:`, payload)
            return true
        }
        console.warn(`[useMQTT] Cannot publish to ${topic} - Not connected`)
        return false
    }

    return {
        connect,
        disconnect,
        publishMessage,
        isConnected,
        connectionStatus,
        plantsData
    }
}

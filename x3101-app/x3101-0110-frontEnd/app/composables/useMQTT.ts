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
    // Node-RED /Mix-0X/Recipe individual topic fields
    IBC_REQ?: number       // MIX01.IBC_REQ  — IBC scale weight (kg)
    LS_REQ?: number        // MIX01.LS_REQ   — Line speed / liquid scale
    MIS_REQ?: number       // MIX01.MIS_REQ  — Mixing tank scale weight
    RO_REQ?: number        // MIX01.RO_REQ   — RO water flow / volume
    TEMP01?: number        // MIX01.TEMP01   — Mixing tank temperature
    TEMP02?: number        // MIX01.TEMP02   — High shear temperature
    TEMP03?: number        // MIX01.TEMP03   — Circulation temperature
    lastScan?: {
        batch_record_id: string
        material_id: string
        net_weight: number
        timestamp: string
    }
}

// ── Node-RED individual topic → field map ──────────────────────────────────
// Maps topic suffix (after "MIX0X.") to the PlantData field it populates
const NODE_RED_FIELD_MAP: Record<string, keyof PlantData> = {
    'IBC_REQ':  'IBC_REQ',
    'LS_REQ':   'LS_REQ',
    'MIS_REQ':  'MIS_REQ',
    'RO_REQ':   'RO_REQ',
    'TEMP01':   'TEMP01',
    'TEMP02':   'TEMP02',
    'TEMP03':   'TEMP03',
}

const mqttClient = ref<mqtt.MqttClient | null>(null)
const isConnected = ref(false)
const connectionStatus = ref('Disconnected')
const messageCallbacks = new Set<(topic: string, payload: any) => void>()

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
                const messageStr = message.toString()
                console.log('📥 [MQTT raw]', topic, messageStr)

                try {
                    const round2 = (val: any) => {
                        if (val === undefined || val === null) return undefined;
                        const n = Number(val);
                        return isNaN(n) ? val : Number(n.toFixed(2));
                    }

                    // ── NODE-RED Individual Topic Handler ───────────────────────────────
                    // Topics: MIX01.IBC_REQ, MIX01.LS_REQ, MIX01.MIS_REQ, MIX01.RO_REQ
                    //         MIX01.TEMP01,  MIX01.TEMP02,  MIX01.TEMP03
                    const topicUpper = topic.toUpperCase()
                    const mixMatch = topicUpper.match(/^MIX0?(\d+)\.(.+)$/)
                    if (mixMatch) {
                        const plantId = mixMatch[1]!          // '1', '2', '3'
                        const fieldKey = mixMatch[2]!          // 'IBC_REQ', 'TEMP01', etc.
                        const numVal = round2(messageStr)

                        // Find which PlantData field this maps to
                        const mappedField = NODE_RED_FIELD_MAP[fieldKey]

                        if (mappedField !== undefined && plantId) {
                            const prev = (plantsData.value[plantId] || {}) as Partial<PlantData>
                            console.log(`📊 [Node-RED] Plant ${plantId} | ${fieldKey} → ${mappedField} = ${numVal}`)

                            // Also mirror to semantic fields for existing computed properties
                            const semanticUpdate: Partial<PlantData> = {
                                [mappedField]: numVal,
                                last_update: new Date().toLocaleTimeString()
                            }

                            // Mirror to canonical PlantData fields
                            if (fieldKey === 'IBC_REQ')  semanticUpdate.Hopper_Weight = numVal
                            if (fieldKey === 'MIS_REQ')  semanticUpdate.Mixing_Tank_Volume = numVal
                            if (fieldKey === 'TEMP01')   semanticUpdate.Mixing_Tank_Temperature = numVal
                            if (fieldKey === 'TEMP02')   semanticUpdate.HighShare_Temperature = numVal
                            if (fieldKey === 'TEMP03')   semanticUpdate.Circulation_Temperature = numVal
                            if (fieldKey === 'LS_REQ')   semanticUpdate.Circulation_Speed = numVal
                            if (fieldKey === 'RO_REQ')   semanticUpdate.Flow_Rate = numVal

                            plantsData.value = {
                                ...plantsData.value,
                                [plantId]: { ...prev, ...semanticUpdate } as PlantData
                            }

                            // Trigger registered callbacks
                            messageCallbacks.forEach(cb => cb(topic, { [mappedField]: numVal, raw: messageStr }))
                            return  // Handled — skip generic parser below
                        }
                    }

                    // ── /Mix-0X/Recipe Full Payload Handler ─────────────────────────────
                    // Topic: /Mix-01/Recipe (Node-RED publishes full recipe object here)
                    const recipeMatch = topic.match(/\/Mix-0?(\d+)\/Recipe/i)
                    if (recipeMatch) {
                        const plantId = recipeMatch[1]!
                        let payload: any = {}
                        try { payload = JSON.parse(messageStr) } catch { payload = { raw: messageStr } }

                        const prev = (plantsData.value[plantId] || {}) as Partial<PlantData>
                        console.log(`📦 [Node-RED Recipe] Plant ${plantId}:`, payload)
                        plantsData.value = {
                            ...plantsData.value,
                            [plantId]: {
                                ...prev,
                                IBC_REQ:  round2(payload.IBC_REQ  ?? payload['MIX01.IBC_REQ']  ?? prev.IBC_REQ),
                                LS_REQ:   round2(payload.LS_REQ   ?? payload['MIX01.LS_REQ']   ?? prev.LS_REQ),
                                MIS_REQ:  round2(payload.MIS_REQ  ?? payload['MIX01.MIS_REQ']  ?? prev.MIS_REQ),
                                RO_REQ:   round2(payload.RO_REQ   ?? payload['MIX01.RO_REQ']   ?? prev.RO_REQ),
                                TEMP01:   round2(payload.TEMP01   ?? payload['MIX01.TEMP01']   ?? prev.TEMP01),
                                TEMP02:   round2(payload.TEMP02   ?? payload['MIX01.TEMP02']   ?? prev.TEMP02),
                                TEMP03:   round2(payload.TEMP03   ?? payload['MIX01.TEMP03']   ?? prev.TEMP03),
                                // Mirror to canonical fields
                                Hopper_Weight:            round2(payload.IBC_REQ  ?? payload['MIX01.IBC_REQ']  ?? prev.Hopper_Weight),
                                Mixing_Tank_Volume:       round2(payload.MIS_REQ  ?? payload['MIX01.MIS_REQ']  ?? prev.Mixing_Tank_Volume),
                                Mixing_Tank_Temperature:  round2(payload.TEMP01   ?? payload['MIX01.TEMP01']   ?? prev.Mixing_Tank_Temperature),
                                HighShare_Temperature:    round2(payload.TEMP02   ?? payload['MIX01.TEMP02']   ?? prev.HighShare_Temperature),
                                Circulation_Temperature:  round2(payload.TEMP03   ?? payload['MIX01.TEMP03']   ?? prev.Circulation_Temperature),
                                Circulation_Speed:        round2(payload.LS_REQ   ?? payload['MIX01.LS_REQ']   ?? prev.Circulation_Speed),
                                Flow_Rate:                round2(payload.RO_REQ   ?? payload['MIX01.RO_REQ']   ?? prev.Flow_Rate),
                                last_update: new Date().toLocaleTimeString()
                            } as PlantData
                        }
                        messageCallbacks.forEach(cb => cb(topic, payload))
                        return
                    }

                    // ── Generic / Legacy JSON Handler ───────────────────────────────────
                    let payload: any
                    if (messageStr.startsWith('{')) {
                        try {
                            payload = JSON.parse(messageStr)
                        } catch (e) {
                            payload = {}
                            const pairs = messageStr.match(/"?(\w+)"?\s*:\s*"?([^,"}]*)"?/g)
                            if (pairs) {
                                pairs.forEach(pair => {
                                    const m = pair.match(/"?(\w+)"?\s*:\s*"?([^,"}]*)"?/)
                                    if (m) {
                                        const key = m[1]!
                                        let val: any = m[2]!.replace(/"/g, '').trim()
                                        const num = Number(val)
                                        payload[key] = isNaN(num) || val === '' ? val : num
                                    }
                                })
                            }
                        }
                    } else {
                        payload = { raw: messageStr }
                    }

                    console.log('📥 [Parsed Payload]', payload)
                    messageCallbacks.forEach(cb => cb(topic, payload))
                    
                    let plantId = ''
                    if (topicUpper.includes('MIX-1') || topicUpper.includes('MIX-01') || topic.includes('mixing/plant/1')) plantId = '1'
                    if (topicUpper.includes('MIX-2') || topicUpper.includes('MIX-02') || topic.includes('mixing/plant/2')) plantId = '2'
                    if (topicUpper.includes('MIX-3') || topicUpper.includes('MIX-03') || topic.includes('mixing/plant/3')) plantId = '3'
                    
                    let actualPayload = payload
                    if (payload['MIX-01']) { plantId = '1'; actualPayload = payload['MIX-01'] }
                    else if (payload['MIX-02']) { plantId = '2'; actualPayload = payload['MIX-02'] }
                    else if (payload['MIX-03']) { plantId = '3'; actualPayload = payload['MIX-03'] }
                    
                    if (actualPayload['MIX-01.WATCHDOG'] !== undefined || actualPayload['AGI301.CurSpeed'] !== undefined) plantId = '1'
                    if (actualPayload['MIX-02.WATCHDOG'] !== undefined || actualPayload['AGI302.CurSpeed'] !== undefined) plantId = '2'
                    if (actualPayload['MIX-03.WATCHDOG'] !== undefined || actualPayload['AGI303.CurSpeed'] !== undefined) plantId = '3'
                    
                    if (!plantId && (actualPayload['Watch-Dog'] !== undefined || actualPayload.Step_No !== undefined || actualPayload.MixingTank !== undefined)) {
                        plantId = '1'
                    }

                    if (plantId) {
                        console.log(`📥 [Vue Dashboard] Valid payload parsed for Plant ${plantId} from topic "${topic}"`)
                        const prev = (plantsData.value[plantId] || {}) as Partial<PlantData>

                        plantsData.value = {
                            ...plantsData.value,
                            [plantId]: {
                                ...prev,
                                ...actualPayload,
                                Step_no: (actualPayload[`MIX0${plantId}.STEP_NO`] ?? actualPayload.Step_No ?? actualPayload.Step_no ?? actualPayload.Step_No_Act ?? prev.Step_no) || 0,
                                Step_ID: (actualPayload[`MIX0${plantId}.Step_ID`] ?? actualPayload.Step_ID ?? actualPayload.Step_id ?? prev.Step_ID) || 0,
                                Batch_ID: actualPayload[`MIX0${plantId}.Batch_ID`] ?? actualPayload[`MIX0${plantId}.Batch_id`] ?? actualPayload.Batch_ID ?? actualPayload.Batch_id ?? actualPayload.batch_id ?? prev.Batch_ID,
                                Plan_ID: actualPayload[`MIX0${plantId}.Plan_ID`] ?? actualPayload[`MIX0${plantId}.Plan_id`] ?? actualPayload.Plan_ID ?? actualPayload.Plan_id ?? actualPayload.plan_id ?? prev.Plan_ID,
                                SKU_Name: actualPayload[`MIX0${plantId}.SKU_Name`] ?? actualPayload[`MIX0${plantId}.SKU_name`] ?? actualPayload.SKU_Name ?? actualPayload.SKU_name ?? actualPayload.sku_name ?? prev.SKU_Name,
                                PLC_State: (actualPayload[`MIX0${plantId}.PLC_State`] ?? actualPayload.PLC_State ?? prev.PLC_State) || 0,
                                Current_Step: (actualPayload[`MIX0${plantId}.Current_Step`] ?? actualPayload.Current_Step ?? prev.Current_Step) || 0,
                                Step_Timer: (actualPayload[`MIX0${plantId}.STEP_TIMER`] ?? actualPayload[`MIX0${plantId}.Step_Timer`] ?? actualPayload.Step_Timer ?? actualPayload.Timer_Act ?? prev.Step_Timer) || 0,
                                watchdog: actualPayload[`MIX0${plantId}.WATCHDOG`] ?? actualPayload[`MIX0${plantId}.Watch_Doc`] ?? actualPayload['Watch-Dog'] ?? actualPayload.Watch_Doc ?? prev.watchdog,
                                Hopper_Weight: round2(actualPayload[`MIX0${plantId}.HOPPER.SCALE`] ?? actualPayload[`MIX0${plantId}.Hopper_Weight`] ?? actualPayload.Hopper_Weight ?? actualPayload.HopperScale_Act ?? prev.Hopper_Weight),
                                MixingTank_Agitator_Speed: round2(actualPayload[`MIX0${plantId}.MIXING.AJITATOR SPEED`] ?? actualPayload[`MIX0${plantId}.Agitator_Act`] ?? actualPayload.MixingTank_Agitator_Speed ?? actualPayload.Agitator_Act ?? actualPayload.Agitator_Speed ?? prev.MixingTank_Agitator_Speed),
                                HighShare_Speed: round2(actualPayload[`MIX0${plantId}.HIGHSHARE.SPEED`] ?? actualPayload[`MIX0${plantId}.HighShear_Act`] ?? actualPayload.HighShare_Speed ?? actualPayload.HighShear_Act ?? actualPayload.HighShare_Speed_Act ?? prev.HighShare_Speed),
                                HighShare_Temperature: round2(actualPayload[`MIX0${plantId}.HIGHSHARE.TEMPERATURE`] ?? actualPayload[`MIX0${plantId}.HighShear_Temp`] ?? actualPayload.HighShare_Temperature ?? actualPayload.HighShear_Temp ?? prev.HighShare_Temperature),
                                Mixing_Tank_Volume: round2(actualPayload[`MIX0${plantId}.MIXING.SCALE`] ?? actualPayload[`MIX0${plantId}.MixTank_Weight`] ?? actualPayload.Mixing_Tank_Volume ?? actualPayload.Mixing_Tank_Weight ?? actualPayload.MixTank_Weight ?? actualPayload.Scale_Act ?? prev.Mixing_Tank_Volume),
                                Mixing_Tank_Temperature: round2(actualPayload[`MIX0${plantId}.MIXING.TEMPERATURE`] ?? actualPayload[`MIX0${plantId}.MixTank_Temp`] ?? actualPayload.Mixing_Tank_Temperature ?? actualPayload.MixTank_Temp ?? actualPayload.Temp_Act ?? prev.Mixing_Tank_Temperature),
                                Circulation_Speed: round2(actualPayload[`MIX0${plantId}.CIRCULATION.PUMP SPEED`] ?? actualPayload[`MIX0${plantId}.Circulation_Pump_Act`] ?? actualPayload.Circulation_Speed ?? actualPayload.Circulation_Pump_Act ?? prev.Circulation_Speed),
                                Flow_Rate: round2(actualPayload[`MIX0${plantId}.CIRCULATION.FLOW RATE`] ?? actualPayload[`MIX0${plantId}.Flow_Rate_Act`] ?? actualPayload.Flow_Rate ?? actualPayload.Flow_Rate_Act ?? prev.Flow_Rate),
                                Circulation_Temperature: round2(actualPayload[`MIX0${plantId}.CIRCULATION.TEMPERATURE`] ?? actualPayload[`MIX0${plantId}.Circulation_Temp_Act`] ?? actualPayload.Circulation_Temperature ?? actualPayload.Circulation_Temp_Act ?? prev.Circulation_Temperature),
                                last_update: new Date().toLocaleTimeString()
                            }
                        }

                        if (actualPayload.b) {
                            const prevData = plantsData.value[plantId];
                            plantsData.value = {
                                ...plantsData.value,
                                [plantId]: {
                                    ...prevData,
                                    lastScan: {
                                        batch_record_id: String(actualPayload.b),
                                        material_id: String(actualPayload.m || ''),
                                        net_weight: Number(actualPayload.n || 0),
                                        timestamp: new Date().toLocaleTimeString()
                                    }
                                }
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

    const onMessage = (cb: (topic: string, payload: any) => void) => {
        messageCallbacks.add(cb)
    }

    const offMessage = (cb: (topic: string, payload: any) => void) => {
        messageCallbacks.delete(cb)
    }

    return {
        connect,
        disconnect,
        publishMessage,
        onMessage,
        offMessage,
        isConnected,
        connectionStatus,
        plantsData
    }
}


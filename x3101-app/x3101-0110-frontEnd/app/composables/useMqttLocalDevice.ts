import { ref, watch } from 'vue'
import mqtt from 'mqtt'
import { useQuasar } from 'quasar'

export interface ScanData {
    node_id: string
    barcode: string
    timestamp: string
    location?: string
    scanner_type?: string
    metadata?: Record<string, any>
}

// Global state for MQTT - shared across all components (Singleton Pattern)
const mqttClient = ref<mqtt.MqttClient | null>(null)
const isConnected = ref(false)
const lastScan = ref<ScanData | null>(null)
const scanHistory = ref<ScanData[]>([])
const connectionStatus = ref('Disconnected')

// Topics to subscribe to
const TOPICS = ['scanner/+/scan', 'scale/#']

export function useMqttLocalDevice() {
    // Configuration
    const getBrokerUrl = () => {
        const hostname = (typeof window !== 'undefined' && window.location) ? window.location.hostname : 'localhost'
        return `ws://${hostname}:15675/ws`
    }

    const MQTT_BROKER = getBrokerUrl()
    const MQTT_USERNAME = 'xMixingNode-1'
    const MQTT_PASSWORD = 'x123456'

    const connect = () => {
        // 1. Never run on Server-Side (Nuxt SSR)
        if (import.meta.server) return

        // 2. Prevent multiple connections
        if (mqttClient.value?.connected || connectionStatus.value === 'Connecting...') {
            console.log('📡 MQTT (Local): Already connected or connecting')
            return
        }

        try {
            console.log('🔌 MQTT (Local): Initializing connection to', MQTT_BROKER)
            connectionStatus.value = 'Connecting...'

            const url = new URL(MQTT_BROKER)

            const options: any = {
                clientId: `xmixing-web-local-${Math.random().toString(16).substring(2, 10)}`,
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
                wsOptions: {
                    protocols: ['mqtt']
                }
            }

            mqttClient.value = mqtt.connect(options)

            mqttClient.value.on('connect', () => {
                console.log('✅ MQTT (Local): Connected')
                isConnected.value = true
                connectionStatus.value = 'Connected'

                TOPICS.forEach(topic => {
                    mqttClient.value?.subscribe(topic)
                    console.log(`📡 MQTT (Local): Subscribed to ${topic}`)
                })
            })

            mqttClient.value.on('message', (topic, message) => {
                try {
                    // Skip scale messages - handled by page-specific handlers
                    if (topic.startsWith('scale/')) {
                        console.log(`📊 MQTT (Local): Scale data on ${topic} - skipping global handler`)
                        return
                    }

                    const payload = message.toString()
                    let scanData: ScanData

                    try {
                        // Try parsing as JSON first
                        scanData = JSON.parse(payload)
                    } catch {
                        // Fallback for plain text barcodes
                        scanData = {
                            node_id: topic === 'scanner/+/scan' ? 'scanner' : topic,
                            barcode: payload.trim(),
                            timestamp: new Date().toISOString()
                        }
                    }

                    console.log(`📦 MQTT (Local): Message on ${topic}:`, scanData)
                    lastScan.value = scanData
                    scanHistory.value.unshift(scanData)

                    // Keep history manageable
                    if (scanHistory.value.length > 50) {
                        scanHistory.value = scanHistory.value.slice(0, 50)
                    }

                    // Show global notification if on client
                    if (import.meta.client) {
                        const $q = useQuasar()
                        $q.notify({
                            type: 'info',
                            message: `Scan: ${scanData.barcode}`,
                            caption: `From ${scanData.node_id}`,
                            position: 'top-right',
                            icon: 'qr_code_scanner'
                        })
                    }
                } catch (error) {
                    console.error('❌ MQTT (Local): Message processing error', error)
                }
            })

            mqttClient.value.on('error', (err) => {
                console.error('❌ MQTT (Local): Error', err)
                connectionStatus.value = `Error: ${err.message}`
            })

            mqttClient.value.on('close', () => {
                isConnected.value = false
                connectionStatus.value = 'Disconnected'
            })

            mqttClient.value.on('reconnect', () => {
                connectionStatus.value = 'Reconnecting...'
            })

        } catch (error) {
            console.error('❌ MQTT (Local): Bootstrap error', error)
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

    const publish = (topic: string, message: string | object) => {
        if (mqttClient.value?.connected) {
            const payload = typeof message === 'string' ? message : JSON.stringify(message)
            mqttClient.value.publish(topic, payload)
        }
    }

    return {
        connect,
        disconnect,
        publish,
        isConnected,
        connectionStatus,
        lastScan,
        scanHistory,
        mqttClient
    }
}

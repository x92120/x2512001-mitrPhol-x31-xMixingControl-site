<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useMQTT } from '~/composables/useMQTT'

const $q = useQuasar()

// Simulated PLC State Registers
const simState = ref({
    PLC_State: 1, // 1=Idle, 2=Running, 3=Hold, 4=Fault
    Step_No: 0,
    Step_Timer: 0,
    Brix: 0.0,
    PH: 0.0,
    Temperature: 0.0,
    Agitator_RPM: 0.0,
    Hopper_Weight: 0.0,
    Water_Meter: 0.0,
    Checksum: 0
})

const timerInterval = ref<any>(null)
const broadcastInterval = ref<any>(null)

// Shared MQTT Connection
const { connect, publishMessage, isConnected: plcConnectedGlobal, onMessage, offMessage } = useMQTT()

// Incoming Command Log
const incomingLogs = ref<any[]>([])

// Handle incoming commands from Frontend / Backend
const handleSimulatorMessage = (topic: string, payload: any) => {
    let parsed = payload
    if (typeof payload === 'string') {
        try { parsed = JSON.parse(payload) } catch(e) {}
    }

    // Log the incoming message
    incomingLogs.value.unshift({ time: new Date().toLocaleTimeString(), topic, payload: parsed })
    if (incomingLogs.value.length > 20) incomingLogs.value.pop()

    // 1. Respond to Start / Stop / Next commands
    if (topic.includes('/cmd')) {
        if (parsed.command === 'START') {
            simState.value.PLC_State = 2 // Running
            if (simState.value.Step_No === 0) simState.value.Step_No = 1
        }
        else if (parsed.command === 'PAUSE') {
            simState.value.PLC_State = 3 // Hold
        }
        else if (parsed.command === 'ABORT') {
            simState.value.PLC_State = 1 // Idle
            simState.value.Step_No = 0
            simState.value.Step_Timer = 0
        }
    }

    // 2. Respond to Recipe Transfer Checksum calculation
    // The backend chunking algorithm sends target_checksum. In a real PLC, it adds them up.
    // For simulation, we'll just echo the Checksum so the backend verification succeeds!
    if (topic.includes('/recipe_transfer')) {
        if (parsed.command === 'PREPARE') {
            simState.value.Checksum = 0 // Reset
        } else if (parsed.command === 'VERIFY') {
            // Fake the successful checksum verification
            simState.value.Checksum = parsed.target_checksum
        }
    }

    // 3. Respond to Step Confirm from the Operator (Manual Add)
    if (topic.includes('/step_confirm')) {
        if (parsed.Confirm_Step) {
            $q.notify({ type: 'positive', message: 'Operator Confirmed Step!', position: 'bottom' })
            // Auto-advance simulation to next step
            triggerStepDone()
        }
    }
}

// ── Simulator Actions ──

const triggerStepDone = () => {
    // 1. Broadcast STEP_COMPLETE to mixing/plant/1/status (so x62 knows)
    publishMessage(`mixing/plant/1/status`, {
        status: 'STEP_COMPLETE',
        step_no: simState.value.Step_No,
        timestamp: new Date().toISOString()
    })
    
    // 2. Advance simulated step
    simState.value.Step_No += 1
    simState.value.Step_Timer = 0
    
    $q.notify({ type: 'info', message: `Fired STEP_COMPLETE for Step ${simState.value.Step_No - 1}` })
}

const sendAlarm = () => {
    publishMessage(`mixing/plant/1/alarms`, {
        code: 'A1001',
        message: 'SIMULATED AGITATOR FAULT',
        severity: 'high',
        timestamp: new Date().toISOString()
    })
    simState.value.PLC_State = 4 // Fault
}

// ── Main Loop ──
onMounted(() => {
    if (!plcConnectedGlobal.value) connect()
    
    onMessage(handleSimulatorMessage)

    // Simulate Step Timer if running
    timerInterval.value = setInterval(() => {
        if (simState.value.PLC_State === 2) {
            simState.value.Step_Timer += 1
        }
    }, 1000)

    // Broadcast MIX-01-READ 10x a second like the real PLC
    broadcastInterval.value = setInterval(() => {
        if (plcConnectedGlobal.value) {
            publishMessage('MIX-01-READ', {
                PLC_State: simState.value.PLC_State,
                Step_No: simState.value.Step_No,
                Step_Timer: simState.value.Step_Timer,
                Brix: simState.value.Brix,
                PH: simState.value.PH,
                Temperature: simState.value.Temperature,
                Agitator_RPM: simState.value.Agitator_RPM,
                Hopper_Weight: simState.value.Hopper_Weight,
                Water_Meter: simState.value.Water_Meter,
                Checksum: simState.value.Checksum,
                Process_Active: 1 // Simulated Active
            })
        }
    }, 1000)
})

onUnmounted(() => {
    offMessage(handleSimulatorMessage)
    if (timerInterval.value) clearInterval(timerInterval.value)
    if (broadcastInterval.value) clearInterval(broadcastInterval.value)
})

</script>

<template>
  <q-page padding class="bg-grey-2" style="font-family: 'Inter', sans-serif;">
    <div class="row items-center q-mb-md">
      <q-icon name="precision_manufacturing" size="40px" color="teal-8" class="q-mr-sm" />
      <div>
        <h4 class="text-h5 text-weight-bolder text-teal-10 q-my-none">PLC Simulator Test Module</h4>
        <div class="text-caption text-grey-7">Simulate S7-1200 hardware signals over MQTT to test Production Workflow</div>
      </div>
      <q-space />
      <q-chip :color="plcConnectedGlobal ? 'positive' : 'negative'" text-color="white" icon="wifi">
        {{ plcConnectedGlobal ? 'MQTT Connected' : 'Disconnected' }}
      </q-chip>
    </div>

    <div class="row q-col-gutter-md">
      <!-- CONTROL PANEL -->
      <div class="col-12 col-md-5">
        <q-card class="shadow-2" style="border-radius: 12px; height: 100%;">
          <div class="bg-teal-9 text-white q-pa-sm text-subtitle1 text-weight-bold text-center">
            Virtual PLC Control Panel
          </div>
          <q-card-section>
            <q-select 
                v-model="simState.PLC_State" 
                :options="[{label:'1 - Idle', value:1}, {label:'2 - Running', value:2}, {label:'3 - Hold', value:3}, {label:'4 - Fault', value:4}]" 
                emit-value map-options
                label="Global PLC State" 
                outlined dense class="q-mb-md"
            />
            
            <div class="row q-col-gutter-sm q-mb-md">
              <div class="col-6">
                <q-input v-model.number="simState.Step_No" type="number" label="Current Step No" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.Step_Timer" type="number" label="Step Timer (sec)" outlined dense />
              </div>
            </div>

            <q-separator class="q-my-md" />
            <div class="text-caption text-grey-8 text-weight-bold q-mb-sm">Simulated Sensors</div>
            
            <div class="row q-col-gutter-sm">
              <div class="col-6">
                <q-input v-model.number="simState.Hopper_Weight" type="number" label="Hopper Weight (kg)" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.Water_Meter" type="number" label="Water Meter (L)" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.Temperature" type="number" label="Temperature (°C)" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.Agitator_RPM" type="number" label="Agitator RPM" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.Brix" type="number" label="In-line Brix" outlined dense />
              </div>
              <div class="col-6">
                <q-input v-model.number="simState.PH" type="number" label="In-line pH" outlined dense />
              </div>
            </div>

            <div class="row q-col-gutter-sm q-mt-lg">
                <div class="col-6">
                    <q-btn color="primary" class="full-width" icon="skip_next" label="Fire STEP DONE" @click="triggerStepDone" />
                </div>
                <div class="col-6">
                    <q-btn color="negative" class="full-width" icon="warning" label="Trigger Alarm" @click="sendAlarm" />
                </div>
            </div>
            
            <div class="text-caption text-grey text-center q-mt-sm">
                * Simulates the exact payload sent by Node-RED from the real PLC
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- INCOMING LOGS -->
      <div class="col-12 col-md-7">
        <q-card class="shadow-2" style="border-radius: 12px; height: 100%;">
          <div class="bg-grey-9 text-white q-pa-sm text-subtitle1 text-weight-bold text-center row justify-between items-center">
            <span>Incoming App/Backend Commands</span>
            <q-btn flat round dense icon="delete" @click="incomingLogs = []" />
          </div>
          <q-card-section style="max-height: 500px; overflow-y: auto;" class="bg-black text-green-4 font-mono text-caption">
            <div v-if="incomingLogs.length === 0" class="text-grey-6 text-center q-pa-lg">
                Waiting for commands from Mixing Control...
            </div>
            <div v-for="(log, i) in incomingLogs" :key="i" class="q-mb-sm q-pb-sm" style="border-bottom: 1px solid #333;">
                <div class="text-yellow-6">[{{ log.time }}] Topic: {{ log.topic }}</div>
                <pre class="q-ma-none" style="white-space: pre-wrap; word-break: break-all;">{{ log.payload }}</pre>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.font-mono { font-family: 'Courier New', Courier, monospace; }
</style>

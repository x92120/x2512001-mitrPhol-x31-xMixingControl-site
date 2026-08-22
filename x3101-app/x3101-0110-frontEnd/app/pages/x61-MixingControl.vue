<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useRoute, useRouter } from 'vue-router'
import { useMQTT } from '~/composables/useMQTT'

// ── Global API & State Base ──
const remoteApiBaseUrl = computed(() => appConfig.apiBaseUrl)
let _lastUserStepAction = 0  // Timestamp of last manual step change to prevent multi-client sync race

// ── PLC Step Descriptions ──
const plcStepDescriptions: Record<number, string> = {
  0: "Stand By",
  1: "Starting Program",
  2: "Start Program",
  3: "Filling Major Ingredient",
  4: "Fill Major Ingredient",
  5: "Filling Major Done",
  6: "Fill Major Done",
  7: "Preblending",
  8: "Preblending",
  9: "Waiting First Confirm",
  10: "First Confirm",
  11: "Pre Heating",
  12: "Pre Heats",
  13: "Filling Minor Ingredient",
  14: "Fill Minor Ingredient",
  15: "Second Heating",
  16: "Second Heat",
  17: "Filling Third Ingredient",
  18: "Fill Third Ingredient",
  19: "Pasteurizing",
  20: "Pasteurizer",
  21: "Waiting QC Confirm",
  22: "QC Confirm",
  23: "Preparing Transfer",
  24: "Ready To Transfer",
  25: "Transferring",
  26: "Transferring",
  27: "Ending STEP",
  28: "End STEP"
}

// ── Phase_Type + Action_Code → PLC Step Number ──────────────────────────────
// Matches FC_MapPhaseToStep.scl v1.0 (2026-07-06) exactly
// phaseType: 1=A1010, 2=A1020, 3=D1010, 4=D1030, 5=x1010, 6=x1020, 7=x1030, 8=x1040
const getPlcStepNumber = (phaseType: number, actionCode: number, tempSp: number = 0, stepTime: number = 0): number => {
  switch (phaseType) {
    case 1: // A1010 — Auto Batching Major (Fill from pipe: IBC/LS/MIS/RO)
      if ([10010, 10020, 10030, 10040].includes(actionCode)) return 2  // Start Program — auto batching
      if ([30010, 20040].includes(actionCode))               return 14 // Fill Minor — manual add
      return 2  // default: auto batching
    case 2: // A1020 — High Shear / Pre-blend
      return 14  // Fill Major Done — High Shear running
    case 3: // D1010 — Dissolve Tank 1
      if (actionCode === 20020) return 9   // Waiting First Confirm (กลั้วภาชนะ)
      return 18  // Preblending — dissolve active
    case 4: // D1030 — Dissolve Tank 2
      return 18  // First Confirm — secondary dissolve
    case 5: // x1010 — Heating Phase
      if (actionCode === 20050 || actionCode === 20020) return 14  // Fill Minor
      if (actionCode === 30500) {
        if (stepTime > 0)    return 18  // Fill Third — timed hold
        if (tempSp >= 83.0)  return 16  // Second Heat
        return 12                        // Pre Heats
      }
      if (actionCode === 30010) return tempSp >= 83.0 ? 16 : 12
      return 12  // default: Pre Heats
    case 6: // x1020 — Pasteurization
      return 20  // Pasteurizer
    case 7: // x1030 — Holding / Start Cooling
      if (actionCode === 30010)  return 22  // QC Confirm
      if (actionCode === 30600 || actionCode === 30020) return 24  // Ready To Transfer
      if (actionCode === 30500) return tempSp >= 83.0 ? 22 : 24
      return 22  // default: QC Confirm
    case 8: // x1040 — Final Cooling
      return 26  // Transferring
    default:
      return 0   // Stand By
  }
}

const route = useRoute()
const router = useRouter()

// ── PLC Connection via Shared MQTT Composable ──
const { connect, disconnect, publishMessage, isConnected: plcConnectedGlobal, plantsData, onMessage, offMessage } = useMQTT()

// ── SIM-Aware MQTT Topic Helper ─────────────────────────────────────────────
// In SIM mode (VITE_SIM_MODE=true), use VITE_PLANT{N}_CMD / sim/plant/{N}/...
// In Production mode, use the standard mixing/plant/{N}/... topics
// This prevents SIM frontend from writing to the real Production PLC.
const isSimMode = import.meta.env.VITE_SIM_MODE === 'true'

// Returns the correct MQTT topic prefix for a given plant ID
// e.g. simCmdTopic(1, 'step_cmd') → 'sim/plant/1/step_cmd'  (SIM)
//                                  → 'mixing/plant/1/step_cmd' (Prod)
const simCmdTopic = (plantId: string | number, suffix: string): string => {
    if (isSimMode) {
        // Use VITE_PLANT{N}_CMD if available, else fall back to sim/plant/{N}/...
        const envKey = `VITE_PLANT${plantId}_CMD` as keyof ImportMeta['env']
        const base = import.meta.env[envKey] || `sim/plant/${plantId}/step_cmd`
        // base = 'sim/plant/1/step_cmd' — replace last segment with suffix
        const baseParts = base.split('/')
        baseParts[baseParts.length - 1] = suffix
        return baseParts.join('/')
    }
    return `mixing/plant/${plantId}/${suffix}`
}
const { getAuthHeader, user, switchStationUser } = useAuth()

// ── Operator Scan State ─────────────────────────────────────────────────
// User 1: เท (Pour operator) — auto from login, scannable
const pourScanInput = ref('')

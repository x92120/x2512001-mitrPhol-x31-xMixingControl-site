<template>
  <div class="pour-hud-container" :class="{ 'dark-mode': isDark }">
    <!-- Top HUD Header -->
    <header class="hud-header">
      <div class="hud-brand">
        <span class="hud-badge">POUR STATION</span>
        <h1 class="hud-title">🫗 จุดเทส่วนผสม (Pour HUD)</h1>
      </div>

      <!-- Plant Selectors -->
      <div class="plant-tabs">
        <button 
          v-for="p in [1, 2, 3]" 
          :key="p"
          class="plant-btn"
          :class="{ 
            'plant-active': selectedPlant === p,
            'plant-has-batch': plantBatchStatus[p]
          }"
          @click="selectPlant(p)"
        >
          PLANT {{ p }}
          <span v-if="plantBatchStatus[p]" class="dot-running" title="มีแบทช์กำลังรัน">●</span>
        </button>
      </div>

      <div class="hud-status-group">
        <div v-if="batchInfo?.batch_id" class="batch-tag">
          <span class="tag-label">BATCH NO.</span>
          <span class="tag-val">{{ batchInfo.batch_id }}</span>
        </div>
        <div class="plc-state-badge" v-if="plcStateText">
          <span class="tag-label">PLC STATE</span>
          <span class="tag-val">{{ plcStateText }}</span>
        </div>
        <button class="theme-toggle-btn" @click="isDark = !isDark" :title="isDark ? 'Light Mode' : 'Dark Mode'">
          {{ isDark ? '☀️' : '🌙' }}
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="hud-main">
      <!-- Loading State -->
      <div v-if="loading && !batchInfo?.batch_id" class="hud-state-box">
        <div class="spinner"></div>
        <p>กำลังเชื่อมต่อระบบสถานีผสม Plant {{ selectedPlant }}...</p>
      </div>

      <!-- No Active Batch on selected plant -->
      <div v-else-if="!batchInfo?.batch_id" class="hud-state-box">
        <div class="idle-icon">⏳</div>
        <h2>Plant {{ selectedPlant }}: ยังไม่มีแบทช์ที่กำลังดำเนินการ</h2>
        <p>กรุณารอคนคุมเครื่องเริ่มแบทช์ หรือแตะเลือก Plant อื่นด้านบน</p>
        <div class="idle-plants-hint" v-if="anyPlantRunning">
          💡 พบแบทช์กำลังดำเนินการที่: 
          <button v-for="p in runningPlants" :key="p" class="hint-plant-btn" @click="selectPlant(p)">
            👉 สลับไปดู PLANT {{ p }}
          </button>
        </div>
      </div>

      <!-- Active Batch Content -->
      <div v-else class="hud-active-layout">
        <!-- Hero Summary Bar -->
        <div class="hero-bar" :class="isViewingPhaseDone ? 'hero-done' : 'hero-pending'">
          <div class="hero-left">
            <div class="sku-title">{{ batchInfo.sku_name || batchInfo.sku_id }}</div>
            <div class="sku-meta">
              <span class="meta-chip">SKU: {{ batchInfo.sku_id }}</span>
              <span class="meta-chip">แบทช์ขนาด: {{ batchInfo.batch_size || 1200 }} kg</span>
              <span class="meta-chip highlight-chip">Phase สดหน้างาน: {{ currentActivePhaseLabel }} (Step {{ currentPlcStepNo }})</span>
              <span class="meta-chip temp-chip" v-if="currentTemp !== null">🌡️ {{ currentTemp }}°C</span>
              <span class="meta-chip agitator-chip" v-if="currentAgitator !== null">🔄 {{ currentAgitator }} RPM</span>
            </div>
          </div>
          <div class="hero-right">
            <div class="progress-box">
              <div class="progress-numbers">
                <span class="scanned-num">{{ viewingPhaseScannedCount }}</span>
                <span class="total-num">/ {{ viewingPhaseIngredients.length }}</span>
              </div>
              <div class="progress-lbl">สแกนใน Phase {{ currentViewingPhaseLabel }}</div>
            </div>
          </div>
        </div>

        <!-- Live Banner Matching Main Screen -->
        <div class="live-status-banner" :class="isViewingPhaseDone ? 'banner-done' : 'banner-wait'">
          <span v-if="isViewingPhaseDone">🎉 PHASE {{ currentViewingPhaseLabel }} — สแกนครบทุกถุงใน Phase นี้เรียบร้อยแล้ว!</span>
          <span v-else>⚡ PHASE {{ currentViewingPhaseLabel }} — กำลังรอสแกนวัตถุดิบ (สามารถสแกนตัวไหนก่อน-หลังก็ได้)</span>
        </div>

        <!-- Phase Navigation Pills -->
        <div class="phase-pills-row">
          <button 
            v-for="ph in phasesList" 
            :key="ph.phase_no"
            class="phase-pill"
            :class="{
              'pill-selected': viewingPhaseNo === ph.phase_no,
              'pill-current-active': currentPlcPhaseNo === ph.phase_no,
              'pill-completed': ph.isDone
            }"
            @click="viewingPhaseNo = ph.phase_no"
          >
            <span class="pill-name">{{ ph.label }}</span>
            <span v-if="ph.isDone" class="pill-check">✓</span>
            <span v-else class="pill-count">({{ ph.items.length }})</span>
          </button>
        </div>

        <!-- Ingredients Checklist Grid -->
        <div class="checklist-container">
          <div class="section-banner">
            <span class="section-title">
              📋 รายการวัตถุดิบ (IND) สำหรับ: <strong>{{ currentViewingPhaseFullLabel }}</strong>
            </span>
            <button 
              v-if="viewingPhaseNo !== currentPlcPhaseNo" 
              class="jump-active-btn" 
              @click="viewingPhaseNo = currentPlcPhaseNo"
            >
              🎯 กลับไป Phase ปัจจุบัน ({{ currentActivePhaseLabel }})
            </button>
          </div>

          <div v-if="viewingPhaseIngredients.length === 0" class="no-ing-box">
            Phase นี้เป็นขั้นตอนอัตโนมัติ (เช่น ปั๊มน้ำ, Heat Up, หรือกวนผสม) ไม่มีวัตถุดิบต้องสแกนมือ
          </div>

          <div v-else class="ing-grid">
            <div 
              v-for="(item, idx) in viewingPhaseIngredients" 
              :key="item.seq || idx"
              class="ing-card"
              :class="{
                'card-done': item.isCompleted || item.isScanned,
                'card-pending': !item.isCompleted && !item.isScanned,
                'card-error': lastFaultItem === item.re_code
              }"
            >
              <div class="card-top">
                <span class="step-seq-tag">Step {{ item.sub_step || item.seq }}</span>
                <span v-if="item.isCompleted || item.isScanned" class="status-badge-ok">✓ ผ่านแล้ว</span>
                <span v-else class="status-badge-pending">⏳ รอสแกน</span>
              </div>

              <div class="card-body">
                <div class="ing-name">{{ item.re_code || item.description || 'วัตถุดิบ' }}</div>
                <div class="ing-sub-desc">{{ item.description || getActionDescription(item.action_code) }}</div>
                
                <div class="ing-details-table">
                  <div class="detail-row">
                    <span class="d-lbl">น้ำหนักเป้าหมาย:</span>
                    <span class="d-val font-bold text-primary">{{ item.target_weight > 0 ? `${item.target_weight.toFixed(2)} kg` : '-' }}</span>
                  </div>
                  <div class="detail-row" v-if="item.actual_value">
                    <span class="d-lbl">น้ำหนักจริงที่ชั่ง:</span>
                    <span class="d-val font-bold text-success">✓ {{ item.actual_value.toFixed(2) }} kg</span>
                  </div>
                  <div class="detail-row">
                    <span class="d-lbl">อุณหภูมิ / กวน:</span>
                    <span class="d-val">
                      {{ item.temp_sp ? `${item.temp_sp}°C` : '-' }} | {{ item.agitator_sp ? `${item.agitator_sp} rpm` : '-' }}
                    </span>
                  </div>
                  <div class="detail-row" v-if="item.scannedTime">
                    <span class="d-lbl">เวลาที่สแกน:</span>
                    <span class="d-val text-success font-mono">{{ item.scannedTime }}</span>
                  </div>
                </div>
              </div>

              <div class="card-footer">
                <div v-if="item.isCompleted || item.isScanned" class="footer-ok">
                  🟢 บันทึกข้อมูลและน้ำหนักเข้าระบบเรียบร้อย
                </div>
                <div v-else class="footer-wait">
                  👉 นำหัวอ่านบาร์โค้ดยิงที่ถุง/กระสอบนี้ได้ทันที
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Live Scan Fault Alert Modal/Banner -->
        <div v-if="lastErrorMsg" class="error-banner">
          <div class="err-icon">🚨</div>
          <div class="err-text">
            <strong>สแกนผิดพลาด:</strong> {{ lastErrorMsg }}
          </div>
          <button class="err-close" @click="lastErrorMsg = ''">✕</button>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="hud-footer">
      <div class="footer-status">
        <span class="live-dot"></span> เชื่อมต่อ Real-time MQTT + PLC Plant {{ selectedPlant }} (Auto-Sync ทุก 2 วินาที)
      </div>
      <div class="footer-actions">
        <button class="refresh-btn" @click="fetchData">🔄 รีเฟรช</button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useMQTT } from '~/composables/useMQTT'

const isDark = ref(true)
const loading = ref(true)
const selectedPlant = ref(2) // Default to Plant 2 (SPP)
const plantBatchStatus = ref<Record<number, boolean>>({ 1: false, 2: false, 3: false })

const batchInfo = ref<any>(null)
const rawSteps = ref<any[]>([])
const activeSeq = ref(1)
const totalSteps = ref(0)
const currentPlcPhaseNo = ref(16)
const currentPlcStepNo = ref(10)
const viewingPhaseNo = ref(16)

const dbStepLogs = ref<any[]>([])
const lastErrorMsg = ref('')
const lastFaultItem = ref('')
const localScannedKeys = ref<Record<string, { time: string }>>({})

// MQTT integration
const { plantsData, connect, onMessage } = useMQTT()
const plantMqttData = computed(() => (plantsData.value[String(selectedPlant.value)] || {}) as any)

// Watch MQTT Telemetry for Real-time Phase and Step updates!
watch(plantMqttData, (data) => {
  if (!data) return
  
  const rawPhase = data.Phase_ID || data.Phase_id || data.phase_id
  if (rawPhase) {
    const m = String(rawPhase).replace(/\0/g, '').trim().match(/^p(\d+)/i)
    if (m) {
      const pNum = parseInt(m[1], 10)
      if (pNum && currentPlcPhaseNo.value !== pNum) {
        currentPlcPhaseNo.value = pNum
        viewingPhaseNo.value = pNum
      }
    }
  }

  const stepVal = Number(data.Step_ID || data.Step_id || data.step_id || 0)
  if (stepVal > 0) {
    currentPlcStepNo.value = stepVal
  }
}, { deep: true })

const plcStateText = computed(() => {
  const st = plantMqttData.value?.PLC_State || plantMqttData.value?.State
  if (st === 24) return '24 -> Ready To Transfer'
  if (st === 1) return 'Running'
  if (st === 2) return 'Hold/Paused'
  return st ? `State ${st}` : ''
})

const currentTemp = computed(() => {
  const t = plantMqttData.value?.Mixing_Tank_Temperature || plantMqttData.value?.TEMP01
  return t ? Number(t).toFixed(1) : null
})

const currentAgitator = computed(() => {
  const a = plantMqttData.value?.MixingTank_Agitator_Speed
  return a ? Math.round(Number(a)) : null
})

// Dynamic API Base URL
const getApiBaseUrl = () => {
  return appConfig.apiBaseUrl
}

// Sound notifications
const playBeep = () => {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880
    gain.gain.value = 0.3
    osc.start()
    osc.stop(ctx.currentTime + 0.15)
  } catch (e) {}
}

const playAlarm = () => {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sawtooth'
    osc.frequency.value = 220
    gain.gain.value = 0.5
    osc.start()
    osc.stop(ctx.currentTime + 0.5)
  } catch (e) {}
}

const selectPlant = (p: number) => {
  selectedPlant.value = p
  loading.value = true
  fetchData()
}

const getActionDescription = (code: string) => {
  const map: Record<string, string> = {
    '10020': 'MIS Batching',
    '30500': 'Heats Up ต้มเพิ่มอุณหภูมิ',
    '30010': 'Manual add Ingredient to Mixing Tank เทส่วนผสมเข้าถังผสม',
    '20030': 'เขย่าผสมก่อน High Shear',
    '10010': 'RO Water Batching เติมน้ำ RO'
  }
  return map[String(code)] || 'ขั้นตอนการผลิต'
}

// Check all plants status
const checkAllPlants = async () => {
  const baseUrl = getApiBaseUrl()
  for (const p of [1, 2, 3]) {
    try {
      const res = await fetch(`${baseUrl}/plc/plant/${p}/recipe-status`)
      if (res.ok) {
        const d = await res.json()
        const hasBatch = !!(d?.target?.batch_id && d.target.batch_id !== '-' && d.target.batch_id !== '0')
        plantBatchStatus.value[p] = hasBatch
      }
    } catch (e) {}
  }
}

const anyPlantRunning = computed(() => Object.values(plantBatchStatus.value).some(Boolean))
const runningPlants = computed(() => [1, 2, 3].filter(p => plantBatchStatus.value[p]))

// Fetch active plant data & step logs
const fetchData = async () => {
  try {
    const baseUrl = getApiBaseUrl()
    const res = await fetch(`${baseUrl}/plc/plant/${selectedPlant.value}/recipe-status`)
    if (res.ok) {
      const d = await res.json()
      if (d.success && d.target?.batch_id) {
        const t = d.target
        const bId = t.batch_id
        batchInfo.value = {
          batch_id: bId,
          sku_id: t.sku_id,
          sku_name: t.sku_name || t.sku_id,
          batch_size: t.batch_size || 1200,
          total_steps: t.total_steps || 31
        }
        totalSteps.value = t.total_steps || 31
        rawSteps.value = t.steps || []

        // Fetch completed DB step logs
        try {
          const logsRes = await fetch(`${baseUrl}/production-batches/${bId}/logs`)
          if (logsRes.ok) {
            const logsData = await logsRes.json()
            dbStepLogs.value = logsData.logs || []
          }
        } catch (logErr) {
          console.warn('[Logs Fetch Error]', logErr)
        }

        // Auto determine active phase from logs or MQTT
        const mqttPhase = plantMqttData.value?.Phase_ID || plantMqttData.value?.Phase_id || plantMqttData.value?.phase_id
        if (mqttPhase) {
          const m = String(mqttPhase).replace(/\0/g, '').trim().match(/^p(\d+)/i)
          if (m) {
            const pNum = parseInt(m[1], 10)
            if (pNum) {
              currentPlcPhaseNo.value = pNum
              if (!viewingPhaseNo.value || viewingPhaseNo.value === 10) {
                viewingPhaseNo.value = pNum
              }
            }
          }
        } else if (dbStepLogs.value.length > 0) {
          // Get the latest log phase
          const lastLog = dbStepLogs.value[dbStepLogs.value.length - 1]
          const m = String(lastLog.phase_id).match(/^p(\d+)/i)
          if (m) {
            const pNum = parseInt(m[1], 10)
            currentPlcPhaseNo.value = pNum
            if (!viewingPhaseNo.value || viewingPhaseNo.value === 10) {
              viewingPhaseNo.value = pNum
            }
          }
        } else {
          currentPlcPhaseNo.value = 16
          viewingPhaseNo.value = 16
        }
      } else {
        batchInfo.value = null
      }
    }
  } catch (err) {
    console.warn('[PourHUD Error]', err)
  } finally {
    loading.value = false
  }
}

// Group raw steps into Phases and merge with DB Step Logs
const phasesList = computed(() => {
  if (!rawSteps.value || rawSteps.value.length === 0) return []
  const groups: Record<number, { phase_no: number; label: string; items: any[]; isDone: boolean }> = {}

  rawSteps.value.forEach(s => {
    const pNo = s.phase_no || 0
    if (!groups[pNo]) {
      const pId = s.phase_id || `Phase ${pNo}`
      groups[pNo] = {
        phase_no: pNo,
        label: `p0${pNo} (${pId})`,
        items: [],
        isDone: false
      }
    }

    // Check if step is completed in DB step logs
    const normP = `p0${pNo}`
    const matchingLog = dbStepLogs.value.find(l => {
      const lPhase = String(l.phase_id || '').toLowerCase()
      const isPhaseMatch = lPhase === normP.toLowerCase() || lPhase.includes(String(pNo))
      const isSubMatch = Number(l.sub_step || 0) === Number(s.sub_step || s.seq || 0)
      return isPhaseMatch && isSubMatch
    })

    const isCompleted = !!matchingLog || !!localScannedKeys.value[s.re_code] || s.action_code === '10020'
    const actualVal = matchingLog?.actual_value ?? (isCompleted ? s.target_weight : null)
    const scannedTs = matchingLog?.completed_at ? new Date(matchingLog.completed_at).toLocaleTimeString('th-TH') : (localScannedKeys.value[s.re_code]?.time || '')

    groups[pNo].items.push({
      ...s,
      isCompleted,
      actual_value: actualVal,
      scannedTime: scannedTs
    })
  })

  // Mark phase done if all items done
  Object.values(groups).forEach(g => {
    g.isDone = g.items.every(i => i.isCompleted)
  })

  return Object.values(groups)
})

const currentActivePhaseLabel = computed(() => {
  return `p0${currentPlcPhaseNo.value}`
})

const currentViewingPhaseLabel = computed(() => {
  return `p0${viewingPhaseNo.value}`
})

const currentViewingPhaseFullLabel = computed(() => {
  const p = phasesList.value.find(ph => ph.phase_no === viewingPhaseNo.value)
  return p ? p.label : `p0${viewingPhaseNo.value}`
})

const viewingPhaseIngredients = computed(() => {
  const p = phasesList.value.find(ph => ph.phase_no === viewingPhaseNo.value)
  if (!p) return []
  return p.items.filter(i => i.re_code || i.action_code === '30010' || i.action_code === '20030')
})

const viewingPhaseScannedCount = computed(() => {
  return viewingPhaseIngredients.value.filter(i => i.isCompleted || i.isScanned).length
})

const isViewingPhaseDone = computed(() => {
  return viewingPhaseIngredients.value.length > 0 && viewingPhaseScannedCount.value >= viewingPhaseIngredients.value.length
})

// Barcode Scanning Engine
let scanBuffer = ''
let lastKeypress = 0

const onKeyDown = (e: KeyboardEvent) => {
  const isEnter = e.key === 'Enter' || e.key === 'Tab' || e.code === 'Enter'
  const now = Date.now()

  if (now - lastKeypress > 150) {
    scanBuffer = ''
  }
  lastKeypress = now

  if (isEnter) {
    e.preventDefault()
    const code = scanBuffer.trim()
    scanBuffer = ''
    if (code && code.length >= 3) {
      handleScannedBarcode(code)
    }
  } else if (e.key && e.key.length === 1) {
    scanBuffer += e.key
  }
}

const handleScannedBarcode = (code: string) => {
  const norm = code.toLowerCase().replace(/[^a-z0-9]/g, '')
  console.log('[PourHUD Barcode Scanned]', code, norm)

  let matched = false
  for (const item of viewingPhaseIngredients.value) {
    const itemRe = (item.re_code || '').toLowerCase().replace(/[^a-z0-9]/g, '')
    if (itemRe && (norm.includes(itemRe) || itemRe.includes(norm))) {
      matched = true
      localScannedKeys.value[item.re_code] = {
        time: new Date().toLocaleTimeString('th-TH')
      }
      item.isCompleted = true
      playBeep()
      lastErrorMsg.value = ''
      lastFaultItem.value = ''
      break
    }
  }

  if (!matched) {
    playAlarm()
    lastErrorMsg.value = `บาร์โค้ด "${code}" ไม่ตรงกับรายการใน Phase ${currentViewingPhaseLabel.value}!`
    lastFaultItem.value = code
  }
}

let pollInterval: any = null

onMounted(async () => {
  connect()
  await checkAllPlants()
  // Default to Plant 2 if active
  if (plantBatchStatus.value[2]) {
    selectedPlant.value = 2
  }
  await fetchData()

  pollInterval = setInterval(() => {
    checkAllPlants()
    fetchData()
  }, 2000)

  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
.pour-hud-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f1f5f9;
  color: #0f172a;
  font-family: 'Prompt', 'Inter', -apple-system, sans-serif;
  user-select: none;
}
.pour-hud-container.dark-mode {
  background: #090d16;
  color: #f8fafc;
}

/* Header */
.hud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 18px;
  background: #ffffff;
  border-bottom: 2px solid #e2e8f0;
}
.dark-mode .hud-header {
  background: #111827;
  border-bottom: 2px solid #1e293b;
}
.hud-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hud-badge {
  background: #1e40af;
  color: #ffffff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
}
.hud-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}

/* Plant Selector Tabs */
.plant-tabs {
  display: flex;
  gap: 6px;
}
.plant-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: all 0.15s ease;
}
.dark-mode .plant-btn {
  background: #1e293b;
  border-color: #334155;
  color: #94a3b8;
}
.plant-btn.plant-active {
  background: #2563eb !important;
  color: #ffffff !important;
  border-color: #1d4ed8 !important;
  box-shadow: 0 2px 6px rgba(37,99,235,0.3);
}
.dot-running {
  color: #22c55e;
  font-size: 10px;
}

.hud-status-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.batch-tag, .plc-state-badge {
  display: flex;
  flex-direction: column;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  padding: 3px 8px;
  border-radius: 5px;
}
.dark-mode .batch-tag, .dark-mode .plc-state-badge {
  background: #1e293b;
  border-color: #3b82f6;
}
.tag-label {
  font-size: 8px;
  font-weight: 700;
  color: #64748b;
}
.tag-val {
  font-size: 12px;
  font-weight: 800;
  color: #1e40af;
}
.dark-mode .tag-val {
  color: #60a5fa;
}
.theme-toggle-btn {
  background: none;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
}

/* Main */
.hud-main {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

/* State Boxes */
.hud-state-box {
  margin: auto;
  text-align: center;
  padding: 30px;
}
.idle-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.idle-plants-hint {
  margin-top: 20px;
  padding: 12px 18px;
  background: #eff6ff;
  border: 1px dashed #3b82f6;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.dark-mode .idle-plants-hint {
  background: #1e293b;
}
.hint-plant-btn {
  background: #2563eb;
  color: #fff;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-weight: 700;
  cursor: pointer;
}

/* Hero Bar */
.hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-radius: 10px;
  border: 2px solid;
  margin-bottom: 10px;
}
.hero-pending {
  background: #ffffff;
  border-color: #3b82f6;
}
.dark-mode .hero-pending {
  background: #111827;
  border-color: #2563eb;
}
.hero-done {
  background: #f0fdf4;
  border-color: #22c55e;
}
.dark-mode .hero-done {
  background: #052e16;
  border-color: #16a34a;
}
.sku-title {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 4px;
}
.sku-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.meta-chip {
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #475569;
}
.dark-mode .meta-chip {
  background: #1e293b;
  color: #cbd5e1;
}
.highlight-chip {
  background: #dbeafe !important;
  color: #1e40af !important;
  font-weight: 700;
}
.dark-mode .highlight-chip {
  background: #1e3a8a !important;
  color: #93c5fd !important;
}
.temp-chip {
  background: #fef3c7 !important;
  color: #b45309 !important;
  font-weight: 700;
}
.agitator-chip {
  background: #e0f2fe !important;
  color: #0369a1 !important;
  font-weight: 700;
}

.progress-box {
  text-align: right;
}
.progress-numbers {
  font-size: 26px;
  font-weight: 900;
  line-height: 1;
}
.scanned-num {
  color: #22c55e;
}
.total-num {
  font-size: 16px;
  color: #64748b;
}
.progress-lbl {
  font-size: 10px;
  color: #64748b;
  font-weight: 600;
}

/* Live Status Banner */
.live-status-banner {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}
.banner-done {
  background: #15803d;
  color: #ffffff;
}
.banner-wait {
  background: #1e40af;
  color: #ffffff;
}

/* Phase Pills */
.phase-pills-row {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 6px;
  margin-bottom: 12px;
}
.phase-pill {
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}
.dark-mode .phase-pill {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}
.phase-pill.pill-selected {
  border-color: #2563eb !important;
  background: #eff6ff !important;
  color: #1d4ed8 !important;
}
.dark-mode .phase-pill.pill-selected {
  background: #1e3a8a !important;
  color: #93c5fd !important;
}
.phase-pill.pill-current-active {
  box-shadow: 0 0 0 2px #22c55e;
}
.phase-pill.pill-completed {
  border-color: #22c55e !important;
  color: #16a34a !important;
}
.pill-check {
  color: #22c55e;
  font-weight: 900;
}

/* Checklist Section */
.checklist-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.section-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.section-title {
  font-size: 14px;
  font-weight: 700;
}
.jump-active-btn {
  background: #2563eb;
  color: #ffffff;
  border: none;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

/* Ingredients Grid */
.ing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
.ing-card {
  border: 2px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.dark-mode .ing-card {
  background: #111827;
  border-color: #1f2937;
}
.card-done {
  border-color: #22c55e !important;
  background: #f0fdf4 !important;
}
.dark-mode .card-done {
  background: #052e16 !important;
  border-color: #15803d !important;
}
.card-pending {
  border-color: #f59e0b !important;
}
.card-error {
  border-color: #ef4444 !important;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.step-seq-tag {
  background: #f1f5f9;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  color: #475569;
}
.dark-mode .step-seq-tag {
  background: #1e293b;
  color: #94a3b8;
}
.status-badge-ok {
  background: #22c55e;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 10px;
}
.status-badge-pending {
  background: #f59e0b;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 10px;
}

.ing-name {
  font-size: 16px;
  font-weight: 800;
  margin-bottom: 2px;
}
.ing-sub-desc {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 8px;
}
.ing-details-table {
  background: rgba(0,0,0,0.03);
  padding: 6px 8px;
  border-radius: 6px;
}
.dark-mode .ing-details-table {
  background: rgba(255,255,255,0.04);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding: 2px 0;
}
.d-lbl {
  color: #64748b;
}
.d-val {
  font-weight: 600;
}
.text-primary {
  color: #2563eb;
}
.dark-mode .text-primary {
  color: #60a5fa;
}
.text-success {
  color: #16a34a;
}

.card-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
  font-size: 10.5px;
  font-weight: 600;
}
.dark-mode .card-footer {
  border-top-color: #1f2937;
}
.footer-ok {
  color: #16a34a;
}
.footer-wait {
  color: #d97706;
}

/* Error Banner */
.error-banner {
  position: fixed;
  bottom: 50px;
  left: 20px;
  right: 20px;
  background: #fee2e2;
  border: 2px solid #ef4444;
  color: #991b1b;
  padding: 12px 18px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  z-index: 100;
}
.dark-mode .error-banner {
  background: #450a0a;
  color: #fecaca;
}
.err-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  margin-left: auto;
  color: inherit;
}

/* Footer */
.hud-footer {
  padding: 8px 18px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #64748b;
}
.dark-mode .hud-footer {
  background: #111827;
  border-top-color: #1f2937;
}
.live-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #22c55e;
  border-radius: 50%;
  margin-right: 4px;
}
.refresh-btn {
  background: none;
  border: 1px solid #cbd5e1;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}
</style>

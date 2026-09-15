<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useAuth } from '~/composables/useAuth'
import { useI18n } from '~/composables/useI18n'
import { useQuasar } from 'quasar'

const { hasPermission, user, logout, switchStationUser } = useAuth()
const { t, toggleLocale, localeFlag, localeName, isThai } = useI18n()
const $q = useQuasar()
const appConfig = useAppConfig()
const apiBase = appConfig.apiBaseUrl || 'http://192.168.121.23:8031'

// Zoom control
const ZOOM_KEY = 'app-zoom-level'
const zoomLevel = ref(1.0)

const applyZoom = () => {
  if (import.meta.client) {
    document.documentElement.style.zoom = String(zoomLevel.value)
    localStorage.setItem(ZOOM_KEY, String(zoomLevel.value))
  }
}

const zoomOptions = [
  { label: '80%', value: 0.8 },
  { label: '90%', value: 0.9 },
  { label: '100%', value: 1.0 },
  { label: '110%', value: 1.1 },
  { label: '120%', value: 1.2 },
  { label: '130%', value: 1.3 },
  { label: '140%', value: 1.4 },
  { label: '150%', value: 1.5 },
  { label: '160%', value: 1.6 },
  { label: '170%', value: 1.7 },
  { label: '180%', value: 1.8 },
  { label: '190%', value: 1.9 },
  { label: '200%', value: 2.0 },
]

watch(zoomLevel, applyZoom)

// ─────────────────────────────────────────────────────────────────────────────
// ⏰ Auto Shift-Cutoff Watcher & QR Badge Dialog
// ─────────────────────────────────────────────────────────────────────────────
const showShiftCutoffDialog = ref(false)
const cutoffShiftName = ref('')
const cutoffNextShiftName = ref('')
const cutoffQrInput = ref('')
const cutoffQrLoading = ref(false)
const cutoffQrInputRef = ref<any>(null)
let shiftCheckInterval: any = null
let lastWarnedShiftCutoff = ''

const checkShiftCutoff = () => {
  if (!import.meta.client) return
  const now = new Date()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  const seconds = now.getSeconds()
  const day = now.getDay() // 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat

  // Schedule Rules:
  // Mon - Thu (day: 1, 2, 3, 4): 3 shifts -> Cutoffs at 06:00, 14:00, 22:00
  // Fri - Sun (day: 5, 6, 0): 2 shifts -> Cutoffs at 06:00, 18:00

  const isWeekday = day >= 1 && day <= 4

  let isCutoffTriggered = false
  let isNearCutoffTriggered = false
  let endedShiftLabel = ''
  let nextShiftLabel = ''

  if (isWeekday) {
    // 3 Shifts Schedule (Mon - Thu)
    // Cutoff 1: 06:00 (Night -> Morning)
    if (hours === 6 && minutes === 0 && seconds <= 40) {
      isCutoffTriggered = true
      endedShiftLabel = isThai.value ? 'กะดึก (22:00 - 06:00)' : 'Night Shift (22:00 - 06:00)'
      nextShiftLabel = isThai.value ? 'กะเช้า (06:00 - 14:00)' : 'Morning Shift (06:00 - 14:00)'
    }
    // Cutoff 2: 14:00 (Morning -> Afternoon)
    else if (hours === 14 && minutes === 0 && seconds <= 40) {
      isCutoffTriggered = true
      endedShiftLabel = isThai.value ? 'กะเช้า (06:00 - 14:00)' : 'Morning Shift (06:00 - 14:00)'
      nextShiftLabel = isThai.value ? 'กะบ่าย (14:00 - 22:00)' : 'Afternoon Shift (14:00 - 22:00)'
    }
    // Cutoff 3: 22:00 (Afternoon -> Night)
    else if (hours === 22 && minutes === 0 && seconds <= 40) {
      isCutoffTriggered = true
      endedShiftLabel = isThai.value ? 'กะบ่าย (14:00 - 22:00)' : 'Afternoon Shift (14:00 - 22:00)'
      nextShiftLabel = isThai.value ? 'กะดึก (22:00 - 06:00)' : 'Night Shift (22:00 - 06:00)'
    }

    // 5-minute warnings: 05:55, 13:55, 21:55
    if ((hours === 5 && minutes >= 55) || (hours === 13 && minutes >= 55) || (hours === 21 && minutes >= 55)) {
      isNearCutoffTriggered = true
    }
  } else {
    // 2 Shifts Schedule (Fri - Sun: day 5, 6, 0)
    // Cutoff 1: 06:00 (Night -> Morning)
    if (hours === 6 && minutes === 0 && seconds <= 40) {
      isCutoffTriggered = true
      endedShiftLabel = day === 5
        ? (isThai.value ? 'กะดึก (22:00 - 06:00)' : 'Night Shift (22:00 - 06:00)') // Thu night ended
        : (isThai.value ? 'กะดึก (18:00 - 06:00)' : 'Night Shift (18:00 - 06:00)')
      nextShiftLabel = isThai.value ? 'กะเช้า (06:00 - 18:00)' : 'Morning Shift (06:00 - 18:00)'
    }
    // Cutoff 2: 18:00 (Morning -> Night)
    else if (hours === 18 && minutes === 0 && seconds <= 40) {
      isCutoffTriggered = true
      endedShiftLabel = isThai.value ? 'กะเช้า (06:00 - 18:00)' : 'Morning Shift (06:00 - 18:00)'
      nextShiftLabel = isThai.value ? 'กะดึก (18:00 - 06:00)' : 'Night Shift (18:00 - 06:00)'
    }

    // 5-minute warnings: 05:55, 17:55
    if ((hours === 5 && minutes >= 55) || (hours === 17 && minutes >= 55)) {
      isNearCutoffTriggered = true
    }
  }

  // 5-minute warning notification
  if (isNearCutoffTriggered && lastWarnedShiftCutoff !== `${hours}:${minutes}`) {
    lastWarnedShiftCutoff = `${hours}:${minutes}`
    $q.notify({
      type: 'warning',
      message: isThai.value ? '⏰ อีก 5 นาทีจะหมดเวลากะการทำงาน กรุณาสรุปและส่งมอบ E-Logbook' : '⏰ Shift ends in 5 minutes. Please complete and submit the E-Logbook handover.',
      position: 'top',
      timeout: 6000
    })
  }

  // Show Shift Cutoff Dialog
  if (isCutoffTriggered && !showShiftCutoffDialog.value) {
    cutoffShiftName.value = endedShiftLabel
    cutoffNextShiftName.value = nextShiftLabel
    showShiftCutoffDialog.value = true
    setTimeout(() => {
      if (cutoffQrInputRef.value) cutoffQrInputRef.value.focus()
    }, 300)
  }
}

// Zero-Click auto-scan debounce watcher (150ms for hardware USB/Bluetooth RFID/QR scanner)
let _cutoffDebounce: any = null
watch(cutoffQrInput, (val) => {
  if (!val) return
  if (_cutoffDebounce) clearTimeout(_cutoffDebounce)
  _cutoffDebounce = setTimeout(() => {
    if (cutoffQrInput.value.trim()) handleCutoffQrScan()
  }, 150)
})

watch(showShiftCutoffDialog, (isOpen) => {
  if (isOpen) {
    cutoffQrInput.value = ''
    setTimeout(() => {
      if (cutoffQrInputRef.value) cutoffQrInputRef.value.focus()
    }, 300)
  }
})

// Global window keypress listener for Zero-Click Scanner when Cutoff Dialog is active
const handleGlobalScanKey = (e: KeyboardEvent) => {
  if (!showShiftCutoffDialog.value) return
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
  // If user scanned while focus was on background, auto-focus scanner input
  if (cutoffQrInputRef.value) {
    cutoffQrInputRef.value.focus()
  }
}

const handleCutoffQrScan = async () => {
  const rawCode = cutoffQrInput.value.trim()
  if (!rawCode) return
  cutoffQrLoading.value = true
  const badge_code = rawCode.startsWith('@') ? rawCode.substring(1).trim() : rawCode
  try {
    const res = await $fetch<any>(`${apiBase}/auth/badge-login`, {
      method: 'POST',
      body: { badge_code, username: badge_code }
    })
    if (res?.user) {
      switchStationUser(res.user)
      $q.notify({
        type: 'positive',
        message: isThai.value ? `✅ เข้าสู่ระบบกะใหม่สำเร็จ: ยินดีต้อนรับคุณ ${res.user.full_name || res.user.username}` : `✅ Shift login successful: Welcome ${res.user.full_name || res.user.username}`,
        position: 'top'
      })
      showShiftCutoffDialog.value = false
      cutoffQrInput.value = ''
    }
  } catch (err: any) {
    $q.notify({
      type: 'negative',
      message: (isThai.value ? 'รหัส QR Badge ไม่ถูกต้อง: ' : 'Invalid QR Badge: ') + (err.message || ''),
      position: 'top'
    })
  } finally {
    cutoffQrLoading.value = false
  }
}

const goToShiftLogbook = () => {
  showShiftCutoffDialog.value = false
  navigateTo('/x78-ShiftLogbook')
}

onMounted(() => {
  const stored = localStorage.getItem(ZOOM_KEY)
  if (stored) {
    zoomLevel.value = parseFloat(stored)
  } else {
    applyZoom()
  }

  // Start shift check interval every 20s
  shiftCheckInterval = setInterval(checkShiftCutoff, 20000)

  // Attach global zero-click scan listener
  if (import.meta.client) {
    window.addEventListener('keydown', handleGlobalScanKey)
  }
})

onUnmounted(() => {
  if (shiftCheckInterval) clearInterval(shiftCheckInterval)
  if (import.meta.client) {
    window.removeEventListener('keydown', handleGlobalScanKey)
  }
})

const handleLogout = async () => {
  showShiftCutoffDialog.value = false
  await logout()
  $q.notify({
    type: 'info',
    message: t('nav.loggedOut'),
    position: 'top',
  })
  navigateTo('/x80-UserLogin')
}

const printScreen = () => {
  window.print()
}

const goToPlant = (plant: number) => {
  window.location.href = `/x61-MixingControl?plant=${plant}`
}

</script>

<template>
  <q-layout view="hHh lpR fFf" class="bg-grey-2">
    <q-header elevated class="bg-primary text-white" height-hint="98">
      <q-toolbar>
        <q-toolbar-title>
          <div class="row items-center q-gutter-sm">
            <img src="/x_logo-192.png" alt="xMixing" style="height: 38px; display: block;" />
          </div>
        </q-toolbar-title>

        <!-- Zoom Control -->
        <div class="row items-center q-mr-md gt-xs" style="min-width: 180px;">
          <q-icon name="zoom_out" size="xs" class="q-mr-xs" />
          <q-slider v-model="zoomLevel" :min="0.8" :max="2.0" :step="0.1" color="white" dense style="flex: 1;" />
          <q-icon name="zoom_in" size="xs" class="q-mx-xs" />
          <q-select
            v-model="zoomLevel"
            :options="zoomOptions"
            emit-value
            map-options
            dense dark borderless
            style="min-width: 60px;"
          />
        </div>

        <!-- Print Screen -->
        <q-btn flat round dense icon="print" @click="printScreen" class="q-mr-sm">
          <q-tooltip>Print Screen</q-tooltip>
        </q-btn>

        <!-- Language Toggle -->
        <q-btn flat round dense @click="toggleLocale" class="q-mr-sm">
          <span style="font-size: 26px">{{ localeFlag }}</span>
        </q-btn>

        <!-- Login / Logout -->
        <template v-if="user">
          <q-chip dark dense color="white" text-color="primary" icon="person" class="q-mr-xs">
            {{ user.full_name || user.username }}
          </q-chip>
          <q-btn flat round dense icon="logout" @click="handleLogout">
            <q-tooltip>{{ t('nav.logout') }}</q-tooltip>
          </q-btn>
        </template>
        <q-btn v-else flat round dense icon="login" @click="navigateTo('/x80-UserLogin')">
          <q-tooltip>{{ t('nav.login') }}</q-tooltip>
        </q-btn>
      </q-toolbar>

      <q-tabs align="left" dense active-color="amber-3" indicator-color="amber-3">
        <q-route-tab to="/" icon="home" :label="t('nav.home')" />

        <q-route-tab
          to="/x55-ProductionPlan"
          icon="calendar_month"
          :label="t('nav.productionPlan')"
          v-if="hasPermission('production_list')"
        />

        <q-route-tab
          to="/x56-SkuView"
          icon="science"
          :label="t('nav.sku')"
          v-if="hasPermission('production_list')"
        />

        <q-route-tab
          to="/x60-CheckForProduction"
          icon="fact_check"
          :label="t('nav.checkForProduction')"
          v-if="hasPermission('production_list')"
        />

        <q-btn-dropdown
          flat
          no-caps
          stretch
          icon="precision_manufacturing"
          :label="t('nav.mixingControl')"
          v-if="hasPermission('production_list')"
          class="q-tab__label"
        >
          <q-list dense style="min-width: 180px;">
            <q-item clickable v-close-popup @click="goToPlant(1)">
              <q-item-section avatar><q-icon name="looks_one" color="blue-7" /></q-item-section>
              <q-item-section>Mixing 1</q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="goToPlant(2)">
              <q-item-section avatar><q-icon name="looks_two" color="teal-7" /></q-item-section>
              <q-item-section>Mixing 2</q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="goToPlant(3)">
              <q-item-section avatar><q-icon name="looks_3" color="deep-purple-7" /></q-item-section>
              <q-item-section>Mixing 3</q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        
        <!-- 📋 E-Logbook & Shift Handover Tab -->
        <q-route-tab to="/x78-ShiftLogbook" icon="assignment" label="E-Logbook" />

        <q-route-tab to="/x89-UserConfig" icon="manage_accounts" :label="t('nav.user')" v-if="hasPermission('admin')" />
        <q-route-tab to="/x100-PlantMonitor" icon="monitor" :label="t('nav.plantMonitor')" />
        <q-route-tab to="/x70-ProductionReport" icon="assessment" :label="t('nav.productionReport')" />
        <q-route-tab to="/x71-MixingReport" icon="description" :label="t('nav.mixingReport')" />
        <q-route-tab to="/x99-About" icon="info" :label="t('nav.about')" />
      </q-tabs>
    </q-header>

    <q-page-container>
      <NuxtPage />
    </q-page-container>

    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- ⏰ Auto Shift-Cutoff & Fast QR Badge Login Modal -->
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <q-dialog v-model="showShiftCutoffDialog" persistent>
      <q-card style="min-width: 440px; border-radius: 18px; overflow: hidden; background: #0f172a; color: white; border: 2px solid #eab308; box-shadow: 0 10px 40px rgba(0,0,0,0.8);">
        <q-card-section class="bg-amber-9 text-dark text-center q-py-md">
          <q-icon name="alarm_on" size="48px" class="q-mb-xs" />
          <div class="text-h5 text-weight-bolder">{{ isThai ? "หมดเวลากะการทำงาน (Shift Cutoff)" : "Shift Cutoff Reached" }}</div>
          <div class="text-caption text-weight-bold opacity-90 q-mt-xs">
            {{ isThai ? "สิ้นสุดรอบ:" : "Ended:" }} {{ cutoffShiftName }} ➔ {{ isThai ? "เริ่มรอบ:" : "Starting:" }} {{ cutoffNextShiftName }}
          </div>
        </q-card-section>

        <q-card-section class="q-pa-lg text-center">
          <div class="text-body2 text-grey-3 q-mb-md">
            {{ isThai ? "กรุณาทำการส่งมอบงานใน E-Logbook หรือให้ Operator กะใหม่สแกน QR Badge เพื่อเริ่มงานกะถัดไป" : "Please hand over duties in E-Logbook or have the next shift operator scan their QR Badge to begin." }}
          </div>

          <!-- QR Badge Fast Scan Box -->
          <div class="badge-scan-box q-pa-md q-mb-lg text-left" style="background: rgba(126, 87, 194, 0.2); border: 2px solid #a855f7; border-radius: 12px;">
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-subtitle2 text-weight-bold text-purple-2">{{ isThai ? "⚡ สแกน QR Badge กะใหม่ทันที" : "⚡ Scan Next Shift QR Badge" }}</span>
              <q-badge color="deep-purple-6">Ready to Scan</q-badge>
            </div>
            <q-input
              ref="cutoffQrInputRef"
              v-model="cutoffQrInput"
              outlined dense dark
              placeholder="Waiting for RFID/QR Scan..."
              bg-color="grey-10"
              class="q-mt-xs"
              :loading="cutoffQrLoading"
              @keyup.enter="handleCutoffQrScan"
            >
              <template v-slot:prepend><q-icon name="qr_code_scanner" color="purple-3" /></template>
            </q-input>
          </div>

          <div class="row q-gutter-sm">
            <q-btn
              class="col"
              unelevated
              color="amber-8"
              text-color="dark"
              icon="menu_book"
              :label="isThai ? 'เปิด E-Logbook ส่งมอบงาน' : 'Open E-Logbook Handover'"
              @click="goToShiftLogbook"
            />
            <q-btn
              class="col-auto"
              flat
              color="red-4"
              icon="logout"
              label="Logout"
              @click="handleLogout"
            />
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

  </q-layout>
</template>

<style>
/* Smooth scrolling */
html, body {
  min-height: 100vh;
  margin: 0;
  padding: 0;
}
</style>

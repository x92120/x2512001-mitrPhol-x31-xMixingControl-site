<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import { useI18n } from '~/composables/useI18n'

const router = useRouter()
const route = useRoute()
const $q = useQuasar()
const { login: authLogin } = useAuth()
const { t } = useI18n()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')

// ── Badge QR Auto-Scan Login ──────────────────────────────────────────────
const badgeScanInput = ref('')
const badgeInputRef = ref<any>(null)
let _badgeDebounce: ReturnType<typeof setTimeout> | null = null

// Auto-submit badge scan when scanner types directly into focused field
watch(badgeScanInput, (val) => {
  if (!val) return
  if (_badgeDebounce) clearTimeout(_badgeDebounce)
  _badgeDebounce = setTimeout(() => {
    if (badgeScanInput.value.trim()) onBadgeScanSubmit()
  }, 120)
})

const focusBadgeScanner = () => {
  if (!import.meta.client) return
  nextTick(() => {
    const inputEl = badgeInputRef.value?.$el?.querySelector('input') || badgeInputRef.value
    inputEl?.focus?.()
  })
}

// ── Universal Zero-Click Barcode Scanner Capture Engine ────────────────────────
let globalScannerBuffer = ''
let lastScanKeyTime = 0
let _scannerBurstTimer: ReturnType<typeof setTimeout> | null = null

// Physical key to ASCII mapper: Hardware scan codes (e.code) - Immune to Thai keyboard layout!
const physicalKeyToAscii = (e: KeyboardEvent): string => {
  const s = e.shiftKey
  const c = e.code

  // Digit row: 0-9 and shifted symbols (@, #, $, etc.)
  if (c.startsWith('Digit')) {
    const d = c.slice(5)
    const shiftDigits = ')!@#$%^&*('
    return s ? (shiftDigits[parseInt(d, 10)] ?? d) : d
  }
  // Letter keys: always produce Latin a-z / A-Z
  if (c.startsWith('Key')) {
    const letter = c.slice(3)
    return s ? letter.toUpperCase() : letter.toLowerCase()
  }
  // Numpad keys
  if (c.startsWith('Numpad')) {
    const numMap: Record<string, string> = {
      Numpad0: '0', Numpad1: '1', Numpad2: '2', Numpad3: '3', Numpad4: '4',
      Numpad5: '5', Numpad6: '6', Numpad7: '7', Numpad8: '8', Numpad9: '9',
      NumpadDecimal: '.', NumpadDivide: '/', NumpadMultiply: '*',
      NumpadSubtract: '-', NumpadAdd: '+'
    }
    return numMap[c] ?? ''
  }
  // Punctuation & JSON symbols
  const puncMap: Record<string, [string, string]> = {
    BracketLeft:  ['[', '{'],
    BracketRight: [']', '}'],
    Quote:        ["'", '"'],
    Semicolon:    [';', ':'],
    Comma:        [',', '<'],
    Period:       ['.', '>'],
    Slash:        ['/', '?'],
    Minus:        ['-', '_'],
    Equal:        ['=', '+'],
    Backslash:    ['\\', '|'],
    Backquote:    ['`', '~'],
    Space:        [' ', ' ']
  }
  if (puncMap[c]) {
    return s ? puncMap[c][1] : puncMap[c][0]
  }
  
  // Direct ASCII fallback
  if (e.key && e.key.length === 1 && e.key.charCodeAt(0) >= 32 && e.key.charCodeAt(0) <= 126) {
    return e.key
  }
  return ''
}

const handleGlobalScanKeydown = (e: KeyboardEvent) => {
  // Ignore browser shortcuts
  if (e.ctrlKey || e.altKey || e.metaKey) return

  const isEnter = e.key === 'Enter' || e.key === 'Tab' || e.code === 'Enter' || e.code === 'NumpadEnter'
  if (e.key.length > 1 && !isEnter) return

  const now = Date.now()
  const delta = now - lastScanKeyTime
  lastScanKeyTime = now

  // Barcode scanners type with < 60ms between characters. If pause > 150ms, start fresh buffer.
  if (delta > 150) {
    globalScannerBuffer = ''
  }

  const activeEl = typeof document !== 'undefined' ? (document.activeElement as HTMLElement) : null
  const mainInputEl = badgeInputRef.value?.$el?.querySelector('input')
  const isManualAuthField = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA') && activeEl !== mainInputEl

  if (isEnter) {
    if (_scannerBurstTimer) { clearTimeout(_scannerBurstTimer); _scannerBurstTimer = null }

    // If user is manually typing in username/password field and buffer is short, allow manual form submission
    if (isManualAuthField && globalScannerBuffer.length < 3 && !globalScannerBuffer.startsWith('@')) {
      return
    }

    const codeToProcess = (globalScannerBuffer.trim() || badgeScanInput.value.trim())
    if (codeToProcess && codeToProcess.length >= 2) {
      e.preventDefault()
      e.stopPropagation()

      // Clean up manual inputs if scanner typed into them
      if (isManualAuthField && activeEl) {
        try {
          const inputEl = activeEl as HTMLInputElement
          if (inputEl.value && globalScannerBuffer && inputEl.value.endsWith(globalScannerBuffer)) {
            inputEl.value = inputEl.value.slice(0, -globalScannerBuffer.length)
            inputEl.dispatchEvent(new Event('input', { bubbles: true }))
          }
          inputEl.blur()
        } catch {}
      }

      globalScannerBuffer = ''
      badgeScanInput.value = ''
      onBadgeScanSubmit(codeToProcess)
    }
  } else {
    const char = physicalKeyToAscii(e)
    if (char) {
      globalScannerBuffer += char

      // Auto-submit safety timer: If scanner does not send Enter, auto-process after 120ms burst
      if (_scannerBurstTimer) clearTimeout(_scannerBurstTimer)
      _scannerBurstTimer = setTimeout(() => {
        const codeToProcess = globalScannerBuffer.trim()
        if (codeToProcess.length >= 3 && (codeToProcess.startsWith('@') || !isManualAuthField)) {
          globalScannerBuffer = ''
          badgeScanInput.value = ''
          console.log('[Zero-Click Badge Burst Timeout]', codeToProcess)
          onBadgeScanSubmit(codeToProcess)
        }
      }, 120)
    }
  }
}

// Keep scanner focused when clicking anywhere on background
const handleGlobalDocClick = (e: MouseEvent) => {
  if (!import.meta.client) return
  const target = e.target as HTMLElement
  const isInteractive = target?.closest('input, textarea, select, .q-field--focused, button, .q-btn, .q-dialog, .q-menu, a')
  if (!isInteractive) {
    focusBadgeScanner()
  }
}

onMounted(() => {
  focusBadgeScanner()
  if (import.meta.client) {
    window.addEventListener('keydown', handleGlobalScanKeydown, { capture: true })
    document.addEventListener('click', handleGlobalDocClick, { capture: true })
    window.addEventListener('focus', focusBadgeScanner)
  }
})

onUnmounted(() => {
  if (import.meta.client) {
    window.removeEventListener('keydown', handleGlobalScanKeydown, { capture: true })
    document.removeEventListener('click', handleGlobalDocClick, { capture: true })
    window.removeEventListener('focus', focusBadgeScanner)
  }
  if (_scannerBurstTimer) clearTimeout(_scannerBurstTimer)
})

const onBadgeScanSubmit = async (scannedCode?: string) => {
  const rawVal = (typeof scannedCode === 'string' && scannedCode ? scannedCode : badgeScanInput.value).trim()
  if (!rawVal) return
  badgeScanInput.value = ''
  globalScannerBuffer = ''
  errorMessage.value = ''

  const username = rawVal.startsWith('@') ? rawVal.substring(1).trim() : rawVal.trim()
  if (!username) return

  isLoading.value = true
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/auth/badge-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    })
    if (response.ok) {
      const data = await response.json()
      authLogin(data.user, data.access_token)
      $q.notify({
        type: 'positive',
        icon: 'how_to_reg',
        message: `Welcome, ${data.user.full_name || data.user.username}!`,
        position: 'top',
        timeout: 1500
      })
      const redirectPath = (route.query.redirect as string) || '/'
      await router.replace(redirectPath)
    } else {
      const err = await response.json().catch(() => ({}))
      const msg = err.detail || t('login.invalidCredentials')
      errorMessage.value = msg
      $q.notify({ type: 'negative', icon: 'error', message: msg, position: 'top' })
    }
  } catch (error: any) {
    errorMessage.value = t('login.cannotConnect')
    $q.notify({ type: 'negative', message: errorMessage.value, position: 'top' })
  } finally {
    isLoading.value = false
    await nextTick()
    focusBadgeScanner()
  }
}

// ── Regular Manual Login ──────────────────────────────────────────────────
const handleLogin = async () => {
  if (!email.value || !email.value.trim()) {
    errorMessage.value = t('login.fillFields')
    $q.notify({ type: 'negative', message: errorMessage.value, position: 'top' })
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username_or_email: email.value.trim(),
        password: password.value ? password.value : ''
      }),
    })
    if (response.ok) {
      const data = await response.json()
      authLogin(data.user, data.access_token)
      $q.notify({ type: 'positive', message: t('login.loginSuccess'), position: 'top', timeout: 1000 })
      const redirectPath = (route.query.redirect as string) || '/'
      await router.replace(redirectPath)
    } else {
      const errorData = await response.json().catch(() => ({}))
      const msg = errorData.detail || t('login.invalidCredentials')
      errorMessage.value = msg
      $q.notify({ type: 'negative', message: msg, position: 'top' })
    }
  } catch (error: any) {
    errorMessage.value = `${t('login.cannotConnect')} (${appConfig.apiBaseUrl}). Error: ${error.message}`
    $q.notify({ type: 'negative', message: errorMessage.value, position: 'top', timeout: 5000 })
  } finally {
    isLoading.value = false
  }
}

const goToRegister = () => router.push('/x81-UserRegister')
const closeLogin = () => router.replace('/')
</script>

<template>
  <q-page class="q-pa-md" style="background-color: #0f172a; min-height: 100vh; display: flex; align-items: center; justify-content: center;">
    <div class="col-12 col-sm-10 col-md-6 col-lg-4" style="max-width: 520px; width: 100%;">
      <q-card class="shadow-10" style="border-radius: 18px; overflow: hidden; background: #1e293b; border: 1px solid rgba(255,255,255,0.1);">
        <!-- Title Bar -->
        <q-card-section class="bg-primary text-white q-pa-sm">
          <div class="row items-center no-wrap">
            <div class="col text-subtitle1 text-weight-bold row items-center q-gutter-x-sm">
              <q-icon name="precision_manufacturing" size="22px" />
              <span>xMixing Desktop HMI</span>
            </div>
            <q-btn icon="close" flat round dense @click="closeLogin" size="sm" />
          </div>
        </q-card-section>

        <!-- Header -->
        <q-card-section class="text-center bg-primary text-white q-pt-md q-pb-lg">
          <img src="/images/logo-final.svg" style="height: 64px; margin-bottom: 12px;" />
          <div class="text-h4 text-weight-bolder" style="letter-spacing: -0.5px;">{{ t('login.title') }}</div>
          <div class="text-caption text-blue-2 q-mt-xs">Production Operator & Supervisor Portal</div>
        </q-card-section>

        <!-- Form Content -->
        <q-card-section class="q-pa-lg text-white">

          <!-- Error Alert Banner -->
          <q-banner v-if="errorMessage" rounded dense class="bg-red-9 text-white q-mb-md shadow-2" style="border-radius: 8px;">
            <template v-slot:avatar>
              <q-icon name="error" color="white" />
            </template>
            <div class="text-weight-medium">{{ errorMessage }}</div>
          </q-banner>

          <!-- ── QR Badge Scan Section ── -->
          <div class="badge-scan-box q-mb-md">
            <div class="row items-center justify-between q-mb-xs">
              <div class="row items-center q-gutter-x-xs">
                <span class="radar-dot"></span>
                <span class="text-subtitle2 text-weight-bolder text-deep-purple-2" style="letter-spacing: 0.5px;">{{ t('login.qrBadgeLogin') }}</span>
              </div>
              <q-badge color="deep-purple-5" text-color="white" class="text-weight-bold" style="font-size: 11px;">
                {{ t('login.readyToScan') }}
              </q-badge>
            </div>
            
            <div class="text-caption text-grey-4 q-mb-sm">
              {{ t('login.scanBadgePlaceholder') }}
            </div>

            <q-input
              ref="badgeInputRef"
              v-model="badgeScanInput"
              outlined dense
              placeholder="Waiting for RFID/QR Scan..."
              @keyup.enter="onBadgeScanSubmit"
              bg-color="grey-10"
              dark
              class="scan-input"
            >
              <template v-slot:prepend>
                <q-icon name="qr_code_scanner" color="deep-purple-3" />
              </template>
              <template v-slot:append>
                <q-btn flat dense round icon="center_focus_strong" color="amber-4" @click="focusBadgeScanner">
                  <q-tooltip>{{ t('login.tapToFocus') }}</q-tooltip>
                </q-btn>
              </template>
            </q-input>
          </div>

          <!-- Divider -->
          <div class="row items-center q-gutter-sm q-mb-md">
            <q-separator class="col" dark style="opacity: 0.2;" />
            <span class="text-caption text-grey-4">{{ t('login.orLoginManually') }}</span>
            <q-separator class="col" dark style="opacity: 0.2;" />
          </div>

          <!-- Username Field -->
          <div class="q-mb-md">
            <q-input v-model="email" outlined :label="t('login.usernameOrEmail')" dense dark bg-color="grey-10" @keyup.enter="handleLogin">
              <template v-slot:prepend><q-icon name="person" color="primary" /></template>
            </q-input>
          </div>

          <!-- Password Field -->
          <div class="q-mb-md">
            <q-input v-model="password" outlined :label="t('login.password')" :type="showPassword ? 'text' : 'password'" dense dark bg-color="grey-10" @keyup.enter="handleLogin">
              <template v-slot:prepend><q-icon name="lock" color="primary" /></template>
              <template v-slot:append>
                <q-icon :name="showPassword ? 'visibility' : 'visibility_off'" class="cursor-pointer" color="primary" @click="showPassword = !showPassword" />
              </template>
            </q-input>
          </div>

          <!-- Login Button -->
          <q-btn :label="t('login.loginButton')" color="primary" size="lg" class="full-width text-white text-weight-bold q-py-sm" style="border-radius: 10px;" :loading="isLoading" @click="handleLogin" />

          <!-- Register & Links -->
          <div class="row items-center justify-between q-mt-md">
            <q-btn :label="t('login.createAccount')" flat size="sm" color="blue-3" @click="goToRegister" />
            <q-btn :label="t('login.forgotPassword')" flat size="sm" color="grey-4" />
          </div>
        </q-card-section>

        <!-- Footer -->
        <q-card-section class="text-center text-caption text-grey-5 bg-grey-10 q-py-sm">
          {{ t('login.copyright') }}
        </q-card-section>
      </q-card>
    </div>
  </q-page>
</template>

<style scoped>
.badge-scan-box {
  background: linear-gradient(135deg, rgba(103, 58, 183, 0.25), rgba(63, 81, 181, 0.2));
  border: 2px solid #7e57c2;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 4px 20px rgba(126, 87, 194, 0.2);
}

.radar-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #a855f7;
  display: inline-block;
  box-shadow: 0 0 10px #c084fc;
  animation: radar-pulse 1.6s ease-in-out infinite;
}

@keyframes radar-pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(168, 85, 247, 0.7); }
  70% { transform: scale(1.15); box-shadow: 0 0 0 10px rgba(168, 85, 247, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(168, 85, 247, 0); }
}
</style>

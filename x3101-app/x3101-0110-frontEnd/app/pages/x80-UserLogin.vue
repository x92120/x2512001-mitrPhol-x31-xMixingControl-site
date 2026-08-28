<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'

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

// ── Badge QR Login ────────────────────────────────────────────────────────
const badgeScanInput = ref('')
const badgePin = ref('')
const scannedBadgeUser = ref<string | null>(null)  // username from QR
const showPinDialog = ref(false)
const badgePinLoading = ref(false)
const badgeInputRef = ref<any>(null)
const pinFieldRef = ref<any>(null)
let _badgeDebounce: ReturnType<typeof setTimeout> | null = null

// Auto-submit badge scan when scanner stops typing (150ms debounce)
watch(badgeScanInput, (val) => {
  if (!val) return
  if (_badgeDebounce) clearTimeout(_badgeDebounce)
  _badgeDebounce = setTimeout(() => {
    if (badgeScanInput.value.trim()) onBadgeScanSubmit()
  }, 150)
})

const focusBadgeScanner = () => {
  badgeInputRef.value?.focus()
}

onMounted(() => {
  focusBadgeScanner()
})

const onBadgeScanSubmit = async () => {
  const val = badgeScanInput.value.trim()
  if (!val) return
  badgeScanInput.value = ''
  errorMessage.value = ''
  scannedBadgeUser.value = val
  showPinDialog.value = true
  await nextTick()
  pinFieldRef.value?.focus()
}

const handleBadgeLogin = async () => {
  if (!scannedBadgeUser.value || badgePin.value.length < 4) {
    errorMessage.value = 'Please enter your 4-8 digit PIN'
    $q.notify({ type: 'negative', message: errorMessage.value, position: 'top' })
    return
  }
  badgePinLoading.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/auth/badge-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: scannedBadgeUser.value, badge_pin: badgePin.value })
    })
    if (response.ok) {
      const data = await response.json()
      authLogin(data.user, data.access_token)
      showPinDialog.value = false
      $q.notify({ type: 'positive', icon: 'how_to_reg', message: `Welcome, ${data.user.full_name || data.user.username}!`, position: 'top', timeout: 1500 })
      const redirectPath = (route.query.redirect as string) || '/'
      await router.replace(redirectPath)
    } else {
      const err = await response.json().catch(() => ({}))
      const msg = err.detail || t('login.invalidPin')
      errorMessage.value = msg
      $q.notify({ type: 'negative', icon: 'lock', message: msg, position: 'top' })
      badgePin.value = ''
      pinFieldRef.value?.focus()
    }
  } catch {
    errorMessage.value = t('login.cannotConnect')
    $q.notify({ type: 'negative', message: errorMessage.value, position: 'top' })
  } finally {
    badgePinLoading.value = false
  }
}

const closePinDialog = () => {
  showPinDialog.value = false
  scannedBadgeUser.value = null
  badgePin.value = ''
  focusBadgeScanner()
}

// ── Regular Login ────────────────────────────────────────────────────────
const handleLogin = async () => {
  if (!email.value || !password.value) {
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
      body: JSON.stringify({ username_or_email: email.value, password: password.value }),
    })
    if (response.ok) {
      const data = await response.json()
      authLogin(data.user, data.access_token)
      $q.notify({ type: 'positive', message: t('login.loginSuccess'), position: 'top', timeout: 1000 })
      const redirectPath = (route.query.redirect as string) || '/'
      await router.replace(redirectPath)
    } else {
      const errorData = await response.json().catch(() => ({}))
      errorMessage.value = errorData.detail || t('login.invalidCredentials')
      $q.notify({ type: 'negative', message: errorMessage.value, position: 'top' })
    }
  } catch (error: any) {
    errorMessage.value = `${t('login.cannotConnect')} (${appConfig.apiBaseUrl}). ${error.message || ''}`
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

    <!-- ── Badge PIN Dialog ── -->
    <q-dialog v-model="showPinDialog" persistent>
      <q-card style="min-width: 360px; border-radius: 16px; overflow: hidden; background: #1e293b; color: white;">
        <!-- Header -->
        <q-card-section class="bg-deep-purple-8 text-white text-center q-py-lg">
          <q-icon name="how_to_reg" size="48px" class="q-mb-sm" />
          <div class="text-h6 text-weight-bold">{{ t('login.badgeLoginDialogTitle') }}</div>
          <div class="text-body2 opacity-80 q-mt-xs">
            <q-icon name="person" size="sm" class="q-mr-xs" />
            <strong>{{ scannedBadgeUser }}</strong>
          </div>
        </q-card-section>

        <!-- PIN Input -->
        <q-card-section class="q-pa-lg text-center">
          <div class="text-body2 text-grey-4 q-mb-md">{{ t('login.enterBadgePin') }}</div>
          <q-input
            ref="pinFieldRef"
            v-model="badgePin"
            type="password"
            outlined
            dense
            dark
            bg-color="grey-10"
            :placeholder="t('login.badgePinPlaceholder')"
            maxlength="8"
            style="font-size: 24px; letter-spacing: 8px; text-align: center;"
            @keyup.enter="handleBadgeLogin"
            input-class="text-center"
            autofocus
          >
            <template v-slot:prepend><q-icon name="pin" color="deep-purple-3" /></template>
          </q-input>
        </q-card-section>

        <!-- Actions -->
        <q-card-actions class="q-px-lg q-pb-lg row q-gutter-sm">
          <q-btn flat class="col" :label="t('common.cancel')" color="grey-4" @click="closePinDialog" />
          <q-btn class="col" :label="t('login.loginButton')" color="deep-purple-7" unelevated :loading="badgePinLoading" @click="handleBadgeLogin" />
        </q-card-actions>
      </q-card>
    </q-dialog>
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

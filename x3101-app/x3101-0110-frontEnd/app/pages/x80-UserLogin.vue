<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
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

// ── Badge QR Login ────────────────────────────────────────────────────────
const badgeScanInput = ref('')
const badgePin = ref('')
const scannedBadgeUser = ref<string | null>(null)  // username from QR
const showPinDialog = ref(false)
const badgePinLoading = ref(false)
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

const onBadgeScanSubmit = async () => {
  const val = badgeScanInput.value.trim()
  if (!val) return
  badgeScanInput.value = ''
  scannedBadgeUser.value = val
  showPinDialog.value = true
  await nextTick()
  pinFieldRef.value?.focus()
}

const handleBadgeLogin = async () => {
  if (!scannedBadgeUser.value || badgePin.value.length < 4) {
    $q.notify({ type: 'negative', message: 'Please enter your 4-digit PIN', position: 'top' })
    return
  }
  badgePinLoading.value = true
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
      $q.notify({ type: 'negative', icon: 'lock', message: err.detail || 'Invalid PIN', position: 'top' })
      badgePin.value = ''
      pinFieldRef.value?.focus()
    }
  } catch {
    $q.notify({ type: 'negative', message: 'Cannot connect to server', position: 'top' })
  } finally {
    badgePinLoading.value = false
  }
}

const closePinDialog = () => {
  showPinDialog.value = false
  scannedBadgeUser.value = null
  badgePin.value = ''
}

// ── Regular Login ────────────────────────────────────────────────────────
const handleLogin = async () => {
  if (!email.value || !password.value) {
    $q.notify({ type: 'negative', message: t('login.fillFields'), position: 'top' })
    return
  }
  isLoading.value = true
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
      $q.notify({ type: 'negative', message: errorData.detail || t('login.invalidCredentials'), position: 'top' })
    }
  } catch (error: any) {
    $q.notify({ type: 'negative', message: `${t('login.cannotConnect')} (${appConfig.apiBaseUrl}). Error: ${error.message}`, position: 'top', timeout: 5000 })
  } finally {
    isLoading.value = false
  }
}

const goToRegister = () => router.push('/x81-UserRegister')
const closeLogin = () => router.replace('/')
</script>

<template>
  <q-page class="q-pa-md" style="background-color: #f5f5f5; min-height: 100vh; display: flex; align-items: center; justify-content: center;">
    <div class="col-12 col-sm-8 col-md-5 col-lg-4">
      <q-card class="shadow-1">
        <!-- Title Bar -->
        <q-card-section class="bg-primary text-white q-pa-sm">
          <div class="row items-center no-wrap">
            <div class="col text-h6 text-weight-bold">xMixing</div>
            <q-btn icon="close" flat round dense @click="closeLogin" size="sm" />
          </div>
        </q-card-section>

        <!-- Header -->
        <q-card-section class="text-center bg-primary text-white q-pt-md q-pb-lg">
          <img src="/images/logo-final.svg" style="height: 80px; margin-bottom: 20px;" />
          <div class="text-h4 text-weight-bold">{{ t('login.title') }}</div>
        </q-card-section>

        <!-- Form Content -->
        <q-card-section class="q-pa-lg">

          <!-- ── QR Badge Scan Section ── -->
          <div class="badge-scan-section q-mb-md">
            <div class="row items-center q-gutter-xs q-mb-xs">
              <q-icon name="qr_code_scanner" color="deep-purple-7" size="20px" />
              <span class="text-caption text-weight-bold text-deep-purple-8" style="letter-spacing: 0.5px; text-transform: uppercase;">QR Badge Login</span>
            </div>
            <q-input
              v-model="badgeScanInput"
              outlined dense
              placeholder="Scan your QR Badge..."
              @keyup.enter="onBadgeScanSubmit"
              bg-color="white"
              autofocus
            >
              <template v-slot:prepend>
                <q-icon name="badge" color="deep-purple-6" />
              </template>
            </q-input>
          </div>

          <!-- Divider -->
          <div class="row items-center q-gutter-sm q-mb-md">
            <q-separator class="col" color="grey-4" />
            <span class="text-caption text-grey-6">or login manually</span>
            <q-separator class="col" color="grey-4" />
          </div>

          <!-- Username Field -->
          <div class="q-mb-md">
            <q-input v-model="email" outlined :label="t('login.usernameOrEmail')" dense @keyup.enter="handleLogin">
              <template v-slot:prepend><q-icon name="person" color="primary" /></template>
            </q-input>
          </div>

          <!-- Password Field -->
          <div class="q-mb-md">
            <q-input v-model="password" outlined :label="t('login.password')" :type="showPassword ? 'text' : 'password'" dense @keyup.enter="handleLogin">
              <template v-slot:prepend><q-icon name="lock" color="primary" /></template>
              <template v-slot:append>
                <q-icon :name="showPassword ? 'visibility' : 'visibility_off'" class="cursor-pointer" color="primary" @click="showPassword = !showPassword" />
              </template>
            </q-input>
          </div>

          <!-- Login Button -->
          <q-btn :label="t('login.loginButton')" color="primary" size="lg" class="full-width text-white text-weight-bold" :loading="isLoading" @click="handleLogin" />

          <!-- Divider -->
          <div class="q-my-md text-center">
            <q-separator color="primary" class="q-my-md" />
            <div class="text-caption">{{ t('login.noAccount') }}</div>
          </div>

          <!-- Register -->
          <q-btn :label="t('login.createAccount')" color="primary" outline size="lg" class="full-width text-weight-bold" @click="goToRegister" />

          <!-- Forgot -->
          <div class="text-center q-mt-md">
            <q-btn :label="t('login.forgotPassword')" flat size="sm" color="primary" />
          </div>
        </q-card-section>

        <!-- Footer -->
        <q-card-section class="text-center text-caption bg-primary text-white">
          {{ t('login.copyright') }}
        </q-card-section>
      </q-card>
    </div>

    <!-- ── Badge PIN Dialog ── -->
    <q-dialog v-model="showPinDialog" persistent>
      <q-card style="min-width: 320px; border-radius: 16px; overflow: hidden;">
        <!-- Header -->
        <q-card-section class="bg-deep-purple-8 text-white text-center q-py-lg">
          <q-icon name="how_to_reg" size="48px" class="q-mb-sm" />
          <div class="text-h6 text-weight-bold">Badge Login</div>
          <div class="text-body2 opacity-80 q-mt-xs">
            <q-icon name="person" size="sm" class="q-mr-xs" />
            <strong>{{ scannedBadgeUser }}</strong>
          </div>
        </q-card-section>

        <!-- PIN Input -->
        <q-card-section class="q-pa-lg text-center">
          <div class="text-body2 text-grey-7 q-mb-md">Enter your 4-digit Badge PIN</div>
          <q-input
            ref="pinFieldRef"
            v-model="badgePin"
            type="password"
            outlined
            dense
            placeholder="● ● ● ●"
            maxlength="8"
            style="font-size: 24px; letter-spacing: 8px; text-align: center;"
            @keyup.enter="handleBadgeLogin"
            input-class="text-center"
          >
            <template v-slot:prepend><q-icon name="pin" color="deep-purple-7" /></template>
          </q-input>
        </q-card-section>

        <!-- Actions -->
        <q-card-actions class="q-px-lg q-pb-lg row q-gutter-sm">
          <q-btn flat class="col" label="Cancel" color="grey-7" @click="closePinDialog" />
          <q-btn class="col" label="Login" color="deep-purple-8" unelevated :loading="badgePinLoading" @click="handleBadgeLogin" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<style scoped>
.badge-scan-section {
  background: linear-gradient(135deg, #ede7f6, #f3e5f5);
  border: 1px solid #ce93d8;
  border-radius: 10px;
  padding: 12px 16px;
}
</style>

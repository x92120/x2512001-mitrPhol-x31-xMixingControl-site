<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'

const router = useRouter()
const $q = useQuasar()
const { t } = useI18n()

const formData = ref({
  username: '',
  fullName: '',
  email: '',
  password: '',
  confirmPassword: '',
  department: '',
})

const showPassword = ref(false)
const showConfirmPassword = ref(false)
const isLoading = ref(false)

const departments = ['Production', 'Quality Control', 'Inventory', 'Management', 'Admin']

const validateForm = () => {
  if (
    !formData.value.username ||
    !formData.value.fullName ||
    !formData.value.email ||
    !formData.value.password
  ) {
    $q.notify({
      type: 'negative',
      message: t('register.fillRequired'),
      position: 'top',
    })
    return false
  }

  if (formData.value.password !== formData.value.confirmPassword) {
    $q.notify({
      type: 'negative',
      message: t('register.passwordsNoMatch'),
      position: 'top',
    })
    return false
  }

  return true
}

const handleRegister = async () => {
  if (!validateForm()) return

  isLoading.value = true

  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: formData.value.username,
        email: formData.value.email,
        password: formData.value.password,
        full_name: formData.value.fullName,
        department: formData.value.department,
        role: 'Operator',
        status: 'Active',
        permissions: [],
      }),
    })

    if (response.ok) {
      $q.notify({
        type: 'positive',
        message: t('register.success'),
        position: 'top',
        timeout: 2000
      })
      router.push('/x80-UserLogin')
    } else {
      const errorData = await response.json().catch(() => ({}))
      $q.notify({
        type: 'negative',
        message: errorData.detail || t('register.failed'),
        position: 'top',
      })
    }
  } catch (error) {
    console.error('❌ Registration error:', error)
    $q.notify({
      type: 'negative',
      message: t('register.networkError'),
      position: 'top',
    })
  } finally {
    isLoading.value = false
  }
}

const goToLogin = () => router.push('/x80-UserLogin')
</script>

<template>
  <q-page
    class="q-pa-md"
    style="
      background-color: #f5f5f5;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding-top: 2rem;
      padding-bottom: 2rem;
    "
  >
    <div class="col-12 col-sm-8 col-md-6 col-lg-5">
      <q-card class="shadow-1">
        <!-- Header -->
        <q-card-section class="text-center bg-primary text-white">
          <img src="/images/logo-final.svg" style="height: 80px; margin-bottom: 20px;" />
          <div class="text-subtitle2 q-mt-sm">{{ t('register.createAccount') }}</div>
        </q-card-section>

        <!-- Form Content -->
        <q-card-section class="q-pa-lg">
          <!-- Username -->
          <div class="q-mb-md">
            <q-input v-model="formData.username" outlined :label="t('register.username') + ' *'" dense>
              <template v-slot:prepend>
                <q-icon name="account_circle" color="primary" />
              </template>
            </q-input>
          </div>

          <!-- Full Name -->
          <div class="q-mb-md">
            <q-input v-model="formData.fullName" outlined :label="t('register.fullName') + ' *'" dense>
              <template v-slot:prepend>
                <q-icon name="person" color="primary" />
              </template>
            </q-input>
          </div>

          <!-- Email -->
          <div class="q-mb-md">
            <q-input v-model="formData.email" outlined :label="t('register.email') + ' *'" type="email" dense>
              <template v-slot:prepend>
                <q-icon name="email" color="primary" />
              </template>
            </q-input>
          </div>

          <!-- Department -->
          <div class="q-mb-md">
            <q-select
              v-model="formData.department"
              outlined
              :options="departments"
              :label="t('register.department')"
              dense
              emit-value
              map-options
            >
              <template v-slot:prepend>
                <q-icon name="work" color="primary" />
              </template>
            </q-select>
          </div>

          <!-- Password -->
          <div class="q-mb-md">
            <q-input
              v-model="formData.password"
              outlined
              :label="t('register.password') + ' *'"
              :type="showPassword ? 'text' : 'password'"
              dense
            >
              <template v-slot:prepend>
                <q-icon name="lock" color="primary" />
              </template>
              <template v-slot:append>
                <q-icon
                  :name="showPassword ? 'visibility' : 'visibility_off'"
                  class="cursor-pointer"
                  color="primary"
                  @click="showPassword = !showPassword"
                />
              </template>
            </q-input>
          </div>

          <!-- Confirm Password -->
          <div class="q-mb-md">
            <q-input
              v-model="formData.confirmPassword"
              outlined
              :label="t('register.confirmPassword') + ' *'"
              :type="showConfirmPassword ? 'text' : 'password'"
              dense
            >
              <template v-slot:prepend>
                <q-icon name="lock" color="primary" />
              </template>
              <template v-slot:append>
                <q-icon
                  :name="showConfirmPassword ? 'visibility' : 'visibility_off'"
                  class="cursor-pointer"
                  color="primary"
                  @click="showConfirmPassword = !showConfirmPassword"
                />
              </template>
            </q-input>
          </div>

          <!-- Register Button -->
          <q-btn
            :label="t('register.createBtn')"
            color="primary"
            size="lg"
            class="full-width text-white text-weight-bold"
            :loading="isLoading"
            @click="handleRegister"
          />

          <!-- Login Link -->
          <div class="text-center q-mt-md">
            <span>{{ t('register.alreadyHaveAccount') }} </span>
            <q-btn :label="t('register.loginHere')" flat size="sm" color="primary" @click="goToLogin" />
          </div>
        </q-card-section>

        <!-- Footer -->
        <q-card-section class="text-center text-caption bg-primary text-white">
          {{ t('register.copyright') }}
        </q-card-section>
      </q-card>
    </div>
  </q-page>
</template>

<style scoped></style>

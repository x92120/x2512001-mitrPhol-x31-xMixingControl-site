<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '~/composables/useAuth'
import QRCode from 'qrcode'

interface User {
  id?: number
  username: string
  email: string
  full_name: string
  role: string
  department: string
  status: string
  permissions: string[]
  last_login?: string
  password?: string
  new_password?: string
  badge_pin?: string
}

const $q = useQuasar()
const { getAuthHeader } = useAuth()
const { t } = useI18n()

const formatDateTime = (date: any) => {
  if (!date) return '-'
  const d = new Date(date)
  if (isNaN(d.getTime())) return date
  return d.toLocaleString('en-GB')
}

const selectedUser = ref<User | null>(null)
const isCreateDialogOpen = ref(false)
const newUser = ref<User>({
  username: '',
  email: '',
  full_name: '',
  role: 'Operator',
  department: '',
  status: 'Active',
  permissions: [],
  password: ''
})
const searchQuery = ref('')
const isLoading = ref(false)

// QR Code
const newUserQrDataUrl = ref<string>('')
const selectedUserQrDataUrl = ref<string>('')

const generateQr = async (username: string, target: 'new' | 'selected') => {
  if (!username || username.trim() === '') {
    if (target === 'new') newUserQrDataUrl.value = ''
    else selectedUserQrDataUrl.value = ''
    return
  }
  try {
    const url = await QRCode.toDataURL(username.trim(), {
      width: 200,
      margin: 2,
      color: { dark: '#1a237e', light: '#ffffff' },
    })
    if (target === 'new') newUserQrDataUrl.value = url
    else selectedUserQrDataUrl.value = url
  } catch (e) {
    console.error('QR generation error:', e)
  }
}

const printQr = (username: string, fullName: string, qrDataUrl: string) => {
  if (!qrDataUrl) return
  const win = window.open('', '_blank', 'width=400,height=520')
  if (!win) return
  win.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8" />
      <title>QR Code - ${username}</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: 'Segoe UI', Arial, sans-serif;
          background: #f5f7ff;
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
        }
        .card {
          background: white;
          border-radius: 16px;
          padding: 32px 40px;
          text-align: center;
          box-shadow: 0 4px 24px rgba(26,35,126,0.15);
          border-top: 6px solid #1a237e;
        }
        .logo-bar {
          font-size: 13px;
          color: #1a237e;
          font-weight: 700;
          letter-spacing: 2px;
          margin-bottom: 20px;
          text-transform: uppercase;
        }
        .qr-wrap {
          background: #f0f4ff;
          border-radius: 12px;
          padding: 12px;
          display: inline-block;
          margin-bottom: 20px;
        }
        .qr-wrap img { display: block; width: 200px; height: 200px; }
        .name { font-size: 18px; font-weight: 700; color: #1a237e; margin-bottom: 6px; }
        .username { font-size: 14px; color: #555; background: #eef0ff; border-radius: 6px; padding: 4px 14px; display: inline-block; margin-bottom: 20px; }
        .footer { font-size: 11px; color: #aaa; margin-top: 8px; }
        @media print {
          body { background: white; }
          .card { box-shadow: none; }
        }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="logo-bar">xMixing System</div>
        <div class="qr-wrap">
          <img src="${qrDataUrl}" alt="QR Code" />
        </div>
        <div class="name">${fullName || username}</div>
        <div class="username">@${username}</div>
        <div class="footer">Scan to identify user &bull; xMixing v2.5</div>
      </div>
      <script>window.onload = () => { window.print(); window.onafterprint = () => window.close(); }<\/script>
    </body>
    </html>
  `)
  win.document.close()
}

// Users list
const users = ref<User[]>([])

// Available permissions
const allPermissions = ref([
  { value: 'sku_management', label: 'SKU Management' },
  { value: 'ingredient_receipt', label: 'Ingredient Receipt' },
  { value: 'production_planning', label: 'Production Planning' },
  { value: 'production_list', label: 'Production List' },
  { value: 'prepare_batch', label: 'Prepare Batch' },
  { value: 'admin', label: 'Admin' },
])

// Roles
const roles = ['Admin', 'Manager', 'Operator', 'QC Inspector', 'Viewer']

const filteredUsers = computed(() => {
  if (!searchQuery.value) return users.value
  const query = searchQuery.value.toLowerCase()
  return users.value.filter(u => 
    (u.full_name?.toLowerCase().includes(query)) || 
    (u.email?.toLowerCase().includes(query)) ||
    (u.username?.toLowerCase().includes(query)) ||
    (u.role?.toLowerCase().includes(query)) ||
    (u.department?.toLowerCase().includes(query))
  )
})

const selectUser = (user: User) => {
  selectedUser.value = { ...user }
}

const fetchUsers = async () => {
  isLoading.value = true
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/users/`, {
      headers: getAuthHeader() as Record<string, string>,
    })
    if (response.ok) {
      users.value = await response.json()
    } else {
      $q.notify({
        type: 'negative',
        message: t('userConfig.failedFetchUsers'),
        position: 'top',
      })
    }
  } catch (error) {
    console.error('Error fetching users:', error)
    $q.notify({
      type: 'negative',
      message: t('userConfig.errorFetchUsers'),
      position: 'top',
    })
  } finally {
    isLoading.value = false
  }
}

const saveUserChanges = async () => {
  if (!selectedUser.value) return

  isLoading.value = true
  try {
    const payload: any = {
      username: selectedUser.value.username,
      full_name: selectedUser.value.full_name,
      email: selectedUser.value.email,
      role: selectedUser.value.role,
      department: selectedUser.value.department,
      status: selectedUser.value.status,
      permissions: selectedUser.value.permissions,
    }

    if (selectedUser.value.new_password) {
      payload.password = selectedUser.value.new_password
    }
    if (selectedUser.value.badge_pin !== undefined) {
      payload.badge_pin = selectedUser.value.badge_pin  // '' = clear PIN
    }

    const response = await fetch(`${appConfig.apiBaseUrl}/users/${selectedUser.value.id}`, {
      method: 'PUT',
      headers: {
        ...getAuthHeader() as Record<string, string>,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (response.ok) {
      const updatedUser = await response.json()
      const index = users.value.findIndex((u) => u.id === updatedUser.id)
      if (index !== -1) {
        users.value[index] = updatedUser
      }
      $q.notify({
        type: 'primary',
        message: t('userConfig.userUpdated'),
        position: 'top',
      })
      selectedUser.value = null
    } else {
      const errorData = await response.json()
      let errorMessage = t('userConfig.failedUpdate')
      if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        // Handle Pydantic validation errors
        errorMessage = errorData.detail.map((err: any) => err.msg).join(', ')
      } else if (typeof errorData.detail === 'object') {
        errorMessage = JSON.stringify(errorData.detail)
      }
      throw new Error(errorMessage)
    }
  } catch (error: any) {
    console.error('Error updating user:', error)
    $q.notify({
      type: 'negative',
      message: error.message || t('userConfig.failedUpdate'),
      position: 'top',
    })
  } finally {
    isLoading.value = false
  }
}

const createUser = async () => {
  isLoading.value = true
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}/users/`, {
      method: 'POST',
      headers: {
        ...getAuthHeader() as Record<string, string>,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newUser.value),
    })

    if (response.ok) {
      const createdUser = await response.json()
      users.value.push(createdUser)
      $q.notify({
        type: 'primary',
        message: t('userConfig.userCreated'),
        position: 'top',
      })
      closeCreateDialog()
    } else {
      const errorData = await response.json()
      throw new Error(errorData.detail || t('userConfig.failedCreate'))
    }
  } catch (error: any) {
    console.error('Error creating user:', error)
    $q.notify({
      type: 'negative',
      message: error.message || t('userConfig.failedCreate'),
      position: 'top',
    })
  } finally {
    isLoading.value = false
  }
}

const closeCreateDialog = () => {
  isCreateDialogOpen.value = false
  newUserQrDataUrl.value = ''
  newUser.value = {
    username: '',
    email: '',
    full_name: '',
    role: 'Operator',
    department: '',
    status: 'Active',
    permissions: [],
    password: ''
  }
}

// Watch username changes to auto-generate QR
watch(() => newUser.value.username, (val) => generateQr(val, 'new'))
watch(() => selectedUser.value?.username, (val) => { if (val) generateQr(val, 'selected') })


onMounted(() => {
  fetchUsers()
})

const togglePermission = (permission: string) => {
  if (!selectedUser.value) return
  const index = selectedUser.value.permissions.indexOf(permission)
  if (index > -1) {
    selectedUser.value.permissions.splice(index, 1)
  } else {
    selectedUser.value.permissions.push(permission)
  }
}

const hasPermission = (permission: string) => {
  return selectedUser.value && selectedUser.value.permissions.includes(permission)
}

const closeDialog = () => {
  selectedUser.value = null
}

const deleteUser = (user: User) => {
  $q.dialog({
    title: t('userConfig.deleteUser'),
    message: t('userConfig.confirmDeleteUser', { name: user.full_name || user.username }),
    cancel: true,
    persistent: true,
    color: 'negative',
  }).onOk(async () => {
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/users/${user.id}`, {
        method: 'DELETE',
        headers: getAuthHeader() as Record<string, string>,
      })
      if (response.ok) {
        users.value = users.value.filter(u => u.id !== user.id)
        $q.notify({ type: 'positive', message: t('userConfig.userDeleted', { name: user.full_name || user.username }), position: 'top' })
      } else {
        const errorData = await response.json()
        throw new Error(errorData.detail || t('userConfig.failedDeleteUser'))
      }
    } catch (error: any) {
      $q.notify({ type: 'negative', message: error.message || t('userConfig.failedDeleteUser'), position: 'top' })
    }
  })
}
</script>

<template>
  <q-page class="q-pa-md" style="background-color: #f5f5f5">
    <!-- Header -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card class="shadow-1">
          <q-card-section class="bg-info text-white">
            <div class="text-h6 text-weight-bold">{{ t('userConfig.title') }}</div>
          </q-card-section>

          <q-form class="q-pa-md">
            <!-- Search Section -->
            <div class="row q-col-gutter-md q-mb-md">
              <div class="col-12 row items-center no-wrap">
                <q-input
                  v-model="searchQuery"
                  outlined
                  :label="t('userConfig.searchUsers')"
                  dense
                  class="col"
                >
                  <template v-slot:prepend>
                    <q-icon name="search" color="info" />
                  </template>
                </q-input>
                <q-btn
                  :label="t('userConfig.addUser')"
                  color="primary"
                  icon="add"
                  class="q-ml-md"
                  @click="isCreateDialogOpen = true"
                />
              </div>
            </div>
          </q-form>
        </q-card>
      </div>
    </div>

    <!-- Users Table -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card class="shadow-1">
          <q-table
            :rows="filteredUsers"
            :columns="[
              { name: 'full_name', label: t('userConfig.name'), field: 'full_name', align: 'left' },
              { name: 'email', label: t('userConfig.email'), field: 'email', align: 'left' },
              { name: 'role', label: t('userConfig.role'), field: 'role', align: 'left' },
              { name: 'department', label: t('userConfig.department'), field: 'department', align: 'left' },
              { name: 'status', label: t('common.status'), field: 'status', align: 'center' },
              { name: 'last_login', label: t('login.lastLogin'), field: 'last_login', align: 'center', format: (val: any) => formatDateTime(val) },
              { name: 'actions', label: t('common.actions'), field: 'actions', align: 'center' },
            ]"
            row-key="id"
            flat
          >
            <template v-slot:body-cell-status="props">
              <q-td :props="props">
                <q-chip
                  :label="props.row.status"
                  :color="props.row.status === 'Active' ? 'primary' : 'negative'"
                  text-color="white"
                  size="sm"
                />
              </q-td>
            </template>

            <template v-slot:body-cell-actions="props">
              <q-td :props="props">
                <q-btn
                  :label="t('userConfig.manage')"
                  color="info"
                  size="sm"
                  padding="xs md"
                  class="text-white text-weight-bold q-mr-sm"
                  @click="selectUser(props.row)"
                />
                <q-btn
                  :label="t('common.delete')"
                  color="negative"
                  size="sm"
                  padding="xs md"
                  class="text-white text-weight-bold"
                  icon="delete"
                  @click="deleteUser(props.row)"
                />
              </q-td>
            </template>
          </q-table>
        </q-card>
      </div>
    </div>

    <!-- Create User Dialog -->
    <q-dialog v-model="isCreateDialogOpen" persistent>
      <q-card style="min-width: 400px">
        <q-card-section class="bg-primary text-white">
          <div class="row items-center">
            <div class="text-h6">{{ t('userConfig.addNewUser') }}</div>
            <q-space />
            <q-btn icon="close" flat round dense @click="closeCreateDialog" />
          </div>
        </q-card-section>

        <q-card-section class="q-pt-none q-pa-lg">
          <q-form @submit.prevent="createUser" class="q-gutter-md">
            <q-input
              filled
              v-model="newUser.username"
              label="Username *"
              :hint="t('userConfig.uniqueId')"
              lazy-rules
              :rules="[ val => val && val.length > 0 || t('userConfig.pleaseType')]"
            />

            <!-- QR Code Preview (auto-generate from username) -->
            <div v-if="newUserQrDataUrl" class="qr-preview-block">
              <div class="qr-preview-label">QR Code Preview</div>
              <div class="qr-preview-wrap">
                <img :src="newUserQrDataUrl" alt="QR Code" class="qr-img" />
                <div class="qr-username-badge">@{{ newUser.username }}</div>
              </div>
              <q-btn
                icon="print"
                label="Print QR"
                color="indigo-8"
                size="sm"
                class="q-mt-sm full-width"
                @click="printQr(newUser.username, newUser.full_name, newUserQrDataUrl)"
              />
            </div>

            <q-input
              filled
              v-model="newUser.email"
              label="Email *"
              type="email"
              lazy-rules
              :rules="[ val => val && val.length > 0 || t('userConfig.pleaseType')]"
            />
            <q-input
              filled
              v-model="newUser.password"
              label="Password *"
              type="password"
              lazy-rules
              :rules="[ val => val && val.length >= 6 || t('userConfig.passwordMinLength')]"
            />
            <q-input
              filled
              v-model="newUser.full_name"
              label="Full Name"
            />
            <q-select
              filled
              v-model="newUser.role"
              :options="roles"
              label="Role"
            />
            <q-input
              filled
              v-model="newUser.department"
              label="Department"
            />

            <div align="right">
              <q-btn :label="t('common.cancel')" flat color="primary" v-close-popup class="q-mr-sm" @click="closeCreateDialog" />
              <q-btn :label="t('userConfig.createUser')" type="submit" color="primary" :loading="isLoading" />
            </div>
          </q-form>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- User Permissions Dialog -->
    <q-dialog
      :model-value="selectedUser !== null"
      position="right"
      :maximized="false"
      @update:model-value="
        (val) => {
          if (!val) closeDialog()
        }
      "
      @hide="closeDialog"
    >
      <q-card style="min-width: 800px; max-width: 900px" v-if="selectedUser">
        <!-- Dialog Header -->
        <q-card-section class="bg-info text-white">
          <div class="row items-center">
            <div class="col">
              <div class="text-h6 text-weight-bold">{{ selectedUser.full_name }}</div>
              <div style="font-size: 0.9rem">{{ selectedUser.email }}</div>
            </div>
            <q-btn icon="close" flat round dense @click="closeDialog" />
          </div>
        </q-card-section>

        <q-card-section class="q-pa-lg">
          <div class="row q-col-gutter-xl">
            <!-- Left Column: User Info -->
            <div class="col-12 col-md-6">
              <div class="text-subtitle2 text-weight-bold q-mb-md">{{ t('userConfig.userInfo') }}</div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('register.username') }}</div>
                <q-input v-model="selectedUser.username" outlined dense />
              </div>

              <!-- QR Code Section in Manage Dialog -->
              <div class="qr-manage-block q-mb-lg">
                <div class="qr-manage-label">
                  <q-icon name="qr_code_2" size="18px" class="q-mr-xs" />
                  QR Code Badge
                </div>
                <div v-if="selectedUserQrDataUrl" class="qr-manage-inner">
                  <img :src="selectedUserQrDataUrl" alt="QR" class="qr-manage-img" />
                  <div class="qr-manage-name">{{ selectedUser.full_name || selectedUser.username }}</div>
                  <div class="qr-manage-user">@{{ selectedUser.username }}</div>
                  <q-btn
                    icon="print"
                    label="Print QR Badge"
                    color="indigo-8"
                    size="sm"
                    class="q-mt-sm full-width"
                    @click="printQr(selectedUser.username, selectedUser.full_name, selectedUserQrDataUrl)"
                  />
                </div>
                <div v-else class="qr-manage-empty">
                  <q-icon name="qr_code" size="40px" color="grey-4" />
                  <div class="text-caption text-grey-5 q-mt-xs">Enter username to generate QR</div>
                </div>
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('register.fullName') }}</div>
                <q-input v-model="selectedUser.full_name" outlined dense />
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('userConfig.email') }}</div>
                <q-input v-model="selectedUser.email" outlined dense />
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('userConfig.role') }}</div>
                <q-select v-model="selectedUser.role" outlined :options="roles" dense emit-value />
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('userConfig.department') }}</div>
                <q-input v-model="selectedUser.department" outlined dense />
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('common.status') }}</div>
                <q-select
                  v-model="selectedUser.status"
                  outlined
                  :options="['Active', 'Inactive']"
                  dense
                  emit-value
                />
              </div>

              <div class="q-mb-md">
                <div class="text-caption">{{ t('login.lastLogin') }}</div>
                <div class="text-subtitle2">{{ formatDateTime(selectedUser.last_login) }}</div>
              </div>
              
              <div class="q-mt-lg">
                <q-expansion-item
                  icon="lock"
                  :label="t('userConfig.changePassword')"
                  header-class="bg-grey-2 text-grey-8"
                  expand-icon-class="text-grey-8"
                  default-closed
                >
                  <q-card>
                    <q-card-section class="q-pa-sm">
                      <q-input 
                        v-model="selectedUser.new_password" 
                        outlined 
                        dense 
                        :label="t('userConfig.newPassword')"
                        type="password"
                        :hint="t('userConfig.keepCurrentPassword')"
                      />
                    </q-card-section>
                  </q-card>
                </q-expansion-item>

                <!-- Badge PIN for QR Login -->
                <q-expansion-item
                  icon="qr_code_scanner"
                  label="Badge PIN (QR Login)"
                  header-class="bg-deep-purple-1 text-deep-purple-9"
                  expand-icon-class="text-deep-purple-7"
                  default-closed
                  class="q-mt-xs"
                >
                  <q-card>
                    <q-card-section class="q-pa-sm">
                      <q-banner dense class="bg-deep-purple-1 text-deep-purple-9 q-mb-sm rounded-borders" style="font-size: 12px;">
                        <template v-slot:avatar><q-icon name="info" color="deep-purple-7" /></template>
                        Set a 4-6 digit PIN for QR badge login on the Login page. Leave blank to keep current. Type a space to clear.
                      </q-banner>
                      <q-input 
                        v-model="selectedUser.badge_pin" 
                        outlined 
                        dense 
                        label="Badge PIN (4-6 digits)"
                        type="password"
                        maxlength="8"
                        hint="e.g. 1234 — Used with QR badge scan on Login page"
                        :rules="[v => !v || (v.length >= 4 && /^\d+$/.test(v)) || 'Must be 4-8 digits']"
                      >
                        <template v-slot:prepend><q-icon name="pin" color="deep-purple-7" /></template>
                        <template v-slot:append>
                          <q-btn v-if="selectedUser.badge_pin" flat round dense icon="clear" size="xs" color="grey-6"
                            @click="selectedUser.badge_pin = ''" >
                            <q-tooltip>Clear Badge PIN</q-tooltip>
                          </q-btn>
                        </template>
                      </q-input>
                    </q-card-section>
                  </q-card>
                </q-expansion-item>
              </div>
            </div>

            <!-- Right Column: Permissions -->
            <div class="col-12 col-md-6">
              <div class="text-subtitle2 text-weight-bold q-mb-md">{{ t('userConfig.permissions') }}</div>
              <q-separator class="q-mb-md" />

              <div class="column q-gutter-sm">
                <q-checkbox
                  v-for="permission in allPermissions"
                  :key="permission.value"
                  :model-value="hasPermission(permission.value)"
                  :label="permission.label"
                  color="info"
                  @update:model-value="togglePermission(permission.value)"
                />
              </div>
            </div>
          </div>
        </q-card-section>

        <!-- Dialog Actions -->
        <q-card-section class="text-right bg-info text-white">
          <q-btn
            :label="t('common.cancel')"
            flat
            class="q-mr-sm text-white text-weight-bold"
            @click="closeDialog"
          />
          <q-btn
            :label="t('userConfig.saveChanges')"
            color="white"
            text-color="info"
            class="text-weight-bold"
            :loading="isLoading"
            @click="saveUserChanges"
          />
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<style scoped>
:deep(.q-table__card) {
  box-shadow: 0 1px 5px rgba(0, 0, 0, 0.1);
}

/* QR Preview - Create Dialog */
.qr-preview-block {
  background: linear-gradient(135deg, #e8eaf6 0%, #ede7f6 100%);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  border: 1.5px dashed #7986cb;
}
.qr-preview-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #5c6bc0;
  margin-bottom: 10px;
}
.qr-preview-wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.qr-img {
  width: 140px;
  height: 140px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(63,81,181,0.18);
  background: white;
  padding: 6px;
}
.qr-username-badge {
  font-size: 13px;
  font-weight: 700;
  color: #3f51b5;
  background: white;
  border-radius: 20px;
  padding: 3px 14px;
  letter-spacing: 0.5px;
}

/* QR Section - Manage Dialog */
.qr-manage-block {
  background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  border: 1.5px solid #9fa8da;
}
.qr-manage-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #5c6bc0;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.qr-manage-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.qr-manage-img {
  width: 160px;
  height: 160px;
  border-radius: 10px;
  box-shadow: 0 2px 16px rgba(63,81,181,0.2);
  background: white;
  padding: 8px;
}
.qr-manage-name {
  font-size: 14px;
  font-weight: 700;
  color: #1a237e;
}
.qr-manage-user {
  font-size: 12px;
  color: #5c6bc0;
  background: white;
  border-radius: 20px;
  padding: 2px 12px;
}
.qr-manage-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  opacity: 0.6;
}
</style>

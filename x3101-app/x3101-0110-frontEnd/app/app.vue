<script setup lang="ts">
const { hasPermission, user, logout } = useAuth()
const { t, toggleLocale, localeFlag, localeName } = useI18n()
const $q = useQuasar()

// Zoom control
const ZOOM_KEY = 'app-zoom-level'
const zoomLevel = ref(1.5)

const applyZoom = () => {
  document.documentElement.style.zoom = String(zoomLevel.value)
  localStorage.setItem(ZOOM_KEY, String(zoomLevel.value))
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
  { label: '210%', value: 2.1 },
  { label: '220%', value: 2.2 },
  { label: '230%', value: 2.3 },
  { label: '240%', value: 2.4 },
  { label: '250%', value: 2.5 },
]

watch(zoomLevel, applyZoom)
onMounted(() => {
  const stored = localStorage.getItem(ZOOM_KEY)
  if (stored) {
    zoomLevel.value = parseFloat(stored)
  } else {
    applyZoom()
  }
})

const handleLogout = async () => {
  await logout()
  $q.notify({
    type: 'info',
    message: t('nav.loggedOut'),
    position: 'top',
  })
  navigateTo('/')
}

const printScreen = () => {
  window.print()
}

const goToPlant = (plant: number) => {
  window.location.href = `/x61-MixingControl?plant=${plant}`
}

</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white" height-hint="98">
      <q-toolbar>
        <q-toolbar-title>
          <div class="row items-center q-gutter-sm">
            <img src="/x_logo-192.png" alt="xMixing" style="height: 38px; display: block;" />
          </div>
        </q-toolbar-title>

        <!-- Zoom Control -->
        <div class="row items-center q-mr-md gt-xs" style="min-width: 200px;">
          <q-icon name="zoom_out" size="xs" class="q-mr-xs" />
          <q-slider v-model="zoomLevel" :min="0.8" :max="2.5" :step="0.1" color="white" dense style="flex: 1;" />
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

      <q-tabs align="left" dense>
        <q-route-tab to="/" icon="home" :label="t('nav.home')" />

        <q-route-tab
          to="/x55-ProductionPlan"
          icon="calendar_month"
          label="PRODUCTION PLAN"
          v-if="hasPermission('production_list')"
        />

        <q-route-tab
          to="/x56-SkuView"
          icon="science"
          label="SKU"
          v-if="hasPermission('production_list')"
        />

        <q-route-tab
          to="/x60-CheckForProduction"
          icon="fact_check"
          label="CHECK FOR PRODUCTION"
          v-if="hasPermission('production_list')"
        />

        <q-btn-dropdown
          flat
          no-caps
          stretch
          icon="precision_manufacturing"
          label="MIXING CONTROL"
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
        <q-route-tab to="/x89-UserConfig" icon="manage_accounts" :label="t('nav.user')" v-if="hasPermission('admin')" />
        <q-route-tab to="/x100-PlantMonitor" icon="monitor" label="Plant Monitor" />
        <q-route-tab to="/x70-ProductionReport" icon="assessment" label="PRODUCTION REPORT" />
        <q-route-tab to="/x71-MixingReport" icon="description" label="MIXING REPORT" />
        <q-route-tab to="/x99-About" icon="info" :label="t('nav.about')" />
      </q-tabs>
    </q-header>

    <q-page-container style="padding-top: 105px !important;">
      <NuxtPage />
    </q-page-container>
  </q-layout>
</template>

<style>
body {
  overflow: hidden !important;
}
/* Global styles if needed */
</style>

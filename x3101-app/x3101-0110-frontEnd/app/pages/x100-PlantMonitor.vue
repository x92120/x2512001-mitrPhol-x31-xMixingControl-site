<template>
  <q-page padding class="monitor-page bg-blue-grey-1">
    <div class="row items-center q-mb-xl q-mt-sm">
      <q-icon name="precision_manufacturing" size="3rem" color="primary" class="q-mr-md" />
      <div class="text-h3 text-grey-9 text-weight-bolder" style="letter-spacing: 1px;">Plant Production Monitor</div>
      <q-space />
      <q-chip 
        :color="isConnected ? 'positive' : 'negative'" 
        text-color="white" 
        :icon="isConnected ? 'wifi' : 'wifi_off'"
        size="lg"
        class="shadow-4 text-weight-bold shadow-soft"
      >
        Gate Way {{ connectionStatus }}
      </q-chip>
    </div>

    <div class="row q-col-gutter-lg justify-center">
      <!-- Plant Cards -->
      <div v-for="id in ['1', '2', '3']" :key="id" class="col-12 col-md-4">
        <q-card class="plant-card bg-white" :class="{'offline-dim': !plantsData[id]?.last_update}">
          <!-- Header Area -->
          <div class="plant-header q-pa-md" :class="`bg-gradient-${id}`">
            <div class="row items-center justify-between">
              <div class="text-h5 text-white text-weight-bolder">MIXING PLANT {{ id }}</div>
              <q-badge :color="plantsData[id]?.last_update ? 'positive' : 'blue-grey-4'" align="middle" class="text-weight-bold text-caption shadow-2">
                {{ plantsData[id]?.last_update ? 'ONLINE' : 'STANDBY' }}
              </q-badge>
            </div>
            <div class="row items-center q-mt-md">
              <q-icon name="favorite" color="white" size="14px" class="q-mr-xs" :class="{'heartbeat-anim text-pink-2': plantsData[id]?.watchdog}" />
              <span class="text-caption text-white q-mr-sm tech-font">{{ plantsData[id]?.watchdog || 0 }}</span>
              <q-linear-progress 
                :value="(plantsData[id]?.watchdog || 0) / 100" 
                color="white" 
                track-color="transparent" 
                class="watchdog-bar"
              />
            </div>
            <div class="text-caption text-white q-mt-xs text-right tech-font" style="opacity: 0.85">
              LAST UPDATE: {{ plantsData[id]?.last_update || '--:--:--' }}
            </div>
          </div>
          
          <q-card-section class="q-pa-lg">
            
            <!-- Step Progress -->
            <div class="row items-center q-col-gutter-x-md q-mb-lg bg-blue-grey-1 q-pa-md rounded-borders shadow-inset">
              <div class="col-6 text-center border-right-light">
                <div class="text-overline text-grey-6 text-weight-bold">CURRENT STEP</div>
                <div class="text-h4 text-primary text-weight-bolder">{{ plantsData[id]?.Step_no || 0 }}</div>
              </div>
              <div class="col-6 text-center">
                <div class="text-overline text-grey-6 text-weight-bold">STEP TIMER</div>
                <div class="text-h4 text-cyan-8 text-weight-bolder">{{ plantsData[id]?.Step_Timer || 0 }}<span class="text-subtitle1 text-grey-6 q-ml-xs">s</span></div>
              </div>
            </div>

            <!-- Dashboard Metrics -->
            <div class="row q-col-gutter-md">
              
              <!-- Volume -->
              <div class="col-6">
                <q-card class="metric-card bg-white text-grey-9 border-subtle">
                  <q-card-section>
                    <div class="row items-center q-mb-sm">
                      <div class="icon-bubble bg-blue-1 text-blue-7 q-mr-xs">
                        <q-icon name="water_drop" size="xs"/>
                      </div>
                      <div class="text-caption text-grey-6 text-weight-bold">VOLUME</div>
                    </div>
                    <div class="text-h5 text-weight-bold">{{ plantsData[id]?.Mixing_Tank_Volume || 0 }} <span class="text-body2 text-grey-5">kg</span></div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- Temperature -->
              <div class="col-6">
                <q-card class="metric-card bg-white text-grey-9 border-subtle">
                  <q-card-section>
                    <div class="row items-center q-mb-sm">
                      <div class="icon-bubble bg-orange-1 text-orange-7 q-mr-xs">
                        <q-icon name="thermostat" size="xs"/>
                      </div>
                      <div class="text-caption text-grey-6 text-weight-bold">TEMP</div>
                    </div>
                    <div class="text-h5 text-weight-bold" :class="getTempColor(plantsData[id]?.Mixing_Tank_Temperature)">
                      {{ plantsData[id]?.Mixing_Tank_Temperature || 0 }} <span class="text-body2 text-grey-5">°C</span>
                    </div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- Agitator Speed -->
              <div class="col-6">
                <q-card class="metric-card bg-white text-grey-9 border-subtle">
                  <q-card-section>
                    <div class="row items-center q-mb-sm">
                      <div class="icon-bubble bg-amber-1 text-amber-8 q-mr-xs">
                        <q-icon name="autorenew" size="xs" :class="{'spin-anim': (plantsData[id]?.MixingTank_Agitator_Speed || 0) > 0}"/>
                      </div>
                      <div class="text-caption text-grey-6 text-weight-bold">AGITATOR</div>
                    </div>
                    <div class="text-h5 text-weight-bold">{{ plantsData[id]?.MixingTank_Agitator_Speed || 0 }} <span class="text-body2 text-grey-5">RPM</span></div>
                  </q-card-section>
                </q-card>
              </div>

              <!-- High Shear Speed -->
              <div class="col-6">
                <q-card class="metric-card bg-white text-grey-9 border-subtle">
                  <q-card-section>
                    <div class="row items-center q-mb-sm">
                      <div class="icon-bubble bg-red-1 text-red-6 q-mr-xs">
                        <q-icon name="storm" size="xs" :class="{'fast-spin-anim': (plantsData[id]?.HighShare_Speed || 0) > 0}"/>
                      </div>
                      <div class="text-caption text-grey-6 text-weight-bold">HIGH SHEAR</div>
                    </div>
                    <div class="text-h5 text-weight-bold">{{ plantsData[id]?.HighShare_Speed || 0 }} <span class="text-body2 text-grey-5">RPM</span></div>
                  </q-card-section>
                </q-card>
              </div>

            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useMQTT } from '~/composables/useMQTT'

const { connect, disconnect, isConnected, connectionStatus, plantsData } = useMQTT()

onMounted(() => {
  connect()
})

onUnmounted(() => {
  disconnect()
})

const getTempColor = (temp: number | undefined) => {
  const t = temp || 0
  if (t > 80) return 'text-negative'
  if (t > 50) return 'text-warning'
  return 'text-green-8'
}
</script>

<style scoped>
.monitor-page {
  min-height: 100vh;
}

.plant-card {
  border-radius: 16px;
  overflow: hidden;
  border: none;
  box-shadow: 0 8px 24px rgba(100, 110, 140, 0.15);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.plant-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 15px 35px rgba(100, 110, 140, 0.25) !important;
}

.offline-dim {
  opacity: 0.65;
  filter: grayscale(20%);
}

.bg-gradient-1 { background: linear-gradient(135deg, #1976D2, #0D47A1); }
.bg-gradient-2 { background: linear-gradient(135deg, #00796B, #004D40); }
.bg-gradient-3 { background: linear-gradient(135deg, #303F9F, #1A237E); }

.plant-header {
  box-shadow: inset 0 -5px 15px rgba(0,0,0,0.1);
}

.metric-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04) !important;
  transition: all 0.2s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.08) !important;
}

.border-subtle {
  border: 1px solid #eef1f5;
}

.border-right-light {
  border-right: 1px solid rgba(0,0,0,0.06);
}

.shadow-inset {
  box-shadow: inset 0 2px 5px rgba(0,0,0,0.03);
}

.shadow-soft {
  box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
}

.icon-bubble {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tech-font {
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
}

.watchdog-bar {
  border-radius: 4px;
  height: 6px;
  flex: 1;
  background: rgba(0,0,0,0.15);
}

@keyframes beat {
  0% { transform: scale(1); }
  15% { transform: scale(1.3); }
  30% { transform: scale(1); }
  45% { transform: scale(1.15); }
  60% { transform: scale(1); }
  100% { transform: scale(1); }
}

.heartbeat-anim {
  animation: beat 1s infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin-anim {
  animation: spin 3s linear infinite;
}

.fast-spin-anim {
  animation: spin 0.8s linear infinite;
}
</style>

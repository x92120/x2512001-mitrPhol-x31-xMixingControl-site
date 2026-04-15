<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '~/composables/useAuth'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'

const router = useRouter()
const route = useRoute()
const $q = useQuasar()
const { hasPermission, user, getAuthHeader } = useAuth()
const { t } = useI18n()

// ── Helpers ──
const fmtDT = (d: any) => {
  if (!d) return '-'
  const dt = new Date(d)
  return isNaN(dt.getTime()) ? d : dt.toLocaleString('en-GB')
}

// ── Reactive State ──
const counts = ref({ skus: 0, stock: 0, batches: 0, productions: 0 })
const recentActivities = ref<any[]>([])
const systemStatus = ref({
  dbStatus: 'Operational', uptime: '99.9%', sync: 'Real-time',
  storageUsed: 0, storageTotal: 100, storagePercent: 0, lastBackup: 'Unknown'
})

// ── API Fetch (Parallel) ──
const apiFetch = (path: string) =>
  fetch(`${appConfig.apiBaseUrl}${path}`, { headers: getAuthHeader() as Record<string, string> })
    .then(r => r.ok ? r.json() : [])
    .catch(() => [])

const fetchDashboard = async () => {
  const [skus, intakes, batches, plansResp] = await Promise.all([
    apiFetch('/skus/'),
    apiFetch('/ingredient-intake-lists/'),
    apiFetch('/production-batches/'),
    apiFetch('/production-plans/?status=all')
  ])
  const plans = plansResp?.plans || plansResp || []

  // Counts — only uses `status` field from each record
  counts.value = {
    skus: skus.filter((s: any) => s.status === 'Active').length,
    stock: intakes.filter((i: any) => i.status === 'Active').length,
    batches: batches.filter((b: any) => ['Pending', 'Planned', 'Created'].includes(b.status)).length,
    productions: plans.filter((p: any) => ['In Progress', 'Running', 'Started'].includes(p.status)).length
  }

  // Recent Activities — only uses: created_at, sku_name, creat_by, intake_at, mat_sap_code, material_description, intake_vol, uom, intake_by, updated_at, batch_id, status, done
  const acts: any[] = []
  skus.forEach((s: any) => s.created_at && acts.push({
    id: `sku-${s.id}`, title: 'New SKU Created', icon: 'add_circle', color: 'blue',
    description: `SKU: ${s.sku_name}`, time: s.created_at, ts: new Date(s.created_at).getTime(),
    user: s.creat_by || 'System'
  }))
  intakes.forEach((i: any) => i.intake_at && acts.push({
    id: `ing-${i.id}`, title: 'Ingredient Replenishment', icon: 'local_shipping', color: 'purple',
    description: `${i.material_description || i.mat_sap_code} received: ${i.intake_vol} ${i.uom || 'kg'}`,
    time: i.intake_at, ts: new Date(i.intake_at).getTime(), user: i.intake_by || 'Warehouse'
  }))
  batches.forEach((b: any) => {
    const time = b.updated_at || b.created_at
    if (!time) return
    const done = b.status === 'Completed' || b.done
    acts.push({
      id: `batch-${b.id}`, title: done ? 'Batch Completed' : `Batch ${b.status}`,
      icon: done ? 'check_circle' : 'play_circle', color: done ? 'green' : 'orange',
      description: `Batch ${b.batch_id} — ${b.status}`, time, ts: new Date(time).getTime(), user: 'System'
    })
  })
  recentActivities.value = acts.sort((a, b) => b.ts - a.ts).slice(0, 10).map(a => ({ ...a, time: fmtDT(a.time) }))
}

const fetchSystemStatus = async () => {
  try {
    const data = await apiFetch('/server-status')
    if (data && !Array.isArray(data)) {
      systemStatus.value = {
        dbStatus: data.status || 'Operational', uptime: data.uptime || '99.9%', sync: 'Real-time',
        storageUsed: data.disk_usage_gb || 0, storageTotal: data.disk_total_gb || 100,
        storagePercent: (data.disk_usage_gb || 0) / (data.disk_total_gb || 100),
        lastBackup: data.last_backup ? fmtDT(data.last_backup) : '2 hours ago'
      }
    }
  } catch { /* silent */ }
}

onMounted(() => {
  if (route.query.error === 'no-permission') {
    $q.notify({ type: 'negative', message: t('home.accessDenied'), position: 'top', timeout: 3000 })
    router.replace({ query: {} })
  }
  fetchDashboard()
  fetchSystemStatus()
})

// ── Stats Config ──
const stats = computed(() => [


  { label: t('home.pendingBatches'), value: counts.value.batches, icon: 'pending_actions',
    grad: 'grad-amber', glow: 'glow-amber', iconBg: 'rgba(245,158,11,.2)',
    path: '/x30-PreBatch', perm: 'prepare_batch', desc: t('home.batchesWaiting') },
  { label: t('home.activeProductions'), value: counts.value.productions, icon: 'precision_manufacturing',
    grad: 'grad-violet', glow: 'glow-violet', iconBg: 'rgba(139,92,246,.2)',
    path: '/x40-ProductionPlan', perm: 'production_planning', desc: t('home.monitorProduction') },
])



const go = (path: string) => router.push(path)
const ok = (perm: string) => !!(user.value && hasPermission(perm))
</script>

<template>
  <q-page class="dash-page">
    <!-- Background Orbs -->
    <div class="bg-orbs"><div class="orb o1" /><div class="orb o2" /><div class="orb o3" /></div>

    <div class="dash q-pa-lg">
      <!-- Welcome Banner -->
      <div class="welcome q-mb-xl">
        <div class="welcome-inner">
          <div class="row items-center no-wrap">
            <div class="col">
              <div class="row items-center q-mb-sm">
                <div class="avatar-ring q-mr-lg">
                  <div class="avatar">{{ user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U' }}</div>
                </div>
                <div>
                  <div class="w-title">{{ t('home.welcome') }}, {{ user?.full_name || user?.username || t('home.guest') }}</div>
                  <div class="w-sub">{{ user?.role || t('home.guestUser') }} • {{ user?.department || t('home.production') }}</div>
                </div>
              </div>
              <div class="w-desc q-mt-sm">{{ t('home.manageDesc') }}</div>
              <div class="w-badges q-mt-md">
                <span class="badge badge-green"><span class="dot-pulse" />{{ t('home.active') }}</span>
                <span class="badge-sep">|</span>
                <span class="badge badge-blue"><q-icon name="dns" size="14px" class="q-mr-xs" />{{ t('home.systemOperational') }}</span>
              </div>
            </div>
            <div class="col-auto q-pl-md gt-sm">
              <img src="/images/xDev_WeAreWeCan.svg" alt="xDev" style="width:320px;filter:drop-shadow(0 0 20px rgba(255,255,255,.1))" />
            </div>
          </div>
        </div>
      </div>

      <!-- Stat Cards -->
      <div class="row q-mb-xl q-col-gutter-lg">
        <div v-for="(s, i) in stats" :key="s.label" class="col-12 col-sm-6 col-lg-3">
          <div class="stat" :class="[s.grad, s.glow, ok(s.perm) ? 'clickable' : 'locked']"
               @click="ok(s.perm) && go(s.path)" :style="{ animationDelay: `${i * .1}s` }">
            <div class="stat-inner">
              <div class="row items-start justify-between q-mb-md">
                <div class="stat-icon" :style="{ background: s.iconBg }">
                  <q-icon :name="s.icon" size="28px" color="white" />
                </div>
                <q-badge v-if="!ok(s.perm)" color="rgba(255,255,255,.15)" text-color="white" class="lock-badge">
                  <q-icon name="lock" size="12px" class="q-mr-xs" />{{ t('common.noAccess') }}
                </q-badge>
              </div>
              <div class="stat-val">{{ s.value }}</div>
              <div class="stat-lbl">{{ s.label }}</div>
            </div>
            <div class="shimmer" />
            <q-tooltip v-if="ok(s.perm)">{{ s.desc }}</q-tooltip>
          </div>
        </div>
      </div>



      <!-- Activities + System Status -->
      <div class="row q-col-gutter-lg">
        <div class="col-12 col-md-7">
          <div class="glass">
            <div class="glass-head">
              <q-icon name="history" size="22px" class="q-mr-sm" style="color:#60a5fa" />
              <span class="sec-title">{{ t('home.recentActivities') }}</span>
              <q-space />
              <q-badge v-if="recentActivities.length" color="rgba(96,165,250,.2)" text-color="white">{{ recentActivities.length }}</q-badge>
            </div>
            <q-separator class="glass-sep" />
            <div class="act-list">
              <div v-for="(a, i) in recentActivities" :key="a.id" class="act-item" :style="{ animationDelay: `${i * .05}s` }">
                <div class="act-ico" :class="`act-${a.color}`"><q-icon :name="a.icon" size="18px" color="white" /></div>
                <div class="act-body">
                  <div class="act-title">{{ a.title }}</div>
                  <div class="act-desc">{{ a.description }}</div>
                  <div class="act-meta"><q-icon name="person" size="12px" class="q-mr-xs" />{{ a.user }} • {{ a.time }}</div>
                </div>
              </div>
              <div v-if="!recentActivities.length" class="act-empty">
                <q-icon name="inbox" size="48px" style="color:rgba(255,255,255,.15)" />
                <div class="q-mt-sm" style="color:rgba(255,255,255,.4)">{{ t('home.noActivities') }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-12 col-md-5">
          <div class="glass">
            <div class="glass-head">
              <q-icon name="monitor_heart" size="22px" class="q-mr-sm" style="color:#34d399" />
              <span class="sec-title">{{ t('home.systemStatus') }}</span>
            </div>
            <q-separator class="glass-sep" />
            <div class="sys-list">
              <div class="sys-row"><div class="sys-left"><span class="dot dot-g" />{{ t('home.database') }}</div><span class="sys-ok">{{ systemStatus.dbStatus }}</span></div>
              <div class="sys-row"><div class="sys-left"><span class="dot dot-b" />{{ t('home.sync') }}</div><span class="sys-ok">{{ systemStatus.sync }}</span></div>
              <div class="sys-row"><div class="sys-left"><span class="dot dot-g" />{{ t('home.uptime') }}</div><span class="sys-ok">{{ systemStatus.uptime }}</span></div>
              <div class="sys-row">
                <div class="sys-left"><q-icon name="storage" size="16px" style="color:#fbbf24" class="q-mr-sm" />{{ t('home.storageUsage') }}</div>
                <span class="sys-warn">{{ systemStatus.storageUsed }} / {{ systemStatus.storageTotal }} GB</span>
              </div>
              <div class="sys-bar"><div class="sys-fill" :style="{ width: (systemStatus.storagePercent * 100) + '%' }" /></div>
              <div class="sys-row" style="border:0">
                <div class="sys-left"><q-icon name="backup" size="16px" style="color:#a78bfa" class="q-mr-sm" />{{ t('home.lastBackup') }}</div>
                <span class="sys-muted">{{ systemStatus.lastBackup }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
/* ── Page ── */
.dash-page { background: #060918; min-height: 100vh; position: relative; overflow: hidden; }
.dash { position: relative; z-index: 1; }

/* ── Orbs ── */
.bg-orbs { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.orb { position: absolute; border-radius: 50%; filter: blur(100px); opacity: .15; animation: orb 20s ease-in-out infinite; }
.o1 { width: 500px; height: 500px; background: #3b82f6; top: -100px; left: -100px; animation-duration: 18s; }
.o2 { width: 400px; height: 400px; background: #8b5cf6; bottom: -50px; right: -50px; animation-duration: 22s; animation-delay: -5s; }
.o3 { width: 350px; height: 350px; background: #06b6d4; top: 50%; left: 50%; animation-duration: 25s; animation-delay: -10s; }
@keyframes orb { 0%,100%{transform:translate(0,0) scale(1)} 25%{transform:translate(40px,-30px) scale(1.05)} 50%{transform:translate(-20px,20px) scale(.95)} 75%{transform:translate(30px,40px) scale(1.02)} }

/* ── Welcome ── */
.welcome { border-radius: 20px; background: linear-gradient(135deg,#1e3a8a,#3b82f6 50%,#2563eb); padding: 2px; box-shadow: 0 8px 32px rgba(59,130,246,.3); }
.welcome-inner { border-radius: 18px; background: linear-gradient(135deg,rgba(30,58,138,.95),rgba(59,130,246,.85)); padding: 32px 36px; backdrop-filter: blur(20px); }
.avatar-ring { width: 64px; height: 64px; border-radius: 50%; padding: 3px; background: linear-gradient(135deg,#60a5fa,#a78bfa); box-shadow: 0 0 20px rgba(96,165,250,.4); }
.avatar { width: 100%; height: 100%; border-radius: 50%; background: #1e293b; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; font-weight: 700; color: #93c5fd; }
.w-title { font-size: 1.8rem; font-weight: 800; color: #fff; letter-spacing: -.02em; }
.w-sub { font-size: .95rem; color: rgba(191,219,254,.8); font-weight: 500; }
.w-desc { color: rgba(191,219,254,.65); font-size: .9rem; }
.w-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.badge { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600; }
.badge-green { background: rgba(34,197,94,.15); color: #4ade80; border: 1px solid rgba(34,197,94,.3); }
.badge-blue { background: rgba(96,165,250,.12); color: #93c5fd; border: 1px solid rgba(96,165,250,.2); }
.badge-sep { color: rgba(255,255,255,.15); }
.dot-pulse { width: 6px; height: 6px; border-radius: 50%; background: #4ade80; margin-right: 6px; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.3)} }

/* ── Stat Cards ── */
.stat { border-radius: 16px; padding: 2px; position: relative; overflow: hidden; animation: up .6s ease both; }
.stat-inner { border-radius: 14px; padding: 24px; background: rgba(15,23,42,.85); backdrop-filter: blur(20px); position: relative; z-index: 1; }
.grad-blue { background: linear-gradient(135deg,#1d4ed8,#3b82f6); }
.grad-emerald { background: linear-gradient(135deg,#059669,#10b981); }
.grad-amber { background: linear-gradient(135deg,#d97706,#f59e0b); }
.grad-violet { background: linear-gradient(135deg,#7c3aed,#8b5cf6); }
.glow-blue { box-shadow: 0 8px 30px rgba(59,130,246,.25); }
.glow-emerald { box-shadow: 0 8px 30px rgba(16,185,129,.25); }
.glow-amber { box-shadow: 0 8px 30px rgba(245,158,11,.25); }
.glow-violet { box-shadow: 0 8px 30px rgba(139,92,246,.25); }
.stat.clickable { cursor: pointer; transition: transform .3s, box-shadow .3s; }
.stat.clickable:hover { transform: translateY(-6px) scale(1.02); }
.stat.clickable:hover .shimmer { opacity: 1; transform: translateX(100%); }
.glow-blue.clickable:hover { box-shadow: 0 16px 48px rgba(59,130,246,.4); }
.glow-emerald.clickable:hover { box-shadow: 0 16px 48px rgba(16,185,129,.4); }
.glow-amber.clickable:hover { box-shadow: 0 16px 48px rgba(245,158,11,.4); }
.glow-violet.clickable:hover { box-shadow: 0 16px 48px rgba(139,92,246,.4); }
.stat.locked { opacity: .5; filter: grayscale(40%); cursor: not-allowed; }
.shimmer { position: absolute; inset: 0; background: linear-gradient(105deg,transparent 40%,rgba(255,255,255,.08) 50%,transparent 60%); opacity: 0; transform: translateX(-100%); transition: transform .8s, opacity .3s; z-index: 2; pointer-events: none; }
.stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.lock-badge { font-size: .7rem; padding: 3px 8px; border-radius: 8px; }
.stat-val { font-size: 2.4rem; font-weight: 800; color: #fff; line-height: 1; margin-top: 8px; letter-spacing: -.02em; }
.stat-lbl { font-size: .82rem; color: rgba(255,255,255,.5); font-weight: 500; margin-top: 4px; text-transform: uppercase; letter-spacing: .05em; }
@keyframes up { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }

/* ── Section ── */
.sec-head { display: flex; align-items: center; }
.sec-title { font-size: 1.15rem; font-weight: 700; color: rgba(255,255,255,.9); }

/* ── Quick Access ── */
.qa { border-radius: 14px; padding: 20px; position: relative; overflow: hidden; animation: up .6s ease both; display: flex; flex-direction: column; min-height: 140px; }
.qa.clickable { cursor: pointer; transition: transform .3s, box-shadow .3s; }
.qa.clickable:hover { transform: translateY(-4px); box-shadow: 0 12px 36px rgba(0,0,0,.3); }
.qa.clickable:hover .qa-arrow { transform: translateX(4px); opacity: 1; }
.qa.locked { opacity: .4; filter: grayscale(50%); cursor: not-allowed; }
.qa-1 { background: linear-gradient(135deg,#0e7490,#06b6d4); }
.qa-2 { background: linear-gradient(135deg,#0284c7,#38bdf8); }
.qa-3 { background: linear-gradient(135deg,#b45309,#f59e0b); }
.qa-4 { background: linear-gradient(135deg,#4d7c0f,#84cc16); }
.qa-icon { width: 44px; height: 44px; border-radius: 12px; background: rgba(255,255,255,.15); display: flex; align-items: center; justify-content: center; margin-bottom: 12px; }
.qa-label { font-size: .95rem; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: .03em; }
.qa-desc { font-size: .75rem; color: rgba(255,255,255,.6); margin-top: 4px; line-height: 1.3; }
.qa-arrow { position: absolute; bottom: 16px; right: 16px; color: rgba(255,255,255,.4); transition: transform .3s, opacity .3s; opacity: .5; }

/* ── Glass Cards ── */
.glass { border-radius: 16px; background: rgba(15,23,42,.6); border: 1px solid rgba(255,255,255,.06); backdrop-filter: blur(20px); overflow: hidden; }
.glass-head { display: flex; align-items: center; padding: 18px 22px; }
.glass-sep { background: rgba(255,255,255,.06) !important; }

/* ── Activities ── */
.act-list { padding: 8px 16px 16px; max-height: 380px; overflow-y: auto; }
.act-list::-webkit-scrollbar { width: 4px; }
.act-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 4px; }
.act-item { display: flex; gap: 14px; padding: 12px 8px; border-radius: 10px; transition: background .2s; animation: up .4s ease both; }
.act-item:hover { background: rgba(255,255,255,.03); }
.act-ico { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.act-blue { background: rgba(59,130,246,.2); }
.act-purple { background: rgba(139,92,246,.2); }
.act-green { background: rgba(34,197,94,.2); }
.act-orange { background: rgba(245,158,11,.2); }
.act-body { flex: 1; min-width: 0; }
.act-title { font-size: .85rem; font-weight: 600; color: rgba(255,255,255,.9); }
.act-desc { font-size: .78rem; color: rgba(255,255,255,.45); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.act-meta { font-size: .7rem; color: rgba(255,255,255,.3); margin-top: 4px; display: flex; align-items: center; }
.act-empty { display: flex; flex-direction: column; align-items: center; padding: 48px 0; }

/* ── System Status ── */
.sys-list { padding: 8px 22px 16px; }
.sys-row { display: flex; justify-content: space-between; align-items: center; padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,.05); }
.sys-left { display: flex; align-items: center; gap: 10px; font-size: .85rem; color: rgba(255,255,255,.7); font-weight: 500; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot-g { background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,.4); }
.dot-b { background: #60a5fa; box-shadow: 0 0 8px rgba(96,165,250,.4); }
.sys-ok { font-size: .82rem; font-weight: 600; color: #4ade80; }
.sys-warn { font-size: .82rem; font-weight: 600; color: #fbbf24; }
.sys-muted { font-size: .82rem; font-weight: 500; color: rgba(255,255,255,.5); }
.sys-bar { height: 6px; border-radius: 6px; background: rgba(255,255,255,.08); overflow: hidden; }
.sys-fill { height: 100%; border-radius: 6px; background: linear-gradient(90deg,#fbbf24,#f59e0b); transition: width 1s; min-width: 4px; }
</style>

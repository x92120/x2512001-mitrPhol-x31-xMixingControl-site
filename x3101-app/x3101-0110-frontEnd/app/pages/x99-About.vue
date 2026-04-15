<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'

const $q = useQuasar()
const { t, reloadTranslations } = useI18n()

const applicationVersion = '1.0.0'
const releaseDate = 'January 2026'
const developerName = 'devTeam@xDev.co.th'

const features = computed(() => [
  {
    icon: 'inventory',
    title: t('about.featIngTitle'),
    description: t('about.featIngDesc'),
  },
  {
    icon: 'menu_book',
    title: t('about.featSkuTitle'),
    description: t('about.featSkuDesc'),
  },
  {
    icon: 'shopping_cart',
    title: t('about.featPreBatchTitle'),
    description: t('about.featPreBatchDesc'),
  },
  {
    icon: 'show_chart',
    title: t('about.featProdTitle'),
    description: t('about.featProdDesc'),
  },
])

const technologies = ref([
  { name: 'Nuxt 4', version: '4.3.0' },
  { name: 'Vue 3', version: '3.5.27' },
  { name: 'Quasar Framework', version: '2.18.6' },
  { name: 'Vite', version: 'Nuxt Built-in' },
  { name: 'Vue Router', version: '4.6.4' },
  { name: 'TypeScript', version: 'Latest' },
])

// ==========================================
// Translation Editor
// ==========================================
interface TranslationRow {
  key: string
  en: string
  th: string
  section: string
}

const allTranslations = ref<Record<string, Record<string, string>>>({})
const translationRows = ref<TranslationRow[]>([])
const isLoadingTranslations = ref(false)
const translationSearch = ref('')
const translationSectionFilter = ref('all')
const showTranslationEditor = ref(false)
const backendStats = ref({ total_keys: 0, sections_count: 0 })

// Edit dialog
const showEditDialog = ref(false)
const editKey = ref('')
const editEn = ref('')
const editTh = ref('')
const isSaving = ref(false)

// Fetch all translations from API
const fetchAllTranslations = async () => {
  isLoadingTranslations.value = true
  try {
    const statsRes = await fetch(`${appConfig.apiBaseUrl}/translations/stats`)
    if (statsRes.ok) {
        backendStats.value = await statsRes.json()
    }

    const res = await fetch(`${appConfig.apiBaseUrl}/translations/`)
    if (res.ok) {
      const data = await res.json()
      allTranslations.value = data

      // Build rows: merge EN and TH by key
      const allKeys = new Set<string>()
      if (data.en) Object.keys(data.en).forEach(k => allKeys.add(k))
      if (data.th) Object.keys(data.th).forEach(k => allKeys.add(k))

      translationRows.value = Array.from(allKeys)
        .sort()
        .map(key => ({
          key,
          en: data.en?.[key] || '',
          th: data.th?.[key] || '',
          section: key.split('.')[0] || 'common'
        }))
    }
  } catch (e) {
    console.error('Failed to fetch translations', e)
    $q.notify({ type: 'negative', message: t('about.failedLoadTranslations') })
  } finally {
    isLoadingTranslations.value = false
  }
}

// Get unique sections from keys
const sectionOptions = computed(() => {
  const sections = new Set<string>()
  translationRows.value.forEach(row => {
    sections.add(row.section)
  })
  return [
    { label: `${t('about.section')}: All (${translationRows.value.length})`, value: 'all' },
    ...Array.from(sections).sort().map(s => {
      const count = translationRows.value.filter(r => r.section === s).length
      return { label: `${s}.json (${count})`, value: s }
    })
  ]
})

// Filtered rows
const filteredTranslationRows = computed(() => {
  let rows = translationRows.value

  // Section filter
  if (translationSectionFilter.value !== 'all') {
    rows = rows.filter(r => r.section === translationSectionFilter.value)
  }

  // Text search
  if (translationSearch.value) {
    const q = translationSearch.value.toLowerCase()
    rows = rows.filter(r =>
      r.key.toLowerCase().includes(q) ||
      r.en.toLowerCase().includes(q) ||
      r.th.toLowerCase().includes(q)
    )
  }

  return rows
})

// Open edit dialog
const openEditDialog = (row: TranslationRow) => {
  editKey.value = row.key
  editEn.value = row.en
  editTh.value = row.th
  showEditDialog.value = true
}

// Save edited translation
const saveTranslation = async () => {
  isSaving.value = true
  try {
    // Update EN
    await fetch(`${appConfig.apiBaseUrl}/translations/en/${editKey.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: editEn.value }),
    })

    // Update TH
    await fetch(`${appConfig.apiBaseUrl}/translations/th/${editKey.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: editTh.value }),
    })

    // Update local data
    const idx = translationRows.value.findIndex(r => r.key === editKey.value)
    const row = idx >= 0 ? translationRows.value[idx] : undefined
    if (row) {
      row.en = editEn.value
      row.th = editTh.value
    }

    // Reload live dictionary in the i18n composable
    await reloadTranslations()

    showEditDialog.value = false
    $q.notify({
      type: 'positive',
      message: `✅ ${t('about.updated')}: ${editKey.value}`,
      position: 'top',
      timeout: 1500,
    })
  } catch (e) {
    console.error('Save error', e)
    $q.notify({ type: 'negative', message: t('about.failedSaveTranslation') })
  } finally {
    isSaving.value = false
  }
}

// Add new key dialog
const showAddDialog = ref(false)
const newKey = ref('')
const newEn = ref('')
const newTh = ref('')

const openAddDialog = () => {
  newKey.value = ''
  newEn.value = ''
  newTh.value = ''
  showAddDialog.value = true
}

const saveNewTranslation = async () => {
  if (!newKey.value) {
    $q.notify({ type: 'warning', message: t('about.keyRequired') })
    return
  }

  isSaving.value = true
  try {
    await fetch(`${appConfig.apiBaseUrl}/translations/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([
        { key: newKey.value, locale: 'en', value: newEn.value },
        { key: newKey.value, locale: 'th', value: newTh.value },
      ]),
    })

    // Add to local rows
    translationRows.value.push({
      key: newKey.value,
      en: newEn.value,
      th: newTh.value,
      section: newKey.value.split('.')[0] || 'common'
    })
    translationRows.value.sort((a, b) => a.key.localeCompare(b.key))

    await reloadTranslations()

    showAddDialog.value = false
    $q.notify({
      type: 'positive',
      message: `✅ ${t('about.added')}: ${newKey.value}`,
      position: 'top',
    })
  } catch (e) {
    $q.notify({ type: 'negative', message: t('about.failedAddTranslation') })
  } finally {
    isSaving.value = false
  }
}

// Stats
const translationStats = computed(() => {
  const total = translationRows.value.length
  const missingTh = translationRows.value.filter(r => !r.th).length
  const missingEn = translationRows.value.filter(r => !r.en).length
  return { ...translationStats, total, missingTh, missingEn, sections: backendStats.value.sections_count }
})

// Table columns
const translationColumns = [
  { name: 'section', label: 'File', field: 'section', align: 'left' as const, sortable: true, style: 'width: 120px; color: #666' },
  { name: 'key', label: t('about.keyLabel'), field: 'key', align: 'left' as const, sortable: true, style: 'width: 250px; font-family: monospace; font-size: 11px; color: #1565c0' },
  { name: 'en', label: '🇬🇧 English', field: 'en', align: 'left' as const, sortable: true },
  { name: 'th', label: '🇹🇭 ไทย', field: 'th', align: 'left' as const, sortable: true },
  { name: 'actions', label: '', field: 'actions', align: 'center' as const, style: 'width: 60px' },
]

onMounted(() => {
  fetchAllTranslations()
})
</script>

<template>
  <q-page class="q-pa-md bg-light-blue-1">
    <!-- Header Section -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card class="bg-gradient text-white shadow-4">
          <q-card-section class="text-center q-py-xl">
            <div class="text-h3 q-mb-md text-weight-bold">xMixing</div>
            <div class="text-subtitle1 q-mb-sm">{{ t('about.subtitle') }}</div>
            <div class="text-caption">
              {{ t('about.version') }} {{ applicationVersion }} | {{ t('about.released') }} {{ releaseDate }}
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- About Description -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card>
          <q-card-section>
            <div class="text-h5 q-mb-md text-weight-bold">{{ t('about.aboutTitle') }}</div>
            <p class="text-body1 q-mb-md">
              {{ t('about.aboutDesc1') }}
            </p>
            <p class="text-body1 q-mb-md">
              {{ t('about.aboutDesc2') }}
            </p>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Key Features Section -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <div class="text-h5 q-mb-md text-weight-bold">{{ t('about.keyFeatures') }}</div>
      </div>
      <div
        v-for="feature in features"
        :key="feature.title"
        class="col-12 col-sm-6 col-md-6 col-lg-3 q-mb-md"
      >
        <q-card class="full-height hover-card">
          <q-card-section class="text-center">
            <q-icon :name="feature.icon" size="3rem" color="light-blue-7" class="q-mb-md" />
            <div class="text-h6 text-weight-bold q-mb-sm">{{ feature.title }}</div>
            <p class="text-caption text-grey-7">{{ feature.description }}</p>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- ====================================================== -->
    <!-- TRANSLATION EDITOR BUTTON                               -->
    <!-- ====================================================== -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-btn
          color="blue-9"
          icon="translate"
          label="Translation Editor / แก้ไขคำแปล"
          unelevated
          class="full-width"
          size="lg"
          @click="showTranslationEditor = true; fetchAllTranslations()"
        >
          <q-badge v-if="translationStats.missingTh > 0" color="orange" floating>
            {{ translationStats.missingTh }}
          </q-badge>
        </q-btn>
      </div>
    </div>

    <!-- ====================================================== -->
    <!-- TRANSLATION EDITOR DIALOG (FULLSCREEN)                  -->
    <!-- ====================================================== -->
    <q-dialog v-model="showTranslationEditor" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card class="column" style="height: 100vh;">
        <!-- Header -->
        <q-card-section class="bg-blue-9 text-white q-py-sm">
          <div class="row items-center justify-between">
            <div class="row items-center q-gutter-sm">
              <q-icon name="translate" size="sm" />
              <div class="text-h6 text-weight-bold">{{ t('about.translationEditor') }} / แก้ไขคำแปล</div>
            </div>
            <div class="row items-center q-gutter-sm">
              <q-badge color="white" text-color="blue-9">
                {{ translationStats.total }} {{ t('about.keys') }}
              </q-badge>
              <q-badge v-if="translationStats.missingTh > 0" color="orange">
                {{ translationStats.missingTh }} {{ t('about.missingTh') }}
              </q-badge>
              <q-btn
                flat round dense
                icon="add"
                color="white"
                @click="openAddDialog"
              >
                <q-tooltip>{{ t('about.addNewKey') }}</q-tooltip>
              </q-btn>
              <q-btn
                flat round dense
                icon="refresh"
                color="white"
                @click="fetchAllTranslations"
                :loading="isLoadingTranslations"
              >
                <q-tooltip>{{ t('about.reloadFromDb') }}</q-tooltip>
              </q-btn>
              <q-btn
                flat round dense
                icon="close"
                color="white"
                v-close-popup
              >
                <q-tooltip>{{ t('common.close') }}</q-tooltip>
              </q-btn>
            </div>
          </div>
        </q-card-section>

        <!-- Filters Bar -->
        <q-card-section class="q-py-sm bg-blue-grey-1">
          <div class="row q-col-gutter-sm items-center">
            <div class="col-12 col-md-4">
              <q-select
                v-model="translationSectionFilter"
                :options="sectionOptions"
                emit-value
                map-options
                outlined
                dense
                bg-color="white"
                :label="t('about.section')"
              >
                <template v-slot:prepend>
                  <q-icon name="folder" color="blue-9" size="xs" />
                </template>
              </q-select>
            </div>
            <div class="col-12 col-md-8">
              <q-input
                v-model="translationSearch"
                outlined
                dense
                :placeholder="t('about.searchPlaceholder')"
                bg-color="white"
                clearable
              >
                <template v-slot:prepend>
                  <q-icon name="search" color="blue-9" size="xs" />
                </template>
              </q-input>
            </div>
          </div>
        </q-card-section>

        <!-- Table (fills remaining space) -->
        <q-card-section class="col q-pa-none" style="overflow: auto;">
          <q-table
            :rows="filteredTranslationRows"
            :columns="translationColumns"
            row-key="key"
            flat
            bordered
            dense
            :loading="isLoadingTranslations"
            :rows-per-page-options="[15, 30, 50, 100, 0]"
            :rows-per-page-label="t('about.rowsPerPage')"
            class="translation-table"
            :filter="translationSearch"
            :filter-method="() => filteredTranslationRows"
            virtual-scroll
            style="height: 100%;"
          >
            <!-- Key column -->
            <template v-slot:body-cell-key="props">
              <q-td :props="props" style="font-family: 'Roboto Mono', monospace; font-size: 12px; color: #1565c0; word-break: break-all;">
                <q-icon v-if="!props.row.th" name="warning" color="orange" size="xs" class="q-mr-xs" />
                {{ props.value }}
              </q-td>
            </template>

            <!-- English column -->
            <template v-slot:body-cell-en="props">
              <q-td :props="props" class="text-grey-9" style="max-width: 350px; word-wrap: break-word; white-space: normal;">
                {{ props.value || '—' }}
              </q-td>
            </template>

            <!-- Thai column -->
            <template v-slot:body-cell-th="props">
              <q-td :props="props" style="max-width: 350px; word-wrap: break-word; white-space: normal;">
                <span v-if="props.value" class="text-grey-9">{{ props.value }}</span>
                <span v-else class="text-orange text-italic">{{ t('about.missing') }}</span>
              </q-td>
            </template>

            <!-- Actions column -->
            <template v-slot:body-cell-actions="props">
              <q-td :props="props">
                <q-btn
                  flat round dense
                  icon="edit"
                  color="blue-9"
                  size="sm"
                  @click="openEditDialog(props.row)"
                >
                  <q-tooltip>{{ t('common.edit') }} / แก้ไข</q-tooltip>
                </q-btn>
              </q-td>
            </template>

            <!-- No data -->
            <template v-slot:no-data>
              <div class="text-center q-pa-lg text-grey-5">
                <q-icon name="translate" size="64px" class="q-mb-md" />
                <div class="text-h6">{{ t('about.noTranslationsFound') }}</div>
                <div class="text-caption">{{ t('about.tryAdjusting') }}</div>
              </div>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- ====================================================== -->
    <!-- EDIT TRANSLATION DIALOG                                 -->
    <!-- ====================================================== -->
    <q-dialog v-model="showEditDialog" persistent>
      <q-card style="min-width: 550px; max-width: 700px" class="q-pa-none">
        <!-- Dialog Header -->
        <q-card-section class="bg-blue-9 text-white q-py-sm">
          <div class="row items-center">
            <q-icon name="edit" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold">{{ t('about.editTranslation') }} / แก้ไขคำแปล</div>
            <q-space />
            <q-btn flat round dense icon="close" color="white" v-close-popup />
          </div>
        </q-card-section>

        <q-card-section class="q-pt-md">
          <!-- Key (read-only) -->
          <q-input
            v-model="editKey"
            outlined
            dense
            readonly
            bg-color="grey-2"
            :label="t('about.keyLabel')"
            class="q-mb-md"
          >
            <template v-slot:prepend>
              <q-icon name="key" color="blue-9" />
            </template>
          </q-input>

          <!-- English Value -->
          <q-input
            v-model="editEn"
            outlined
            dense
            label="🇬🇧 English"
            type="textarea"
            autogrow
            class="q-mb-md"
          >
            <template v-slot:prepend>
              <q-icon name="language" color="blue-7" />
            </template>
          </q-input>

          <!-- Thai Value -->
          <q-input
            v-model="editTh"
            outlined
            dense
            label="🇹🇭 ภาษาไทย"
            type="textarea"
            autogrow
          >
            <template v-slot:prepend>
              <q-icon name="language" color="green-7" />
            </template>
          </q-input>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md bg-grey-1">
          <q-btn flat :label="t('common.cancel') + ' / ยกเลิก'" color="grey" v-close-popup />
          <q-btn
            unelevated
            :label="t('common.save') + ' / บันทึก'"
            color="blue-9"
            icon="save"
            @click="saveTranslation"
            :loading="isSaving"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ====================================================== -->
    <!-- ADD NEW KEY DIALOG                                      -->
    <!-- ====================================================== -->
    <q-dialog v-model="showAddDialog" persistent>
      <q-card style="min-width: 550px; max-width: 700px" class="q-pa-none">
        <q-card-section class="bg-green-8 text-white q-py-sm">
          <div class="row items-center">
            <q-icon name="add_circle" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold">{{ t('about.addNewTranslationKey') }}</div>
            <q-space />
            <q-btn flat round dense icon="close" color="white" v-close-popup />
          </div>
        </q-card-section>

        <q-card-section class="q-pt-md">
          <q-input
            v-model="newKey"
            outlined
            dense
            :label="t('about.keyPlaceholder')"
            class="q-mb-md"
            :hint="t('about.keyHint')"
          >
            <template v-slot:prepend>
              <q-icon name="key" color="green-8" />
            </template>
          </q-input>

          <q-input
            v-model="newEn"
            outlined
            dense
            :label="'🇬🇧 ' + t('about.englishValue')"
            type="textarea"
            autogrow
            class="q-mb-md"
          />

          <q-input
            v-model="newTh"
            outlined
            dense
            :label="'🇹🇭 ' + t('about.thaiValue') + ' (ภาษาไทย)'"
            type="textarea"
            autogrow
          />
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md bg-grey-1">
          <q-btn flat :label="t('common.cancel')" color="grey" v-close-popup />
          <q-btn
            unelevated
            :label="t('about.addKey')"
            color="green-8"
            icon="add"
            @click="saveNewTranslation"
            :loading="isSaving"
            :disable="!newKey"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Technology Stack Section -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card>
          <q-card-section>
            <div class="text-h5 q-mb-md text-weight-bold">{{ t('about.techStack') }}</div>
            <div class="row q-col-gutter-md">
              <div v-for="tech in technologies" :key="tech.name" class="col-12 col-sm-6 col-md-4">
                <q-item class="bg-light-blue-7 text-white rounded-borders">
                  <q-item-section avatar>
                    <q-icon name="code" size="lg" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="text-weight-bold">{{ tech.name }}</q-item-label>
                    <q-item-label caption class="text-grey-3">v{{ tech.version }}</q-item-label>
                  </q-item-section>
                </q-item>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Developer & Copyright Section -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card class="bg-light-blue-7 text-white">
          <q-card-section class="text-center">
            <div class="text-h6 q-mb-md">{{ t('about.developedBy') }}</div>
            <div class="text-body2 q-mb-lg">{{ developerName }}</div>
            <div class="text-body2 q-mb-md">{{ t('about.copyright') }}</div>
            <div class="text-caption">{{ t('about.builtWith') }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Support & Contact Section -->
    <div class="row q-mb-lg">
      <div class="col-12">
        <q-card>
          <q-card-section>
            <div class="text-h5 q-mb-md text-weight-bold">{{ t('about.supportFeedback') }}</div>
            <p class="text-body2 q-mb-md">
              {{ t('about.supportDesc') }}
            </p>
            <div class="row q-gutter-md">
              <q-btn
                color="light-blue-7"
                :label="t('about.contactSupport')"
                icon="email"
                flat
                @click="$q.notify({ message: t('about.supportComingSoon') })"
              />
              <q-btn
                color="light-blue-7"
                :label="t('about.reportIssue')"
                icon="bug_report"
                flat
                @click="$q.notify({ message: t('about.bugReportComingSoon') })"
              />
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.bg-gradient {
  background: linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%);
}

.hover-card {
  transition: all 0.3s ease;
}

.hover-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.translation-table :deep(td),
.translation-table :deep(th) {
  font-size: 13px !important;
}

.translation-table :deep(th) {
  background-color: #e3f2fd;
  font-weight: 700;
  color: #0d47a1;
}

.translation-table :deep(tr:hover td) {
  background-color: #e8f5e9 !important;
}
</style>

export type Locale = 'en' | 'th'
import { ref, computed } from 'vue'
import { appConfig } from '~/appConfig/config'

// Import all local locale JSON files as fallback
import aboutJson from '~/i18n/locales/about.json'
import commonJson from '~/i18n/locales/common.json'
import dashboardJson from '~/i18n/locales/dashboard.json'
import homeJson from '~/i18n/locales/home.json'
import ingConfigJson from '~/i18n/locales/ingConfig.json'
import ingredientJson from '~/i18n/locales/ingredient.json'
import loginJson from '~/i18n/locales/login.json'
import navJson from '~/i18n/locales/nav.json'
import packingJson from '~/i18n/locales/packing.json'
import packingListJson from '~/i18n/locales/packingList.json'
import planJson from '~/i18n/locales/plan.json'
import prebatchJson from '~/i18n/locales/prebatch.json'
import prodPlanJson from '~/i18n/locales/prodPlan.json'
import recheckJson from '~/i18n/locales/recheck.json'
import registerJson from '~/i18n/locales/register.json'
import reportJson from '~/i18n/locales/report.json'
import skuJson from '~/i18n/locales/sku.json'
import soundJson from '~/i18n/locales/sound.json'
import userConfigJson from '~/i18n/locales/userConfig.json'
import whConfigJson from '~/i18n/locales/whConfig.json'
import wrongBoxJson from '~/i18n/locales/wrongBox.json'

// Build local fallback dictionary from JSON files
const localeFiles = [
    aboutJson, commonJson, dashboardJson, homeJson, ingConfigJson,
    ingredientJson, loginJson, navJson, packingJson, packingListJson,
    planJson, prebatchJson, prodPlanJson, recheckJson, registerJson,
    reportJson, skuJson, soundJson, userConfigJson, whConfigJson, wrongBoxJson
]

const localDictionary: Record<string, Record<string, string>> = { en: {}, th: {} }
for (const file of localeFiles) {
    const f = file as Record<string, Record<string, string> | undefined>
    if (f.en) localDictionary.en = { ...localDictionary.en, ...f.en }
    if (f.th) localDictionary.th = { ...localDictionary.th, ...f.th }
}

/**
 * useI18n Composable
 */
export const useI18n = () => {
    // Use useState for instant reactivity (no cookie write delay)
    const locale = useState<Locale>('app_locale', () => {
        if (import.meta.client) {
            return (localStorage.getItem('app_locale') as Locale) || 'en'
        }
        return 'en'
    })

    // Dictionary state - using useState to share across components and sync SSR/Client
    const liveDictionary = useState<Record<string, Record<string, string>>>('i18n_dictionary', () => ({}))
    const isLoaded = useState('i18n_loaded', () => false)

    /**
     * Fetch translations from API
     */
    const fetchTranslations = async () => {
        try {
            const data = await $fetch<Record<string, Record<string, string>>>(`${appConfig.apiBaseUrl}/translations/`)
            if (data) {
                liveDictionary.value = data
                isLoaded.value = true
                console.log('✅ i18n: Loaded translations from API')
            }
        } catch (error) {
            console.warn('⚠️ i18n: API fetch failed, using local fallback')
            liveDictionary.value = localDictionary
            isLoaded.value = true
        }
    }

    // Initial fetch is now handled by plugins/i18n.init.ts for better SSR support

    /**
     * Translate a key — checks live dictionary first, falls back to local
     */
    const t = (key: string, params?: Record<string, string | number>): string => {
        let text =
            liveDictionary.value[locale.value]?.[key] ||
            liveDictionary.value['en']?.[key] ||
            localDictionary[locale.value]?.[key] ||
            localDictionary['en']?.[key] ||
            key

        if (params) {
            Object.entries(params).forEach(([k, v]) => {
                text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
            })
        }
        return text
    }

    const toggleLocale = () => {
        locale.value = locale.value === 'en' ? 'th' : 'en'
        if (import.meta.client) localStorage.setItem('app_locale', locale.value)
    }

    const setLocale = (newLocale: Locale) => {
        locale.value = newLocale
        if (import.meta.client) localStorage.setItem('app_locale', newLocale)
    }

    const reloadTranslations = () => fetchTranslations()
    const localeName = computed(() => locale.value === 'en' ? 'English' : 'ไทย')
    const localeFlag = computed(() => locale.value === 'en' ? '🇬🇧' : '🇹🇭')
    const isThai = computed(() => locale.value === 'th')

    return {
        t,
        locale,
        toggleLocale,
        setLocale,
        reloadTranslations,
        localeName,
        localeFlag,
        isThai,
        isLoaded,
    }
}

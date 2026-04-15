export default defineNuxtPlugin(async (nuxtApp) => {
    const { reloadTranslations } = useI18n()

    // Fetch translations once on startup (both SSR and CSR)
    // useAsyncData ensures it's fetched once on server and payload is sent to client
    await useAsyncData('i18n-init', async () => {
        await reloadTranslations()
        return true
    })
})

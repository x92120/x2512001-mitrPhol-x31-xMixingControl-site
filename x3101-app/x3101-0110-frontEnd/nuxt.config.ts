import { fileURLToPath } from 'node:url'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  css: [
    '~/assets/fonts.css'
  ],
  app: {
    head: {
      title: 'xMixing Control',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'xMixing Control System 2025 - Production Management' },
        { name: 'application-name', content: 'xMixingControl-01' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/x_logo.svg' },
        { rel: 'icon', type: 'image/png', sizes: '48x48', href: '/x_logo-48.png' },
        { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/x_logo-192.png' },
        { rel: 'apple-touch-icon', href: '/x_logo-192.png' },
        { rel: 'manifest', href: '/manifest.json' }
      ]
    }
  },
  modules: [
    'nuxt-quasar-ui'
  ],
  quasar: {
    sassVariables: fileURLToPath(new URL('./app/assets/quasar-variables.sass', import.meta.url)),
    plugins: [
      'Notify',
      'Dialog'
    ],
    extras: {
      fontIcons: ['material-icons']
    }
  },
  devtools: { enabled: true },
  future: {
    compatibilityVersion: 4,
  },
  vite: {
    server: {
      allowedHosts: ['xmixingcontrolprocess.xdev.co.th', 'localhost']
    }
  },
  compatibilityDate: '2024-11-01',
})

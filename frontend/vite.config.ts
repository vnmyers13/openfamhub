import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'OpenFamHub - Family Hub',
        short_name: 'FamHub',
        description: 'Family Hub — Calendar, Announcements, Wall Display',
        theme_color: '#1a1a2e',
        background_color: '#1a1a2e',
        display: 'fullscreen',
        orientation: 'landscape',
        icons: [
          {
            src: 'pwa-64x64.png',
            sizes: '64x64',
            type: 'image/png',
          },
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/openfamhub\.local\/api\/meals\/shopping-list.*/i,
            handler: 'CacheFirst',
            options: { cacheName: 'shopping-cache', expiration: { maxEntries: 10, maxAgeSeconds: 300 }, cacheableResponse: { statuses: [0, 200] } },
          },
          {
            urlPattern: /^https:\/\/openfamhub\.local\/api\/chores\/instances.*/i,
            handler: 'CacheFirst',
            options: { cacheName: 'chores-cache', expiration: { maxEntries: 10, maxAgeSeconds: 300 }, cacheableResponse: { statuses: [0, 200] } },
          },
          {
            urlPattern: /^https:\/\/openfamhub\.local\/api\/.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 60 }, cacheableResponse: { statuses: [0, 200] } },
          },
          {
            urlPattern: /^https:\/\/openfamhub\.local\/ws\/.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'ws-cache', expiration: { maxEntries: 10, maxAgeSeconds: 30 }, cacheableResponse: { statuses: [0, 200] } },
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': 'ws://localhost:8000',
    },
  },
})

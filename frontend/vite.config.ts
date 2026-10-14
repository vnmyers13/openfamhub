import { defineConfig } from 'vite'
import { runtimeCaching } from './src/lib/swCaching'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: 'icons/*.png',
      manifest: {
        name: 'OpenFamHub',
        short_name: 'OpenFamHub',
        description: 'OpenFamHub — family calendar for home',
        theme_color: '#4F46E5',
        background_color: '#1E1B4B',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/apple-touch-icon-180x180.png', sizes: '180x180', type: 'image/png' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/photos/],
        // Workbox tests a RegExp against the full URL (https://host/...), so a
        // /^\/api/ pattern never matched. Match on the pathname instead.
        // /api/auth/* is deliberately not cached (a stale "signed in" is worse
        // than an offline error).
        runtimeCaching,
      },
    }),
  ],
  server: {
    proxy: {
      // ws: true so the wall's /api/ws/wall socket works in dev too.
      '/api': { target: 'http://localhost:8000', ws: true },
      '/photos': 'http://localhost:8000',
    },
  },
})

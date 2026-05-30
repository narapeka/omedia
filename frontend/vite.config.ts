import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), tailwindcss()],
    define: {
      __OMEDIA_API_BASE_URL__: JSON.stringify(env.VITE_OMEDIA_API_BASE_URL ?? ''),
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 7108,
      proxy: {
        '/api': {
          target: env.VITE_OMEDIA_PROXY_TARGET ?? 'http://127.0.0.1:7100',
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 7109,
    },
    test: {
      environment: 'jsdom',
      exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
      setupFiles: './tests/setup/vitest.setup.ts',
    },
  }
})

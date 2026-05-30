import { defineConfig } from '@playwright/test'

process.env.NO_PROXY = ['127.0.0.1', 'localhost', '::1', process.env.NO_PROXY].filter(Boolean).join(',')
process.env.no_proxy = process.env.NO_PROXY

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './tests/.results/playwright',
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:7109',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npx vite --host=127.0.0.1 --port=7109',
    url: 'http://127.0.0.1:7109',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})

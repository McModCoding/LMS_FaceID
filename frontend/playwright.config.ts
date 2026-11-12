import { defineConfig } from '@playwright/test'

process.env.PHASE1_RUN ||= Date.now().toString(36)

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['json', { outputFile: '../.local/playwright-results.json' }]],
  use: {
    baseURL: process.env.PHASE1_BASE_URL || 'http://127.0.0.1:5188',
    viewport: { width: 1440, height: 1000 },
    timezoneId: 'Asia/Ho_Chi_Minh',
    locale: 'vi-VN',
    colorScheme: 'light',
    screenshot: 'only-on-failure',
    trace: 'off',
  },
})

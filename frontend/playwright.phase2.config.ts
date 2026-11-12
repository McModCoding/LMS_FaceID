import { defineConfig } from '@playwright/test'
import base from './playwright.config'
export default defineConfig({ ...base, testMatch: 'phase2.spec.ts',
  reporter: [['list'], ['json', { outputFile: process.env.PHASE2_REPORT || '../.local/phase2-playwright-results.json' }]],
  use: { ...base.use, baseURL: process.env.PHASE2_BASE_URL || 'http://127.0.0.1:5198', hasTouch: true },
})

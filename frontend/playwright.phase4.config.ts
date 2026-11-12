import { defineConfig } from '@playwright/test'
import base from './playwright.config'
export default defineConfig({ ...base, testMatch: 'phase4.spec.ts', timeout: 180_000,
  reporter: [['list'], ['json', { outputFile: process.env.PHASE4_REPORT || '../.local/phase4-browser-results.json' }]],
  use: { ...base.use, baseURL: 'http://127.0.0.1:5218', hasTouch: true },
})

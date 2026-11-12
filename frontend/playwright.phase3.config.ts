import { defineConfig } from '@playwright/test'
import base from './playwright.config'
export default defineConfig({ ...base, testMatch: 'phase3.spec.ts',
  reporter: [['list'], ['json', { outputFile: process.env.PHASE3_REPORT || '../.local/phase3-browser-results.json' }]],
  use: { ...base.use, baseURL: 'http://127.0.0.1:5208', hasTouch: true },
})

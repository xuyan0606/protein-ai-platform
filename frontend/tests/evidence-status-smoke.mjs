import { chromium } from 'playwright'

// Keep the fixture default aligned with vite.smoke.config.ts.  CI/local
// callers can still override it for an already-running server.
const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4201'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()

try {
  await page.goto(`${baseUrl}/smoke-tests.html`, { waitUntil: 'networkidle' })
  const fixture = page.locator('[data-testid="evidence-status-fixtures"]')
  await fixture.waitFor()
  const text = await fixture.innerText()
  for (const status of ['waiting', 'failed', 'not_run', 'computed', 'experimental']) {
    if (!text.includes(status)) throw new Error(`Missing evidence status: ${status}`)
  }
  const cards = fixture.locator('button')
  if (await cards.count() !== 5) throw new Error(`Expected 5 evidence cards, got ${await cards.count()}`)
  const sourceBadges = fixture.locator('button span').filter({ hasText: /waiting|failed|not_run|computed|experimental/ })
  if (await sourceBadges.count() < 5) throw new Error('Evidence status badges are not rendered for all fixture states')
  console.log('Evidence status fixture smoke passed')
} finally {
  await browser.close()
}

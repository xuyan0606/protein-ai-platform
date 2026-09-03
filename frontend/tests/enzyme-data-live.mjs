import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(chrome) ? chrome : undefined)
const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
const user = {
  email: `enzyme-data-live-${id}@example.com`,
  password: `EnzymeData-${id}-pw`,
  name: 'Enzyme Data Live Gate',
}

const browser = await chromium.launch({ headless: true, executablePath })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const consoleErrors = []
const failedRequests = []
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('requestfailed', (request) => {
  if (!request.url().includes('/api/auth/logout')) {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`)
  }
})

try {
  const registered = await page.request.post(`${baseUrl}/api/auth/register`, { data: user })
  if (![200, 201].includes(registered.status())) throw new Error(`register failed: HTTP ${registered.status()}`)

  await page.goto(`${baseUrl}/login?next=%2Fdata%3Ftab%3Denzymes`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/data\?tab=enzymes/, { timeout: 30000 })
  await page.getByRole('heading', { name: '多酶证据库' }).waitFor({ timeout: 30000 })

  for (const family of ['Amylase', 'Mannanase', 'Xylanase', 'Acid protease', 'Phytase', 'Glucose oxidase']) {
    await page.getByRole('button', { name: new RegExp(`^${family}`) }).click()
    await page.getByText('integrity: ok').waitFor({ timeout: 15000 })
    await page.getByText('文献 Papers').waitFor()
    await page.getByText('变体 Variants').waitFor()
    await page.getByText('实验 Measurements').waitFor()
    const unavailable = await page.getByText(/数据源未挂载|无法判断该库是否为空/).count()
    if (unavailable) throw new Error(`${family}: database unavailable state shown`)
  }

  const input = page.getByPlaceholder('搜索突变、底物、性质、DOI...')
  const searchButton = input.locator('xpath=../..').getByRole('button')
  await input.fill('activity')
  await searchButton.click()
  await searchButton.getByText('搜索').waitFor({ timeout: 15000 })
  await input.fill('')
  await searchButton.getByText('重置').waitFor({ timeout: 15000 })
  await searchButton.click()
  await page.getByText('integrity: ok').waitFor({ timeout: 15000 })

  if (failedRequests.length) throw new Error(`request failures: ${failedRequests.join(' | ')}`)
  const relevantConsoleErrors = consoleErrors.filter((line) => !line.includes('favicon'))
  if (relevantConsoleErrors.length) throw new Error(`console errors: ${relevantConsoleErrors.join(' | ')}`)

  console.log(JSON.stringify({ status: 'passed', families: 6, search: true, reset: true, console_errors: 0, request_failures: 0 }))
} finally {
  await browser.close()
}

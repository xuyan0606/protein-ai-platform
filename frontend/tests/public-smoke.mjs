import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4200'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage()
const errors = []
const httpErrors = []

page.on('pageerror', (error) => {
  errors.push(`pageerror: ${error.message}`)
})

page.on('console', (msg) => {
  if (msg.type() === 'error') {
    errors.push(`console:${msg.type()}: ${msg.text()}`)
  }
})

page.on('response', async (response) => {
  if (response.status() >= 400) {
    httpErrors.push(`${response.status()} ${response.url()}`)
  }
})

async function visit(path) {
  const response = await page.goto(`${baseUrl}${path}`, { waitUntil: 'domcontentloaded' })
  if (!response) throw new Error(`No HTTP response for ${path}`)
  if (response.status() >= 400) throw new Error(`HTTP ${response.status()} for ${path}`)
  await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(750)
  return page.textContent('body')
}

try {
  const loginText = await visit('/login')
  if (!/login|sign in|protein/i.test(loginText || '')) {
    throw new Error('Login page did not render expected auth content')
  }

  const homeText = await visit('/home')
  if (!/workspace|conversation|agent|protein/i.test(homeText || '')) {
    throw new Error('Home page did not render expected shell content')
  }

  const dataText = await visit('/data')
  if (!/protein|uniprot|search|data/i.test(dataText || '')) {
    throw new Error('Data page did not render expected browser content')
  }

  if (httpErrors.length > 0) {
    throw new Error(`HTTP error responses detected:\n${httpErrors.join('\n')}`)
  }

  if (errors.length > 0) {
    throw new Error(`Browser runtime errors detected:\n${errors.join('\n')}`)
  }

  console.log('Public smoke passed')
} finally {
  await browser.close()
}

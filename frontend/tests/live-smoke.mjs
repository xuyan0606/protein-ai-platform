import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4200'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)

function explainNetworkFailure(error) {
  const message = error instanceof Error ? error.message : String(error)
  if (message.includes('fetch failed') || message.includes('connect EPERM') || message.includes('ECONNREFUSED')) {
    return new Error(`live-smoke cannot reach ${baseUrl}. Start the local frontend on port 4200 or set FRONTEND_BASE_URL to a live target before running smoke.`)
  }
  return error
}

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage()
const errors = []
const httpErrors = []

page.on('pageerror', (error) => {
  errors.push(`pageerror: ${error.message}`)
})

page.on('console', (msg) => {
  const text = msg.text()
  const anonymousAuthProbe = msg.type() === 'error' && (
    text.includes('Failed to fetch models')
    || text.includes('Failed to sync conversations')
    || text.includes('Failed to load resource: the server responded with a status of 401 (Unauthorized)')
  )
  if (anonymousAuthProbe) return
  if (msg.type() === 'error') {
    errors.push(`console:${msg.type()}: ${text}`)
  }
})

page.on('response', async (response) => {
  const url = response.url()
  const anonymousAuthProbe = response.status() === 401 && (
    url.includes('/api/conversations') || url.includes('/api/chat/models')
  )
  if (response.status() >= 400 && !anonymousAuthProbe) {
    httpErrors.push(`${response.status()} ${url}`)
  }
})

async function ensureHttpOk(path) {
  const response = await page.goto(`${baseUrl}${path}`, { waitUntil: 'domcontentloaded' })
  if (!response) throw new Error(`No HTTP response for ${path}`)
  if (response.status() >= 400) {
    throw new Error(`HTTP ${response.status()} for ${path}`)
  }
  return response
}

async function waitForPageSettled() {
  await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(750)
}

try {
  await ensureHttpOk('/login')
  await waitForPageSettled()
  if (!/login|sign in|protein/i.test(await page.textContent('body') || '')) {
    throw new Error('Login page did not render expected auth content')
  }

  await ensureHttpOk('/home')
  await waitForPageSettled()
  const homeText = await page.textContent('body') || ''
  if (!/workspace|conversation|agent|protein/i.test(homeText)) {
    throw new Error('Home page did not render expected shell content')
  }

  await ensureHttpOk('/data')
  await waitForPageSettled()
  const dataText = await page.textContent('body') || ''
  if (!/protein|uniprot|search|data/i.test(dataText)) {
    throw new Error('Data page did not render expected browser content')
  }

  await ensureHttpOk('/chat/agent')
  await waitForPageSettled()
  const chatUrl = page.url()
  if (!chatUrl.includes('/chat/agent') && !chatUrl.includes('/login')) {
    throw new Error(`Unexpected chat route resolution: ${chatUrl}`)
  }

  await ensureHttpOk('/kb')
  await waitForPageSettled()
  const kbUrl = page.url()
  const kbText = await page.textContent('body') || ''
  if (!kbUrl.includes('/kb') && !kbUrl.includes('/login?next=%2Fkb')) {
    throw new Error(`Unexpected KB route resolution: ${kbUrl}`)
  }
  if (
    kbUrl.includes('/login?next=')
    && !/login|sign in|protein/i.test(kbText)
  ) {
    throw new Error(`KB login redirect did not render expected auth content (url=${kbUrl})`)
  }

  if (httpErrors.length > 0) {
    throw new Error(`HTTP error responses detected:\n${httpErrors.join('\n')}`)
  }

  if (errors.length > 0) {
    throw new Error(`Browser runtime errors detected:\n${errors.join('\n')}`)
  }

  console.log('Live smoke passed')
} catch (error) {
  throw explainNetworkFailure(error)
} finally {
  await browser.close()
}

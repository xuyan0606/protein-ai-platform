import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const outputDir = path.resolve(process.cwd(), 'output/playwright')
const timeoutMs = Number(process.env.CONNECTIVITY_CHAT_TIMEOUT_MS || 120000)

async function requestJson(pathname, { method = 'GET', token, payload } = {}) {
  const response = await fetch(`${baseUrl}${pathname}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(payload ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  })
  const text = await response.text()
  let body = {}
  try {
    body = text.trim() ? JSON.parse(text) : {}
  } catch {
    body = { detail: text.slice(0, 300) }
  }
  return { response, body }
}

function countMatches(text, pattern) {
  return [...text.matchAll(pattern)].length
}

async function waitForStreamingDone(page) {
  await page.getByText('Agent is responding').waitFor({ state: 'visible', timeout: 30000 }).catch(() => {})
  await page.getByText('Agent is responding').waitFor({ state: 'hidden', timeout: timeoutMs })
}

const id = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}`
const email = `connectivity-live-${id}@example.com`
const password = `Connectivity-${crypto.randomBytes(12).toString('hex')}!`
const registered = await requestJson('/api/auth/register', {
  method: 'POST',
  payload: { email, password, name: 'Connectivity Live Gate' },
})
if (![200, 201].includes(registered.response.status)) {
  throw new Error(`register failed: HTTP ${registered.response.status}`)
}

const login = await requestJson('/api/auth/login', {
  method: 'POST',
  payload: { email, password },
})
if (login.response.status !== 200 || !login.body.access_token) {
  throw new Error(`login failed: HTTP ${login.response.status}`)
}
const token = login.body.access_token

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 920 } })
const consoleErrors = []
const httpErrors = []
const streamRequests = []

page.on('pageerror', (error) => consoleErrors.push(`pageerror:${error.message}`))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(`console:${message.text()}`)
})
page.on('request', (request) => {
  if (request.method() === 'POST' && request.url().endsWith('/api/chat/stream')) {
    streamRequests.push(request)
  }
})
page.on('response', (response) => {
  if (response.status() >= 500) httpErrors.push(`${response.status()} ${response.url()}`)
})

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.evaluate((auth) => {
    window.localStorage.setItem('token', auth.accessToken)
    window.localStorage.setItem('refreshToken', auth.refreshToken)
    window.dispatchEvent(new Event('protein-ai:auth-updated'))
  }, { accessToken: token, refreshToken: login.body.refresh_token })
  await page.goto(`${baseUrl}/chat/agent`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.locator('textarea').last().waitFor({ timeout: 30000 })

  const input = page.locator('textarea').last()
  const sendButton = input.locator('xpath=following-sibling::button[1]')
  await input.fill('你联网了吗？')
  await sendButton.dblclick({ delay: 5 })
  await page.getByRole('button', { name: '确认执行', exact: true }).waitFor({ timeout: timeoutMs })

  if (streamRequests.length !== 1) {
    throw new Error(`double-click started ${streamRequests.length} plan requests; expected 1`)
  }

  await page.getByRole('button', { name: '确认执行', exact: true }).click()
  await waitForStreamingDone(page)
  await page.getByText(/本轮刚刚进行了实时外部探测/).waitFor({ timeout: timeoutMs })

  if (streamRequests.length !== 2) {
    throw new Error(`expected plan+execute requests once each; requests=${streamRequests.length}`)
  }

  const bodyText = await page.locator('body').innerText()
  if (countMatches(bodyText, /确认执行上述分析策略/g) !== 1) {
    throw new Error('browser did not render exactly one confirmed-execution user message')
  }
  if (countMatches(bodyText, /external_connectivity_check/g) < 1) {
    throw new Error('browser did not render the connectivity tool call')
  }
  if (countMatches(bodyText, /本轮刚刚进行了实时外部探测/g) !== 1) {
    throw new Error('browser rendered duplicate final connectivity answers')
  }
  if (consoleErrors.length || httpErrors.length) {
    throw new Error(`browser errors: ${JSON.stringify({ consoleErrors, httpErrors })}`)
  }

  fs.mkdirSync(outputDir, { recursive: true })
  const screenshot = path.join(outputDir, 'connectivity-chat-live.png')
  await page.screenshot({ path: screenshot, fullPage: true })

  console.log(JSON.stringify({
    status: 'passed',
    baseUrl,
    tempUserEmail: email,
    checks: {
      doubleClickPlanRequests: 1,
      confirmedExecutionRequests: 1,
      streamingFinished: true,
      finalAnswerRenderCount: 1,
      connectivityToolPlanned: true,
    },
    screenshot,
    consoleErrors: 0,
    httpErrors: 0,
    secretsPrinted: false,
  }, null, 2))
} finally {
  const conversations = await requestJson('/api/conversations', { token }).catch(() => null)
  for (const conversation of conversations?.body || []) {
    if (conversation?.id) {
      await requestJson(`/api/conversations/${conversation.id}`, { method: 'DELETE', token }).catch(() => null)
    }
  }
  await browser.close()
}

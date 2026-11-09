import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const outputDir = path.resolve(process.cwd(), 'output/playwright')
const timeoutMs = Number(process.env.STOP_EXECUTION_TIMEOUT_MS || 120000)

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

async function createTempUser() {
  const id = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}`
  const email = `stop-execution-live-${id}@example.com`
  const password = `Stop-${crypto.randomBytes(12).toString('hex')}!`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: 'Stop Execution Live Gate' },
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
  return { email, token: login.body.access_token, refreshToken: login.body.refresh_token }
}

const user = await createTempUser()
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 920 } })
const consoleErrors = []
const httpErrors = []
const chatStreamRequests = []

async function captureDebug(label) {
  fs.mkdirSync(outputDir, { recursive: true })
  const screenshot = path.join(outputDir, `${label}.png`)
  await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {})
  const bodyPreview = await page.locator('body').innerText().catch(() => '')
  return { screenshot, bodyPreview: bodyPreview.slice(0, 1600) }
}

page.on('pageerror', (error) => consoleErrors.push(`pageerror:${error.message}`))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(`console:${message.text()}`)
})
page.on('request', (request) => {
  if (request.method() === 'POST' && request.url().endsWith('/api/chat/stream')) {
    chatStreamRequests.push(request.url())
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
  }, { accessToken: user.token, refreshToken: user.refreshToken })

  await page.goto(`${baseUrl}/chat/agent`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  const input = page.locator('textarea').last()
  await input.waitFor({ timeout: 30000 })
  const sendButton = input.locator('xpath=following-sibling::button[1]')

  await input.fill('你联网了吗？')
  await sendButton.click()
  await page.getByRole('button', { name: '确认执行', exact: true }).waitFor({ timeout: timeoutMs }).catch(async (error) => {
    const debug = await captureDebug('stop-execution-confirm-timeout')
    throw new Error(`plan confirmation button was not visible; debug=${JSON.stringify(debug)}; cause=${error.message}`)
  })

  await page.getByRole('button', { name: '确认执行', exact: true }).click()
  const stopButton = page.getByRole('button', { name: /停止执行/ }).first()
  await stopButton.waitFor({ state: 'visible', timeout: 30000 })
  await stopButton.click()
  await page.getByText('已停止执行。').waitFor({ timeout: 30000 })
  await stopButton.waitFor({ state: 'hidden', timeout: 30000 }).catch(() => {})

  const textareaEnabled = await input.isEnabled()
  const bodyText = await page.locator('body').innerText()
  if (!bodyText.includes('确认执行上述分析策略')) {
    throw new Error('confirmed execution user message was not rendered')
  }
  if (!bodyText.includes('已停止执行。')) {
    throw new Error('stop marker was not rendered')
  }
  if (!textareaEnabled) {
    throw new Error('chat input stayed disabled after stopping')
  }
  if (chatStreamRequests.length < 2) {
    throw new Error(`expected plan and confirmed execution stream requests; got ${chatStreamRequests.length}`)
  }
  if (consoleErrors.length || httpErrors.length) {
    throw new Error(`browser errors: ${JSON.stringify({ consoleErrors, httpErrors })}`)
  }

  fs.mkdirSync(outputDir, { recursive: true })
  const screenshot = path.join(outputDir, 'stop-execution-live.png')
  await page.screenshot({ path: screenshot, fullPage: true })

  console.log(JSON.stringify({
    status: 'passed',
    baseUrl,
    tempUserEmail: user.email,
    checks: {
      planConfirmationVisible: true,
      stopButtonVisibleAfterConfirm: true,
      stoppedMarkerRendered: true,
      inputEnabledAfterStop: textareaEnabled,
      streamRequests: chatStreamRequests.length,
    },
    screenshot,
    consoleErrors: 0,
    httpErrors: 0,
    secretsPrinted: false,
  }, null, 2))
} finally {
  const conversations = await requestJson('/api/conversations', { token: user.token }).catch(() => null)
  for (const conversation of conversations?.body || []) {
    if (conversation?.id) {
      await requestJson(`/api/conversations/${conversation.id}`, {
        method: 'DELETE',
        token: user.token,
      }).catch(() => null)
    }
  }
  await browser.close()
}

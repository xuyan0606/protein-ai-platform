import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)
const timeoutMs = Number(process.env.CHAT_SSE_DEEP_TIMEOUT_MS || 180000)

function randomId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

async function requestJson(path, { method = 'GET', token, payload, timeout = 30000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      signal: controller.signal,
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
  } finally {
    clearTimeout(timer)
  }
}

async function createLiveUser() {
  const id = randomId()
  const email = `codex-front-${id}@example.com`
  const password = `Codex-${id}-pw`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: 'Codex Front Deep' },
  })
  if (![200, 201].includes(registered.response.status)) {
    throw new Error(`register failed: HTTP ${registered.response.status}`)
  }
  return { email, password }
}

async function loginViaUi(page, user) {
  const loginResponse = await requestJson('/api/auth/login', {
    method: 'POST',
    payload: { email: user.email, password: user.password },
    timeout: 30000,
  })
  if (![200, 201].includes(loginResponse.response.status)) {
    throw new Error(`api login failed: HTTP ${loginResponse.response.status}`)
  }

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {})
  await page.evaluate((auth) => {
    if (auth?.access_token) window.localStorage.setItem('token', auth.access_token)
    if (auth?.refresh_token) window.localStorage.setItem('refreshToken', auth.refresh_token)
    if (auth?.access_token) window.dispatchEvent(new Event('protein-ai:auth-updated'))
  }, loginResponse.body)
  await page.goto(`${baseUrl}/chat/agent`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {})
  await page.waitForURL(/\/chat\/agent/, { timeout: 30000 }).catch(() => {})
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
}

async function waitForStreamingDone(page, label) {
  await page.getByText('Agent is responding').waitFor({ state: 'visible', timeout: 45000 }).catch(() => {})
  await page.getByText('Agent is responding').waitFor({ state: 'hidden', timeout: timeoutMs })
  const isStreaming = await page.evaluate(() => window.localStorage.getItem('currentConversationId'))
  if (!isStreaming) {
    throw new Error(`${label}: currentConversationId was not persisted`)
  }
}

async function sendTextMessage(page, text) {
  const input = page.locator('textarea').last()
  await input.fill(text)
  await page.keyboard.press('Enter')
}

async function runBaselineChat(page) {
  const marker = `baseline front deep ${randomId()}`
  await sendTextMessage(page, `请用中文简短说明你可以帮助做蛋白稳定性分析。测试标记：${marker}`)
  await waitForStreamingDone(page, 'baseline chat')

  const state = await page.evaluate(() => {
    const messages = document.body.innerText
    const markerIndex = messages.indexOf('baseline front deep')
    const textAfterMarker = markerIndex >= 0 ? messages.slice(markerIndex + 'baseline front deep'.length) : ''
    return {
      currentConversationId: window.localStorage.getItem('currentConversationId'),
      hasAgentResponding: messages.includes('Agent is responding'),
      hasUserMarker: messages.includes('baseline front deep'),
      assistantTextAfterMarkerLength: textAfterMarker.trim().length,
      hasProteinAssistantText: /蛋白|稳定性|序列|结构|突变|分析|请提供/.test(textAfterMarker),
      bodyTextLength: messages.length,
      bodyPreview: messages.slice(0, 700),
    }
  })
  if (
    !state.currentConversationId ||
    state.hasAgentResponding ||
    !state.hasUserMarker ||
    state.assistantTextAfterMarkerLength < 20 ||
    !state.hasProteinAssistantText ||
    state.bodyTextLength < 200
  ) {
    throw new Error(`baseline chat state invalid: ${JSON.stringify(state)}`)
  }
  return state
}

async function runFileMdChat(page) {
  const structurePath = path.resolve(process.cwd(), 'deploy_data/pdb/4HHB.cif')
  if (!fs.existsSync(structurePath)) {
    throw new Error(`Missing structure fixture: ${structurePath}`)
  }

  await page.locator('input[type="file"]').setInputFiles(structurePath)
  await page.getByText(/4HHB\.cif/i).waitFor({ timeout: 15000 })
  await page.getByRole('button', { name: '深度' }).click()

  await sendTextMessage(page, '对上传PDB做分子动力学深度分析，看看RMSD/RMSF和热稳定性。')
  try {
    await page.getByText('gromacs_md', { exact: false }).waitFor({ timeout: 90000 })
  } catch (error) {
    const debug = await page.evaluate(() => ({
      currentConversationId: window.localStorage.getItem('currentConversationId'),
      bodyPreview: document.body.innerText.slice(0, 1600),
      hasAgentResponding: document.body.innerText.includes('Agent is responding'),
    }))
    throw new Error(`gromacs_md did not appear; debug=${JSON.stringify(debug)}`)
  }
  const gromacsCard = page.getByRole('button', { name: /^gromacs_md\b/i }).first()
  await gromacsCard.waitFor({ timeout: 120000 })
  await gromacsCard.click()
  await page.getByText(/task_id|status_url|api\/tools\/tasks/i).waitFor({ timeout: 15000 }).catch(() => {})
  await waitForStreamingDone(page, 'file md chat')

  const state = await page.evaluate(() => {
    const text = document.body.innerText
    return {
      hasGromacs: text.includes('gromacs_md'),
      hasTerminalStatus: /gromacs_md\s+(Completed|Complete|Failed|submitted)/i.test(text),
      currentConversationId: window.localStorage.getItem('currentConversationId'),
    }
  })
  if (!state.hasGromacs || !state.hasTerminalStatus || !state.currentConversationId) {
    throw new Error(`file md chat state invalid: ${JSON.stringify(state)}`)
  }
  return state
}

async function runLogoutReset(page) {
  await page.getByRole('button', { name: /user menu/i }).click()
  await page.getByRole('button', { name: /sign out/i }).click()
  await page.waitForURL(/\/login/, { timeout: 30000 })
  const state = await page.evaluate(() => ({
    token: window.localStorage.getItem('token'),
    refreshToken: window.localStorage.getItem('refreshToken'),
    currentConversationId: window.localStorage.getItem('currentConversationId'),
    body: document.body.innerText.slice(0, 300),
  }))
  if (state.token || state.refreshToken || state.currentConversationId) {
    throw new Error(`logout did not clear local state: ${JSON.stringify(state)}`)
  }
  return { cleared: true }
}

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage({ viewport: { width: 1440, height: 920 } })
const consoleErrors = []
const httpErrors = []

page.on('pageerror', (error) => {
  consoleErrors.push(`pageerror: ${error.message}`)
})
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(`console:${msg.text()}`)
})
page.on('response', (response) => {
  const status = response.status()
  const url = response.url()
  if (status >= 500) httpErrors.push(`${status} ${url}`)
})

try {
  const user = await createLiveUser()
  await loginViaUi(page, user)
  const baseline = await runBaselineChat(page)
  const fileMd = await runFileMdChat(page)
  const logout = await runLogoutReset(page)

  if (consoleErrors.length > 0) {
    throw new Error(`browser console errors:\n${consoleErrors.join('\n')}`)
  }
  if (httpErrors.length > 0) {
    throw new Error(`server HTTP errors:\n${httpErrors.join('\n')}`)
  }

  console.log(JSON.stringify({
    status: 'passed',
    baseUrl,
    checks: {
      baseline,
      fileMd,
      logout,
    },
    consoleErrors: 0,
    httpErrors: 0,
    secretsPrinted: false,
  }, null, 2))
} finally {
  await browser.close()
}

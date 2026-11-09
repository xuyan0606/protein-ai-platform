import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)

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

async function createLiveUser(label) {
  const id = randomId()
  const email = `codex-session-${label}-${id}@example.com`
  const password = `Codex-${id}-pw`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: `Codex Session ${label}` },
  })
  if (![200, 201].includes(registered.response.status)) {
    throw new Error(`register ${label} failed: HTTP ${registered.response.status}`)
  }
  return {
    email,
    password,
    token: registered.body.access_token,
  }
}

async function createConversation(user, title) {
  const created = await requestJson('/api/conversations', {
    method: 'POST',
    token: user.token,
    payload: { title },
  })
  if (![200, 201].includes(created.response.status)) {
    throw new Error(`create conversation failed: HTTP ${created.response.status}`)
  }
  return created.body
}

async function deleteConversation(user, id) {
  await requestJson(`/api/conversations/${id}`, { method: 'DELETE', token: user.token }).catch(() => undefined)
}

async function loginViaUi(page, user) {
  await page.goto(`${baseUrl}/login?next=%2Fchat%2Fagent`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/chat\/agent/, { timeout: 30000 })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
}

async function logoutViaUi(page) {
  await page.getByRole('button', { name: /user menu/i }).click()
  await page.getByRole('button', { name: /sign out/i }).click()
  await page.waitForURL(/\/login/, { timeout: 30000 })
}

async function waitForVisibleText(page, text, timeout = 30000) {
  await page.waitForFunction((expected) => {
    return Array.from(document.querySelectorAll('body *')).some((el) => {
      if (el.textContent !== expected) return false
      const style = window.getComputedStyle(el)
      return style.visibility !== 'hidden' && style.display !== 'none' && el.getClientRects().length > 0
    })
  }, text, { timeout })
}

async function hasVisibleText(page, text) {
  return page.evaluate((expected) => {
    return Array.from(document.querySelectorAll('body *')).some((el) => {
      if (el.textContent !== expected) return false
      const style = window.getComputedStyle(el)
      return style.visibility !== 'hidden' && style.display !== 'none' && el.getClientRects().length > 0
    })
  }, text)
}

async function sendTextMessage(page, text) {
  const input = page.locator('textarea').last()
  await input.fill(text)
  await page.keyboard.press('Enter')
}

async function selectConversation(page, title, expectedId) {
  await waitForVisibleText(page, title)
  const detailResponsePromise = page.waitForResponse((response) => {
    return response.url().includes(`/api/conversations/${expectedId}`) && response.status() === 200
  }, { timeout: 30000 }).catch(() => undefined)
  const clicked = await page.evaluate((expected) => {
    const target = Array.from(document.querySelectorAll('body *')).find((el) => {
      if (el.textContent !== expected) return false
      const style = window.getComputedStyle(el)
      return style.visibility !== 'hidden' && style.display !== 'none' && el.getClientRects().length > 0
    })
    const clickable = target?.closest('.cursor-pointer')
    if (!(clickable instanceof HTMLElement)) return false
    clickable.click()
    return true
  }, title)
  if (!clicked) {
    throw new Error(`visible conversation row not clickable: ${title}`)
  }
  await page.waitForFunction((id) => window.localStorage.getItem('currentConversationId') === String(id), expectedId, { timeout: 20000 })
  await detailResponsePromise
}

async function runRestoreSession(page, user, conversation) {
  await loginViaUi(page, user)
  await selectConversation(page, conversation.title, conversation.id)
  const beforeReload = await page.evaluate(() => ({
    currentConversationId: window.localStorage.getItem('currentConversationId'),
    conversationKeys: Object.fromEntries(
      Object.keys(window.localStorage)
        .filter((key) => key.startsWith('currentConversationId'))
        .map((key) => [key, window.localStorage.getItem(key)])
    ),
    bodyPreview: document.body.innerText.slice(0, 500),
  }))
  const restoredDetailResponsePromise = page.waitForResponse((response) => {
    return response.url().includes(`/api/conversations/${conversation.id}`) && response.status() === 200
  }, { timeout: 30000 }).catch(() => undefined)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForVisibleText(page, conversation.title)
  try {
    await page.waitForFunction((id) => window.localStorage.getItem('currentConversationId') === String(id), conversation.id, { timeout: 20000 })
    await restoredDetailResponsePromise
  } catch (error) {
    const debug = await page.evaluate((expectedTitle) => ({
      currentConversationId: window.localStorage.getItem('currentConversationId'),
      conversationKeys: Object.fromEntries(
        Object.keys(window.localStorage)
          .filter((key) => key.startsWith('currentConversationId'))
          .map((key) => [key, window.localStorage.getItem(key)])
      ),
      tokenPresent: Boolean(window.localStorage.getItem('token')),
      refreshTokenPresent: Boolean(window.localStorage.getItem('refreshToken')),
      bodyIncludesTitle: document.body.innerText.includes(expectedTitle),
      bodyPreview: document.body.innerText.slice(0, 1000),
    }), conversation.title)
    throw new Error(`restoreSession did not persist selected conversation; beforeReload=${JSON.stringify(beforeReload)} debug=${JSON.stringify(debug)}`)
  }
  return { restoredConversationId: String(conversation.id) }
}

async function runTokenRefresh(page, conversation) {
  const invalidToken = `invalid-token-${randomId()}`
  let observedRefresh = false
  const refreshResponsePromise = page.waitForResponse((response) => {
    return response.url().includes('/api/auth/refresh') && response.status() === 200
  }, { timeout: 60000 }).then(() => {
    observedRefresh = true
  }).catch(() => undefined)

  await page.evaluate((token) => {
    window.localStorage.setItem('token', token)
  }, invalidToken)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForVisibleText(page, conversation.title)
  await sendTextMessage(page, `请用中文简短回复：token refresh live ${randomId()}`)
  await page.getByText('Agent is responding').waitFor({ state: 'visible', timeout: 30000 }).catch(() => {})
  await page.getByText('Agent is responding').waitFor({ state: 'hidden', timeout: 90000 })
  await refreshResponsePromise
  const state = await page.evaluate((token) => ({
    tokenReplaced: Boolean(window.localStorage.getItem('token')) && window.localStorage.getItem('token') !== token,
    refreshTokenPresent: Boolean(window.localStorage.getItem('refreshToken')),
    currentConversationId: window.localStorage.getItem('currentConversationId'),
    bodyPreview: document.body.innerText.slice(0, 900),
  }), invalidToken)
  if (!state.tokenReplaced || !state.refreshTokenPresent || state.currentConversationId !== String(conversation.id)) {
    throw new Error(`token refresh state invalid: ${JSON.stringify(state)}`)
  }
  return { ...state, observedRefresh }
}

async function runUserSwitchIsolation(page, firstConversation, secondUser, secondConversation) {
  await logoutViaUi(page)
  await loginViaUi(page, secondUser)
  await waitForVisibleText(page, secondConversation.title)
  if (await hasVisibleText(page, firstConversation.title)) {
    throw new Error('first user conversation remained visible after switching users')
  }
  const state = await page.evaluate(() => ({
    currentConversationId: window.localStorage.getItem('currentConversationId'),
  }))
  if (state.currentConversationId) {
    throw new Error(`currentConversationId was not cleared on user switch: ${JSON.stringify(state)}`)
  }
  return { firstConversationHiddenAfterSwitch: true, currentConversationCleared: true }
}

async function runMissingSavedConversationCleanup(page, staleId) {
  await page.evaluate((id) => {
    window.localStorage.setItem('currentConversationId', String(id))
  }, staleId)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  const state = await page.evaluate(() => ({
    currentConversationId: window.localStorage.getItem('currentConversationId'),
  }))
  if (state.currentConversationId) {
    throw new Error(`stale saved conversation was not cleared: ${JSON.stringify(state)}`)
  }
  return { staleSavedConversationCleared: true }
}

const firstUser = await createLiveUser('a')
const secondUser = await createLiveUser('b')
const stamp = randomId()
const firstConversation = await createConversation(firstUser, `session-restore-${stamp}-a`)
const secondConversation = await createConversation(secondUser, `session-restore-${stamp}-b`)

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
const consoleErrors = []
const httpErrors = []
const traceStorage = process.env.TRACE_SESSION_STORAGE === '1'

if (traceStorage) {
  await page.addInitScript(() => {
    const originalRemoveItem = Storage.prototype.removeItem
    const originalSetItem = Storage.prototype.setItem
    const originalClear = Storage.prototype.clear
    Storage.prototype.removeItem = function patchedRemoveItem(key) {
      if (String(key).startsWith('currentConversationId')) {
        console.warn(`storage-trace removeItem ${String(key)} ${new Error().stack}`)
      }
      return originalRemoveItem.apply(this, arguments)
    }
    Storage.prototype.setItem = function patchedSetItem(key, value) {
      if (String(key).startsWith('currentConversationId')) {
        console.warn(`storage-trace setItem ${String(key)}=${String(value)} ${new Error().stack}`)
      }
      return originalSetItem.apply(this, arguments)
    }
    Storage.prototype.clear = function patchedClear() {
      console.warn(`storage-trace clear ${new Error().stack}`)
      return originalClear.apply(this, arguments)
    }
  })
}

page.on('pageerror', (error) => {
  consoleErrors.push(`pageerror: ${error.message}`)
})
page.on('console', (msg) => {
  if (traceStorage && msg.text().startsWith('storage-trace')) {
    console.log(msg.text().split('\n').slice(0, 6).join('\n'))
  }
  if (msg.type() === 'error') consoleErrors.push(`console:${msg.text()}`)
})
page.on('response', (response) => {
  const status = response.status()
  if (status >= 500) httpErrors.push(`${status} ${response.url()}`)
})

try {
  const restore = await runRestoreSession(page, firstUser, firstConversation)
  const tokenRefresh = await runTokenRefresh(page, firstConversation)
  const userSwitch = await runUserSwitchIsolation(page, firstConversation, secondUser, secondConversation)
  const staleCleanup = await runMissingSavedConversationCleanup(page, firstConversation.id)

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
      restore,
      tokenRefresh: {
        tokenReplaced: tokenRefresh.tokenReplaced,
        refreshTokenPresent: tokenRefresh.refreshTokenPresent,
        currentConversationIdPreserved: tokenRefresh.currentConversationId === String(firstConversation.id),
      },
      userSwitch,
      staleCleanup,
    },
    consoleErrors: 0,
    httpErrors: 0,
    secretsPrinted: false,
  }, null, 2))
} finally {
  await browser.close()
  await deleteConversation(firstUser, firstConversation.id)
  await deleteConversation(secondUser, secondConversation.id)
}

import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)

const users = JSON.parse(await new Promise((resolve) => {
  let data = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk) => { data += chunk })
  process.stdin.on('end', () => resolve(data))
}))

if (!Array.isArray(users) || users.length < 2) {
  throw new Error('stdin JSON must contain at least two users')
}

async function apiLogin(user) {
  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  })
  if (!response.ok) throw new Error(`API login failed for ${user.email}: ${response.status}`)
  return response.json()
}

async function createConversation(user, title) {
  const login = await apiLogin(user)
  const response = await fetch(`${baseUrl}/api/conversations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${login.access_token}`,
    },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) throw new Error(`create conversation failed for ${user.email}: ${response.status}`)
  return { token: login.access_token, conversation: await response.json() }
}

async function deleteConversation(token, id) {
  await fetch(`${baseUrl}/api/conversations/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => undefined)
}

async function uiLogin(page, user) {
  await page.goto(`${baseUrl}/login?next=%2Fchat%2Fagent`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: 'Sign In' }).click()
  await page.waitForURL(/\/chat\/agent/, { timeout: 20000 })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
}

async function uiLogout(page) {
  await page.getByLabel('User menu').click()
  await page.getByRole('button', { name: /sign out/i }).click()
  await page.waitForURL(/\/login/, { timeout: 20000 })
  await page.waitForLoadState('domcontentloaded')
}

async function waitForVisibleText(page, text) {
  await page.waitForFunction((expected) => {
    return Array.from(document.querySelectorAll('body *')).some((el) => {
      if (el.textContent !== expected) return false
      const style = window.getComputedStyle(el)
      return style.visibility !== 'hidden' && style.display !== 'none' && el.getClientRects().length > 0
    })
  }, text, { timeout: 20000 })
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

const stamp = Date.now()
const firstTitle = `switch-isolation-${stamp}-kwb01`
const secondTitle = `switch-isolation-${stamp}-kwb02`
const first = await createConversation(users[0], firstTitle)
const second = await createConversation(users[1], secondTitle)

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = []

page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console:${msg.text()}`)
})

try {
  await uiLogin(page, users[0])
  await waitForVisibleText(page, firstTitle)
  if (await hasVisibleText(page, secondTitle)) {
    throw new Error('second user conversation visible while first user is logged in')
  }

  await uiLogout(page)

  await uiLogin(page, users[1])
  await waitForVisibleText(page, secondTitle)
  if (await hasVisibleText(page, firstTitle)) {
    throw new Error('first user conversation remained visible after switching to second user')
  }

  if (errors.length) {
    throw new Error(`browser errors detected:\n${errors.join('\n')}`)
  }

  console.log(JSON.stringify({
    status: 'passed',
    baseUrl,
    usersChecked: [users[0].email, users[1].email],
    firstConversationHiddenAfterSwitch: true,
    passwordsPrinted: false,
  }, null, 2))
} finally {
  await browser.close()
  await deleteConversation(first.token, first.conversation.id)
  await deleteConversation(second.token, second.conversation.id)
}

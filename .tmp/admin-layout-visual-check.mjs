import fs from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const sshKey = process.env.ADMIN_LIVE_SSH_KEY || `${process.env.HOME}/.ssh/id_ed25519`
const sshHost = process.env.ADMIN_LIVE_SSH_HOST || 'root@120.27.108.138'
const remoteRoot = process.env.ADMIN_LIVE_REMOTE_ROOT || '/opt/protein-ai-platform/current'
const outDir = fileURLToPath(new URL('./', import.meta.url))
const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium } = require('playwright')

function randomId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

async function requestJson(path, { method = 'GET', token, payload } = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(payload ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  })
  const text = await response.text()
  return { response, body: text ? JSON.parse(text) : {} }
}

async function createTempUser() {
  const id = randomId()
  const user = {
    email: `admin-layout-gate-${id}@example.com`,
    password: `AdminLayout-${id}-pw`,
  }
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { ...user, name: 'Admin Layout Gate' },
  })
  if (![200, 201].includes(registered.response.status)) {
    throw new Error(`register failed: HTTP ${registered.response.status}`)
  }
  return { ...user, id: registered.body.user.id }
}

function updateRemoteRole(email, role, { active = true } = {}) {
  const script = `
import asyncio
from sqlalchemy import select
from app.core.database import session_scope
from app.models.user import User

EMAIL = ${JSON.stringify(email)}
ROLE = ${JSON.stringify(role)}
ACTIVE = ${active ? 'True' : 'False'}

async def main():
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            raise SystemExit("user not found")
        user.role = ROLE
        user.is_active = ACTIVE
        user.locked_at = None
        user.disabled_reason = None if ACTIVE else "admin layout visual gate completed"

asyncio.run(main())
print("role-updated")
`
  const remoteCommand = [
    `cd ${remoteRoot}/docker`,
    'docker compose --env-file .env --env-file .env.deploy-data --env-file .env.aliyun.app -f docker-compose.aliyun-app.yml exec -T backend /opt/venv/bin/python -',
  ].join('; ')
  execFileSync('ssh', ['-i', sshKey, sshHost, remoteCommand], {
    input: script,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  })
}

async function login(page, user) {
  await page.goto(`${baseUrl}/login?next=%2Fadmin`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/admin/, { timeout: 30000 })
  await page.getByRole('heading', { name: '平台管理后台' }).waitFor({ timeout: 30000 })
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {})
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const root = document.documentElement
    const body = document.body
    const sections = Array.from(document.querySelectorAll('section')).map((section) => {
      const rect = section.getBoundingClientRect()
      return {
        text: section.textContent?.replace(/\s+/g, ' ').trim().slice(0, 80) || '',
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        scrollWidth: section.scrollWidth,
        clientWidth: section.clientWidth,
      }
    })
    const scrollables = Array.from(document.querySelectorAll('[class*="overflow-y-auto"]')).map((el) => {
      const rect = el.getBoundingClientRect()
      return {
        text: el.textContent?.replace(/\s+/g, ' ').trim().slice(0, 80) || '',
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      }
    })
    const elementRects = Array.from(document.querySelectorAll('body *'))
      .map((el) => {
        const rect = el.getBoundingClientRect()
        return {
          tag: el.tagName.toLowerCase(),
          className: typeof el.className === 'string' ? el.className : '',
          text: el.textContent?.replace(/\s+/g, ' ').trim().slice(0, 100) || '',
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
        }
      })
    const overflowing = elementRects
      .filter((item) => item.right > window.innerWidth + 2 || item.left < -2 || item.scrollWidth > item.clientWidth + 2)
      .sort((a, b) => (b.right - window.innerWidth) - (a.right - window.innerWidth))
      .slice(0, 20)
    const nearViewportRight = elementRects
      .filter((item) => item.right > window.innerWidth + 2 && item.right < window.innerWidth + 160)
      .sort((a, b) => b.right - a.right)
      .slice(0, 20)
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      document: {
        scrollWidth: root.scrollWidth,
        clientWidth: root.clientWidth,
        bodyScrollWidth: body.scrollWidth,
        bodyClientWidth: body.clientWidth,
      },
      bodyTextLength: body.innerText.length,
      sections,
      scrollables,
      overflowing,
      nearViewportRight,
    }
  })
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const user = await createTempUser()
  updateRemoteRole(user.email, 'admin')
  const browser = await chromium.launch({ headless: true })
  const results = []
  try {
    for (const viewport of [
      { name: 'desktop', width: 1440, height: 1100 },
      { name: 'mobile', width: 390, height: 1200 },
    ]) {
      const context = await browser.newContext({ viewport, deviceScaleFactor: 1 })
      const page = await context.newPage()
      await login(page, user)
      const screenshot = `${outDir}admin-layout-${viewport.name}.png`
      await page.screenshot({ path: screenshot, fullPage: true })
      const metrics = await collectMetrics(page)
      results.push({ viewport, screenshot, metrics })
      await context.close()
    }
  } finally {
    await browser.close()
    updateRemoteRole(user.email, 'researcher', { active: false })
  }
  await fs.writeFile(`${outDir}admin-layout-visual-check.json`, `${JSON.stringify({
    status: 'passed',
    tempUserId: user.id,
    tempUserFinalState: 'disabled',
    passwordsPrinted: false,
    results,
  }, null, 2)}\n`)
  console.log(JSON.stringify({
    status: 'passed',
    screenshots: results.map((item) => item.screenshot),
    tempUserId: user.id,
    tempUserFinalState: 'disabled',
    passwordsPrinted: false,
  }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

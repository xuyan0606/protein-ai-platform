import fs from 'node:fs'
import { execFileSync } from 'node:child_process'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const sshKey = process.env.ADMIN_LIVE_SSH_KEY || `${process.env.HOME}/.ssh/id_ed25519`
const sshHost = process.env.ADMIN_LIVE_SSH_HOST || 'root@120.27.108.138'
const remoteRoot = process.env.ADMIN_LIVE_REMOTE_ROOT || '/opt/protein-ai-platform/current'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MOS/Google Chrome'
const fallbackChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)
  || (fs.existsSync(fallbackChromePath) ? fallbackChromePath : undefined)

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

async function createTempUser() {
  const id = randomId()
  const email = `admin-ui-gate-${id}@example.com`
  const password = `AdminUi-${id}-pw`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: 'Admin UI Gate' },
  })
  if (![200, 201].includes(registered.response.status)) {
    throw new Error(`register failed: HTTP ${registered.response.status}`)
  }
  return { email, password, id: registered.body.user.id }
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
        user.disabled_reason = None if ACTIVE else "admin ui live gate completed"

asyncio.run(main())
print("role-updated")
`
  const remoteCommand = [
    `cd ${remoteRoot}/docker`,
    'docker compose --env-file .env --env-file .env.deploy-data --env-file .env.aliyun.app -f docker-compose.aliyun-app.yml exec -T backend /opt/venv/bin/python -',
  ].join('; ')
  const output = execFileSync('ssh', ['-i', sshKey, sshHost, remoteCommand], {
    input: script,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  if (!output.includes('role-updated')) {
    throw new Error(`remote role update did not confirm: ${output.slice(0, 200)}`)
  }
}

async function loginViaUi(page, user) {
  await page.goto(`${baseUrl}/login?next=%2Fadmin`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/admin/, { timeout: 30000 })
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {})
}

async function runAdminPageSmoke(page) {
  await page.getByRole('heading', { name: '平台管理后台' }).waitFor({ timeout: 30000 })
  for (const text of ['用户与角色', '任务审计', '组织与项目授权', '数据资产状态', '权限边界说明']) {
    await page.getByText(text).first().waitFor({ timeout: 15000 })
  }

  const body = await page.locator('body').innerText()
  if (!body.includes('Admin UI Gate')) {
    throw new Error('temporary admin user was not visible in the admin user list')
  }
  if (!/users|任务审计|数据资产|组织/.test(body)) {
    throw new Error(`admin body missing expected business text: ${body.slice(0, 500)}`)
  }

  const downloadPromise = page.waitForEvent('download', { timeout: 30000 })
  await page.getByRole('button', { name: /导出 CSV/ }).click()
  const download = await downloadPromise
  const suggestedFilename = download.suggestedFilename()
  const failure = await download.failure()
  if (failure) {
    throw new Error(`CSV download failed: ${failure}`)
  }
  if (!suggestedFilename.endsWith('.csv')) {
    throw new Error(`unexpected CSV filename: ${suggestedFilename}`)
  }

  const importResponsePromise = page.waitForResponse(
    (response) => response.url().includes('/api/data/admin/import') && response.request().method() === 'POST',
    { timeout: 30000 },
  )
  await page.getByRole('button', { name: /生成 dry-run 导入计划/ }).click()
  const importResponse = await importResponsePromise
  if (importResponse.status() !== 200) {
    throw new Error(`deploy_data dry-run import returned HTTP ${importResponse.status()}`)
  }
  await page.getByText(/dry-run|导入计划/).first().waitFor({ timeout: 30000 })

  return {
    bodyLength: body.length,
    suggestedFilename,
    importDryRunStatus: importResponse.status(),
  }
}

async function main() {
  const user = await createTempUser()
  updateRemoteRole(user.email, 'admin')

  const browser = await chromium.launch({ headless: true, executablePath })
  const context = await browser.newContext({ acceptDownloads: true })
  const page = await context.newPage()
  const consoleErrors = []
  const httpErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('response', (response) => {
    const status = response.status()
    const url = response.url()
    if (status >= 400 && !url.includes('/favicon')) {
      httpErrors.push({ status, url })
    }
  })

  let adminPage = null
  try {
    await loginViaUi(page, user)
    adminPage = await runAdminPageSmoke(page)
  } finally {
    await browser.close()
    updateRemoteRole(user.email, 'researcher', { active: false })
  }

  if (consoleErrors.length || httpErrors.length) {
    throw new Error(JSON.stringify({ consoleErrors, httpErrors }, null, 2))
  }

  console.log(JSON.stringify({
    status: 'passed',
    adminPage,
    consoleErrors: consoleErrors.length,
    httpErrors: httpErrors.length,
    tempUserId: user.id,
    tempUserFinalState: 'disabled',
    tokensPrinted: false,
    passwordsPrinted: false,
  }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

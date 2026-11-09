import fs from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://120.27.108.138'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)

function randomId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function logStage(stage) {
  console.error(`[workbench-live] ${stage}`)
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
  const email = `codex-workbench-${id}@example.com`
  const password = `Codex-${id}-pw`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: 'Codex Workbench Deep' },
  })
  if (![200, 201].includes(registered.response.status)) {
    throw new Error(`register failed: HTTP ${registered.response.status}`)
  }
  return { email, password, token: registered.body.access_token }
}

async function loginViaUi(page, user) {
  await page.goto(`${baseUrl}/login?next=%2Fhome`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[autocomplete="username"]').fill(user.email)
  await page.locator('input[autocomplete="current-password"]').fill(user.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/home/, { timeout: 30000 })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
}

async function waitForStreamingDone(page, label, timeout = 120000) {
  await page.waitForFunction(() => {
    return /Agent is responding|Streaming response/i.test(document.body.innerText)
  }, undefined, { timeout: 45000 }).catch(() => {})
  try {
    await page.waitForFunction(() => {
      return !/Agent is responding|Streaming response/i.test(document.body.innerText)
    }, undefined, { timeout })
  } catch (error) {
    const debug = await page.evaluate(() => ({
      url: window.location.href,
      currentConversationId: window.localStorage.getItem('currentConversationId'),
      historyState: window.history.state,
      bodyPreview: document.body.innerText.slice(0, 1600),
    }))
    throw new Error(`${label}: streaming did not finish within ${timeout}ms; debug=${JSON.stringify(debug)}`)
  }
  const currentId = await page.evaluate(() => window.localStorage.getItem('currentConversationId'))
  if (!currentId) {
    const debug = await page.evaluate(() => ({
      url: window.location.href,
      historyState: window.history.state,
      bodyPreview: document.body.innerText.slice(0, 1200),
      tokenPresent: Boolean(window.localStorage.getItem('token')),
      refreshTokenPresent: Boolean(window.localStorage.getItem('refreshToken')),
    }))
    throw new Error(`${label}: currentConversationId missing; debug=${JSON.stringify(debug)}`)
  }
  return currentId
}

async function runHomeQuickPrompt(page) {
  await page.goto(`${baseUrl}/home`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  if (await page.getByText('管理后台').count()) {
    throw new Error('admin card is visible to a normal researcher')
  }
  const clicked = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'))
    const target = buttons.find((button) => {
      const text = button.innerText || ''
      return /stability|稳定|热稳定/i.test(text) && !/start chat|开始/i.test(text)
    })
    if (!target) return false
    target.click()
    return true
  })
  if (!clicked) {
    const buttons = await page.locator('button').evaluateAll((nodes) => nodes.map((node) => node.innerText))
    throw new Error(`quick analysis stability button not found; buttons=${JSON.stringify(buttons)}`)
  }
  await page.waitForURL(/\/chat\/agent/, { timeout: 30000 })
  const currentConversationId = await waitForStreamingDone(page, 'home quick prompt')
  const body = await page.textContent('body') || ''
  if (!/stability|稳定|热稳定|蛋白/.test(body)) {
    throw new Error('quick prompt did not inject a protein stability prompt')
  }
  return { currentConversationId }
}

async function runHomeUploadEntry(page) {
  await page.goto(`${baseUrl}/home`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
  const fasta = [
    '>codex_workbench_smoke',
    'MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPQ',
    '',
  ].join('\n')
  const tmpPath = `/tmp/protein-ai-workbench-${randomId()}.fasta`
  fs.writeFileSync(tmpPath, fasta)
  await page.locator('input[type="file"]').setInputFiles(tmpPath)
  await page.waitForURL(/\/chat\/agent/, { timeout: 30000 })
  await page.getByText(/protein-ai-workbench-.*\.fasta/).waitFor({ timeout: 20000 })
  const currentConversationId = await waitForStreamingDone(page, 'home upload entry')
  return { currentConversationId }
}

async function createProjectViaUi(page, stamp) {
  const projectName = `workbench-live-${stamp}`
  await page.goto(`${baseUrl}/projects`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /new project/i }).click()
  await page.locator('input[placeholder^="Project name"]').fill(projectName)
  await page.locator('textarea[placeholder^="Description"]').fill('Codex live workbench project')
  await page.getByRole('button', { name: /^Create$/ }).click()
  await page.waitForURL(/\/projects\/[^/]+$/, { timeout: 30000 })
  await page.getByText(projectName, { exact: true }).waitFor({ timeout: 30000 })
  const projectId = page.url().split('/projects/')[1]
  if (!projectId) throw new Error('project id missing after create')
  return { projectId, projectName }
}

async function runProjectDetail(page, projectName) {
  const sequenceName = `seq-${randomId()}`
  await page.getByRole('button', { name: /add sequence/i }).click()
  await page.locator('input[placeholder^="Sequence name"]').fill(sequenceName)
  await page.locator('textarea[placeholder^="Amino acid sequence"]').fill('MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPQ')
  await page.locator('input[placeholder^="Notes"]').fill('live gate sequence')
  await page.getByRole('button', { name: /^Add$/ }).click()
  await page.getByText(sequenceName, { exact: true }).waitFor({ timeout: 30000 })
  await page.getByText('Sequences (1)').waitFor({ timeout: 30000 })

  await page.getByRole('button', { name: /Properties/i }).click()
  await page.getByRole('button', { name: /Run on 1 sequences/i }).click()
  await page.getByText(/Running\.\.\./).waitFor({ timeout: 5000 }).catch(() => {})
  await page.getByText('Results (1)').waitFor({ timeout: 60000 })
  await page.getByRole('button', { name: /Results/i }).click()
  await page.getByText(sequenceName, { exact: true }).waitFor({ timeout: 30000 })

  await page.getByRole('button', { name: /Wiki/i }).click()
  await page.getByText(/知识库|暂无Wiki文档|选择左侧文档/).first().waitFor({ timeout: 30000 })

  await page.getByRole('button', { name: /Sequences/i }).click()
  await page.locator('button').filter({ hasText: '' }).count()
  await page.getByText(projectName, { exact: true }).waitFor({ timeout: 10000 })
  return { sequenceName, batchResultsVisible: true, wikiTabUsable: true }
}

async function runSecondaryRoutes(page) {
  const routes = [
    { route: '/benchmarks', expected: /Benchmark Library|真实项目基准案例/ },
    { route: '/benchmarks/venus-15b', expected: /Venus-15B 低 pH|候选突变位点|资产状态/ },
    { route: '/pdb', expected: /PDB|结构|上传|Structure/i },
    { route: '/wiki', expected: /Knowledge Base|Wiki|知识库|文档|Outline/i },
    { route: '/data', expected: /Data|数据|Readiness|PDB|真实数据/i },
    { route: '/admin', expected: /Admin|管理|权限|无权|Forbidden|not authorized/i },
  ]
  const results = []
  for (const { route, expected } of routes) {
    const response = await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {})
    try {
      await page.waitForFunction(
        ({ source, flags }) => {
          return new RegExp(source, flags).test(document.body.innerText)
        },
        { source: expected.source, flags: expected.flags },
        { timeout: 30000 }
      )
    } catch (error) {
      const debug = await page.evaluate(() => ({
        url: window.location.href,
        bodyPreview: document.body.innerText.slice(0, 1200),
      }))
      throw new Error(`${route}: expected page marker not found; debug=${JSON.stringify(debug)}`)
    }
    const body = await page.textContent('body') || ''
    if (!response || response.status() >= 500) {
      throw new Error(`${route}: HTTP ${response?.status()}`)
    }
    results.push({ route, status: response.status(), bodyLength: body.length })
  }
  return results
}

async function deleteProject(token, projectId) {
  await requestJson(`/api/projects/${projectId}`, { method: 'DELETE', token }).catch(() => undefined)
}

const user = await createLiveUser()
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
page.setDefaultNavigationTimeout(60000)
page.setDefaultTimeout(45000)
const consoleErrors = []
const httpErrors = []
let projectId = null

page.on('pageerror', (error) => {
  consoleErrors.push(`pageerror: ${error.message}`)
})
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(`console:${msg.text()}`)
})
page.on('response', (response) => {
  const status = response.status()
  if (status >= 500) httpErrors.push(`${status} ${response.url()}`)
})

try {
  logStage('login')
  await loginViaUi(page, user)
  logStage('home quick prompt')
  const homeQuick = await runHomeQuickPrompt(page)
  logStage('home upload entry')
  const homeUpload = await runHomeUploadEntry(page)
  logStage('project create')
  const createdProject = await createProjectViaUi(page, randomId())
  projectId = createdProject.projectId
  logStage('project detail')
  const projectDetail = await runProjectDetail(page, createdProject.projectName)
  logStage('secondary routes')
  const secondaryRoutes = await runSecondaryRoutes(page)

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
      homeQuick,
      homeUpload,
      project: {
        id: projectId,
        name: createdProject.projectName,
        ...projectDetail,
      },
      secondaryRoutes,
    },
    consoleErrors: 0,
    httpErrors: 0,
    secretsPrinted: false,
  }, null, 2))
} finally {
  await browser.close()
  if (projectId) {
    await deleteProject(user.token, projectId)
  }
}

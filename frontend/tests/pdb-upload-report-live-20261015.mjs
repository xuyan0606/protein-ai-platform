import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const base = process.env.PDB_LIVE_BASE || 'http://120.27.108.138:4200'
const output = process.env.PDB_LIVE_BROWSER_OUT
const pdb = process.env.PDB_LIVE_BROWSER_SAMPLE
if (!output || !pdb) throw new Error('PDB_LIVE_BROWSER_OUT and PDB_LIVE_BROWSER_SAMPLE are required')
fs.mkdirSync(output, { recursive: true })
const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
const credentials = { email: `pdb-live-20261015-browser-${id}@example.com`, password: `Pdb${id}A!`, name: 'PDB Browser QA' }
const result = { user_id: null, requests: [], task_statuses: [], checks: {}, failures: [], conversation_id: null, object_name: null }
let token
let browser

function check(name, okay, detail) {
  result.checks[name] = { pass: !!okay, detail }
  if (!okay) result.failures.push(name)
  process.stdout.write(JSON.stringify({ check: name, pass: !!okay, detail }) + '\n')
}

async function api(route, opts = {}) {
  const response = await fetch(base + route, { ...opts, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
  let body = null
  try { body = await response.json() } catch { /* 204 */ }
  return { status: response.status, body }
}

try {
  const registered = await api('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(credentials) })
  if (registered.status !== 201) throw new Error(`register HTTP ${registered.status}`)
  token = registered.body.access_token
  result.user_id = registered.body.user.id
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  browser = await chromium.launch({ headless: true, ...(fs.existsSync(chrome) ? { executablePath: chrome } : {}) })
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 920 } })
  const page = await context.newPage()
  page.on('response', async response => {
    const url = response.url()
    if (/\/api\/tools\/tasks\/[a-f0-9-]+$/.test(url) && response.status() === 200) {
      try { result.task_statuses.push((await response.json()).status) } catch { /* ignored */ }
    }
    if (!/\/api\/(files\/upload|pdb\/analyze-by-name|chat\/stream)/.test(url)) return
    const entry = { method: response.request().method(), path: new URL(url).pathname, status: response.status() }
    result.requests.push(entry)
    if (entry.path === '/api/files/upload' && entry.status === 200) {
      try { result.object_name = (await response.json()).id } catch { /* keep status */ }
    }
  })
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  await page.evaluate(auth => {
    localStorage.setItem('token', auth.access_token)
    if (auth.refresh_token) localStorage.setItem('refreshToken', auth.refresh_token)
    window.dispatchEvent(new Event('protein-ai:auth-updated'))
  }, registered.body)
  await page.goto(base + '/chat/agent', { waitUntil: 'domcontentloaded' })
  await page.locator('textarea').last().waitFor({ timeout: 30000 })
  await page.locator('input[type="file"]').setInputFiles(path.resolve(pdb))
  await page.getByText(path.basename(pdb), { exact: false }).first().waitFor({ timeout: 15000 })
  await page.locator('textarea').last().fill('请分析上传的 PDB 结构、稳定性改造风险和证据边界，生成完整报告。')
  await page.locator('textarea').last().press('Enter')
  await page.getByRole('button', { name: '确认执行' }).waitFor({ timeout: 120000 })
  result.conversation_id = await page.evaluate(() => localStorage.getItem('currentConversationId'))
  check('browser_upload_and_analysis_request', result.requests.some(x => x.path === '/api/files/upload' && x.status === 200) && result.requests.some(x => x.path === '/api/pdb/analyze-by-name' && x.status === 200), result.requests)
  check('browser_plan_visible', !!result.conversation_id, { conversation_id: result.conversation_id })
  await page.getByRole('button', { name: '确认执行' }).click()
  await page.getByText('酶蛋白工程分析报告', { exact: false }).first().waitFor({ timeout: 180000 })
  await page.getByText('正在生成或传输结果', { exact: false }).waitFor({ state: 'hidden', timeout: 180000 }).catch(() => {})
  await page.waitForTimeout(1200)
  check('browser_report_visible', (await page.locator('body').innerText()).includes('酶蛋白工程分析报告'), { chat_requests: result.requests.filter(x => x.path === '/api/chat/stream').length })
  if (process.env.PDB_LIVE_BROWSER_CHECK_TASK) {
    const deadline = Date.now() + 170000
    while (Date.now() < deadline && !result.task_statuses.some(x => ['completed', 'degraded', 'failed', 'canceled'].includes(x))) {
      await page.waitForTimeout(3000)
    }
    const terminal = result.task_statuses.find(x => ['completed', 'degraded', 'failed', 'canceled'].includes(x))
    check('browser_async_task_terminal_visible', Boolean(terminal) && (await page.locator('body').innerText()).includes(terminal === 'degraded' ? 'Degraded' : terminal === 'completed' ? 'Complete' : 'Failed'), { statuses: result.task_statuses })
  }
  await page.screenshot({ path: path.join(output, 'report.png'), fullPage: true })
  try {
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 })
    await page.getByRole('button', { name: 'Export report' }).click()
    const download = await downloadPromise
    const reportPath = path.join(output, 'browser-report.html')
    await download.saveAs(reportPath)
    const html = fs.readFileSync(reportPath, 'utf8')
    check('browser_html_export', html.includes('酶蛋白工程分析报告') && html.length > 1000, { bytes: Buffer.byteLength(html) })
  } catch (error) {
    check('browser_html_export', false, String(error).slice(0, 250))
  }
} catch (error) {
  result.failures.push('fatal')
  result.error = String(error).slice(0, 500)
  process.stderr.write(result.error + '\n')
} finally {
  if (browser) await browser.close()
  if (token && result.conversation_id) result.conversation_cleanup = (await api(`/api/conversations/${result.conversation_id}`, { method: 'DELETE' })).status
  if (token && result.object_name) result.file_cleanup = (await api(`/api/files/${result.object_name}`, { method: 'DELETE' })).status
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2))
  process.stdout.write(JSON.stringify({ result_file: path.join(output, 'results.json'), user_id: result.user_id, failures: result.failures }) + '\n')
}
if (result.failures.length) process.exitCode = 2

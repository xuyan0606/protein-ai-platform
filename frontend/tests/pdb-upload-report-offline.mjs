import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const baseUrl = process.env.PDB_REPORT_TEST_BASE || 'http://127.0.0.1:4210'
const outputDir = process.env.PDB_REPORT_TEST_OUT || '/private/tmp/protein-ai-pdb-report-offline'
const systemChromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  || (fs.existsSync(systemChromePath) ? systemChromePath : undefined)
const conversationId = 42019
const plan = [
  {
    id: 1,
    tool_name: 'structure_search_foldseek',
    description: 'Parse the uploaded PDB structure and source metadata',
    params: { pdb_object_name: 'uploads/user_7/sample.pdb' },
    status: 'pending',
  },
  {
    id: 2,
    tool_name: 'mutation_priority_score',
    description: 'Summarize evidence gates and reportable mutation hypotheses',
    params: { pdb_object_name: 'uploads/user_7/sample.pdb' },
    status: 'pending',
  },
]
const mutationResult = {
  engineering_goal: 'general',
  candidate_table_status: 'blocked_by_identity_gate',
  identity_gate: {
    status: 'blocked',
    identity_status: 'unresolved',
    reason: 'Mocked PDB-only run: numbering evidence has not been mapped.',
  },
  summary: {
    total_positions: 36,
    tier_1_count: 0,
    tier_2_count: 0,
    tier_3_count: 0,
    never_mutate_count: 0,
    never_mutate_positions: [],
  },
  active_site_positions: [],
  tier_1_candidates: [],
  tier_2_candidates: [],
  all_positions: [],
}
const signature = 'offline-pdb-report-signature-20261019'
const fingerprint = 'offline-pdb-report-fingerprint-20261019'
const result = { requests: [], checks: {}, failures: [], console_errors: [], page_errors: [] }
let streamCount = 0
let checkpointActive = true
let browser

function check(name, pass, detail) {
  result.checks[name] = { pass: Boolean(pass), detail }
  if (!pass) result.failures.push(name)
  process.stdout.write(`${pass ? 'PASS' : 'FAIL'} ${name}: ${JSON.stringify(detail)}\n`)
}

function jsonBody(data) {
  return { contentType: 'application/json', body: JSON.stringify(data) }
}

function sse(events) {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
}

function completedState() {
  return {
    type: 'state',
    stage: 'done',
    waiting_for: null,
    plan: plan.map((step) => ({ ...step, status: 'completed' })),
    current_step: 2,
    step_results: [
      {
        step: 1,
        tool: 'structure_search_foldseek',
        status: 'completed',
        result_preview: JSON.stringify({
          query_structure: {
            total_residues: 36,
            method: 'X-RAY DIFFRACTION',
            resolution: 1.65,
            chains: [{ chain_id: 'A', residue_count: 36 }],
          },
        }),
      },
      {
        step: 2,
        tool: 'mutation_priority_score',
        status: 'completed',
        result_preview: JSON.stringify(mutationResult),
      },
    ],
    strategy_signature: signature,
    task_fingerprint: fingerprint,
  }
}

async function fulfillJson(route, data, status = 200) {
  const currentRequest = result.requests[result.requests.length - 1]
  if (currentRequest) currentRequest.status = status
  await route.fulfill({ status, ...jsonBody(data) })
}

async function run() {
  fs.mkdirSync(outputDir, { recursive: true })
  browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 960 } })
  const page = await context.newPage()
  page.on('console', (message) => {
    if (message.type() === 'error') result.console_errors.push(message.text())
  })
  page.on('pageerror', (error) => result.page_errors.push(error.message))

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()
    const pathname = url.pathname
    result.requests.push({ method, path: pathname })

    if (method === 'GET' && pathname === '/api/chat/models') {
      return fulfillJson(route, [{
        id: 'gpt6-sol', name: 'GPT-6-sol', provider: 'openai', model: 'gpt-6-sol',
        description: 'Offline browser test model', available: true,
      }])
    }
    if (method === 'GET' && pathname === '/api/tools') {
      return fulfillJson(route, { tools: [], categories: {} })
    }
    if (method === 'GET' && pathname === '/api/conversations') {
      return fulfillJson(route, [{ id: conversationId, title: 'PDB report offline test', message_count: 4 }])
    }
    if (method === 'GET' && pathname === '/api/chat/strategy-checkpoints/active') {
      const state = checkpointActive ? {
        stage: 'plan',
        waiting_for: 'plan_confirmation',
        plan,
        current_step: 0,
        step_results: [],
        strategy_signature: signature,
        task_fingerprint: fingerprint,
        next_action: 'confirm_execute',
        artifacts: {},
      } : null
      return fulfillJson(route, {
        checkpoint: checkpointActive ? {
          id: 'offline-checkpoint', status: 'awaiting_confirmation',
          strategy_signature: signature, task_fingerprint: fingerprint,
          plan_payload: plan, next_action: 'confirm_execute',
        } : null,
        agent_state: state,
      })
    }
    if (method === 'GET' && pathname === '/api/chat/strategy-checkpoints/history') {
      return fulfillJson(route, { records: [] })
    }
    if (method === 'GET' && pathname === '/api/chat/strategy-checkpoints/recent') {
      return fulfillJson(route, { records: [], scope: { type: 'conversation', conversation_id: conversationId } })
    }
    if (method === 'POST' && pathname === '/api/files/upload') {
      return fulfillJson(route, {
        id: 'uploads/user_7/sample.pdb',
        object_name: 'uploads/user_7/sample.pdb',
        name: 'sample.pdb',
        size: 540,
        content_type: 'chemical/x-pdb',
        download_url: '/api/files/uploads/user_7/sample.pdb/download',
      })
    }
    if (method === 'POST' && pathname === '/api/pdb/analyze-by-name') {
      return fulfillJson(route, {
        object_name: 'uploads/user_7/sample.pdb',
        title: 'Offline PDB fixture',
        total_residues: 36,
        total_atoms: 288,
        chains: [{ chain_id: 'A', residue_count: 36, atom_count: 288 }],
      })
    }
    if (method === 'POST' && pathname === '/api/chat/stream') {
      streamCount += 1
      let body = {}
      try { body = request.postDataJSON() } catch { /* captured below */ }
      result.requests[result.requests.length - 1].payload = body
      result.requests[result.requests.length - 1].status = 200
      if (streamCount === 1) {
        const events = [
          {
            type: 'state', stage: 'plan', waiting_for: 'plan_confirmation', plan,
            current_step: 0, step_results: [], strategy_signature: signature,
            task_fingerprint: fingerprint, next_action: 'confirm_execute',
          },
          {
            type: 'text',
            content: '分析策略确认\n状态：等待确认，未执行工具。\n策略依据上传的 PDB 结构生成。',
          },
          { type: 'done', conversation_id: conversationId },
        ]
        return route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse(events) })
      }

      const events = [
        completedState(),
        {
          type: 'text',
          content: '# 酶蛋白工程分析报告\n\n## 输入与编号边界\nPDB-only；当前不把结构编号声明为 UniProt 编号。\n\n## 下一步实验建议\n先建立 WT 基线，再验证候选。',
        },
        { type: 'done', conversation_id: conversationId },
      ]
      checkpointActive = false
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse(events) })
    }

    return fulfillJson(route, {})
  })

  await page.goto(`${baseUrl}/chat/agent`, { waitUntil: 'domcontentloaded' })
  await page.locator('textarea').last().waitFor({ timeout: 30000 })
  await page.locator('input[type="file"]').setInputFiles({
    name: 'sample.pdb',
    mimeType: 'chemical/x-pdb',
    buffer: Buffer.from('SEQRES   1 A    1  ALA\nATOM      1  CA  ALA A   1      11.000  12.000  13.000  1.00 20.00           C\nEND\n'),
  })
  await page.getByText('sample.pdb', { exact: false }).first().waitFor({ timeout: 15000 })
  await page.locator('textarea').last().fill('请深度分析上传的 PDB，并给出有证据边界的实验建议。')
  await page.locator('textarea').last().press('Enter')

  await page.getByRole('button', { name: '确认执行' }).waitFor({ timeout: 30000 })
  const firstPayload = result.requests.find((item) => item.path === '/api/chat/stream')?.payload || {}
  check('pdb_upload_and_preanalysis',
    result.requests.some((item) => item.path === '/api/files/upload' && item.method === 'POST' && item.status === 200)
      && result.requests.some((item) => item.path === '/api/pdb/analyze-by-name' && item.method === 'POST' && item.status === 200)
      && result.requests.some((item) => item.path === '/api/chat/stream' && item.method === 'POST' && item.status === 200)
      && String(firstPayload.message || '').includes('name: sample.pdb')
      && String(firstPayload.message || '').includes('uploads/user_7/sample.pdb'),
    { request_count: result.requests.length, uploaded_name_in_chat: String(firstPayload.message || '').includes('name: sample.pdb') },
  )
  check('plan_waits_for_confirmation',
    streamCount === 1
      && (await page.locator('body').innerText()).includes('尚未执行工具')
      && (await page.getByRole('button', { name: '确认执行' }).isVisible()),
    { visible: true },
  )

  await page.getByRole('button', { name: '确认执行' }).click()
  await page.getByText('酶蛋白工程分析报告', { exact: false }).first().waitFor({ timeout: 30000 })
  await page.getByText('PDB-only；当前不把结构编号声明为 UniProt 编号。', { exact: false }).waitFor({ timeout: 15000 })
  const executeRequest = result.requests.filter((item) => item.path === '/api/chat/stream')[1]
  check('confirmed_plan_execution_and_report',
    streamCount === 2
      && executeRequest?.status === 200
      && executeRequest?.payload?.agent_control === 'execute_confirmed'
      && executeRequest.payload.strategy_signature === signature
      && Array.isArray(executeRequest.payload.confirmed_plan)
      && JSON.stringify(executeRequest.payload.confirmed_plan) === JSON.stringify(plan)
      && (await page.locator('body').innerText()).includes('先建立 WT 基线'),
    { stream_count: streamCount, control: executeRequest?.payload?.agent_control, report_visible: true },
  )

  const mutationCard = page.getByRole('button').filter({ hasText: 'mutation_priority_score' }).last()
  if (await mutationCard.count()) await mutationCard.click()
  const reportBody = await page.locator('body').innerText()
  await page.screenshot({ path: path.join(outputDir, 'report-before-export.png'), fullPage: true })
  check('completed_tool_result_rendered',
    (reportBody.includes('blocked_by_identity_gate') || reportBody.includes('突变候选输出门控'))
      && !reportBody.includes('undefined'),
    {
      contains_gate: reportBody.includes('突变候选输出门控'),
      has_undefined: reportBody.includes('undefined'),
      tail: reportBody.slice(-1800),
    },
  )

  const downloadPromise = page.waitForEvent('download', { timeout: 15000 })
  await page.getByRole('button', { name: 'Export report' }).click()
  const download = await downloadPromise
  const reportPath = path.join(outputDir, download.suggestedFilename())
  await download.saveAs(reportPath)
  const html = fs.readFileSync(reportPath, 'utf8')
  check('html_report_export',
    html.includes('酶蛋白工程分析报告')
      && html.includes('突变优先级报告')
      && html.includes('PDB-only')
      && html.length > 1000,
    { bytes: Buffer.byteLength(html), path: reportPath },
  )

  check('browser_health', result.console_errors.length === 0 && result.page_errors.length === 0,
    { console_errors: result.console_errors, page_errors: result.page_errors },
  )
  check('no_server_errors', !result.requests.some((item) => (item.status || 0) >= 500),
    { api_requests: result.requests.length },
  )
  await page.screenshot({ path: path.join(outputDir, 'report.png'), fullPage: true })
}

try {
  await run()
} catch (error) {
  result.failures.push('fatal')
  result.error = String(error)
  process.stderr.write(`${result.error}\n`)
} finally {
  if (browser) await browser.close()
  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(path.join(outputDir, 'results.json'), JSON.stringify(result, null, 2))
  process.stdout.write(`Results: ${path.join(outputDir, 'results.json')}\n`)
}

if (result.failures.length > 0) process.exitCode = 1

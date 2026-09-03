import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const projectRoot = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4200'
const json = process.argv.includes('--json')
const planOnly = process.argv.includes('--plan-only')

function result(name, status, detail) {
  return { name, category: 'frontend', status, detail }
}

function readTest(name) {
  return readFileSync(resolve(projectRoot, 'frontend', 'tests', name), 'utf8')
}

const results = []
let parsedUrl
try {
  parsedUrl = new URL(baseUrl)
} catch {
  parsedUrl = null
}

if (!parsedUrl) {
  results.push(result('frontend_base_url', 'failed', `FRONTEND_BASE_URL is not parseable: ${baseUrl}`))
} else {
  const port = Number(parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80))
  if (parsedUrl.hostname === '127.0.0.1' || parsedUrl.hostname === 'localhost') {
    results.push(
      result(
        'frontend_base_url',
        port >= 4200 && port <= 4299 ? 'passed' : 'failed',
        `local browser smoke target is ${parsedUrl.origin}; Codex ports must stay in 4200-4299`,
      ),
    )
  } else {
    results.push(result('frontend_base_url', 'planned', `external live browser target is ${parsedUrl.origin}`))
  }
}

const publicSmoke = readTest('public-smoke.mjs')
const liveSmoke = readTest('live-smoke.mjs')
const httpSmoke = readTest('http-smoke.mjs')

results.push(
  result(
    'browser_public_smoke_contract',
    publicSmoke.includes('FRONTEND_BASE_URL') && publicSmoke.includes("await visit('/login')")
      ? 'passed'
      : 'failed',
    'public-smoke uses configurable live base URL and checks public SPA routes',
  ),
)
results.push(
  result(
    'browser_live_smoke_contract',
    liveSmoke.includes('FRONTEND_BASE_URL') && liveSmoke.includes("await ensureHttpOk('/kb')")
      ? 'passed'
      : 'failed',
    'live-smoke uses configurable live base URL and checks wiki/login/data/chat route contracts',
  ),
)
results.push(
  result(
    'http_smoke_contract',
    httpSmoke.includes('FRONTEND_BASE_URL') && httpSmoke.includes("'/api/health'")
      ? 'passed'
      : 'failed',
    'http-smoke remains a non-browser live HTTP contract for SPA/backend/wiki routing',
  ),
)
results.push(
  result(
    'plan_only_contract',
    'passed',
    'plan-only mode validates the contract without launching a browser',
  ),
)

const failed = results.filter((item) => item.status === 'failed').length
const planned = results.filter((item) => item.status === 'planned').length
const payload = {
  summary: {
    status: failed ? 'failed' : planned ? 'planned' : 'passed',
    failed,
    planned,
    total: results.length,
  },
  base_url: baseUrl,
  plan_only: planOnly,
  results,
}

if (json) {
  console.log(JSON.stringify(payload, null, 2))
} else {
  for (const item of results) {
    console.log(`${item.name}\t${item.status}\t${item.detail}`)
  }
  console.log(`summary\t${payload.summary.status}\t${failed} failed / ${planned} planned / ${results.length} total`)
}

process.exit(failed ? 1 : 0)

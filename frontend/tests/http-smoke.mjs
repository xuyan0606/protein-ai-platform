const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4200'

function explainNetworkFailure(error) {
  const message = error instanceof Error ? error.message : String(error)
  if (message.includes('fetch failed') || message.includes('connect EPERM') || message.includes('ECONNREFUSED')) {
    return new Error(`http-smoke cannot reach ${baseUrl}. Start the local frontend on port 4200 or set FRONTEND_BASE_URL to a live target before running smoke.`)
  }
  return error
}

async function request(path, init = {}) {
  const response = await fetch(`${baseUrl}${path}`, { redirect: 'manual', ...init })
  const text = await response.text()
  return { response, text }
}

function assertStatus(response, expected, label) {
  if (response.status !== expected) {
    throw new Error(`${label}: expected HTTP ${expected}, got ${response.status}`)
  }
}

function assertHtml(text, label) {
  if (!/<div id="root"><\/div>/.test(text) || !/Protein AI Platform/i.test(text)) {
    throw new Error(`${label}: expected frontend SPA HTML`)
  }
}

function assertSameOriginFrameHeader(response, label) {
  const value = response.headers.get('x-frame-options') || ''
  if (value.toLowerCase() !== 'sameorigin') {
    throw new Error(`${label}: expected X-Frame-Options=SAMEORIGIN, got ${value || '<missing>'}`)
  }
}

try {
  const publicPages = ['/login', '/home', '/data']
  for (const path of publicPages) {
    const { response, text } = await request(path)
    assertStatus(response, 200, path)
    assertHtml(text, path)
    assertSameOriginFrameHeader(response, path)
  }

  const health = await request('/api/health')
  assertStatus(health.response, 200, '/api/health')
  if (!/"status"\s*:\s*"ok"/.test(health.text)) {
    throw new Error('/api/health: expected status=ok JSON')
  }

  const nginxHealth = await request('/nginx-health')
  assertStatus(nginxHealth.response, 200, '/nginx-health')
  if (nginxHealth.text.trim() !== 'ok') {
    throw new Error(`/nginx-health: expected ok, got ${nginxHealth.text.trim() || '<empty>'}`)
  }

  const wikiDocument = await request('/wiki/home', {
    headers: {
      accept: 'text/html',
      'sec-fetch-dest': 'document',
    },
  })
  assertStatus(wikiDocument.response, 200, '/wiki/home document')
  assertHtml(wikiDocument.text, '/wiki/home document')

  const wikiEmbedded = await request('/wiki/home', {
    headers: {
      accept: 'text/html',
    },
  })
  assertStatus(wikiEmbedded.response, 302, '/wiki/home embedded/bootstrap')
  const location = wikiEmbedded.response.headers.get('location') || ''
  if (location !== '/wiki/auth/oidc') {
    throw new Error(`/wiki/home embedded/bootstrap: expected location=/wiki/auth/oidc, got ${location}`)
  }

  console.log('HTTP smoke passed')
} catch (error) {
  throw explainNetworkFailure(error)
}

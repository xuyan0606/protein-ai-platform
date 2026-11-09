import crypto from 'node:crypto'

const baseUrl = (process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:4200').replace(/\/$/, '')
const timeoutMs = Number(process.env.STRATEGY_CHAT_TIMEOUT_MS || 180000)
const sequenceA = 'MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY'
const sequenceB = 'MGGGGGGGGGGGGNNSTGGSGGAGGGGTTTTGGGGGGGSSSSGGGGGGGAAAGGGGGGG'

class ContractError extends Error {
  constructor(check, detail) {
    super(`${check}: ${detail}`)
    this.check = check
    this.detail = detail
  }
}

function assertContract(check, condition, detail) {
  if (!condition) throw new ContractError(check, detail)
}

async function requestJson(pathname, { method = 'GET', token, payload, timeout = 30000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`${baseUrl}${pathname}`, {
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
      body = { detail: text.slice(0, 500) }
    }
    return { response, body }
  } finally {
    clearTimeout(timer)
  }
}

function parseSseBuffer(buffer) {
  const frames = []
  let dataLines = []
  for (const rawLine of buffer.split(/\r?\n/)) {
    const line = rawLine.trimEnd()
    if (!line) {
      if (dataLines.length) {
        const data = dataLines.join('\n')
        try {
          frames.push(JSON.parse(data))
        } catch {
          frames.push({ type: 'raw', content: data })
        }
        dataLines = []
      }
      continue
    }
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (dataLines.length) {
    const data = dataLines.join('\n')
    try {
      frames.push(JSON.parse(data))
    } catch {
      frames.push({ type: 'raw', content: data })
    }
  }
  return frames
}

async function streamChat(token, payload) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${baseUrl}/api/chat/stream`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    })
    const text = await response.text()
    if (response.status !== 200) {
      throw new Error(`chat stream HTTP ${response.status}: ${text.slice(0, 500)}`)
    }
    return parseSseBuffer(text)
  } finally {
    clearTimeout(timer)
  }
}

function joinedText(frames) {
  return frames
    .filter((frame) => frame.type === 'text')
    .map((frame) => String(frame.content || ''))
    .join('')
}

function states(frames) {
  return frames.filter((frame) => frame.type === 'state')
}

function conversationId(frames) {
  for (const frame of frames.slice().reverse()) {
    if (Number.isInteger(frame.conversation_id)) return frame.conversation_id
  }
  return null
}

function latestPlanState(frames) {
  return states(frames).slice().reverse().find((frame) => Array.isArray(frame.plan) && frame.plan.length > 0) || null
}

function canonicalPlan(plan) {
  return JSON.stringify((plan || []).map((step) => ({
    id: step.id,
    tool_name: step.tool_name,
    description: step.description,
    params: step.params || {},
  })))
}

function toolsSeen(frames) {
  const tools = new Set()
  for (const frame of states(frames)) {
    for (const step of frame.plan || []) {
      if (step?.tool_name) tools.add(step.tool_name)
    }
    for (const result of frame.step_results || []) {
      if (result?.tool) tools.add(result.tool)
    }
  }
  return [...tools]
}

function hasDone(frames) {
  return frames.some((frame) => frame.type === 'done')
}

async function authenticate() {
  const configuredEmail = process.env.STRATEGY_CHAT_EMAIL || process.env.LIVE_AI_EMAIL || ''
  const configuredPassword = process.env.STRATEGY_CHAT_PASSWORD || process.env.LIVE_AI_PASSWORD || ''
  if (configuredEmail && configuredPassword) {
    const login = await requestJson('/api/auth/login', {
      method: 'POST',
      payload: { email: configuredEmail, password: configuredPassword },
    })
    assertContract('login_configured_user', login.response.status === 200 && login.body.access_token, `HTTP ${login.response.status}`)
    return { token: login.body.access_token, tempUserEmail: null }
  }

  const id = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}`
  const email = `strategy-live-${id}@example.com`
  const password = `Strategy-${crypto.randomBytes(12).toString('hex')}!`
  const registered = await requestJson('/api/auth/register', {
    method: 'POST',
    payload: { email, password, name: 'Strategy Chat Live Gate' },
  })
  assertContract('register_temp_user', [200, 201].includes(registered.response.status), `HTTP ${registered.response.status}`)
  const login = await requestJson('/api/auth/login', {
    method: 'POST',
    payload: { email, password },
  })
  assertContract('login_temp_user', login.response.status === 200 && login.body.access_token, `HTTP ${login.response.status}`)
  return { token: login.body.access_token, tempUserEmail: email }
}

async function cleanup(token) {
  const conversations = await requestJson('/api/conversations', { token }).catch(() => null)
  for (const conversation of conversations?.body || []) {
    if (conversation?.id) {
      await requestJson(`/api/conversations/${conversation.id}`, { method: 'DELETE', token }).catch(() => null)
    }
  }
}

const results = []
let token = ''
let tempUserEmail = null

try {
  const auth = await authenticate()
  token = auth.token
  tempUserEmail = auth.tempUserEmail

  const taskA = `请制定提高这个酶比活力的分析策略，序列：${sequenceA}`
  const planFramesA = await streamChat(token, {
    message: taskA,
    history: [],
    agent_control: 'plan_only',
    analysis_depth: 'fast',
  })
  const planStateA = latestPlanState(planFramesA)
  const planTextA = joinedText(planFramesA)
  const convA = conversationId(planFramesA)

  assertContract('initial_strategy_checkpoint', hasDone(planFramesA), 'initial plan stream did not finish')
  assertContract('initial_strategy_checkpoint', Number.isInteger(convA), 'conversation_id missing from done frame')
  assertContract('initial_strategy_checkpoint', planStateA?.waiting_for === 'plan_confirmation', 'plan did not stop at confirmation checkpoint')
  assertContract('initial_strategy_checkpoint', Array.isArray(planStateA.plan) && planStateA.plan.length > 0, 'plan payload missing')
  assertContract('initial_strategy_checkpoint', typeof planStateA.strategy_signature === 'string' && planStateA.strategy_signature.length > 8, 'strategy signature missing')
  assertContract('initial_strategy_checkpoint', typeof planStateA.task_fingerprint === 'string' && planStateA.task_fingerprint.length > 8, 'task fingerprint missing')
  assertContract('initial_strategy_checkpoint', /状态：等待确认，未执行工具/.test(planTextA), 'confirmation boundary text missing')
  results.push({ id: 'initial_strategy_checkpoint', status: 'passed', tools_seen: toolsSeen(planFramesA) })

  const executeFrames = await streamChat(token, {
    message: `${taskA}\n\n[用户确认] 请按上面的分析策略执行工具。`,
    conversation_id: convA,
    history: [
      { role: 'user', content: taskA },
      { role: 'assistant', content: planTextA },
    ],
    agent_control: 'execute_confirmed',
    analysis_depth: 'fast',
    confirmed_plan: planStateA.plan,
    strategy_signature: planStateA.strategy_signature,
    task_fingerprint: planStateA.task_fingerprint,
  })
  const executePlanState = latestPlanState(executeFrames)
  const executeText = joinedText(executeFrames)
  assertContract('confirmed_execution_no_replan', hasDone(executeFrames), 'execute stream did not finish')
  assertContract('confirmed_execution_no_replan', states(executeFrames).some((frame) => frame.stage === 'execute'), 'execute stage was not observed')
  assertContract(
    'confirmed_execution_no_replan',
    canonicalPlan(executePlanState?.plan) === canonicalPlan(planStateA.plan),
    'executed plan did not match the confirmed plan payload'
  )
  assertContract(
    'confirmed_execution_no_replan',
    !/状态：等待确认，未执行工具/.test(executeText),
    'confirmed execution returned a new confirmation prompt'
  )
  const activeAfterExecute = await requestJson(
    `/api/chat/strategy-checkpoints/active?conversation_id=${encodeURIComponent(String(convA))}`,
    { token }
  )
  assertContract('confirmed_execution_no_replan', activeAfterExecute.response.status === 200, `active checkpoint HTTP ${activeAfterExecute.response.status}`)
  assertContract('confirmed_execution_no_replan', activeAfterExecute.body.checkpoint === null, 'confirmed checkpoint stayed active after execution')
  const historyAfterExecute = await requestJson(
    `/api/chat/strategy-checkpoints/history?conversation_id=${encodeURIComponent(String(convA))}`,
    { token }
  )
  const executedRecord = (historyAfterExecute.body.records || []).find(
    (record) => record.strategy_signature === planStateA.strategy_signature
  )
  assertContract('confirmed_execution_no_replan', executedRecord, 'confirmed checkpoint missing from history')
  assertContract(
    'confirmed_execution_no_replan',
    executedRecord.status !== 'awaiting_confirmation',
    `confirmed checkpoint still awaiting in history: ${executedRecord.status}`
  )
  results.push({ id: 'confirmed_execution_no_replan', status: 'passed', tools_seen: toolsSeen(executeFrames) })

  const followupMessage = '继续解释上面为什么推荐P1位点，基于已给出的结果回答'
  const followupFrames = await streamChat(token, {
    message: followupMessage,
    conversation_id: convA,
    history: [
      { role: 'user', content: taskA },
      { role: 'assistant', content: planTextA },
      { role: 'user', content: '确认执行上述分析策略' },
      { role: 'assistant', content: executeText || '上一轮已执行并给出候选位点。' },
    ],
    agent_control: 'plan_only',
    analysis_depth: 'fast',
  })
  const followupStateWithPlan = latestPlanState(followupFrames)
  assertContract('same_problem_followup_no_rerun', hasDone(followupFrames), 'follow-up stream did not finish')
  assertContract('same_problem_followup_no_rerun', !followupStateWithPlan, 'follow-up generated a new tool plan')
  assertContract(
    'same_problem_followup_no_rerun',
    states(followupFrames).some((frame) => frame.research_notes === 'same_problem_synthesis_followup'),
    'follow-up was not classified as same-problem synthesis'
  )
  results.push({ id: 'same_problem_followup_no_rerun', status: 'passed', tools_seen: toolsSeen(followupFrames) })

  const taskB = `另一个新序列，提高这个酶的比活力，序列：${sequenceB}`
  const planFramesB = await streamChat(token, {
    message: taskB,
    conversation_id: convA,
    history: [
      { role: 'user', content: taskA },
      { role: 'assistant', content: executeText || planTextA },
    ],
    agent_control: 'plan_only',
    analysis_depth: 'fast',
  })
  const planStateB = latestPlanState(planFramesB)
  const planTextB = joinedText(planFramesB)
  assertContract('new_sequence_new_strategy', hasDone(planFramesB), 'new-sequence stream did not finish')
  assertContract('new_sequence_new_strategy', planStateB?.waiting_for === 'plan_confirmation', 'new sequence did not create a strategy checkpoint')
  assertContract(
    'new_sequence_new_strategy',
    planStateB.task_fingerprint && planStateB.task_fingerprint !== planStateA.task_fingerprint,
    'new sequence reused the prior task fingerprint'
  )
  results.push({ id: 'new_sequence_new_strategy', status: 'passed', tools_seen: toolsSeen(planFramesB) })

  const typedConfirmFrames = await streamChat(token, {
    message: '是，执行',
    conversation_id: convA,
    history: [
      { role: 'user', content: taskB },
      { role: 'assistant', content: planTextB },
    ],
    agent_control: 'plan_only',
    analysis_depth: 'fast',
  })
  const typedConfirmText = joinedText(typedConfirmFrames)
  assertContract('typed_confirmation_fail_closed', hasDone(typedConfirmFrames), 'typed confirmation stream did not finish')
  assertContract('typed_confirmation_fail_closed', /策略检查点校验失败/.test(typedConfirmText), 'missing checkpoint failure text was not returned')
  assertContract('typed_confirmation_fail_closed', /不会执行工具/.test(typedConfirmText), 'fail-closed safety boundary text missing')
  assertContract('typed_confirmation_fail_closed', !latestPlanState(typedConfirmFrames), 'typed confirmation created a new plan')
  results.push({ id: 'typed_confirmation_fail_closed', status: 'passed', tools_seen: toolsSeen(typedConfirmFrames) })

  console.log(JSON.stringify({
    summary: {
      status: 'passed',
      total: results.length,
      failed: 0,
      secrets_printed: false,
    },
    baseUrl,
    tempUserEmail,
    checks: results,
  }, null, 2))
} catch (error) {
  const failed = error instanceof ContractError
    ? { id: error.check, status: 'failed', detail: error.detail }
    : { id: 'strategy_chat_live', status: 'failed', detail: error instanceof Error ? error.message : String(error) }
  console.log(JSON.stringify({
    summary: {
      status: 'failed',
      total: results.length + 1,
      failed: 1,
      secrets_printed: false,
    },
    baseUrl,
    tempUserEmail,
    checks: [...results, failed],
  }, null, 2))
  process.exitCode = 1
} finally {
  if (token) await cleanup(token)
}

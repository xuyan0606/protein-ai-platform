import { chromium } from 'playwright'
import crypto from 'node:crypto'

const baseUrl = 'http://120.27.108.138'
const email = `ui-checkpoint-${Date.now()}-${crypto.randomBytes(3).toString('hex')}@example.com`
const password = `Tmp!${crypto.randomBytes(12).toString('hex')}`

async function request(path, payload, token) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: payload ? 'POST' : 'GET',
    headers: {
      Accept: 'application/json',
      ...(payload ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  })
  const text = await response.text()
  return { status: response.status, body: text ? JSON.parse(text) : {} }
}

const auth = await request('/api/auth/register', { email, password, name: 'UI Checkpoint' })
const token = auth.body.access_token
if (!token) throw new Error(`register failed ${auth.status}`)
const conv = await request('/api/conversations', { title: 'UI checkpoint stale state' }, token)
const convId = String(conv.body.id)

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()
try {
  await page.addInitScript(({ token, convId }) => {
    localStorage.setItem('token', token)
    localStorage.setItem('currentConversationId', convId)
  }, { token, convId })
  await page.goto(`${baseUrl}/chat/agent`, { waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForTimeout(1000)
  await page.evaluate(() => {
    const root = document.querySelector('#root')
    if (!root) throw new Error('root missing')
  })

  // Inject stale local Zustand agent state by reaching the store through React is not reliable in production.
  // Instead create a real plan, execute it to consume the active checkpoint, then reload the conversation.
  const textarea = page.locator('textarea').first()
  await textarea.fill('提高这个酶的比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY')
  await textarea.press('Enter')
  await page.getByText('确认执行', { exact: false }).waitFor({ timeout: 90000 }).catch(async (err) => {
    await page.screenshot({ path: 'output/playwright/checkpoint-ui-timeout.png', fullPage: true })
    console.log(JSON.stringify({ failed_waiting_confirm: true, body: (await page.locator('body').innerText()).slice(0, 2000) }, null, 2))
    throw err
  })
  const confirmButton = page.locator('button').filter({ hasText: '确认执行' }).first()
  await confirmButton.waitFor({ state: 'visible', timeout: 90000 })
  const confirmVisibleBefore = await confirmButton.isVisible()
  await confirmButton.click()
  await page.waitForTimeout(3000)
  await page.reload({ waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForTimeout(2500)
  const confirmButtonsAfter = await page.getByRole('button', { name: /确认执行/ }).count()
  const bodyText = await page.locator('body').innerText()
  const active = await request(`/api/chat/strategy-checkpoints/active?conversation_id=${convId}`, null, token)

  console.log(JSON.stringify({
    email_printed: false,
    conversation_id: convId,
    confirm_visible_before_execute: confirmVisibleBefore,
    active_after_execute: active.body.agent_state,
    confirm_button_count_after_reload: confirmButtonsAfter,
    no_confirm_button_after_consumed: confirmButtonsAfter === 0,
    no_signature_mismatch_visible: !bodyText.includes('strategy_signature does not match confirmed_plan'),
    passed: confirmVisibleBefore && active.body.agent_state === null && confirmButtonsAfter === 0 && !bodyText.includes('strategy_signature does not match confirmed_plan'),
  }, null, 2))
} finally {
  await browser.close()
  await fetch(`${baseUrl}/api/conversations/${convId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }).catch(() => {})
}

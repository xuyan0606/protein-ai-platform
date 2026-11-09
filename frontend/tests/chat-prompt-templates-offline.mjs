import fs from 'node:fs'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const base = process.env.CHAT_TEMPLATE_TEST_BASE || 'http://127.0.0.1:4210'
const out = process.env.CHAT_TEMPLATE_TEST_OUT || '/private/tmp/platform-chat-template-test'
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const result = { checks: [], errors: [], streams: [], uploads: 0, browser_path: 'Browser plugin returned No browser is available; existing project Playwright harness used' }
const check = (name, condition) => { assert.ok(condition, name); result.checks.push(name); console.log(`PASS ${name}`) }
page.on('pageerror', error => result.errors.push(error.message))
page.on('console', message => { if (message.type() === 'error') result.errors.push(message.text()) })
let releaseStream
let notifyStreamStarted
const streamStarted = new Promise(resolve => { notifyStreamStarted = resolve })
await page.route('**/api/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  const json = value => route.fulfill({ json: value })
  if (path === '/api/chat/models') return json([{ id: 'gpt6-sol', name: 'GPT-6-sol', available: true }])
  if (path === '/api/conversations') return json([])
  if (path.includes('/strategy-checkpoints/')) return json({ records: [], checkpoint: null, agent_state: null })
  if (path === '/api/tools') return json({ tools: [], categories: {} })
  if (path === '/api/files/upload') {
    result.uploads += 1
    return json({ id: 'uploads/user_7/notes.txt', object_name: 'uploads/user_7/notes.txt', download_url: '/api/files/uploads/user_7/notes.txt/download' })
  }
  if (path === '/api/chat/stream') {
    result.streams.push(request.postDataJSON())
    await new Promise(resolve => { releaseStream = resolve; notifyStreamStarted() })
    return route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"text","content":"已收到测试模板。"}\n\ndata: {"type":"done"}\n\n' })
  }
  return json({})
})

try {
  await page.goto(`${base}/chat/agent`)
  const templates = page.getByRole('region', { name: '提问模板' })
  await templates.getByRole('button', { name: '提高热稳定性', exact: true }).waitFor({ timeout: 10000 })
  const input = page.locator('textarea').last()
  const names = ['提高热稳定性', '提高比活力', '耐酸耐碱', '调整底物选择性', '分析已有突变', '解读序列或结构']
  check('six_templates_above_chat_input', (await templates.boundingBox()).y < (await input.boundingBox()).y && await templates.getByRole('button').count() >= 6)
  for (const name of names) assert.equal(await templates.getByRole('button', { name, exact: true }).count(), 1)
  await templates.getByRole('button', { name: names[0], exact: true }).click()
  let text = await input.inputValue()
  check('thermal_template_has_editable_assay_fields', text.includes('热处理条件') && text.includes('分钟') && text.includes('残余酶活') && text.includes('【') && text.includes('测定方法'))
  check('template_click_does_not_send_or_upload', result.streams.length === 0 && result.uploads === 0)
  await page.waitForFunction(() => document.activeElement instanceof HTMLTextAreaElement)
  check('template_focuses_input', await input.evaluate(el => document.activeElement === el))

  await input.fill('保留我的草稿')
  await page.locator('input[type=file]').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('owned fixture') })
  await templates.getByRole('button', { name: names[1], exact: true }).click()
  await page.getByRole('button', { name: '保留原文', exact: true }).waitFor()
  check('existing_draft_not_overwritten', await input.inputValue() === '保留我的草稿')
  await page.getByRole('button', { name: '保留原文', exact: true }).click()
  check('cancel_template_keeps_draft_and_attachment', await input.inputValue() === '保留我的草稿' && await page.getByText('notes.txt', { exact: true }).count() === 1)
  await templates.getByRole('button', { name: names[1], exact: true }).click()
  await page.getByRole('button', { name: '替换输入', exact: true }).click()
  check('confirmed_template_replaces_only_text', (await input.inputValue()).includes('比活力') && await page.getByText('notes.txt', { exact: true }).count() === 1)

  for (const name of names.slice(2)) {
    await input.fill('')
    await templates.getByRole('button', { name, exact: true }).click()
    check(`usable_template_${name}`, (await input.inputValue()).includes('【') && (await input.inputValue()).length > 100)
  }
  await input.fill('')
  await templates.getByRole('button', { name: names[0], exact: true }).click()
  text = (await input.inputValue()).replaceAll(/【[^】]+】/g, '未知')
  await input.fill(text)
  await input.press('Enter')
  await streamStarted
  check('manual_send_preserves_template_and_attachment', result.streams.length === 1 && result.streams[0].message.includes('热稳定性') && result.streams[0].message.includes('notes.txt') && result.streams[0].agent_control === 'plan_only')
  check('templates_disabled_during_stream', await templates.getByRole('button', { name: names[0], exact: true }).isDisabled())
  releaseStream()
  await page.getByText('已收到测试模板。', { exact: true }).waitFor()
  await templates.getByRole('button', { name: names[0], exact: true }).and(page.locator(':enabled')).waitFor()
  check('templates_available_after_messages', await templates.isVisible())

  await page.setViewportSize({ width: 390, height: 844 })
  // The existing desktop sidebar becomes a modal on mobile; dismiss it normally.
  const sidebarBackdrop = page.locator('div.fixed.inset-0.bg-black\\/50')
  if (await sidebarBackdrop.isVisible()) {
    await sidebarBackdrop.click({ position: { x: 380, y: 420 } })
    await sidebarBackdrop.waitFor({ state: 'hidden' })
  }
  await input.fill('')
  await templates.getByRole('button', { name: names[0], exact: true }).click()
  const metrics = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }))
  check('mobile_no_horizontal_overflow', metrics.viewport === 390 && metrics.document === 390)
  check('mobile_input_visible', (await input.boundingBox()).height > 0 && (await input.boundingBox()).y < 844)
  await templates.getByRole('button', { name: '收起模板', exact: true }).click()
  check('template_panel_collapses', !await templates.getByRole('button', { name: names[0], exact: true }).isVisible())
  await templates.getByRole('button', { name: '展开模板', exact: true }).click()
  check('template_panel_reopens', await templates.getByRole('button', { name: names[0], exact: true }).isVisible())
  check('no_browser_errors', result.errors.length === 0)
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = String(error); throw error
} finally {
  fs.mkdirSync(out, { recursive: true })
  fs.writeFileSync(`${out}/result.json`, JSON.stringify(result, null, 2))
  await browser.close()
}

import fs from 'node:fs'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const out = '/private/tmp/platform-blast-polling'
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const result = { checks: [], errors: [], polls: 0, resumes: 0, submissions: 0 }
const check = (name, condition) => { assert.ok(condition, name); result.checks.push(name); console.log(`PASS ${name}`) }
page.on('pageerror', error => result.errors.push(error.message))
let releaseHeldRequest
let phase = 'hung'
await page.route('**/api/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  if (path === '/api/chat/models') return route.fulfill({ json: [{ id:'gpt6-sol',name:'GPT-6-sol',available:true }] })
  if (path === '/api/conversations') return route.fulfill({ json: [] })
  if (path.includes('strategy-checkpoints')) return route.fulfill({ json: { checkpoint:null,agent_state:null,records:[] } })
  if (path === '/api/chat/stream') return route.fulfill({ contentType: 'text/event-stream', body: [
    {type:'state',stage:'done',plan:[{id:1,tool_name:'blast_search',description:'后台同源搜索',params:{},status:'submitted'}],current_step:1,step_results:[{step:1,tool:'blast_search',status:'submitted',raw_result:JSON.stringify({task_id:'poll-fixture',status:'submitted',status_url:'/api/tools/tasks/poll-fixture'})}]},
    {type:'text',content:'同源搜索已提交，身份尚未确认。'}, {type:'done'},
  ].map(event => `data: ${JSON.stringify(event)}\n\n`).join('') })
  if (path === '/api/tools/tasks/poll-fixture/resume') {
    result.resumes += 1; phase='completed'
    return route.fulfill({ json: {status:'waiting'} })
  }
  if (path === '/api/tools/tasks/poll-fixture') {
    result.polls += 1
    if (phase === 'hung') {
      await new Promise(resolve => { releaseHeldRequest = resolve })
      return route.fulfill({ json: {task_id:'poll-fixture',status:'waiting',rid:'SAME-RID',message:'过期请求不应覆盖新状态'} }).catch(() => {})
    }
    return route.fulfill({ json: {task_id:'poll-fixture',status:phase,rid:'SAME-RID',
      message: phase==='degraded' ? '已达到本轮后台等待上限；可继续查询原任务。此状态不表示无同源命中。' : '同源搜索已完成',
      can_resume:phase==='degraded',result:phase==='completed'?{status:'completed',results_count:0,results:[],database:'swissprot',query_length:486,evidence_status:'completed_no_hit'}:null} })
  }
  if (request.method()==='POST' && path.includes('/submit')) result.submissions += 1
  return route.fulfill({ json: {} })
})
try {
  await page.goto('http://127.0.0.1:4210/chat/agent')
  await page.locator('textarea').last().fill('分析该酶的同源搜索状态')
  await page.locator('textarea').last().press('Enter')
  const retry = page.getByRole('button', {name:'重新查询状态',exact:true})
  await retry.waitFor({ timeout:25000 })
  check('hung_status_request_becomes_retryable', result.polls===1 && await retry.isVisible())
  phase='degraded'
  await retry.click()
  const resume = page.getByRole('button', {name:'继续查询原任务',exact:true})
  await resume.waitFor()
  check('timeout_is_not_no_hit_and_saved_rid_visible', (await page.locator('body').innerText()).includes('SAME-RID') && (await page.locator('body').innerText()).includes('不表示无同源命中'))
  releaseHeldRequest?.()
  await resume.click()
  await page.getByRole('status').filter({hasText:'同源搜索已完成'}).first().waitFor()
  check('resume_reuses_original_task_without_resubmission', result.resumes===1 && result.submissions===0 && result.polls>=3)
  check('no_page_errors', result.errors.length===0)
  result.status='passed'
} catch (error) {
  result.status='failed'; result.error=String(error); throw error
} finally {
  releaseHeldRequest?.()
  fs.mkdirSync(out,{recursive:true});fs.writeFileSync(`${out}/result.json`,JSON.stringify(result,null,2))
  await browser.close()
}

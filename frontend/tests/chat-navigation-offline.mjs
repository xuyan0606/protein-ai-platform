import assert from 'node:assert/strict'
import fs from 'node:fs'
import { chromium } from 'playwright'
const base=process.env.CHAT_NAV_BASE || 'http://127.0.0.1:4211'
const out=new URL('../../output/remaining-fixes-20261106/',import.meta.url)
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'})
const page=await browser.newPage({viewport:{width:1440,height:1000}})
page.setDefaultTimeout(10000)
const result={checks:[],streams:[],errors:[],created:0}, held=new Map(), counts=new Map()
let delayed=new Set(),fail=new Set(), delayCheckpoint=false, delayList=false
const check=(name,value)=>{assert.ok(value,name);result.checks.push(name);console.log('PASS '+name)}
const until=async predicate=>{const end=Date.now()+10000;while(!predicate()){assert.ok(Date.now()<end,'network barrier timeout');await new Promise(r=>setTimeout(r,10))}}
page.on('pageerror',e=>result.errors.push(e.message))
await page.route('**/api/**',async route=>{
 const req=route.request(),url=new URL(req.url()),p=url.pathname
 const json=value=>route.fulfill({json:value})
 if(p==='/api/chat/models')return json([{id:'gpt6-sol',name:'GPT-6-sol',available:true}])
 if(p==='/api/conversations'){
  if(req.method()==='POST'){result.created++;return json({id:'unexpected-new'})}
  if(delayList)await new Promise(r=>held.set('list',r))
  return json(['A','B','C'].map(id=>({id,title:'项目'+id,created_at:'2026-11-06T00:00:00Z',message_count:1})))
 }
 if(/^\/api\/conversations\/[ABC]$/.test(p)){
  const id=p.split('/').pop();counts.set(id,(counts.get(id)||0)+1)
  if(delayed.has(id))await new Promise(r=>held.set(id,r))
  if(fail.has(id))return route.fulfill({status:500,json:{detail:'controlled test failure'}})
  return json({id,title:'项目'+id,messages:[{id:id+'1',role:'user',content:'原始项目'+id+'上下文'}]})
 }
 if(p.includes('/strategy-checkpoints/')){
  if(delayCheckpoint && p.endsWith('/active'))await new Promise(r=>held.set('checkpoint',r))
  return json({agent_state:null,records:[]})
 }
 if(p==='/api/chat/stream'){
  const body=req.postDataJSON();result.streams.push(body)
  return route.fulfill({contentType:'text/event-stream',body:'data: '+JSON.stringify({type:'text',content:'已接续项目'+body.conversation_id})+'\n\ndata: '+JSON.stringify({type:'done',conversation_id:body.conversation_id})+'\n\n'})
 }
 if(p==='/api/tools')return json({tools:[],categories:{}})
 return json({})
})
const select=id=>page.getByText('项目'+id,{exact:true}).filter({visible:true}).click()
try{
 await page.goto(base+'/chat/agent')
 const input=page.locator('textarea').last()
 await page.getByText('项目A',{exact:true}).filter({visible:true}).waitFor()
 await input.fill('补充温度90度，继续原项目')
 delayed.add('A');await select('A');await until(()=>held.has('A'))
 await page.getByRole('status').filter({hasText:'正在加载所选会话'}).waitFor()
 await input.press('Enter')
 check('fast_send_while_loading_does_not_create_or_stream',result.created===0&&result.streams.length===0)
 check('draft_kept_while_loading',await input.inputValue()==='补充温度90度，继续原项目')
 delayed.delete('A');held.get('A')();held.delete('A')
 await page.getByText('原始项目A上下文',{exact:true}).waitFor()
 await page.getByRole('status').filter({hasText:'正在加载所选会话'}).waitFor({state:'hidden'})
 await input.press('Enter');await page.getByText('已接续项目A',{exact:true}).waitFor()
 check('send_uses_selected_conversation_and_prior_history',result.streams[0].conversation_id==='A'&&result.streams[0].history.some(m=>m.content==='原始项目A上下文'))
 await page.waitForFunction(async()=>{const {useChatStore}=await import('/src/stores/chat.ts');return !useChatStore.getState().streaming})
 delayed.add('A');await select('A');await until(()=>held.has('A'))
 await select('B');await page.getByText('原始项目B上下文',{exact:true}).waitFor()
 delayed.delete('A');held.get('A')();held.delete('A')
 // Wait for the intercepted A response to be consumed by the real store.
 await page.waitForFunction(async()=>{const {useChatStore}=await import('/src/stores/chat.ts');return !useChatStore.getState().conversationLoading})
 await page.evaluate(async()=>{await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))})
 check('out_of_order_response_does_not_replace_project_B',await page.getByText('原始项目B上下文',{exact:true}).count()===1&&await page.getByText('原始项目A上下文',{exact:true}).count()===0)
 await input.fill('补充pH4.5');await input.press('Enter');await page.getByText('已接续项目B',{exact:true}).waitFor()
 check('subsequent_supplement_sent_to_project_B',result.streams.at(-1).conversation_id==='B')
 await page.waitForFunction(async()=>{const {useChatStore}=await import('/src/stores/chat.ts');return !useChatStore.getState().streaming})
 fail.add('C');await input.fill('不能丢失的草稿');await select('C')
 await page.getByRole('alert').filter({hasText:'会话加载失败'}).waitFor();const n=result.streams.length
 await input.press('Enter')
 check('failed_load_blocks_send_and_keeps_draft',result.streams.length===n&&await input.inputValue()==='不能丢失的草稿')
 fail.delete('C');delayCheckpoint=true;await select('C');await until(()=>held.has('checkpoint'))
 await page.getByText('原始项目C上下文',{exact:true}).waitFor();await input.press('Enter')
 check('checkpoint_restoration_blocks_send',result.streams.length===n)
 delayCheckpoint=false;held.get('checkpoint')();held.delete('checkpoint')
 await page.getByRole('status').filter({hasText:'正在加载所选会话'}).waitFor({state:'hidden'})
 await input.press('Enter');await page.getByText('已接续项目C',{exact:true}).waitFor()
 check('retry_restores_original_project',result.streams.at(-1).conversation_id==='C'&&result.created===0)
 await page.waitForFunction(async()=>{const {useChatStore}=await import('/src/stores/chat.ts');return !useChatStore.getState().streaming})
 delayList=true;delayed.add('C');await page.reload();await until(()=>held.has('list'))
 await input.fill('刷新后快速补充，不能新开项目');const beforeReloadSend=result.streams.length
 await input.press('Enter')
 check('refresh_pending_list_blocks_send_and_keeps_draft',result.streams.length===beforeReloadSend&&result.created===0&&await input.inputValue()==='刷新后快速补充，不能新开项目')
 delayList=false;held.get('list')();held.delete('list');await until(()=>held.has('C'))
 delayed.delete('C');held.get('C')();held.delete('C')
 await page.getByText('原始项目C上下文',{exact:true}).waitFor()
 await page.getByRole('status').filter({hasText:'正在加载所选会话'}).waitFor({state:'hidden'})
 await input.press('Enter');await page.getByText('已接续项目C',{exact:true}).waitFor()
 check('refresh_fast_supplement_uses_restored_conversation',result.streams.at(-1).conversation_id==='C'&&result.created===0)
 check('reload_restores_last_selected_project',await page.getByText('原始项目C上下文',{exact:true}).isVisible())
 check('no_page_errors',result.errors.length===0)
 await page.screenshot({path:new URL('navigation-browser.png',out).pathname,fullPage:true})
 result.status='passed'
}catch(e){result.status='failed';result.error=String(e);throw e}
finally{fs.mkdirSync(out,{recursive:true});fs.writeFileSync(new URL('navigation-browser.json',out),JSON.stringify(result,null,2));await browser.close()}

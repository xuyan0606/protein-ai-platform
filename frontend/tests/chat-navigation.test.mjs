import assert from 'node:assert/strict'
import { test } from 'node:test'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'
const require=createRequire(import.meta.url)
function fixture(overrides = {}) {
  const pending=new Map(), storage=new Map()
  const api={getConversation:id=>new Promise((resolve,reject)=>pending.set(id,{resolve,reject})),
    getActiveStrategyCheckpoint:async()=>({agent_state:null}),getStrategyCheckpointHistory:async()=>({records:[]}),
    getRecentStrategyMemory:async()=>({records:[]}), ...overrides}
  const auth={getState:()=>({user:{id:7},logout:()=>{}})}
  const module={exports:{}}
  class ApiError extends Error {}
  const js=ts.transpileModule(fs.readFileSync(new URL('../src/stores/chat.ts',import.meta.url),'utf8'),
    {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  vm.runInNewContext(js,{module,exports:module.exports,console,Date,Set,Map,
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    require:name=>name==='@/lib/api'?{api,ApiError,isUnauthorizedError:()=>false,normalizeFileDownloadUrl:x=>x}:
      name==='@/stores/auth'?{useAuthStore:auth}:name==='@/stores/ui'?{useUIStore:{getState:()=>({setConversationsLoading:()=>{}})}}:require(name)})
  const store=module.exports.useChatStore
  store.setState({ownerUserId:'7',currentId:'old',messages:[{role:'user',content:'old project'}]})
  const resolve=(id,content=id)=>pending.get(id).resolve({id,title:id,messages:[{role:'user',content}]})
  return {store,pending,resolve,storage}
}
test('selecting a slow conversation binds its ID immediately and blocks sending until loaded',async()=>{
  const {store,resolve}=fixture();const loading=store.getState().setCurrentId('chosen')
  assert.equal(store.getState().currentId,'chosen')
  assert.equal(store.getState().conversationLoading,true)
  resolve('chosen');await loading
  assert.equal(store.getState().conversationLoading,false)
  assert.equal(store.getState().messages[0].content,'chosen')
})
test('a late earlier conversation response never replaces the newer selection',async()=>{
  const {store,resolve}=fixture();const first=store.getState().setCurrentId('A');const last=store.getState().setCurrentId('B')
  resolve('B');await last;resolve('A');await first
  assert.equal(store.getState().currentId,'B');assert.equal(store.getState().messages[0].content,'B')
})
test('logout invalidates pending conversation loads',async()=>{
  const {store,resolve}=fixture();const loading=store.getState().setCurrentId('private')
  store.getState().resetUserScopedState(null);resolve('private','private content');await loading
  assert.equal(store.getState().currentId,null);assert.equal(store.getState().messages.length,0)
})
test('failed loading keeps the selected conversation blocked instead of creating a blank task',async()=>{
  const {store,pending}=fixture();const loading=store.getState().setCurrentId('failed')
  pending.get('failed').reject(new Error('network unavailable'));await loading
  assert.equal(store.getState().currentId,'failed')
  assert.equal(store.getState().conversationLoading,false)
  assert.ok(store.getState().conversationLoadError)
})

test('checkpoint loading continues to block sends after messages arrive',async()=>{
  let release, started
  const checkpointStarted=new Promise(r=>{started=r})
  const {store,resolve}=fixture({getActiveStrategyCheckpoint:()=>new Promise(r=>{release=r;started()})})
  const loading=store.getState().setCurrentId('checkpoint');resolve('checkpoint')
  await checkpointStarted;assert.equal(store.getState().conversationLoading,true)
  release({agent_state:null});await loading;assert.equal(store.getState().conversationLoading,false)
})
test('new conversation cancels an earlier history response',async()=>{
  const {store,resolve}=fixture();const loading=store.getState().setCurrentId('A')
  store.getState().newConversation();const selected=store.getState().currentId
  resolve('A');await loading;assert.equal(store.getState().currentId,selected)
  assert.equal(store.getState().messages.length,0)
})
test('session restoration cannot override a selection made while listing conversations',async()=>{
  let list
  const {store,resolve,storage}=fixture({getConversations:()=>new Promise(r=>{list=r})})
  storage.set('currentConversationId','saved')
  const restoring=store.getState().restoreSession()
  const selection=store.getState().setCurrentId('selected');resolve('selected');await selection
  resolve('saved');list([{id:'saved'},{id:'selected'}]);await restoring
  assert.equal(store.getState().currentId,'selected')
})
test('late conversation lists cannot restore data after user-scoped reset',async()=>{
  let list
  const {store}=fixture({getConversations:()=>new Promise(r=>{list=r})})
  const loading=store.getState().syncConversations();store.getState().resetUserScopedState(null)
  list([{id:'private',title:'private title'}]);await loading
  assert.equal(store.getState().ownerUserId,null);assert.equal(store.getState().conversations.length,0)
})
test('late new-conversation response cannot override another selection',async()=>{
  let create
  const {store,resolve}=fixture({createConversation:()=>new Promise(r=>{create=r})})
  const creating=store.getState().syncNewConversation()
  const selection=store.getState().setCurrentId('selected');resolve('selected');await selection
  create({id:'new'});await creating;assert.equal(store.getState().currentId,'selected')
})
test('deleting a selected conversation invalidates its pending load and unlocks input',async()=>{
  const {store,resolve}=fixture();const loading=store.getState().setCurrentId('deleted')
  store.getState().deleteConversation('deleted');resolve('deleted');await loading
  assert.equal(store.getState().currentId,null);assert.equal(store.getState().conversationLoading,false)
})
test('a new user session can list conversations while the old request is still pending',async()=>{
  const lists=[]
  const {store}=fixture({getConversations:()=>new Promise(r=>lists.push(r))})
  const first=store.getState().syncConversations();store.getState().resetUserScopedState('7')
  const second=store.getState().syncConversations()
  assert.equal(lists.length,2)
  lists[1]([{id:'fresh'}]);await second;lists[0]([{id:'stale'}]);await first
  assert.equal(store.getState().conversations[0].id,'fresh')
})
test('refresh binds saved conversation and blocks sending before the conversation list returns',async()=>{
  let list
  const {store,resolve,storage}=fixture({getConversations:()=>new Promise(r=>{list=r})})
  store.setState({currentId:null,messages:[]})
  storage.set('currentConversationId','saved')
  const restoring=store.getState().restoreSession()
  assert.equal(store.getState().currentId,'saved')
  assert.equal(store.getState().conversationLoading,true)
  resolve('saved','original project after refresh')
  list([{id:'saved'}]);await restoring
  assert.equal(store.getState().messages[0].content,'original project after refresh')
  assert.equal(store.getState().conversationLoading,false)
})

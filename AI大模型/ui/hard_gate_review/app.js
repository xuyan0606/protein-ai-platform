const state = { kind: "strict", packets: { strict: [], substrate: [] }, selected: null, forms: {}, status: {}, busy: false };
const $ = (id) => document.getElementById(id);
const nowLocal = () => { const d = new Date(); const p = (n) => String(n).padStart(2,"0"); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };
const rules = {
  strict: ["确认是 Venus-15B 真实实验，不是设计突变或预测。", "序列和 PDB chain A 的 WT 残基必须一致。", "逐条检查数值、对照、条件和来源记录。", "确认没有训练集泄漏；拿不准就待补充。"],
  substrate: ["原文必须明确写出底物或工艺体系。", "确认是单一化合物、定义底物集合还是混合物。", "混合物不能凭空填写单分子 SMILES。", "确认工艺阶段、条件和 protocol 版本；证据不足就待补充。"],
};
const decisionOptions = {
  strict: [["approve_strict_holdout","通过 strict holdout"],["reject_candidate","拒绝候选"],["needs_more_info","待补充"]],
  substrate: [["approve_reviewed_substrate_identity","通过底物身份"],["reject_substrate_identity","拒绝底物身份"],["needs_more_info","待补充"]],
};
const checks = {
  strict: [["source_evidence_confirmed","真实实验来源已确认"],["numbering_confirmed","序列/PDB编号已确认"],["wetlab_result_confirmed","实验结果已确认"],["leakage_check_passed","无训练/测试泄漏"]],
  substrate: [["identity_confirmed","原文底物身份已确认"],["scope_confirmed","底物范围已确认"],["condition_confirmed","条件已确认"],["protocol_version_confirmed","protocol版本已确认"]],
};
const guideSteps = [
  ["build_hard_gate_review_packets", "刷新审核包"],
  ["validate_hard_gate_reviews", "验证人工审核"],
  ["build_hard_gate_bridge", "生成 benchmark bridge"],
  ["validate_hard_gate_bridge", "验证 bridge"],
  ["apply_benchmark_score_cache", "写入 score cache"],
  ["validate_benchmark_score_cache", "验证 benchmark"],
  ["safe_pipeline", "运行安全训练管线"],
];
async function api(path, payload) {
  const r = await fetch(path, payload ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)} : {});
  const text = await r.text();
  let d={};
  try { d=JSON.parse(text); } catch { d={raw:text}; }
  if(!r.ok || d.ok===false) {
    const detail = [d.error || d.raw || `${r.status}`, d.stdout, d.stderr].filter(Boolean).join("\n\n");
    throw new Error(detail);
  }
  return d;
}
async function load() {
  const d=await api("../../api/hard-gate/status");
  state.status=d;
  state.packets.strict=d.strict_packets||[];
  state.packets.substrate=d.substrate_packets||[];
  if(!state.selected || !state.packets[state.kind].some(x=>x.review_key===state.selected.review_key)) state.selected=state.packets[state.kind][0]||null;
  render();
}
function currentForm() { const key=state.selected?.review_key; if(!key) return { decision:decisionOptions[state.kind][2][0], checks:{}, reviewer:"", reviewed_at:nowLocal(), review_basis:"", receipt:"", representation_type:"" }; if(!state.forms[key]) { const old=state.selected.decision_row||{}; const oldChecks={}; (checks[state.kind]||[]).forEach(([field])=>{oldChecks[field]=old[field]===true;}); state.forms[key]={ decision:old.decision||decisionOptions[state.kind][2][0], checks:oldChecks, reviewer:old.reviewer||"", reviewed_at:old.reviewed_at||nowLocal(), review_basis:old.review_basis||"", receipt:old.acceptance_receipt||"", representation_type:old.representation_type||"" }; } return state.forms[key]; }
function renderQueue() { const rows=state.packets[state.kind]; $("queueCount").textContent=rows.length; $("queueList").innerHTML=rows.length?rows.map((r,i)=>`<button class="queue-row ${state.selected&&r.review_key===state.selected.review_key?"active":""}" data-key="${i}"><strong>${state.kind==="strict"?r.variant:r.substrate_name_source_text}</strong><small>${state.kind==="strict"?`${r.project_id} · ${r.canonical_position} · ${r.project_overall_judgement||"待核实"}`:`${r.substrate_identity_normalized} · ${r.source_format}`}</small></button>`).join(""):"<div class='empty'>没有审核包，请先运行安全管线。</div>"; document.querySelectorAll(".queue-row").forEach(b=>b.addEventListener("click",()=>{state.selected=rows[Number(b.dataset.key)];render();})); }
function evidenceValue(value) { if(value===null||value===undefined||value==="") return "未提供"; if(typeof value==="object") return JSON.stringify(value,null,2); return String(value); }
function renderEvidence() { const r=state.selected; if(!r){$("title").textContent="选择一条记录";$("evidence").innerHTML="";return;} $("title").textContent=state.kind==="strict"?`${r.variant} · Venus-15B`:`${r.substrate_name_source_text} · ${r.substrate_identity_normalized}`; const fields=state.kind==="strict"?[ ["项目",r.project_id],["WT / mutant",`${r.wild_type} → ${r.mutant}`],["canonical位置",r.canonical_position],["序列 / PDB",`${r.sequence_residue} / ${r.pdb_residue} · ${r.sequence_pdb_cross_check?.exact_match?"一致":"不一致"}`],["项目判断",r.project_overall_judgement],["测量条数",(r.measurement_evidence_rows||[]).length],["来源回执",r.source_receipts]] : [["规范化身份",r.substrate_identity_normalized],["原文名称",r.substrate_name_source_text],["SMILES",r.substrate_smiles||"未推断"],["SMILES状态",r.smiles_status],["来源",r.source_file],["来源SHA256",r.source_file_sha256],["工艺阶段",r.assay_context?.process_stage],["条件证据",r.protocol_numeric_evidence]]; $("evidence").innerHTML=`<div class="evidence-grid">${fields.map(([k,v])=>`<div class="evidence-item ${typeof v==="object"?"evidence-wide":""}"><b>${k}</b><span>${evidenceValue(v)}</span></div>`).join("")}<details class="evidence-wide"><summary>展开原文证据</summary><pre>${evidenceValue(state.kind==="strict"?r.measurement_evidence_rows:r.evidence_paragraphs)}</pre></details></div>`; }
function renderDecision() { const r=state.selected; const f=currentForm(); $("rules").innerHTML=rules[state.kind].map(x=>`<li>${x}</li>`).join(""); $("kindLabel").textContent=state.kind==="strict"?"突变 holdout":"底物身份"; const savedDecision=r?.decision_row?.decision; $("gateState").textContent=savedDecision?.includes("approve")?"已提交通过":savedDecision?.includes("reject")?"已拒绝":"blocked"; $("decisionButtons").innerHTML=decisionOptions[state.kind].map(([v,l])=>`<button data-decision="${v}" class="${f.decision===v?"active":""}">${l}</button>`).join(""); document.querySelectorAll("[data-decision]").forEach(b=>b.addEventListener("click",()=>{f.decision=b.dataset.decision;renderDecision();})); $("checks").innerHTML=checks[state.kind].map(([k,l])=>`<label><input type="checkbox" data-check="${k}" ${f.checks[k]||false?"checked":""}/> <span>${l}</span></label>`).join(""); document.querySelectorAll("[data-check]").forEach(b=>b.addEventListener("change",()=>{f.checks[b.dataset.check]=b.checked;})); $("reviewer").value=f.reviewer; $("reviewedAt").value=f.reviewed_at; $("reviewBasis").value=f.review_basis; $("receipt").value=f.receipt; $("receipt").placeholder=state.kind==="strict"?"实验记录号或审核回执":"protocol/审核回执号"; $("representationField").hidden=state.kind!=="substrate"; $("representationType").value=f.representation_type||"process_mixture"; $("saveBtn").disabled=!r; }
function renderStatus() {
  const d=state.status||{};
  const benchmark=d.benchmark_validation||{};
  const bridge=d.bridge||{};
  const pipeline=d.pipeline||{};
  $("statusText").textContent=`strict决策 ${d.strict_decision_rows||0} 条；底物决策 ${d.substrate_decision_rows||0} 条；benchmark ${benchmark.valid_rows||0}/${benchmark.benchmark_rows||0}`;
  const cards=[
    ["strict正式通过", d.strict_formal_approved_rows||0, bridge.strict?.status || "blocked"],
    ["底物正式通过", d.substrate_formal_approved_rows||0, bridge.substrate?.status || "blocked"],
    ["Benchmark", `${benchmark.valid_rows||0}/${benchmark.benchmark_rows||0}`, `heads_ready=${benchmark.heads_ready||0}`],
    ["安全管线", pipeline.success===true?"通过":"未通过/未运行", `steps=${pipeline.steps_run||0} failed=${pipeline.failed_steps||0}`],
  ];
  $("summaryCards").innerHTML=cards.map(([k,v,n])=>`<div><b>${k}</b><strong>${v}</strong><span>${n}</span></div>`).join("");
}
function renderGuide() {
  $("guideSteps").innerHTML=guideSteps.map(([step,label],i)=>`<button type="button" data-guide-step="${step}"><span>${i+1}</span>${label}</button>`).join("");
  document.querySelectorAll("[data-guide-step]").forEach(b=>b.addEventListener("click",()=>runGuideStep(b.dataset.guideStep)));
  $("runAllBtn").disabled=state.busy;
}
function render() { renderStatus(); renderQueue(); renderEvidence(); renderDecision(); renderGuide(); }
function buildDecision() { const f=currentForm(); f.reviewer=$("reviewer").value.trim(); f.reviewed_at=$("reviewedAt").value; f.review_basis=$("reviewBasis").value.trim(); f.receipt=$("receipt").value.trim(); if(state.kind==="substrate") f.representation_type=$("representationType").value; const row={review_key:state.selected.review_key,decision:f.decision,review_basis:f.review_basis,reviewer:f.reviewer,reviewed_at:f.reviewed_at,acceptance_receipt:f.receipt}; checks[state.kind].forEach(([k])=>row[k]=Boolean(f.checks[k])); if(state.kind==="strict") row.approved_label=state.selected.candidate_label; if(state.kind==="substrate") { row.representation_type=f.representation_type||"process_mixture"; row.substrate_smiles=state.selected.substrate_smiles||null; } return row; }
function localValidate(row) { const errors=[]; if(!row.review_key) errors.push("缺少记录"); if(!row.reviewer) errors.push("请填写真实审核人"); if(!row.reviewed_at) errors.push("请填写审核时间"); if(!row.review_basis) errors.push("请填写审核依据"); if(!row.acceptance_receipt) errors.push("请填写真实receipt或实验记录号"); if(row.decision.includes("approve")) checks[state.kind].forEach(([k])=>{if(!row[k])errors.push(`通过前必须确认：${k}`);}); return errors; }
async function save() { if(!state.selected)return; const row=buildDecision(); const errors=localValidate(row); if(errors.length){$("output").textContent=`不能保存：\n- ${errors.join("\n- ")}`;return;} try { const d=await api("../../api/save-hard-gate-decision",{kind:state.kind,decision:row}); $("output").textContent=`已保存人工结论。\n${JSON.stringify(d,null,2)}\n\n注意：保存不等于训练导入，下一步请点击“验证两个硬门槛”。`; await load(); } catch(e){$("output").textContent=`保存失败：${e.message}`;} }
async function validate() { try { const d=await api("../../api/run-step",{step:"validate_hard_gate_reviews"}); $("output").textContent=`验证结果：\n${d.stdout||JSON.stringify(d,null,2)}`; } catch(e){$("output").textContent=`验证失败：${e.message}`;} }
async function pollRun(runId, label) {
  for(let i=0;i<180;i+=1) {
    await new Promise(resolve=>setTimeout(resolve,1500));
    const d=await api(`../../api/run-step-status?id=${encodeURIComponent(runId)}`);
    $("output").textContent=`${label} 正在运行...\nrun_id=${runId}\n状态：${d.status}`;
    if(["succeeded","failed"].includes(d.status)) {
      if(!d.ok) throw new Error([d.stderr,d.stdout].filter(Boolean).join("\n\n") || `${label} 执行失败`);
      return d;
    }
  }
  throw new Error(`${label} 超时，请到服务端查看 run_id=${runId}`);
}
async function runGuideStep(step) {
  const item=guideSteps.find(([s])=>s===step);
  const label=item?item[1]:step;
  state.busy=true;
  renderGuide();
  try {
    $("output").textContent=`正在执行：${label}...`;
    let d=await api("../../api/run-step",{step});
    if(d.run_id) d=await pollRun(d.run_id,label);
    const stdout=d.stdout?`\n\n输出：\n${d.stdout}`:"";
    const stderr=d.stderr?`\n\n提示：\n${d.stderr}`:"";
    $("output").textContent=`${label} 完成。${stdout}${stderr}`;
    await load();
    return true;
  } catch(e) {
    $("output").textContent=`${label} 失败：\n${e.message}`;
    return false;
  } finally {
    state.busy=false;
    renderGuide();
  }
}
async function runAllGuide() {
  for(const [step] of guideSteps) {
    const ok=await runGuideStep(step);
    if(!ok) return;
  }
  $("output").textContent += "\n\n全部按钮流程已跑完。请看上方 Benchmark 和安全管线状态；没有正式人工通过时仍会保持 blocked。";
}
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.kind=b.dataset.kind;state.selected=state.packets[state.kind][0]||null;render();})); $("saveBtn").addEventListener("click",save); $("validateBtn").addEventListener("click",validate); $("refreshBtn").addEventListener("click",()=>load().catch(e=>$("output").textContent=`加载失败：${e.message}`)); load().catch(e=>{document.body.innerHTML=`<pre style="padding:20px">加载失败：${e.message}</pre>`;});
$("runAllBtn").addEventListener("click",runAllGuide);

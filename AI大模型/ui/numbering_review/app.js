const STORAGE_KEY = "kwb-numbering-review-v1";
const CHECKS = [
  ["sourceProteinConfirmed", "原文确认蛋白身份"],
  ["mutationFound", "原文找到突变写法"],
  ["numberingBasisConfirmed", "编号体系已确认"],
  ["wtResidueVerified", "WT 残基映射已核实"],
  ["assayProvenanceChecked", "实验/测量来源已核实"],
  ["notTitleOnly", "不是标题/摘要弱匹配"],
];

const WORKFLOW_STEPS = [
  { key: "save", label: "保存正式结果", shortLabel: "保存", hint: "把当前人工判断写入正式 decision 文件。" },
  { key: "validate", label: "运行验证", shortLabel: "验证", hint: "检查正式 decision 文件格式和审核规则。" },
  { key: "apply", label: "应用修正", shortLabel: "应用", hint: "把通过验证的编号修正应用到可用数据。" },
  { key: "pipeline", label: "安全管线", shortLabel: "安全管线", hint: "重新运行安全训练前检查，刷新可声明状态。" },
  { key: "done", label: "完成", shortLabel: "完成", hint: "这条记录的按钮流程已完成，可以继续审核下一条。" },
];

const GUIDES = {
  map_to_canonical: {
    title: "正确：证据明确，才能标 map",
    bullets: [
      "原文/数据库明确是这个蛋白。",
      "原文里能找到这个突变写法或等价写法。",
      "能说清楚作者编号、isoform 编号或成熟蛋白编号怎么转到 canonical。",
      "canonical 位置上的 WT 残基必须对得上。",
      "不确定时不要 map，先标 weak。",
    ],
  },
  keep_unresolved_weak: {
    title: "不确定：看不准就标 weak",
    bullets: [
      "找到了部分线索，但蛋白、突变、编号体系有一项说不清。",
      "可能是 isoform 或构建体编号，但没有足够证据映射 canonical。",
      "weak 不进入强监督训练，只保留为弱证据。",
      "这是保守结论，不是失败。",
    ],
  },
  reject_label: {
    title: "错误：明显对不上就标 reject",
    bullets: [
      "PMID/文章不是这个蛋白。",
      "文章里找不到这个突变。",
      "数据库记录疑似串文献、串蛋白或串突变。",
      "reject 会拒绝该标签，不让它进入训练。",
    ],
  },
};

const state = {
  rows: [],
  filtered: [],
  selectedId: null,
  drafts: {},
  forms: {},
  existingDecisions: {},
  semanticConflicts: {},
  serverAvailable: false,
  decisionRows: null,
  semanticConflictRows: null,
  operatorQueueRows: null,
  openNumberingRows: null,
  operatorQueueGeneratedAt: null,
  semanticConflictGeneratedAt: null,
  workflowSteps: {},
  busyByRecord: {},
  pipelineRuns: {},
};

const el = {};

function qs(id) {
  return document.getElementById(id);
}

function loadStore() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    state.drafts = parsed.drafts || {};
    state.forms = parsed.forms || {};
    state.workflowSteps = parsed.workflowSteps || {};
  } catch {
    state.drafts = {};
    state.forms = {};
    state.workflowSteps = {};
  }
}

function saveStore() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      drafts: state.drafts,
      forms: state.forms,
      workflowSteps: state.workflowSteps,
    })
  );
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function fetchJsonl(path) {
  const response = await fetch(path);
  if (!response.ok) return [];
  const text = await response.text();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function apiJson(path, payload = null) {
  const options = payload
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    : {};
  const response = await fetch(path, options);
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || data.stderr || data.raw || `${path} ${response.status}`);
  }
  return data;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollRunStep(runId, label) {
  for (;;) {
    await sleep(3000);
    const response = await fetch(`../../api/run-step-status?id=${encodeURIComponent(runId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `${label} 状态查询失败`);
    if (data.status === "queued" || data.status === "running") {
      const started = data.started_at ? `；started_at=${data.started_at}` : "";
      setStepOutput(`${label} 正在后台执行，页面会自动刷新状态${started}。`);
      continue;
    }
    if (data.status === "succeeded") return data;
    throw new Error(data.error || data.stderr || `${label} 后台任务失败`);
  }
}

async function pollPipelineRun(recordId, runId, label) {
  for (;;) {
    await sleep(3000);
    const response = await fetch(`../../api/run-step-status?id=${encodeURIComponent(runId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `${label} 状态查询失败`);
    if (data.status === "queued" || data.status === "running") {
      if (state.selectedId === recordId) {
        setStepOutput(`${label} ${data.status === "queued" ? "排队中" : "执行中"}，可继续复核其他记录。\n\nrun_id=${runId}`);
      }
      continue;
    }
    delete state.pipelineRuns[recordId];
    const row = state.rows.find((item) => item.record_id === recordId);
    if (data.status === "succeeded") {
      setWorkflowStep(row, 4);
      if (state.selectedId === recordId) setStepOutput(`${label} 已通过。\n\nrun_id=${runId}`);
      updateWorkflowButtons();
      return data;
    }
    if (state.selectedId === recordId) setStepOutput(`${label} 失败，可重新提交。\n\nrun_id=${runId}\n${data.error || data.stderr || ""}`);
    updateWorkflowButtons();
    throw new Error(data.error || data.stderr || `${label} 后台任务失败`);
  }
}

function mutationParts(mutation) {
  const match = String(mutation || "").match(/^([A-Za-z])(\d+)([A-Za-z])$/);
  if (!match) return { wt: "", pos: "", mut: "" };
  return { wt: match[1].toUpperCase(), pos: match[2], mut: match[3].toUpperCase() };
}

function toDatetimeLocal(date = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function datetimeLocalToIso(value) {
  if (!value) return new Date().toISOString();
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString();
}

function displayDateTime(iso) {
  const date = iso ? new Date(iso) : new Date();
  if (Number.isNaN(date.getTime())) return toDatetimeLocal();
  return toDatetimeLocal(date);
}

function sourceRefsFor(row) {
  const refs = [];
  const pmid = row.pmid || row.publication_pubmed || row.literature_ref;
  if (pmid) refs.push(pmid);
  if (row.uniprot_id) refs.push(`UniProt:${row.uniprot_id}`);
  (row.candidate_isoforms || []).forEach((isoform) => refs.push(`UniProtIsoform:${isoform}`));
  return refs;
}

function defaultForm(row) {
  const parts = mutationParts(row.mutation);
  const deepAuditReject = row.audit_recommended_decision === "reject_label";
  return {
    checks: {},
    decision: deepAuditReject ? "reject_label" : "keep_unresolved_weak",
    canonical_uniprot_id: row.uniprot_id || "",
    canonical_position: "",
    canonical_wild_type: "",
    canonical_mutant: parts.mut || "",
    mapping_basis: "unresolved",
    source_refs: sourceRefsFor(row).join(", "),
    confidence: 0,
    notes: deepAuditReject
      ? `Deep audit recommends reject_label for ${row.record_id}: source lineage is generated or fixture data and must not be mapped into supervised labels. Confirm the evidence, then keep reject_label or document a separately imported real-source receipt.`
      : `Human review pending for ${row.record_id}; source protein, mutation, numbering basis, WT residue, and assay provenance must be checked before promotion.`,
    curator: localStorage.getItem("kwb-numbering-curator") || "keweibo",
    curated_at: toDatetimeLocal(),
  };
}

function noteTemplate(kind, row, form) {
  const pmid = row.pmid || row.publication_pubmed || row.literature_ref || "PMID";
  const uniprot = form.canonical_uniprot_id || row.uniprot_id || "UniProt";
  const mutation = row.mutation || "mutation";
  if (kind === "map") {
    return `已人工核实 ${pmid} 和 ${uniprot}；原文支持 ${mutation}，编号体系为 ${form.mapping_basis}，可映射到 canonical ${uniprot} position ${form.canonical_position || "待填"}，WT=${form.canonical_wild_type || "待填"}，mutant=${form.canonical_mutant || "待填"}。`;
  }
  if (kind === "weak") {
    return `已人工核实 ${pmid} 和 ${uniprot}；目前不能同时确认蛋白身份、突变证据、编号体系和 canonical 映射，保留为 weak evidence，不进入强监督训练。`;
  }
  return `已人工核实 ${pmid}；该来源不能支持 ${uniprot} 的 ${mutation} 标签，疑似文献、蛋白或突变匹配错误，拒绝该标签。`;
}

function formFor(recordId) {
  const row = state.rows.find((item) => item.record_id === recordId);
  if (!state.forms[recordId]) state.forms[recordId] = defaultForm(row);
  return state.forms[recordId];
}

function currentRow() {
  return state.rows.find((row) => row.record_id === state.selectedId) || null;
}

function setText(node, value) {
  node.textContent = value == null || value === "" ? "-" : String(value);
}

function statusFor(row) {
  if (state.semanticConflicts[row.record_id]) return "conflict";
  if (state.existingDecisions[row.record_id]) return "existing";
  if (state.drafts[row.record_id]) return "drafted";
  return "todo";
}

function getWorkflowStep(row) {
  if (!row) return 0;
  const stored = Number(state.workflowSteps[row.record_id] || 0);
  const saved = state.existingDecisions[row.record_id] ? 1 : 0;
  return Math.max(stored, saved);
}

function setWorkflowStep(row, step) {
  if (!row) return;
  state.workflowSteps[row.record_id] = Math.max(getWorkflowStep(row), step);
  saveStore();
}

function currentWorkflowAction(row) {
  const step = getWorkflowStep(row);
  return WORKFLOW_STEPS[Math.min(step, WORKFLOW_STEPS.length - 1)];
}

function applyFilters() {
  const query = el.searchInput.value.trim().toLowerCase();
  const packet = el.packetFilter.value;
  const decisionFilter = el.decisionFilter.value;
  state.filtered = state.rows.filter((row) => {
    const searchable = [
      row.record_id,
      row.uniprot_id,
      row.mutation,
      row.pmid || row.publication_pubmed || row.literature_ref,
      row.notes,
      row.protein_name,
      (row.ec_numbers || []).join(" "),
      row.packet_id,
    ].join(" ").toLowerCase();
    const queryOk = !query || searchable.includes(query);
    const packetOk = packet === "all" || row.packet_id === packet;
    const status = statusFor(row);
    const statusOk = decisionFilter === "all" || decisionFilter === status;
    return queryOk && packetOk && statusOk;
  });
}

function renderQueue() {
  applyFilters();
  if (!state.filtered.some((row) => row.record_id === state.selectedId)) {
    state.selectedId = state.filtered[0]?.record_id || null;
  }
  el.queueMeta.textContent = `${state.filtered.length} / ${state.rows.length} rows`;
  const conflictCount = state.rows.filter((row) => statusFor(row) === "conflict").length;
  const openCount = state.rows.filter((row) => statusFor(row) === "todo").length;
  el.openCount.textContent = conflictCount ? `${conflictCount} conflicts · ${openCount} open` : `${openCount} open`;
  el.queueList.innerHTML = "";
  if (!state.filtered.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = state.rows.length
      ? "当前筛选条件下没有记录。"
      : "队列数据为空，请刷新最新数据或检查 reports/numbering_review_operator_queue.json。";
    el.queueList.appendChild(empty);
    return;
  }
  state.filtered.forEach((row) => {
    const status = statusFor(row);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `queue-row ${row.record_id === state.selectedId ? "active" : ""}`;
    button.innerHTML = `
      <span class="rank">${row.review_rank || row.execution_order || ""}</span>
      <span>
        <strong>${row.record_id} · ${row.mutation}</strong>
        <small>${row.uniprot_id} · ${row.packet_id} · ${row.operator_status || row.audit_recommended_decision || row.title_flag}</small>
      </span>
      <span class="row-state ${status}" title="${status}"></span>
    `;
    button.addEventListener("click", () => {
      persistCurrentForm();
      state.selectedId = row.record_id;
      renderAll();
    });
    el.queueList.appendChild(button);
  });
}

function renderDetail(row) {
  const parts = mutationParts(row.mutation);
  const pmidValue = row.pmid || row.publication_pubmed || row.literature_ref || "";
  const ecNumbers = (row.ec_numbers || []).join(", ");
  const evidenceTitle = [row.protein_name, ecNumbers ? `EC ${ecNumbers}` : "", row.notes].filter(Boolean).join(" · ");
  setText(el.detailTitle, `${row.record_id} · ${row.mutation}`);
  setText(el.detailUniProt, row.uniprot_id);
  setText(el.detailMutation, row.mutation);
  setText(el.detailReported, `${parts.wt || "?"}${parts.pos || "?"}${parts.mut || "?"}`);
  const residue = row.current_residue || row.current_sequence_residue;
  setText(el.detailResidue, residue ? `${residue} at reported position` : "-");
  setText(el.detailTitleText, evidenceTitle || row.notes);
  setText(el.detailIsoforms, (row.candidate_isoforms || []).join(", "));
  setText(el.detailMethod, row.method);
  setText(el.detailSourceDb, row.source_db);
  const auditFlags = (row.audit_flags || []).slice(0, 3).join(", ");
  setText(
    el.detailAudit,
    row.audit_recommended_decision
      ? `${row.audit_recommended_decision}; ${auditFlags || "deep audit evidence present"}`
      : "-"
  );
  setText(el.detailNextAction, row.operator_next_action);
  el.riskBadge.textContent = row.audit_recommended_decision || row.title_flag || "risk";
  el.riskBadge.className = `risk-badge ${
    state.semanticConflicts[row.record_id] || row.audit_recommended_decision === "reject_label" || row.title_flag === "title_mismatch_risk"
      ? "blocked"
      : "warn"
  }`;
  el.trackState.textContent = statusFor(row);
  const pmid = String(pmidValue).replace(/^PMID:/, "");
  el.pubmedLink.textContent = pmidValue || "-";
  el.pubmedLink.href = pmid ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/` : "#";
  el.externalLinks.innerHTML = `
    <a href="https://www.uniprot.org/uniprotkb/${encodeURIComponent(row.uniprot_id || "")}/entry" target="_blank" rel="noreferrer">UniProt</a>
    <span> · </span>
    <a href="https://scholar.google.com/scholar?q=${encodeURIComponent(`${row.uniprot_id || ""} ${row.mutation || ""} ${pmid}`)}" target="_blank" rel="noreferrer">Scholar</a>
  `;
}

function renderConflictBox(row) {
  const conflict = state.semanticConflicts[row.record_id];
  if (!conflict) {
    el.conflictBox.hidden = true;
    return;
  }
  el.conflictBox.hidden = false;
  el.conflictRecord.textContent = row.record_id;
  el.conflictText.textContent =
    "人工意见写的是拒绝/不能支持该标签，但正式字段还是 keep_unresolved_weak。请二选一：按意见改成 reject，或重新确认只保留 weak。";
}

function renderChecks(row) {
  const form = formFor(row.record_id);
  el.checkGrid.innerHTML = "";
  CHECKS.forEach(([key, label]) => {
    const wrapper = document.createElement("label");
    wrapper.className = "check-item";
    wrapper.innerHTML = `
      <input type="checkbox" data-check="${key}" ${form.checks[key] ? "checked" : ""} />
      <span>${label}</span>
    `;
    wrapper.querySelector("input").addEventListener("change", (event) => {
      form.checks[key] = event.target.checked;
      saveStore();
      updateValidation();
    });
    el.checkGrid.appendChild(wrapper);
  });
}

function renderForm(row) {
  const form = formFor(row.record_id);
  [...el.decisionButtons.querySelectorAll("button")].forEach((button) => {
    button.classList.toggle("active", button.dataset.decision === form.decision);
  });
  el.canonicalUniprot.value = form.canonical_uniprot_id || "";
  el.canonicalPosition.value = form.canonical_position || "";
  el.canonicalWt.value = form.canonical_wild_type || "";
  el.canonicalMutant.value = form.canonical_mutant || "";
  el.mappingBasis.value = form.mapping_basis || "unresolved";
  el.confidence.value = form.confidence || 0;
  el.confidenceValue.textContent = Number(form.confidence || 0).toFixed(2);
  el.sourceRefs.value = form.source_refs || "";
  el.notes.value = form.notes || "";
  el.curator.value = form.curator || "";
  el.curatedAt.value = displayDateTime(form.curated_at);
  el.jsonlOutput.value = state.drafts[row.record_id] || "";
  renderPlainGuide(form.decision);
  renderConflictBox(row);
  [el.buildLineBtn, el.saveDraftBtn, el.clearDraftBtn].forEach((button) => {
    button.disabled = false;
  });
  updateValidation();
}

function renderEmptySelection() {
  setText(el.detailTitle, "当前筛选条件下没有记录");
  [el.detailUniProt, el.detailMutation, el.detailReported, el.detailResidue, el.detailTitleText, el.detailIsoforms,
    el.detailMethod, el.detailSourceDb, el.detailAudit, el.detailNextAction].forEach((node) => setText(node, "-"));
  el.riskBadge.textContent = "empty";
  el.riskBadge.className = "risk-badge";
  el.trackState.textContent = "-";
  el.pubmedLink.textContent = "-";
  el.pubmedLink.href = "#";
  el.externalLinks.innerHTML = "";
  el.checkGrid.innerHTML = "";
  el.conflictBox.hidden = true;
  [...el.decisionButtons.querySelectorAll("button")].forEach((button) => button.classList.remove("active"));
  [el.canonicalUniprot, el.canonicalPosition, el.canonicalWt, el.canonicalMutant, el.sourceRefs, el.notes, el.curator, el.jsonlOutput]
    .forEach((input) => { input.value = ""; });
  el.confidence.value = "0";
  el.confidenceValue.textContent = "0.00";
  el.validationBox.className = "validation-box blocked";
  el.validationBox.textContent = "当前筛选条件下没有记录。";
  el.readinessBadge.textContent = "blocked";
  el.readinessBadge.className = "risk-badge blocked";
  [el.buildLineBtn, el.saveDraftBtn, el.clearDraftBtn].forEach((button) => {
    button.disabled = true;
  });
  updateWorkflowButtons();
}

function renderPlainGuide(decision) {
  const guide = GUIDES[decision] || GUIDES.keep_unresolved_weak;
  el.guideDecision.textContent = guide.title;
  el.guideBullets.innerHTML = guide.bullets.map((item) => `<li>${item}</li>`).join("");
}

function persistCurrentForm() {
  if (!state.selectedId) return;
  const form = formFor(state.selectedId);
  form.canonical_uniprot_id = el.canonicalUniprot.value.trim();
  form.canonical_position = el.canonicalPosition.value.trim();
  form.canonical_wild_type = el.canonicalWt.value.trim().toUpperCase();
  form.canonical_mutant = el.canonicalMutant.value.trim().toUpperCase();
  form.mapping_basis = el.mappingBasis.value;
  form.confidence = Number(el.confidence.value || 0);
  form.source_refs = el.sourceRefs.value.trim();
  form.notes = el.notes.value.trim();
  form.curator = el.curator.value.trim();
  form.curated_at = el.curatedAt.value;
  localStorage.setItem("kwb-numbering-curator", form.curator);
  saveStore();
}

function validateForm(row, form) {
  const errors = [];
  if (!form.decision) errors.push("decision 缺失");
  if (!form.curator) errors.push("curator 缺失");
  if (!form.notes) errors.push("notes 缺失");
  if (!form.source_refs) errors.push("source_refs 缺失");
  if (form.decision === "map_to_canonical") {
    if (!form.canonical_uniprot_id) errors.push("canonical UniProt 缺失");
    if (!form.canonical_position) errors.push("canonical position 缺失");
    if (!form.canonical_wild_type) errors.push("canonical WT 缺失");
    if (!form.canonical_mutant) errors.push("mutant 缺失");
    if (form.mapping_basis === "unresolved") errors.push("map 不能使用 unresolved basis");
    if (Number(form.confidence) < 0.5) errors.push("map confidence 必须 >= 0.5");
  }
  if (form.decision !== "map_to_canonical" && Number(form.confidence) > 0.49) {
    errors.push("weak/reject 建议 confidence < 0.5");
  }
  if (row.title_flag === "title_mismatch_risk" && form.decision === "map_to_canonical" && !form.checks.notTitleOnly) {
    errors.push("title mismatch 必须确认不是标题/摘要弱匹配");
  }
  if (row.audit_recommended_decision === "reject_label" && form.decision === "map_to_canonical") {
    errors.push("深度审计已标记 generated/fixture source，不能 map；需 reject 或导入独立真实来源回执");
  }
  return errors;
}

function updateValidation() {
  const row = currentRow();
  if (!row) return;
  persistCurrentForm();
  const form = formFor(row.record_id);
  const errors = validateForm(row, form);
  const ready = errors.length === 0;
  const unchecked = CHECKS.filter(([key]) => !form.checks[key]).length;
  el.validationBox.className = `validation-box ${ready ? "ready" : "blocked"}`;
  el.validationBox.textContent = ready
    ? unchecked
      ? `浏览器字段检查通过；${unchecked} 项人工核实尚未勾选，仍可提交草稿。正式写入后仍必须运行本地 validator。`
      : "浏览器字段检查通过；正式写入后仍必须运行本地 validator。"
    : `阻塞：${errors.join("；")}`;
  el.readinessBadge.textContent = ready ? "draft ready" : "blocked";
  el.readinessBadge.className = `risk-badge ${ready ? "ready" : "blocked"}`;
  updateWorkflowButtons();
}

function buildDecisionLine() {
  const row = currentRow();
  persistCurrentForm();
  const form = formFor(row.record_id);
  const sourceRefs = form.source_refs
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const isMap = form.decision === "map_to_canonical";
  const decision = {
    record_id: row.record_id,
    decision: form.decision,
    canonical_uniprot_id: isMap ? form.canonical_uniprot_id : form.canonical_uniprot_id || null,
    canonical_position: isMap ? Number(form.canonical_position) : null,
    canonical_wild_type: isMap ? form.canonical_wild_type : null,
    canonical_mutant: isMap ? form.canonical_mutant : form.canonical_mutant || null,
    mapping_basis: form.mapping_basis,
    source_refs: sourceRefs,
    confidence: Number(form.confidence),
    notes: form.notes,
    curator: form.curator,
    curated_at: datetimeLocalToIso(form.curated_at),
    expected_submission_id: state.existingDecisions[row.record_id]?.submission_id || null,
  };
  return JSON.stringify(decision);
}

function renderAll() {
  renderQueue();
  const row = currentRow();
  if (row) {
    renderDetail(row);
    renderChecks(row);
    renderForm(row);
  } else {
    renderEmptySelection();
  }
}

function updatePacketFilter() {
  const current = el.packetFilter.value || "all";
  const packets = ["all", ...new Set(state.rows.map((row) => row.packet_id).filter(Boolean))];
  el.packetFilter.innerHTML = packets
    .map((packet) => `<option value="${packet}">${packet === "all" ? "全部 packet" : packet}</option>`)
    .join("");
  el.packetFilter.value = packets.includes(current) ? current : "all";
}

function hydrateRows(baseRows, statusRows, deepAuditRows, semanticConflictRows) {
  const statusById = {};
  statusRows.forEach((row) => {
    statusById[row.record_id] = row;
  });
  const deepAuditById = {};
  deepAuditRows.forEach((row) => {
    deepAuditById[row.record_id] = row;
  });
  const rowMap = {};
  baseRows.forEach((row) => {
    rowMap[row.record_id] = row;
  });
  semanticConflictRows.forEach((row) => {
    if (!rowMap[row.record_id]) {
      rowMap[row.record_id] = {
        record_id: row.record_id,
        uniprot_id: row.uniprot_id,
        mutation: row.mutation,
        pmid: (row.source_refs || []).find((ref) => String(ref).startsWith("PMID:")),
        packet_id: "semantic_conflict",
        review_rank: "!",
        notes: row.notes,
        title_flag: row.conflict_type,
      };
    }
  });
  return Object.values(rowMap).map((row) => ({
    ...row,
    ...(statusById[row.record_id] || {}),
    ...(deepAuditById[row.record_id] || {}),
    ...(state.semanticConflicts[row.record_id] || {}),
  })).sort((a, b) => {
    const orderA = Number(a.operator_order || a.review_rank || 999999);
    const orderB = Number(b.operator_order || b.review_rank || 999999);
    return orderA - orderB;
  });
}

function setStepOutput(message, payload = null) {
  const suffix = payload ? `\n\n${JSON.stringify(payload, null, 2)}` : "";
  el.stepOutput.textContent = `${message}${suffix}`;
}

function isWorkflowBusy(row = currentRow()) {
  return Boolean(row && state.busyByRecord[row.record_id]);
}

function setWorkflowBusy(row, isBusy) {
  if (!row) return;
  if (isBusy) state.busyByRecord[row.record_id] = true;
  else delete state.busyByRecord[row.record_id];
  updateWorkflowButtons();
}

function updateWorkflowButtons() {
  const row = currentRow();
  const form = row ? formFor(row.record_id) : null;
  const ready = row && form && validateForm(row, form).length === 0;
  const step = getWorkflowStep(row);
  const action = currentWorkflowAction(row);
  const busy = isWorkflowBusy(row);
  const pipelinePending = Boolean(row && state.pipelineRuns[row.record_id]);
  const disabled = !state.serverAvailable || busy;

  el.saveOfficialBtn.disabled = disabled || !ready;
  el.runValidateBtn.disabled = disabled || step < 1;
  el.runApplyBtn.disabled = disabled || step < 2;
  el.runPipelineBtn.disabled = disabled || pipelinePending || step < 3;
  el.nextStepBtn.disabled = disabled || pipelinePending || step >= 4 || (!ready && step === 0);
  el.nextStepBtn.textContent = step >= 4 ? "流程完成，审核下一条" : `下一步：${action.label}`;
  el.workflowCurrent.textContent = step >= 4 ? "当前记录已完成按钮流程" : `当前：${action.label}`;
  el.workflowHint.textContent =
    !ready && step === 0
      ? "先选择 map / weak / reject，补齐来源和意见；人工核实项可按进度逐项补充。"
      : pipelinePending
        ? `安全管线已排队：${state.pipelineRuns[row.record_id]}`
        : action.hint;

  [
    [el.stepSave, 0],
    [el.stepValidate, 1],
    [el.stepApply, 2],
    [el.stepPipeline, 3],
  ].forEach(([node, index]) => {
    node.className = "wizard-step";
    if (step > index) node.classList.add("done");
    if (step === index && step < 4) node.classList.add("active");
  });

  if (!state.serverAvailable) {
    el.serverMode.textContent = "按钮服务未启用：当前只能生成草稿。请用专用平台服务打开页面。";
  } else if (busy) {
    el.serverMode.textContent = "当前记录正在提交；其他记录仍可继续复核。";
  } else {
    const countText = state.decisionRows == null ? "" : `；正式 decision 文件已有 ${state.decisionRows} 行`;
    const conflictText = state.semanticConflictRows == null ? "" : `；语义冲突 ${state.semanticConflictRows} 条`;
    const queueText = state.operatorQueueRows == null ? "" : `；完整队列 ${state.operatorQueueRows} 条`;
    const openText = state.openNumberingRows == null ? "" : `；待审 ${state.openNumberingRows} 条`;
    el.serverMode.textContent = `按钮服务已启用${countText}${conflictText}${queueText}${openText}。`;
  }
}

async function detectServerMode() {
  try {
    const status = await apiJson("../../api/status");
    state.serverAvailable = true;
    state.decisionRows = status.decision_rows;
    state.semanticConflictRows = status.semantic_conflict_rows;
    state.operatorQueueRows = status.operator_queue_rows;
    state.openNumberingRows = status.open_numbering_rows;
    state.semanticConflictGeneratedAt = status.semantic_conflict_generated_at || null;
    state.operatorQueueGeneratedAt = status.operator_queue_generated_at || null;
    updateWorkflowButtons();
  } catch {
    state.serverAvailable = false;
    state.decisionRows = null;
    state.semanticConflictRows = null;
    state.operatorQueueRows = null;
    state.openNumberingRows = null;
    state.semanticConflictGeneratedAt = null;
    state.operatorQueueGeneratedAt = null;
    el.serverMode.textContent = "按钮服务未启用：当前页面不能直接写入或运行验证。";
    updateWorkflowButtons();
  }
}

async function refreshLatestData() {
  const row = currentRow();
  if (!state.serverAvailable || isWorkflowBusy(row)) return;
  setWorkflowBusy(row, true);
  try {
    setStepOutput("正在刷新最新编号数据...");
    const result = await apiJson("../../api/run-step", { step: "refresh_numbering_review_data" });
    const stdout = result.stdout ? `\n\n输出：\n${result.stdout}` : "";
    setStepOutput(`最新编号数据已刷新。${stdout}`);
    window.location.reload();
  } catch (error) {
    setStepOutput(`刷新失败：${error.message}`);
  } finally {
    setWorkflowBusy(row, false);
  }
}

async function saveOfficialDecision() {
  const row = currentRow();
  if (!row || isWorkflowBusy(row)) return false;
  setWorkflowBusy(row, true);
  try {
    persistCurrentForm();
    const form = formFor(row.record_id);
    const errors = validateForm(row, form);
    if (errors.length) {
      setStepOutput(`当前记录还不能保存：${errors.join("；")}`);
      return false;
    }
    const decision = JSON.parse(buildDecisionLine());
    setStepOutput("正在保存正式审核结果...");
    const result = await apiJson("../../api/save-numbering-decision", { decision });
    state.decisionRows = result.decision_rows;
    state.existingDecisions[row.record_id] = {
      ...decision,
      submission_id: result.submission_id,
      submitted_at: result.submitted_at,
    };
    delete state.drafts[row.record_id];
    setWorkflowStep(row, 1);
    saveStore();
    renderQueue();
    setStepOutput(`已保存 ${row.record_id} 的正式审核结果。下一步点按钮运行验证。`);
    return true;
  } finally {
    setWorkflowBusy(row, false);
  }
}

async function rebuildSemanticConflictQueue() {
  try {
    await apiJson("../../api/run-step", { step: "build_semantic_conflicts" });
    const rows = await fetchJsonl("../../datasets/curation/numbering_decision_semantic_conflict_queue.jsonl");
    state.semanticConflicts = {};
    rows.forEach((row) => {
      if (row.record_id) state.semanticConflicts[row.record_id] = row;
    });
    state.semanticConflictRows = rows.length;
  } catch {
    // Validation and pipeline buttons still expose server-side failures.
  }
}

async function resolveSemanticConflict(action) {
  const row = currentRow();
  if (!row || isWorkflowBusy(row)) return false;
  const conflict = state.semanticConflicts[row.record_id];
  if (!conflict) {
    setStepOutput("当前记录不在语义冲突队列里。");
    return false;
  }
  persistCurrentForm();
  const form = formFor(row.record_id);
  const notes =
    action === "convert_to_reject_label"
      ? noteTemplate("reject", row, form)
      : `已人工确认 ${row.record_id} 仅保留为 unresolved weak evidence，不进入强监督训练；当前证据不足，等待真实来源回执后再复核。`;
  setWorkflowBusy(row, true);
  try {
    setStepOutput("正在保存语义冲突处理结果...");
    const result = await apiJson("../../api/resolve-numbering-semantic-conflict", {
      record_id: row.record_id,
      action,
      curator: form.curator || "keweibo",
      notes,
    });
    state.decisionRows = result.decision_rows;
    state.existingDecisions[row.record_id] = {
      ...(state.existingDecisions[row.record_id] || {}),
      record_id: row.record_id,
      decision: result.decision,
      notes,
      curator: form.curator || "keweibo",
    };
    delete state.semanticConflicts[row.record_id];
    setWorkflowStep(row, 1);
    saveStore();
    await rebuildSemanticConflictQueue();
    renderAll();
    setStepOutput(`已处理 ${row.record_id}：${result.decision}。下一步运行验证。`);
    return true;
  } finally {
    setWorkflowBusy(row, false);
  }
}

async function runServerStep(step, nextStep, label) {
  const row = currentRow();
  if (!row || isWorkflowBusy(row)) return false;
  setWorkflowBusy(row, true);
  try {
    setStepOutput(`正在执行：${label}...`);
    let result = await apiJson("../../api/run-step", { step });
    if (result.run_id && step === "safe_pipeline") {
      state.pipelineRuns[row.record_id] = result.run_id;
      setStepOutput(`${label} 已进入后台队列，可继续复核其他记录。\n\nrun_id=${result.run_id}`);
      pollPipelineRun(row.record_id, result.run_id, label).catch((error) => {
        delete state.pipelineRuns[row.record_id];
        if (state.selectedId === row.record_id) setStepOutput(`${label} 状态查询失败，可重新提交。\n\n${error.message}`);
        updateWorkflowButtons();
      });
      return true;
    }
    if (result.run_id) result = await pollRunStep(result.run_id, label);
    setWorkflowStep(row, nextStep);
    const stdout = result.stdout ? `\n\n输出：\n${result.stdout}` : "";
    const stderr = result.stderr ? `\n\n提示：\n${result.stderr}` : "";
    el.stepOutput.textContent = `${label} 已通过。${stdout}${stderr}`;
    return true;
  } finally {
    setWorkflowBusy(row, false);
  }
}

async function runValidateStep() {
  return runServerStep("validate_numbering", 2, "编号验证");
}

async function runApplyStep() {
  return runServerStep("apply_numbering", 3, "应用修正");
}

async function runPipelineStep() {
  return runServerStep("safe_pipeline", 4, "安全管线");
}

async function runNextStep() {
  try {
    const row = currentRow();
    const step = getWorkflowStep(row);
    if (step <= 0) {
      await saveOfficialDecision();
    } else if (step === 1) {
      await runValidateStep();
    } else if (step === 2) {
      await runApplyStep();
    } else if (step === 3) {
      await runPipelineStep();
    } else {
      setStepOutput("当前按钮流程已完成。可以选择下一条记录继续审核。");
    }
  } catch (error) {
    setStepOutput(`执行失败：${error.message}`);
  }
}

function exportDrafts() {
  const jsonl = Object.values(state.drafts).filter(Boolean).join("\n") + "\n";
  const blob = new Blob([jsonl], { type: "application/x-ndjson;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "numbering_curation_decisions.reviewed.draft.jsonl";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function copyDrafts() {
  const jsonl = Object.values(state.drafts).filter(Boolean).join("\n");
  await navigator.clipboard.writeText(jsonl);
  el.copyAllBtn.textContent = "已复制";
  setTimeout(() => {
    el.copyAllBtn.innerHTML = "<span>□</span> 复制草稿";
  }, 1200);
}

function bindEvents() {
  ["searchInput", "packetFilter", "decisionFilter"].forEach((id) => {
    el[id].addEventListener("input", renderAll);
  });
  el.decisionButtons.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-decision]");
    if (!button) return;
    setDecision(button.dataset.decision);
  });
  document.querySelectorAll("[data-rule-decision]").forEach((button) => {
    button.addEventListener("click", () => setDecision(button.dataset.ruleDecision));
  });
  document.querySelectorAll("[data-template]").forEach((button) => {
    button.addEventListener("click", () => {
      persistCurrentForm();
      const row = currentRow();
      if (!row) return;
      const form = formFor(row.record_id);
      el.notes.value = noteTemplate(button.dataset.template, row, form);
      updateValidation();
    });
  });
  el.resolveRejectBtn.addEventListener("click", () => {
    resolveSemanticConflict("convert_to_reject_label").catch((error) => setStepOutput(`处理失败：${error.message}`));
  });
  el.resolveWeakBtn.addEventListener("click", () => {
    resolveSemanticConflict("confirm_keep_unresolved_weak").catch((error) => setStepOutput(`处理失败：${error.message}`));
  });
  [
    "canonicalUniprot",
    "canonicalPosition",
    "canonicalWt",
    "canonicalMutant",
    "mappingBasis",
    "confidence",
    "sourceRefs",
    "notes",
    "curator",
    "curatedAt",
  ].forEach((id) => {
    el[id].addEventListener("input", () => {
      if (id === "confidence") el.confidenceValue.textContent = Number(el.confidence.value || 0).toFixed(2);
      updateValidation();
    });
  });
  el.buildLineBtn.addEventListener("click", () => {
    if (!currentRow()) return;
    el.jsonlOutput.value = buildDecisionLine();
  });
  el.saveDraftBtn.addEventListener("click", () => {
    if (!currentRow()) return;
    const line = buildDecisionLine();
    state.drafts[state.selectedId] = line;
    el.jsonlOutput.value = line;
    saveStore();
    renderQueue();
  });
  el.clearDraftBtn.addEventListener("click", () => {
    if (!currentRow()) return;
    delete state.drafts[state.selectedId];
    el.jsonlOutput.value = "";
    saveStore();
    renderQueue();
  });
  el.exportAllBtn.addEventListener("click", exportDrafts);
  el.copyAllBtn.addEventListener("click", copyDrafts);
  el.refreshBtn.addEventListener("click", () => {
    refreshLatestData().catch((error) => setStepOutput(`刷新失败：${error.message}`));
  });
  el.saveOfficialBtn.addEventListener("click", () => {
    saveOfficialDecision().catch((error) => setStepOutput(`保存失败：${error.message}`));
  });
  el.runValidateBtn.addEventListener("click", () => {
    runValidateStep().catch((error) => setStepOutput(`验证失败：${error.message}`));
  });
  el.runApplyBtn.addEventListener("click", () => {
    runApplyStep().catch((error) => setStepOutput(`应用失败：${error.message}`));
  });
  el.runPipelineBtn.addEventListener("click", () => {
    runPipelineStep().catch((error) => setStepOutput(`安全管线失败：${error.message}`));
  });
  el.nextStepBtn.addEventListener("click", runNextStep);
}

function setDecision(decision) {
  const row = currentRow();
  if (!row) return;
  const form = formFor(row.record_id);
  form.decision = decision;
  if (form.decision === "map_to_canonical" && Number(form.confidence) < 0.5) form.confidence = 0.75;
  if (form.decision !== "map_to_canonical") {
    form.mapping_basis = "unresolved";
    if (Number(form.confidence) > 0.49) form.confidence = 0;
  }
  saveStore();
  renderForm(row);
}

async function init() {
  [
    "searchInput",
    "packetFilter",
    "decisionFilter",
    "exportAllBtn",
    "copyAllBtn",
    "refreshBtn",
    "queueMeta",
    "openCount",
    "queueList",
    "detailTitle",
    "riskBadge",
    "detailUniProt",
    "detailMutation",
    "detailReported",
    "detailResidue",
    "trackState",
    "pubmedLink",
    "detailTitleText",
    "detailIsoforms",
    "detailMethod",
    "detailSourceDb",
    "detailAudit",
    "detailNextAction",
    "externalLinks",
    "checkGrid",
    "decisionButtons",
    "plainGuide",
    "guideDecision",
    "guideBullets",
    "conflictBox",
    "conflictRecord",
    "conflictText",
    "resolveRejectBtn",
    "resolveWeakBtn",
    "readinessBadge",
    "canonicalUniprot",
    "canonicalPosition",
    "canonicalWt",
    "canonicalMutant",
    "mappingBasis",
    "confidence",
    "confidenceValue",
    "curator",
    "curatedAt",
    "sourceRefs",
    "notes",
    "validationBox",
    "buildLineBtn",
    "saveDraftBtn",
    "clearDraftBtn",
    "jsonlOutput",
    "serverMode",
    "workflowCurrent",
    "workflowHint",
    "stepSave",
    "stepValidate",
    "stepApply",
    "stepPipeline",
    "saveOfficialBtn",
    "runValidateBtn",
    "runApplyBtn",
    "runPipelineBtn",
    "nextStepBtn",
    "stepOutput",
  ].forEach((id) => {
    el[id] = qs(id);
  });

  loadStore();
  async function loadReviewData() {
    const [briefing, statusRows, existingDecisions, deepAuditRows, semanticConflictRows] = await Promise.all([
      fetchJson("../../reports/numbering_review_briefing.json").catch(() => ({ briefing_rows: [] })),
      fetchJsonl("../../datasets/curation/numbering_review_briefing_status_board.jsonl"),
      fetchJsonl("../../datasets/curation/numbering_curation_decisions.jsonl"),
      fetchJsonl("../../datasets/curation/numbering_deep_audit_review_queue.jsonl"),
      fetchJsonl("../../datasets/curation/numbering_decision_semantic_conflict_queue.jsonl"),
    ]);
  const packetById = {};
  const statusById = {};
  statusRows.forEach((row) => {
    statusById[row.record_id] = row;
  });
  const deepAuditById = {};
  deepAuditRows.forEach((row) => {
    deepAuditById[row.record_id] = row;
  });
  existingDecisions.forEach((row) => {
    if (row.record_id) state.existingDecisions[row.record_id] = row;
  });
  semanticConflictRows.forEach((row) => {
    if (row.record_id) state.semanticConflicts[row.record_id] = row;
  });
  state.semanticConflictRows = semanticConflictRows.length;
  state.rows = hydrateRows(briefing.briefing_rows || [], statusRows, deepAuditRows, semanticConflictRows);
  loadFullOperatorQueue(statusRows, deepAuditRows, semanticConflictRows).catch(() => {
    // Keep the briefing queue visible if the full report is slow or unavailable.
  });
  }

  async function loadFullOperatorQueue(statusRows, deepAuditRows, semanticConflictRows) {
    const operatorQueue = await fetchJson("../../reports/numbering_review_operator_queue.json");
    state.rows = hydrateRows(operatorQueue.rows || operatorQueue.top_items || [], statusRows, deepAuditRows, semanticConflictRows);
    state.operatorQueueRows = operatorQueue.queue_rows;
    state.openNumberingRows = operatorQueue.open_numbering_rows;
    state.operatorQueueGeneratedAt = operatorQueue.created_at || null;
    if (!state.rows.find((row) => row.record_id === state.selectedId)) {
      state.selectedId = state.rows[0] ? state.rows[0].record_id : null;
    }
    updatePacketFilter();
    renderAll();
  }

  await loadReviewData();
  updatePacketFilter();
  bindEvents();
  await detectServerMode();
  renderAll();
}

init().catch((error) => {
  document.body.innerHTML = `<pre style="padding:20px;color:#b83232">加载失败：${error.message}</pre>`;
});

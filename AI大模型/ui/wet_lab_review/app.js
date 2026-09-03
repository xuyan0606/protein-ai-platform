const state = {
  rows: [],
  filtered: [],
  selectedId: null,
  forms: {},
};

const el = {};
const ORDER = { E331Q: 0, D105N: 1, S265T: 2 };

function qs(id) { return document.getElementById(id); }
function value(id) { return qs(id).value.trim(); }
function nowLocal() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function isoFromLocal(valueText) {
  const d = new Date(valueText);
  return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
}
function json(text) { return JSON.stringify(text, null, 2); }
async function api(path, payload) {
  const response = await fetch(path, payload ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  } : {});
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!response.ok || data.ok === false) throw new Error(data.error || data.stderr || data.raw || `HTTP ${response.status}`);
  return data;
}
function persist() {
  localStorage.setItem("kwb-wet-lab-review-v1", JSON.stringify({ forms: state.forms }));
}
function restore() {
  try { state.forms = JSON.parse(localStorage.getItem("kwb-wet-lab-review-v1") || "{}").forms || {}; } catch { state.forms = {}; }
}
function currentRow() { return state.rows.find((row) => row.feedback_candidate_id === state.selectedId); }
function sortRows(rows) {
  return [...rows].sort((a, b) => {
    const av = ORDER[a.variant] ?? 9;
    const bv = ORDER[b.variant] ?? 9;
    return av - bv || Number(a.source_row_index || 0) - Number(b.source_row_index || 0);
  });
}
function formFor(row) {
  if (!state.forms[row.feedback_candidate_id]) {
    state.forms[row.feedback_candidate_id] = {
      authorization_decision: "needs_more_info",
      qc_decision: "not_reviewed",
      reviewer: localStorage.getItem("kwb-wet-lab-reviewer") || "",
      reviewed_at: nowLocal(),
      authorization_basis: "",
      conditions: "",
      residual_risks: "尚未完成全部来源、编号、条件、批次和重复/QC 核实。",
      checks: {},
      activity_head: row.assay_type === "activity",
      stability_head: row.assay_type === "stability",
    };
  }
  return state.forms[row.feedback_candidate_id];
}
function statusFor(row) {
  const auth = row.authorization;
  if (auth?.authorization_decision === "approved_for_feedback_intake") return "approved";
  if (auth) return "saved";
  return "open";
}
function renderQueue() {
  const query = value("searchInput").toLowerCase();
  const variant = qs("variantFilter").value;
  const wantedStatus = qs("statusFilter").value;
  state.filtered = sortRows(state.rows).filter((row) => {
    const text = [row.variant, row.metric_name, row.feedback_candidate_id, row.sample_id, row.source_file].join(" ").toLowerCase();
    return (!query || text.includes(query)) &&
      (variant === "all" || row.variant === variant) &&
      (wantedStatus === "all" || statusFor(row) === wantedStatus);
  });
  qs("queueMeta").textContent = `${state.filtered.length} / ${state.rows.length} 条`;
  const open = state.rows.filter((row) => statusFor(row) === "open").length;
  qs("countBadge").textContent = `${open} 条未审核`;
  qs("queueList").innerHTML = "";
  state.filtered.forEach((row, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `queue-row ${row.feedback_candidate_id === state.selectedId ? "active" : ""}`;
    const status = statusFor(row);
    button.innerHTML = `<span class="rank">${index + 1}</span><span><strong>${row.variant} · ${row.metric_name}</strong><small>${row.outcome_candidate} · ratio ${Number(row.vs_control_ratio || 0).toFixed(3)}</small></span><span class="dot ${status}"></span>`;
    button.addEventListener("click", () => { state.selectedId = row.feedback_candidate_id; renderAll(); });
    qs("queueList").appendChild(button);
  });
}
function renderDetail(row) {
  if (!row) {
    qs("emptyState").classList.remove("hidden");
    qs("detailBody").classList.add("hidden");
    qs("detailHeading").textContent = "选择一条记录";
    return;
  }
  qs("emptyState").classList.add("hidden");
  qs("detailBody").classList.remove("hidden");
  qs("detailHeading").textContent = `${row.variant} · ${row.metric_name}`;
  const priority = row.qc_context?.review_priority || "review";
  qs("priorityBadge").textContent = priority;
  qs("priorityBadge").className = `badge ${row.qc_context?.conflicting_property_signal ? "danger" : "warn"}`;
  qs("variantValue").textContent = row.variant || "-";
  qs("metricValue").textContent = row.metric_name || "-";
  qs("outcomeValue").textContent = row.outcome_candidate || "-";
  qs("ratioValue").textContent = Number(row.vs_control_ratio || 0).toFixed(3);
  qs("candidateValue").textContent = row.feedback_candidate_id || "-";
  qs("batchValue").textContent = `${row.batch_id || "-"} / ${row.sample_id || "-"}`;
  qs("rawValue").textContent = `${row.raw_value_numeric ?? "-"} / ${row.control_value_numeric ?? "-"}`;
  qs("sourceValue").textContent = row.source_file || "-";
  qs("rowValue").textContent = row.source_row_index ?? "-";
  const tradeoff = qs("tradeoffBox");
  if (row.qc_context?.conflicting_property_signal) {
    tradeoff.classList.remove("hidden");
    tradeoff.textContent = "这是同一变体的多性质冲突记录：必须结合该变体全部 4 个指标审查，不能只看当前一行。";
  } else tradeoff.classList.add("hidden");
  qs("ruleNotice").textContent = row.variant === "E331Q"
    ? "E331Q 优先：酸性保持率为 go，但 85C 热稳定性为 no_go，授权前必须写清 tradeoff 处理意见。"
    : "按当前 metric 独立审核；同一变体的其他指标不能被自动合并成一个结论。";
}
function renderForm(row) {
  if (!row) return;
  const form = formFor(row);
  qs("decision").value = form.authorization_decision;
  qs("qcDecision").value = form.qc_decision;
  qs("reviewer").value = form.reviewer;
  qs("reviewedAt").value = form.reviewed_at;
  qs("basis").value = form.authorization_basis;
  qs("conditions").value = form.conditions;
  qs("risks").value = form.residual_risks;
  qs("activityHead").checked = Boolean(form.activity_head);
  qs("stabilityHead").checked = Boolean(form.stability_head);
  document.querySelectorAll("[data-check]").forEach((box) => { box.checked = Boolean(form.checks?.[box.dataset.check]); });
  const status = statusFor(row);
  qs("decisionState").textContent = status === "approved" ? "已授权" : status === "saved" ? "已保存" : "未审核";
  qs("decisionState").className = `badge ${status === "approved" ? "ready" : status === "saved" ? "warn" : "danger"}`;
}
function captureForm() {
  const row = currentRow();
  if (!row) return null;
  const form = formFor(row);
  form.authorization_decision = qs("decision").value;
  form.qc_decision = qs("qcDecision").value;
  form.reviewer = value("reviewer");
  form.reviewed_at = value("reviewedAt");
  form.authorization_basis = value("basis");
  form.conditions = value("conditions");
  form.residual_risks = value("risks");
  form.activity_head = qs("activityHead").checked;
  form.stability_head = qs("stabilityHead").checked;
  form.checks = {};
  document.querySelectorAll("[data-check]").forEach((box) => { form.checks[box.dataset.check] = box.checked; });
  state.forms[row.feedback_candidate_id] = form;
  persist();
  return form;
}
function validateForm(row, form) {
  const errors = [];
  const checks = ["source_trace_reviewed", "numbering_reviewed", "unit_condition_reviewed", "batch_control_reviewed", "replicate_policy_reviewed"];
  if (!form.reviewer) errors.push("请填写审核人");
  if (!form.reviewed_at) errors.push("请填写审核时间");
  if (!form.authorization_basis) errors.push("请填写授权依据 / 审核意见");
  if (form.authorization_decision === "approved_for_feedback_intake") {
    checks.forEach((key) => { if (!form.checks[key]) errors.push(`未完成：${key}`); });
    if (!["pass", "pass_with_conditions"].includes(form.qc_decision)) errors.push("授权必须有 QC pass");
    if (form.qc_decision === "pass_with_conditions" && !form.conditions) errors.push("条件 QC 必须填写条件");
    if (form.residual_risks) errors.push("授权通过时剩余风险必须为空");
    if (!form.activity_head && !form.stability_head) errors.push("至少选择一个训练 head");
  }
  if (row.qc_context?.conflicting_property_signal && form.authorization_decision === "approved_for_feedback_intake" && !form.authorization_basis.includes("tradeoff")) {
    errors.push("E331Q 授权意见需明确写出 tradeoff");
  }
  return errors;
}
function buildAuthorization(row, form) {
  const heads = [];
  if (form.activity_head) heads.push("activity_risk_head");
  if (form.stability_head) heads.push("stability_head");
  const conditions = form.conditions.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  const risks = form.residual_risks.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  return {
    authorization_id: row.authorization_template_id,
    feedback_candidate_id: row.feedback_candidate_id,
    authorization_decision: form.authorization_decision,
    approved_training_heads: heads,
    approved_data_granularity: "numeric_relative_to_control_measurement",
    qc_decision: form.qc_decision,
    source_trace_reviewed: Boolean(form.checks.source_trace_reviewed),
    numbering_reviewed: Boolean(form.checks.numbering_reviewed),
    unit_condition_reviewed: Boolean(form.checks.unit_condition_reviewed),
    batch_control_reviewed: Boolean(form.checks.batch_control_reviewed),
    replicate_policy_reviewed: Boolean(form.checks.replicate_policy_reviewed),
    allow_append_to_experiment_feedback_local: false,
    reviewer: form.reviewer,
    reviewed_at: isoFromLocal(form.reviewed_at),
    authorization_basis: form.authorization_basis,
    conditions,
    residual_risks: risks,
    candidate_summary: {
      source_project: row.source_project,
      variant: row.variant,
      mutation_set: row.mutation_set,
      assay_type: row.assay_type,
      metric_name: row.metric_name,
      raw_value_numeric: row.raw_value_numeric,
      vs_control_ratio: row.vs_control_ratio,
      batch_id: row.batch_id,
      sample_id: row.sample_id,
      source_file: row.source_file,
      source_row_index: row.source_row_index,
    },
    policy: "Human-reviewed authorization only; not a training label and does not directly append experiment_feedback.local.jsonl.",
  };
}
async function runStep(step) {
  try {
    const result = await api("/api/run-wet-lab-step", { step });
    qs("output").textContent = JSON.stringify(result, null, 2);
    qs("validationBox").className = "validation ok";
    qs("validationBox").textContent = `${step} 已完成。`;
    await loadData();
  } catch (error) {
    qs("validationBox").className = "validation error";
    qs("validationBox").textContent = error.message;
    qs("output").textContent = error.stack || error.message;
  }
}
async function saveAuthorization() {
  const row = currentRow();
  if (!row) return;
  const form = captureForm();
  const errors = validateForm(row, form);
  if (errors.length) {
    qs("validationBox").className = "validation error";
    qs("validationBox").textContent = errors.join("\n");
    return;
  }
  try {
    const result = await api("/api/save-wet-lab-authorization", { authorization: buildAuthorization(row, form) });
    qs("validationBox").className = "validation ok";
    qs("validationBox").textContent = "已保存人工授权 decision；下一步必须运行授权验证。";
    qs("output").textContent = JSON.stringify(result, null, 2);
    await loadData();
  } catch (error) {
    qs("validationBox").className = "validation error";
    qs("validationBox").textContent = error.message;
  }
}
async function loadData() {
  const data = await api("/api/wet-lab/status");
  state.rows = sortRows(data.rows || []);
  if (!state.selectedId || !state.rows.some((row) => row.feedback_candidate_id === state.selectedId)) {
    state.selectedId = state.rows[0]?.feedback_candidate_id || null;
  }
  renderQueue();
  const row = currentRow();
  renderDetail(row);
  renderForm(row);
}
function renderAll() {
  renderQueue();
  const row = currentRow();
  renderDetail(row);
  renderForm(row);
}
["searchInput", "variantFilter", "statusFilter"].forEach((id) => qs(id).addEventListener("input", renderQueue));
document.querySelectorAll("[data-check]").forEach((box) => box.addEventListener("change", captureForm));
["decision", "qcDecision", "reviewer", "reviewedAt", "basis", "conditions", "risks", "activityHead", "stabilityHead"].forEach((id) => {
  qs(id).addEventListener("input", captureForm);
  qs(id).addEventListener("change", captureForm);
});
qs("refreshBtn").addEventListener("click", loadData);
qs("saveBtn").addEventListener("click", saveAuthorization);
qs("validateBtn").addEventListener("click", () => runStep("validate_wet_lab_authorizations"));
qs("preflightBtn").addEventListener("click", () => runStep("build_wet_lab_preflight"));
qs("applyPlanBtn").addEventListener("click", () => runStep("build_wet_lab_apply_plan"));
restore();
loadData().catch((error) => {
  qs("validationBox").className = "validation error";
  qs("validationBox").textContent = `无法读取平台服务：${error.message}`;
});

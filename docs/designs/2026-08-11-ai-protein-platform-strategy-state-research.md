# AI Protein Platform Strategy/State Research

## Purpose

This note records research for improving the enzyme/protein AI platform around four product requirements:

- Strategy output must be rich enough for real R&D decisions.
- Once a strategy is confirmed, execution must follow that exact strategy and parameters.
- Dry-lab predictions must improve toward wet-lab reliability through calibration and feedback, not claims.
- The assistant must distinguish continuation of the same project from a new task or explicit rerun.

## External Platform Patterns

| Platform class | Examples | What they do well | What to borrow |
|---|---|---|---|
| Conversational wet/dry-loop agent | MatwingsVenus | Natural-language task decomposition, preflight, staged tool execution, wet-lab service and expert support | Conversation should maintain task stage, next action, artifacts, and explicit rerun vs continue semantics |
| Protein engineering SaaS | Cradle, OpenProtein.AI | Project/round/dataset/job structure; lab data upload; custom models; plate/library design | Store project state and strategy checkpoints as structured objects, not Markdown only |
| Generative biology platforms | Generate:Biomedicines/Chroma, Absci, Profluent, MoleculeMind, BioMap | Foundation models plus wet-lab validation, multi-property optimization | Treat activity/stability/expression/developability as trade-offs with constraints and evidence levels |
| Industrial enzyme DBTL platforms | Arzeda | Design-to-commercialization constraints, application-relevant assays, manufacturability | Industrial enzyme strategy must include substrate, assay, process conditions, expression and scale-up constraints |
| Model/workflow platforms | NVIDIA BioNeMo, ESM/Forge, PaddleHelix, AlphaFold Server, RFdiffusion/ProteinMPNN | Model APIs, workflow blueprints, job status, downloadable artifacts, confidence metrics | Strict job/run state and artifact provenance are required for truthful execution |

## Detailed Evidence From Platform Research

### Cradle

Cradle is the clearest public example of productizing ML-guided protein engineering rounds.

Relevant mechanisms:

- A round starts with protein type, whether experimental data exists, and the intended operation.
- The platform guides data preparation, model training, sequence generation, sequence evaluation, and lab candidate selection.
- It emphasizes traceability: users can see which trained model produced which candidates.
- Its platform page says users can upload wet-lab data, the system analyzes data quality and learnability, and every uploaded lab result improves the platform's understanding of the protein.
- Its wet lab page is explicit that real experiments drive reliable results, and that model iterations are A/B tested against previous models across assays/properties.

Product implication:

- The platform should not pretend zero-shot predictions are wet-lab accurate.
- The platform should show whether a strategy is zero-shot, project-calibrated, or experimentally supported.
- The platform should make each optimization round reproducible: dataset version, model version, generated candidates, selected plate/library, measured results.

### OpenProtein.AI

OpenProtein exposes the cleanest public data/job primitives.

Relevant mechanisms:

- Assay datasets are first-class objects containing sequences and measurements.
- Jobs are asynchronous objects with ID, type, status, creation/start/end dates, prerequisite job ID, progress messages, counters and failure messages.
- Common workflows distinguish zero-shot prediction, custom predictor training from assay data, and structure prediction.
- Web tools are described as standalone but composable at any point in a project.

Product implication:

- This platform needs persistent `project -> assay_dataset -> model/job -> design/run` links.
- Long-running analysis must return task/job IDs and status instead of blocking or regenerating hidden plans.
- Continuation questions should bind to current project objects and latest completed jobs, not just natural-language history.

### MatwingsVenus

MatwingsVenus is the most relevant UX reference because it is conversational.

Relevant mechanisms:

- Official manual describes conversational protein engineering with multi-agent collaboration, big biological data, AI prediction models, wet-lab delivery, and expert support.
- Its FAQ states more accurate results require PDB structure, experimental throughput, and wet-lab data in engineering tasks.
- Official product pages describe directed evolution, single-point saturation prediction, multi-point mutation prediction using user wet-lab data, functional site risk analysis and physicochemical prediction.
- Local stream-events confirm staged execution: preflight -> user confirmation -> formal tool call -> next-stage confirmation -> artifact handoff.

Product implication:

- We should borrow staged checkpoints, confirmation semantics, artifact handoff and wet-lab data escalation.
- We should not borrow overconfident wording such as unqualified high success percentages.

### NVIDIA BioNeMo

BioNeMo is mainly infrastructure/reference workflow rather than a full R&D project manager.

Relevant mechanisms:

- BioNeMo Framework is an ecosystem for building, training, fine-tuning and deploying biomolecular AI models.
- BioNeMo Blueprints combine model microservices into workflows such as binder design with AlphaFold2, RFdiffusion and ProteinMPNN.
- Release notes and model docs include model availability, known issues, validation status and security/accuracy caveats.

Product implication:

- Model/workflow capability should be represented with capability status, runtime status, model version and known caveats.
- A workflow should be explicit about each model's responsibility; for example, DiffDock confidence is not binding affinity, AlphaFold confidence is not wet-lab function.

### BioMap / xTrimo

BioMap/xTrimoPGLM is primarily a foundation-model capability reference.

Relevant mechanisms:

- xTrimoPGLM provides large-scale protein language models for both understanding and design.
- Public materials emphasize benchmark/task performance and generated sequence evaluation.
- WEF description of BioMap highlights real-world data and internally generated high-throughput wet-lab data for therapeutic target and biologics design.

Product implication:

- Large model scale is useful but insufficient by itself.
- The platform needs target-specific assay data and high-throughput feedback to improve practical design accuracy.

### MoleculeMind / MoleculeOS

MoleculeMind publicly describes a one-stop protein design platform with de novo protein, enzyme and antibody design workflows.

Relevant mechanisms:

- It emphasizes multi-objective protein design and specific workflows for enzyme activity/selectivity, thermostability and expression optimization.
- Public pages present wet-lab tested examples but with some data withheld for confidentiality.
- External Chinese coverage emphasizes workflow packaging and conversational AI Agent access to industrial enzyme and drug-design workflows.

Product implication:

- Our strategy object should include multiple objective-specific modules, not one generic enzyme flow.
- Report confidence should distinguish public case examples from user/project-specific evidence.

## Accuracy Lessons

Dry-lab predictions become more reliable only when the platform can learn from measured outcomes. The useful public pattern is:

1. Upload or ingest measured sequence-property data.
2. Assess data quality and learnability.
3. Train or calibrate project-specific predictors.
4. Generate candidates under explicit objectives and constraints.
5. Design plates/libraries that balance exploitation and exploration.
6. Run wet experiments and feed results back into the next round.

Implication for this platform:

- A zero-shot recommendation is an exploratory hypothesis.
- A recommendation calibrated by project wet-lab data can be upgraded.
- A recommendation supported by direct wet-lab data can be marked experimental-supported.
- The report must never blur those three states.

## Strategy Richness Standard

A strategy checkpoint should contain:

- `task_identity`: normalized sequence fingerprint, structure object, protein name/ID, project ID, round ID.
- `objectives`: primary goal, secondary goals, preserved properties, trade-offs.
- `assays`: current and required wet-lab measures.
- `evidence_state`: experimental support, project data, literature, structure/numbering, live/degraded/blocked tool evidence.
- `constraints`: active-site lock, cofactor/metal/disulfide lock, blocked mutations, allowed regions, user constraints.
- `execution_plan`: ordered steps, tools, params, input artifact, expected output artifact, timeout/cost/risk.
- `candidate_policy`: P1/P2/P3 rules, exploration/deepening ratio, combination criteria.
- `success_criteria`: Go/Watch/No-Go thresholds and promotion rules.

## State Machine Requirement

The platform needs an active checkpoint state machine:

```text
draft_strategy
  -> awaiting_confirmation
  -> executing
  -> completed
  -> awaiting_next_stage | awaiting_feedback
  -> superseded | restarted
```

User input classification should happen before route/plan:

| Input class | Examples | Required action |
|---|---|---|
| `confirm_current_strategy` | 确认执行、是、开始吧、按上面来 | Execute the active awaiting checkpoint only |
| `continue_current_project` | 继续、上面、这个酶、这些数据、下一轮 | Reuse current project state, artifacts and feedback |
| `revise_strategy` | 修改策略、先不要跑某工具、增加文献 | Create a new revision under same task fingerprint |
| `explicit_restart` | 重新执行、重跑、从头、全部重来 | Create a rerun checkpoint and say it is a full rerun |
| `new_task` | 新序列、另一个酶、换一个结构/项目 | Create a new task boundary and do not inherit old artifacts |

## Current Platform Gap

The current frontend stores `agentState.plan`, but does not send it back as a confirmed plan payload. The backend receives `agent_control=execute_confirmed`, strips the `[用户确认]` marker, then still routes and plans again.

That means the UI promises "execute the above strategy", while backend execution is actually "regenerate a plan that is usually similar". This must be fixed before claiming strict strategy execution.

## Minimum Safe Repair Direction

Short term:

- Include `confirmed_plan`, `strategy_signature`, and `planned_task_fingerprint` in the confirm request.
- Backend recomputes/validates signature and executes that plan directly.
- If missing or mismatched, return a fail-closed message asking for strategy regeneration.
- Add tests proving `_plan_cb` is not called in confirmed execution when a valid confirmed plan exists.

Medium term:

- Persist active strategy checkpoint in the database, ideally linked to conversation/project/user.
- Store plan steps, params, strategy signature, task fingerprint, status, next action, and artifacts.
- Use checkpoint state for continuation vs restart classification.

Long term:

- Promote wet-lab feedback into a project-level calibration dataset.
- Track prediction accuracy by objective, protein family, assay and round.
- Only label predictions `wet_lab_calibrated` when enough project/family data and validation criteria exist.

## Non-Negotiable Truthfulness Rules

- Do not call exploratory dry-lab output wet-lab validated.
- Do not claim exact fold improvement without evidence.
- Do not claim live database search unless a live tool executed successfully.
- Do not output structure-distance conclusions without numbering/structure mapping.
- Do not say "strictly executed confirmed strategy" unless the executed plan was the confirmed checkpoint.

## Primary Sources Reviewed

- MatwingsVenus user manual and official site/news.
- Local MatVenus stream-events and reviews in `matvenus-research/`.
- Cradle platform, wet lab, Guided Rounds, and variant-selection materials.
- OpenProtein.AI docs for project/data/job/property regression workflows.
- NVIDIA BioNeMo overview, model docs, and protein binder blueprint materials.
- EvolutionaryScale ESM3/Forge official materials.
- PaddleHelix/HelixFold3/HelixDesign official pages and docs.

Reference URLs used in this pass:

- https://matvenus.com/zh/manual
- https://matvenus.com/en
- https://matvenus.com/en/news/matwingsvenusai
- https://www.cradle.bio/platform
- https://www.cradle.bio/lab
- https://docs.openprotein.ai/
- https://docs.openprotein.ai/rest-api/authentication-and-jobs.html
- https://generatebiomedicines.com/platform/
- https://www.arzeda.com/technology/
- https://docs.nvidia.com/bionemo-framework/latest/
- https://www.evolutionaryscale.ai/blog/esm3-release
- https://deepmind.google/science/alphafold/
- https://github.com/PaddlePaddle/PaddleHelix
- https://github.com/dptech-corp/Uni-Fold
- https://drug.ai.tencent.com/introduction_cn/
- https://healthcare.tencent.com/production/74

## Second-Pass Platform Research, 2026-08-11

This second pass separates "what to borrow" from "what not to overclaim".

### Highest-value mechanisms by platform

| Platform | Mechanism observed | Product lesson for this platform |
|---|---|---|
| MatwingsVenus | `preflight_only=true` before costly stages; user confirmation flips only that stage to formal execution; AlphaFold2 output is passed to VenusREM as `structure_file`; explicit "重新执行任务" is treated as full rerun | Implement checkpointed stage execution with `next_action` and artifact handoff. Do not classify continuation by text similarity alone |
| Cradle | Guided Rounds structure a campaign from raw data to lab-ready candidates; rounds preserve trained model, dataset, candidate and decision traceability; uploaded lab results improve project-specific models | Strategy must become a round object with dataset/model/candidate provenance, not a chat paragraph |
| OpenProtein.AI | Assay datasets and asynchronous jobs are first-class API objects; jobs expose ID, status, progress, prerequisite, failure message and result retrieval | Long tools and confirmed execution should produce durable run/job records; follow-up questions should bind to job IDs and assay datasets |
| Generate:Biomedicines | Continuous generate-build-measure-learn loop; generated sequences are made as real proteins and measured | Accuracy improvement must be framed as DBTL learning from measured outputs, not as a dry-lab guarantee |
| Absci | Data to train, AI to create, wet lab to validate; emphasizes high-throughput wet-lab validation and iterative cycles | Prediction confidence upgrades require real assay feedback and high-throughput validation metadata |
| Arzeda | Closed-loop DBTL with 15+ years of structured design/assay data; application-relevant conditions, manufacturability and scale-up are design constraints | Industrial enzyme strategy must include expression host, process pH/temperature, formulation, scale-up and assay conditions from the start |
| EvolutionaryScale ESM3 | Multimodal sequence/structure/function generative model; laboratory feedback or existing experimental data can align generations with biological success | Use large foundation models as proposal engines; upgrade confidence only after project/family feedback and claim gates |
| NVIDIA BioNeMo | Model/workflow framework with release notes, known issues, model/version/provenance boundaries | Every model/tool in reports needs capability status, runtime status, model version and known caveats |
| AlphaFold / AlphaFold Server | Output is structured as ranked mmCIF plus confidence JSON; pLDDT/PAE/ipTM have explicit interpretation limits | Structure prediction confidence is not activity confidence. Residue-level design must cite structure/numbering confidence separately |
| PaddleHelix / HelixFold3 | Bio-computing platform and server/API around structure prediction, docking and foundation models; clear job-like online service boundary | Good reference for packaging models into serviceable jobs, but it does not replace project strategy state |
| Tencent iDrug | AI drug discovery modules expose task submission, history, status, downloads; disclaimer states outputs are computational references and models are still iterating | Keep a visible truth boundary: computation result, not experimental fact; job lifecycle and result download are product basics |
| DP Technology / Uni-Fold / Uni-Dock / Uni-Mol | Open tools focus on reproducible model/runtime artifacts for folding, docking and molecular representation | Borrow artifact contracts and reproducible runtime manifests, not marketing confidence |
| BioMap / xTrimoPGLM | 100B-scale protein language model family for understanding/design; open weights include resource/licensing constraints | Large model scale helps but does not solve project-specific wet-lab accuracy without assay feedback |
| MoleculeMind / MoleculeOS | One-stop protein design workflow including antibody, enzyme activity/selectivity, thermostability and expression optimization; public cases often with data withheld | Borrow objective modules and workflow packaging, but report confidence must distinguish public case evidence from our user/project evidence |

### Best-available architecture for this platform

The optimal repair is not a single "same question" classifier. It is a stateful protein-engineering operating model:

1. `ProjectState`
   - `project_id`, `conversation_id`, owner/ACL, current protein identity, sequence fingerprint, structure artifacts, assay context, wet-lab feedback datasets, current round.
   - This is the boundary for "same project" versus "new task".

2. `StrategyCheckpoint`
   - `checkpoint_id`, `conversation_id`, `project_id`, `task_fingerprint`, `strategy_signature`, `revision`, `status`, `next_action`.
   - Structured fields: objectives, constraints, assays, evidence_state, execution_plan, candidate_policy, success_criteria, artifacts.
   - Status transitions: `draft -> awaiting_confirmation -> executing -> completed -> awaiting_next_stage | awaiting_feedback`, with `superseded` and `restarted` as explicit branches.

3. `Run/Job`
   - Every confirmed execution creates one or more run records with tool name, params, input artifacts, runtime status, timeout policy, model/runtime version, output artifacts and failure class.
   - Confirmed execution consumes the checkpoint execution plan. It must not call the planner unless the checkpoint is missing, mismatched or explicitly revised.

4. `WetLabCalibration`
   - Stores assay dataset schema, measured sequence/variant values, plate/batch metadata, units, controls, noise/batch-effect notes, objective mapping and data-quality grade.
   - Candidate confidence can only move from `computational_hypothesis` to `wet_lab_calibrated` after enough relevant assay feedback exists.

5. `ClaimGate`
   - Blocks or downgrades statements that exceed evidence.
   - Required labels: `computational_hypothesis`, `wet_lab_calibrated`, `experimental_supported`, `blocked`.

### Non-hardcoded design requirement

The repair must not hardcode a Venus-style fixed pipeline, a fixed tool order, fixed keyword rules, fixed thresholds, fixed candidate counts, or a fixed "same question" decision table.

The code should implement a general state/checkpoint framework:

- Policies define objective modules, allowed tools, evidence gates, rerun semantics and confidence labels.
- Current project state defines sequence/structure/artifacts/assay/wet-lab context.
- Strategy generation creates an execution plan from policies plus current context.
- Confirmation execution consumes the exact checkpoint that was shown to the user.
- Continuation/restart decisions use `status`, `next_action`, `task_fingerprint`, `strategy_signature`, `artifacts` and explicit user intent.
- New protein classes or future tools should be added through policy/tool metadata, not by rewriting the core router.

### Short-term repair design

This is the minimum code-level repair needed before the UI can honestly say "strictly execute confirmed strategy":

1. Frontend sends the active plan back on confirmation:
   - Extend chat request with `confirmed_plan`, `strategy_signature`, `task_fingerprint`.
   - `ChatInput.tsx` already has `agentState.plan`; `useChatStream.ts` must include it in the request body only for `execute_confirmed`.

2. Backend validates the plan before execution:
   - Recompute signature from `confirmed_plan`.
   - Validate control is `execute_confirmed`, plan is non-empty, signature matches, and current task fingerprint matches or is explicitly a continuation.
   - If validation fails, fail closed with a clear message: strategy checkpoint missing or changed; regenerate and confirm again.

3. Backend executes the confirmed plan directly:
   - Convert `confirmed_plan` to `PlanStep`.
   - Skip `_route_intent`, `_research_pi`, and `_plan_cb` for valid `execute_confirmed`.
   - Preserve the existing execution, review and synthesis pipeline after the plan is loaded.

4. Tests first:
   - Valid confirmed plan does not call `_plan_cb`.
   - Missing/mismatched signature fails closed.
   - "确认执行/开始吧/是，执行" advances active checkpoint.
   - "继续/上面/这个酶/下一轮" reuses project state/artifacts.
   - "重新执行/重跑/从头" creates explicit rerun and is labeled as full rerun.

### Medium-term repair design

The frontend-payload approach fixes the immediate lie, but it is not enough for robust multi-session recovery. The medium-term implementation should persist checkpoints server-side:

- Add `strategy_checkpoints` table linked to user, conversation and project.
- Persist plan-only assistant state as structured checkpoint metadata, not just Markdown content.
- Add `strategy_runs` or reuse tool audit records with `checkpoint_id`.
- Add an input classifier that runs before routing and returns:
  - `confirm_current_strategy`
  - `continue_current_project`
  - `revise_strategy`
  - `explicit_restart`
  - `new_task`
- Store artifact links after each stage and expose `next_action` to the frontend.

### Long-term wet-lab accuracy design

To approach wet-lab reliability, the system needs a measurement loop:

- Require assay schema before high-confidence ranking: objective, unit, baseline WT, controls, replicate count, condition, batch.
- Track hit rate by project, family, objective and assay.
- Separate exploration candidates from exploitation candidates.
- Use project wet-lab data to recalibrate candidate priority and epistasis risk.
- Report the calibration basis in every candidate table: number of relevant measured variants, assay quality, family similarity, model/runtime used, and last validation date.

The system must still never say dry-lab equals wet-lab by default. The correct promise is: dry-lab output is progressively calibrated by wet-lab feedback until its historical hit rate in this project/family justifies stronger labels.

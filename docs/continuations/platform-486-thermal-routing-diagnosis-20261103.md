# 486 aa 热稳定性案例为何仍进入旧增活流程

结论：当前生产版本仍存在目标识别、条件抽取、聊天规划接入及工具注册冲突，不能将本案例归因为用户提供的数据不够，也不能用此前336 aa匿名理论模型验收替代。本轮仅只读诊断，没有修改代码、部署、确认执行、提交新BLAST或改写原报告。

## 实际请求与复现

生产会话1030，用户消息4208（2026-11-03 15:14北京时间），计划消息4209、执行消息4211。用户明确要求提高热稳定性：95℃处理5分钟，剩余酶活目前30%，希望60%以上；独立FASTA为486 aa，与上传PDB链A精确匹配。

只读重放当前规划器得到与用户反馈相同的12步顺序：

```text
structure_search_foldseek
residue_mapping_sifts
disulfide_saltbridge_scan
predict_properties
enzyme_identity_profile
enzyme_objective_module_plan
protein_benchmark
build_site_structure_function_features
mutation_priority_score
kcat_predict
mutation_scan
blast_search
```

附件治理路由返回false；故本次不是此前“模型质量”摘要误触发治理的问题。结构可读，序列来源为user_fasta_exact_pdb_match；结构未被解析器标记为理论模型、没有已验证外部参考绑定。热稳定性候选工具已注册，但没有被主聊天计划选中。

## 已证实的根因

1. **热处理残余酶活被当作独立增活目标。** `agent_graph.py:3172`仅排除“残余活性/热处理后活性”等若干说法，没有“剩余酶活”。随后“酶活”命中activity。最小复现：同一请求用“剩余酶活”得到activity+thermostability；替换为“残余活性”则只得到thermostability。无需上传任何结构也可复现。
2. **混合信号被硬编码优先activity。** `agent_graph.py:3191`在activity和thermostability并存时直接返回activity，不根据用户的热处理终点确定主目标。用户没有要求提高未热处理时比活力。
3. **自然语言实验条件没有进入结构化上下文。** 本案 `_extract_assay_context()`返回空字典。解析器主要记录少量固定格式的存在布尔值，不足以表达本案的95度、5min、当前30%、目标60%以上。用户已经给出了这些条件，不能在报告里把它们全部视作未提供。
4. **新候选工作流未接管普通聊天的确定性规划。** `_plan_cb()`明确调用 `_generate_fallback_plan()`；后者仍追加mutation_priority_score、kcat_predict、mutation_scan，并在它们之后追加BLAST。热稳定性YAML里已有thermostability_candidate_workflow，运行时有参数桥接、策略限制和报告支持，但普通聊天的确定性规划没有据此生成这一步。“工具接通”未闭合为“该输入自动走新流程”。属性路由另能识别为WF-STABILITY，但没有替换这段旧工具编排。
5. **此前身份收集修复条件过窄。** `agent_graph.py:6601`要求activity目标、结构被标为理论模型、无模板、无已验证参考。本案theoretical=false，条件为false。FASTA精确匹配仅能证明输入序列一致，不能证明家族/催化位点身份，但本案仍保留了候选与kcat步骤。不能简单归因于“多提供FASTA就跳过”：直接排除本案的是理论模型条件。
6. **二硫键工具同名重复注册导致参数合同不一致。** `disulfide_saltbridge_scan.py`接收pdb_object_name/chain_id；`stability_feature_scan.py:147`又注册同名工具且要求protein_pdb。`registry.py`按固定顺序先导入前者、后导入后者，并以字典赋值覆盖同名注册。实际执行错误正是 `missing required parameters: ['protein_pdb']. Provided: ['pdb_object_name', 'chain_id']`。这是工具接口冲突，不是结构文件缺失。

## 已保存的真实执行结果

- 结构解析、编号映射、理化性质、结构特征完成。
- 二硫键/盐桥扫描failed，原因为上述参数不一致。
- identity_profile为unresolved；objective_module和protein_benchmark被门控拦截。
- mutation_priority_score与mutation_scan均blocked，code=DEPENDENCY_REQUIRED，不能说它们已完成可信候选打分。
- kcat_predict实际执行且completed，但is_real_inference=false，方法为序列/底物复杂度代理的启发式统计估算；没有帮助回答95℃残余活性目标。
- BLAST最后submitted。本轮诊断没有新增、取消或改动该任务，保留用户原任务。

## 修复应覆盖的范围

统一“目标语义—测定条件—主目标—工具依赖”链路：将本案识别为residual_activity终点，保留95℃/300秒、WT基线0.30、目标至少0.60；身份/编号及保护证据先行，异步检索不被当作已完成证据；条件不足时输出明确阶段结果。热稳定性候选分支应明确调用新复合工作流，按需启用DDGun/ESM/数据库/MSA分支。已有结构不必强制ColabFold，无合格MSA不必强制共进化。

候选排序仍须遵守真实证据门，不应以更换工具名或取消门控解决。修复二硫键工具需消除重复注册并覆盖新进程、不同导入顺序和真实上传对象参数，不能只直接调用某个模块函数作为通过证据。

此前1792项及336 aa场景验收在当时范围内通过，但遗漏了本案的残余酶活同义表述、普通PDB+FASTA、自然条件解析、普通聊天选入新工作流，以及新进程注册合同。这是验收覆盖缺口；“已按反馈改造”不能扩大为全部用户路径均已走通。

脱敏执行诊断回执保存在本地忽略目录 `output/thermal-routing-486-diagnosis-20261103/execution.json`。原序列、附件和登录凭据不进入本记录。

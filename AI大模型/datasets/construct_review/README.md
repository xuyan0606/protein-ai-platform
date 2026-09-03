# 构建体序列与编号复核导入模板

该目录用于人工补录文献候选的 construct 序列、成熟链边界和突变编号。

## 使用规则

- 空模板不构成复核结论。
- `numbering_verified`、`condition_comparable`、`authorization_received` 必须由人工确认。
- 缺少 FASTA/accession、编号方案、复核人或回执时，记录保持 blocked。
- 本模板不会自动把候选提升为训练标签。

## 必填字段

`measurement_id`、`construct_accession` 或 `construct_fasta`、`parent_accession`、`mutation_notation`、`numbering_scheme`、`numbering_verified`、`reviewer`、`reviewed_at`、`authorization_received`。

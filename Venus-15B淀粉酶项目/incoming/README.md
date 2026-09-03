# Venus-15B Incoming Assets

把后续真实文件按下面目录放进来，然后执行：

```bash
cd /Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台
python3 scripts/sync_benchmark_case.py --case-id venus-15b --rebuild-foldseek
```

如果想先扫描本机里已有的候选文件，再决定哪些要接进来，先执行：

```bash
cd /Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台
python3 scripts/discover_benchmark_assets.py --case-id venus-15b --search-root /Users/xuyan/科为博
```

发现清单会写到：

- `incoming/discovery/asset_inventory.json`

如果想让系统自动挑选一批最相关的参考文档，执行：

```bash
cd /Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台
python3 scripts/select_benchmark_reference_docs.py --case-id venus-15b
```

自动选择结果会写到：

- `incoming/reference_docs/selected_manifest.json`
- `incoming/reference_docs/auto_selected/`

目录约定：

- `incoming/alphafold/`
  - 放 `AlphaFold` 结构文件，例如 `*.cif`、`*.pdb`
  - 可同时放 `PAE` 或元数据 `*.json`
- `incoming/sifts/`
  - 放真实或自定义位点映射文件，例如 `*.json`、`*.xml`、`*.tsv`
- `incoming/annotations/`
  - 放案例专属注释文件，例如 `*.json`、`*.csv`、`*.tsv`
- `incoming/reference_docs/`
  - 放希望随案例一起打包迁移的参考文档，例如 `*.pdf`、`*.docx`、`*.md`

同步后会进入：

- `deploy_data/alphafold/local_cases/venus-15b/`
- `deploy_data/sifts/local_cases/venus-15b/`
- `deploy_data/annotations/local_cases/venus-15b/`
- `deploy_data/benchmarks/venus-15b/`

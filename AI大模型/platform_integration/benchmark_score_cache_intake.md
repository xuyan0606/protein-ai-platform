# Benchmark Score Cache Intake

P68 creates a local intake path for ProteinGym-style benchmark scorecards and
other external benchmark artifacts.

## Files

- Template: `datasets/benchmark/benchmark_score_cache_intake.template.jsonl`
- Local intake: `datasets/benchmark/benchmark_score_cache_intake.local.jsonl`
- Manifest: `reports/benchmark_score_cache_manifest.json`
- Intake report: `reports/benchmark_score_cache_intake_report.json`
- Validation report: `reports/benchmark_score_cache_validation_report.json`

## Required Artifacts

Each benchmark row must provide:

- local dataset file and sha256
- split definition and sha256
- scorecard and sha256
- metric report and sha256
- dataset version
- license review status
- leakage check status
- reviewer and review timestamp

## Policy

Benchmark data is an evaluation gate. It must not be used as KWB wet-lab labels,
training approval, customer delivery approval or model-quality claim by itself.

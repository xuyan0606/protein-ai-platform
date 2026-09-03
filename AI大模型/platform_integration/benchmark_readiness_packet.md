# Benchmark Readiness Packet

This lane owns a local, fail-closed execution contract for the current benchmark
coverage gaps. It is separate from the benchmark score-cache intake and does not
open any model, training, release, or production gate.

## Files

- Packet: `datasets/governance/benchmark_readiness_packets.jsonl`
- Packet schema: `contracts/benchmark_readiness_packet.schema.json`
- Builder: `scripts/build_benchmark_readiness_packet.py`
- Validator: `scripts/validate_benchmark_readiness_packet.py`
- Build report: `reports/benchmark_readiness_packet_report.json`
- Validation report: `reports/benchmark_readiness_packet_validation_report.json`

## Receipt Order

Each invalid benchmark gap has three receipts:

1. `acquisition_receipt`: identify an authorized local source or an internal
   local-only contract. The packet never authorizes or performs a download.
2. `score_receipt`: register real dataset, split, scorecard, and metric
   artifacts with SHA-256 values after license and leakage gates pass. Score
   values are intentionally absent from the packet.
3. `validation_receipt`: rerun the existing score-cache and coverage validators,
   then regenerate this packet against the new source snapshot.

`local_contract_only` means no external download is required for the contract
itself. It does not mean the benchmark is ready or accepted.

The current authoritative set is the matrix plus coverage/gap queue plus score
cache validation. The older `datasets/benchmark/five_head_benchmark_gap_actions.jsonl`
summary undercounts the `mutation_rank` invalid set by one; the packet records
that discrepancy and keeps all 14 invalid rows blocked.

## Commands

```bash
python3 scripts/build_benchmark_readiness_packet.py
python3 scripts/validate_benchmark_readiness_packet.py
python3 scripts/validate_benchmark_readiness_packet.py --require-ready
```

The second command validates that the blocked packet is internally consistent.
The third command is expected to return non-zero while any of the 14 gaps
remains unresolved.

## Forbidden Effects

Packet generation and validation do not:

- download benchmark data;
- write `datasets/benchmark/benchmark_score_cache_intake.local.jsonl`;
- update `reports/benchmark_score_cache_manifest.json`;
- create or alter benchmark scores;
- modify training labels;
- open model claims or release flags.

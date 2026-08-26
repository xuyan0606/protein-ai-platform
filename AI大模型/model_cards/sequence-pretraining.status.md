# Sequence Pretraining Status

Local-only pretraining asset. This is not a release model card or a biological-performance claim.

## Asset

- Task: masked amino-acid self-supervised pretraining
- Unlabeled unique sequences: 12,830
- Completed batches: 26
- Current embedding baseline: continuous_full_v2 (single checkpoint across all 12,830 sequences)
- Validation objective: masked-token input and masked-position cross-entropy (v2 corrected)
- Embedding dimension: 32
- Checkpoint integrity: 26/26 SHA-256 verified

## Verified scope

- Training receipts and checkpoint hashes are present.
- Full embedding index contains 12,830 records.
- Index validation and collision audit pass with zero collisions.
- Repeated index construction is deterministic after timestamp normalization.

## Prohibited claims and uses

- No claim of mutation-effect, activity, stability, affinity, substrate-fit, or assay-success prediction.
- No supervised fine-tuning, customer delivery, ordering decision, wet-lab guarantee, or production inference.
- Cosine similarity is representation-space proximity only, not biological equivalence.

## Release decision

`blocked_pretraining_only`: `safe_for_supervised_training=false`, `safe_for_model_claim=false`, and production release is prohibited until independently labeled data, evaluation evidence, authorization, and release receipts satisfy their respective gates.

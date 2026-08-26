# Sequence Pretraining Status

Local-only pretraining asset. This is not a release model card or a biological-performance claim.

## Asset

- Task: masked amino-acid self-supervised pretraining
- Unlabeled unique sequences: 12,830
- Completed batches: 26
- Current embedding baseline: continuous_full_v4 (3 epochs across all 12,830 sequences)
- Validation objective: masked-token input and masked-position cross-entropy (v2 corrected)
- Validation split: source-group holdout with zero train/validation source overlap (v3 corrected)
- Independent MLM evaluation: 5 mask repeats, mean loss 2.902550, perplexity 18.2206, masked-token accuracy 9.8025%
- Uniform amino-acid reference: loss 2.995732 and expected accuracy 5%; this is a reconstruction baseline, not a biological benchmark
- Random-initialization control on the same masks: loss 3.177272, accuracy 5.3821%; trained-minus-random loss reduction 0.274722 and accuracy gain 4.4204 percentage points
- Compared with v3, v4 improves mean loss by 0.003066 and accuracy by 0.1367 percentage points; the gain is consistent across 5/5 mask repeats but remains small
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

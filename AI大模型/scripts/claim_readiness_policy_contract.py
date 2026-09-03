"""Shared claim-readiness policy contract consumed by builders and validators."""

from __future__ import annotations

import hashlib
import json
from typing import Any


POLICY_VERSION = "claim-readiness-policy-v1"

MUST_ALLOW_INTERNAL_CLAIM_IDS = frozenset({
    "internal_design_review_artifacts",
})

CONDITIONAL_INTERNAL_CLAIM_IDS = frozenset({
    "local_safe_training_pipeline",
})

BLOCKED_CLAIM_IDS = frozenset({
    "active_learning_experiment_submission",
    "approved_for_ordering",
    "biosecurity_screened",
    "customer_sequence_package",
    "external_tool_production_use",
    "five_head_training_run",
    "ip_fto_cleared",
    "local_release_review_package",
    "model_quality_claim",
})

INTERNAL_CLAIM_IDS = MUST_ALLOW_INTERNAL_CLAIM_IDS | CONDITIONAL_INTERNAL_CLAIM_IDS
CANONICAL_CLAIM_IDS = INTERNAL_CLAIM_IDS | BLOCKED_CLAIM_IDS


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_policy_payload() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "canonical_claim_ids": sorted(CANONICAL_CLAIM_IDS),
        "must_allow_internal_claim_ids": sorted(MUST_ALLOW_INTERNAL_CLAIM_IDS),
        "conditional_internal_claim_ids": sorted(CONDITIONAL_INTERNAL_CLAIM_IDS),
        "blocked_claim_ids": sorted(BLOCKED_CLAIM_IDS),
    }


def test_vector_payload() -> dict[str, Any]:
    return {
        "policy": canonical_policy_payload(),
        "probe": {
            "allowed_claim_ids": ["internal_design_review_artifacts"],
            "blocked_claim_ids": sorted(CANONICAL_CLAIM_IDS - {"internal_design_review_artifacts"}),
            "all_claims_ready": False,
            "promotion_policy_allows_all_claims": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
    }


def canonical_policy_sha256() -> str:
    return canonical_sha256(canonical_policy_payload())


def test_vector_sha256() -> str:
    return canonical_sha256(test_vector_payload())

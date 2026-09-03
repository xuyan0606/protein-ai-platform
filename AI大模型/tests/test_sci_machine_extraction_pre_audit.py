import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sci_machine_extraction_pre_audit",
    ROOT / "scripts" / "pre_audit_sci_machine_extraction.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_empty_cells_are_insufficient_evidence():
    result = MODULE.audit_row({"pmcid": "PMC1", "table_locator": "T1", "cells": ["", ""]})
    assert result["pre_audit_status"] == "insufficient_evidence"
    assert "empty_cells" in result["risk_flags"]


def test_numeric_construct_row_is_candidate_for_human_verification():
    result = MODULE.audit_row(
        {
            "pmcid": "PMC1",
            "table_locator": "T1",
            "cells": ["E42A", "kcat", "12.4", "s^-1"],
        }
    )
    assert result["pre_audit_status"] == "precheck_candidate"
    assert result["human_verification_required"] is True
    assert result["evidence_signals"] == ["construct_or_variant", "measurement_term", "numeric_value", "unit"]


def test_non_measurement_row_needs_human_verification():
    result = MODULE.audit_row(
        {"pmcid": "PMC1", "table_locator": "T1", "cells": ["wild type", "active", "yes"]}
    )
    assert result["pre_audit_status"] == "needs_human_verification"
    assert result["human_verification_required"] is True

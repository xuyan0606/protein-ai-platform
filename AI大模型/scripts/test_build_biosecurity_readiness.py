import json

from build_biosecurity_readiness import order_artifact_reasons, suspicious_order_artifacts


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_execution_order_and_codon_audits_are_not_order_payloads(tmp_path):
    write_json(tmp_path / "release_guard_order_validation_report.json", {"success": True})
    write_json(tmp_path / "codon262_sequence_quality_audit.json", {"ready_for_ordering": False})
    assert suspicious_order_artifacts([tmp_path]) == []


def test_true_order_payload_is_detected(tmp_path):
    path = write_json(
        tmp_path / "dna_order.json",
        {"ready_for_ordering": True, "dna_sequence": "ATGC", "order_items": [{"quantity": 1}]},
    )
    reasons = order_artifact_reasons(path)
    assert any(reason.startswith("ordering_approval_true:") for reason in reasons)
    assert any(reason.startswith("order_payload_present:") for reason in reasons)
    assert any(reason.startswith("ordering_nucleotide_payload_present:") for reason in reasons)


def test_approval_flag_is_detected_even_with_neutral_filename(tmp_path):
    path = write_json(tmp_path / "candidate.json", {"approved_for_synthesis": True})
    assert order_artifact_reasons(path) == ["ordering_approval_true:approved_for_synthesis"]


def test_unparseable_explicit_order_file_fails_closed(tmp_path):
    path = tmp_path / "synthesis_order.json"
    path.write_text("{", encoding="utf-8")
    assert order_artifact_reasons(path) == ["explicit_order_artifact_unparseable"]

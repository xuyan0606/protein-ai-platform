import json

from build_domain_unresolved_packet import build_packet


def test_packet_contains_only_unresolved_rows_and_blocks_training(tmp_path):
    curated = tmp_path / "curated.jsonl"
    evidence = tmp_path / "evidence.jsonl"
    curated.write_text("\n".join(json.dumps(x) for x in [
        {"domain_record_id": 1, "curation_status": "domain_interval_curated", "usable_for_position_features": True},
        {"domain_record_id": 2, "curation_status": "domain_interval_unresolved", "usable_for_position_features": False},
    ]) + "\n")
    evidence.write_text(json.dumps({"domain_record_id": 2, "uniprot_id": "Q2", "pfam_id": "PF1", "other_pfam_ids": ["PF2"]}) + "\n")
    result = build_packet(curated, evidence)
    assert len(result["rows"]) == 1
    assert result["rows"][0]["domain_record_id"] == 2
    assert result["rows"][0]["recommended_decision"] == "keep_unresolved"
    assert result["training_authorized"] is False

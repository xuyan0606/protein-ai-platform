from audit_general_enzyme_dataset import audit_rows


def test_same_sequence_mutants_are_grouped_together():
    rows = [
        {"record_id": "a", "sequence_hash": "wt1", "metric": "Tm", "split": "train", "license_status": "approved", "quality_flags": []},
        {"record_id": "b", "sequence_hash": "wt1", "metric": "mutation_effect", "split": "test", "license_status": "approved", "quality_flags": []},
    ]
    audit = audit_rows(rows)
    assert audit["training_import_allowed"] is False
    assert "sequence_group_cross_split" in audit["errors"]


def test_clean_research_rows_are_eligible():
    rows = [
        {"record_id": "a", "sequence_hash": "wt1", "metric": "Tm", "split": "train", "license_status": "approved", "quality_flags": [], "source_file_sha256": "a" * 64},
        {"record_id": "b", "sequence_hash": "wt2", "metric": "Tm", "split": "test", "license_status": "approved", "quality_flags": [], "source_file_sha256": "b" * 64},
    ]
    audit = audit_rows(rows)
    assert audit["training_import_allowed"] is True
    assert audit["status"] == "passed"


def test_license_block_is_reported():
    row = {"record_id": "a", "sequence_hash": "wt1", "metric": "Km", "split": "train", "license_status": "blocked_license", "quality_flags": [], "source_file_sha256": "a" * 64}
    audit = audit_rows([row])
    assert audit["training_import_allowed"] is False
    assert "license_blocked" in audit["errors"]


def test_empty_dataset_is_blocked():
    audit = audit_rows([])
    assert audit["status"] == "blocked_no_records"
    assert audit["training_import_allowed"] is False


def test_distinct_substrates_are_not_duplicate_records():
    rows = [
        {"record_id": "a", "sequence_hash": "wt1", "metric": "km", "value_si": 1.0, "source_id": "s1", "source_record_id": "r1", "substrate": "A", "license_status": "approved", "quality_flags": [], "source_file_sha256": "a" * 64},
        {"record_id": "b", "sequence_hash": "wt1", "metric": "km", "value_si": 1.0, "source_id": "s1", "source_record_id": "r2", "substrate": "B", "license_status": "approved", "quality_flags": [], "source_file_sha256": "a" * 64},
    ]
    audit = audit_rows(rows)
    assert "duplicate_record" not in audit["errors"]

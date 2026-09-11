import pytest

from normalize_literature_measurements import normalize_row


def test_normalize_preserves_original_unit_and_converts_km():
    row = {
        "source_id": "src-1",
        "protein_sequence": "MKT",
        "metric": "Km",
        "value": 2.5,
        "unit": "mM",
        "pH": 6.5,
        "temperature": 37,
        "assay_method": "steady state",
        "source_row_or_table": "Table 2 row 4",
        "license": "CC-BY-4.0",
    }
    normalized = normalize_row(row)
    assert normalized["original_value"] == 2.5
    assert normalized["original_unit"] == "mM"
    assert normalized["value_si"] == pytest.approx(0.0025)
    assert normalized["training_import_status"] == "training_candidate"


def test_missing_unit_and_license_stays_review():
    normalized = normalize_row(
        {"source_id": "src-2", "protein_sequence": "MKT", "metric": "Tm", "value": 55}
    )
    assert normalized["training_import_status"] == "needs_review"
    assert "missing_unit" in normalized["quality_flags"]
    assert "missing_license" in normalized["quality_flags"]


def test_mutation_position_must_match_wild_type_sequence():
    normalized = normalize_row(
        {
            "source_id": "src-3",
            "protein_sequence": "MKT",
            "metric": "mutation_effect",
            "value": 1.2,
            "unit": "relative",
            "mutation": "A2V",
            "source_row_or_table": "Table 1",
            "license": "CC-BY-4.0",
        }
    )
    assert normalized["training_import_status"] == "needs_review"
    assert "mutation_wild_type_mismatch" in normalized["quality_flags"]

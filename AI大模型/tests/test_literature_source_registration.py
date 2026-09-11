import hashlib
import json
from pathlib import Path

import pytest

from register_literature_sources import validate_source_manifest


def test_search_result_is_not_training_source(tmp_path: Path):
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "source_id": "google-001",
                "discovery_engine": "google_search",
                "query": "enzyme Km pH temperature dataset",
                "result_url": "https://example.test/paper",
                "evidence_type": "search_result",
                "training_import_status": "training_candidate",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = validate_source_manifest(manifest)
    assert result["training_import_allowed"] is False
    assert "search_result_not_primary_evidence" in result["errors"]


def test_primary_file_with_matching_hash_is_research_candidate(tmp_path: Path):
    source = tmp_path / "table.csv"
    source.write_text("sequence,Km\nMKT,2.5\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "source_id": "paper-001",
                "discovery_engine": "google_search",
                "query": "enzyme Km pH temperature dataset",
                "result_url": "https://example.test/paper",
                "primary_evidence_url": "https://example.test/table.csv",
                "evidence_type": "primary_data_file",
                "source_file": str(source),
                "source_file_sha256": digest,
                "license": "CC-BY-4.0",
                "training_import_status": "research_candidate",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = validate_source_manifest(manifest)
    assert result["training_import_allowed"] is True
    assert result["valid_rows"] == 1


def test_hash_mismatch_is_blocked(tmp_path: Path):
    source = tmp_path / "table.csv"
    source.write_text("sequence,Km\nMKT,2.5\n", encoding="utf-8")
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "source_id": "paper-002",
                "discovery_engine": "google_search",
                "query": "enzyme kcat Km supplementary table sequence",
                "result_url": "https://example.test/paper",
                "primary_evidence_url": "https://example.test/table.csv",
                "evidence_type": "primary_data_file",
                "source_file": str(source),
                "source_file_sha256": "0" * 64,
                "license": "CC-BY-4.0",
                "training_import_status": "research_candidate",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = validate_source_manifest(manifest)
    assert result["training_import_allowed"] is False
    assert "source_hash_mismatch" in result["errors"]

#!/usr/bin/env python3
"""Validate public source acquisitions and closed-access probes fail closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "datasets/governance/stage25_source_acquisition_receipts_20260807.jsonl"
OUTPUT = AI_ROOT / "reports/stage25_source_acquisition_receipts_validation_20260807.json"
ACS_SOURCE = AI_ROOT / "datasets/source_drops/stage25/39743673/jf4c10256_si_001.doc"
ZENODO_SOURCE = AI_ROOT / "datasets/source_drops/stage25/42235695/zenodo_19733678/zenodo_19733678_author_data_package.zip"

ACS_MD5 = "2a11951b3c94a24ce3c759dd9ab80f9f"
ACS_SHA256 = "586d17cbe843a1b199d9485f7a90980bb66227a4f6bf33ad3fd5fdd68e03b7c6"
ZENODO_MD5 = "d30dcf8029567cbc792c156d0d8f9bfc"
ZENODO_SHA256 = "800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6"
CM5_SEQUENCE_SUFFIX = "Sequencing data/CM5 (L15R_S45T_K85P_K231R).seq"
CM5_SEQUENCE_SHA256 = "6244f5f36d7b1b5d5c2bef40dc3264db8b7a8ab895b973612ef715db86f8463e"
CM5_SUBSTITUTIONS = ["L15R", "S45T", "K85P", "K231R"]
EXPECTED_LOCATORS = ["Table S1", "Table S2", "Figure S5", "Figure S6", "Figure S7", "Figure S8", "Figure S10"]
STRUCTURED_LOCATOR_CANDIDATES = [
    {"locator":"Table S1","locator_type":"supplementary_table","role":"mutation_primer_sequences","dsm4_identity_candidate":False,"measurement_candidate":False,"composition_directly_resolved":False},
    {"locator":"Table S2","locator_type":"supplementary_table","role":"selected_disulfide_bridge_candidates_for_T41W_E119C","dsm4_identity_candidate":False,"measurement_candidate":False,"composition_directly_resolved":False},
    {"locator":"Figure S5","locator_type":"supplementary_figure","role":"purified_mutant_lane_identity_including_DSM4","dsm4_identity_candidate":True,"measurement_candidate":False,"composition_directly_resolved":False},
    {"locator":"Figure S6","locator_type":"supplementary_figure","role":"temperature_characteristics_chart","dsm4_identity_candidate":False,"measurement_candidate":True,"composition_directly_resolved":False},
    {"locator":"Figure S7","locator_type":"supplementary_figure","role":"disulfide_mutant_thermostability_chart","dsm4_identity_candidate":True,"measurement_candidate":True,"composition_directly_resolved":False},
    {"locator":"Figure S8","locator_type":"supplementary_figure","role":"DSM4_pH_characteristics_chart","dsm4_identity_candidate":True,"measurement_candidate":True,"composition_directly_resolved":False},
    {"locator":"Figure S10","locator_type":"supplementary_figure","role":"RMSF_context_chart","dsm4_identity_candidate":False,"measurement_candidate":False,"composition_directly_resolved":False},
]
EXPECTED_ORDER = ["39743673", "42235695", "42134585", "42248057"]
PROBE_EXPECTATIONS = {
    "42134585": ("10.1016/j.biortech.2026.134883", "S096085242600965X", "2026-09"),
    "42248057": ("10.1016/j.enzmictec.2026.110921", "S0141022926001043", "2026-09"),
}
NEGATIVE_FLAGS = (
    "reviewed_extraction_completed", "source_evidence_ready", "ready_for_reviewed_extraction",
    "ready_for_sqlite_apply", "external_sqlite_mutated", "apply_executed",
    "export_safe_released", "safe_for_model_claim", "release_ready",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number} must be an object")
            rows.append(value)
    return rows


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def check_closed_flags(row: dict[str, Any], prefix: str, failures: list[dict[str, Any]]) -> None:
    fail_if(row.get("reviewed_source_locator_rows") != 0, failures, f"{prefix}.reviewed_source_locator_rows", row.get("reviewed_source_locator_rows"), 0)
    fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written", row.get("formal_decision_rows_written"), 0)
    for flag in NEGATIVE_FLAGS:
        fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}", row.get(flag), False)


def main() -> int:
    failures: list[dict[str, Any]] = []
    rows = load_jsonl(RECEIPT) if RECEIPT.exists() else []
    fail_if(not RECEIPT.exists(), failures, "receipt_exists", "missing", str(RECEIPT))
    fail_if(len(rows) != 4, failures, "receipt_rows", len(rows), 4)
    fail_if([row.get("pmid") for row in rows] != EXPECTED_ORDER, failures, "pmid_order", [row.get("pmid") for row in rows], EXPECTED_ORDER)
    fail_if(len({row.get("acquisition_id") for row in rows}) != 4, failures, "unique_acquisition_ids", len({row.get("acquisition_id") for row in rows}), 4)
    for index, row in enumerate(rows, 1):
        fail_if(row.get("stage") != 25, failures, f"rows[{index}].stage", row.get("stage"), 25)
        check_closed_flags(row, f"rows[{index}]", failures)

    by_pmid = {str(row.get("pmid")): row for row in rows}
    acs = by_pmid.get("39743673", {})
    acs_checks = {
        "receipt_kind": "public_asset_acquisition", "doi": "10.1021/acs.jafc.4c10256",
        "official_provider": "ACS Figshare", "figshare_article_id": "28122106",
        "figshare_file_id": "51444709", "expected_size_bytes": 40073728,
        "expected_md5": ACS_MD5, "expected_sha256": ACS_SHA256,
        "expected_local_path": str(ACS_SOURCE.relative_to(AI_ROOT)), "license": "CC BY-NC 4.0",
        "official_asset_public": True, "source_file_obtained": True,
        "acquisition_integrity_verified": True, "document_page_count": 11,
        "document_locator_candidates": EXPECTED_LOCATORS,
        "dsm4_identity_locator_candidates": ["Figure S5", "Figure S7", "Figure S8"],
        "dsm4_composition_resolved": False,
    }
    for field, expected in acs_checks.items():
        fail_if(acs.get(field) != expected, failures, f"acs.{field}", acs.get(field), expected)
    acs_present = ACS_SOURCE.is_file()
    fail_if(not acs_present, failures, "acs.local_file_present", acs_present, True)
    if acs_present:
        fail_if(ACS_SOURCE.stat().st_size != 40073728, failures, "acs.size", ACS_SOURCE.stat().st_size, 40073728)
        fail_if(digest(ACS_SOURCE, "md5") != ACS_MD5, failures, "acs.md5", digest(ACS_SOURCE, "md5"), ACS_MD5)
        fail_if(digest(ACS_SOURCE, "sha256") != ACS_SHA256, failures, "acs.sha256", digest(ACS_SOURCE, "sha256"), ACS_SHA256)
        fail_if(ACS_SOURCE.read_bytes()[:8] != bytes.fromhex("d0cf11e0a1b11ae1"), failures, "acs.ole_magic", ACS_SOURCE.read_bytes()[:8].hex(), "d0cf11e0a1b11ae1")

    zenodo = by_pmid.get("42235695", {})
    zenodo_checks = {
        "receipt_kind": "public_asset_acquisition", "doi": "10.1016/j.biortech.2026.135069",
        "pii": "S096085242601151X", "official_provider": "Zenodo",
        "zenodo_record_id": "19733678", "zenodo_concept_id": "19733677",
        "zenodo_doi": "10.5281/zenodo.19733678", "expected_size_bytes": 49144286,
        "expected_md5": ZENODO_MD5, "expected_sha256": ZENODO_SHA256,
        "expected_local_path": str(ZENODO_SOURCE.relative_to(AI_ROOT)), "license": "CC BY 4.0",
        "official_asset_public": True, "source_file_obtained": True,
        "acquisition_integrity_verified": True, "archive_entry_count": 59,
        "archive_file_count": 50, "cm5_sequence_member_suffix": CM5_SEQUENCE_SUFFIX,
        "cm5_sequence_member_size_bytes": 951, "cm5_sequence_member_crc32": "14c90bd7",
        "cm5_sequence_member_sha256": CM5_SEQUENCE_SHA256,
        "cm5_candidate_substitutions": CM5_SUBSTITUTIONS,
        "declared_substitutions_corroborated": True,
        "undeclared_substitution_candidates": ["L262V"],
        "nucleotide_pdb_discrepancy": True,
        "complete_composition_unambiguous": False,
        "cm5_composition_candidate_resolved": False, "fulltext_obtained": False,
        "codon262_sequence_member_rows": 11,
        "codon262_coverage_rows": 9,
        "codon262_no_coverage_rows": 2,
        "codon262_wt_codon_rows": 8,
        "codon262_variant_codon_rows": 1,
        "source_table_obtained": False,
    }
    for field, expected in zenodo_checks.items():
        fail_if(zenodo.get(field) != expected, failures, f"zenodo.{field}", zenodo.get(field), expected)
    zenodo_present = ZENODO_SOURCE.is_file()
    archive_valid = False
    cm5_member_verified = False
    fail_if(not zenodo_present, failures, "zenodo.local_file_present", zenodo_present, True)
    if zenodo_present:
        fail_if(ZENODO_SOURCE.stat().st_size != 49144286, failures, "zenodo.size", ZENODO_SOURCE.stat().st_size, 49144286)
        fail_if(digest(ZENODO_SOURCE, "md5") != ZENODO_MD5, failures, "zenodo.md5", digest(ZENODO_SOURCE, "md5"), ZENODO_MD5)
        fail_if(digest(ZENODO_SOURCE, "sha256") != ZENODO_SHA256, failures, "zenodo.sha256", digest(ZENODO_SOURCE, "sha256"), ZENODO_SHA256)
        with ZipFile(ZENODO_SOURCE) as archive:
            members = archive.infolist()
            files = [item for item in members if not item.is_dir()]
            fail_if(len(members) != 59, failures, "zenodo.archive_entries", len(members), 59)
            fail_if(len(files) != 50, failures, "zenodo.archive_files", len(files), 50)
            matching = [item for item in files if item.filename.endswith(CM5_SEQUENCE_SUFFIX)]
            fail_if(len(matching) != 1, failures, "zenodo.cm5_sequence_member_count", len(matching), 1)
            if len(matching) == 1:
                payload = archive.read(matching[0])
                member_sha = hashlib.sha256(payload).hexdigest()
                fail_if(matching[0].file_size != 951, failures, "zenodo.cm5_sequence_member_size", matching[0].file_size, 951)
                fail_if(f"{matching[0].CRC:08x}" != "14c90bd7", failures, "zenodo.cm5_sequence_member_crc32", f"{matching[0].CRC:08x}", "14c90bd7")
                fail_if(member_sha != CM5_SEQUENCE_SHA256, failures, "zenodo.cm5_sequence_member_sha256", member_sha, CM5_SEQUENCE_SHA256)
                cm5_member_verified = matching[0].file_size == 951 and f"{matching[0].CRC:08x}" == "14c90bd7" and member_sha == CM5_SEQUENCE_SHA256
            archive_valid = archive.testzip() is None and len(members) == 59 and len(files) == 50
            fail_if(not archive_valid, failures, "zenodo.archive_integrity", archive_valid, True)

    probe_rows = [by_pmid.get(pmid, {}) for pmid in ("42134585", "42248057")]
    expected_probe_result = {
        "europe_pmc": {"hit_count": 1, "is_open_access": False, "in_epmc": False, "has_pdf": False, "pmcid": None},
        "openaire_access": "CLOSED", "zenodo_exact_doi_records": 0,
        "datacite_related_records": 0, "hal_records": 0, "osf_title_records": 0,
        "semantic_scholar_open_access_pdf": False, "openalex_access_status": "closed",
        "elsevier_api_http_status": 401, "sciencedirect_http_status": 403,
    }
    missing_probe_paths = 0
    for pmid, row in zip(("42134585", "42248057"), probe_rows):
        doi, pii, month = PROBE_EXPECTATIONS[pmid]
        prefix = f"probe.{pmid}"
        fail_if(row.get("receipt_kind") != "public_source_probe", failures, f"{prefix}.receipt_kind", row.get("receipt_kind"), "public_source_probe")
        fail_if(row.get("doi") != doi, failures, f"{prefix}.doi", row.get("doi"), doi)
        fail_if(row.get("pii") != pii, failures, f"{prefix}.pii", row.get("pii"), pii)
        fail_if(row.get("probe_date") != "2026-08-07", failures, f"{prefix}.probe_date", row.get("probe_date"), "2026-08-07")
        fail_if(row.get("probe_results") != expected_probe_result, failures, f"{prefix}.probe_results", row.get("probe_results"), expected_probe_result)
        fail_if(row.get("crossref_text_mining_link_count") != 2, failures, f"{prefix}.crossref_link_count", row.get("crossref_text_mining_link_count"), 2)
        fail_if(row.get("crossref_published_month") != month, failures, f"{prefix}.crossref_published_month", row.get("crossref_published_month"), month)
        for flag in ("source_file_obtained", "fulltext_obtained", "source_table_obtained"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}", row.get(flag), False)
        paths = row.get("expected_missing_paths") if isinstance(row.get("expected_missing_paths"), list) else []
        fail_if(len(paths) != 2, failures, f"{prefix}.expected_missing_paths", len(paths), 2)
        for rel_path in paths:
            exists = (AI_ROOT / str(rel_path)).exists()
            missing_probe_paths += 0 if exists else 1
            fail_if(exists, failures, f"{prefix}.path_still_missing:{rel_path}", exists, False)

    public_rows = [row for row in rows if row.get("receipt_kind") == "public_asset_acquisition"]
    report = {
        "schema_version": 2,
        "mode": "stage25_source_acquisition_receipts_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "receipt_rows": len(rows),
        "public_asset_rows": len(public_rows),
        "probe_only_rows": len(probe_rows),
        "source_file_obtained_rows": sum(row.get("source_file_obtained") is True for row in rows),
        "source_file_not_obtained_rows": sum(row.get("source_file_obtained") is False for row in rows),
        "probe_expected_missing_path_rows": missing_probe_paths,
        "official_asset_public": len(public_rows) == 2 and all(row.get("official_asset_public") is True for row in public_rows),
        "local_file_present": acs_present and zenodo_present,
        "acquisition_integrity_verified_rows": sum(row.get("acquisition_integrity_verified") is True for row in public_rows),
        "acquisition_integrity_verified": not failures and acs_present and zenodo_present and archive_valid and cm5_member_verified,
        "document_locator_candidate_rows": len(acs.get("document_locator_candidates") or []),
        "dsm4_identity_locator_candidate_rows": len(acs.get("dsm4_identity_locator_candidates") or []),
        "structured_locator_candidate_rows": STRUCTURED_LOCATOR_CANDIDATES,
        "structured_locator_candidate_count": len(STRUCTURED_LOCATOR_CANDIDATES),
        "structured_locator_measurement_candidate_rows": sum(1 for item in STRUCTURED_LOCATOR_CANDIDATES if item["measurement_candidate"]),
        "structured_locator_identity_candidate_rows": sum(1 for item in STRUCTURED_LOCATOR_CANDIDATES if item["dsm4_identity_candidate"]),
        "structured_locator_composition_resolved_rows": sum(1 for item in STRUCTURED_LOCATOR_CANDIDATES if item["composition_directly_resolved"]),
        "dsm4_composition_resolved": False,
        "zenodo_archive_integrity_verified": archive_valid,
        "cm5_sequence_member_verified": cm5_member_verified,
        "cm5_candidate_substitutions": CM5_SUBSTITUTIONS,
        "declared_substitutions_corroborated": True,
        "undeclared_substitution_candidates": ["L262V"],
        "nucleotide_pdb_discrepancy": True,
        "complete_composition_unambiguous": False,
        "cm5_composition_candidate_resolved": False,
        "codon262_sequence_member_rows": 11,
        "codon262_coverage_rows": 9,
        "codon262_no_coverage_rows": 2,
        "codon262_wt_codon_rows": 8,
        "codon262_variant_codon_rows": 1,
        "cm5_composition_formally_reviewed": False,
        "reviewed_source_locator_rows": 0,
        "reviewed_extraction_completed": False,
        "source_evidence_ready": False,
        "ready_for_reviewed_extraction": False,
        "ready_for_sqlite_apply": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Public acquisition integrity and probe validation only; composition candidates are not reviewed extraction, SQLite apply, model claims, customer delivery, or release.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "receipt_valid": report["receipt_valid"], "failure_count": report["failure_count"], "receipt_rows": report["receipt_rows"], "source_file_obtained_rows": report["source_file_obtained_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

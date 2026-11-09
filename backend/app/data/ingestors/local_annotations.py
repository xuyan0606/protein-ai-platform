"""Local annotation ingestor for InterPro/M-CSA/SignalP seed datasets."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from app.core.config import settings
from app.data.base_ingestor import BaseIngestor
from app.data.ingestor_registry import register
from app.services.annotation_dataset_service import AnnotationDatasetService


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
LEGACY_FIXTURE = FIXTURE_DIR / "local_annotation_samples.json"
STRUCTURED_FIXTURE_DIR = FIXTURE_DIR / "local_annotations"


def _read_json(path: Path) -> list[dict] | dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_scalar(value: str) -> object:
    raw = value.strip()
    if raw == "":
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() == "null":
        return None
    if raw[:1] in {"{", "["}:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _read_tabular(path: Path) -> list[dict]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle, delimiter=delimiter):
            rows.append({key: _coerce_scalar(value or "") for key, value in row.items() if key})
        return rows


def _records_from_file(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = _read_json(path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return payload["records"]
        raise ValueError(f"Unsupported local annotation JSON shape: {path}")
    if suffix in {".csv", ".tsv"}:
        return _read_tabular(path)
    raise ValueError(f"Unsupported local annotation file format: {path}")


def _pick(record: dict, *keys: str):
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _build_base_bundle(record: dict) -> dict:
    enzyme = record.get("enzyme")
    if not isinstance(enzyme, dict):
        enzyme = {
            "uniprot_id": _pick(record, "uniprot_id", "accession", "enzyme_uniprot_id", "enzyme_accession"),
            "name": _pick(record, "name", "enzyme_name"),
            "sequence": _pick(record, "sequence", "enzyme_sequence"),
            "protein_name": _pick(record, "protein_name", "enzyme_protein_name"),
            "gene_name": _pick(record, "gene_name", "enzyme_gene_name"),
            "source_db": _pick(record, "source_db", "enzyme_source_db"),
            "source_version": _pick(record, "source_version", "enzyme_source_version"),
        }
        enzyme = {key: value for key, value in enzyme.items() if value not in (None, "")}

    taxonomy = record.get("taxonomy")
    if not isinstance(taxonomy, dict):
        taxonomy = {
            "scientific_name": _pick(record, "scientific_name", "taxonomy_scientific_name"),
            "common_name": _pick(record, "common_name", "taxonomy_common_name"),
            "kingdom": _pick(record, "kingdom", "taxonomy_kingdom"),
            "phylum": _pick(record, "phylum", "taxonomy_phylum"),
            "class_name": _pick(record, "class_name", "taxonomy_class_name"),
            "order_name": _pick(record, "order_name", "taxonomy_order_name"),
            "family": _pick(record, "family", "taxonomy_family"),
            "genus": _pick(record, "genus", "taxonomy_genus"),
            "species": _pick(record, "species", "taxonomy_species"),
            "ncbi_taxid": _pick(record, "ncbi_taxid", "taxonomy_ncbi_taxid"),
        }
        taxonomy = {key: value for key, value in taxonomy.items() if value not in (None, "")}

    def _list_field(name: str) -> list[dict]:
        value = record.get(name)
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        raise ValueError(f"{name} must be a JSON array when using tabular base exports")

    signal = record.get("signal_peptide_prediction")
    if signal in ("", None):
        signal = None
    elif not isinstance(signal, dict):
        raise ValueError("signal_peptide_prediction must be a JSON object when using tabular base exports")

    return {
        "taxonomy": taxonomy,
        "enzyme": enzyme,
        "ec_numbers": _list_field("ec_numbers"),
        "pfam_domains": _list_field("pfam_domains"),
        "interpro_annotations": _list_field("interpro_annotations"),
        "catalytic_sites": _list_field("catalytic_sites"),
        "signal_peptide_prediction": signal,
    }


def _require_uniprot_id(record: dict, path: Path) -> str:
    uniprot_id = record.get("uniprot_id") or record.get("accession")
    if not uniprot_id:
        raise ValueError(f"Missing uniprot_id/accession in {path}")
    return str(uniprot_id)


def _parse_structured_fixture(raw_dir: Path) -> list[dict]:
    """Merge source-shaped local exports into unified annotation bundles.

    Expected optional files:
    - base.(json|csv|tsv): complete bundles or enzyme/taxonomy records
    - interpro.(json|csv|tsv): InterPro records keyed by uniprot_id/accession
    - mcsa.(json|csv|tsv): catalytic site records keyed by uniprot_id/accession
    - signalp.(json|csv|tsv): SignalP records keyed by uniprot_id/accession
    """

    metadata_path = raw_dir / "metadata.json"
    metadata = _read_json(metadata_path) if metadata_path.exists() else {}
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata.json must be a JSON object: {metadata_path}")

    bundles: dict[str, dict] = {}

    def _find_source_file(stem: str) -> Path | None:
        for suffix in (".json", ".csv", ".tsv"):
            candidate = raw_dir / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
        return None

    base_path = _find_source_file("base")
    if base_path is not None:
        for raw_record in _records_from_file(base_path):
            record = raw_record if isinstance(raw_record.get("enzyme"), dict) else _build_base_bundle(raw_record)
            enzyme = record.get("enzyme") or record
            uniprot_id = enzyme.get("uniprot_id") or enzyme.get("accession")
            if not uniprot_id:
                raise ValueError(f"Missing enzyme.uniprot_id in {base_path}")
            enzyme_source_db = enzyme.get("source_db") or metadata.get("default_source_db") or "local_demo"
            enzyme_source_version = enzyme.get("source_version") or metadata.get("dataset_version")
            bundles[str(uniprot_id)] = {
                "taxonomy": record.get("taxonomy") or {},
                "enzyme": {
                    **enzyme,
                    "uniprot_id": str(uniprot_id),
                    "source_db": enzyme_source_db,
                    "source_version": enzyme_source_version,
                },
                "ec_numbers": record.get("ec_numbers") or [],
                "pfam_domains": record.get("pfam_domains") or [],
                "interpro_annotations": record.get("interpro_annotations") or [],
                "catalytic_sites": record.get("catalytic_sites") or [],
                "signal_peptide_prediction": record.get("signal_peptide_prediction"),
            }

    for stem, target_key in (
        ("interpro", "interpro_annotations"),
        ("mcsa", "catalytic_sites"),
    ):
        path = _find_source_file(stem)
        if path is None:
            continue
        grouped: dict[str, list[dict]] = defaultdict(list)
        for record in _records_from_file(path):
            uniprot_id = _require_uniprot_id(record, path)
            grouped[uniprot_id].append(
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"uniprot_id", "accession"}
                }
            )
        for uniprot_id, records in grouped.items():
            if uniprot_id not in bundles:
                raise ValueError(f"{path.name} references unknown uniprot_id: {uniprot_id}")
            bundles[uniprot_id][target_key] = records

    signalp_path = _find_source_file("signalp")
    if signalp_path is not None:
        for record in _records_from_file(signalp_path):
            uniprot_id = _require_uniprot_id(record, signalp_path)
            if uniprot_id not in bundles:
                raise ValueError(f"{signalp_path.name} references unknown uniprot_id: {uniprot_id}")
            bundles[uniprot_id]["signal_peptide_prediction"] = {
                key: value
                for key, value in record.items()
                if key not in {"uniprot_id", "accession"}
            }

    return list(bundles.values())


@register("local_annotations")
class LocalAnnotationIngestor(BaseIngestor):
    """Seed repeatable local annotations for demo and validation workflows."""

    source_name = "local_annotations"

    async def _download_raw(self) -> Path:
        configured = (settings.LOCAL_ANNOTATION_FIXTURE_PATH or "").strip()
        if configured:
            return Path(configured)
        if STRUCTURED_FIXTURE_DIR.exists():
            return STRUCTURED_FIXTURE_DIR
        return LEGACY_FIXTURE

    async def _parse_raw(self, raw_path: Path) -> list[dict]:
        if raw_path.is_dir():
            return _parse_structured_fixture(raw_path)
        return _records_from_file(raw_path)

    async def _store_batch(self, batch: list[dict]) -> tuple[int, int]:
        service = AnnotationDatasetService(self.db)
        return await service.ingest_records(batch)

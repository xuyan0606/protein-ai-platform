"""Data ingestion module — base framework + per-source ingestors."""

from app.data.base_ingestor import BaseIngestor, IngestReport, IngestStatus

__all__ = ["BaseIngestor", "IngestReport", "IngestStatus"]

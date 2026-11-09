"""Pure BLAST report-state contracts that do not require the database fixture."""

from app.services.evidence_source_status import evidence_source_status
from app.tools.blast_search import _result_payload


def test_blast_report_states_never_collapse_waiting_or_failed_into_no_hit():
    states = {
        "submitted": _result_payload(seq="ACDE", program="blastp", database="nr", hits=[], status="submitted"),
        "waiting": _result_payload(seq="ACDE", program="blastp", database="nr", hits=[], status="waiting"),
        "failed": _result_payload(seq="ACDE", program="blastp", database="nr", hits=[], status="failed"),
        "completed_no_hit": _result_payload(seq="ACDE", program="blastp", database="nr", hits=[], status="completed"),
        "completed_with_hits": _result_payload(seq="ACDE", program="blastp", database="nr", hits=[{"accession": "P1"}], status="completed"),
    }
    assert states["submitted"]["evidence_status"] == "submitted"
    assert states["waiting"]["evidence_status"] == "waiting"
    assert states["failed"]["evidence_status"] == "failed"
    assert states["completed_no_hit"]["evidence_status"] == "completed_no_hit"
    assert states["completed_with_hits"]["evidence_status"] == "completed_with_hits"


def test_live_blast_source_keeps_checked_time_endpoint_database_and_rid():
    source = evidence_source_status(
        source="NCBI BLAST",
        status="live",
        mode="durable_ncbi_blast",
        live_query_executed=True,
        endpoint="https://blast.ncbi.nlm.nih.gov/Blast.cgi",
        details={"rid": "RID-123", "database": "nr"},
    )
    result = _result_payload(
        seq="ACDE",
        program="blastp",
        database="nr",
        hits=[],
        evidence_source=source,
    )
    assert result["evidence_source"]["status"] == "live"
    assert result["evidence_source"]["live_query_executed"] is True
    assert result["evidence_source"]["endpoint"].endswith("Blast.cgi")
    assert result["evidence_source"]["checked_at"]
    assert result["evidence_source"]["details"] == {"rid": "RID-123", "database": "nr"}

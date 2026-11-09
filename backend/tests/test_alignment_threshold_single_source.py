"""The aligned-FASTA acceptance gate must use the same threshold as residue mapping.

Two call sites decide that a user FASTA is "near-identical" to the structure
sequence: the residue mapping tool (fraction units, MIN_ALIGNMENT_IDENTITY) and
the plan hydration in agent_graph (percent units). They are the same policy
decision and must not drift apart, so these tests pin agent_graph's accepted /
rejected boundary to MIN_ALIGNMENT_IDENTITY rather than to a private literal.
"""
import asyncio
import inspect

from app.core.agent_graph import AgentOrchestrator, PlanStep, _sequence_identity_pct
from app.tools.residue_mapping_sifts import (
    MIN_ALIGNMENT_IDENTITY,
    alignment_accepts_projection,
    projection_accepted,
)

# 20 residues keeps the behavioural band exact: 19/20 == 95% (accept) and
# 18/20 == 90% (reject), straddling the 95% gate with no floating-point noise.
COORDINATE_SEQUENCE = "ACDEFGHIKLMNPQRSTVWY"


def _with_interior_substitutions(positions, replacement="W"):
    residues = list(COORDINATE_SEQUENCE)
    for position in positions:
        residues[position] = "A" if residues[position] == replacement else replacement
    return "".join(residues)


NEAR_IDENTICAL_FASTA = _with_interior_substitutions([9])       # 95.0%
DISTINCT_FASTA = _with_interior_substitutions([8, 9])          # 90.0%
UNRELATED_FASTA = _with_interior_substitutions([5, 6, 7, 8, 9])  # 75.0%


def _task_for(fasta_sequence):
    return (
        f"预测这个蛋白的性质\n>user_fasta\n{fasta_sequence}\n"
        "[Attached files:\nname: sample.pdb, object_name: uploads/user_999/sample.pdb]"
    )


def _hydrate(monkeypatch, fasta_sequence, chains=None):
    """Run plan hydration with the coordinate sequence pinned by a fake preflight.

    With no per-chain sequences the step takes the aligned_fasta decision that
    the user FASTA and coordinate sequence drive in production. With chains the
    step takes the chain-scoped branch, which must apply the same policy.
    """
    orchestrator = AgentOrchestrator()

    async def preflight(_task):
        return {
            "status": "readable",
            "display_name": "sample.pdb",
            "coordinate_sequence": COORDINATE_SEQUENCE,
            "seqres_sequence": "",
            "chains": chains or [],
        }

    monkeypatch.setattr(orchestrator, "_build_pdb_preflight_summary", preflight)
    plan = [PlanStep(id=1, tool_name="predict_properties", description="properties", params={})]
    hydrated = asyncio.run(
        orchestrator._hydrate_uploaded_pdb_sequence_for_plan(plan, _task_for(fasta_sequence))
    )
    return hydrated[0].params


def _hydrate_with_plan(monkeypatch, fasta_sequence, chains, plan):
    orchestrator = AgentOrchestrator()

    async def preflight(_task):
        return {
            "status": "readable",
            "display_name": "sample.pdb",
            "coordinate_sequence": COORDINATE_SEQUENCE,
            "seqres_sequence": "",
            "chains": chains,
        }

    monkeypatch.setattr(orchestrator, "_build_pdb_preflight_summary", preflight)
    hydrated = asyncio.run(
        orchestrator._hydrate_uploaded_pdb_sequence_for_plan(plan, _task_for(fasta_sequence))
    )
    return hydrated[0].params


def test_helper_reports_expected_identity_around_the_gate():
    assert _sequence_identity_pct(NEAR_IDENTICAL_FASTA, COORDINATE_SEQUENCE) == 95.0
    assert _sequence_identity_pct(DISTINCT_FASTA, COORDINATE_SEQUENCE) == 90.0
    # Guard: if the canonical gate moved to 0.90, the "rejected" specimen would
    # start passing and this test must fail loudly instead of silently agreeing.
    assert MIN_ALIGNMENT_IDENTITY * 100 > _sequence_identity_pct(DISTINCT_FASTA, COORDINATE_SEQUENCE)
    assert MIN_ALIGNMENT_IDENTITY * 100 <= _sequence_identity_pct(NEAR_IDENTICAL_FASTA, COORDINATE_SEQUENCE)


def test_hydration_accepts_fasta_exactly_at_the_canonical_threshold(monkeypatch):
    params = _hydrate(monkeypatch, NEAR_IDENTICAL_FASTA)
    assert params["sequence"] == NEAR_IDENTICAL_FASTA
    assert params["sequence_provenance"] == "user_fasta_aligned"
    assert "_sequence_input_conflict" not in params


def test_hydration_rejects_fasta_just_below_the_canonical_threshold(monkeypatch):
    params = _hydrate(monkeypatch, DISTINCT_FASTA)
    assert params["sequence"] == COORDINATE_SEQUENCE
    assert params["sequence_provenance"] == "pdb_coordinate_derived"
    assert params["_sequence_input_conflict"] is True


def test_hydration_rejects_unrelated_fasta(monkeypatch):
    params = _hydrate(monkeypatch, UNRELATED_FASTA)
    assert params["sequence"] == COORDINATE_SEQUENCE
    assert params["_sequence_input_conflict"] is True


def test_chain_scoped_hydration_accepts_near_identical_fasta(monkeypatch):
    # A successful per-chain preflight must apply the same near-identical-FASTA
    # policy; otherwise a truncated clone is misreported as a different protein
    # exactly when the structure parsed cleanly.
    chains = [{"chain_id": "A", "sequence": COORDINATE_SEQUENCE}]
    plan_step = PlanStep(id=1, tool_name="predict_properties", description="properties",
                         params={"chain_id": "A"})
    params = _hydrate_with_plan(monkeypatch, NEAR_IDENTICAL_FASTA, chains, [plan_step])
    assert params["sequence"] == NEAR_IDENTICAL_FASTA
    assert params["sequence_provenance"] == "user_fasta_aligned"
    assert "_sequence_input_conflict" not in params


def test_chain_scoped_hydration_rejects_distinct_fasta(monkeypatch):
    chains = [{"chain_id": "A", "sequence": COORDINATE_SEQUENCE}]
    plan_step = PlanStep(id=1, tool_name="predict_properties", description="properties",
                         params={"chain_id": "A"})
    params = _hydrate_with_plan(monkeypatch, DISTINCT_FASTA, chains, [plan_step])
    assert params["sequence"] == COORDINATE_SEQUENCE
    assert params["sequence_provenance"] == "pdb_coordinate_derived"
    assert params["_sequence_input_conflict"] is True


def test_hydration_source_uses_the_canonical_constant():
    """Source-level backstop: the decision must be delegated, not re-implemented.

    The behavioural tests above prove the boundary lands on 95% today. This
    check proves *where* that 95% comes from: hydration must call the residue
    mapping tool's shared predicate rather than compare an identity percentage
    itself. A local re-implementation is how the fragment hole appeared — it
    only checked identity and silently dropped the coverage and basis floors.
    """
    hydration = inspect.getsource(AgentOrchestrator._hydrate_uploaded_pdb_sequence_for_plan)
    assert "from app.tools.residue_mapping_sifts import alignment_accepts_projection" in hydration
    assert hydration.count("alignment_accepts_projection(") == 2  # coordinate + chain branches
    assert "MIN_ALIGNMENT_IDENTITY" not in hydration

    predicate = inspect.getsource(projection_accepted)
    assert "MIN_ALIGNMENT_IDENTITY" in predicate
    assert "MIN_ALIGNMENT_COVERAGE" in predicate
    assert "MIN_IDENTITY_BASIS" in predicate


def test_short_fragment_of_a_long_chain_is_not_the_users_protein(monkeypatch):
    # 12 of the 20 coordinate residues, all identical: identity 1.0, input-side
    # coverage 1.0, but only 12 comparable pairs. Accepting it would hand the
    # pipeline a 12-residue "protein" in place of a full chain, and the mapping
    # tool refuses the same pair for exactly this reason.
    fragment = COORDINATE_SEQUENCE[:12]
    params = _hydrate(monkeypatch, fragment)
    assert params["sequence"] == COORDINATE_SEQUENCE
    assert params["sequence_provenance"] == "pdb_coordinate_derived"
    assert params["_sequence_input_conflict"] is True


def test_chain_scoped_hydration_rejects_short_fragment(monkeypatch):
    chains = [{"chain_id": "A", "sequence": COORDINATE_SEQUENCE}]
    plan_step = PlanStep(id=1, tool_name="predict_properties", description="properties",
                         params={"chain_id": "A"})
    params = _hydrate_with_plan(monkeypatch, COORDINATE_SEQUENCE[:12], chains, [plan_step])
    assert params["sequence"] == COORDINATE_SEQUENCE
    assert params["sequence_provenance"] == "pdb_coordinate_derived"
    assert params["_sequence_input_conflict"] is True


def test_predicate_agrees_with_residue_mapping_acceptance():
    """The shared predicate must accept exactly what the mapping tool accepts."""
    assert alignment_accepts_projection(NEAR_IDENTICAL_FASTA, COORDINATE_SEQUENCE)
    assert not alignment_accepts_projection(DISTINCT_FASTA, COORDINATE_SEQUENCE)
    assert not alignment_accepts_projection(COORDINATE_SEQUENCE[:12], COORDINATE_SEQUENCE)
    assert not alignment_accepts_projection("", COORDINATE_SEQUENCE)
    # A truncated construct (missing the first residue) still has 19 comparable
    # pairs against this 20-residue stand-in, below the 20-pair floor.
    assert not alignment_accepts_projection(COORDINATE_SEQUENCE[1:], COORDINATE_SEQUENCE)

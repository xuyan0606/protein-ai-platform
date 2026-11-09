"""Chain selection when a caller supplies a FASTA but no chain.

Without a chain the mapping tool used to concatenate every protein chain and
align the FASTA against the join: a homodimer burned its coverage budget on the
duplicate, and a complex with a short chain could clear the coverage floor while
emitting cross-chain consecutive numbering under mapping_scope="chain".
"""
from app.core.agent_graph import AgentOrchestrator
from app.tools.residue_mapping_sifts import residue_mapping_sifts

THREE = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY",
    "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU", "M": "MET", "N": "ASN",
    "P": "PRO", "Q": "GLN", "R": "ARG", "S": "SER", "T": "THR", "V": "VAL",
    "W": "TRP", "Y": "TYR",
}

CHAIN_A = "MKTIIALSYIFCLVFADYKDDDDK"
CHAIN_B = "GAVLIPFYWSTCMNQHEDRKAVLIP"


def multi_chain_pdb(chains):
    """chains: list of (chain_id, sequence, first_author_number)."""
    lines = []
    serial = 0
    for chain_id, sequence, start in chains:
        for offset, aa in enumerate(sequence):
            serial += 1
            lines.append(
                f"ATOM  {serial:5d}  CA  {THREE[aa]:>3s} {chain_id}{start + offset:4d}    "
                f"{float(serial):8.3f}{0.000:8.3f}{0.000:8.3f}  1.00 20.00           C"
            )
    lines.append("END")
    return "\n".join(lines) + "\n"


async def map_without_chain(pdb_data, input_sequence):
    return await residue_mapping_sifts(pdb_data=pdb_data, input_sequence=input_sequence)


async def test_fasta_selects_the_chain_it_matches_not_the_first_chain():
    pdb = multi_chain_pdb([("A", CHAIN_A, 1), ("B", CHAIN_B, 1)])
    result = await map_without_chain(pdb, CHAIN_B)

    assert result["status"] == "completed"
    assert result["chain_id"] == "B"
    assert result["chain_selection"]["status"] == "selected"
    assert result["chain_selection"]["chain_id"] == "B"
    assert {row["target_chain_id"] for row in result["numbering_registry_rows"]} == {"B"}
    assert result["mapping_count"] == len(CHAIN_B)


async def test_homodimer_with_shared_numbering_is_not_ambiguous():
    # Identical chains on identical author numbering are interchangeable: the
    # projection is the same either way, so this is a selection, not a failure.
    pdb = multi_chain_pdb([("A", CHAIN_A, 1), ("B", CHAIN_A, 1)])
    result = await map_without_chain(pdb, CHAIN_A)

    assert result["status"] == "completed"
    assert result["chain_selection"]["status"] == "selected"
    assert result["chain_selection"]["shared_numbering"] is True
    assert result["mapping_count"] == len(CHAIN_A)


async def test_homodimer_with_different_author_frames_blocks_instead_of_guessing():
    # Same sequence, different author numbering: the projection would differ by
    # a constant per chain, so any automatic pick silently renumbers the clone.
    pdb = multi_chain_pdb([("A", CHAIN_A, 1), ("B", CHAIN_A, 50)])
    result = await map_without_chain(pdb, CHAIN_A)

    assert result["status"] == "blocked"
    assert result["error_code"] == "AMBIGUOUS_CHAIN_MATCH"
    assert result["ambiguous_chains"] == ["A", "B"]
    assert result["mapping_count"] == 0
    assert result["numbering_registry_status"] == "blocked"
    # The boundary must say what the user has to do; the generic QC wording
    # reads as "the tool failed" rather than "pick a chain".
    assert "指定 chain_id" in result["report_boundary"]
    assert "A、B" in result["report_boundary"]


async def test_short_chain_cannot_donate_names_to_a_longer_fasta():
    # A short chain that fully matches a fragment of the FASTA must not win over
    # the chain the whole FASTA belongs to.
    pdb = multi_chain_pdb([("A", CHAIN_B, 1), ("B", CHAIN_A, 7)])
    result = await map_without_chain(pdb, CHAIN_A)

    assert result["status"] == "completed"
    assert result["chain_selection"]["chain_id"] == "B"
    assert {row["target_chain_id"] for row in result["numbering_registry_rows"]} == {"B"}
    # Exact sequence match: input position 1 lands on author residue 7.
    assert result["mappings"][0]["pdb_residue_no"] == 7


async def test_explicit_chain_still_bypasses_selection():
    pdb = multi_chain_pdb([("A", CHAIN_A, 1), ("B", CHAIN_B, 1)])
    result = await residue_mapping_sifts(pdb_data=pdb, chain_id="B", input_sequence=CHAIN_A)

    # The caller asked for B; the tool reports why that projection failed instead
    # of overriding the request with its own pick.
    assert result["status"] == "blocked"
    assert result["error_code"] == "INPUT_SEQUENCE_MISMATCH"


async def test_unmatched_fasta_keeps_the_concatenated_baseline():
    # No chain projection accepts the FASTA: behaviour stays as before, so the
    # existing mismatch diagnostics and their error text are unchanged.
    pdb = multi_chain_pdb([("A", CHAIN_A, 1), ("B", CHAIN_B, 1)])
    result = await map_without_chain(pdb, "GGGGGGGGGGGGGGGGGGGGGGGG")

    assert result["status"] == "blocked"
    assert result["error_code"] == "INPUT_SEQUENCE_MISMATCH"
    assert "chain_selection" not in result


def test_preview_prefers_the_chain_the_fasta_matches():
    # The preflight's coordinate_sequence feeds hydration's aligned_fasta
    # decision. Taking chains[0] made that decision depend on file order: a FASTA
    # for chain B was compared against chain A and reported as a conflict.
    analysis = {
        "chains": [
            {"chain_id": "A", "sequence": CHAIN_A},
            {"chain_id": "B", "sequence": CHAIN_B},
        ]
    }
    assert AgentOrchestrator._sequence_preview_from_pdb_analysis(analysis, CHAIN_B) == CHAIN_B
    assert AgentOrchestrator._sequence_preview_from_pdb_analysis(analysis, CHAIN_A) == CHAIN_A


def test_preview_keeps_first_chain_when_no_fasta_is_given():
    analysis = {
        "chains": [
            {"chain_id": "A", "sequence": CHAIN_A},
            {"chain_id": "B", "sequence": CHAIN_B},
        ]
    }
    assert AgentOrchestrator._sequence_preview_from_pdb_analysis(analysis) == CHAIN_A


def test_preview_ignores_a_fasta_that_matches_no_chain():
    # An unrelated FASTA must not silently switch the preview to whichever chain
    # happens to be nearest; conflict detection needs the file-order baseline.
    analysis = {
        "chains": [
            {"chain_id": "A", "sequence": CHAIN_A},
            {"chain_id": "B", "sequence": CHAIN_B},
        ]
    }
    assert AgentOrchestrator._sequence_preview_from_pdb_analysis(
        analysis, "GGGGGGGGGGGGGGGGGGGGGGGG"
    ) == CHAIN_A


def test_preview_falls_back_to_seqres_without_chains():
    analysis = {"chains": [], "seqres_sequence": CHAIN_A}
    assert AgentOrchestrator._sequence_preview_from_pdb_analysis(analysis, CHAIN_B) == CHAIN_A

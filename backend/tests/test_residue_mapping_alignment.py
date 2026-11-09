"""Near-identical FASTA numbering: global alignment replaces exact-match-only refusal."""
import pytest

from app.tools.residue_mapping_sifts import residue_mapping_sifts


THREE = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY",
    "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU", "M": "MET", "N": "ASN",
    "P": "PRO", "Q": "GLN", "R": "ARG", "S": "SER", "T": "THR", "V": "VAL",
    "W": "TRP", "Y": "TYR",
}


def pdb_text(sequence, chain="A", start=1):
    """One CA atom per residue; author numbering deliberately not one-based."""
    lines = []
    for offset, aa in enumerate(sequence):
        text = THREE.get(aa, "UNK")
        lines.append(
            f"ATOM  {offset + 1:5d}  CA  {text:>3s} {chain}{start + offset:4d}    "
            f"{float(offset):8.3f}{0.000:8.3f}{0.000:8.3f}  1.00 20.00           C"
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


REFERENCE = "MKTIIALSYIFCLVFADYKDDDDK"


async def map_sequence(input_sequence, pdb_sequence=REFERENCE, **kwargs):
    return await residue_mapping_sifts(
        pdb_data=pdb_text(pdb_sequence), chain_id="A", input_sequence=input_sequence,
        **kwargs,
    )


async def test_point_substitution_maps_every_position_on_user_numbering():
    # Position 4 I->V: the clone carries the variant, the model the wild type.
    result = await map_sequence("MKTVIALSYIFCLVFADYKDDDDK")

    assert result["found"] is True
    assert result["source"] == "input_sequence_global_alignment"
    assert result["sequence_match"]["status"] == "aligned"
    assert result["sequence_match"]["identity"] == pytest.approx(23 / 24, abs=1e-4)
    assert result["sequence_match"]["coverage"] == 1.0
    assert result["mapping_count"] == len(REFERENCE)
    assert {row["mapping_confidence"] for row in result["mappings"]} == {"high_alignment"}
    assert result["sequence_substitutions"] == [{
        "user_sequence_position": 4, "user_residue_aa": "V",
        "pdb_residue_no": 4, "pdb_residue_aa": "I",
    }]
    assert result["unmapped_input_positions"] == []


async def test_truncated_fasta_maps_full_length_without_shifting_numbering():
    # The model starts with an M the clone lacks. Every input position still
    # maps back to the correct author number instead of shifting by one.
    result = await map_sequence("KTIIALSYIFCLVFADYKDDDDK")

    assert result["found"] is True
    assert result["mapping_count"] == len(REFERENCE) - 1
    assert result["unmapped_input_positions"] == []
    first = result["mappings"][0]
    assert first["user_sequence_position"] == 1
    assert first["pdb_residue_no"] == 2
    assert first["residue_aa"] == "K"


async def test_low_identity_sequence_is_still_blocked():
    result = await map_sequence("GGGGGGGGGGGGGGGGGGGGGGGG")

    assert result["found"] is False
    assert result["status"] == "blocked"
    assert result["error_code"] == "INPUT_SEQUENCE_MISMATCH"
    assert result["alignment"]["identity"] < 0.95


async def test_aligned_mapping_row_marks_numbering_and_passes_gate():
    from app.tools.mutation_priority_score import mutation_priority_score

    mapped = await map_sequence("MKTVIALSYIFCLVFADYKDDDDK")
    scoring_sequence = "MKTVIALSYIFCLVFADYKDDDDK"
    result = await mutation_priority_score(
        sequence=scoring_sequence, chain_id="A",
        sequence_provenance="user_fasta_aligned",
        pdb_coordinate_mapping=mapped["mappings"],
        identity_profile={"identity_status": "identified", "guardrail": {"status": "ready"}},
        objective_module_plan={"status": "ready", "candidate_output_allowed": True},
        include_lipase_evidence=False,
    )

    site = next(item for item in result["all_positions"] if item["position"] == 5)
    assert site["numbering_status"] == "aligned_user_sequence_to_pdb"
    assert site["pdb_position"] == "A:5"
    # identified + guardrail ready => profile_ready, so the gate is passed,
    # not exploratory (exploratory is the fallback for unconfirmed identity).
    assert result["identity_gate"]["status"] == "passed"


async def test_truncated_fasta_keeps_author_offset_in_scorer_table():
    from app.tools.mutation_priority_score import mutation_priority_score

    # The clone lacks the model's leading M, so user position k sits on author
    # residue k + 1. The scorer must carry that offset through instead of
    # renumbering the clone from 1.
    scoring_sequence = "KTIIALSYIFCLVFADYKDDDDK"
    mapped = await map_sequence(scoring_sequence)
    result = await mutation_priority_score(
        sequence=scoring_sequence, chain_id="A",
        sequence_provenance="user_fasta_aligned",
        pdb_coordinate_mapping=mapped["mappings"],
        identity_profile={"identity_status": "identified", "guardrail": {"status": "ready"}},
        objective_module_plan={"status": "ready", "candidate_output_allowed": True},
        include_lipase_evidence=False,
    )

    sites = {item["position"]: item for item in result["all_positions"]}
    assert len(sites) == len(scoring_sequence)
    first = sites[1]
    assert first["numbering_status"] == "aligned_user_sequence_to_pdb"
    assert first["pdb_position"] == "A:2"
    assert first["wild_type"] == "K"
    # Spot checks at distinct positions confirm the one-residue offset holds
    # across the whole table, not just the first row.
    for position in (5, 22, 23):
        assert sites[position]["numbering_status"] == "aligned_user_sequence_to_pdb"
        assert sites[position]["pdb_position"] == f"A:{position + 1}"
    assert sites[23]["wild_type"] == "K"

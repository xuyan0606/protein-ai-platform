"""Report contract for the global-alignment numbering path."""
import pytest

from app.tools.residue_mapping_sifts import _with_report_contract, residue_mapping_sifts


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
UNMAPPED_BOUNDARY_TEXT = "未得到可用映射"


async def map_sequence(input_sequence, pdb_sequence=REFERENCE, **kwargs):
    return await residue_mapping_sifts(
        pdb_data=pdb_text(pdb_sequence), chain_id="A", input_sequence=input_sequence,
        **kwargs,
    )


async def test_aligned_truncated_fasta_uses_alignment_contract():
    # Clone lacks the leading M; still a confident global alignment.
    result = await map_sequence("KTIIALSYIFCLVFADYKDDDDK")

    assert result["source"] == "input_sequence_global_alignment"
    assert result["numbering_registry_status"] == "ready"
    assert result["capability_status"] == "aligned_user_sequence_mapping"
    assert result["evidence_level"] == "GLOBAL_ALIGNMENT_MAPPING"
    assert UNMAPPED_BOUNDARY_TEXT not in result["report_boundary"]
    assert "全局比对" in result["report_boundary"]
    assert "输入序列编号" in result["report_boundary"]
    # Dynamic part reflects the payload's own alignment numbers.
    assert "一致" in result["report_boundary"]
    assert "100.00%" in result["report_boundary"]


async def test_report_boundary_names_the_sequence_substitution():
    result = await map_sequence("MKTVIALSYIFCLVFADYKDDDDK")

    assert result["capability_status"] == "aligned_user_sequence_mapping"
    assert "1 处差异" in result["report_boundary"]
    assert "4I>V" in result["report_boundary"]


async def test_constant_offset_is_stated_in_the_report_boundary():
    # The session-03 shape: the crystal lost the leading AAP to missing density,
    # so structure numbering runs 3 behind the user's sequence. Every position
    # shifts by the same amount and the user had to derive "+3" by hand.
    result = await map_sequence("AAP" + REFERENCE)

    assert result["source"] == "input_sequence_global_alignment"
    assert result["numbering_offset"] == -3
    assert "结构编号 = 输入序列编号 - 3" in result["report_boundary"]
    assert result["mapping_count"] == len(REFERENCE)
    first = result["mappings"][0]
    assert first["user_sequence_position"] == 4
    assert first["pdb_residue_no"] == 1


async def test_zero_offset_is_stated_as_no_conversion_needed():
    result = await map_sequence("MKTVIALSYIFCLVFADYKDDDDK")

    assert result["numbering_offset"] == 0
    assert "结构编号 = 输入序列编号，无需换算" in result["report_boundary"]


async def test_offset_is_not_claimed_when_positions_do_not_agree():
    # The structure lacks the leading M (so it can only be reached by alignment)
    # and its author numbering jumps between the two halves. Each half has its
    # own offset, so no single conversion may be stated.
    lines = []
    for offset, aa in enumerate(REFERENCE[1:]):
        author = offset + 1 if offset < 11 else offset + 40
        lines.append(
            f"ATOM  {offset + 1:5d}  CA  {THREE[aa]:>3s} A{author:4d}    "
            f"{float(offset):8.3f}{0.000:8.3f}{0.000:8.3f}  1.00 20.00           C"
        )
    lines.append("END")
    result = await residue_mapping_sifts(
        pdb_data="\n".join(lines) + "\n", chain_id="A",
        input_sequence="AAP" + REFERENCE,
    )

    assert result["source"] == "input_sequence_global_alignment"
    assert result["status"] == "completed"
    assert result["numbering_offset"] is None
    assert "偏移一致" not in result["report_boundary"]


def test_constant_offset_helper_refuses_ambiguous_mappings():
    from app.tools.residue_mapping_sifts import _constant_numbering_offset

    def row(user, author, chain="A", insertion=None):
        return {
            "user_sequence_position": user,
            "pdb_residue_no": author,
            "chain_id": chain,
            "insertion_code": insertion,
        }

    assert _constant_numbering_offset([row(1, 4), row(2, 5), row(3, 6)]) == 3
    assert _constant_numbering_offset([row(1, 1), row(2, 2)]) == 0
    assert _constant_numbering_offset([row(1, 4), row(2, 6)]) is None
    assert _constant_numbering_offset([row(1, 4), row(2, 5, insertion="A")]) is None
    assert _constant_numbering_offset([row(1, 4), row(2, 5, chain="B")]) is None
    assert _constant_numbering_offset([row(1, 4), {"pdb_residue_no": 5}]) is None
    assert _constant_numbering_offset([]) is None


async def test_exact_match_contract_unchanged():
    result = await map_sequence(REFERENCE)

    assert result["source"] == "input_sequence_exact_coordinate_mapping"
    assert result["capability_status"] == "verified_input_structure_mapping"
    assert result["evidence_level"] == "EXACT_SEQUENCE_COORDINATE_MAPPING"
    assert "逐残基一致" in result["report_boundary"]


async def test_blocked_default_contract_unchanged():
    result = await map_sequence("GGGGGGGGGGGGGGGGGGGGGGGG")

    assert result["status"] == "blocked"
    assert result["capability_status"] == "residue_mapping_qc"
    assert result["evidence_level"] == "NUMBERING_QC"
    assert UNMAPPED_BOUNDARY_TEXT in result["report_boundary"]


def test_contract_survives_missing_sequence_fields():
    # A bare success payload (no sequence_match/substitutions) must not crash.
    payload = _with_report_contract({"source": "input_sequence_global_alignment"})

    assert payload["capability_status"] == "aligned_user_sequence_mapping"
    # Static text only: no identity/coverage sentence, no substitution sentence.
    assert "本次比对一致性" not in payload["report_boundary"]
    assert "处差异" not in payload["report_boundary"]
    assert payload["report_boundary"].count("全局比对") == 1


def test_contract_ignores_empty_substitution_list():
    payload = _with_report_contract({
        "source": "input_sequence_global_alignment",
        "sequence_match": {"identity": 1.0, "coverage": 0.95},
        "sequence_substitutions": [],
    })

    assert "100.00%" in payload["report_boundary"]
    assert "95.00%" in payload["report_boundary"]
    assert "处差异" not in payload["report_boundary"]


async def test_unknown_structure_residues_are_excluded_not_mismatched():
    # Structure has UNK components (rendered as "X") at positions 5, 12 and 26;
    # the user FASTA carries the real residues there. Unknown residues are not
    # evidence of a substitution, so they must not depress identity or appear
    # in the substitution list.
    pdb_sequence = "MKTIIALSYFCLVFADYKDDDDKAAAAGGGGGG"
    assert len(pdb_sequence) == 33
    structure_sequence = "".join(
        "X" if offset in {4, 11, 25} else aa for offset, aa in enumerate(pdb_sequence)
    )
    assert structure_sequence.count("X") == 3

    result = await map_sequence(pdb_sequence, pdb_sequence=structure_sequence)

    assert result["status"] == "completed"
    assert result["source"] == "input_sequence_global_alignment"
    assert result["numbering_registry_status"] == "ready"
    match = result["sequence_match"]
    assert match["identity"] == 1.0
    assert match["coverage"] == 1.0
    assert match["identity_basis_count"] == 30
    assert result["mapping_count"] == 33
    assert result["sequence_substitutions"] == []
    unknown_positions = {5, 12, 26}
    assert {
        item["user_sequence_position"] for item in result["sequence_substitutions"]
    }.isdisjoint(unknown_positions)
    assert "处差异" not in result["report_boundary"]
    assert "可比对位点 30 个" in result["report_boundary"]


async def test_short_comparable_island_is_blocked_not_scored():
    # Only a 10-residue window of the structure consists of known residues;
    # the rest is UNK. The comparable island matches perfectly, which without
    # the basis floor would read as identity 1.0.
    island = "ACDEFGHIKL"
    structure_sequence = "X" * 13 + island + "X" * 13
    result = await map_sequence(
        "GGGGGGG" + island + "GGGGGGG", pdb_sequence=structure_sequence
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "INPUT_SEQUENCE_MISMATCH"
    assert "10 comparable aligned residues" in result["error"]
    assert "minimum 20" in result["error"]
    assert result["alignment"]["identity"] == 1.0
    assert result["alignment"]["identity_basis_count"] == 10
    assert result["mapping_count"] == 0
    assert result["numbering_registry_status"] == "blocked"
    assert UNMAPPED_BOUNDARY_TEXT in result["report_boundary"]


def test_contract_renders_basis_count_when_present():
    payload = _with_report_contract({
        "source": "input_sequence_global_alignment",
        "sequence_match": {"identity": 0.98, "coverage": 0.9, "identity_basis_count": 42},
    })

    assert "可比对位点 42 个" in payload["report_boundary"]
    assert "98.00%" in payload["report_boundary"]

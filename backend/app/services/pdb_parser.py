"""PDB file parser — extracts sequence, structure metadata, and quality metrics.

Pure Python, no external dependencies. Parses the standard PDB format (v3.30).
"""

from __future__ import annotations

import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from app.services.structure_records import cif_records, coordinate_summary, pdb_records


# Standard 3-letter to 1-letter amino acid mapping
_AA3TO1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    # Non-standard
    "MSE": "M", "SEC": "U", "PYL": "O", "HYP": "P",
    "ASX": "B", "GLX": "Z", "XLE": "J", "UNK": "X",
}

# PDB writes common covalently incorporated amino-acid variants as HETATM.
# Other HETATM records are ligands, ions, glycans, solvents, etc. and must not
# be counted as protein residues or converted to synthetic ``X`` chains.
_POLYMER_HETATM_RESIDUES = {"MSE", "SEC", "PYL", "HYP"}


@dataclass
class ChainInfo:
    chain_id: str
    sequence: str = ""
    residue_count: int = 0
    atom_count: int = 0
    residue_range: tuple[int, int] | None = None
    b_factors: list[float] = field(default_factory=list)


@dataclass
class PDBResult:
    header: dict[str, Any] = field(default_factory=dict)
    chains: list[ChainInfo] = field(default_factory=list)
    resolution: float | None = None
    r_factor: float | None = None
    space_group: str | None = None
    unit_cell: dict[str, float] | None = None
    b_factor_stats: dict[str, float] = field(default_factory=dict)
    total_atoms: int = 0
    total_residues: int = 0
    seqres_sequence: str = ""
    seqres_by_chain: dict[str, str] = field(default_factory=dict)
    method: str | None = None
    deposited_date: str | None = None
    nonpolymer_components: list[dict[str, Any]] = field(default_factory=list)
    compound_annotation: dict[str, str] = field(default_factory=dict)
    engineered_mutations: list[dict[str, Any]] = field(default_factory=list)
    theoretical_model: dict[str, Any] | None = None


def pdb_coordinate_text(content: str) -> str:
    """Give coordinate tools PDB records while preserving author chain numbering."""
    if not content.lstrip().startswith("data_"):
        return content
    from Bio.PDB import MMCIFParser, PDBIO

    structure = MMCIFParser(QUIET=True).get_structure("uploaded", io.StringIO(content))
    writer = PDBIO()
    writer.set_structure(structure)
    pdb_stream = io.StringIO()
    writer.save(pdb_stream)
    return pdb_stream.getvalue()


def _parse_mmcif(content: str) -> dict[str, Any]:
    """Read native mmCIF categories without reducing author chain identifiers."""
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict

    cif = MMCIF2Dict(io.StringIO(content))
    analysis = _to_dict(PDBResult())
    analysis.update(coordinate_summary(content, *cif_records(cif), _AA3TO1))

    def value(key: str) -> str | None:
        raw = cif.get(key)
        item = raw[0] if isinstance(raw, list) and raw else raw
        text = str(item).strip() if item is not None else ""
        return text if text and text not in {"?", "."} else None

    def number(key: str) -> float | None:
        raw = value(key)
        try:
            return float(raw) if raw is not None else None
        except ValueError:
            return None

    analysis["header"]["title"] = value("_struct.title")
    analysis["header"]["classification"] = value("_struct_keywords.pdbx_keywords")
    analysis["method"] = value("_exptl.method")
    analysis["resolution"] = number("_refine.ls_d_res_high")
    analysis["r_factor"] = number("_refine.ls_R_factor_R_work")
    analysis["space_group"] = value("_symmetry.space_group_name_H-M") or value("_space_group.name_H-M_alt")
    analysis["deposited_date"] = value("_pdbx_database_status.recvd_initial_deposition_date")
    cell_keys = {axis: number(f"_cell.length_{axis}") for axis in "abc"}
    angle_keys = {axis: number(f"_cell.angle_{axis}") for axis in ("alpha", "beta", "gamma")}
    if all(item is not None for item in (*cell_keys.values(), *angle_keys.values())):
        analysis["unit_cell"] = {**cell_keys, **angle_keys}
    # Keep source categories instead of silently dropping them during PDB conversion.
    for category, output in (
        ('_pdbx_unobs_or_zero_occ_residues.', 'unobserved_residues'),
        ('_pdbx_struct_assembly.', 'assemblies'),
        ('_pdbx_struct_assembly_gen.', 'assembly_generators'),
        ('_pdbx_struct_oper_list.', 'assembly_operations'),
    ):
        columns = {k[len(category):]: v if isinstance(v, list) else [v]
                   for k, v in cif.items() if k.startswith(category)}
        count = max((len(v) for v in columns.values()), default=0)
        analysis[output] = [{k: v[i] if i < len(v) else None for k, v in columns.items()} for i in range(count)]
    entities = cif.get('_entity_poly.pdbx_strand_id', [])
    sequences = cif.get('_entity_poly.pdbx_seq_one_letter_code_can', [])
    for strands, sequence in zip(entities, sequences):
        for chain in strands.split(','):
            analysis['seqres_by_chain'][chain.strip() or '_'] = re.sub(r'\s+', '', sequence)
    analysis['seqres_sequence'] = ''.join(analysis['seqres_by_chain'].values()) or None
    return analysis


def parse_pdb(content: str) -> dict[str, Any]:
    """Parse PDB file content into structured analysis data.

    Args:
        content: Raw PDB file text.

    Returns:
        Dict with chains, sequences, quality metrics, and structure metadata.
    """
    if content.lstrip().startswith("data_"):
        return _parse_mmcif(content)

    result = PDBResult()
    lines = content.splitlines()

    seqres_chains: dict[str, str] = defaultdict(str)
    compound_fragments: list[str] = []
    title_fragments: list[str] = []
    remark_fragments: list[str] = []

    for line in lines:
        record = line[:6].strip()

        if record == "HEADER":
            result.header["classification"] = line[10:50].strip() or None
            result.deposited_date = line[50:59].strip() or None

        elif record == "EXPDTA":
            result.method = _parse_method(line[10:].strip())

        elif record == "COMPND":
            compound_fragments.append(line[10:].strip())

        elif record == "SEQADV" and "ENGINEERED MUTATION" in line[49:].upper():
            try:
                result.engineered_mutations.append({
                    "chain_id": line[16].strip() or "_",
                    "pdb_residue_no": int(line[18:22]),
                    "pdb_residue_aa": line[12:15].strip(),
                    "reference_residue_aa": line[39:42].strip(),
                    "reference_position": int(line[43:48]),
                })
            except (IndexError, ValueError):
                pass

        elif record == "TITLE":
            title_fragments.append(line[10:].strip())

        elif record == "REMARK":
            _parse_remark(line, result)
            remark_num = line[7:10].strip()
            upper_line = line.upper()
            if (
                remark_num in {"99", "999", "4"}
                or "SWISS" in upper_line
                or "TEMPLATE" in upper_line
                or "GMQE" in upper_line
                or "QMEAN" in upper_line
            ) and len(remark_fragments) < 200:
                remark_fragments.append(line[11:].strip())

        elif record == "CRYST1":
            result.space_group = line[55:66].strip() or None
            try:
                result.unit_cell = {
                    "a": float(line[6:15]),
                    "b": float(line[15:24]),
                    "c": float(line[24:33]),
                    "alpha": float(line[33:40]),
                    "beta": float(line[40:47]),
                    "gamma": float(line[47:54]),
                }
            except ValueError:
                pass

        elif record == "SEQRES":
            chain_id = line[11].strip() or "_"
            if chain_id not in seqres_chains:
                seqres_chains[chain_id] = ""
            res_names = line[19:].split()
            for rn in res_names:
                normalized = rn.upper()
                if normalized in _AA3TO1:
                    seqres_chains[chain_id] += _AA3TO1[normalized]

    # SEQRES (full construct sequence)
    if seqres_chains:
        ordered = sorted(seqres_chains.keys())
        result.seqres_by_chain = dict(seqres_chains)
        result.seqres_sequence = "".join(seqres_chains[c] for c in ordered)

    if title_fragments:
        result.header["title"] = " ".join(title_fragments)

    compound_text = " ".join(compound_fragments)
    if len(re.findall(r"\bMOL_ID\s*:", compound_text, flags=re.IGNORECASE)) <= 1:
        for entry in compound_text.split(";"):
            key, separator, value = entry.partition(":")
            if separator and value.strip():
                result.compound_annotation[key.strip().lower()] = value.strip()

    analysis = {**_to_dict(result), **coordinate_summary(content, *pdb_records(content), _AA3TO1)}
    header_blob = " ".join(
        [result.header.get("title") or "", result.method or "", *remark_fragments]
    )
    analysis["theoretical_model"] = _parse_theoretical_model(
        result.method, header_blob, analysis.get("b_factor_stats")
    )
    semantics = analysis["theoretical_model"].get("b_factor_semantics")
    if not analysis["theoretical_model"].get("is_theoretical"):
        # Experimental structures keep the raw temperature factor column; a
        # prediction score only exists for predicted models.
        semantics = None
    analysis["b_factor_semantics"] = semantics
    if semantics == "model_quality_per_residue_score":
        analysis["b_factor_scope"] = (
            "theoretical model per-residue local quality score (0-1 scale); "
            "not a crystallographic temperature factor"
        )
    elif semantics == "plddt_confidence_score":
        analysis["b_factor_scope"] = (
            "predicted per-residue confidence (pLDDT, 0-100 scale); "
            "not a crystallographic temperature factor; >=90 confident, <50 low-confidence flexible region"
        )
    return analysis


def _parse_method(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    method_map = {
        "X-RAY": "X-RAY DIFFRACTION",
        "SOLUTION NMR": "SOLUTION NMR",
        "ELECTRON MICROSCOPY": "ELECTRON MICROSCOPY",
        "SOLID-STATE NMR": "SOLID-STATE NMR",
        "ELECTRON CRYSTALLOGRAPHY": "ELECTRON CRYSTALLOGRAPHY",
        "FIBER DIFFRACTION": "FIBER DIFFRACTION",
        "NEUTRON DIFFRACTION": "NEUTRON DIFFRACTION",
        "POWDER DIFFRACTION": "POWDER DIFFRACTION",
    }
    for key, val in method_map.items():
        if key in raw.upper():
            return val
    return raw


def _parse_remark(line: str, result: PDBResult) -> None:
    """Parse REMARK 2 (resolution) and REMARK 3 (R-factor)."""
    remark_num = line[7:10].strip()
    text = line[11:]

    if remark_num == "2":
        m = re.search(r"RESOLUTION\.\s+(\d+\.?\d*)\s+ANGSTROMS", text)
        if m and result.resolution is None:
            result.resolution = float(m.group(1))

    elif remark_num == "3":
        m = re.search(r"R VALUE\s+\(WORKING SET\)\s*:\s*(\d+\.?\d*)", text)
        if m and result.r_factor is None:
            result.r_factor = float(m.group(1))


_SWISS_MODEL_TEMPLATE_RE = re.compile(r"TEMPLATE[^\n]{0,48}?\b([0-9][A-Za-z0-9]{3})\b")
_SWISS_MODEL_GMQE_RE = re.compile(r"GMQE[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)")
_SWISS_MODEL_QMEAN_RE = re.compile(r"QMEAN(?!\s*Z)[^0-9\-]{0,10}(-?[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_SWISS_MODEL_QMEAN_Z_RE = re.compile(
    r"QMEAN\s*Z(?:[\s\-]*SCORE)?\s*:?\s*(-?[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE
)
_SWISS_MODEL_IDENTITY_RE = re.compile(r"(?:SEQUENCE\s+)?IDENTITY[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*%?")
_SWISS_MODEL_COVERAGE_RE = re.compile(r"(?:SEQUENCE\s+)?COVERAGE[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*%?")
_SWISS_MODEL_MARKER_RE = re.compile(r"SWISS[-\s]?MODEL|THEORETICAL\s+MODEL|HOMOLOGY[-\s]?MODEL", re.IGNORECASE)


def _fraction(raw: str | None) -> float | None:
    """Normalize a percentage-like token to 0-1; values already fractional pass through."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return round(value / 100.0, 3) if value > 1.0 else round(value, 3)


def _parse_theoretical_model(method: str | None, header_text: str, b_factor: dict[str, float] | None) -> dict[str, Any]:
    """Detect theoritical/homology models and extract their template evidence.

    SWISS-MODEL writes template id, GMQE, QMEAN and target-template identity in
    REMARK 99 (older exports: REMARK 999 / HEADER-TITLE text) with varying layouts,
    so matching is tolerant and anything not recognized stays explicitly unknown.
    The B-factor column of these files carries per-residue model quality (0-1
    scale), not a crystallographic temperature factor.
    """
    combined = " ".join(f"{method or ''} {header_text}".split())
    is_theoretical = bool(_SWISS_MODEL_MARKER_RE.search(combined))
    if not is_theoretical:
        return {"status": "not_theoretical", "is_theoretical": False}

    templates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _SWISS_MODEL_TEMPLATE_RE.finditer(combined):
        template_id = match.group(1).lower()
        if template_id in seen or template_id.isdigit():
            continue
        seen.add(template_id)
        templates.append({"template_id": template_id})

    model = {
        "status": "identified",
        "is_theoretical": True,
        "source": "SWISS-MODEL" if "swiss" in combined.lower() else "theoretical/homology model",
        "templates": templates,
        "gmqe": None,
        "qmean": None,
        "qmean_z": None,
        "template_sequence_identity": None,
        "template_coverage": None,
        "b_factor_semantics": None,
    }
    gmqe = _SWISS_MODEL_GMQE_RE.search(combined)
    if gmqe:
        model["gmqe"] = _fraction(gmqe.group(1))
    qmean = _SWISS_MODEL_QMEAN_RE.search(combined)
    if qmean:
        model["qmean"] = float(qmean.group(1))
    qmean_z = _SWISS_MODEL_QMEAN_Z_RE.search(combined)
    if qmean_z:
        model["qmean_z"] = float(qmean_z.group(1))
    identity = _SWISS_MODEL_IDENTITY_RE.search(combined)
    if identity:
        model["template_sequence_identity"] = _fraction(identity.group(1))
    coverage = _SWISS_MODEL_COVERAGE_RE.search(combined)
    if coverage:
        model["template_coverage"] = _fraction(coverage.group(1))
    if b_factor:
        model["b_factor_semantics"] = _theoretical_b_factor_semantics(b_factor)
    return model


def _theoretical_b_factor_semantics(b_factor: dict[str, float]) -> str:
    """Name what a predicted model's B-factor column carries.

    The column means different things per producer, and the numeric ranges are
    disjoint: SWISS-MODEL local quality is 0-1, AlphaFold pLDDT is 0-100 with a
    high mean, and anything else is an unclassified score that must not be
    presented as a confidence or temperature factor.
    """
    try:
        minimum = float(b_factor.get("min", 0.0))
        maximum = float(b_factor.get("max", 0.0))
        mean = float(b_factor.get("mean", 0.0))
    except (TypeError, ValueError):
        return "unclassified_score"
    if 0.0 <= minimum and maximum <= 2.0:
        # SWISS-MODEL local-quality scale; a crystallographic B-factor column
        # essentially never fits inside [0, 2].
        return "model_quality_per_residue_score"
    if 0.0 <= minimum and maximum <= 100.0 and mean >= 50.0:
        # AlphaFold pLDDT: 0-100 per residue, with a confident overall mean.
        return "plddt_confidence_score"
    return "unclassified_score"


def _to_dict(result: PDBResult) -> dict[str, Any]:
    return {
        "header": result.header,
        "chains": [
            {
                "chain_id": c.chain_id,
                "sequence": c.sequence,
                "residue_count": c.residue_count,
                "atom_count": c.atom_count,
                "residue_range": list(c.residue_range) if c.residue_range else None,
            }
            for c in result.chains
        ],
        "resolution": result.resolution,
        "r_factor": result.r_factor,
        "space_group": result.space_group,
        "unit_cell": result.unit_cell,
        "b_factor_stats": result.b_factor_stats or None,
        "b_factor_scope": (
            "protein_polymer_atoms_only; raw PDB temperature-factor column; interpretation depends on structure source"
            if result.b_factor_stats else None
        ),
        "total_atoms": result.total_atoms,
        "total_residues": result.total_residues,
        "seqres_sequence": result.seqres_sequence or None,
        "seqres_by_chain": result.seqres_by_chain,
        "nonpolymer_components": result.nonpolymer_components,
        "compound_annotation": result.compound_annotation,
        "engineered_mutations": result.engineered_mutations,
        "theoretical_model": result.theoretical_model,
        "method": result.method,
        "deposited_date": result.deposited_date,
    }

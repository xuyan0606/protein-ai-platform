from app.tools.gromacs_md import (
    _build_artifact_manifest,
    _build_analysis_selection_plan,
    _build_md_batch_replicate_summary,
    _build_md_interpretation,
    _build_replicate_execution_plan,
    _build_replicate_consistency,
    _classify_topology_warning,
    _prepare_point_mutant_pdbs,
    _parse_energy_terms,
    _parse_hbond_count,
    _parse_hbond_counts,
    _parse_xvg_multi_series,
    _run_step_with_selection_fallback,
    _scan_topology_warnings,
    _scan_structure_preparation,
    _validate_pdb_topology,
    gromacs_md,
)
from app.services.md_protocols import build_protocol_review, list_md_protocols, resolve_md_protocol_parameters


_MUTANT_PDB = """ATOM      1  N   MET A 204      11.104  13.207   8.678  1.00 20.00           N
ATOM      2  CA  MET A 204      12.104  13.207   8.678  1.00 20.00           C
ATOM      3  C   MET A 204      12.504  14.607   8.678  1.00 20.00           C
ATOM      4  O   MET A 204      13.504  14.807   8.678  1.00 20.00           O
ATOM      5  CB  MET A 204      12.204  12.107   9.678  1.00 20.00           C
ATOM      6  CG  MET A 204      12.304  10.707   9.678  1.00 20.00           C
ATOM      7  SD  MET A 204      12.404   9.307   9.678  1.00 20.00           S
TER       8      MET A 204
END
"""


def test_prepare_point_mutant_pdb_strips_incompatible_sidechain_and_marks_validation_required():
    result = _prepare_point_mutant_pdbs(_MUTANT_PDB, ["A:M204A"])

    mutant = result["mutants"][0]
    assert result["status"] == "prepared"
    assert mutant["status"] == "prepared"
    assert mutant["topology_readiness"] == "requires_topology_validation"
    assert mutant["metrics"]["matched_atom_count"] == 7
    assert mutant["metrics"]["removed_sidechain_atom_count"] == 2
    assert "ALA A 204" in mutant["pdb_data"]
    assert " SD  ALA" not in mutant["pdb_data"]
    assert mutant["topology_readiness"] != "validated"
    assert result["topology_policy"]["safe_for_ranking_without_validation"] is False


def test_prepare_point_mutant_pdb_blocks_ambiguous_residue_without_chain():
    pdb = _MUTANT_PDB.replace(" A 204", " B 204") + _MUTANT_PDB

    result = _prepare_point_mutant_pdbs(pdb, ["M204A"])

    mutant = result["mutants"][0]
    assert result["status"] == "blocked_or_partial"
    assert mutant["status"] == "blocked"
    assert mutant["blocked_reason"] == "ambiguous_residue_without_chain"
    assert mutant["pdb_data"] is None


def test_validate_pdb_topology_reports_unavailable_without_gromacs(monkeypatch):
    monkeypatch.setattr("app.tools.gromacs_md._find_gmx", lambda: None)

    result = _validate_pdb_topology(_MUTANT_PDB)

    assert result["status"] == "unavailable"
    assert result["error_code"] == "GROMACS_NOT_INSTALLED"
    assert result["topology_validated"] is False
    assert result["safe_for_ranking"] is False


def test_validate_pdb_topology_runs_pdb2gmx_and_detects_outputs(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "pdb2gmx completed\n"

    def fake_run(cmd, cwd, text, stdout, stderr, timeout, check):
        assert cmd[1] == "pdb2gmx"
        assert "-ff" in cmd
        (cwd / "processed.gro").write_text("Generated gro\n", encoding="utf-8")
        (cwd / "topol.top").write_text("Generated topology\n", encoding="utf-8")
        return Completed()

    monkeypatch.setattr("app.tools.gromacs_md._find_gmx", lambda: "/usr/bin/gmx")
    monkeypatch.setattr("app.tools.gromacs_md._resolve_force_field", lambda requested: (requested, [requested]))
    monkeypatch.setattr("app.tools.gromacs_md.subprocess.run", fake_run)

    result = _validate_pdb_topology(_MUTANT_PDB, force_field="amber99sb-ildn", water_model="tip3p")

    assert result["status"] == "validated"
    assert result["topology_validated"] is True
    assert result["safe_for_ranking"] is True
    assert result["outputs"] == {"processed_gro": True, "topol_top": True}
    assert result["topology_review"]["warning_count"] == 0


def test_artifact_manifest_groups_uploaded_md_outputs():
    artifacts = [
        {"name": "input.pdb", "size": 10, "object_name": "md/job/input.pdb"},
        {"name": "md.tpr", "size": 20, "object_name": "md/job/md.tpr"},
        {"name": "md.xtc", "size": 30, "object_name": "md/job/md.xtc"},
        {"name": "rmsd.xvg", "size": 40, "object_name": "md/job/rmsd.xvg"},
        {"name": "rmsd.csv", "size": 50, "object_name": "md/job/rmsd.csv"},
        {"name": "md.mdp", "size": 60, "object_name": "md/job/md.mdp"},
        {"name": "13_mdrun_md.log.txt", "size": 70, "object_name": "md/job/13_mdrun_md.log.txt"},
        {"name": "energy.xvg", "size": 80, "object_name": "md/job/energy.xvg"},
        {"name": "hbonds.csv", "size": 90, "object_name": "md/job/hbonds.csv"},
        {"name": "hbonds_solvent.csv", "size": 100, "object_name": "md/job/hbonds_solvent.csv"},
    ]

    manifest = _build_artifact_manifest(artifacts)

    assert manifest["version"] == 1
    assert manifest["total_count"] == 10
    assert manifest["total_size"] == 550
    assert manifest["counts"] == {
        "structures": 1,
        "topology": 1,
        "trajectory": 1,
        "analysis": 5,
        "parameters": 1,
        "logs": 1,
    }
    assert manifest["groups"]["trajectory"][0]["name"] == "md.xtc"
    assert manifest["groups"]["trajectory"][0]["category"] == "trajectory"


def test_artifact_manifest_omits_empty_groups():
    manifest = _build_artifact_manifest([])

    assert manifest == {
        "version": 1,
        "total_count": 0,
        "total_size": 0,
        "groups": {},
        "counts": {},
    }


def test_parse_energy_and_hbond_xvg_outputs(tmp_path):
    energy = tmp_path / "energy.xvg"
    energy.write_text(
        "\n".join(
            [
                "@ title \"Energy\"",
                "# time potential kinetic total",
                "0 -1000 200 -800",
                "1 -900 210 -690",
                "2 -1100 190 -910",
            ]
        ),
        encoding="utf-8",
    )
    hbonds = tmp_path / "hbonds.xvg"
    hbonds.write_text("@ title \"Hbonds\"\n0 11\n1 12\n2 13\n", encoding="utf-8")

    assert _parse_xvg_multi_series(energy) == [
        [0.0, -1000.0, 200.0, -800.0],
        [1.0, -900.0, 210.0, -690.0],
        [2.0, -1100.0, 190.0, -910.0],
    ]
    assert _parse_energy_terms(energy) == {
        "potential_energy_kjmol": -1000.0,
        "kinetic_energy_kjmol": 200.0,
        "total_energy_kjmol": -800.0,
    }
    assert _parse_hbond_counts(hbonds) == {
        "intra_protein_hbonds": 13,
        "protein_solvent_hbonds": None,
    }
    assert _parse_hbond_count(hbonds) == 13


def test_parse_energy_terms_uses_xvg_legends_when_columns_shift(tmp_path):
    energy = tmp_path / "energy.xvg"
    energy.write_text(
        "\n".join(
            [
                '@ s0 legend "Total-Energy"',
                '@ s1 legend "Potential"',
                '@ s2 legend "Kinetic-En."',
                "0 -800 -1000 200",
                "1 -700 -900 200",
            ]
        ),
        encoding="utf-8",
    )

    assert _parse_energy_terms(energy) == {
        "potential_energy_kjmol": -950.0,
        "kinetic_energy_kjmol": 200.0,
        "total_energy_kjmol": -750.0,
    }


def test_parse_energy_terms_accepts_real_gromacs_legend_aliases(tmp_path):
    energy = tmp_path / "energy_aliases.xvg"
    energy.write_text(
        "\n".join(
            [
                '@ s0 legend "Epot (kJ/mol)"',
                '@ s1 legend "Kinetic Energy"',
                '@ s2 legend "Etot"',
                "0 -100 20 -80",
                "1 -120 24 -96",
            ]
        ),
        encoding="utf-8",
    )

    assert _parse_energy_terms(energy) == {
        "potential_energy_kjmol": -110.0,
        "kinetic_energy_kjmol": 22.0,
        "total_energy_kjmol": -88.0,
    }


def test_analysis_selection_plan_uses_named_groups_and_energy_terms():
    plan = _build_analysis_selection_plan()

    assert plan["version"] == 2
    assert plan["group_selections"]["rms"] == ["Backbone", "Backbone"]
    assert plan["group_selections"]["hbond_protein_solvent"] == ["Protein", "SOL"]
    assert plan["energy_terms"] == ["Potential", "Kinetic-En.", "Total-Energy"]
    assert plan["group_selection_candidates"]["rms"][-1] == ["4", "4"]
    assert ["Potential-Energy", "Kinetic-Energy", "Total Energy"] in plan["energy_term_candidates"]
    assert plan["inputs"]["rms"] == "Backbone\nBackbone\n"
    assert plan["inputs"]["energy"] == "Potential\nKinetic-En.\nTotal-Energy\n\n"
    assert plan["fallback_inputs"]["hbond_protein_solvent"][1] == "Protein\nWater\n"
    assert plan["fallback_policy"]["numeric_groups_are_last_resort"] is True
    assert any("Named selections" in note for note in plan["notes"])


def test_run_step_with_selection_fallback_records_successful_fallback(tmp_path):
    attempts: list[str] = []

    def fake_run_step(step_number, name, cmd, input_text=None, timeout=1800):
        attempts.append(input_text)
        if input_text == "Backbone\nBackbone\n":
            raise RuntimeError("Group Backbone not found")
        (tmp_path / f"{name}.log.txt").write_text("ok", encoding="utf-8")

    result = _run_step_with_selection_fallback(
        fake_run_step,
        step_number=14,
        name="14_rms",
        cmd=["gmx", "rms"],
        candidate_inputs=["Backbone\nBackbone\n", "Protein\nProtein\n"],
        workdir=tmp_path,
    )

    assert result["status"] == "fallback"
    assert result["selected_index"] == 1
    assert attempts == ["Backbone\nBackbone\n", "Protein\nProtein\n"]
    assert "Group Backbone not found" in (tmp_path / "14_rms.selection_fallback.log.txt").read_text()


def test_run_step_with_selection_fallback_raises_after_all_candidates_fail(tmp_path):
    def fake_run_step(step_number, name, cmd, input_text=None, timeout=1800):
        raise RuntimeError(f"missing selection for {input_text!r}")

    try:
        _run_step_with_selection_fallback(
            fake_run_step,
            step_number=18,
            name="18_energy",
            cmd=["gmx", "energy"],
            candidate_inputs=["Potential\n\n", "Total\n\n"],
            workdir=tmp_path,
        )
    except RuntimeError as exc:
        assert "All selection candidates failed for 18_energy" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

    text = (tmp_path / "18_energy.selection_fallback.log.txt").read_text()
    assert "candidate[0]" in text
    assert "candidate[1]" in text


def test_topology_warning_classifier_uses_vocab():
    assert _classify_topology_warning("The sum of charge group radii is large") == {
        "category": "charge_balance",
        "severity": "warning",
    }
    assert _classify_topology_warning("missing atom type for ligand parameter") == {
        "category": "missing_atoms_or_parameters",
        "severity": "warning",
    }
    assert _classify_topology_warning("No default Proper Dih. types for residue") == {
        "category": "force_field_parameterization",
        "severity": "warning",
    }
    assert _classify_topology_warning("His protonation state should be checked") == {
        "category": "protonation_or_termini",
        "severity": "warning",
    }
    assert _classify_topology_warning("12 solvent molecules were replaced by ions") == {
        "category": "solvent_or_ion_setup",
        "severity": "warning",
    }
    assert _classify_topology_warning("benign informational line") == {
        "category": "unclassified",
        "severity": "info",
    }


def test_topology_warning_scan_extracts_gromacs_preprocessing_warnings(tmp_path):
    (tmp_path / "04_grompp_ions.log.txt").write_text(
        "\n".join(
            [
                "Some normal line",
                "WARNING 1 [file topol.top, line 12]:",
                "The sum of the two largest charge group radii is large",
                "NOTE: missing atoms were generated by pdb2gmx",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "13_mdrun_md.log.txt").write_text("WARNING: runtime warning should not be scanned here", encoding="utf-8")

    review = _scan_topology_warnings(tmp_path)

    assert review["warning_count"] == 2
    assert "gromacs_topology_warnings_present" in review["risk_flags"]
    assert "topology_charge_warning" in review["risk_flags"]
    assert "topology_missing_atom_or_parameter_warning" in review["risk_flags"]
    assert "topology_charge_balance_warning" in review["risk_flags"]
    assert "topology_missing_atoms_or_parameters_warning" in review["risk_flags"]
    assert review["entries"][0]["file"] == "04_grompp_ions.log.txt"
    assert review["entries"][0]["category"] == "charge_balance"


def test_structure_preparation_scan_flags_md_input_risks():
    pdb_text = "\n".join(
        [
            "REMARK 465   M RES C SSSEQI",
            "SSBOND   1 CYS A   10    CYS A   25",
            "ATOM      1  N  AHIS A   1      11.104  13.207   9.111  0.50 20.00           N",
            "ATOM      2  CA  HIS A   1      12.104  13.207   9.111  1.00 20.00           C",
            "ATOM      3  SG  CYS A  10      13.104  13.207   9.111  1.00 20.00           S",
            "HETATM    4  PA  NAD A 201      14.104  13.207   9.111  1.00 20.00           P",
            "HETATM    5 ZN    ZN A 202      15.104  13.207   9.111  1.00 20.00          ZN",
            "HETATM    6  O   HOH A 301      16.104  13.207   9.111  1.00 20.00           O",
        ]
    )

    scan = _scan_structure_preparation(pdb_text)

    assert scan["counts"]["atoms"] == 6
    assert scan["counts"]["hetatm"] == 3
    assert scan["counts"]["water_atoms"] == 1
    assert scan["counts"]["non_water_hetatm_atoms"] == 2
    assert scan["counts"]["alternate_location_atoms"] == 1
    assert scan["histidine_count"] == 1
    assert scan["cysteine_count"] == 1
    assert scan["hetero_residue_counts"]["NAD"] == 1
    assert scan["cofactor_counts"]["NAD"] == 1
    assert scan["ion_counts"]["ZN"] == 1
    assert set(scan["risk_flags"]) >= {
        "non_water_hetatm_present",
        "cofactor_like_residue_present",
        "metal_or_ion_present",
        "alternate_locations_present",
        "missing_residue_records_present",
        "histidine_protonation_review",
        "ssbond_records_present",
    }


def test_replicate_consistency_marks_single_run_insufficient_for_ranking():
    review = _build_replicate_consistency(
        wild_type_replicates=[{"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "rg_change_nm": 0.02, "is_stable": True}],
        minimum_replicates=3,
    )

    assert review["status"] == "insufficient_replicates"
    assert review["ranking_allowed"] is False
    assert review["groups"][0]["replicate_count"] == 1
    assert any(gate["metric"] == "WT:replicate_count" and gate["status"] == "missing" for gate in review["quality_gates"])


def test_replicate_consistency_passes_low_variance_wt_and_mutant_replicates():
    review = _build_replicate_consistency(
        wild_type_replicates=[
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "rg_change_nm": 0.02, "is_stable": True},
            {"rmsd_drift_nm": 0.05, "mean_rmsf_nm": 0.17, "rg_change_nm": 0.02, "is_stable": True},
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "rg_change_nm": 0.03, "is_stable": True},
        ],
        mutant_replicates=[
            {"variant": "M204H", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.18, "stability_delta": -0.12, "rmsf_change_mean": -0.02, "is_stable": True},
            {"variant": "M204H", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.17, "stability_delta": -0.10, "rmsf_change_mean": -0.03, "is_stable": True},
            {"variant": "M204H", "rmsd_drift_nm": 0.05, "mean_rmsf_nm": 0.18, "stability_delta": -0.11, "rmsf_change_mean": -0.02, "is_stable": True},
        ],
        minimum_replicates=3,
    )

    assert review["status"] == "consistent"
    assert review["ranking_allowed"] is True
    assert {group["variant"] for group in review["groups"]} == {"WT", "M204H"}
    assert all(gate["status"] == "pass" for gate in review["quality_gates"])


def test_replicate_consistency_fails_mutant_delta_direction_disagreement():
    review = _build_replicate_consistency(
        wild_type_replicates=[
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "is_stable": True},
            {"rmsd_drift_nm": 0.05, "mean_rmsf_nm": 0.17, "is_stable": True},
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "is_stable": True},
        ],
        mutant_replicates=[
            {"variant": "S265D", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.18, "stability_delta": -0.12, "rmsf_change_mean": -0.02},
            {"variant": "S265D", "rmsd_drift_nm": 0.07, "mean_rmsf_nm": 0.19, "stability_delta": 0.14, "rmsf_change_mean": -0.03},
            {"variant": "S265D", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.18, "stability_delta": -0.11, "rmsf_change_mean": 0.05},
        ],
        minimum_replicates=3,
    )

    assert review["status"] == "inconsistent"
    assert review["ranking_allowed"] is False
    assert any(gate["metric"] == "mutant_delta_direction" and gate["status"] == "fail" for gate in review["quality_gates"])


def test_replicate_execution_plan_builds_wt_and_mutant_tasks_without_running_md():
    plan = _build_replicate_execution_plan(
        protocol_id="engineering_short",
        parameters={
            "simulation_time_ns": 1.0,
            "equilibration_ps": 200.0,
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "ensemble": "npt",
        },
        variants=["M204H", {"mutation": "S265D"}],
        replicate_count=3,
        seed_base=5000,
    )

    assert plan["status"] == "planned"
    assert plan["variant_count"] == 3
    assert plan["total_tasks"] == 9
    assert plan["variants"] == ["WT", "M204H", "S265D"]
    assert plan["tasks"][0]["task_id"] == "WT:rep1"
    assert plan["tasks"][0]["seed"] == 5001
    assert plan["tasks"][3]["variant"] == "M204H"
    assert plan["tasks"][3]["requires_mutant_structure"] is True
    assert any("prepared mutant PDB" in warning for warning in plan["warnings"])


def test_md_batch_replicate_summary_ranks_consistent_mutants():
    summary = _build_md_batch_replicate_summary(
        wild_type_replicates=[
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "rg_change_nm": 0.02, "is_stable": True},
            {"rmsd_drift_nm": 0.05, "mean_rmsf_nm": 0.17, "rg_change_nm": 0.02, "is_stable": True},
            {"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16, "rg_change_nm": 0.03, "is_stable": True},
        ],
        mutant_replicates=[
            {"variant": "M204H", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.18, "stability_delta": -0.12, "rmsf_change_mean": -0.02, "is_stable": True},
            {"variant": "M204H", "rmsd_drift_nm": 0.06, "mean_rmsf_nm": 0.17, "stability_delta": -0.10, "rmsf_change_mean": -0.03, "is_stable": True},
            {"variant": "M204H", "rmsd_drift_nm": 0.05, "mean_rmsf_nm": 0.18, "stability_delta": -0.11, "rmsf_change_mean": -0.02, "is_stable": True},
            {"variant": "S265D", "rmsd_drift_nm": 0.07, "mean_rmsf_nm": 0.20, "stability_delta": -0.04, "rmsf_change_mean": 0.01, "is_stable": True},
            {"variant": "S265D", "rmsd_drift_nm": 0.07, "mean_rmsf_nm": 0.20, "stability_delta": -0.05, "rmsf_change_mean": 0.01, "is_stable": True},
            {"variant": "S265D", "rmsd_drift_nm": 0.08, "mean_rmsf_nm": 0.21, "stability_delta": -0.04, "rmsf_change_mean": 0.02, "is_stable": True},
        ],
        minimum_replicates=3,
    )

    assert summary["status"] == "ranking_ready"
    assert summary["ranking_allowed"] is True
    assert summary["candidate_count"] == 2
    assert summary["ranked_candidates"][0]["variant"] == "M204H"
    assert summary["ranked_candidates"][0]["ranking_ready"] is True
    assert summary["replicate_consistency"]["status"] == "consistent"


def test_gromacs_md_replicate_plan_only_does_not_require_gromacs():
    result = gromacs_md(
        protocol_id="engineering_short",
        replicate_plan_only=True,
        replicate_count=2,
        replicate_variants=["M204H"],
        simulation_time_ns=1.0,
        wild_type_replicates=[{"rmsd_drift_nm": 0.04, "mean_rmsf_nm": 0.16}],
    )

    assert result["status"] == "planned"
    assert result["is_real_md"] is False
    assert result["replicate_execution_plan"]["total_tasks"] == 4
    assert result["replicate_execution_plan"]["variants"] == ["WT", "M204H"]
    assert result["batch_replicate_summary"]["ranking_allowed"] is False
    assert result["protocol_review"]["protocol_id"] == "engineering_short"
    assert "no GROMACS command was executed" in result["note"]


def test_md_batch_replicate_summary_attaches_lipase_evidence(monkeypatch):
    def fake_lipase_context(**kwargs):
        return {
            "status": "ready",
            "requested_mutations": kwargs.get("mutations") or [],
            "requested_positions": [223],
            "exact_mutation_matches": [
                {
                    "mutation_code": "D223G",
                    "position": 223,
                    "paper_key": "Xie_2014",
                    "claim_group": "kinetic_stability",
                    "evidence_level": "article_level",
                }
            ],
            "position_matches": [{"mutation_code": "D223G", "position": 223, "paper_key": "Xie_2014"}],
            "counts": {"exact_mutation_matches": 1, "position_matches": 1, "search_matches": 0},
        }

    monkeypatch.setattr("app.tools.gromacs_md.build_lipase_evidence_context", fake_lipase_context)
    wild_type = [
        {"variant": "WT", "rmsd_drift_nm": 0.12, "mean_rmsf_nm": 0.22, "is_stable": True},
        {"variant": "WT", "rmsd_drift_nm": 0.11, "mean_rmsf_nm": 0.21, "is_stable": True},
        {"variant": "WT", "rmsd_drift_nm": 0.13, "mean_rmsf_nm": 0.23, "is_stable": True},
    ]
    mutant = [
        {"variant": "D223G", "rmsd_drift_nm": 0.09, "mean_rmsf_nm": 0.18, "stability_delta": -0.03, "rmsf_change_mean": -0.04, "is_stable": True},
        {"variant": "D223G", "rmsd_drift_nm": 0.08, "mean_rmsf_nm": 0.17, "stability_delta": -0.04, "rmsf_change_mean": -0.05, "is_stable": True},
        {"variant": "D223G", "rmsd_drift_nm": 0.10, "mean_rmsf_nm": 0.19, "stability_delta": -0.02, "rmsf_change_mean": -0.03, "is_stable": True},
    ]

    summary = _build_md_batch_replicate_summary(
        wild_type_replicates=wild_type,
        mutant_replicates=mutant,
        minimum_replicates=3,
    )

    assert summary["ranking_allowed"] is True
    assert summary["lipase_evidence_context"]["status"] == "ready"
    candidate = summary["ranked_candidates"][0]
    assert candidate["variant"] == "D223G"
    assert candidate["lipase_evidence"]["exact_match_count"] == 1
    assert candidate["lipase_evidence"]["position_match_count"] == 1


def test_md_batch_replicate_summary_blocks_candidate_without_safe_topology():
    wild_type = [
        {"variant": "WT", "rmsd_drift_nm": 0.10, "mean_rmsf_nm": 0.20, "is_stable": True},
        {"variant": "WT", "rmsd_drift_nm": 0.11, "mean_rmsf_nm": 0.21, "is_stable": True},
        {"variant": "WT", "rmsd_drift_nm": 0.09, "mean_rmsf_nm": 0.19, "is_stable": True},
    ]
    mutant = [
        {
            "variant": "M204A",
            "rmsd_drift_nm": 0.08,
            "mean_rmsf_nm": 0.18,
            "stability_delta": -0.03,
            "rmsf_change_mean": -0.04,
            "is_stable": True,
            "topology_validation": {"topology_validated": True, "safe_for_ranking": False},
        },
        {
            "variant": "M204A",
            "rmsd_drift_nm": 0.07,
            "mean_rmsf_nm": 0.17,
            "stability_delta": -0.04,
            "rmsf_change_mean": -0.05,
            "is_stable": True,
            "topology_validation": {"topology_validated": True, "safe_for_ranking": False},
        },
        {
            "variant": "M204A",
            "rmsd_drift_nm": 0.09,
            "mean_rmsf_nm": 0.19,
            "stability_delta": -0.02,
            "rmsf_change_mean": -0.03,
            "is_stable": True,
            "topology_validation": {"topology_validated": True, "safe_for_ranking": False},
        },
    ]

    summary = _build_md_batch_replicate_summary(
        wild_type_replicates=wild_type,
        mutant_replicates=mutant,
        minimum_replicates=3,
    )

    assert summary["status"] == "ranking_blocked"
    assert summary["ranking_allowed"] is False
    assert summary["blocked_candidate_count"] == 1
    assert summary["ranked_candidates"] == []
    candidate = summary["candidates"][0]
    assert candidate["ranking_score"] is not None
    assert candidate["ranking_ready"] is False
    assert candidate["blocked_reasons"] == ["mutant_topology_not_safe_for_ranking"]
    assert any(gate["metric"] == "mutant_topology_validation" and gate["status"] == "blocked" for gate in candidate["quality_gates"])


def test_md_interpretation_marks_short_stable_smoke_run():
    interpretation = _build_md_interpretation(
        rmsd_final=0.22,
        rmsd_drift=0.04,
        mean_rmsf=0.16,
        max_rmsf=0.31,
        rg_initial=2.1,
        rg_final=2.12,
        sasa_initial=180.0,
        sasa_final=181.0,
        flexible_regions=[{"residues": "12", "mean_rmsf_nm": 0.31}],
        simulation_time_ns=0.1,
        protocol_review={"review_warnings": ["Replicate policy is below ranking-grade."], "scientific_controls": {"replicate_policy": {"minimum_for_ranking": 3}}},
        energetics={"potential_energy_kjmol": None},
        interactions={"intra_protein_hbonds": None},
        analysis_files={"energy_edr": False, "rmsd_xvg": True},
        structure_preparation={
            "risk_flags": ["cofactor_like_residue_present"],
            "warnings": ["Common cofactor-like residues were detected; verify retained cofactors."],
        },
        replicate_consistency={
            "ranking_allowed": False,
            "group_count": 1,
            "minimum_replicates": 3,
            "warnings": ["WT has 1 replicate(s); ranking requires at least 3."],
            "recommended_next_steps": ["Run enough WT and mutant replicates before ranking candidates."],
        },
        topology_review={
            "warning_count": 1,
            "risk_flags": ["gromacs_topology_warnings_present"],
            "warnings": ["1 GROMACS topology/preprocessing warning(s) detected; inspect grompp/pdb2gmx logs."],
        },
    )

    assert interpretation["verdict"] == "stable_short_run"
    assert interpretation["confidence"] == "low"
    assert interpretation["evidence_level"] == "smoke"
    assert "conclusion" in interpretation
    assert interpretation["metric_snapshot"]["rmsd_drift_nm"] == 0.04
    assert any(gate["metric"] == "rmsd_drift_nm" and gate["status"] == "pass" for gate in interpretation["quality_gates"])
    assert any("shorter than 1 ns" in warning for warning in interpretation["warnings"])
    assert interpretation["protocol_review"]["review_warnings"][0] == "Replicate policy is below ranking-grade."
    assert any("3 replicates" in step for step in interpretation["recommended_next_steps"])
    assert any(item["metric"] == "energy_edr" for item in interpretation["missing_evidence"])
    assert any(item["metric"] == "potential_energy_kjmol" for item in interpretation["missing_evidence"])
    assert any(item["metric"] == "cofactor_like_residue_present" for item in interpretation["missing_evidence"])
    assert any(item["metric"] == "replicate_consistency" for item in interpretation["missing_evidence"])
    assert any(item["metric"] == "gromacs_topology_warnings_present" for item in interpretation["missing_evidence"])
    assert any(gate["metric"] == "energy_edr" and gate["status"] == "missing" for gate in interpretation["quality_gates"])
    assert any("structure-preparation risk flags" in step for step in interpretation["recommended_next_steps"])
    assert any("topology/preprocessing warnings" in step for step in interpretation["recommended_next_steps"])


def test_md_interpretation_flags_high_rmsd_drift():
    interpretation = _build_md_interpretation(
        rmsd_final=0.8,
        rmsd_drift=0.42,
        mean_rmsf=0.5,
        max_rmsf=0.9,
        rg_initial=2.1,
        rg_final=2.4,
        sasa_initial=180.0,
        sasa_final=210.0,
        flexible_regions=[],
        simulation_time_ns=5.0,
    )

    assert interpretation["verdict"] == "unstable_or_unconverged"
    assert interpretation["confidence"] == "medium"
    assert interpretation["evidence_level"] == "screening"
    assert any("RMSD drift is high" in finding for finding in interpretation["findings"])
    assert any(gate["status"] == "fail" for gate in interpretation["quality_gates"])
    assert any("Do not rank" in step for step in interpretation["recommended_next_steps"])


def test_md_protocol_templates_include_safe_default():
    payload = list_md_protocols()

    assert payload["version"] == 1
    assert payload["default_protocol_id"] == "smoke_short"
    assert {protocol["id"] for protocol in payload["protocols"]} >= {
        "smoke_short",
        "engineering_short",
        "production_review",
    }
    production = next(protocol for protocol in payload["protocols"] if protocol["id"] == "production_review")
    assert production["scientific_controls"]["replicate_policy"]["minimum_for_ranking"] == 3
    assert production["parameters"]["coulombtype"] == "PME"
    assert production["parameters"]["constraint_algorithm"] == "lincs"


def test_md_protocol_resolution_applies_allowed_overrides_only():
    resolved = resolve_md_protocol_parameters(
        "smoke_short",
        {
            "simulation_time_ns": 0.2,
            "force_field": "amber99sb-ildn",
            "unsafe_shell": "rm -rf /",
        },
    )

    assert resolved["protocol_id"] == "smoke_short"
    assert resolved["parameters"]["simulation_time_ns"] == 0.2
    assert resolved["parameters"]["force_field"] == "amber99sb-ildn"
    assert resolved["protocol_review"]["protocol_id"] == "smoke_short"
    assert resolved["protocol_review"]["scientific_controls"]["cutoff_policy"]["coulombtype"] == "PME"
    assert "unsafe_shell" not in resolved["parameters"]


def test_protocol_review_flags_short_non_ranking_runs():
    review = build_protocol_review(
        "smoke_short",
        {
            "simulation_time_ns": 0.1,
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "ensemble": "npt",
        },
    )

    assert review["risk_level"] == "low_runtime_low_scientific_confidence"
    assert review["requires_expert_review"] is False
    assert any("below 1 ns" in warning for warning in review["review_warnings"])

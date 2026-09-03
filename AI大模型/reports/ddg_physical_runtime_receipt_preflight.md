# P145 ddG Physical Runtime Receipt Preflight

Created: `2026-09-03T07:33:45.179544+00:00`

This is a fail-closed scaffold. It does not install Rosetta/PyRosetta/FoldX, enable config, write a formal runtime receipt, run a physical ddG smoke job, or connect the safe pipeline/manifest.

## Summary

- Physical backend rows: 3
- Runtime receipt rows: 2
- Missing license rows: 1
- Missing install path/module rows: 1
- Missing config-enabled rows: 1
- Missing probe rows: 1
- Missing smoke artifact rows: 1
- Ready to write formal receipt rows: 2

| Backend | License | Install path/module | Config enabled | Probe | Smoke artifact | Status |
| --- | --- | --- | --- | --- | --- | --- |
| rosetta | present | present | present | present | present | runtime_receipt_validated_ready |
| pyrosetta | present | present | present | present | present | runtime_receipt_validated_ready |
| foldx | missing | missing | missing | missing | missing | blocked_missing_preflight_evidence |

## Backend Details

### rosetta

- License missing: none
- Install path/module missing: none
- Config enabled missing: none
- Probe missing: none
- Smoke artifact missing: none
- Runtime receipt missing: none

### pyrosetta

- License missing: none
- Install path/module missing: none
- Config enabled missing: none
- Probe missing: none
- Smoke artifact missing: none
- Runtime receipt missing: none

### foldx

- License missing: runtime_receipt_license_decision_reviewed
- Install path/module missing: runtime_receipt_install_path, runtime_receipt_executable_paths
- Config enabled missing: runtime_receipt_config_enabled_reviewed
- Probe missing: runtime_receipt_probe_evidence_reviewed
- Smoke artifact missing: runtime_receipt_smoke_plan_reviewed, runtime_receipt_smoke_artifact_paths, runtime_receipt_smoke_artifact_sha256, parameters.json, input_structure.sha256, mutation_list.json, ddg_table.json, runtime.log
- Runtime receipt missing: approved_runtime_receipt

## Policy

Blocked actions: do_not_install_or_enable_unapproved_rosetta_pyrosetta_or_foldx, do_not_write_unreviewed_formal_runtime_receipt, do_not_execute_unreceipted_rosetta_pyrosetta_or_foldx, do_not_import_computed_ddg_as_training_label, do_not_set_model_or_release_claims_from_runtime_smoke

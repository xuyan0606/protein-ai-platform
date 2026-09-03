# CM5 L262V Discrepancy Adjudication Packet

Status: `needs_more_info`

Declared substitutions: `L15R,S45T,K85P,K231R`
Observed conflict: WT codon 262 `TTG` / CM5 read `GTG` / CM5 PDB `LEU` / WT PDB `LEU`.

The eight TTG calls are from other constructs. They provide WT-context evidence but are not independent CM5 replicates and cannot resolve CM5 composition.

| Read | Evidence role | Codon 262 | Counts as CM5 independent replicate |
|---|---|---:|---:|
| `CM5 (L15R_S45T_K85P_K231R).seq` | `cm5_direct_read` | `GTG` | `false` |
| `E70Q_T201D.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `K85P_K170Y.seq` | `other_construct_no_codon262_coverage` | `None` | `false` |
| `K85P_K231R.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `K85P_K431T_F.seq` | `other_construct_no_codon262_coverage` | `None` | `false` |
| `K85P_K431T_R.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `L15R_S45T.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `L15R_S45T_K85P_K231Q_K280S.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `L15R_S45T_K85P_K231R_K280S.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `L15R_S45T_K85P_K231V.seq` | `other_construct_wt_context` | `TTG` | `false` |
| `S45T_N113K_D167K.seq` | `other_construct_wt_context` | `TTG` | `false` |

CM5 independent replicate rows: `0`
Reviewed raw trace rows: `0`
Quality-bearing artifact rows: `0`

## Allowed Adjudication Options

- `needs_more_info`: Keep the discrepancy open while any decisive CM5-specific evidence is missing
- `confirm_L262V_in_CM5_construct`: Reviewed CM5 raw trace with per-base quality supporting GTG at codon 262 or independent CM5 clone resequencing supporting GTG; Reviewed complete CM5 construct record including L262V; Reviewed reconciliation of the CM5 nucleotide call with the LEU262 PDB model
- `reject_L262V_as_sequence_artifact`: Reviewed CM5 raw trace demonstrating an unreliable or incorrect GTG call or independent CM5 clone resequencing supporting TTG; Reviewed explanation linking the corrected sequence to the CM5 construct and LEU262 PDB model
- `confirm_construct_or_model_version_mismatch`: Reviewed provenance linking the sequence read, physical CM5 construct, and PDB model to distinct versions; Reviewed complete composition decision for each version

## Reviewer Fields

- Adjudication decision: [blank]
- Reviewer: [blank]
- Reviewed at: [blank]
- Reviewed source locator: [blank]
- Decision basis: [blank]
- Review notes: [blank]

`discrepancy_resolved=false`; `complete_composition_unambiguous=false`; `reviewed_extraction_completed=false`; `ready_for_sqlite_apply=false`; `apply_executed=false`; `safe_for_model_claim=false`; `release_ready=false`.

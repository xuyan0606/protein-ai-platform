# Google/GitHub Advanced Model Research 2026-07-28

## Verdict

KWB-EnzymeDesigner is not yet a claimable top-tier model. The local code now has
advanced architecture and adapter landing zones, but the decisive evidence is
still missing: real MSA/cache, reviewed numbering, reviewed structure graph,
validated ddG/kinetics artifacts, external benchmark scorecards and KWB wet-lab
feedback calibration.

## What Changed This Round

This round updates the advanced model roadmap with newer or stronger external
signals found through Google/GitHub research.

## Recommended Priority

### P0: unblock model evidence

- MMseqs2 or trusted MSA cache: first unlock for conservation, mutation effect
  and OOD risk.
- Reviewed structure graph: convert chain-reviewed structures into residue
  neighborhoods, protected-site flags and structure-token inputs.
- ProteinGym benchmark cache: external mutation-effect scorecards before any
  top-tier claim.
- KWB wet-lab feedback: plate/well-level calibration remains the strongest
  defensible data moat.

### P1: add high-value external predictors

- Boltz-2: commercial-friendly structure and affinity adapter candidate.
- ThermoMPNN/ThermoMPNN-D: stability proxy and double-mutant stress-test
  candidate; still not a Rosetta/FoldX replacement.
- ESMC/SaProt/ProSST/ProstT5: sequence/structure-aware representation adapter
  candidates, with license gates per model and weight.
- CatPred: kcat/Km/Ki kinetics adapter candidate using sequence, structure and
  substrate SMILES.

### P2: generate candidates only after gates

- LigandMPNN/ProteinMPNN: structure-conditioned sequence generation/scoring.
- RFdiffusion2: enzyme active-site scaffolding route; must be blocked behind
  protected-site policy, biosecurity screening, human approval and experiment
  budget gates.

## Tool-Specific Findings

| Tool/model | Role | Commercial posture | KWB action |
|---|---|---|---|
| MMseqs2 | MSA/search/conservation | GitHub reports MIT, but package channels may differ | Build runtime + database/cache validator first |
| ESMC/ESM3 | sequence PLM and folding/design | license depends on exact model/weight/API route | Keep per-weight license gate; do not assume all ESM routes are commercial-ready |
| SaProt | structure-aware PLM | needs structure/3Di tokens and license review | Add structure-token cache before use |
| ProSST | structure-token PLM | GPL-3.0 in visible repo | Isolate from closed-source commercial mainline unless legal approves |
| Boltz-2 | complex structure + affinity | MIT code and weights per upstream | Best P1 structure/affinity adapter candidate |
| Chai-1 | multimodal structure prediction | Apache-2.0, but Linux/CUDA/bfloat16 heavy | Keep as Linux-CUDA benchmark/alternative |
| AlphaFold 3 | broad biomolecular structure | non-commercial source/weights terms | Benchmark/isolation only, not commercial mainline |
| ThermoMPNN | point-mutant ddG proxy | MIT | Add after reviewed structures exist |
| ThermoMPNN-D | double-mutant stability stress test | MIT | Use for epistasis risk, not single score replacement |
| Rosetta/PyRosetta/FoldX | physics/stability ddG | license/commercial gates required | Keep optional backend until license/runtime artifacts exist |
| CatPred | enzyme kcat/Km/Ki | MIT code | Strong kinetics/function adapter candidate |
| ProteinGym | mutation-effect benchmark | MIT/open data route | Build benchmark cache and no-leak split report |
| LigandMPNN/ProteinMPNN | ligand/backbone-conditioned sequence generation | MIT lineage visible for ProteinMPNN; verify LigandMPNN package terms | Candidate generation only after review gates |
| RFdiffusion2 | enzyme active-site scaffold generation | public GitHub route, license must be reviewed | P2 only; never auto-order sequences |

## Engineering Decisions

- Do not install or execute any external model in this research round.
- Do not upgrade any adapter from `blocked` to `ready` based on search results.
- Add explicit `linux_cuda_ready`, `license_ready`, `model_weight_ready`,
  `database_or_cache_ready`, `artifact_checksum_ready` and `validator_ready`
  gates before execution.
- Keep AlphaFold 3 and non-commercial/research-use tools outside the commercial
  mainline until legal review is complete.
- Treat RFdiffusion2 and LigandMPNN as candidate-generation tools, not ranking
  truth. Generated candidates still require protected-site review, ΔΔG/kinetics
  evidence, biosecurity screening, human approval and wet-lab validation.

## Sources

- https://github.com/jwohlwend/boltz
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12262699/
- https://github.com/evolutionaryscale/esm
- https://www.evolutionaryscale.ai/policies/terms-of-use
- https://www.evolutionaryscale.ai/policies/cambrian-open-license-agreement
- https://www.evolutionaryscale.ai/policies/cambrian-non-commercial-license-agreement
- https://github.com/westlake-repl/SaProt
- https://github.com/openmedlab/ProSST
- https://github.com/soedinglab/MMseqs2
- https://github.com/Kuhlman-Lab/ThermoMPNN
- https://github.com/Kuhlman-Lab/ThermoMPNN-D
- https://github.com/maranasgroup/CatPred
- https://www.nature.com/articles/s41467-025-57215-9
- https://github.com/OATML-Markslab/ProteinGym
- https://registry.opendata.aws/proteingym/
- https://github.com/chaidiscovery/chai-lab
- https://huggingface.co/chaidiscovery/chai-1
- https://github.com/google-deepmind/alphafold3
- https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md
- https://github.com/dauparas/LigandMPNN
- https://github.com/RosettaCommons/RFdiffusion2
- https://rosettacommons.org/2025/09/15/rfdiffusion2-is-now-available-on-github/

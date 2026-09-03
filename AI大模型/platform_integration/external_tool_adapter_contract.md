# External Tool Adapter Contract

This contract keeps foreign tools as local evidence providers. GPT-5.6 remains the platform controller, and KWB-EnzymeDesigner remains the unified expert model surface.

## Adapter Rules

- Every external tool must pass license gating before commercial production use.
- Tool outputs are evidence, not wet-lab labels.
- Predicted structures and affinities must be labeled as predicted evidence.
- Generated candidates must pass KWB ranking, catalytic guardrails, numbering checks, and experimental planning before recommendation.
- Non-commercial or restricted tools stay benchmark-only unless legal review explicitly clears usage.

## Priority Adapters

1. `mmseqs2`: MSA/conservation feature production.
2. `boltz2`: complex structure and binding affinity proxy.
3. `chai1`: complex structure comparison backend.
4. `thermompnn`: stability baseline and ddG proxy features.
5. `clean`: EC/function consistency evidence.
6. `ligandmpnn`: ligand-aware candidate generation after structure mapping is reviewed.

## Result Envelope

Adapters must emit `contracts/external_tool_adapter.schema.json` compatible results. The evidence level must be explicit so the UI can separate sequence-only, predicted-structure, experimental-structure, MSA-supported, and wet-lab-supported conclusions.

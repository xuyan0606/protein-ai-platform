# Workflow Catalog

## WF-STABILITY

### Purpose
Optimize or preserve enzyme stability while keeping activity loss controlled.

### Entry rule
This workflow is only a top-level router label. The tool-level implementation, mandatory/optional/forbidden tool map, and execution order are defined in `references/stability_workflow.md`.

### Forbidden steps
- Default substrate-specific redesign unless specificity is also a declared target.
- Unspecified multi-objective branching.
- Using the generic stability description instead of the stability-specific tool map.

## WF-PH

### Purpose
Optimize pH optimum, target-pH activity, pH window, or acid/base tolerance.

### Entry rule
This workflow is only a top-level router label. The tool-level implementation, mandatory/optional/forbidden tool map, and execution order are defined in `references/ph_workflow.md`.

### Forbidden steps
- Routing ordinary heat stability, solvent tolerance, or protease tolerance into the pH path.
- Using surface pI alone as proof of pH optimum shift.
- Reusing the stability tool map instead of the pH-specific tool map.

## WF-ACTIVITY

### Purpose
Improve catalytic output or reaction efficiency.

### Entry rule
This workflow is only a top-level router label. The tool-level implementation, mandatory/optional/forbidden tool map, and execution order are defined in `references/activity_workflow.md`.

### Forbidden steps
- Treating stability screening as a substitute for catalytic analysis.
- Reusing specificity workflow without explicit specificity demand.
- Using the generic activity description instead of the activity-specific tool map.

## WF-SPECIFICITY

### Purpose
Change substrate preference, selectivity, or regio-/stereoselectivity.

### Entry rule
This workflow is only a top-level router label. The tool-level implementation, mandatory/optional/forbidden tool map, and execution order are defined in `references/specificity_workflow.md`.

### Forbidden steps
- Using general activity gain as the sole success criterion.
- Skipping off-target definition.
- Using the generic specificity description instead of the specificity-specific tool map.

## WF-EXPRESSION

### Purpose
Improve expression, solubility, secretion, or folding.

### Entry rule
This workflow is only a top-level router label. The tool-level implementation, mandatory/optional/forbidden tool map, and execution order are defined in `references/expression_workflow.md`.

### Forbidden steps
- Replacing expression optimization with activity optimization.
- Redesigning catalytic core unless explicitly constrained.
- Using the generic expression description instead of the expression-specific tool map.

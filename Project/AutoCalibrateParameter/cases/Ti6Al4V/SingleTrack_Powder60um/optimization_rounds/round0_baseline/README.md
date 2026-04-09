# Round 0 Baseline

This directory captures the pre-campaign optimization state before starting the guided three-round continuation.

- Source case: `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um`
- History rows: 15
- Best iteration: 8
- Best objective: 27.81776329331189
- Best parameters:
  - `sigma = 1.0`
  - `Marangoni_Constant = -0.0004`

Reason for round 1 changes:
- The best point sits on both the lower `sigma` bound and the more-negative `Marangoni_Constant` bound.
- The sampled landscape suggests improvement toward lower `sigma` and more-negative marangoni values.
- Round 1 therefore expands those bounds while preserving all existing warmstart samples.

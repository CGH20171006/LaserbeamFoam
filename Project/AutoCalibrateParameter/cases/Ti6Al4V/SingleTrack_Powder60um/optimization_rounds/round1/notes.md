# Round 1 Notes

## Hypothesis
The optimizer has already shown its best performance at the low-sigma and more-negative-marangoni boundary. Expanding that corner should give the EI acquisition function a chance to sample a better region without discarding prior information.

## Changes from baseline
- `sigma_bounds`: `[1.0, 2.0]` -> `[0.8, 2.0]`
- `marangoni_bounds`: `[-4e-4, -1e-6]` -> `[-6e-4, -1e-6]`
- `n_initial_points`: `5` -> `15` so the current warmstart history is treated as the starting sample set
- `n_batches`: `10` -> `1` for one guided round at a time

## Success criteria
- The round adds exactly one new row to `round1/runs/bayes_history-Ti64.csv`.
- Best objective improves below `27.81776329331189`, or at minimum the new point confirms whether the beneficial direction is further down/left.

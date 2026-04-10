# Findings & Decisions

## Requirements
- Guide and execute three additional optimization rounds for `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um`.
- Preserve a snapshot for each round.
- Adjust configuration and strategy based on the observed Bayesian optimization results after each round.

## Research Findings
- The repository includes a case-specific visualization script named `visualize_meltpool.py` in the target case directory.
- Planning-with-files session bootstrap script was unavailable at the default plugin path in this environment, so planning files were initialized manually.
- `visualize_meltpool.py` must be run with `pvpython`; it scans `runs/<run_id>/<power>/0.0003/meltHistory`, creates missing `constant`/`system` symlinks in each run case, and saves PNGs into `visualization_output/<run_id>/<power>_meltHistory.png`.
- The case config points `pvpython` to `pvpython`, optimizes only `sigma` and `marangoni`, and uses `bayes_history-Ti64.csv` as the warm-start/history source.
- The history CSV currently has 15 rows with objective values and meltpool metrics at 300W/400W/500W.
- `pvpython` is available at `/home/cgh/miniconda3/bin/pvpython`.
- The `runs` directory contains numeric run folders `1` through `15`, each with `300W`, `400W`, and `500W`; the visualization script will therefore attempt 45 case renders.
- The current best history entry is row 7 with objective `27.81776329331189`, at `sigma=1.0` and `Marangoni_Constant=-0.0004`. No later row improves on that best value.
- Running `pvpython visualize_meltpool.py` from the case directory completed successfully and generated all 45 expected PNGs in `visualization_output/`.
- Experimental targets from `SingleTrackExperimentalData.csv` are substantially larger than the current best simulated widths/depths, especially at 500W.
- The latest sampled point (run 15) is notably worse than the best point (run 8), indicating the search has not monotonically converged and recent exploration moved away from the current optimum.
- The sampled objective landscape shows the best points clustered near the lower sigma bound and the more-negative marangoni bound, which supports expanding the search region toward lower `sigma` and more negative `Marangoni_Constant`.
- The case-local `main.py` is a wrapper around `PyMeltpoolCalib.run_cli.main`, so the stable launch command is `python3 main.py --method bayes --config <config> --output-dir <runs_dir>`.
- Config YAML paths are resolved relative to the YAML file location, so round-specific configs stored outside the case directory must use absolute paths for `case_dir`, `exp_csv`, `postproc_script`, and `runs_root`.
- The package had an import-time coupling bug: `bayes` startup failed because `PyMeltpoolCalib` eagerly imported ACBICI-dependent modules (`optimizer_acbici`, `meltpool_model`) even when only Bayesian optimization was requested.
- A minimal optional-import fix in `PyMeltpoolCalib/__init__.py`, `optimizers/__init__.py`, and `models/__init__.py` restored `python3 main.py --help` and unblocked the Bayesian workflow without requiring the `ACBICI` package.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Start from the case directory and inspect the script before running it | Case-local scripts often depend on relative paths for config/history/output files |
| Cross-check script output with `bayes_history-Ti64.csv` | The user asked about optimization status, which is best inferred from both visuals and numeric history |
| Run one new Bayesian batch per round | This gives us a chance to re-steer search bounds and settings after each fresh sample |
| Store each new round in a dedicated output directory | Avoids overwriting the existing `runs` tree while preserving a complete per-round snapshot |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Skill bootstrap helper path does not exist in this environment | Proceeded with manual planning file creation |
| Initial `find` command missed the case files due to shallow `maxdepth` | Re-checked the `runs` directory structure with a Python scan matching the script logic |
| Ad hoc CSV comparison script failed with `KeyError: 'Power_W'` | Confirmed the experimental CSV column is `power_W` and reran the comparison with the correct column name |
| Bayesian CLI could not start because `ACBICI` was imported unconditionally | Made ACBICI-dependent imports optional at package/model/optimizer init level and verified CLI help works |

## Resources
- `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/visualize_meltpool.py`
- `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/runs/bayes_history-Ti64.csv`
- `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/config.yaml`
- `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/main.py`
- `/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/src/PyMeltpoolCalib/run_cli.py`

## Visual/Browser Findings
- `visualization_output/8/500W_meltHistory.png` shows a visibly deeper and wider meltpool cavity than `visualization_output/15/500W_meltHistory.png`.
- `visualization_output/15/500W_meltHistory.png` appears shallower/narrower, consistent with the degraded width/depth metrics in the history CSV.
- `runs/plots/objective_param_scatter.png` shows the best samples grouped in the lower-left explored region (`sigma` low, `Marangoni_Constant` more negative).

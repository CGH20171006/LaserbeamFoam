# Ti6Al4V Three-Round Optimization Campaign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run three additional Bayesian optimization rounds for the Ti6Al4V SingleTrack Powder60um case, preserving each round as a separate snapshot and adjusting search settings from evidence.

**Architecture:** Treat the current `runs` directory as the baseline history source, then create a dedicated directory for each new round containing a copied warmstart history, a round-specific config, and the new optimization outputs. After each run, analyze whether the best objective improved and use that evidence to set the next round strategy.

**Tech Stack:** Python CLI (`main.py` / `PyMeltpoolCalib.run_cli`), YAML config, CSV history files, matplotlib diagnostics, OpenFOAM/laserbeamFoam execution via the existing case setup.

---

### Task 1: Capture baseline metadata

**Files:**
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round0_baseline/README.md`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round0_baseline/config.yaml`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round0_baseline/bayes_history-Ti64.csv`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round0_baseline/result.json`

**Step 1:** Create the baseline snapshot directory.

**Step 2:** Copy the current `config.yaml`, `runs/bayes_history-Ti64.csv`, and `runs/result.json` into that directory.

**Step 3:** Write a short README noting the baseline best objective and why the next round will expand the low-sigma / more-negative-marangoni region.

**Step 4:** Verify the copied history row count matches the current `runs/bayes_history-Ti64.csv`.

### Task 2: Prepare round 1

**Files:**
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round1/config.yaml`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round1/runs/bayes_history-Ti64.csv`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round1/notes.md`

**Step 1:** Create the round 1 directory structure.

**Step 2:** Copy the baseline history CSV into `round1/runs/`.

**Step 3:** Write a round 1 config with absolute paths, `n_batches: 1`, `batch_size: 1`, and expanded bounds that still include all existing warmstart samples.

**Step 4:** Write notes documenting the round 1 hypothesis and expected success criteria.

**Step 5:** Verify the config loads and points to the round 1 `runs_root`.

### Task 3: Execute and verify round 1

**Files:**
- Modify: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round1/runs/*`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round1/review.md`

**Step 1:** Run `python3 main.py --method bayes --config optimization_rounds/round1/config.yaml --output-dir optimization_rounds/round1/runs`.

**Step 2:** Verify the history file gained exactly one new row and inspect the new objective.

**Step 3:** Regenerate or save convergence diagnostics for the round.

**Step 4:** Write a review summary stating whether the round improved the best objective and what that implies for round 2.

### Task 4: Repeat for rounds 2 and 3

**Files:**
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round2/...`
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/round3/...`

**Step 1:** Copy the previous round’s full `runs` directory into the next round’s starting point.

**Step 2:** Update the next round config according to the observed result.

**Step 3:** Run one new Bayesian batch for that round.

**Step 4:** Verify one-row history growth and write a review summary.

### Task 5: Final summary

**Files:**
- Create: `Project/AutoCalibrateParameter/cases/Ti6Al4V/SingleTrack_Powder60um/optimization_rounds/campaign_summary.md`

**Step 1:** Compare baseline, round 1, round 2, and round 3 best objectives.

**Step 2:** Summarize which configuration changes helped or hurt.

**Step 3:** Recommend the next search region or model changes for future work.

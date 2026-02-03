from __future__ import annotations

import inspect
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from skopt import Optimizer
from skopt.space import Real

from PyParaCalib.model_params import X_BASELINE
from PyParaCalib.opt_config import BayesConfig
from PyParaCalib.simulation_runner import compute_residuals, run_simulation


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def progress_path(cfg: BayesConfig) -> Path:
    return Path(cfg.runs_root) / "progress.json"


def result_path(cfg: BayesConfig) -> Path:
    return Path(cfg.runs_root) / "opt_result.json"


def history_path(cfg: BayesConfig) -> Path:
    return Path(cfg.runs_root) / "history.json"


def save_history(cfg: BayesConfig, x_iters: List[List[float]], y_iters: List[float]) -> None:
    hpath = history_path(cfg)
    data = {
        "x_iters": x_iters,
        "y_iters": y_iters,
        "n_samples": len(y_iters),
        "best_x": x_iters[int(np.argmin(y_iters))] if y_iters else None,
        "best_y": float(min(y_iters)) if y_iters else None,
        "ts": time.time(),
    }
    atomic_write_json(hpath, data)


def load_history(cfg: BayesConfig) -> Tuple[List[List[float]], List[float]]:
    hpath = history_path(cfg)
    if not hpath.exists():
        return [], []
    try:
        data = json.loads(hpath.read_text(encoding="utf-8"))
        x_iters = data.get("x_iters", [])
        y_iters = data.get("y_iters", [])
        return x_iters, y_iters
    except Exception:
        return [], []


def evaluate_bayes_point(args: Tuple) -> Tuple[int, List[float], float]:
    job_id, k_factors, cfg_dict, exp_time, exp_stress = args
    cfg = BayesConfig(**cfg_dict)

    work_dir = Path(cfg.runs_root) / f"job_{job_id:03d}"
    work_dir.mkdir(parents=True, exist_ok=True)
    job = f"Job_{job_id:03d}"

    k = np.array(k_factors)
    residual = compute_residuals(k, exp_time, exp_stress, cfg, work_dir, job)
    sse = float(np.sum(residual * residual))

    return job_id, k_factors, sse


def run_batch_parallel(
    candidates: List[List[float]],
    cfg: BayesConfig,
    exp_time: np.ndarray,
    exp_stress: np.ndarray,
    batch_offset: int = 0,
) -> List[Tuple[List[float], float]]:
    cfg_dict = asdict(cfg)
    args_list = [
        (batch_offset + i, cand, cfg_dict, exp_time, exp_stress)
        for i, cand in enumerate(candidates)
    ]

    results = []
    with ProcessPoolExecutor(max_workers=cfg.batch_size) as executor:
        futures = {executor.submit(evaluate_bayes_point, args): args[0] for args in args_list}

        for future in as_completed(futures):
            job_id = futures[future]
            try:
                _, k_factors, sse = future.result()
                results.append((k_factors, sse))
                print(f"  [Job_{job_id:03d}] SSE = {sse:.4e}")
            except Exception as exc:
                print(f"  [Job_{job_id:03d}] Failed: {exc}")
                k_factors = args_list[job_id - batch_offset][1]
                results.append((k_factors, 1e16))

    return results


def run_bayesian_optimization(cfg: BayesConfig, exp_time: np.ndarray, exp_stress: np.ndarray) -> dict:
    runs_root = Path(cfg.runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)

    dimensions = [Real(cfg.k_lower, cfg.k_upper, name=f"k_{i}") for i in range(18)]

    all_x: List[List[float]] = []
    all_y: List[float] = []

    if cfg.resume:
        prev_x, prev_y = load_history(cfg)
        if prev_x and prev_y:
            all_x = prev_x
            all_y = prev_y
            print(f"Resume: {len(all_y)} samples, best SSE = {min(all_y):.4e}")

    ppath = progress_path(cfg)
    best_sse = min(all_y) if all_y else float("inf")

    n_existing = len(all_y)
    n_initial_needed = max(0, cfg.n_initial_points - n_existing)

    if n_initial_needed > 0:
        print(f"\n{'=' * 60}")
        print(f"Stage 1: initial sampling ({n_initial_needed} points)")
        print(f"{'=' * 60}")

        rng = np.random.default_rng(seed=42)
        batch_id = 0

        while n_initial_needed > 0:
            n_this_batch = min(cfg.batch_size, n_initial_needed)
            candidates = [
                [rng.uniform(cfg.k_lower, cfg.k_upper) for _ in range(18)]
                for _ in range(n_this_batch)
            ]

            print(f"\nBatch {batch_id + 1}: evaluate {n_this_batch} random points")
            batch_results = run_batch_parallel(
                candidates,
                cfg,
                exp_time,
                exp_stress,
                batch_offset=len(all_y) + 1,
            )

            for k_factors, sse in batch_results:
                all_x.append(k_factors)
                all_y.append(sse)
                if sse < best_sse:
                    best_sse = sse

            save_history(cfg, all_x, all_y)
            atomic_write_json(
                ppath,
                {
                    "phase": "initial_sampling",
                    "n_samples": len(all_y),
                    "best_sse": best_sse,
                    "done": False,
                    "ts": time.time(),
                },
            )

            n_initial_needed -= n_this_batch
            batch_id += 1

        print(f"\nInitial sampling done. Best SSE = {best_sse:.4e}")

    print(f"\n{'=' * 60}")
    print(f"Stage 2: Bayesian optimization ({cfg.n_batches} batches, size={cfg.batch_size})")
    print(f"{'=' * 60}")

    optimizer_kwargs = {
        "dimensions": dimensions,
        "base_estimator": "GP",
        "acq_func": cfg.acq_func,
        "acq_func_kwargs": {"xi": cfg.xi, "kappa": cfg.kappa},
        "n_initial_points": 0,
        "random_state": 42,
    }
    if "noise" in inspect.signature(Optimizer.__init__).parameters:
        optimizer_kwargs["noise"] = cfg.noise

    optimizer = Optimizer(**optimizer_kwargs)

    if all_x and all_y:
        optimizer.tell(all_x, all_y)

    for batch_idx in range(cfg.n_batches):
        print(f"\nBatch {batch_idx + 1}/{cfg.n_batches}: select {cfg.batch_size} candidates")
        candidates = optimizer.ask(n_points=cfg.batch_size)

        batch_results = run_batch_parallel(
            candidates,
            cfg,
            exp_time,
            exp_stress,
            batch_offset=len(all_y) + 1,
        )

        batch_x = []
        batch_y = []
        for k_factors, sse in batch_results:
            batch_x.append(k_factors)
            batch_y.append(sse)
            all_x.append(k_factors)
            all_y.append(sse)
            if sse < best_sse:
                best_sse = sse

        optimizer.tell(batch_x, batch_y)

        save_history(cfg, all_x, all_y)
        atomic_write_json(
            ppath,
            {
                "phase": "bayesian_optimization",
                "batch": batch_idx + 1,
                "n_batches": cfg.n_batches,
                "n_samples": len(all_y),
                "best_sse": best_sse,
                "done": False,
                "ts": time.time(),
            },
        )

        print(f"Batch {batch_idx + 1} done. Best SSE = {best_sse:.4e}")

    best_idx = int(np.argmin(all_y))
    k_opt = np.array(all_x[best_idx])
    x_final = (k_opt * X_BASELINE).tolist()

    out = {
        "method": "bayes",
        "k_opt": all_x[best_idx],
        "x_final": x_final,
        "cost": best_sse,
        "n_samples": len(all_y),
        "message": f"Bayesian optimization completed with {len(all_y)} total evaluations",
        "optimizer": "skopt.Optimizer (batch parallel)",
        "acq_func": cfg.acq_func,
    }

    atomic_write_json(
        ppath,
        {"phase": "completed", "n_samples": len(all_y), "best_sse": best_sse, "done": True, "ts": time.time()},
    )

    result_path(cfg).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("\nGenerating convergence plot...")
    from PyParaCalib.postprocess import save_comparison_plot, save_convergence_plot

    save_convergence_plot(runs_root, all_y, cfg.n_initial_points)

    try:
        print("Generating best-fit comparison plot...")
        work_dir = runs_root / "best_result"
        work_dir.mkdir(parents=True, exist_ok=True)
        job = "Best"

        sim_time, sim_stress, _ = run_simulation(cfg, k_opt, work_dir, job)
        if sim_time.size > 0:
            save_comparison_plot(work_dir, job, exp_time, exp_stress, sim_time, sim_stress, best_sse)
    except Exception as exc:
        print(f"Plot failed: {exc}")

    return out

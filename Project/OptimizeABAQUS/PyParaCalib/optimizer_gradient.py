from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from scipy.optimize import least_squares

from PyParaCalib.model_params import X_BASELINE
from PyParaCalib.opt_config import GradientConfig
from PyParaCalib.postprocess import save_comparison_plot, save_iteration_plot
from PyParaCalib.simulation_runner import compute_residuals, run_simulation


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    last_exc: Exception | None = None
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except Exception as exc:  # pragma: no cover - Windows file locks
            last_exc = exc
            time.sleep(0.1)
    try:
        path.write_text(payload, encoding="utf-8")
    except Exception:
        if last_exc is not None:
            raise last_exc
        raise


def progress_path(cfg: GradientConfig, direction_id: int) -> Path:
    return Path(cfg.runs_root) / f"run_{direction_id:03d}" / "progress.json"


def result_path(cfg: GradientConfig, direction_id: int) -> Path:
    return Path(cfg.runs_root) / f"run_{direction_id:03d}" / "opt_result.json"


def _initial_direction(cfg: GradientConfig, direction_id: int) -> np.ndarray:
    rng = np.random.default_rng(seed=1000 + direction_id)
    vec = rng.normal(0.0, 1.0, size=18)
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        vec[0] = 1.0
        norm = 1.0
    return vec / norm


def _initial_k(cfg: GradientConfig, direction_id: int) -> np.ndarray:
    if cfg.init_strategy == "legacy_single":
        return np.ones(18, dtype=float)
    if cfg.init_strategy == "legacy_multi":
        rng = np.random.default_rng(seed=1000 + direction_id)
        return rng.uniform(cfg.k_lower, cfg.k_upper, size=18)
    if cfg.init_strategy == "directional":
        direction = _initial_direction(cfg, direction_id)
        return np.clip(1.0 + cfg.direction_scale * direction, cfg.k_lower, cfg.k_upper)
    raise ValueError(f"Unknown init_strategy: {cfg.init_strategy}")


def optimize_direction(
    direction_id: int,
    cfg_dict: dict,
    exp_time: np.ndarray,
    exp_stress: np.ndarray,
) -> dict:
    cfg = GradientConfig(**cfg_dict)

    runs_root = Path(cfg.runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    work_dir = runs_root / f"run_{direction_id:03d}"
    work_dir.mkdir(parents=True, exist_ok=True)
    job = f"Job_{direction_id:03d}"

    lb = np.full(18, cfg.k_lower, dtype=float)
    ub = np.full(18, cfg.k_upper, dtype=float)

    x0 = _initial_k(cfg, direction_id)

    eval_count = 0
    best_sse = float("inf")
    last_sse = float("inf")

    ppath = progress_path(cfg, direction_id)
    atomic_write_json(
        ppath,
        {
            "direction_id": direction_id,
            "job": job,
            "pid": os.getpid(),
            "eval": 0,
            "last_sse": None,
            "best_sse": None,
            "done": False,
            "ts": time.time(),
        },
    )

    sse_history: list[float] = []
    k_history: list[list[float]] = []  # 保存每次迭代的参数

    def fun(k: np.ndarray) -> np.ndarray:
        nonlocal eval_count, best_sse, last_sse
        eval_count += 1
        residual = compute_residuals(k, exp_time, exp_stress, cfg, work_dir, job)
        sse = float(np.sum(residual * residual))
        sse_history.append(sse)
        k_history.append(k.tolist())  # 记录当前参数
        last_sse = sse
        if sse < best_sse:
            best_sse = sse

        if cfg.log_every_eval <= 1 or (eval_count % cfg.log_every_eval) == 0:
            atomic_write_json(
                ppath,
                {
                    "direction_id": direction_id,
                    "job": job,
                    "pid": os.getpid(),
                    "eval": eval_count,
                    "last_sse": last_sse,
                    "best_sse": best_sse,
                    "done": False,
                    "ts": time.time(),
                },
            )
        return residual

    res = least_squares(
        fun,
        x0,
        bounds=(lb, ub),
        max_nfev=cfg.max_nfev,
        ftol=cfg.ftol,
        xtol=cfg.xtol,
        diff_step=cfg.diff_step,
        x_scale=np.ones_like(x0),
        verbose=0,
    )

    final_sse = float(res.cost) * 2.0

    atomic_write_json(
        ppath,
        {
            "direction_id": direction_id,
            "job": job,
            "pid": os.getpid(),
            "eval": int(res.nfev),
            "last_sse": last_sse,
            "best_sse": best_sse,
            "done": True,
            "ts": time.time(),
        },
    )

    k_opt = res.x
    x_final = (k_opt * X_BASELINE).tolist()
    out = {
        "method": "gradient",
        "direction_id": direction_id,
        "job": job,
        "work_dir": str(work_dir),
        "k_opt": k_opt.tolist(),
        "x_final": x_final,
        "cost": final_sse,
        "nfev": int(res.nfev),
        "status": int(res.status),
        "message": res.message,
        "cfg": cfg_dict,
    }

    result_path(cfg, direction_id).write_text(json.dumps(out, indent=2), encoding="utf-8")

    try:
        sim_time, sim_stress, _ = run_simulation(cfg, k_opt, work_dir, job)
        if sim_time.size > 0:
            save_comparison_plot(work_dir, job, exp_time, exp_stress, sim_time, sim_stress, final_sse)
    except Exception as exc:
        print(f"[{job}] Plot failed: {exc}")

    save_iteration_plot(work_dir, job, sse_history)

    # 保存迭代历史到JSON文件
    history_path = work_dir / "history.json"
    atomic_write_json(history_path, {
        "direction_id": direction_id,
        "job": job,
        "sse_history": sse_history,
        "k_history": k_history,  # 参数变化历史
        "k_init": x0.tolist(),   # 初始参数
        "k_opt": k_opt.tolist(), # 最优参数
        "n_evals": len(sse_history),
        "best_sse": min(sse_history) if sse_history else None,
        "final_sse": final_sse,
    })

    return out


def monitor_loop(cfg: GradientConfig, stop_event: threading.Event) -> None:
    last_rows: list[tuple] | None = None
    poll_interval = max(0.1, cfg.monitor_interval_sec)
    while not stop_event.is_set():
        rows = []
        for i in range(1, cfg.n_directions + 1):
            p = progress_path(cfg, i)
            done = result_path(cfg, i).exists()
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    rows.append(
                        (
                            i,
                            d.get("job", f"Job_{i:03d}"),
                            int(d.get("eval") or 0),
                            d.get("last_sse"),
                            d.get("best_sse"),
                            bool(d.get("done")) or done,
                        )
                    )
                except Exception:
                    rows.append((i, f"Job_{i:03d}", 0, None, None, done))
            else:
                rows.append((i, f"Job_{i:03d}", 0, None, None, done))

        if rows != last_rows:
            print("\n" + "=" * 78)
            print(f"Direction progress - {time.strftime('%H:%M:%S')}")
            print(f"{'ID':>3}  {'JOB':>8}  {'EVAL':>6}  {'LAST_SSE':>12}  {'BEST_SSE':>12}  {'DONE':>5}")
            for _id, job, ev, last_sse, best_sse, done in rows:
                ls = f"{last_sse:.2e}" if isinstance(last_sse, (int, float)) else "-"
                bs = f"{best_sse:.2e}" if isinstance(best_sse, (int, float)) else "-"
                print(f"{_id:>3}  {job:>8}  {ev:>6}  {ls:>12}  {bs:>12}  {str(done):>5}")
            last_rows = rows

        time.sleep(poll_interval)


def run_gradient_optimization(cfg: GradientConfig, exp_time: np.ndarray, exp_stress: np.ndarray) -> dict:
    Path(cfg.runs_root).mkdir(parents=True, exist_ok=True)

    print(f"Loaded exp points: {exp_time.size} (t in [{cfg.t_min}, {cfg.t_max}])")
    print(f"Directions: n_directions={cfg.n_directions}, max_workers={cfg.max_workers}, cpus/job={cfg.cpus}")
    if cfg.scratch_dir:
        print(f"scratch_dir={cfg.scratch_dir}")
    print(
        f"Monitoring: log_every_eval={cfg.log_every_eval}, poll_interval={cfg.monitor_interval_sec}s, plot={cfg.show_plot}"
    )

    cfg_dict = asdict(cfg)
    stop_event = threading.Event()
    mon = threading.Thread(target=monitor_loop, args=(cfg, stop_event), daemon=True)
    mon.start()

    results = []
    best = None

    try:
        with ProcessPoolExecutor(max_workers=cfg.max_workers) as ex:
            futs = [
                ex.submit(optimize_direction, i + 1, cfg_dict, exp_time, exp_stress)
                for i in range(cfg.n_directions)
            ]
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    results.append(r)
                    if best is None or r["cost"] < best["cost"]:
                        best = r
                    print(
                        f"\n[FINISHED] direction {r['direction_id']:03d}  cost={r['cost']:.3e}  dir={r['work_dir']}"
                    )
                except Exception as exc:
                    print(f"\n[ERROR] Worker failed: {exc}")
    finally:
        stop_event.set()
        mon.join(timeout=2.0)

    if best is None:
        print("\n[WARNING] No results produced (all directions failed?)")
        return {"method": "gradient", "message": "No results produced"}

    Path("opt_result_best.json").write_text(json.dumps(best, indent=2), encoding="utf-8")
    print(f"\nBest saved: opt_result_best.json (direction {best['direction_id']:03d}, cost={best['cost']:.3e})")

    return best

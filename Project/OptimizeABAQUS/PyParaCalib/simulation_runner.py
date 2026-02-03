from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np
from scipy.interpolate import interp1d

from PyParaCalib.inp_utils import update_inp_18_params
from PyParaCalib.model_params import X_BASELINE
from PyParaCalib.opt_config import BaseConfig
from PyParaCalib.read_dat_s33_e33 import read_dat_s33_e33

PENALTY_RESIDUAL = 1e8


def minimal_cleanup(work_dir: Path, job: str) -> None:
    extensions = [".lck", ".odb", ".msg", ".sta", ".prt", ".sim", ".com", ".log"]
    for ext in extensions:
        p = work_dir / f"{job}{ext}"
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def ensure_user_subroutine_present(cfg: BaseConfig, work_dir: Path) -> str:
    src = Path(cfg.user_subroutine)
    if not src.exists():
        return Path(cfg.user_subroutine).name
    dst = work_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    return src.name


def run_abaqus(cfg: BaseConfig, work_dir: Path, job: str) -> int:
    inp_run = f"{job}.inp"
    user_basename = ensure_user_subroutine_present(cfg, work_dir)
    scratch_part = f" scratch={cfg.scratch_dir}" if cfg.scratch_dir else ""

    cmd_str = (
        f'"{cfg.abaqus_bat}" '
        f"job={job} user={user_basename} input={inp_run} "
        f"cpus={cfg.cpus}{scratch_part} interactive ask_delete=OFF"
    )

    proc = subprocess.run(cmd_str, cwd=str(work_dir), shell=True, capture_output=True)

    if proc.returncode != 0:
        stdout_text = proc.stdout.decode("utf-8", errors="ignore") if proc.stdout else ""
        stderr_text = proc.stderr.decode("utf-8", errors="ignore") if proc.stderr else ""
        (work_dir / "abaqus_stdout.txt").write_text(stdout_text, encoding="utf-8")
        (work_dir / "abaqus_stderr.txt").write_text(stderr_text, encoding="utf-8")

    return proc.returncode


def run_simulation(
    cfg: BaseConfig,
    k_factors: np.ndarray,
    work_dir: Path,
    job: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    real_params = np.asarray(k_factors, dtype=float) * X_BASELINE
    inp_run_path = work_dir / f"{job}.inp"

    update_inp_18_params(Path(cfg.inp_template), inp_run_path, real_params)
    minimal_cleanup(work_dir, job)
    status = run_abaqus(cfg, work_dir, job)
    if status != 0:
        return np.array([]), np.array([]), np.array([])

    sim_time, sim_stress, sim_strain = read_dat_s33_e33(job_name=job, cwd=work_dir)
    minimal_cleanup(work_dir, job)
    return sim_time, sim_stress, sim_strain


def compute_residuals(
    k_factors: np.ndarray,
    exp_time: np.ndarray,
    exp_stress: np.ndarray,
    cfg: BaseConfig,
    work_dir: Path,
    job: str,
) -> np.ndarray:
    sim_time, sim_stress, _ = run_simulation(cfg, k_factors, work_dir, job)
    if sim_time.size == 0:
        return np.ones_like(exp_stress) * PENALTY_RESIDUAL

    try:
        sim_time_u, idx = np.unique(sim_time, return_index=True)
        sim_stress_u = sim_stress[idx]
        f = interp1d(sim_time_u, sim_stress_u, kind="linear", fill_value="extrapolate", assume_sorted=False)
        sim_stress_interp = f(exp_time)
        return sim_stress_interp - exp_stress
    except Exception:
        return np.ones_like(exp_stress) * PENALTY_RESIDUAL

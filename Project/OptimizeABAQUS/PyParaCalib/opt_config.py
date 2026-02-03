from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# 项目根目录（BayesForABAQUS 目录）
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_user_subroutine() -> str:
    return str(PROJECT_ROOT / "Chaboche_Wang.for")


def _default_exp_csv() -> str:
    return str(PROJECT_ROOT / "data.csv")


def _default_inp_template() -> str:
    return str(PROJECT_ROOT / "Tradi-Umat.inp")


def _default_runs_root() -> str:
    return str(PROJECT_ROOT / "runs")


def _default_runs_bayes() -> str:
    return str(PROJECT_ROOT / "runs_bayes")


@dataclass
class BaseConfig:
    user_subroutine: str = field(default_factory=_default_user_subroutine)
    exp_csv: str = field(default_factory=_default_exp_csv)
    inp_template: str = field(default_factory=_default_inp_template)
    t_min: float = 5.0
    t_max: float = 25.0
    runs_root: str = field(default_factory=_default_runs_root)
    scratch_dir: Optional[str] = None
    cpus: int = 2


@dataclass
class BayesConfig(BaseConfig):
    abaqus_bat: str = r"E:\Study\ABAQUS2021\commands\abaqus.bat"
    runs_root: str = field(default_factory=_default_runs_bayes)

    n_batches: int = 50
    n_initial_points: int = 15
    acq_func: str = "EI"
    noise: float = 1e-10
    xi: float = 0.01
    kappa: float = 1.96

    k_lower: float = 0.5
    k_upper: float = 1.5

    resume: bool = True
    batch_size: int = 5

    show_plot: bool = False


@dataclass
class GradientConfig(BaseConfig):
    abaqus_bat: str = r"E:\Study\ABAQUS2021\commands\abaqus.bat"
    cpus: int = 1

    max_nfev: int = 300
    ftol: float = 1e-4
    xtol: float = 1e-4
    diff_step: float = 0.05

    k_lower: float = 0.5
    k_upper: float = 1.5
    direction_scale: float = 0.5

    n_directions: int = 8
    max_workers: int = 8

    log_every_eval: int = 1
    monitor_interval_sec: float = 0.5

    show_plot: bool = False
    init_strategy: str = "legacy_multi"


def build_runs_root(method: str, prefix: str = "runs") -> str:
    safe_method = method.strip().lower().replace(" ", "_")
    if not safe_method:
        safe_method = "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(PROJECT_ROOT / f"{prefix}_{safe_method}_{timestamp}")

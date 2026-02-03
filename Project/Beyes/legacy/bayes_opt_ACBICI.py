#!/usr/bin/env python3
"""
贝叶斯优化驱动脚本（针对 Beyes 案例）
- 自动修改 sigma、Marangoni_Constant、基板温度
- 运行 OpenFOAM 求解与后处理
- 以熔池深度/宽度/面积相对误差为目标

支持两种运行模式：
  - 个人电脑模式（默认）：使用简化的命令执行
  - HPC模式（--hpc）：支持自定义 foam_runner, postproc_runner 等高级配置

后处理固定使用:
    python applications/scripts/postProcessing/characterise_meltpool.py

实验功率点固定为 5 组: 140, 170, 200, 230, 260 W。每次迭代会依次修改功率并运行 5 次仿真与后处理，目标函数为 5 组功率下（宽度/深度/面积）的相对误差平方平均。
"""

import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# 参数范围
PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "sigma": (1.0, 2.0),
    "Marangoni_Constant": (-8e-4, -4e-6),
    "substrate_temp": (300.0, 800.0),
}
POWER_SETTINGS = [140.0, 170.0, 200.0, 230.0, 260.0]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# HPC 模式默认配置
DEFAULT_POSTPROC_HPC = PROJECT_ROOT / "applications" / "scripts" / "postProcessing" / "characterise_meltpool.py"
DEFAULT_BASHRC_HPC = os.environ.get("OF_LOCATION", "/usr/lib/openfoam/openfoam2506/etc/bashrc")
DEFAULT_FOAM_RUNNER_HPC = shutil.which("of2506")

# 个人电脑模式默认配置
DEFAULT_POSTPROC_PC = Path("/home/cgh/LaserbeamFoam/applications/scripts/postProcessing/characterise_meltpool.py")
DEFAULT_BASHRC_PC = Path(os.environ.get("OF_LOCATION", "/usr/lib/openfoam/openfoam2506/etc/bashrc"))


# ---------- 简单高斯过程采样器（纯 numpy 实现，避免外部依赖） ----------

class SimpleBO:
    def __init__(self, bounds: Dict[str, Tuple[float, float]], n_initial: int = 3, seed: int = 42, kappa: float = 2.0):
        self.names = list(bounds.keys())
        self.bounds = np.array([bounds[n] for n in self.names], dtype=float)
        self.n_initial = n_initial
        self.kappa = kappa
        self.rng = np.random.default_rng(seed)
        self.X: List[List[float]] = []
        self.y: List[float] = []
        self.length_scale = np.ones(len(self.names)) * 0.25  # 在 0-1 空间的长度尺度
        self.noise = 1e-6

    def _sample_uniform(self) -> np.ndarray:
        return self.bounds[:, 0] + (self.bounds[:, 1] - self.bounds[:, 0]) * self.rng.random(len(self.names))

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        return (X - self.bounds[:, 0]) / (self.bounds[:, 1] - self.bounds[:, 0])

    def _kernel(self, Xa: np.ndarray, Xb: np.ndarray) -> np.ndarray:
        diff = Xa[:, None, :] - Xb[None, :, :]
        scaled = diff / self.length_scale
        sq = np.sum(scaled * scaled, axis=2)
        return np.exp(-0.5 * sq)

    def suggest(self, n_candidates: int = 256) -> Dict[str, float]:
        if len(self.X) < self.n_initial:
            point = self._sample_uniform()
            return {n: float(v) for n, v in zip(self.names, point)}

        X_arr = np.array(self.X)
        y_arr = np.array(self.y)
        Xn = self._normalize(X_arr)

        K = self._kernel(Xn, Xn) + self.noise * np.eye(len(Xn))
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            point = self._sample_uniform()
            return {n: float(v) for n, v in zip(self.names, point)}

        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_arr))

        candidates = np.array([self._sample_uniform() for _ in range(n_candidates)])
        Cn = self._normalize(candidates)
        k = self._kernel(Xn, Cn)
        mean = k.T @ alpha
        v = np.linalg.solve(L, k)
        var = np.maximum(1.0 - np.sum(v * v, axis=0), 1e-12)  # k(x,x)=1
        std = np.sqrt(var)
        acq = mean - self.kappa * std  # LCB
        idx = int(np.argmin(acq))
        point = candidates[idx]
        return {n: float(v) for n, v in zip(self.names, point)}

    def register(self, params: Dict[str, float], objective: float) -> None:
        self.X.append([params[n] for n in self.names])
        self.y.append(objective)


# ---------- 工具函数 ----------

def _run(cmd: str, workdir: Path) -> None:
    print(f"[cmd] {cmd}")
    subprocess.run(cmd, cwd=str(workdir), shell=True, check=True)


def _run_script(script: str, workdir: Path, runner: Optional[str]) -> None:
    script = script.strip()
    if not script.endswith("\n"):
        script += "\n"
    label = runner or "bash -lc"
    print(f"[cmd:{label}] <<'EOF'\n{script}EOF")
    if runner:
        subprocess.run(runner, cwd=str(workdir), shell=True, check=True, text=True, input=script)
    else:
        subprocess.run(["bash", "-lc", script], cwd=str(workdir), check=True)


def _update_dict_value(path: Path, key: str, value: float) -> None:
    lines = path.read_text().splitlines()
    updated = False
    pattern = re.compile(rf"^\s*{re.escape(key)}\b")
    for i, line in enumerate(lines):
        if pattern.match(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = f"{indent}{key:<23}{value};"
            updated = True
            break
    if not updated:
        lines.append(f"{key:<23}{value};")
    path.write_text("\n".join(lines) + "\n")


def _update_T_internal(path: Path, temperature: float) -> None:
    lines = path.read_text().splitlines()
    pattern = re.compile(r"^\s*internalField\s+uniform\s+([0-9eE+\-\.]+)")
    for i, line in enumerate(lines):
        if pattern.search(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = f"{indent}internalField   uniform {temperature};"
            path.write_text("\n".join(lines) + "\n")
            return
    raise RuntimeError(f"未在 {path} 中找到 internalField 行")


def _rewrite_power_file(path: Path, power_w: float) -> None:
    """
    将 timeVsLaserPower 中所有非零功率替换为 power_w，时间点保持不变。
    """
    lines = path.read_text().splitlines()
    pattern = re.compile(r"\(\s*([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)\s*\)")
    new_lines = []
    for line in lines:
        m = pattern.search(line)
        if m:
            t_str, val_str = m.group(1), m.group(2)
            val = float(val_str)
            new_val = power_w if val != 0.0 else 0.0
            new_lines.append(f"    ({t_str}           {new_val})")
        else:
            new_lines.append(line)
    path.write_text("\n".join(new_lines) + "\n")


# ---------- 案例操作 ----------

@dataclass
class CaseManager:
    case_dir: Path
    postproc_script: Path
    foam_bashrc: Optional[str] = None
    postproc_python: str = "python"
    postproc_runner: Optional[str] = None
    pvpython: Optional[str] = None
    n_proc: int = 12
    foam_runner: Optional[str] = None
    mpirun_flags: Tuple[str, ...] = field(default_factory=tuple)
    history_path: Path = field(default_factory=lambda: Path("bayes_history.csv"))
    hpc_mode: bool = False  # 新增：标记是否为 HPC 模式

    def __post_init__(self) -> None:
        self.case_dir = self.case_dir.resolve()
        self.postproc_script = self.postproc_script.expanduser().resolve()
        if self.foam_bashrc:
            self.foam_bashrc = os.path.expandvars(os.path.expanduser(str(self.foam_bashrc)))
        if not self.history_path.is_absolute():
            self.history_path = (self.case_dir / self.history_path).resolve()
        self.mpirun_flags = tuple(self.mpirun_flags)
        self.transport_props = self.case_dir / "constant" / "transportProperties"
        # 写 initial/T，避免后续拷贝 initial -> 0 时被覆盖
        self.temp_field = self.case_dir / "initial" / "T"
        self.time_vs_power = self.case_dir / "constant" / "timeVsLaserPower"
        self.main_foam = self.case_dir / "main.foam"
        self.results_plots = self.case_dir / "results_plots"
        self.plot_archive = self.case_dir / "results_plots_archive"

    def _list_time_dirs(self) -> List[Path]:
        time_dirs: List[Path] = []
        for p in self.case_dir.iterdir():
            if not p.is_dir():
                continue
            try:
                float(p.name)
            except ValueError:
                continue
            time_dirs.append(p)
        return sorted(time_dirs, key=lambda d: float(d.name))

    def _has_nonzero_time(self) -> bool:
        for d in self._list_time_dirs():
            try:
                if float(d.name) > 0.0:
                    return True
            except ValueError:
                continue
        return False

    def ensure_reconstructed(self) -> None:
        if self._has_nonzero_time():
            return
        lines = ["set -eo pipefail"]
        if self.foam_bashrc:
            lines.append(f"source {shlex.quote(self.foam_bashrc)}")
        lines.append("reconstructPar -latestTime")
        _run_script("\n".join(lines), self.case_dir, self.foam_runner)
        if not self._has_nonzero_time():
            raise RuntimeError("reconstructPar -latestTime 未生成非 0 时间目录，请检查求解输出是否完整")

    def update_parameters(self, sigma: float, marangoni: float, substrate_temp: float) -> None:
        _update_dict_value(self.transport_props, "sigma", sigma)
        _update_dict_value(self.transport_props, "Marangoni_Constant", marangoni)
        _update_T_internal(self.temp_field, substrate_temp)

    def set_power(self, power_w: float) -> None:
        _rewrite_power_file(self.time_vs_power, power_w)

    def run_simulation(self) -> None:
        if self.hpc_mode:
            # HPC 模式：使用 _run_script
            mpirun_cmd = ["mpirun"]
            if self.mpirun_flags:
                mpirun_cmd.extend(self.mpirun_flags)
            mpirun_cmd.extend(["-np", str(self.n_proc), "laserbeamFoam", "-parallel"])
            lines = ["set -eo pipefail"]
            if self.foam_bashrc:
                lines.append(f"source {shlex.quote(self.foam_bashrc)}")
            lines.extend(
                [
                    "bash ./Allclean || true",
                    "rm -rf 0 processor*",
                    "cp -r initial 0",
                    "touch main.foam",
                    "blockMesh",
                    "setSolidFraction",
                    "decomposePar",
                    " ".join(mpirun_cmd),
                    "reconstructPar -latestTime",
                ]
            )
            _run_script("\n".join(lines), self.case_dir, self.foam_runner)
        else:
            # 个人电脑模式：使用简化的 bash -lc 命令
            bashrc = shlex.quote(str(self.foam_bashrc)) if self.foam_bashrc else shlex.quote(str(DEFAULT_BASHRC_PC))
            case_dir = shlex.quote(str(self.case_dir))
            mpirun_flags = " ".join(self.mpirun_flags) if self.mpirun_flags else "--oversubscribe"
            cmd = (
                "bash -lc 'set -eo pipefail; "
                f"export WM_PROJECT_SITE=${{WM_PROJECT_SITE-}}; source {bashrc} && "
                f"cd {case_dir} && bash ./Allclean || true; "
                "rm -rf 0 processor*; "
                "cp -r initial 0; "
                "touch main.foam; "
                "blockMesh; setSolidFraction; decomposePar; "
                f"mpirun -np {self.n_proc} {mpirun_flags} laserbeamFoam -parallel; "
                "reconstructPar -latestTime'"
            )
            _run(cmd, self.case_dir)

    def run_postprocess(self) -> None:
        if self.hpc_mode:
            # HPC 模式：使用 ensure_reconstructed 和环境变量
            self.ensure_reconstructed()
            if not self.main_foam.exists():
                self.main_foam.touch()
            env = os.environ.copy()
            if self.postproc_runner:
                env["POSTPROC_RUNNER"] = self.postproc_runner
            if self.pvpython:
                env["PVPYTHON"] = self.pvpython
            cmd = shlex.split(self.postproc_python) + [str(self.postproc_script)]
            print(f"[cmd] {' '.join(shlex.quote(c) for c in cmd)}")
            subprocess.run(cmd, cwd=str(self.case_dir), check=True, env=env)
        else:
            # 个人电脑模式：直接运行后处理脚本
            cmd = f"{self.postproc_python} {shlex.quote(str(self.postproc_script))}"
            _run(cmd, self.case_dir)

    def read_metrics(self) -> Dict[str, float]:
        metrics_path = self.case_dir / "cross_sections_statistics.csv"
        if not metrics_path.exists():
            raise FileNotFoundError("缺少 cross_sections_statistics.csv，后处理是否成功？")
        df = pd.read_csv(metrics_path)
        return {
            "width_mean_m": float(df["width"].mean()),
            "depth_mean_m": float(df["depth"].mean()),
            "area_mean_m2": float(df["area"].mean()) if "area" in df.columns else math.nan,
        }


# ---------- 目标函数 ----------

def load_targets(exp_path: Path) -> Dict[float, Dict[str, float]]:
    df = pd.read_csv(exp_path)
    targets: Dict[float, Dict[str, float]] = {}
    for p in POWER_SETTINGS:
        row = df.loc[df["power_W"] == p]
        if row.empty:
            raise RuntimeError(f"实验数据中未找到功率 {p} W 的行")
        r = row.iloc[0]
        targets[p] = {
            "width_m": float(r["width_um"]) * 1e-6,
            "depth_m": float(r["depth_um"]) * 1e-6,
            "area_m2": float(r["area_um2"]) * 1e-12,
        }
    return targets


# ---------- 单次评估 ----------

def evaluate_once(
    case: CaseManager,
    params: Dict[str, float],
    targets: Dict[float, Dict[str, float]],
    penalty: float = 1e6,
    iter_idx: Optional[int] = None,
    resume_power_data: Optional[Dict[float, Dict[str, float]]] = None,
) -> Dict[str, float]:
    start = time.time()
    run_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    row: Dict[str, float] = {
        "sigma": params["sigma"],
        "Marangoni_Constant": params["Marangoni_Constant"],
        "substrate_temp": params["substrate_temp"],
    }
    power_rows: List[Dict[str, float]] = []
    completed_power_data = resume_power_data or {}
    try:
        errs_sq: List[float] = []
        # 先计入已完成功率点，避免重复计算
        for power, metrics in completed_power_data.items():
            sim_width_um = metrics["width_um"]
            sim_depth_um = metrics["depth_um"]
            sim_area_um2 = metrics["area_um2"]
            tgt = targets[power]
            err_w = (sim_width_um - tgt["width_m"] * 1e6) / (tgt["width_m"] * 1e6)
            err_d = (sim_depth_um - tgt["depth_m"] * 1e6) / (tgt["depth_m"] * 1e6)
            err_a = (sim_area_um2 - tgt["area_m2"] * 1e12) / (tgt["area_m2"] * 1e12)
            errs_sq.extend([err_w ** 2, err_d ** 2, err_a ** 2])
            row[f"width_um_{int(power)}W"] = sim_width_um
            row[f"depth_um_{int(power)}W"] = sim_depth_um
            row[f"area_um2_{int(power)}W"] = sim_area_um2
            power_rows.append(
                {
                    "power_W": power,
                    "width_um": sim_width_um,
                    "depth_um": sim_depth_um,
                    "area_um2": sim_area_um2,
                }
            )

        case.update_parameters(params["sigma"], params["Marangoni_Constant"], params["substrate_temp"])
        for power in POWER_SETTINGS:
            if power in completed_power_data:
                continue  # 已有结果，跳过重算
            case.set_power(power)
            case.run_simulation()
            case.run_postprocess()
            metrics = case.read_metrics()
            if not all(math.isfinite(v) for v in metrics.values()):
                raise ValueError(f"功率 {power} W 的后处理结果存在 NaN/Inf")
            sim_width_um = metrics["width_mean_m"] * 1e6
            sim_depth_um = metrics["depth_mean_m"] * 1e6
            sim_area_um2 = metrics["area_mean_m2"] * 1e12
            tgt = targets[power]
            err_w = (sim_width_um - tgt["width_m"] * 1e6) / (tgt["width_m"] * 1e6)
            err_d = (sim_depth_um - tgt["depth_m"] * 1e6) / (tgt["depth_m"] * 1e6)
            err_a = (sim_area_um2 - tgt["area_m2"] * 1e12) / (tgt["area_m2"] * 1e12)
            errs_sq.extend([err_w ** 2, err_d ** 2, err_a ** 2])
            row[f"width_um_{int(power)}W"] = sim_width_um
            row[f"depth_um_{int(power)}W"] = sim_depth_um
            row[f"area_um2_{int(power)}W"] = sim_area_um2
            if iter_idx is not None:
                archive_plots(case, iter_idx, power, run_ts)
            power_rows.append(
                {
                    "power_W": power,
                    "width_um": sim_width_um,
                    "depth_um": sim_depth_um,
                    "area_um2": sim_area_um2,
                }
            )
        row["objective"] = float(np.mean(errs_sq))
        row["status"] = "ok"
    except Exception as exc:
        remaining_powers = [p for p in POWER_SETTINGS if p not in [r["power_W"] for r in power_rows]]
        power_rows.extend(
            [
                {"power_W": p, "width_um": math.nan, "depth_um": math.nan, "area_um2": math.nan}
                for p in remaining_powers
            ]
        )
        row.update({
            "width_mean_m": math.nan,
            "depth_mean_m": math.nan,
            "area_mean_m2": math.nan,
            "objective": penalty,
            "status": f"failed: {exc}",
        })
        print(f"[warn] 运行失败，使用惩罚 {penalty}: {exc}")
    row["runtime_sec"] = time.time() - start
    row["timestamp"] = run_ts
    return row, power_rows


def append_detail_records(detail_path: Path, rows: List[Dict[str, float]]) -> None:
    """
    追加写入功率点级别的宽度/深度/面积到独立文件，便于事后核对。
    """
    if not rows:
        return
    df = pd.DataFrame(rows)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(detail_path, mode="a", header=not detail_path.exists(), index=False)


def archive_plots(case: CaseManager, iter_idx: int, power: float, run_ts: str) -> None:
    """
    将当前 results_plots 下的图复制到归档目录，按迭代+功率分文件夹，避免被覆盖。
    """
    if not case.results_plots.exists():
        return
    safe_ts = run_ts.replace(":", "-").replace(" ", "_")
    dest_dir = case.plot_archive / f"iter{iter_idx:03d}_p{int(power)}W_{safe_ts}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in case.results_plots.iterdir():
        if f.is_file():
            shutil.copy(f, dest_dir / f.name)


def load_history_if_any(history_path: Path) -> pd.DataFrame:
    if history_path.exists() and history_path.stat().st_size > 0:
        try:
            return pd.read_csv(history_path)
        except Exception as exc:  # pragma: no cover - 防御式
            print(f"[warn] 无法读取已有历史 {history_path}: {exc}")
    return pd.DataFrame()


def detect_partial_last_row(history_df: pd.DataFrame) -> Tuple[Optional[pd.Series], pd.DataFrame]:
    """
    检查最后一行是否有未完成的功率点（缺少 width/depth/area），用于续跑。
    返回 (partial_row_or_None, history_without_partial)
    """
    if history_df.empty:
        return None, history_df
    last = history_df.iloc[-1]
    missing_power = False
    for p in POWER_SETTINGS:
        if pd.isna(last.get(f"width_um_{int(p)}W", np.nan)) or pd.isna(last.get(f"depth_um_{int(p)}W", np.nan)) or pd.isna(last.get(f"area_um2_{int(p)}W", np.nan)):
            missing_power = True
            break
    if missing_power or str(last.get("status", "")).startswith("failed"):
        return last, history_df.iloc[:-1].copy()
    return None, history_df


def extract_completed_power_data(row: pd.Series) -> Dict[float, Dict[str, float]]:
    data: Dict[float, Dict[str, float]] = {}
    for p in POWER_SETTINGS:
        w = row.get(f"width_um_{int(p)}W", np.nan)
        d = row.get(f"depth_um_{int(p)}W", np.nan)
        a = row.get(f"area_um2_{int(p)}W", np.nan)
        if not (pd.isna(w) or pd.isna(d) or pd.isna(a)):
            data[p] = {"width_um": float(w), "depth_um": float(d), "area_um2": float(a)}
    return data


def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text()) or {}
    except Exception as exc:
        print(f"[warn] 读取配置文件 {config_path} 失败，将使用默认/CLI 参数: {exc}")
        return {}


# ---------- CLI ----------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="贝叶斯优化 Beyes 案例参数（sigma/Marangoni/基板温度）")
    parser.add_argument("--hpc", action="store_true", help="启用 HPC 模式（支持 foam_runner, postproc_runner 等高级配置）")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="YAML 配置文件路径")
    parser.add_argument("--case-dir", type=Path, default=None, help="案例目录（可在 yaml 设置 case_dir）")
    parser.add_argument("--foam-bashrc", type=Path, default=None, help="OpenFOAM 环境脚本")
    parser.add_argument("--foam-runner", default=None, help="[HPC模式] 执行求解器的外部命令（例如 of2506）")
    parser.add_argument("--postproc-python", default=None, help="后处理使用的 python，可选填绝对路径")
    parser.add_argument("--postproc-runner", default=None, help="[HPC模式] 后处理需要的外部命令（例如 of2506）")
    parser.add_argument("--pvpython", default=None, help="[HPC模式] pvpython 路径（默认使用 PATH 中的 pvpython）")
    parser.add_argument("--postproc-script", type=Path, default=None, help="后处理脚本路径")
    parser.add_argument("--experimental-data", type=Path, default=None, help="实验数据 CSV")
    parser.add_argument("--iters", type=int, default=None, help="迭代次数")
    parser.add_argument("--n-initial", type=int, default=None, help="初始随机样本数量")
    parser.add_argument("--n-proc", type=int, default=None, help="mpirun 并行核数")
    parser.add_argument("--mpirun-flags", nargs="*", default=None, help="mpirun 额外参数（例如 --oversubscribe）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--kappa", type=float, default=None, help="LCB 探索/开发系数")
    parser.add_argument("--history", type=Path, default=None, help="历史记录 CSV 路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    # 确定运行模式
    hpc_mode = args.hpc or cfg.get("hpc", False)

    # 根据模式选择默认配置
    if hpc_mode:
        default_bashrc = DEFAULT_BASHRC_HPC
        default_postproc = DEFAULT_POSTPROC_HPC
        default_foam_runner = DEFAULT_FOAM_RUNNER_HPC
        print("[info] 运行在 HPC 模式")
    else:
        default_bashrc = str(DEFAULT_BASHRC_PC)
        default_postproc = DEFAULT_POSTPROC_PC
        default_foam_runner = None
        print("[info] 运行在个人电脑模式")

    def cfg_val(name: str, default: Any) -> Any:
        cli_val = getattr(args, name)
        if cli_val is not None:
            return cli_val
        return cfg.get(name, default)

    case_dir = Path(cfg_val("case_dir", Path(__file__).resolve().parent)).resolve()
    foam_bashrc_val = cfg_val("foam_bashrc", default_bashrc)
    foam_runner = cfg_val("foam_runner", default_foam_runner)
    postproc_python = cfg_val("postproc_python", "python")
    postproc_runner_val = cfg_val("postproc_runner", None)
    pvpython_val = cfg_val("pvpython", None)
    postproc_script = Path(cfg_val("postproc_script", default_postproc))
    experimental_data = Path(cfg_val("experimental_data", Path("experimental_data.csv")))
    iters = int(cfg_val("iters", 5))
    n_initial = int(cfg_val("n_initial", 3))
    n_proc = int(cfg_val("n_proc", 12))
    mpirun_flags_val = cfg_val("mpirun_flags", ["--oversubscribe"])
    seed = int(cfg_val("seed", 42))
    kappa = float(cfg_val("kappa", 2.0))
    history = Path(cfg_val("history", Path("bayes_history.csv")))
    foam_bashrc = str(foam_bashrc_val) if foam_bashrc_val else None
    postproc_runner = str(postproc_runner_val) if postproc_runner_val else None
    pvpython = str(pvpython_val) if pvpython_val else None
    if mpirun_flags_val is None:
        mpirun_flags: List[str] = []
    elif isinstance(mpirun_flags_val, str):
        mpirun_flags = [mpirun_flags_val] if mpirun_flags_val else []
    else:
        mpirun_flags = list(mpirun_flags_val)

    exp_path = experimental_data if experimental_data.is_absolute() else (case_dir / experimental_data)

    case = CaseManager(
        case_dir=case_dir,
        postproc_script=postproc_script,
        foam_bashrc=foam_bashrc,
        postproc_python=postproc_python,
        postproc_runner=postproc_runner,
        pvpython=pvpython,
        n_proc=n_proc,
        foam_runner=foam_runner,
        mpirun_flags=tuple(mpirun_flags),
        history_path=history,
        hpc_mode=hpc_mode,
    )
    detail_path = case.history_path.with_name("bayes_power_metrics.csv")

    targets = load_targets(exp_path)
    print(f"[info] 目标功率点: {POWER_SETTINGS}，对齐实验深度/宽度/面积")

    bo = SimpleBO(bounds=PARAM_BOUNDS, n_initial=n_initial, seed=seed, kappa=kappa)

    # 两种模式都支持续跑功能
    history_df_raw = load_history_if_any(case.history_path)
    partial_row, history_df = detect_partial_last_row(history_df_raw)

    for _, r in history_df.iterrows():
        params_prev = {
            "sigma": float(r["sigma"]),
            "Marangoni_Constant": float(r["Marangoni_Constant"]),
            "substrate_temp": float(r["substrate_temp"]),
        }
        obj_prev = float(r["objective"])
        if math.isfinite(obj_prev):
            bo.register(params_prev, obj_prev)

    if partial_row is not None:
        print(f"[resume] 检测到未完成的迭代，参数将续跑: sigma={partial_row['sigma']}, Marangoni={partial_row['Marangoni_Constant']}, substrate_temp={partial_row['substrate_temp']}")

    if not history_df.empty:
        best_idx = history_df["objective"].idxmin()
        best_obj = float(history_df.loc[best_idx, "objective"])
        best_params = {
            "sigma": float(history_df.loc[best_idx, "sigma"]),
            "Marangoni_Constant": float(history_df.loc[best_idx, "Marangoni_Constant"]),
            "substrate_temp": float(history_df.loc[best_idx, "substrate_temp"]),
        }
        print(f"[resume] 已注册 {len(history_df)} 条完整样本，当前最优 {best_obj:.4g}")
    else:
        best_obj = float("inf")
        best_params: Dict[str, float] = {}

    # 续跑时，下一次迭代号 = 完整样本数 + 1（即未完成的那一行）
    start_iter = len(history_df) + 1

    resume_power_data = extract_completed_power_data(partial_row) if partial_row is not None else {}
    resume_params = None
    if partial_row is not None:
        resume_params = {
            "sigma": float(partial_row["sigma"]),
            "Marangoni_Constant": float(partial_row["Marangoni_Constant"]),
            "substrate_temp": float(partial_row["substrate_temp"]),
        }

    if start_iter > iters:
        print(f"[done] 历史记录已包含 {len(history_df)} >= 设定迭代数 {iters}，无需继续。")
        summary_path = case.history_path.with_name("bayes_best.json")
        summary_path.write_text(json.dumps({"best_objective": best_obj, "best_params": best_params, "powers_W": POWER_SETTINGS}, indent=2))
        print(f"[time] {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return

    for it in range(start_iter, iters + 1):
        if resume_params is not None:
            params = resume_params
            print(f"\n[info] 迭代 {it}/{iters} 续跑，跳过已完成的功率点: {sorted(resume_power_data.keys())}")
        else:
            params = bo.suggest()
            print(f"\n[info] 迭代 {it}/{iters}，候选参数: {params}")

        row, power_rows = evaluate_once(case, params, targets, iter_idx=it, resume_power_data=resume_power_data if resume_params is not None else None)
        for pr in power_rows:
            pr.update({
                "iter": it,
                "objective": row["objective"],
                "status": row["status"],
                "timestamp": row["timestamp"],
            })
        # 仅追加本轮新算的功率点，避免重复写入
        if resume_params is not None:
            completed_set = set(resume_power_data.keys())
            append_rows = [pr for pr in power_rows if pr["power_W"] not in completed_set]
        else:
            append_rows = power_rows
        append_detail_records(detail_path, append_rows)
        bo.register(params, row["objective"])
        history_df = pd.concat([history_df, pd.DataFrame([row])], ignore_index=True)
        history_df.to_csv(case.history_path, index=False)

        if row["objective"] < best_obj:
            best_obj = row["objective"]
            best_params = {k: params[k] for k in params}

        print(f"[info] 本次目标值 {row['objective']:.4g}，当前最优 {best_obj:.4g}")
        resume_params = None
        resume_power_data = {}

    summary = {"best_objective": best_obj, "best_params": best_params, "powers_W": POWER_SETTINGS}
    summary_path = case.history_path.with_name("bayes_best.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\n[done] 最优结果写入 {summary_path}")
    print(f"[time] {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

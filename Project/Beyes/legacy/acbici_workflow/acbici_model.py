#!/usr/bin/env python3
"""
ACBICI模型封装 - OpenFOAM熔池仿真模型

该模块定义了用于ACBICI贝叶斯校准的OpenFOAM模型类。
模型接收材料参数（sigma, Marangoni常数, 基板温度）和功率作为输入，
输出熔池的宽度、深度和面积。
"""

import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

sys.path.append(str(Path(__file__).parent.parent / "ACBICI" / "src"))
from ACBICI import ACBICImodel, Uniform


# ========== 工具函数 ==========

def _run(cmd: str, workdir: Path) -> None:
    """执行shell命令"""
    print(f"[cmd] {cmd}")
    subprocess.run(cmd, cwd=str(workdir), shell=True, check=True)


def _run_script(script: str, workdir: Path, runner: Optional[str]) -> None:
    """执行脚本，支持自定义runner"""
    script = script.strip() + ("\n" if not script.endswith("\n") else "")
    label = runner or "bash -lc"
    print(f"[cmd:{label}] <<'EOF'\n{script}EOF")

    if runner:
        subprocess.run(runner, cwd=str(workdir), shell=True, check=True, text=True, input=script)
    else:
        subprocess.run(["bash", "-lc", script], cwd=str(workdir), check=True)


def _update_dict_value(path: Path, key: str, value: float) -> None:
    """更新OpenFOAM字典文件中的值"""
    lines = path.read_text().splitlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\b")

    for i, line in enumerate(lines):
        if pattern.match(line):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}{key:<23}{value};"
            path.write_text("\n".join(lines) + "\n")
            return

    lines.append(f"{key:<23}{value};")
    path.write_text("\n".join(lines) + "\n")


def _update_T_internal(path: Path, temperature: float) -> None:
    """更新温度场的初始值"""
    lines = path.read_text().splitlines()
    pattern = re.compile(r"^\s*internalField\s+uniform\s+([0-9eE+\-\.]+)")

    for i, line in enumerate(lines):
        if pattern.search(line):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}internalField   uniform {temperature};"
            path.write_text("\n".join(lines) + "\n")
            return
    raise RuntimeError(f"未在 {path} 中找到 internalField 行")


def _rewrite_power_file(path: Path, power_w: float) -> None:
    """修改激光功率文件"""
    lines = path.read_text().splitlines()
    pattern = re.compile(r"\(\s*([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)\s*\)")

    new_lines = []
    for line in lines:
        m = pattern.search(line)
        if m:
            t_str, val_str = m.group(1), m.group(2)
            new_val = power_w if float(val_str) != 0.0 else 0.0
            new_lines.append(f"    ({t_str}           {new_val})")
        else:
            new_lines.append(line)
    path.write_text("\n".join(new_lines) + "\n")


# ========== OpenFOAM案例管理器 ==========

class OpenFOAMCaseManager:
    """管理OpenFOAM案例的运行和后处理"""

    def __init__(self, case_dir: Path, postproc_script: Path, foam_bashrc: Optional[str] = None,
                 postproc_python: str = "python", postproc_runner: Optional[str] = None,
                 pvpython: Optional[str] = None, n_proc: int = 12,
                 foam_runner: Optional[str] = None, mpirun_flags: Tuple[str, ...] = ("--oversubscribe",),
                 hpc_mode: bool = False):
        self.case_dir = case_dir.resolve()
        self.postproc_script = postproc_script.expanduser().resolve()
        self.foam_bashrc = foam_bashrc
        self.postproc_python = postproc_python
        self.postproc_runner = postproc_runner
        self.pvpython = pvpython
        self.n_proc = n_proc
        self.foam_runner = foam_runner
        self.mpirun_flags = tuple(mpirun_flags)
        self.hpc_mode = hpc_mode

        # 关键文件路径
        self.transport_props = case_dir / "constant" / "transportProperties"
        self.temp_field = case_dir / "initial" / "T"
        self.time_vs_power = case_dir / "constant" / "timeVsLaserPower"
        self.laser_props = case_dir / "constant" / "LaserProperties"
        self.main_foam = case_dir / "main.foam"

    def update_parameters(self, sigma: float, marangoni: float, substrate_temp: float, absorptivity: float = 1.0) -> None:
        """
        更新材料参数

        Parameters
        ----------
        sigma : float
            表面张力系数
        marangoni : float
            Marangoni 常数
        substrate_temp : float
            基板温度 (K)
        absorptivity : float, optional
            激光吸收率系数 (默认: 1.0)
        """
        _update_dict_value(self.transport_props, "sigma", sigma)
        _update_dict_value(self.transport_props, "Marangoni_Constant", marangoni)
        _update_T_internal(self.temp_field, substrate_temp)
        _update_dict_value(self.laser_props, "absorptivity", absorptivity)

    def set_power(self, power_w: float, absorptivity: float = 1.0) -> None:
        """
        设置激光功率（考虑吸收率）

        实际功率 = 名义功率 × 吸收率
        """
        effective_power = power_w * absorptivity
        _rewrite_power_file(self.time_vs_power, effective_power)

    def run_simulation(self) -> None:
        """运行OpenFOAM仿真"""
        (self._run_simulation_hpc if self.hpc_mode else self._run_simulation_pc)()

    def _run_simulation_hpc(self) -> None:
        """HPC模式运行仿真"""
        mpirun_cmd = ["mpirun", *self.mpirun_flags, "-np", str(self.n_proc),
                     "laserbeamFoam", "-parallel"]

        lines = ["set -eo pipefail"]
        if self.foam_bashrc:
            lines.append(f"source {shlex.quote(self.foam_bashrc)}")
        lines.extend([
            "bash ./Allclean || true", "rm -rf 0 processor*", "cp -r initial 0",
            "touch main.foam", "blockMesh", "setSolidFraction", "decomposePar",
            " ".join(mpirun_cmd), "reconstructPar -latestTime"
        ])
        _run_script("\n".join(lines), self.case_dir, self.foam_runner)

    def _run_simulation_pc(self) -> None:
        """个人电脑模式运行仿真"""
        DEFAULT_BASHRC = "/usr/lib/openfoam/openfoam2506/etc/bashrc"
        bashrc = shlex.quote(self.foam_bashrc or DEFAULT_BASHRC)
        case_dir = shlex.quote(str(self.case_dir))
        mpirun_flags = " ".join(self.mpirun_flags) if self.mpirun_flags else "--oversubscribe"

        cmd = (f"bash -lc 'set -eo pipefail; "
               f"export WM_PROJECT_SITE=${{WM_PROJECT_SITE-}}; source {bashrc} && "
               f"cd {case_dir} && bash ./Allclean || true; rm -rf 0 processor*; "
               f"cp -r initial 0; touch main.foam; blockMesh; setSolidFraction; decomposePar; "
               f"mpirun -np {self.n_proc} {mpirun_flags} laserbeamFoam -parallel; "
               f"reconstructPar -latestTime'")
        _run(cmd, self.case_dir)

    def run_postprocess(self) -> None:
        """运行后处理脚本"""
        (self._run_postprocess_hpc if self.hpc_mode else self._run_postprocess_pc)()

    def _run_postprocess_hpc(self) -> None:
        """HPC模式后处理"""
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

    def _run_postprocess_pc(self) -> None:
        """个人电脑模式后处理"""
        _run(f"{self.postproc_python} {shlex.quote(str(self.postproc_script))}", self.case_dir)

    def read_metrics(self) -> Dict[str, float]:
        """读取后处理结果"""
        metrics_path = self.case_dir / "cross_sections_statistics.csv"
        if not metrics_path.exists():
            raise FileNotFoundError(f"缺少 {metrics_path}，后处理是否成功？")

        df = pd.read_csv(metrics_path)
        return {
            "width_mean_m": float(df["width"].mean()),
            "depth_mean_m": float(df["depth"].mean()),
            "area_mean_m2": float(df["area"].mean()) if "area" in df.columns else math.nan,
        }


# ========== ACBICI模型类 ==========

class MeltpoolModel(ACBICImodel):
    """
    熔池仿真ACBICI模型

    输入维度 (xdim=1): 激光功率 (W)
    参数维度 (pdim=4): sigma, Marangoni_Constant, substrate_temp, absorptivity
    输出维度 (ydim=3): 宽度(μm), 深度(μm), 面积(μm²)
    """

    def __init__(self, config_path: Path = Path("../config.yaml")):
        self.xdim, self.ydim = 1, 3

        # 添加参数及其先验分布
        self.addParameter(label=r'$\sigma$', prior=Uniform(a=1.0, b=2.0))
        self.addParameter(label=r'$\gamma$', prior=Uniform(a=-8e-4, b=-4e-6))
        self.addParameter(label=r'$T_s$', prior=Uniform(a=300.0, b=800.0))
        self.addParameter(label=r'$\eta$', prior=Uniform(a=0.5, b=3.0))  # 吸收率

        # 加载配置并初始化案例管理器
        self.config = self._load_config(config_path)
        self.case_manager = self._setup_case_manager()

    def _load_config(self, config_path: Path) -> Dict:
        """加载YAML配置文件"""
        resolved = config_path.expanduser()
        if not resolved.is_absolute():
            resolved = (Path.cwd() / resolved).resolve()
        else:
            resolved = resolved.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"配置文件不存在: {resolved}")
        self.config_path = resolved
        with open(resolved, 'r') as f:
            return yaml.safe_load(f)

    def _setup_case_manager(self) -> OpenFOAMCaseManager:
        """根据配置创建案例管理器"""
        cfg = self.config
        config_dir = self.config_path.parent if hasattr(self, "config_path") else Path.cwd()
        case_dir = Path(cfg.get("case_dir", ".")).expanduser()
        if not case_dir.is_absolute():
            case_dir = (config_dir / case_dir).resolve()
        else:
            case_dir = case_dir.resolve()

        # 后处理脚本路径
        postproc_script_str = cfg.get("postproc_script",
                                      "../../applications/scripts/postProcessing/characterise_meltpool.py")
        postproc_script = Path(postproc_script_str)
        if not postproc_script.is_absolute():
            postproc_script = case_dir / postproc_script

        return OpenFOAMCaseManager(
            case_dir=case_dir, postproc_script=postproc_script,
            foam_bashrc=cfg.get("foam_bashrc"),
            postproc_python=cfg.get("postproc_python", "python"),
            postproc_runner=cfg.get("postproc_runner"),
            pvpython=cfg.get("pvpython"), n_proc=cfg.get("n_proc", 12),
            foam_runner=cfg.get("foam_runner"),
            mpirun_flags=tuple(cfg.get("mpirun_flags", ["--oversubscribe"])),
            hpc_mode=cfg.get("hpc", False),
        )

    def symbolicModel(self, x, p):
        """
        符号模型 - OpenFOAM仿真的包装

        Parameters
        ----------
        x : numpy.ndarray, shape (n_samples, xdim)
            输入数组，每行是一个功率值 (W)
        p : numpy.ndarray, shape (n_samples, pdim)
            参数数组，每行是 [sigma, Marangoni_Constant, substrate_temp, absorptivity]

        Returns
        -------
        numpy.ndarray, shape (n_samples, ydim)
            输出数组，每行是 [width_μm, depth_μm, area_μm²]
        """
        x, p = np.atleast_2d(x), np.atleast_2d(p)
        n_samples = x.shape[0]
        results = np.zeros((n_samples, self.ydim))

        for i in range(n_samples):
            power_w = x[i, 0]
            sigma, marangoni, substrate_temp, absorptivity = p[i, 0], p[i, 1], p[i, 2], p[i, 3]

            print(f"\n[Model] 运行样本 {i+1}/{n_samples}")
            print(f"  功率: {power_w:.1f} W")
            print(f"  参数: σ={sigma:.4f}, γ={marangoni:.4e}, T_s={substrate_temp:.1f} K, η={absorptivity:.3f}")
            print(f"  有效功率: {power_w * absorptivity:.1f} W")

            try:
                # 运行仿真和后处理
                self.case_manager.update_parameters(sigma, marangoni, substrate_temp, absorptivity)
                self.case_manager.set_power(power_w, absorptivity)
                self.case_manager.run_simulation()
                self.case_manager.run_postprocess()

                # 读取结果（转换为μm）
                metrics = self.case_manager.read_metrics()
                results[i, :] = [metrics["width_mean_m"] * 1e6,
                                metrics["depth_mean_m"] * 1e6,
                                metrics["area_mean_m2"] * 1e12]

                print(f"  结果: 宽={results[i,0]:.2f}μm, 深={results[i,1]:.2f}μm, 面积={results[i,2]:.2f}μm²")

            except Exception as e:
                print(f"[警告] 样本 {i+1} 仿真失败: {e}")
                results[i, :] = np.nan

        return results

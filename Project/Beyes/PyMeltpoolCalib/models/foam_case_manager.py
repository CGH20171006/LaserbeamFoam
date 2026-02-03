"""
OpenFOAM 案例管理器

管理 OpenFOAM 案例的运行和后处理
从原 acbici_model.py 迁移
"""

from __future__ import annotations

import math
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd


# ========== 工具函数 ==========


def _run(cmd: str, workdir: Path) -> None:
    """执行 shell 命令"""
    print(f"[cmd] {cmd}")
    subprocess.run(cmd, cwd=str(workdir), shell=True, check=True)


def _run_script(script: str, workdir: Path, runner: Optional[str]) -> None:
    """执行脚本，支持自定义 runner"""
    script = script.strip() + ("\n" if not script.endswith("\n") else "")
    label = runner or "bash -lc"
    print(f"[cmd:{label}] <<'EOF'\n{script}EOF")

    if runner:
        subprocess.run(
            runner, cwd=str(workdir), shell=True, check=True, text=True, input=script
        )
    else:
        subprocess.run(["bash", "-lc", script], cwd=str(workdir), check=True)


def _update_dict_value(path: Path, key: str, value: float) -> None:
    """更新 OpenFOAM 字典文件中的值"""
    lines = path.read_text().splitlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\b")

    for i, line in enumerate(lines):
        if pattern.match(line):
            indent = line[: len(line) - len(line.lstrip())]
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
            indent = line[: len(line) - len(line.lstrip())]
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


# ========== OpenFOAM 案例管理器 ==========


class OpenFOAMCaseManager:
    """
    管理 OpenFOAM 案例的运行和后处理

    Attributes
    ----------
    case_dir : Path
        案例目录
    postproc_script : Path
        后处理脚本路径
    foam_bashrc : str, optional
        OpenFOAM bashrc 路径
    foam_runner : str, optional
        OpenFOAM 运行器命令
    n_proc : int
        MPI 并行核数
    hpc_mode : bool
        是否使用 HPC 模式
    """

    def __init__(
        self,
        case_dir: Path,
        postproc_script: Path,
        foam_bashrc: Optional[str] = None,
        postproc_python: str = "python",
        postproc_runner: Optional[str] = None,
        pvpython: Optional[str] = None,
        n_proc: int = 12,
        foam_runner: Optional[str] = None,
        mpirun_flags: Tuple[str, ...] = ("--oversubscribe",),
        hpc_mode: bool = False,
    ):
        """
        初始化案例管理器

        Parameters
        ----------
        case_dir : Path
            OpenFOAM 案例目录
        postproc_script : Path
            后处理脚本路径
        foam_bashrc : str, optional
            OpenFOAM bashrc 路径
        postproc_python : str
            后处理 Python 解释器
        postproc_runner : str, optional
            后处理运行器
        pvpython : str, optional
            pvpython 可执行文件路径
        n_proc : int
            MPI 并行核数
        foam_runner : str, optional
            OpenFOAM 运行器命令 (如 "of2506")
        mpirun_flags : tuple
            mpirun 额外参数
        hpc_mode : bool
            是否使用 HPC 模式
        """
        self.case_dir = Path(case_dir).resolve()
        self.postproc_script = Path(postproc_script).expanduser().resolve()
        self.foam_bashrc = foam_bashrc
        self.postproc_python = postproc_python
        self.postproc_runner = postproc_runner
        self.pvpython = pvpython
        self.n_proc = n_proc
        self.foam_runner = foam_runner
        self.mpirun_flags = tuple(mpirun_flags)
        self.hpc_mode = hpc_mode

        # 关键文件路径
        self.transport_props = self.case_dir / "constant" / "transportProperties"
        self.temp_field = self.case_dir / "initial" / "T"
        self.time_vs_power = self.case_dir / "constant" / "timeVsLaserPower"
        self.laser_props = self.case_dir / "constant" / "LaserProperties"
        self.main_foam = self.case_dir / "main.foam"

    def update_parameters(
        self,
        sigma: float,
        marangoni: float,
        substrate_temp: float,
        absorptivity: float = 1.0,
    ) -> None:
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

        Parameters
        ----------
        power_w : float
            名义激光功率 (W)
        absorptivity : float
            吸收率系数
        """
        effective_power = power_w * absorptivity
        _rewrite_power_file(self.time_vs_power, effective_power)

    def run_simulation(self) -> None:
        """运行 OpenFOAM 仿真"""
        if self.hpc_mode:
            self._run_simulation_hpc()
        else:
            self._run_simulation_pc()

    def _run_simulation_hpc(self) -> None:
        """HPC 模式运行仿真"""
        mpirun_cmd = [
            "mpirun",
            *self.mpirun_flags,
            "-np",
            str(self.n_proc),
            "laserbeamFoam",
            "-parallel",
            ">log.laserbeamFoam",
            "2>&1",
        ]

        lines = ["set -eo pipefail"]
        if self.foam_bashrc:
            lines.append(f"source {shlex.quote(self.foam_bashrc)}")
        lines.extend(
            [
                "bash ./Allclean || true",
                "rm -rf 0 processor*",
                "cp -r initial 0",
                "touch main.foam",
                "blockMesh >log.blockMesh 2>&1",
                "setSolidFraction >log.setSolidFraction 2>&1",
                "decomposePar >log.decomposePar 2>&1",
                " ".join(mpirun_cmd),
                "reconstructPar -latestTime >log.reconstructPar 2>&1",
            ]
        )
        _run_script("\n".join(lines), self.case_dir, self.foam_runner)

    def _run_simulation_pc(self) -> None:
        """个人电脑模式运行仿真"""
        DEFAULT_BASHRC = "/usr/lib/openfoam/openfoam2506/etc/bashrc"
        bashrc = shlex.quote(self.foam_bashrc or DEFAULT_BASHRC)
        case_dir = shlex.quote(str(self.case_dir))
        mpirun_flags = (
            " ".join(self.mpirun_flags) if self.mpirun_flags else "--oversubscribe"
        )

        cmd = (
            f"bash -lc 'set -eo pipefail; "
            f"export WM_PROJECT_SITE=${{WM_PROJECT_SITE-}}; source {bashrc} && "
            f"cd {case_dir} && bash ./Allclean || true; rm -rf 0 processor*; "
            f"cp -r initial 0; touch main.foam; "
            f"blockMesh >log.blockMesh 2>&1; "
            f"setSolidFraction >log.setSolidFraction 2>&1; "
            f"decomposePar >log.decomposePar 2>&1; "
            f"mpirun -np {self.n_proc} {mpirun_flags} laserbeamFoam -parallel >log.laserbeamFoam 2>&1; "
            f"reconstructPar -latestTime >log.reconstructPar 2>&1'"
        )
        _run(cmd, self.case_dir)

    def run_postprocess(self) -> None:
        """运行后处理脚本"""
        if self.hpc_mode:
            self._run_postprocess_hpc()
        else:
            self._run_postprocess_pc()

    def _run_postprocess_hpc(self) -> None:
        """HPC 模式后处理"""
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
        _run(
            f"{self.postproc_python} {shlex.quote(str(self.postproc_script))}",
            self.case_dir,
        )

    def read_metrics(self) -> Dict[str, float]:
        """
        读取后处理结果

        Returns
        -------
        dict
            包含 width_mean_m, depth_mean_m, area_mean_m2 的字典
        """
        metrics_path = self.case_dir / "cross_sections_statistics.csv"
        if not metrics_path.exists():
            raise FileNotFoundError(f"缺少 {metrics_path}，后处理是否成功？")

        df = pd.read_csv(metrics_path)
        return {
            "width_mean_m": float(df["width"].mean()),
            "depth_mean_m": float(df["depth"].mean()),
            "area_mean_m2": float(df["area"].mean()) if "area" in df.columns else math.nan,
        }

    def archive_latest_time(self, dest_parent: Path, new_name: Optional[str] = None) -> None:
        """
        归档最后一个时间步的目录和后处理文件

        Parameters
        ----------
        dest_parent : Path
            目标父目录
        new_name : str, optional
            新目录名，如果为 None 则保持原名
        """
        import shutil

        # 找到最新的数字目录
        time_dirs = []
        for p in self.case_dir.iterdir():
            if p.is_dir():
                try:
                    # 尝试解析为浮点数，排除 processor* 等
                    float(p.name)
                    time_dirs.append(p)
                except ValueError:
                    continue

        if not time_dirs:
            print("  [Archive] 未找到时间目录")
            return

        # 按数值排序
        latest_dir = sorted(time_dirs, key=lambda p: float(p.name))[-1]

        dest_name = new_name if new_name else latest_dir.name
        dest_path = dest_parent / dest_name

        if dest_path.exists():
            shutil.rmtree(dest_path)

        try:
            shutil.copytree(latest_dir, dest_path)
            print(f"  [Archive] 已保存时间目录 {latest_dir.name} -> {dest_path}")

            # 归档后处理生成的 CSV 文件
            postproc_files = [
                "cross_sections_statistics.csv",
                "meltpool.csv",
                "row_statistics.csv",
                "meltpool_slice_xmid.csv",
            ]

            archived_count = 0
            for fname in postproc_files:
                src_file = self.case_dir / fname
                if src_file.exists():
                    dest_file = dest_path / fname
                    try:
                        shutil.copy2(src_file, dest_file)
                        archived_count += 1
                    except Exception as e:
                        print(f"  [Archive] 警告: 复制 {fname} 失败: {e}")

            if archived_count > 0:
                print(f"  [Archive] 已保存 {archived_count} 个后处理文件")

        except Exception as e:
            print(f"  [Archive] 保存失败: {e}")

    @classmethod
    def from_config(cls, config) -> "OpenFOAMCaseManager":
        """
        从配置对象创建案例管理器

        Parameters
        ----------
        config : BaseConfig
            配置对象

        Returns
        -------
        OpenFOAMCaseManager
        """
        return cls(
            case_dir=config.case_dir,
            postproc_script=config.postproc_script,
            foam_bashrc=config.foam_bashrc,
            postproc_python=config.postproc_python,
            postproc_runner=getattr(config, "postproc_runner", None),
            pvpython=config.pvpython,
            n_proc=config.n_proc,
            foam_runner=config.foam_runner,
            mpirun_flags=config.mpirun_flags,
            hpc_mode=config.hpc_mode,
        )

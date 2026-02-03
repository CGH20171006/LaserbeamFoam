"""
基础配置类

所有优化方法共享的配置参数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_case_dir() -> Path:
    return PROJECT_ROOT.parent


def _default_postproc_script() -> Path:
    return PROJECT_ROOT.parent.parent / "applications" / "scripts" / "postProcessing" / "characterise_meltpool.py"


def _default_exp_csv() -> Path:
    return PROJECT_ROOT / "experimental_data.csv"


def _default_runs_root() -> Path:
    return PROJECT_ROOT / "runs"


@dataclass
class BaseConfig:
    """
    所有优化方法共享的基础配置

    Attributes
    ----------
    case_dir : Path
        OpenFOAM 案例目录
    postproc_script : Path
        后处理脚本路径
    exp_csv : Path
        实验数据 CSV 文件路径
    runs_root : Path
        运行结果根目录
    foam_bashrc : str, optional
        OpenFOAM bashrc 路径
    foam_runner : str, optional
        OpenFOAM 运行器命令 (如 "of2506")
    n_proc : int
        MPI 并行核数
    hpc_mode : bool
        是否使用 HPC 模式
    mpirun_flags : tuple
        mpirun 额外参数
    postproc_python : str
        后处理 Python 解释器
    postproc_runner : str, optional
        后处理运行器
    pvpython : str, optional
        pvpython 路径
    sigma_bounds : tuple
        sigma 参数边界
    marangoni_bounds : tuple
        Marangoni 常数边界
    substrate_temp_bounds : tuple
        基板温度边界 (K)
    absorptivity_bounds : tuple
        吸收率边界
    power_range : tuple
        激光功率范围 (W)
    """

    # === 路径配置 ===
    case_dir: Path = field(default_factory=_default_case_dir)
    postproc_script: Path = field(default_factory=_default_postproc_script)
    exp_csv: Path = field(default_factory=_default_exp_csv)
    runs_root: Path = field(default_factory=_default_runs_root)

    # === OpenFOAM 配置 ===
    foam_bashrc: Optional[str] = None
    foam_runner: Optional[str] = None
    n_proc: int = 12
    hpc_mode: bool = False
    mpirun_flags: Tuple[str, ...] = ("--oversubscribe",)
    postproc_python: str = "python"
    postproc_runner: Optional[str] = None
    pvpython: Optional[str] = None

    # === 参数边界 ===
    sigma_bounds: Tuple[float, float] = (1.0, 2.0)
    marangoni_bounds: Tuple[float, float] = (-8e-4, -4e-6)
    substrate_temp_bounds: Tuple[float, float] = (300.0, 800.0)
    absorptivity_bounds: Tuple[float, float] = (0.5, 3.0)

    # === 功率范围 ===
    power_range: Tuple[float, float] = (140.0, 260.0)

    # === 输出权重配置 ===
    output_weights: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])

    # === 参数选择性优化配置 ===
    active_params: Optional[List[str]] = None  # None表示优化所有参数
    fixed_values: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """确保路径类型正确并验证配置"""
        self.case_dir = Path(self.case_dir)
        self.postproc_script = Path(self.postproc_script)
        self.exp_csv = Path(self.exp_csv)
        self.runs_root = Path(self.runs_root)

        # 验证output_weights长度
        if len(self.output_weights) != 3:
            raise ValueError("output_weights must have 3 elements [width, depth, area]")

        # 验证active_params
        if self.active_params is not None:
            from ..models.meltpool_params import PARAM_NAMES
            invalid = set(self.active_params) - set(PARAM_NAMES)
            if invalid:
                raise ValueError(f"Invalid active_params: {invalid}")

        # 验证fixed_values
        if self.fixed_values:
            from ..models.meltpool_params import PARAM_NAMES
            for name in self.fixed_values:
                if name not in PARAM_NAMES:
                    raise ValueError(f"Unknown parameter in fixed_values: {name}")

    def get_param_bounds(self) -> List[Tuple[float, float]]:
        """
        返回参数边界列表

        Returns
        -------
        list of tuple
            [(sigma_min, sigma_max), (marangoni_min, marangoni_max), ...]
        """
        return [
            self.sigma_bounds,
            self.marangoni_bounds,
            self.substrate_temp_bounds,
            self.absorptivity_bounds,
        ]

    def get_param_names(self) -> List[str]:
        """返回参数名称列表"""
        return ["sigma", "marangoni", "substrate_temp", "absorptivity"]

    def build_runs_path(self, method: str) -> Path:
        """
        构建带时间戳的运行目录

        Parameters
        ----------
        method : str
            优化方法名称 (acbici, bayes, gradient)

        Returns
        -------
        Path
            形如 runs/runs_bayes_20250119_120000
        """
        safe_method = method.strip().lower().replace(" ", "_")
        if not safe_method:
            safe_method = "unknown"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.runs_root / f"runs_{safe_method}_{timestamp}"

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "BaseConfig":
        """
        从 YAML 文件加载配置

        Parameters
        ----------
        yaml_path : Path
            YAML 配置文件路径

        Returns
        -------
        BaseConfig
            配置实例
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # 处理路径
        config_dir = yaml_path.parent
        if "case_dir" in data:
            case_dir = Path(data["case_dir"])
            if not case_dir.is_absolute():
                data["case_dir"] = config_dir / case_dir

        # 转换 mpirun_flags 为元组
        if "mpirun_flags" in data and isinstance(data["mpirun_flags"], list):
            data["mpirun_flags"] = tuple(data["mpirun_flags"])

        # 过滤掉不在 dataclass 中的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            "case_dir": str(self.case_dir),
            "postproc_script": str(self.postproc_script),
            "exp_csv": str(self.exp_csv),
            "runs_root": str(self.runs_root),
            "foam_bashrc": self.foam_bashrc,
            "foam_runner": self.foam_runner,
            "n_proc": self.n_proc,
            "hpc_mode": self.hpc_mode,
            "mpirun_flags": list(self.mpirun_flags),
            "postproc_python": self.postproc_python,
            "postproc_runner": self.postproc_runner,
            "pvpython": self.pvpython,
            "sigma_bounds": list(self.sigma_bounds),
            "marangoni_bounds": list(self.marangoni_bounds),
            "substrate_temp_bounds": list(self.substrate_temp_bounds),
            "absorptivity_bounds": list(self.absorptivity_bounds),
            "power_range": list(self.power_range),
            "output_weights": self.output_weights,
            "active_params": self.active_params,
            "fixed_values": self.fixed_values,
        }

    def save_yaml(self, yaml_path: Path) -> None:
        """
        保存配置到 YAML 文件

        Parameters
        ----------
        yaml_path : Path
            YAML 文件保存路径
        """
        yaml_path = Path(yaml_path)
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(yaml_path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

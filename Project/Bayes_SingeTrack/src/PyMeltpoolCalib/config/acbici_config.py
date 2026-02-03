"""
ACBICI 贝叶斯校准配置

用于 MCMC 后验分布采样的参数配置
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .base_config import BaseConfig, PROJECT_ROOT


def _default_synthetic_data_file() -> Path:
    return PROJECT_ROOT / "data" / "synthetic_data.dat"


@dataclass
class ACBICIConfig(BaseConfig):
    """
    ACBICI 贝叶斯校准配置

    继承 BaseConfig，添加 MCMC 和 GP 代理模型参数

    Attributes
    ----------
    synthetic_data_file : Path
        合成数据文件路径
    n_synthetic_samples : int
        生成合成数据的样本数
    kernel : str
        高斯过程核函数 ("expo", "matern32", "matern52", "ratquad")
    nsteps : int
        MCMC 总步数
    burn : float
        燃烧期比例 (0-1)
    nwalkers : int
        并行 walker 数量
    error_type : str
        误差模型类型 ("known" 或 "unknown")
    exp_std : float
        已知实验误差标准差 (μm)
    exp_std_prior_sigma : float
        未知误差时的先验尺度参数
    max_iterations : int
        迭代校准最大迭代次数
    n_new_samples_per_iter : int
        每轮迭代新增样本数
    sampling_strategy : str
        采样策略 ("map_only", "posterior", "hybrid")
    tol_param_change : float
        参数相对变化收敛阈值
    tol_std : float
        后验标准差收敛阈值
    name : str
        校准器名称（用于输出目录）
    """

    # === 合成数据 ===
    synthetic_data_file: Path = field(default_factory=_default_synthetic_data_file)
    n_synthetic_samples: int = 20

    # === GP 代理模型 ===
    kernel: Literal["expo", "matern32", "matern52", "ratquad"] = "matern32"

    # === MCMC 参数 ===
    nsteps: int = 500
    burn: float = 0.2
    nwalkers: int = 16

    # === 误差模型 ===
    error_type: Literal["known", "unknown"] = "known"
    exp_std: float = 5.0  # 已知误差时的标准差 (μm)
    exp_std_prior_sigma: float = 10.0  # 未知误差时的先验尺度

    # === 迭代校准 ===
    max_iterations: int = 5
    n_new_samples_per_iter: int = 3
    sampling_strategy: Literal["map_only", "posterior", "hybrid"] = "hybrid"
    tol_param_change: float = 0.01
    tol_std: float = 0.05

    # === 输出 ===
    name: str = "meltpool_acbici"

    def __post_init__(self):
        """确保路径类型正确"""
        super().__post_init__()
        self.synthetic_data_file = Path(self.synthetic_data_file)

    def to_dict(self) -> dict:
        """转换为字典"""
        base_dict = super().to_dict()
        base_dict.update({
            "synthetic_data_file": str(self.synthetic_data_file),
            "n_synthetic_samples": self.n_synthetic_samples,
            "kernel": self.kernel,
            "nsteps": self.nsteps,
            "burn": self.burn,
            "nwalkers": self.nwalkers,
            "error_type": self.error_type,
            "exp_std": self.exp_std,
            "exp_std_prior_sigma": self.exp_std_prior_sigma,
            "max_iterations": self.max_iterations,
            "n_new_samples_per_iter": self.n_new_samples_per_iter,
            "sampling_strategy": self.sampling_strategy,
            "tol_param_change": self.tol_param_change,
            "tol_std": self.tol_std,
            "name": self.name,
        })
        return base_dict

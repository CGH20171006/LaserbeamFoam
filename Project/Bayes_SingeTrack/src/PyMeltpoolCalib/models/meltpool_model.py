"""
熔池仿真 ACBICI 模型

封装 OpenFOAM 仿真为 ACBICI 接口
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

# 动态导入 ACBICI
ACBICI_PATH = Path(__file__).parent.parent.parent / "ACBICI" / "src"
if str(ACBICI_PATH) not in sys.path:
    sys.path.insert(0, str(ACBICI_PATH))

from ACBICI import ACBICImodel, Uniform

from .foam_case_manager import OpenFOAMCaseManager
from .meltpool_params import DEFAULT_BOUNDS, PARAM_LATEX_LABELS

if TYPE_CHECKING:
    from ..config.base_config import BaseConfig


class MeltpoolModel(ACBICImodel):
    """
    熔池仿真 ACBICI 模型

    输入维度 (xdim=1): 激光功率 (W)
    参数维度 (pdim=4): sigma, Marangoni_Constant, substrate_temp, absorptivity
    输出维度 (ydim=3): 宽度(μm), 深度(μm), 面积(μm²)

    Attributes
    ----------
    xdim : int
        输入维度 (功率)
    ydim : int
        输出维度 (宽度, 深度, 面积)
    case_manager : OpenFOAMCaseManager
        OpenFOAM 案例管理器
    """

    def __init__(self, config: "BaseConfig"):
        """
        初始化熔池模型

        Parameters
        ----------
        config : BaseConfig
            配置对象
        """
        self.xdim = 1
        self.ydim = 3
        self.config = config

        # 添加参数及其先验分布
        sigma_bounds = config.sigma_bounds
        marangoni_bounds = config.marangoni_bounds
        temp_bounds = config.substrate_temp_bounds
        absorptivity_bounds = config.absorptivity_bounds

        self.addParameter(
            label=PARAM_LATEX_LABELS[0],
            prior=Uniform(a=sigma_bounds[0], b=sigma_bounds[1]),
        )
        self.addParameter(
            label=PARAM_LATEX_LABELS[1],
            prior=Uniform(a=marangoni_bounds[0], b=marangoni_bounds[1]),
        )
        self.addParameter(
            label=PARAM_LATEX_LABELS[2],
            prior=Uniform(a=temp_bounds[0], b=temp_bounds[1]),
        )
        self.addParameter(
            label=PARAM_LATEX_LABELS[3],
            prior=Uniform(a=absorptivity_bounds[0], b=absorptivity_bounds[1]),
        )

        # 初始化案例管理器
        self.case_manager = OpenFOAMCaseManager.from_config(config)

    def symbolicModel(self, x, p):
        """
        符号模型 - OpenFOAM 仿真的包装

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
        x = np.atleast_2d(x)
        p = np.atleast_2d(p)
        n_samples = x.shape[0]
        results = np.zeros((n_samples, self.ydim))

        for i in range(n_samples):
            power_w = x[i, 0]
            sigma = p[i, 0]
            marangoni = p[i, 1]
            substrate_temp = p[i, 2]
            absorptivity = p[i, 3]

            print(f"\n[Model] 运行样本 {i + 1}/{n_samples}")
            print(f"  功率: {power_w:.1f} W")
            print(
                f"  参数: σ={sigma:.4f}, γ={marangoni:.4e}, "
                f"T_s={substrate_temp:.1f} K, η={absorptivity:.3f}"
            )
            print(f"  有效功率: {power_w * absorptivity:.1f} W")

            try:
                # 运行仿真和后处理
                self.case_manager.update_parameters(
                    sigma, marangoni, substrate_temp, absorptivity
                )
                self.case_manager.set_power(power_w, absorptivity)
                self.case_manager.run_simulation()
                self.case_manager.run_postprocess()

                # 读取结果（转换为 μm）
                metrics = self.case_manager.read_metrics()
                results[i, :] = [
                    metrics["width_mean_m"] * 1e6,
                    metrics["depth_mean_m"] * 1e6,
                    metrics["area_mean_m2"] * 1e12,
                ]

                print(
                    f"  结果: 宽={results[i, 0]:.2f}μm, "
                    f"深={results[i, 1]:.2f}μm, 面积={results[i, 2]:.2f}μm²"
                )

            except Exception as e:
                print(f"[警告] 样本 {i + 1} 仿真失败: {e}")
                results[i, :] = np.nan

        return results

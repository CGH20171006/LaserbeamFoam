"""
仿真运行器

封装 OpenFOAMCaseManager，提供简化的接口用于优化循环
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Tuple

import numpy as np

from ..models.foam_case_manager import OpenFOAMCaseManager
from .objective import PENALTY_VALUE

if TYPE_CHECKING:
    from ..config.base_config import BaseConfig


class SimulationRunner:
    """
    统一仿真运行器

    封装 OpenFOAMCaseManager，提供简化的接口用于优化循环

    Attributes
    ----------
    config : BaseConfig
        配置对象
    case_manager : OpenFOAMCaseManager
        OpenFOAM 案例管理器
    work_dir : Path
        工作目录
    eval_count : int
        评估计数器
    """

    def __init__(
        self,
        config: "BaseConfig",
        work_dir: Optional[Path] = None,
    ):
        """
        初始化仿真运行器

        Parameters
        ----------
        config : BaseConfig
            配置对象
        work_dir : Path, optional
            工作目录，默认为 config.runs_root / "simulations"
        """
        self.config = config
        self.work_dir = work_dir or config.runs_root / "simulations"
        self.work_dir = Path(self.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 OpenFOAM 案例管理器
        self.case_manager = OpenFOAMCaseManager.from_config(config)

        # 评估计数器
        self.eval_count = 0

    def run(
        self,
        params: np.ndarray,
        power_points: np.ndarray,
        job_id: Optional[str | int] = None,
        on_power_complete: Optional[Callable[[int, float, np.ndarray], None]] = None,
    ) -> np.ndarray:
        """
        运行仿真并返回预测值

        Parameters
        ----------
        params : np.ndarray, shape (4,)
            参数 [sigma, marangoni, substrate_temp, absorptivity]
        power_points : np.ndarray
            功率点列表 [P1, P2, ...]
        job_id : str | int, optional
            任务 ID，用于归档结果
        on_power_complete : Callable[[int, float, np.ndarray], None], optional
            每个功率点完成后的回调函数
            参数: (power_index, power_value, predictions_so_far)

        Returns
        -------
        predictions : np.ndarray, shape (n_powers, 3)
            预测值 [width, depth, area] 单位: μm, μm, μm²
        """
        params = np.asarray(params).flatten()
        power_points = np.asarray(power_points).flatten()

        sigma = params[0]
        marangoni = params[1]
        substrate_temp = params[2]
        absorptivity = params[3]

        n_powers = len(power_points)
        predictions = np.zeros((n_powers, 3))

        for i, power in enumerate(power_points):
            self.eval_count += 1

            try:
                # 更新参数
                self.case_manager.update_parameters(
                    sigma, marangoni, substrate_temp, absorptivity
                )
                self.case_manager.set_power(power, absorptivity)

                # 运行仿真
                self.case_manager.run_simulation()
                self.case_manager.run_postprocess()

                # 读取结果 (m → μm)
                metrics = self.case_manager.read_metrics()
                predictions[i, 0] = metrics["width_mean_m"] * 1e6
                predictions[i, 1] = metrics["depth_mean_m"] * 1e6
                predictions[i, 2] = metrics["area_mean_m2"] * 1e12

                print(
                    f"  [eval {self.eval_count}] P={power:.0f}W: "
                    f"w={predictions[i, 0]:.2f}μm, d={predictions[i, 1]:.2f}μm"
                )

            except Exception as e:
                print(f"  [eval {self.eval_count}] P={power:.0f}W 仿真失败: {e}")
                predictions[i, :] = np.nan

            finally:
                # 归档结果
                if job_id is not None:
                    # 归档到 runs_root/job_{job_id}/{power}W
                    archive_dir = self.config.runs_root / f"{job_id}" / f"{int(power)}W"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    self.case_manager.archive_latest_time(archive_dir)

                # 调用回调函数（如果提供）
                if on_power_complete is not None:
                    try:
                        on_power_complete(i, power, predictions[:i+1].copy())
                    except Exception as e:
                        print(f"  [警告] 功率点完成回调失败: {e}")

        return predictions

    def run_single(
        self,
        params: np.ndarray,
        power: float,
    ) -> Tuple[float, float, float]:
        """
        运行单个功率点的仿真

        Parameters
        ----------
        params : np.ndarray
            参数 [sigma, marangoni, substrate_temp, absorptivity]
        power : float
            激光功率 (W)

        Returns
        -------
        tuple
            (width, depth, area) 单位: μm, μm, μm²
        """
        result = self.run(params, np.array([power]))
        return tuple(result[0])

    def evaluate_objective(
        self,
        params: np.ndarray,
        exp_data: np.ndarray,
    ) -> float:
        """
        评估目标函数 (SSE)

        Parameters
        ----------
        params : np.ndarray
            参数 [sigma, marangoni, substrate_temp, absorptivity]
        exp_data : np.ndarray, shape (n, 4)
            实验数据 [power, width, depth, area]

        Returns
        -------
        float
            SSE 值
        """
        power_points = exp_data[:, 0]
        observations = exp_data[:, 1:4]

        predictions = self.run(params, power_points)

        # 计算 SSE
        residuals = predictions - observations
        nan_mask = np.isnan(residuals)
        if np.any(nan_mask):
            residuals[nan_mask] = PENALTY_VALUE

        return float(np.sum(residuals**2))

    def compute_residuals_flat(
        self,
        params: np.ndarray,
        exp_data: np.ndarray,
    ) -> np.ndarray:
        """
        计算展平的残差向量（用于 scipy.optimize.least_squares）

        Parameters
        ----------
        params : np.ndarray
            参数
        exp_data : np.ndarray
            实验数据

        Returns
        -------
        np.ndarray
            展平的残差向量
        """
        power_points = exp_data[:, 0]
        observations = exp_data[:, 1:4]

        predictions = self.run(params, power_points)

        residuals = (predictions - observations).flatten()
        nan_mask = np.isnan(residuals)
        if np.any(nan_mask):
            residuals[nan_mask] = PENALTY_VALUE

        return residuals

    def reset_eval_count(self) -> None:
        """重置评估计数器"""
        self.eval_count = 0

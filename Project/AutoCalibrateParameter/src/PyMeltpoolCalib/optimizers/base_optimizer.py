"""
优化器基类

定义优化器统一接口和结果数据结构
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class OptimizationResult:
    """
    优化结果统一数据结构

    Attributes
    ----------
    method : str
        优化方法名称 ("ACBICI", "Bayesian", "Gradient")
    best_params : np.ndarray
        最优参数 [sigma, marangoni, substrate_temp, absorptivity]
    best_cost : float
        最优目标函数值 (SSE)
    n_evaluations : int
        总评估次数
    history : dict
        优化历史记录
    message : str
        状态消息
    extra : dict, optional
        方法特定的额外信息
    posterior_samples : np.ndarray, optional
        MCMC 后验样本（仅 ACBICI）
    posterior_stats : dict, optional
        后验统计量（仅 ACBICI）
    """

    method: str
    best_params: np.ndarray
    best_cost: float
    n_evaluations: int
    history: Dict[str, Any]
    message: str
    extra: Dict[str, Any] = field(default_factory=dict)
    posterior_samples: Optional[np.ndarray] = None
    posterior_stats: Optional[Dict[str, np.ndarray]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为可 JSON 序列化的字典"""
        result = {
            "method": self.method,
            "best_params": self.best_params.tolist(),
            "best_cost": self.best_cost,
            "n_evaluations": self.n_evaluations,
            "message": self.message,
        }

        if self.extra:
            result["extra"] = self.extra

        if self.posterior_stats:
            result["posterior_stats"] = {
                k: v.tolist() for k, v in self.posterior_stats.items()
            }

        return result

    def save(self, filepath: Path) -> None:
        """保存结果到 JSON 文件"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"优化结果已保存至: {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "OptimizationResult":
        """从 JSON 文件加载结果"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        posterior_stats = None
        if "posterior_stats" in data:
            posterior_stats = {
                k: np.array(v) for k, v in data["posterior_stats"].items()
            }

        return cls(
            method=data["method"],
            best_params=np.array(data["best_params"]),
            best_cost=data["best_cost"],
            n_evaluations=data["n_evaluations"],
            history={},  # 历史通常不保存
            message=data["message"],
            extra=data.get("extra", {}),
            posterior_stats=posterior_stats,
        )


class BaseOptimizer(ABC):
    """
    优化器抽象基类

    所有优化器必须实现 optimize() 方法
    """

    def __init__(self, config):
        """
        初始化优化器

        Parameters
        ----------
        config : BaseConfig
            配置对象
        """
        self.config = config
        self.history: Dict[str, List[Any]] = {
            "params": [],
            "costs": [],
            "iterations": [],
        }

    @abstractmethod
    def get_name(self) -> str:
        """
        返回优化器名称

        Returns
        -------
        str
            优化器名称
        """
        pass

    @abstractmethod
    def optimize(self, exp_data: np.ndarray) -> OptimizationResult:
        """
        执行优化

        Parameters
        ----------
        exp_data : np.ndarray, shape (n, 4)
            实验数据 [power, width, depth, area]

        Returns
        -------
        OptimizationResult
            优化结果
        """
        pass

    def save_results(
        self,
        result: OptimizationResult,
        output_dir: Path,
    ) -> None:
        """
        保存优化结果

        Parameters
        ----------
        result : OptimizationResult
            优化结果
        output_dir : Path
            输出目录
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存主结果
        result.save(output_dir / "opt_result.json")

        # 保存历史
        if result.history:
            history_file = output_dir / "history.json"
            serializable_history = {}
            for k, v in result.history.items():
                if isinstance(v, np.ndarray):
                    serializable_history[k] = v.tolist()
                elif isinstance(v, list) and len(v) > 0:
                    if isinstance(v[0], np.ndarray):
                        serializable_history[k] = [x.tolist() for x in v]
                    else:
                        serializable_history[k] = v
                else:
                    serializable_history[k] = v

            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(serializable_history, f, indent=2)

        # 保存后验样本（仅 ACBICI）
        if result.posterior_samples is not None:
            np.save(output_dir / "posterior_samples.npy", result.posterior_samples)

    def _log_iteration(
        self,
        params: np.ndarray,
        cost: float,
        iteration: int,
    ) -> None:
        """记录迭代信息"""
        self.history["params"].append(params.copy())
        self.history["costs"].append(cost)
        self.history["iterations"].append(iteration)

    def _print_progress(
        self,
        iteration: int,
        total: int,
        cost: float,
        best_cost: float,
    ) -> None:
        """打印进度信息"""
        print(
            f"  迭代 {iteration}/{total}: "
            f"当前 SSE = {cost:.4e}, 最优 SSE = {best_cost:.4e}"
        )

"""
ACBICI 优化器

使用 ACBICI 库进行贝叶斯校准（MCMC 后验分布采样）
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np

from .base_optimizer import BaseOptimizer, OptimizationResult

# 动态导入 ACBICI
ACBICI_PATH = Path(__file__).parent.parent.parent / "ACBICI" / "src"
if str(ACBICI_PATH) not in sys.path:
    sys.path.insert(0, str(ACBICI_PATH))

from ACBICI import expensiveCalibrator, HalfCauchy

if TYPE_CHECKING:
    from ..config.acbici_config import ACBICIConfig
    from ..models.meltpool_model import MeltpoolModel


class ACBICIOptimizer(BaseOptimizer):
    """
    ACBICI 贝叶斯校准优化器

    特点：
    - 高斯过程代理模型
    - MCMC 采样获取完整后验分布
    - 适用于计算昂贵的仿真

    Attributes
    ----------
    config : ACBICIConfig
        ACBICI 配置
    model : MeltpoolModel
        熔池仿真模型
    calibrator : expensiveCalibrator
        ACBICI 校准器实例
    """

    def __init__(self, config: "ACBICIConfig", model: "MeltpoolModel"):
        """
        初始化 ACBICI 优化器

        Parameters
        ----------
        config : ACBICIConfig
            ACBICI 配置
        model : MeltpoolModel
            熔池仿真模型（继承 ACBICImodel）
        """
        super().__init__(config)
        self.config = config
        self.model = model
        self.calibrator: Optional[expensiveCalibrator] = None

    def get_name(self) -> str:
        return "ACBICI"

    def optimize(self, exp_data: np.ndarray) -> OptimizationResult:
        """
        执行 ACBICI 校准

        Parameters
        ----------
        exp_data : np.ndarray, shape (n, 4)
            实验数据 [power, width, depth, area]

        Returns
        -------
        OptimizationResult
            包含 MAP 估计和后验分布的结果
        """
        cfg = self.config

        print(f"\n{'='*60}")
        print(f"ACBICI 贝叶斯校准")
        print(f"{'='*60}")
        print(f"核函数: {cfg.kernel}")
        print(f"MCMC: {cfg.nsteps} steps, {cfg.nwalkers} walkers, burn-in {cfg.burn*100}%")
        print(f"误差模型: {cfg.error_type}")
        print()

        # 加载合成数据
        if not cfg.synthetic_data_file.exists():
            raise FileNotFoundError(
                f"合成数据文件不存在: {cfg.synthetic_data_file}\n"
                f"请先运行: python -m PyMeltpoolCalib.scripts.generate_synthetic_data"
            )

        synthetic_data = np.loadtxt(cfg.synthetic_data_file)
        print(f"加载合成数据: {cfg.synthetic_data_file}, 形状: {synthetic_data.shape}")

        # 创建校准器
        self.calibrator = expensiveCalibrator(
            self.model,
            name=cfg.name,
            kernel=cfg.kernel,
        )

        # 设置误差模型
        if cfg.error_type == "known":
            self.calibrator.setExperimentalSTDValue(cfg.exp_std)
            print(f"设置已知实验误差: σ = {cfg.exp_std} μm")
        else:
            self.calibrator.setExperimentalSTDPrior(
                HalfCauchy(mu=0, sigma=cfg.exp_std_prior_sigma)
            )
            print(f"设置未知误差先验: HalfCauchy(σ={cfg.exp_std_prior_sigma})")

        # 存储数据
        self.calibrator.storeExperimentalData(exp_data)
        self.calibrator.storeSyntheticData(synthetic_data)

        # 运行 MCMC
        print("\n开始 MCMC 采样...")
        self.calibrator.calibrate(
            nsteps=cfg.nsteps,
            burn=cfg.burn,
            nwalkers=cfg.nwalkers,
        )

        # 提取结果
        map_params = self._extract_map_estimate()
        posterior_stats = self._get_posterior_stats()
        posterior_samples = self._get_posterior_samples()

        # 计算 MAP 处的目标函数值（近似）
        best_cost = self._estimate_cost_at_map()

        n_evaluations = cfg.nsteps * cfg.nwalkers

        return OptimizationResult(
            method="ACBICI",
            best_params=map_params,
            best_cost=best_cost,
            n_evaluations=n_evaluations,
            history=self.history,
            message=f"MCMC 校准完成，共 {n_evaluations} 次采样",
            posterior_samples=posterior_samples,
            posterior_stats=posterior_stats,
        )

    def _extract_map_estimate(self) -> np.ndarray:
        """提取最大后验概率 (MAP) 估计"""
        burn_samples = int(self.config.burn * self.config.nsteps)
        flatchain = self.calibrator.sampler.get_chain(
            flat=True,
            discard=burn_samples,
        )
        lnprob = self.calibrator.sampler.get_log_prob(
            flat=True,
            discard=burn_samples,
        )

        map_idx = np.argmax(lnprob)
        n_params = self.model.getNParam()
        return flatchain[map_idx, :n_params]

    def _get_posterior_stats(self) -> dict:
        """获取后验统计量"""
        burn_samples = int(self.config.burn * self.config.nsteps)
        flatchain = self.calibrator.sampler.get_chain(
            flat=True,
            discard=burn_samples,
        )
        n_params = self.model.getNParam()
        params_chain = flatchain[:, :n_params]

        return {
            "mean": np.mean(params_chain, axis=0),
            "std": np.std(params_chain, axis=0),
            "median": np.median(params_chain, axis=0),
            "q05": np.percentile(params_chain, 5, axis=0),
            "q95": np.percentile(params_chain, 95, axis=0),
            "q025": np.percentile(params_chain, 2.5, axis=0),
            "q975": np.percentile(params_chain, 97.5, axis=0),
        }

    def _get_posterior_samples(self) -> np.ndarray:
        """获取后验样本"""
        burn_samples = int(self.config.burn * self.config.nsteps)
        flatchain = self.calibrator.sampler.get_chain(
            flat=True,
            discard=burn_samples,
        )
        n_params = self.model.getNParam()
        return flatchain[:, :n_params]

    def _estimate_cost_at_map(self) -> float:
        """估计 MAP 处的目标函数值"""
        # 使用后验对数概率的负值作为代理
        burn_samples = int(self.config.burn * self.config.nsteps)
        lnprob = self.calibrator.sampler.get_log_prob(
            flat=True,
            discard=burn_samples,
        )
        return -float(np.max(lnprob))

    def generate_report(self, output_dir: Path) -> None:
        """
        生成校准报告和可视化

        Parameters
        ----------
        output_dir : Path
            输出目录
        """
        if self.calibrator is None:
            raise RuntimeError("请先运行 optimize() 方法")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 使用 ACBICI 内置报告功能
        print("\n生成报告...")
        self.calibrator.printReport()

        print("\n生成可视化...")
        self.calibrator.plot(trace=True, corner=True, dumpfiles=True)

    def get_calibrator(self) -> Optional[expensiveCalibrator]:
        """获取 ACBICI 校准器实例"""
        return self.calibrator

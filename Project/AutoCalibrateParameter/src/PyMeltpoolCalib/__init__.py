"""
PyMeltpoolCalib - LaserbeamFoam 熔池仿真参数校准库

支持三种优化方法:
- ACBICI: 贝叶斯校准 (MCMC 后验分布)
- Bayesian: 贝叶斯优化 (skopt 点估计)
- Gradient: 梯度优化 (scipy 点估计)
"""

__version__ = "1.0.0"
__author__ = "CGH"

from .config import BaseConfig, ACBICIConfig, BayesConfig, GradientConfig
from .optimizers import BaseOptimizer, OptimizationResult, BayesOptimizer, GradientOptimizer
from .simulation import SimulationRunner
from .models import OpenFOAMCaseManager
from .data import load_experiment_data

try:
    from .optimizers import ACBICIOptimizer
except ImportError:
    ACBICIOptimizer = None

try:
    from .models import MeltpoolModel
except ImportError:
    MeltpoolModel = None

__all__ = [
    # Config
    "BaseConfig",
    "ACBICIConfig",
    "BayesConfig",
    "GradientConfig",
    # Optimizers
    "BaseOptimizer",
    "OptimizationResult",
    "ACBICIOptimizer",
    "BayesOptimizer",
    "GradientOptimizer",
    # Simulation
    "SimulationRunner",
    # Models
    "OpenFOAMCaseManager",
    # Data
    "load_experiment_data",
]

if ACBICIOptimizer is not None:
    __all__.append("ACBICIOptimizer")
if MeltpoolModel is not None:
    __all__.append("MeltpoolModel")

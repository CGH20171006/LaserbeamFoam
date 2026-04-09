"""优化器模块"""

from .base_optimizer import BaseOptimizer, OptimizationResult
from .optimizer_bayes import BayesianOptimizer
from .optimizer_gradient import GradientOptimizer

try:
    from .optimizer_acbici import ACBICIOptimizer
except ModuleNotFoundError as exc:
    if exc.name != "ACBICI":
        raise
    ACBICIOptimizer = None

# 别名
BayesOptimizer = BayesianOptimizer

__all__ = [
    "BaseOptimizer",
    "OptimizationResult",
    "BayesianOptimizer",
    "BayesOptimizer",
    "GradientOptimizer",
]

if ACBICIOptimizer is not None:
    __all__.append("ACBICIOptimizer")

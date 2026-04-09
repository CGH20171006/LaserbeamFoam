"""模型模块"""

from .foam_case_manager import OpenFOAMCaseManager
from .meltpool_params import PARAM_NAMES, PARAM_LABELS, DEFAULT_BOUNDS

try:
    from .meltpool_model import MeltpoolModel
except ModuleNotFoundError as exc:
    if exc.name != "ACBICI":
        raise
    MeltpoolModel = None

__all__ = [
    "OpenFOAMCaseManager",
    "PARAM_NAMES",
    "PARAM_LABELS",
    "DEFAULT_BOUNDS",
]

if MeltpoolModel is not None:
    __all__.append("MeltpoolModel")

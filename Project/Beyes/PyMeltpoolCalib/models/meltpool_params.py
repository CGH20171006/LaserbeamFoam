"""
熔池仿真参数定义

定义参数名称、标签和默认边界
"""

from typing import Dict, List, Tuple

# 参数名称
PARAM_NAMES: List[str] = [
    "sigma",
    "marangoni",
    "substrate_temp",
    "absorptivity",
]

# 参数标签 (用于绘图)
PARAM_LABELS: Dict[str, str] = {
    "sigma": r"$\sigma$ (N/m)",
    "marangoni": r"$\gamma$ (N/m·K)",
    "substrate_temp": r"$T_s$ (K)",
    "absorptivity": r"$\eta$",
}

# LaTeX 标签 (用于 ACBICI)
PARAM_LATEX_LABELS: List[str] = [
    r"$\sigma$",
    r"$\gamma$",
    r"$T_s$",
    r"$\eta$",
]

# 默认参数边界
DEFAULT_BOUNDS: Dict[str, Tuple[float, float]] = {
    "sigma": (1.0, 2.0),
    "marangoni": (-8e-4, -4e-6),
    "substrate_temp": (300.0, 800.0),
    "absorptivity": (0.5, 3.0),
}

# 输出名称
OUTPUT_NAMES: List[str] = ["width", "depth", "area"]

# 输出标签 (用于绘图)
OUTPUT_LABELS: Dict[str, str] = {
    "width": r"Width ($\mu$m)",
    "depth": r"Depth ($\mu$m)",
    "area": r"Area ($\mu$m$^2$)",
}

# 输出单位换算因子 (从 SI 到显示单位)
OUTPUT_SCALE_FACTORS: Dict[str, float] = {
    "width": 1e6,   # m -> μm
    "depth": 1e6,   # m -> μm
    "area": 1e12,   # m² -> μm²
}


def get_param_bounds_list() -> List[Tuple[float, float]]:
    """
    返回参数边界列表（按 PARAM_NAMES 顺序）

    Returns
    -------
    list of tuple
        [(sigma_min, sigma_max), (marangoni_min, marangoni_max), ...]
    """
    return [DEFAULT_BOUNDS[name] for name in PARAM_NAMES]


def param_index(name: str) -> int:
    """
    获取参数索引

    Parameters
    ----------
    name : str
        参数名称

    Returns
    -------
    int
        参数在数组中的索引
    """
    return PARAM_NAMES.index(name)

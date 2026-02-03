"""
目标函数模块

定义残差计算、SSE、RMSE 等目标函数
"""

from typing import Optional, Union

import numpy as np

# 仿真失败时的惩罚值
PENALTY_VALUE = 1e8


def compute_residuals(
    predictions: np.ndarray,
    observations: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    计算残差

    Parameters
    ----------
    predictions : np.ndarray, shape (n, m)
        模型预测值
    observations : np.ndarray, shape (n, m)
        实验观测值
    weights : np.ndarray, optional
        权重矩阵，与 predictions 形状相同

    Returns
    -------
    residuals : np.ndarray
        展平后的加权残差向量
    """
    residuals = predictions - observations

    # 处理 NaN（仿真失败）
    nan_mask = np.isnan(residuals)
    if np.any(nan_mask):
        residuals[nan_mask] = PENALTY_VALUE

    if weights is not None:
        residuals = residuals * weights

    return residuals.flatten()


def compute_sse(
    predictions: np.ndarray,
    observations: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> float:
    """
    计算加权误差平方和 (Sum of Squared Errors)

    Parameters
    ----------
    predictions : np.ndarray
        模型预测值
    observations : np.ndarray
        实验观测值
    weights : np.ndarray, optional
        权重矩阵

    Returns
    -------
    float
        SSE 值
    """
    residuals = compute_residuals(predictions, observations, weights)
    return float(np.sum(residuals**2))


def compute_rmse(
    predictions: np.ndarray,
    observations: np.ndarray,
) -> Union[float, np.ndarray]:
    """
    计算均方根误差 (Root Mean Square Error)

    Parameters
    ----------
    predictions : np.ndarray, shape (n, m)
        模型预测值
    observations : np.ndarray, shape (n, m)
        实验观测值

    Returns
    -------
    float or np.ndarray
        如果输入是 1D，返回标量；否则按列返回 RMSE 数组
    """
    residuals = predictions - observations

    # 处理 NaN
    residuals = np.where(np.isnan(residuals), PENALTY_VALUE, residuals)

    if residuals.ndim == 1:
        return float(np.sqrt(np.mean(residuals**2)))
    else:
        return np.sqrt(np.mean(residuals**2, axis=0))


def compute_mae(
    predictions: np.ndarray,
    observations: np.ndarray,
) -> Union[float, np.ndarray]:
    """
    计算平均绝对误差 (Mean Absolute Error)

    Parameters
    ----------
    predictions : np.ndarray
        模型预测值
    observations : np.ndarray
        实验观测值

    Returns
    -------
    float or np.ndarray
        MAE 值
    """
    residuals = np.abs(predictions - observations)

    # 处理 NaN
    residuals = np.where(np.isnan(residuals), PENALTY_VALUE, residuals)

    if residuals.ndim == 1:
        return float(np.mean(residuals))
    else:
        return np.mean(residuals, axis=0)


def compute_relative_error(
    predictions: np.ndarray,
    observations: np.ndarray,
) -> np.ndarray:
    """
    计算相对误差 (%)

    Parameters
    ----------
    predictions : np.ndarray
        模型预测值
    observations : np.ndarray
        实验观测值

    Returns
    -------
    np.ndarray
        相对误差 (%)
    """
    # 避免除零
    denom = np.abs(observations) + 1e-10
    return 100 * np.abs(predictions - observations) / denom


def normalized_residuals(
    predictions: np.ndarray,
    observations: np.ndarray,
    scales: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    计算归一化残差

    Parameters
    ----------
    predictions : np.ndarray
        模型预测值
    observations : np.ndarray
        实验观测值
    scales : np.ndarray, optional
        各输出的缩放因子，默认使用观测值的标准差

    Returns
    -------
    np.ndarray
        归一化残差
    """
    residuals = predictions - observations

    if scales is None:
        scales = np.std(observations, axis=0)
        scales = np.where(scales < 1e-10, 1.0, scales)

    return residuals / scales

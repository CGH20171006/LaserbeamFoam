#!/usr/bin/env python3
"""
ACBICI 校准结果后处理与可视化工具

功能:
1. 从单个 .out 目录读取 samples.npy，生成参数收敛图
2. 从多个 .out 目录对比多轮迭代结果
3. 生成参数后验分布演化图和不确定性图

用法:
    # 处理单个校准结果
    python postprocess_calibration.py ./calibration.out

    # 对比多轮迭代
    python postprocess_calibration.py ./iter01.out ./iter02.out ./iter03.out

    # 自动发现迭代目录
    python postprocess_calibration.py --auto-discover ./results/

作者: 自动生成
日期: 2025-01-19
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

# 设置字体
plt.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


# ========== 数据加载 ==========

def parse_acbici_log(out_dir: Path) -> Optional[Dict]:
    """解析 acbici.log 文件获取校准配置"""
    log_file = out_dir / "acbici.log"
    if not log_file.exists():
        return None

    content = log_file.read_text()
    info = {}

    # 提取参数名
    param_matches = re.findall(r'\+\s+(\$\\[a-zA-Z_]+\$)', content)
    if param_matches:
        info['param_names'] = param_matches

    # 提取 MCMC 配置
    chain_match = re.search(r'Chain length:\s*(\d+)', content)
    if chain_match:
        info['chain_length'] = int(chain_match.group(1))

    walkers_match = re.search(r'N walkers:\s*(\d+)', content)
    if walkers_match:
        info['n_walkers'] = int(walkers_match.group(1))

    burn_match = re.search(r'Burn in:\s*(\d+)', content)
    if burn_match:
        info['burn_in'] = int(burn_match.group(1))

    return info


def load_samples(out_dir: Path, log_info: Optional[Dict] = None) -> Optional[Tuple[np.ndarray, int, int]]:
    """
    加载 MCMC 采样数据

    Returns
    -------
    flat_samples : np.ndarray, shape (n_samples, n_params)
    n_walkers : int
    n_steps : int
    """
    samples_file = out_dir / "samples.npy"
    if not samples_file.exists():
        print(f"[警告] 未找到采样文件: {samples_file}")
        return None

    samples = np.load(samples_file)
    print(f"加载采样数据: {out_dir.name}, shape={samples.shape}")

    if samples.ndim == 3:
        # 3D: (n_walkers, n_steps, n_params)
        n_walkers, n_steps, n_params = samples.shape
        flat_samples = samples.reshape(-1, n_params)
    else:
        # 2D: (n_samples, n_params) - 已经展平
        n_samples, n_params = samples.shape
        # 从日志推断 walkers 和 steps
        n_walkers = log_info.get('n_walkers', 12) if log_info else 12
        n_steps = n_samples // n_walkers
        flat_samples = samples

    return flat_samples, n_walkers, n_steps


def load_logprob(out_dir: Path) -> Optional[np.ndarray]:
    """加载对数后验概率"""
    logprob_file = out_dir / "logprob.npy"
    if not logprob_file.exists():
        return None
    logprob = np.load(logprob_file)
    if logprob.ndim == 2:
        return logprob.flatten()
    return logprob


def get_param_labels(n_params: int, log_info: Optional[Dict] = None) -> List[str]:
    """获取参数标签"""
    if log_info and 'param_names' in log_info:
        names = log_info['param_names']
        if len(names) >= n_params:
            return names[:n_params]

    # 默认参数名
    default_names = [
        r'$\sigma$',
        r'$\gamma$',
        r'$T_s$ [K]',
        r'$\beta_x$',
        r'$\beta_t$',
        r'$\lambda_x$',
    ]
    return default_names[:n_params]


# ========== 统计计算 ==========

def compute_statistics(flat_samples: np.ndarray, n_walkers: int, n_steps: int,
                       burn_frac: float = 0.2) -> Dict:
    """
    计算后验统计量

    Parameters
    ----------
    flat_samples : shape (n_samples, n_params)
    n_walkers : walker 数量
    n_steps : 步数
    burn_frac : burn-in 比例
    """
    n_samples, n_params = flat_samples.shape
    burn_samples = int(burn_frac * n_samples)

    # 去除 burn-in
    post_burn_samples = flat_samples[burn_samples:]

    return {
        'mean': np.mean(post_burn_samples, axis=0),
        'std': np.std(post_burn_samples, axis=0),
        'median': np.median(post_burn_samples, axis=0),
        'q05': np.percentile(post_burn_samples, 5, axis=0),
        'q95': np.percentile(post_burn_samples, 95, axis=0),
        'n_samples': len(post_burn_samples),
        'burn_samples': burn_samples,
    }


def compute_running_stats(flat_samples: np.ndarray, burn_frac: float = 0.2,
                          n_points: int = 100) -> Dict:
    """
    计算运行统计量（累积均值和标准差）

    Parameters
    ----------
    flat_samples : shape (n_samples, n_params)
    burn_frac : burn-in 比例
    n_points : 输出点数
    """
    n_samples, n_params = flat_samples.shape
    burn_samples = int(burn_frac * n_samples)

    # 选取均匀分布的检查点
    check_points = np.linspace(burn_samples + 10, n_samples - 1, n_points, dtype=int)

    running_means = np.zeros((n_points, n_params))
    running_stds = np.zeros((n_points, n_params))

    for i, idx in enumerate(check_points):
        samples_so_far = flat_samples[burn_samples:idx+1]
        running_means[i] = np.mean(samples_so_far, axis=0)
        running_stds[i] = np.std(samples_so_far, axis=0)

    return {
        'check_points': check_points,
        'running_means': running_means,
        'running_stds': running_stds,
    }


def extract_map_estimate(flat_samples: np.ndarray, logprob: np.ndarray,
                         burn_frac: float = 0.2, n_model_params: int = 3) -> np.ndarray:
    """提取 MAP 估计"""
    n_samples = flat_samples.shape[0]
    burn_samples = int(burn_frac * n_samples)

    post_burn_samples = flat_samples[burn_samples:]
    post_burn_logprob = logprob[burn_samples:] if len(logprob) > burn_samples else logprob

    map_idx = np.argmax(post_burn_logprob)
    return post_burn_samples[map_idx, :n_model_params]


# ========== 残差计算 ==========

def compute_running_logprob(logprob: np.ndarray, n_walkers: int, n_steps: int,
                            burn_frac: float = 0.2, n_points: int = 100) -> Dict:
    """
    计算对数后验概率的运行统计量

    用于展示 MCMC 采样过程中拟合质量的演化
    """
    n_samples = len(logprob)
    burn_samples = int(burn_frac * n_samples)

    # 选取检查点
    check_points = np.linspace(burn_samples + 10, n_samples - 1, n_points, dtype=int)

    running_max = np.zeros(n_points)
    running_mean = np.zeros(n_points)
    running_std = np.zeros(n_points)

    for i, idx in enumerate(check_points):
        lp_so_far = logprob[burn_samples:idx+1]
        running_max[i] = np.max(lp_so_far)
        running_mean[i] = np.mean(lp_so_far)
        running_std[i] = np.std(lp_so_far)

    return {
        'check_points': check_points,
        'running_max': running_max,
        'running_mean': running_mean,
        'running_std': running_std,
    }


def compute_residuals_from_synthetic(flat_samples: np.ndarray, synthetic_data: np.ndarray,
                                     experimental_data: np.ndarray, n_model_params: int = 3,
                                     burn_frac: float = 0.2, n_check: int = 50) -> Dict:
    """
    通过合成数据计算参数采样的预测残差

    对每个检查点的参数估计，找到合成数据中最接近的样本，计算与实验数据的残差
    """
    from scipy.spatial.distance import cdist

    n_samples = flat_samples.shape[0]
    burn_samples = int(burn_frac * n_samples)

    # 检查点
    check_points = np.linspace(burn_samples + 10, n_samples - 1, n_check, dtype=int)

    # 实验数据: [power, width, depth, area] 或 [power, depth, width, area]
    exp_powers = experimental_data[:, 0]
    exp_outputs = experimental_data[:, 1:]  # depth, width, area

    # 合成数据格式: [power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]
    # 或者: [power, sigma, Marangoni, substrate_temp, width, depth, area]
    syn_powers = synthetic_data[:, 0]
    syn_params = synthetic_data[:, 1:1+n_model_params]  # 参数列

    # 确定输出列的位置
    n_cols = synthetic_data.shape[1]
    if n_cols >= 8:  # 包含 absorptivity
        syn_outputs = synthetic_data[:, 5:8]  # width, depth, area
    else:
        syn_outputs = synthetic_data[:, 1+n_model_params:]  # width, depth, area

    # 存储残差
    residuals_mae = np.zeros((n_check, 3))  # MAE for width, depth, area
    residuals_rmse = np.zeros((n_check, 3))

    for i, idx in enumerate(check_points):
        # 到此为止的参数均值
        params_mean = np.mean(flat_samples[burn_samples:idx+1, :n_model_params], axis=0)

        # 对每个实验功率点计算预测
        predictions = np.zeros_like(exp_outputs)

        for j, power in enumerate(exp_powers):
            # 找到相同功率的合成数据
            power_mask = np.isclose(syn_powers, power, rtol=0.05)
            if not np.any(power_mask):
                # 找最接近的功率
                closest_power_idx = np.argmin(np.abs(syn_powers - power))
                power_mask = np.zeros(len(syn_powers), dtype=bool)
                power_mask[closest_power_idx] = True

            # 计算参数距离
            power_syn_params = syn_params[power_mask]
            power_syn_outputs = syn_outputs[power_mask]

            if len(power_syn_params) > 0:
                distances = cdist([params_mean], power_syn_params)[0]
                closest_idx = np.argmin(distances)
                predictions[j] = power_syn_outputs[closest_idx]
            else:
                predictions[j] = np.nan

        # 计算残差 (注意列顺序可能不同)
        # 假设 exp_outputs: [depth, width, area], syn_outputs: [width, depth, area]
        # 需要重新排列
        abs_errors = np.abs(predictions - exp_outputs)
        residuals_mae[i] = np.nanmean(abs_errors, axis=0)
        residuals_rmse[i] = np.sqrt(np.nanmean(abs_errors**2, axis=0))

    return {
        'check_points': check_points,
        'mae': residuals_mae,
        'rmse': residuals_rmse,
        'output_names': ['Width', 'Depth', 'Area'],
    }


# ========== 可视化函数 ==========

def plot_parameter_convergence(flat_samples: np.ndarray, n_walkers: int, n_steps: int,
                               out_dir: Path, param_labels: List[str],
                               burn_frac: float = 0.2, n_model_params: int = 3):
    """
    绘制参数收敛图（运行均值随样本数演化）
    """
    running_stats = compute_running_stats(flat_samples, burn_frac)
    n_params = min(n_model_params, flat_samples.shape[1])

    fig, axes = plt.subplots(n_params, 1, figsize=(12, 3 * n_params))
    if n_params == 1:
        axes = [axes]

    check_points = running_stats['check_points']

    for i, (ax, label) in enumerate(zip(axes, param_labels[:n_params])):
        mean = running_stats['running_means'][:, i]
        std = running_stats['running_stds'][:, i]

        ax.plot(check_points, mean, 'b-', linewidth=2, label='Running Mean')
        ax.fill_between(check_points, mean - std, mean + std, alpha=0.2, color='blue',
                        label='±1 Std')

        # 最终值
        final_mean = mean[-1]
        ax.axhline(final_mean, color='green', linestyle='--', linewidth=1.5,
                   label=f'Final: {final_mean:.4g}')

        ax.set_xlabel('Sample', fontsize=11)
        ax.set_ylabel(label, fontsize=11)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle('Parameter Convergence', fontsize=14, fontweight='bold')
    plt.tight_layout()

    output_path = out_dir / "parameter_convergence.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 参数收敛图已保存: {output_path}")
    plt.close()


def plot_uncertainty_evolution(flat_samples: np.ndarray, out_dir: Path,
                               param_labels: List[str], burn_frac: float = 0.2,
                               n_model_params: int = 3):
    """
    绘制不确定性演化图（后验标准差随样本数下降）
    """
    running_stats = compute_running_stats(flat_samples, burn_frac)
    n_params = min(n_model_params, flat_samples.shape[1])

    fig, ax = plt.subplots(figsize=(10, 6))

    check_points = running_stats['check_points']

    for i, label in enumerate(param_labels[:n_params]):
        # 归一化标准差（相对于最终均值）
        final_mean = running_stats['running_means'][-1, i]
        rel_std = running_stats['running_stds'][:, i] / (np.abs(final_mean) + 1e-10)
        ax.plot(check_points, rel_std, linewidth=2, label=label)

    ax.set_xlabel('Sample', fontsize=12)
    ax.set_ylabel('Relative Standard Deviation', fontsize=12)
    ax.set_title('Uncertainty Evolution', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')

    plt.tight_layout()
    output_path = out_dir / "uncertainty_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 不确定性演化图已保存: {output_path}")
    plt.close()


def plot_chain_traces(flat_samples: np.ndarray, n_walkers: int, n_steps: int,
                      out_dir: Path, param_labels: List[str], burn_frac: float = 0.2,
                      n_model_params: int = 3):
    """
    绘制 MCMC 链轨迹（如果可以重塑为 3D）
    """
    n_samples, n_params = flat_samples.shape
    n_params = min(n_model_params, n_params)

    # 尝试重塑为 (n_walkers, n_steps, n_params)
    try:
        samples_3d = flat_samples.reshape(n_walkers, n_steps, -1)
    except ValueError:
        print("[警告] 无法重塑为 3D 数据，跳过链轨迹图")
        return

    burn_steps = int(burn_frac * n_steps)

    fig, axes = plt.subplots(n_params, 1, figsize=(12, 3 * n_params))
    if n_params == 1:
        axes = [axes]

    steps = np.arange(n_steps)

    for i, (ax, label) in enumerate(zip(axes, param_labels[:n_params])):
        # 画每个 walker 的轨迹
        for w in range(n_walkers):
            ax.plot(steps, samples_3d[w, :, i], alpha=0.4, linewidth=0.5)

        # 画均值
        mean_trace = np.mean(samples_3d[:, :, i], axis=0)
        ax.plot(steps, mean_trace, 'k-', linewidth=1.5, label='Mean')

        # 标记 burn-in
        ax.axvline(burn_steps, color='r', linestyle='--', linewidth=1,
                   label=f'Burn-in ({burn_steps})')
        ax.axvspan(0, burn_steps, alpha=0.1, color='red')

        ax.set_xlabel('Step', fontsize=11)
        ax.set_ylabel(label, fontsize=11)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle('MCMC Chain Traces', fontsize=14, fontweight='bold')
    plt.tight_layout()

    output_path = out_dir / "chain_traces.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 链轨迹图已保存: {output_path}")
    plt.close()


def plot_posterior_distributions(flat_samples: np.ndarray, out_dir: Path,
                                 param_labels: List[str], burn_frac: float = 0.2,
                                 n_model_params: int = 3):
    """绘制后验分布直方图"""
    n_samples, n_params = flat_samples.shape
    burn_samples = int(burn_frac * n_samples)
    post_burn = flat_samples[burn_samples:]

    n_params = min(n_model_params, n_params)

    fig, axes = plt.subplots(1, n_params, figsize=(4 * n_params, 4))
    if n_params == 1:
        axes = [axes]

    for i, (ax, label) in enumerate(zip(axes, param_labels[:n_params])):
        data = post_burn[:, i]
        ax.hist(data, bins=50, density=True, alpha=0.7,
                color='steelblue', edgecolor='black', linewidth=0.5)

        mean_val = np.mean(data)
        median_val = np.median(data)

        ax.axvline(mean_val, color='red', linestyle='-', linewidth=2,
                   label=f'Mean: {mean_val:.4g}')
        ax.axvline(median_val, color='green', linestyle='--', linewidth=2,
                   label=f'Median: {median_val:.4g}')

        ax.set_xlabel(label, fontsize=11)
        ax.set_ylabel('Density', fontsize=11)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle('Posterior Distributions', fontsize=14, fontweight='bold')
    plt.tight_layout()

    output_path = out_dir / "posterior_distributions.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 后验分布图已保存: {output_path}")
    plt.close()


def plot_residual_evolution(flat_samples: np.ndarray, logprob: np.ndarray,
                            n_walkers: int, n_steps: int, out_dir: Path,
                            burn_frac: float = 0.2, synthetic_data: np.ndarray = None,
                            experimental_data: np.ndarray = None, n_model_params: int = 3):
    """
    绘制残差/拟合质量随迭代演化图

    包含两种模式:
    1. 基于 log probability 的拟合质量演化
    2. 如果提供了合成数据和实验数据，计算实际预测残差
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    # ===== 图1: Log Probability 演化 =====
    ax1 = axes[0]
    lp_stats = compute_running_logprob(logprob, n_walkers, n_steps, burn_frac)
    check_points = lp_stats['check_points']

    ax1.plot(check_points, lp_stats['running_max'], 'b-', linewidth=2, label='Max Log Prob')
    ax1.plot(check_points, lp_stats['running_mean'], 'g--', linewidth=1.5, label='Mean Log Prob')
    ax1.fill_between(check_points,
                     lp_stats['running_mean'] - lp_stats['running_std'],
                     lp_stats['running_mean'] + lp_stats['running_std'],
                     alpha=0.2, color='green', label='±1 Std')

    ax1.set_xlabel('Sample', fontsize=11)
    ax1.set_ylabel('Log Posterior Probability', fontsize=11)
    ax1.set_title('Fitting Quality Evolution (Log Probability)', fontsize=12, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ===== 图2: 残差演化 (如果有数据) =====
    ax2 = axes[1]

    if synthetic_data is not None and experimental_data is not None:
        try:
            residuals = compute_residuals_from_synthetic(
                flat_samples, synthetic_data, experimental_data,
                n_model_params, burn_frac, n_check=50
            )

            colors = ['#1f77b4', '#ff7f0e']
            # 只绘制 Width 和 Depth (索引 0 和 1)，跳过 Area (索引 2)
            for i, (name, color) in enumerate(zip(['Width', 'Depth'], colors)):
                ax2.plot(residuals['check_points'], residuals['mae'][:, i],
                         'o-', linewidth=2, markersize=4, color=color, label=f'{name} MAE')

            ax2.set_xlabel('Sample', fontsize=11)
            ax2.set_ylabel('Mean Absolute Error (μm)', fontsize=11)
            ax2.set_title('Prediction Residuals vs Experiments (Width & Depth)', fontsize=12, fontweight='bold')
            ax2.legend(loc='upper right', fontsize=9)
            ax2.grid(True, alpha=0.3)

        except Exception as e:
            print(f"[警告] 计算预测残差失败: {e}")
            # 使用 log prob 的负值作为替代
            ax2.plot(check_points, -lp_stats['running_max'], 'r-', linewidth=2,
                     label='Negative Log Prob (proxy for residual)')
            ax2.set_xlabel('Sample', fontsize=11)
            ax2.set_ylabel('-Log Probability', fontsize=11)
            ax2.set_title('Residual Proxy (Negative Log Probability)', fontsize=12, fontweight='bold')
            ax2.legend(loc='upper right', fontsize=9)
            ax2.grid(True, alpha=0.3)
    else:
        # 没有合成/实验数据，使用 log prob 的负值
        ax2.plot(check_points, -lp_stats['running_max'], 'r-', linewidth=2,
                 label='Best -Log Prob')
        ax2.plot(check_points, -lp_stats['running_mean'], 'm--', linewidth=1.5,
                 label='Mean -Log Prob')

        ax2.set_xlabel('Sample', fontsize=11)
        ax2.set_ylabel('-Log Probability (Residual Proxy)', fontsize=11)
        ax2.set_title('Residual Evolution (via Negative Log Probability)', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right', fontsize=9)
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = out_dir / "residual_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 残差演化图已保存: {output_path}")
    plt.close()


# ========== 多轮迭代对比 ==========

def compare_iterations(out_dirs: List[Path], output_dir: Path,
                       burn_frac: float = 0.2, n_model_params: int = 3):
    """
    对比多轮迭代的参数估计
    """
    iteration_stats = []

    for out_dir in out_dirs:
        log_info = parse_acbici_log(out_dir)
        result = load_samples(out_dir, log_info)
        if result is None:
            continue

        flat_samples, n_walkers, n_steps = result
        stats = compute_statistics(flat_samples, n_walkers, n_steps, burn_frac)

        # 尝试提取 MAP
        logprob = load_logprob(out_dir)
        map_estimate = None
        if logprob is not None:
            try:
                map_estimate = extract_map_estimate(flat_samples, logprob, burn_frac, n_model_params)
            except Exception:
                pass

        iteration_stats.append({
            'name': out_dir.name,
            'mean': stats['mean'][:n_model_params],
            'std': stats['std'][:n_model_params],
            'median': stats['median'][:n_model_params],
            'map': map_estimate,
            'n_samples': stats['n_samples'],
        })

    if len(iteration_stats) < 2:
        print("[警告] 需要至少2个迭代结果才能进行对比")
        return

    n_iters = len(iteration_stats)
    param_labels = get_param_labels(n_model_params)

    # 参数收敛图（多轮对比）
    fig, axes = plt.subplots(n_model_params, 1, figsize=(10, 3 * n_model_params))
    if n_model_params == 1:
        axes = [axes]

    iter_nums = np.arange(1, n_iters + 1)

    for i, (ax, label) in enumerate(zip(axes, param_labels)):
        means = [s['mean'][i] for s in iteration_stats]
        stds = [s['std'][i] for s in iteration_stats]

        ax.errorbar(iter_nums, means, yerr=stds, fmt='o-', capsize=5,
                    linewidth=2, markersize=8, label='Mean ± Std')

        # MAP 估计
        maps = [s['map'][i] if s['map'] is not None else np.nan for s in iteration_stats]
        if not np.all(np.isnan(maps)):
            ax.plot(iter_nums, maps, 's--', markersize=6, alpha=0.7, label='MAP')

        ax.set_xlabel('Iteration', fontsize=11)
        ax.set_ylabel(label, fontsize=11)
        ax.set_xticks(iter_nums)
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle('Parameter Convergence Across Iterations', fontsize=14, fontweight='bold')
    plt.tight_layout()

    output_path = output_dir / "iteration_parameter_convergence.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 迭代参数收敛图已保存: {output_path}")
    plt.close()

    # 不确定性演化图
    fig, ax = plt.subplots(figsize=(10, 6))

    for i, label in enumerate(param_labels):
        stds = [s['std'][i] for s in iteration_stats]
        ax.plot(iter_nums, stds, 'o-', linewidth=2, markersize=8, label=label)

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Posterior Standard Deviation', fontsize=12)
    ax.set_title('Uncertainty Evolution Across Iterations', fontsize=14, fontweight='bold')
    ax.set_xticks(iter_nums)
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "iteration_uncertainty_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 迭代不确定性演化图已保存: {output_path}")
    plt.close()

    # 摘要报告
    report_lines = [
        "=" * 70,
        "多轮迭代校准对比报告",
        "=" * 70,
        "",
    ]

    for j, s in enumerate(iteration_stats):
        report_lines.append(f"迭代 {j+1}: {s['name']}")
        report_lines.append(f"  样本数: {s['n_samples']}")
        for i, label in enumerate(param_labels):
            report_lines.append(f"  {label}: {s['mean'][i]:.6g} ± {s['std'][i]:.6g}")
        report_lines.append("")

    report_text = "\n".join(report_lines)
    report_path = output_dir / "iteration_comparison_report.txt"
    report_path.write_text(report_text)
    print(f"✓ 对比报告已保存: {report_path}")
    print(f"\n{report_text}")


def auto_discover_iterations(base_dir: Path) -> List[Path]:
    """自动发现迭代输出目录"""
    patterns = ["*_iter*.out", "*iter*.out", "iter*.out"]

    out_dirs = []
    for pattern in patterns:
        found = sorted(base_dir.glob(pattern))
        if found:
            out_dirs.extend(found)
            break

    out_dirs = sorted(set(out_dirs))

    if not out_dirs:
        out_dirs = sorted(base_dir.glob("*.out"))

    return out_dirs


# ========== 数据文件加载 ==========

def load_synthetic_data_file(base_dir: Path) -> Optional[np.ndarray]:
    """尝试加载合成数据文件"""
    # 可能的路径
    possible_paths = [
        base_dir / "data" / "synthetic_data.dat",
        base_dir.parent / "data" / "synthetic_data.dat",
        base_dir.parent.parent / "data" / "synthetic_data.dat",
        base_dir / "synthetic.dat",
        base_dir.parent / "synthetic.dat",
    ]

    for path in possible_paths:
        if path.exists():
            try:
                data = np.loadtxt(path)
                print(f"加载合成数据: {path}, shape={data.shape}")
                return data
            except Exception:
                continue

    return None


def load_experimental_data_file(base_dir: Path) -> Optional[np.ndarray]:
    """尝试加载实验数据文件"""
    import pandas as pd

    possible_paths = [
        base_dir / "experimental_data.csv",
        base_dir.parent / "experimental_data.csv",
        base_dir.parent.parent / "experimental_data.csv",
    ]

    for path in possible_paths:
        if path.exists():
            try:
                df = pd.read_csv(path)
                # 期望列: power_W, depth_um, width_um, area_um2
                data = df[["power_W", "depth_um", "width_um", "area_um2"]].values
                print(f"加载实验数据: {path}, shape={data.shape}")
                return data
            except Exception:
                continue

    return None


# ========== 主函数 ==========

def process_single_result(out_dir: Path, burn_frac: float = 0.2, n_model_params: int = 3,
                          synthetic_data_path: Path = None, experimental_data_path: Path = None):
    """处理单个校准结果"""
    print(f"\n{'='*60}")
    print(f"处理校准结果: {out_dir}")
    print(f"{'='*60}")

    log_info = parse_acbici_log(out_dir)
    result = load_samples(out_dir, log_info)
    if result is None:
        print("[错误] 无法加载采样数据")
        return

    flat_samples, n_walkers, n_steps = result
    n_params = flat_samples.shape[1]
    param_labels = get_param_labels(n_params, log_info)

    print(f"\n采样数据: {flat_samples.shape[0]} 样本 × {n_params} 参数")
    print(f"推断: {n_walkers} walkers × {n_steps} steps")
    print(f"参数: {param_labels[:n_model_params]}")

    # 加载 logprob
    logprob = load_logprob(out_dir)

    # 尝试加载合成数据和实验数据（用于残差计算）
    synthetic_data = None
    experimental_data = None

    if synthetic_data_path and synthetic_data_path.exists():
        synthetic_data = np.loadtxt(synthetic_data_path)
        print(f"加载合成数据: {synthetic_data_path}")
    else:
        synthetic_data = load_synthetic_data_file(out_dir)

    if experimental_data_path and experimental_data_path.exists():
        import pandas as pd
        df = pd.read_csv(experimental_data_path)
        experimental_data = df[["power_W", "depth_um", "width_um", "area_um2"]].values
        print(f"加载实验数据: {experimental_data_path}")
    else:
        experimental_data = load_experimental_data_file(out_dir)

    # 生成图表
    print("\n生成可视化图表...")
    plot_parameter_convergence(flat_samples, n_walkers, n_steps, out_dir, param_labels,
                               burn_frac, n_model_params)
    plot_uncertainty_evolution(flat_samples, out_dir, param_labels, burn_frac, n_model_params)
    plot_chain_traces(flat_samples, n_walkers, n_steps, out_dir, param_labels,
                      burn_frac, n_model_params)
    plot_posterior_distributions(flat_samples, out_dir, param_labels, burn_frac, n_model_params)

    # 残差演化图
    if logprob is not None:
        plot_residual_evolution(flat_samples, logprob, n_walkers, n_steps, out_dir,
                                burn_frac, synthetic_data, experimental_data, n_model_params)
    else:
        print("[警告] 未找到 logprob.npy，跳过残差演化图")

    # 打印最终统计量
    stats = compute_statistics(flat_samples, n_walkers, n_steps, burn_frac)
    print(f"\n最终统计量 ({stats['n_samples']} 样本，已去除 {stats['burn_samples']} burn-in):")
    for i, label in enumerate(param_labels[:n_model_params]):
        print(f"  {label}: {stats['mean'][i]:.6g} ± {stats['std'][i]:.6g}")
        print(f"         95% CI: [{stats['q05'][i]:.6g}, {stats['q95'][i]:.6g}]")

    print(f"\n✓ 所有图表已保存至: {out_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="ACBICI 校准结果后处理与可视化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单个校准结果
  python postprocess_calibration.py ./calibration.out

  # 对比多轮迭代
  python postprocess_calibration.py ./iter01.out ./iter02.out ./iter03.out

  # 自动发现迭代目录
  python postprocess_calibration.py --auto-discover ./results/

  # 指定数据文件计算残差
  python postprocess_calibration.py ./calibration.out \\
      --synthetic-data ./data/synthetic_data.dat \\
      --experimental-data ./experimental_data.csv
        """
    )

    parser.add_argument("out_dirs", type=Path, nargs='*',
                        help="一个或多个 .out 输出目录")
    parser.add_argument("--auto-discover", type=Path, default=None,
                        help="自动发现指定目录下的迭代结果")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="输出目录（仅用于多轮对比）")
    parser.add_argument("--burn-frac", type=float, default=0.2,
                        help="Burn-in 比例 (默认: 0.2)")
    parser.add_argument("--n-model-params", type=int, default=3,
                        help="模型参数数量（不含超参数，默认: 3）")
    parser.add_argument("--synthetic-data", type=Path, default=None,
                        help="合成数据文件路径 (用于计算预测残差)")
    parser.add_argument("--experimental-data", type=Path, default=None,
                        help="实验数据 CSV 文件路径 (用于计算预测残差)")

    args = parser.parse_args()

    # 确定要处理的目录
    out_dirs = list(args.out_dirs)

    if args.auto_discover:
        discovered = auto_discover_iterations(args.auto_discover)
        if discovered:
            print(f"自动发现 {len(discovered)} 个输出目录:")
            for d in discovered:
                print(f"  - {d}")
            out_dirs.extend(discovered)
        else:
            print(f"[警告] 未在 {args.auto_discover} 中发现输出目录")

    if not out_dirs:
        parser.print_help()
        return

    # 验证目录
    valid_dirs = [d for d in out_dirs if d.exists() and d.is_dir()]
    if not valid_dirs:
        print("[错误] 没有找到有效的输出目录")
        return

    # 处理
    if len(valid_dirs) == 1:
        process_single_result(valid_dirs[0], args.burn_frac, args.n_model_params,
                              args.synthetic_data, args.experimental_data)
    else:
        for out_dir in valid_dirs:
            process_single_result(out_dir, args.burn_frac, args.n_model_params,
                                  args.synthetic_data, args.experimental_data)

        output_dir = args.output_dir or valid_dirs[0].parent
        print(f"\n{'='*60}")
        print("生成多轮迭代对比图...")
        print(f"{'='*60}")
        compare_iterations(valid_dirs, output_dir, args.burn_frac, args.n_model_params)


if __name__ == "__main__":
    main()

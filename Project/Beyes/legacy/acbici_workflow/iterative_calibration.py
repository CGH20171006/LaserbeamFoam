#!/usr/bin/env python3
"""
ACBICI 迭代贝叶斯校准脚本

实现多轮自适应校准流程:
1. 初始合成数据 → 2. GP+MCMC → 3. 提取最优参数 → 4. 新仿真 → 5. 更新数据集 → 循环

作者: 自动生成
日期: 2025-01-13
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from acbici_model import MeltpoolModel

sys.path.append(str(Path(__file__).parent.parent / "ACBICI" / "src"))
from ACBICI import expensiveCalibrator, HalfCauchy


# ========== 数据管理 ==========

def load_synthetic_data(filepath: Path) -> np.ndarray:
    """加载合成数据"""
    data = np.loadtxt(filepath)
    print(f"加载合成数据: {filepath}, 形状 {data.shape}")
    return data


def append_synthetic_data(filepath: Path, new_data: np.ndarray) -> None:
    """追加新数据到合成数据文件"""
    existing_data = load_synthetic_data(filepath)
    updated_data = np.vstack([existing_data, new_data])

    # 备份原文件
    backup_path = filepath.with_suffix(filepath.suffix + ".backup")
    shutil.copy(filepath, backup_path)

    # 保存更新后的数据
    np.savetxt(filepath, updated_data,
               header="power sigma Marangoni substrate_temp width depth area")
    print(f"✓ 数据已更新: {filepath}, 新形状 {updated_data.shape}")


def prepare_experimental_data(exp_csv: Path) -> np.ndarray:
    """准备实验数据: [功率, 宽度, 深度, 面积]"""
    df = pd.read_csv(exp_csv)
    return df[["power_W", "width_um", "depth_um", "area_um2"]].values


# ========== 后验分析 ==========

def extract_map_estimate(cal: expensiveCalibrator) -> np.ndarray:
    """提取最大后验概率(MAP)估计"""
    # 获取所有参数的 MCMC 链
    flatchain = cal.sampler.get_chain(flat=True, discard=int(cal.burn * cal.nsteps))

    # 计算每个样本的对数后验概率
    lnprob = cal.sampler.get_log_prob(flat=True, discard=int(cal.burn * cal.nsteps))

    # 找到最大后验概率点
    map_idx = np.argmax(lnprob)
    map_params = flatchain[map_idx, :cal.getNParam()]  # 只取参数部分，排除误差参数

    return map_params


def get_posterior_stats(cal: expensiveCalibrator) -> Dict[str, np.ndarray]:
    """获取后验统计量"""
    flatchain = cal.sampler.get_chain(flat=True, discard=int(cal.burn * cal.nsteps))
    params_chain = flatchain[:, :cal.getNParam()]  # 只分析模型参数

    return {
        'mean': np.mean(params_chain, axis=0),
        'std': np.std(params_chain, axis=0),
        'median': np.median(params_chain, axis=0),
        'q05': np.percentile(params_chain, 5, axis=0),
        'q95': np.percentile(params_chain, 95, axis=0),
    }


# ========== 采样策略 ==========

def sample_around_map(
    map_params: np.ndarray,
    posterior_std: np.ndarray,
    n_samples: int,
    param_bounds: List[Tuple[float, float]],
    strategy: str = "hybrid"
) -> np.ndarray:
    """
    在 MAP 估计附近采样新参数点

    Parameters
    ----------
    map_params : 最大后验概率参数
    posterior_std : 后验标准差
    n_samples : 采样数量
    param_bounds : 参数边界 [(min, max), ...]
    strategy : 采样策略
        - "map_only": 仅围绕 MAP 采样
        - "posterior": 从后验协方差采样
        - "hybrid": 混合策略 (推荐)
    """
    n_params = len(map_params)
    samples = np.zeros((n_samples, n_params))

    if strategy == "map_only":
        # 纯高斯采样，标准差缩小为后验标准差的 50%
        for i in range(n_samples):
            samples[i] = np.random.normal(map_params, 0.5 * posterior_std)

    elif strategy == "posterior":
        # 使用后验标准差采样
        for i in range(n_samples):
            samples[i] = np.random.normal(map_params, posterior_std)

    elif strategy == "hybrid":
        # 混合策略: 50% 紧密围绕 MAP, 50% 使用后验标准差
        n_exploit = n_samples // 2
        n_explore = n_samples - n_exploit

        for i in range(n_exploit):
            samples[i] = np.random.normal(map_params, 0.3 * posterior_std)

        for i in range(n_exploit, n_samples):
            samples[i] = np.random.normal(map_params, posterior_std)

    else:
        raise ValueError(f"未知采样策略: {strategy}")

    # 裁剪到参数边界内
    for i in range(n_params):
        samples[:, i] = np.clip(samples[:, i], param_bounds[i][0], param_bounds[i][1])

    return samples


# ========== 收敛判断 ==========

def check_convergence(
    iteration: int,
    current_params: np.ndarray,
    previous_params: np.ndarray,
    posterior_std: np.ndarray,
    max_iterations: int,
    tol_param_change: float = 0.01,
    tol_std: float = 0.05,
) -> Tuple[bool, str]:
    """
    检查收敛性

    Returns
    -------
    converged : bool
    reason : str
    """
    # 检查 1: 达到最大迭代次数
    if iteration >= max_iterations:
        return True, f"达到最大迭代次数 {max_iterations}"

    # 检查 2: 参数相对变化
    if previous_params is not None:
        param_change = np.linalg.norm(current_params - previous_params)
        param_norm = np.linalg.norm(previous_params)
        relative_change = param_change / (param_norm + 1e-10)

        if relative_change < tol_param_change:
            return True, f"参数相对变化 {relative_change:.6f} < {tol_param_change}"

    # 检查 3: 后验标准差
    max_std = np.max(posterior_std)
    if max_std < tol_std:
        return True, f"最大后验标准差 {max_std:.6f} < {tol_std}"

    return False, "未收敛"


# ========== 主校准逻辑 ==========

def run_single_calibration(
    model: MeltpoolModel,
    experiments: np.ndarray,
    synthetic_data: np.ndarray,
    name: str,
    kernel: str,
    nsteps: int,
    burn: float,
    nwalkers: int,
    error_type: str,
    **kwargs
) -> expensiveCalibrator:
    """运行单次校准（复用原逻辑）"""
    print(f"\n{'='*70}\n校准: {name}\n{'='*70}")

    cal = expensiveCalibrator(model, name=name, kernel=kernel)

    if error_type == 'known':
        cal.setExperimentalSTDValue(kwargs['std_value'])
    else:
        cal.setExperimentalSTDPrior(HalfCauchy(mu=0, sigma=kwargs['std_prior_sigma']))

    cal.storeExperimentalData(experiments)
    cal.storeSyntheticData(synthetic_data)

    print("开始 MCMC 采样...")
    cal.calibrate(nsteps=nsteps, burn=burn, nwalkers=nwalkers)

    return cal


def run_new_simulations(
    model: MeltpoolModel,
    new_params: np.ndarray,
    power_points: np.ndarray
) -> np.ndarray:
    """
    使用新参数运行仿真

    Parameters
    ----------
    model : MeltpoolModel
    new_params : shape (n_new_params, 4) [sigma, Marangoni, substrate_temp, absorptivity]
    power_points : shape (n_powers,) 功率点

    Returns
    -------
    new_synthetic_data : shape (n_new_params * n_powers, 8)
        [power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]
    """
    n_new = new_params.shape[0]
    n_powers = len(power_points)
    total_runs = n_new * n_powers

    print(f"\n运行新仿真: {n_new} 个参数点 × {n_powers} 个功率点 = {total_runs} 次仿真")

    results = []

    for i, params in enumerate(new_params):
        print(f"\n参数集 {i+1}/{n_new}: σ={params[0]:.4f}, γ={params[1]:.4e}, T_s={params[2]:.1f}, η={params[3]:.3f}")

        for power in power_points:
            x = np.array([[power]])
            p = params.reshape(1, -1)

            try:
                y = model.symbolicModel(x, p)  # [width, depth, area]
                results.append([power, *params, *y[0]])
                print(f"  ✓ {power:.0f}W: w={y[0,0]:.2f}μm, d={y[0,1]:.2f}μm, a={y[0,2]:.2f}μm²")
            except Exception as e:
                print(f"  ✗ {power:.0f}W 仿真失败: {e}")
                results.append([power, *params, np.nan, np.nan, np.nan])

    return np.array(results)


# ========== 迭代主循环 ==========

def iterative_calibration(
    model: MeltpoolModel,
    experiments: np.ndarray,
    synthetic_data_file: Path,
    max_iterations: int,
    n_new_samples_per_iter: int,
    kernel: str,
    nsteps: int,
    burn: float,
    nwalkers: int,
    error_type: str,
    sampling_strategy: str,
    convergence_params: Dict,
    output_dir: Path,
    **error_kwargs
) -> Dict:
    """
    迭代贝叶斯校准主函数
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "iteration_log.json"

    # 初始化日志
    iteration_log = {
        'config': {
            'max_iterations': max_iterations,
            'n_new_samples_per_iter': n_new_samples_per_iter,
            'kernel': kernel,
            'sampling_strategy': sampling_strategy,
            'convergence_params': convergence_params,
        },
        'iterations': []
    }

    # 获取功率点（从实验数据中提取）
    power_points = np.unique(experiments[:, 0])
    print(f"\n实验功率点: {power_points}")

    # 参数边界（从模型先验中获取）
    # sigma, Marangoni, substrate_temp, absorptivity
    param_bounds = [(1.0, 2.0), (-8e-4, -4e-6), (300.0, 800.0), (0.5, 3.0)]

    previous_map = None

    for iteration in range(1, max_iterations + 1):
        iter_start_time = time.time()
        print(f"\n{'#'*70}")
        print(f"# 迭代 {iteration}/{max_iterations}")
        print(f"{'#'*70}\n")

        # ===== 步骤 1: 加载当前数据 =====
        synthetic_data = load_synthetic_data(synthetic_data_file)

        # ===== 步骤 2: 运行校准 =====
        cal_name = f"{output_dir.name}_iter{iteration:02d}"
        cal = run_single_calibration(
            model, experiments, synthetic_data, cal_name,
            kernel, nsteps, burn, nwalkers, error_type, **error_kwargs
        )

        # ===== 步骤 3: 后验分析 =====
        map_estimate = extract_map_estimate(cal)
        posterior_stats = get_posterior_stats(cal)

        print(f"\n迭代 {iteration} 后验统计:")
        print(f"  MAP 估计: σ={map_estimate[0]:.4f}, γ={map_estimate[1]:.4e}, T_s={map_estimate[2]:.1f}")
        print(f"  后验均值: σ={posterior_stats['mean'][0]:.4f}, γ={posterior_stats['mean'][1]:.4e}, T_s={posterior_stats['mean'][2]:.1f}")
        print(f"  后验标差: σ={posterior_stats['std'][0]:.4f}, γ={posterior_stats['std'][1]:.4e}, T_s={posterior_stats['std'][2]:.1f}")

        # ===== 步骤 3.5: 计算预测误差 (可选) =====
        # 使用 MAP 估计预测实验数据，计算误差
        map_predictions = None
        prediction_errors = None

        try:
            print(f"\n计算 MAP 估计的预测误差...")
            x_exp = experiments[:, 0].reshape(-1, 1)  # 实验功率点
            y_exp = experiments[:, 1:]  # 实验观测值

            # 使用 MAP 参数预测（使用 GP 代理模型，快速）
            map_params_expanded = np.tile(map_estimate, (len(x_exp), 1))

            # 从校准器的 GP 模型预测（如果可用）
            # 注意: ACBICI 的 GP 在内部，这里简化为用合成数据最近邻估计
            from scipy.spatial.distance import cdist

            # 找到合成数据中最接近 MAP 的样本
            # 数据格式: [power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]
            syn_params = synthetic_data[:, 1:5]  # 包含 4 个参数
            syn_x = synthetic_data[:, 0]
            syn_y = synthetic_data[:, 5:8]  # 输出在第 5-7 列

            map_predictions = np.zeros_like(y_exp)
            for i, power in enumerate(x_exp[:, 0]):
                # 找到相同功率点的样本
                power_mask = np.isclose(syn_x, power, rtol=0.01)
                if not np.any(power_mask):
                    continue

                # 计算参数距离
                power_samples = syn_params[power_mask]
                power_outputs = syn_y[power_mask]
                distances = cdist([map_estimate], power_samples)[0]

                # 最近邻预测
                closest_idx = np.argmin(distances)
                map_predictions[i] = power_outputs[closest_idx]

            # 计算误差
            prediction_errors = {
                'absolute': map_predictions - y_exp,
                'relative': 100 * (map_predictions - y_exp) / (y_exp + 1e-10),
                'mae': np.mean(np.abs(map_predictions - y_exp), axis=0).tolist(),
                'rmse': np.sqrt(np.mean((map_predictions - y_exp)**2, axis=0)).tolist(),
            }

            print(f"  MAE: 宽度={prediction_errors['mae'][0]:.2f}μm, "
                  f"深度={prediction_errors['mae'][1]:.2f}μm, "
                  f"面积={prediction_errors['mae'][2]:.2f}μm²")

        except Exception as e:
            print(f"  ⚠ 预测误差计算失败: {e}")

        # ===== 步骤 4: 收敛检查 =====
        converged, reason = check_convergence(
            iteration, map_estimate, previous_map,
            posterior_stats['std'], max_iterations,
            **convergence_params
        )

        # 记录本轮迭代
        iter_log = {
            'iteration': iteration,
            'map_estimate': map_estimate.tolist(),
            'posterior_mean': posterior_stats['mean'].tolist(),
            'posterior_std': posterior_stats['std'].tolist(),
            'converged': converged,
            'convergence_reason': reason,
            'elapsed_time_s': time.time() - iter_start_time,
            'synthetic_data_size': synthetic_data.shape[0],
        }

        # 添加预测误差信息
        if prediction_errors is not None:
            iter_log['map_predictions'] = map_predictions.tolist()
            iter_log['prediction_mae'] = prediction_errors['mae']
            iter_log['prediction_rmse'] = prediction_errors['rmse']

        iteration_log['iterations'].append(iter_log)

        # 保存日志
        with open(log_file, 'w') as f:
            json.dump(iteration_log, f, indent=2)

        print(f"\n收敛检查: {reason}")

        if converged:
            print(f"\n✓ 校准已收敛! 总迭代次数: {iteration}")

            # 生成最终报告
            print("\n生成最终报告...")
            cal.printReport()
            cal.plot(trace=True, corner=True, dumpfiles=True)

            break

        # ===== 步骤 5: 采样新参数点 =====
        print(f"\n生成新采样点 (策略: {sampling_strategy})...")
        new_params = sample_around_map(
            map_estimate, posterior_stats['std'],
            n_new_samples_per_iter, param_bounds, sampling_strategy
        )

        print(f"新参数采样范围:")
        for i, label in enumerate(['sigma', 'Marangoni', 'substrate_temp', 'absorptivity']):
            print(f"  {label}: [{new_params[:, i].min():.4e}, {new_params[:, i].max():.4e}]")

        # ===== 步骤 6: 运行新仿真 =====
        new_synthetic_data = run_new_simulations(model, new_params, power_points)

        # ===== 步骤 7: 更新数据集 =====
        append_synthetic_data(synthetic_data_file, new_synthetic_data)

        previous_map = map_estimate

        print(f"\n迭代 {iteration} 完成，耗时 {time.time() - iter_start_time:.1f} 秒")

    else:
        print(f"\n⚠ 达到最大迭代次数 {max_iterations}，停止迭代")

    # 返回最终结果
    return {
        'final_map': map_estimate,
        'final_posterior_stats': posterior_stats,
        'total_iterations': iteration,
        'log_file': log_file,
    }


# ========== 命令行接口 ==========

def main():
    parser = argparse.ArgumentParser(description="ACBICI 迭代贝叶斯校准")

    # 数据文件
    parser.add_argument("--config", type=Path, default=Path("../config.yaml"))
    parser.add_argument("--experimental-data", type=Path, default=Path("../experimental_data.csv"))
    parser.add_argument("--synthetic-data", type=Path, default=Path("../data/synthetic_data.dat"))

    # 迭代参数
    parser.add_argument("--max-iterations", type=int, default=5,
                       help="最大迭代次数 (默认: 5)")
    parser.add_argument("--n-new-samples", type=int, default=3,
                       help="每轮新采样数量 (默认: 3)")
    parser.add_argument("--sampling-strategy", choices=["map_only", "posterior", "hybrid"],
                       default="hybrid", help="采样策略 (默认: hybrid)")

    # 收敛参数
    parser.add_argument("--tol-param-change", type=float, default=0.01,
                       help="参数相对变化阈值 (默认: 0.01)")
    parser.add_argument("--tol-std", type=float, default=0.05,
                       help="后验标准差阈值 (默认: 0.05)")

    # MCMC 参数
    parser.add_argument("--kernel", choices=["expo", "matern32", "matern52", "ratquad"],
                       default="matern32")
    parser.add_argument("--nsteps", type=int, default=500)
    parser.add_argument("--burn", type=float, default=0.2)
    parser.add_argument("--nwalkers", type=int, default=12)

    # 误差参数
    parser.add_argument("--error-type", choices=["known", "unknown"], default="known")
    parser.add_argument("--exp-std", type=float, default=5.0)
    parser.add_argument("--exp-std-prior-sigma", type=float, default=10.0)

    # 输出
    parser.add_argument("--output-dir", type=Path, default=Path("../iterative_calibration_results"))

    args = parser.parse_args()

    start_time = time.time()

    print(f"\n{'='*70}")
    print("ACBICI 迭代贝叶斯校准")
    print(f"{'='*70}\n")

    # 初始化模型
    model = MeltpoolModel(config_path=args.config)

    # 加载实验数据
    experiments = prepare_experimental_data(args.experimental_data)
    print(f"实验数据: {experiments.shape}")

    # 检查合成数据
    if not args.synthetic_data.exists():
        sys.exit(f"[错误] 合成数据不存在: {args.synthetic_data}\n"
                f"请先运行: python generate_synthetic_data.py --n-samples 20")

    # 误差参数
    error_kwargs = {}
    if args.error_type == 'known':
        error_kwargs['std_value'] = args.exp_std
    else:
        error_kwargs['std_prior_sigma'] = args.exp_std_prior_sigma

    # 收敛参数
    convergence_params = {
        'tol_param_change': args.tol_param_change,
        'tol_std': args.tol_std,
    }

    # 运行迭代校准
    results = iterative_calibration(
        model=model,
        experiments=experiments,
        synthetic_data_file=args.synthetic_data,
        max_iterations=args.max_iterations,
        n_new_samples_per_iter=args.n_new_samples,
        kernel=args.kernel,
        nsteps=args.nsteps,
        burn=args.burn,
        nwalkers=args.nwalkers,
        error_type=args.error_type,
        sampling_strategy=args.sampling_strategy,
        convergence_params=convergence_params,
        output_dir=args.output_dir,
        **error_kwargs
    )

    # 总结
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print("迭代校准完成!")
    print(f"{'='*70}")
    print(f"总耗时: {elapsed/60:.1f} 分钟")
    print(f"总迭代次数: {results['total_iterations']}")
    print(f"最终 MAP 估计: {results['final_map']}")
    print(f"日志文件: {results['log_file']}")
    print(f"结果目录: {args.output_dir}/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
从校准器对象直接提取预测误差演化（快速版本）

不重新运行 OpenFOAM，而是使用每轮训练好的 GP 代理模型进行预测。

用法:
    python plot_prediction_error_from_calibrator.py \
        ../iterative_calibration_results/ \
        ../experimental_data.csv
"""

import argparse
import json
import pickle
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_iteration_log(log_file: Path) -> dict:
    """加载迭代日志"""
    with open(log_file, 'r') as f:
        return json.load(f)


def load_experimental_data(exp_file: Path) -> pd.DataFrame:
    """加载实验数据"""
    return pd.read_csv(exp_file)


def extract_predictions_from_calibrator(result_dir: Path, power_points: np.ndarray) -> np.ndarray:
    """
    从 ACBICI 校准器结果中提取 GP 预测

    Parameters
    ----------
    result_dir : 迭代结果目录 (e.g., *_iter01.out/)
    power_points : 功率点数组

    Returns
    -------
    predictions : shape (n_powers, 3) [width, depth, area]
        使用该轮训练的 GP 模型的预测
    """
    # 尝试加载校准器对象（如果保存了）
    calibrator_pkl = result_dir / "calibrator.pkl"

    if not calibrator_pkl.exists():
        print(f"  ⚠ 未找到校准器对象: {calibrator_pkl}")
        print(f"     ACBICI 默认不保存校准器，需要修改脚本添加保存功能")
        return None

    with open(calibrator_pkl, 'rb') as f:
        calibrator = pickle.load(f)

    # TODO: 从 calibrator 的 GP 模型预测
    # 这需要访问 ACBICI 内部的 GP 模型
    # predictions = calibrator.predict(power_points, map_params)

    return None


def extract_predictions_from_map_estimate(
    result_dir: Path,
    map_params: np.ndarray,
    power_points: np.ndarray,
    synthetic_data: np.ndarray
) -> np.ndarray:
    """
    使用简单插值方法从合成数据估计预测

    当无法访问 GP 模型时的备选方案
    """
    # 从合成数据中提取与 MAP 参数最接近的样本
    # 格式: [power, sigma, Marangoni, substrate_temp, width, depth, area]

    predictions = np.zeros((len(power_points), 3))

    for i, power in enumerate(power_points):
        # 找到相同功率点的所有样本
        power_mask = np.isclose(synthetic_data[:, 0], power, rtol=0.01)
        power_samples = synthetic_data[power_mask]

        if len(power_samples) == 0:
            print(f"  ⚠ 未找到功率 {power}W 的样本")
            predictions[i] = np.nan
            continue

        # 计算参数距离
        param_diff = power_samples[:, 1:4] - map_params
        distances = np.linalg.norm(param_diff, axis=1)

        # 选择最近的样本
        closest_idx = np.argmin(distances)
        predictions[i] = power_samples[closest_idx, 4:7]

    return predictions


def load_synthetic_data_at_iteration(
    iteration: int,
    data_file: Path,
    initial_size: int = 100,
    samples_per_iter: int = 15
) -> np.ndarray:
    """
    加载某次迭代时的合成数据

    注意：这需要迭代过程中保存了每轮的数据快照
    如果没有，则使用最终的合成数据（会导致不准确）
    """
    # 计算该迭代时的数据大小
    # 假设初始 100 样本，每轮增加 15 样本
    expected_size = initial_size + (iteration - 1) * samples_per_iter

    # 加载当前的合成数据文件
    synthetic_data = np.loadtxt(data_file)

    # 如果有备份，可以尝试恢复历史版本
    # 这里简化处理：假设使用当前数据
    print(f"  注意: 使用当前合成数据 (大小 {synthetic_data.shape[0]}) 近似迭代 {iteration} 时的数据")

    return synthetic_data


def compute_errors(predictions: np.ndarray, experimental: np.ndarray) -> np.ndarray:
    """计算绝对误差"""
    return predictions - experimental


def compute_relative_errors(predictions: np.ndarray, experimental: np.ndarray) -> np.ndarray:
    """计算相对误差（百分比）"""
    return 100 * (predictions - experimental) / (experimental + 1e-10)


def plot_error_evolution_simple(
    predictions_dict: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """简化版误差演化图"""
    iterations = sorted(predictions_dict.keys())
    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    output_names = ['Width', 'Depth', 'Area']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    for i, (ax, name) in enumerate(zip(axes, output_names)):
        # 对每个功率点绘制相对误差演化
        for j, power in enumerate(power_points):
            error_series = []
            for iter_num in iterations:
                pred = predictions_dict[iter_num]
                rel_error = 100 * (pred[j, i] - exp_values[j, i]) / exp_values[j, i]
                error_series.append(rel_error)

            ax.plot(iterations, error_series, 'o-', label=f'{power:.0f}W',
                   linewidth=2.5, markersize=9, color=colors[j % len(colors)])

        # 添加零线
        ax.axhline(y=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)

        ax.set_ylabel('Relative Error (%)', fontsize=13)
        ax.set_xlabel('Iteration', fontsize=13)
        ax.set_title(f'{name}: Prediction Error Evolution', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11, framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle=':')

        # 设置 y 轴范围（对称）
        max_err = np.max(np.abs([e for es in [error_series] for e in es]))
        ax.set_ylim(-max_err * 1.2, max_err * 1.2)

    plt.tight_layout()
    output_path = output_dir / "prediction_error_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 误差演化图已保存: {output_path}")
    plt.close()


def plot_mae_evolution(predictions_dict: dict, exp_data: pd.DataFrame, output_dir: Path):
    """绘制平均绝对误差演化"""
    iterations = sorted(predictions_dict.keys())
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    output_names = ['Width', 'Depth', 'Area']
    mae_values = {name: [] for name in output_names}

    for iter_num in iterations:
        pred = predictions_dict[iter_num]
        abs_errors = np.abs(pred - exp_values)

        for i, name in enumerate(output_names):
            mae = np.mean(abs_errors[:, i])
            mae_values[name].append(mae)

    fig, ax = plt.subplots(figsize=(10, 6))

    for name in output_names:
        ax.plot(iterations, mae_values[name], 'o-', label=name,
               linewidth=2.5, markersize=10)

    ax.set_xlabel('Iteration', fontsize=13)
    ax.set_ylabel('Mean Absolute Error (μm or μm²)', fontsize=13)
    ax.set_title('Prediction Accuracy Improvement', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "mae_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ MAE 演化图已保存: {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="从校准器提取预测误差演化")
    parser.add_argument("results_dir", type=Path, help="迭代结果目录")
    parser.add_argument("experimental_data", type=Path, help="实验数据文件")
    parser.add_argument("--synthetic-data", type=Path,
                       default=Path("../data/synthetic_data.dat"),
                       help="合成数据文件")
    parser.add_argument("--output-dir", type=Path, default=None,
                       help="输出目录")

    args = parser.parse_args()

    results_dir = args.results_dir
    if not results_dir.exists():
        print(f"[错误] 结果目录不存在: {results_dir}")
        return

    output_dir = args.output_dir or results_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print("预测误差演化分析（快速版）")
    print(f"{'='*70}\n")

    # 加载迭代日志
    log_file = results_dir / "iteration_log.json"
    if not log_file.exists():
        print(f"[错误] 日志文件不存在: {log_file}")
        return

    log_data = load_iteration_log(log_file)
    exp_data = load_experimental_data(args.experimental_data)
    power_points = exp_data['power_W'].values

    print(f"迭代次数: {len(log_data['iterations'])}")
    print(f"功率点: {power_points}\n")

    # 加载合成数据
    synthetic_data = np.loadtxt(args.synthetic_data)
    print(f"合成数据: {synthetic_data.shape}\n")

    # 提取每轮的预测
    predictions_dict = {}

    print("提取每轮预测...")
    for iter_data in log_data['iterations']:
        iter_num = iter_data['iteration']
        map_params = np.array(iter_data['map_estimate'])

        print(f"迭代 {iter_num}: MAP = {map_params}")

        # 使用最近邻插值从合成数据估计预测
        predictions = extract_predictions_from_map_estimate(
            results_dir, map_params, power_points, synthetic_data
        )

        if predictions is not None and not np.any(np.isnan(predictions)):
            predictions_dict[iter_num] = predictions
            print(f"  ✓ 预测提取成功")
        else:
            print(f"  ✗ 预测提取失败")

    if not predictions_dict:
        print("\n[错误] 没有可用的预测数据")
        return

    print(f"\n生成可视化图表...")
    plot_error_evolution_simple(predictions_dict, exp_data, output_dir)
    plot_mae_evolution(predictions_dict, exp_data, output_dir)

    print(f"\n{'='*70}")
    print("快速分析完成!")
    print(f"{'='*70}")
    print(f"图表已保存至: {output_dir}/")
    print("\n生成的文件:")
    print("  - prediction_error_evolution.png")
    print("  - mae_evolution.png")
    print("\n注意：本工具使用最近邻插值估计预测，精度可能不如真实仿真")


if __name__ == "__main__":
    main()

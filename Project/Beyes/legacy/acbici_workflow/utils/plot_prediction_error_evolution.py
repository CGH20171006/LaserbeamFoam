#!/usr/bin/env python3
"""
预测误差演化可视化工具

对每轮迭代的 MAP 估计，运行正向模型预测，计算与实验数据的误差演化。

用法:
    python plot_prediction_error_evolution.py \
        ../iterative_calibration_results/iteration_log.json \
        ../experimental_data.csv \
        --config ../config.yaml
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 导入模型
sys.path.append(str(Path(__file__).parent.parent))
from acbici_model import MeltpoolModel


def load_iteration_log(log_file: Path) -> dict:
    """加载迭代日志"""
    with open(log_file, 'r') as f:
        return json.load(f)


def load_experimental_data(exp_file: Path) -> pd.DataFrame:
    """加载实验数据"""
    return pd.read_csv(exp_file)


def compute_predictions_for_iteration(
    model: MeltpoolModel,
    map_params: np.ndarray,
    power_points: np.ndarray
) -> np.ndarray:
    """
    使用 MAP 参数运行模型预测

    Parameters
    ----------
    model : MeltpoolModel
    map_params : shape (3,) [sigma, Marangoni, substrate_temp]
    power_points : shape (n_powers,)

    Returns
    -------
    predictions : shape (n_powers, 3) [width, depth, area]
    """
    n_powers = len(power_points)
    predictions = np.zeros((n_powers, 3))

    for i, power in enumerate(power_points):
        x = np.array([[power]])
        p = map_params.reshape(1, -1)

        # 运行模型（这里会实际运行 OpenFOAM）
        # 注意：这会很慢！可以选择使用 GP 代理模型代替
        y = model.symbolicModel(x, p)
        predictions[i] = y[0]

    return predictions


def compute_errors(predictions: np.ndarray, experimental: np.ndarray) -> np.ndarray:
    """
    计算预测误差

    Parameters
    ----------
    predictions : shape (n_powers, 3) [width, depth, area]
    experimental : shape (n_powers, 3) [width, depth, area]

    Returns
    -------
    errors : shape (n_powers, 3)
        绝对误差 (预测值 - 实验值)
    """
    return predictions - experimental


def compute_relative_errors(predictions: np.ndarray, experimental: np.ndarray) -> np.ndarray:
    """计算相对误差（百分比）"""
    return 100 * (predictions - experimental) / (experimental + 1e-10)


def plot_error_evolution(
    log_data: dict,
    exp_data: pd.DataFrame,
    predictions_dict: dict,
    output_dir: Path,
    metric: str = "absolute"
):
    """
    绘制误差演化图

    Parameters
    ----------
    predictions_dict : dict
        {iteration: predictions_array}
    metric : str
        'absolute' or 'relative'
    """
    iterations = sorted(predictions_dict.keys())
    n_iters = len(iterations)

    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    # 计算所有迭代的误差
    errors = {}
    for iter_num in iterations:
        pred = predictions_dict[iter_num]
        if metric == "absolute":
            errors[iter_num] = compute_errors(pred, exp_values)
        else:
            errors[iter_num] = compute_relative_errors(pred, exp_values)

    # 创建图表
    output_names = ['Width', 'Depth', 'Area']
    units = ['μm', 'μm', 'μm²'] if metric == "absolute" else ['%', '%', '%']

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    for i, (ax, name, unit) in enumerate(zip(axes, output_names, units)):
        # 对每个功率点绘制误差演化
        for j, power in enumerate(power_points):
            error_series = [errors[iter_num][j, i] for iter_num in iterations]
            ax.plot(iterations, error_series, 'o-', label=f'{power:.0f}W',
                   linewidth=2, markersize=8)

        # 添加零线
        ax.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)

        ylabel = f'Error ({unit})' if metric == "absolute" else f'Relative Error ({unit})'
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_title(f'{name} Prediction Error Evolution', fontsize=13, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    filename = f"prediction_error_{metric}.png"
    output_path = output_dir / filename
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 误差演化图已保存: {output_path}")
    plt.close()


def plot_error_heatmap(
    predictions_dict: dict,
    exp_data: pd.DataFrame,
    output_dir: Path,
    metric: str = "relative"
):
    """
    绘制误差热力图 (功率点 × 迭代次数)
    """
    iterations = sorted(predictions_dict.keys())
    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    output_names = ['Width', 'Depth', 'Area']

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for i, (ax, name) in enumerate(zip(axes, output_names)):
        # 构建误差矩阵 (功率点 × 迭代次数)
        error_matrix = np.zeros((len(power_points), len(iterations)))

        for j, iter_num in enumerate(iterations):
            pred = predictions_dict[iter_num]
            if metric == "absolute":
                errors = compute_errors(pred, exp_values)
            else:
                errors = compute_relative_errors(pred, exp_values)
            error_matrix[:, j] = errors[:, i]

        # 绘制热力图
        im = ax.imshow(error_matrix, aspect='auto', cmap='RdBu_r',
                      vmin=-np.abs(error_matrix).max(),
                      vmax=np.abs(error_matrix).max())

        ax.set_xticks(range(len(iterations)))
        ax.set_xticklabels(iterations)
        ax.set_yticks(range(len(power_points)))
        ax.set_yticklabels([f'{p:.0f}W' for p in power_points])

        ax.set_xlabel('Iteration', fontsize=11)
        ax.set_ylabel('Power', fontsize=11)
        ax.set_title(f'{name} Error Heatmap', fontsize=12, fontweight='bold')

        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax)
        unit = 'μm' if i < 2 else 'μm²'
        if metric == "relative":
            unit = '%'
        cbar.set_label(f'Error ({unit})', fontsize=10)

        # 在格子中标注数值
        for y in range(len(power_points)):
            for x in range(len(iterations)):
                text = ax.text(x, y, f'{error_matrix[y, x]:.1f}',
                             ha="center", va="center", color="black", fontsize=8)

    plt.tight_layout()
    filename = f"prediction_error_heatmap_{metric}.png"
    output_path = output_dir / filename
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 误差热力图已保存: {output_path}")
    plt.close()


def plot_rmse_evolution(
    predictions_dict: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """绘制 RMSE 演化（单个指标汇总所有功率点）"""
    iterations = sorted(predictions_dict.keys())
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    output_names = ['Width', 'Depth', 'Area']
    rmse_values = {name: [] for name in output_names}

    for iter_num in iterations:
        pred = predictions_dict[iter_num]
        errors = pred - exp_values

        for i, name in enumerate(output_names):
            rmse = np.sqrt(np.mean(errors[:, i]**2))
            rmse_values[name].append(rmse)

    # 绘制
    fig, ax = plt.subplots(figsize=(10, 6))

    for name in output_names:
        ax.plot(iterations, rmse_values[name], 'o-', label=name,
               linewidth=2.5, markersize=10)

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('RMSE (μm or μm²)', fontsize=12)
    ax.set_title('Root Mean Square Error Evolution', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "rmse_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ RMSE 演化图已保存: {output_path}")
    plt.close()


def generate_error_summary_table(
    predictions_dict: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """生成误差汇总表格"""
    iterations = sorted(predictions_dict.keys())
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    lines = [
        "=" * 80,
        "预测误差汇总表",
        "=" * 80,
        ""
    ]

    for iter_num in iterations:
        pred = predictions_dict[iter_num]
        abs_errors = pred - exp_values
        rel_errors = 100 * abs_errors / (exp_values + 1e-10)

        lines.append(f"迭代 {iter_num}:")
        lines.append("-" * 80)
        lines.append(f"{'输出':<15} {'MAE (μm/μm²)':<20} {'RMSE (μm/μm²)':<20} {'MAPE (%)':<15}")
        lines.append("-" * 80)

        for i, name in enumerate(['Width', 'Depth', 'Area']):
            mae = np.mean(np.abs(abs_errors[:, i]))
            rmse = np.sqrt(np.mean(abs_errors[:, i]**2))
            mape = np.mean(np.abs(rel_errors[:, i]))
            lines.append(f"{name:<15} {mae:<20.2f} {rmse:<20.2f} {mape:<15.2f}")

        lines.append("")

    lines.append("=" * 80)

    report_text = "\n".join(lines)
    report_path = output_dir / "prediction_error_summary.txt"
    report_path.write_text(report_text)
    print(f"✓ 误差汇总表已保存: {report_path}")

    # 同时打印到终端
    print(f"\n{report_text}")


def main():
    parser = argparse.ArgumentParser(description="可视化预测误差演化")
    parser.add_argument("log_file", type=Path, help="迭代日志文件")
    parser.add_argument("experimental_data", type=Path, help="实验数据文件")
    parser.add_argument("--config", type=Path, default=Path("../config.yaml"),
                       help="OpenFOAM 配置文件")
    parser.add_argument("--output-dir", type=Path, default=None,
                       help="输出目录（默认：日志文件所在目录）")
    parser.add_argument("--use-gp", action="store_true",
                       help="使用 GP 代理模型而非真实仿真（快速但需要训练好的 GP）")
    parser.add_argument("--skip-simulation", action="store_true",
                       help="跳过仿真，仅使用已有的预测数据（如果有）")

    args = parser.parse_args()

    if not args.log_file.exists():
        print(f"[错误] 日志文件不存在: {args.log_file}")
        return

    if not args.experimental_data.exists():
        print(f"[错误] 实验数据文件不存在: {args.experimental_data}")
        return

    output_dir = args.output_dir or args.log_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print("预测误差演化分析")
    print(f"{'='*70}\n")

    # 加载数据
    print("加载数据...")
    log_data = load_iteration_log(args.log_file)
    exp_data = load_experimental_data(args.experimental_data)
    power_points = exp_data['power_W'].values

    print(f"迭代次数: {len(log_data['iterations'])}")
    print(f"功率点: {power_points}")
    print(f"实验数据点数: {len(exp_data)}\n")

    # 初始化模型
    if not args.skip_simulation:
        print("初始化模型...")
        model = MeltpoolModel(config_path=args.config)
        print(f"模型已加载: {args.config}\n")

    # 计算每轮的预测
    predictions_dict = {}

    if args.skip_simulation:
        print("⚠ 跳过仿真模式：需要提供预先计算好的预测数据")
        print("  此功能暂未实现，请移除 --skip-simulation 参数\n")
        return

    print("计算每轮迭代的预测...")
    print("注意：这将为每轮 MAP 估计运行 OpenFOAM 仿真，可能需要较长时间\n")

    for i, iter_data in enumerate(log_data['iterations']):
        iter_num = iter_data['iteration']
        map_params = np.array(iter_data['map_estimate'])

        print(f"迭代 {iter_num}: MAP = {map_params}")

        if args.use_gp:
            print("  ⚠ GP 代理模型预测功能待实现")
            # TODO: 使用已训练的 GP 模型快速预测
            continue
        else:
            print(f"  运行 OpenFOAM 仿真 ({len(power_points)} 个功率点)...")
            predictions = compute_predictions_for_iteration(model, map_params, power_points)
            predictions_dict[iter_num] = predictions
            print(f"  ✓ 预测完成")

    if not predictions_dict:
        print("\n[错误] 没有可用的预测数据")
        return

    print(f"\n生成可视化图表...")

    # 生成各种图表
    plot_error_evolution(log_data, exp_data, predictions_dict, output_dir, metric="absolute")
    plot_error_evolution(log_data, exp_data, predictions_dict, output_dir, metric="relative")
    plot_error_heatmap(predictions_dict, exp_data, output_dir, metric="relative")
    plot_rmse_evolution(predictions_dict, exp_data, output_dir)
    generate_error_summary_table(predictions_dict, exp_data, output_dir)

    print(f"\n{'='*70}")
    print("误差分析完成!")
    print(f"{'='*70}")
    print(f"所有图表已保存至: {output_dir}/")
    print("\n生成的文件:")
    print("  - prediction_error_absolute.png   (绝对误差演化)")
    print("  - prediction_error_relative.png   (相对误差演化)")
    print("  - prediction_error_heatmap_relative.png (误差热力图)")
    print("  - rmse_evolution.png              (RMSE 演化)")
    print("  - prediction_error_summary.txt    (误差汇总表)")


if __name__ == "__main__":
    main()

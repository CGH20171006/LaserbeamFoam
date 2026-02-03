#!/usr/bin/env python3
"""
从迭代日志直接绘制预测误差演化

使用每轮保存的 MAP 预测和误差信息，无需重新计算。

用法:
    python plot_prediction_error_from_log.py \
        ../iterative_calibration_results/iteration_log.json \
        ../experimental_data.csv
"""

import argparse
import json
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


def check_prediction_data_available(log_data: dict) -> bool:
    """检查日志中是否包含预测数据"""
    if not log_data['iterations']:
        return False

    first_iter = log_data['iterations'][0]
    return 'map_predictions' in first_iter and 'prediction_mae' in first_iter


def plot_error_evolution_by_power(
    log_data: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """
    绘制每个功率点的误差演化

    3 个子图 (宽度/深度/面积)，每个子图包含所有功率点的曲线
    """
    iterations_data = log_data['iterations']
    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    iterations = [d['iteration'] for d in iterations_data]
    output_names = ['Width', 'Depth', 'Area']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

    fig, axes = plt.subplots(3, 1, figsize=(12, 11))

    for i, (ax, name) in enumerate(zip(axes, output_names)):
        # 对每个功率点绘制误差演化
        for j, power in enumerate(power_points):
            relative_errors = []

            for iter_data in iterations_data:
                pred = np.array(iter_data['map_predictions'])
                rel_error = 100 * (pred[j, i] - exp_values[j, i]) / exp_values[j, i]
                relative_errors.append(rel_error)

            ax.plot(iterations, relative_errors, 'o-',
                   label=f'{power:.0f}W',
                   linewidth=2.5, markersize=9,
                   color=colors[j % len(colors)])

        # 零线
        ax.axhline(y=0, color='k', linestyle='--', linewidth=1.5, alpha=0.7)

        ax.set_ylabel('Relative Error (%)', fontsize=13)
        ax.set_xlabel('Iteration', fontsize=13)
        ax.set_title(f'{name}: Prediction Error vs Iteration',
                    fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11, framealpha=0.9, ncol=2)
        ax.grid(True, alpha=0.3, linestyle=':')

    plt.tight_layout()
    output_path = output_dir / "prediction_error_by_power.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 预测误差演化图已保存: {output_path}")
    plt.close()


def plot_mae_rmse_evolution(log_data: dict, output_dir: Path):
    """绘制 MAE 和 RMSE 演化"""
    iterations_data = log_data['iterations']

    iterations = [d['iteration'] for d in iterations_data]
    mae_width = [d['prediction_mae'][0] for d in iterations_data]
    mae_depth = [d['prediction_mae'][1] for d in iterations_data]
    mae_area = [d['prediction_mae'][2] for d in iterations_data]

    rmse_width = [d['prediction_rmse'][0] for d in iterations_data]
    rmse_depth = [d['prediction_rmse'][1] for d in iterations_data]
    rmse_area = [d['prediction_rmse'][2] for d in iterations_data]

    # MAE 图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(iterations, mae_width, 'o-', label='Width', linewidth=2.5, markersize=10)
    ax1.plot(iterations, mae_depth, 's-', label='Depth', linewidth=2.5, markersize=10)
    ax1.plot(iterations, mae_area, '^-', label='Area', linewidth=2.5, markersize=10)

    ax1.set_xlabel('Iteration', fontsize=13)
    ax1.set_ylabel('Mean Absolute Error (μm or μm²)', fontsize=13)
    ax1.set_title('MAE Evolution', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # RMSE 图
    ax2.plot(iterations, rmse_width, 'o-', label='Width', linewidth=2.5, markersize=10)
    ax2.plot(iterations, rmse_depth, 's-', label='Depth', linewidth=2.5, markersize=10)
    ax2.plot(iterations, rmse_area, '^-', label='Area', linewidth=2.5, markersize=10)

    ax2.set_xlabel('Iteration', fontsize=13)
    ax2.set_ylabel('Root Mean Square Error (μm or μm²)', fontsize=13)
    ax2.set_title('RMSE Evolution', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "mae_rmse_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ MAE/RMSE 演化图已保存: {output_path}")
    plt.close()


def plot_error_heatmap_combined(
    log_data: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """绘制组合热力图：功率点 × 迭代次数"""
    iterations_data = log_data['iterations']
    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    iterations = [d['iteration'] for d in iterations_data]
    output_names = ['Width (μm)', 'Depth (μm)', 'Area (μm²)']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    for i, (ax, name) in enumerate(zip(axes, output_names)):
        # 构建误差矩阵
        error_matrix = np.zeros((len(power_points), len(iterations)))

        for j, iter_data in enumerate(iterations_data):
            pred = np.array(iter_data['map_predictions'])
            rel_errors = 100 * (pred[:, i] - exp_values[:, i]) / exp_values[:, i]
            error_matrix[:, j] = rel_errors

        # 绘制热力图
        vmax = np.abs(error_matrix).max()
        im = ax.imshow(error_matrix, aspect='auto', cmap='RdBu_r',
                      vmin=-vmax, vmax=vmax, interpolation='nearest')

        ax.set_xticks(range(len(iterations)))
        ax.set_xticklabels(iterations)
        ax.set_yticks(range(len(power_points)))
        ax.set_yticklabels([f'{p:.0f}' for p in power_points])

        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Power (W)', fontsize=12)
        ax.set_title(f'{name} - Relative Error (%)', fontsize=13, fontweight='bold')

        # 颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Error (%)', fontsize=11)

        # 标注数值
        for y in range(len(power_points)):
            for x in range(len(iterations)):
                color = 'white' if abs(error_matrix[y, x]) > vmax * 0.5 else 'black'
                ax.text(x, y, f'{error_matrix[y, x]:.1f}',
                       ha="center", va="center", color=color, fontsize=9, fontweight='bold')

    plt.tight_layout()
    output_path = output_dir / "prediction_error_heatmap.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 预测误差热力图已保存: {output_path}")
    plt.close()


def generate_error_comparison_table(
    log_data: dict,
    exp_data: pd.DataFrame,
    output_dir: Path
):
    """生成详细的误差对比表"""
    iterations_data = log_data['iterations']
    power_points = exp_data['power_W'].values
    exp_values = exp_data[['width_um', 'depth_um', 'area_um2']].values

    lines = [
        "=" * 100,
        "预测误差详细对比表",
        "=" * 100,
        ""
    ]

    for iter_data in iterations_data:
        iter_num = iter_data['iteration']
        pred = np.array(iter_data['map_predictions'])

        lines.append(f"\n{'='*100}")
        lines.append(f"迭代 {iter_num}")
        lines.append(f"{'='*100}\n")

        # 宽度
        lines.append("宽度 (μm):")
        lines.append(f"{'功率(W)':<10} {'实验值':<12} {'预测值':<12} {'绝对误差':<12} {'相对误差(%)':<15}")
        lines.append("-" * 100)
        for i, power in enumerate(power_points):
            exp_val = exp_values[i, 0]
            pred_val = pred[i, 0]
            abs_err = pred_val - exp_val
            rel_err = 100 * abs_err / exp_val
            lines.append(f"{power:<10.0f} {exp_val:<12.2f} {pred_val:<12.2f} {abs_err:<12.2f} {rel_err:<15.2f}")

        lines.append("")

        # 深度
        lines.append("深度 (μm):")
        lines.append(f"{'功率(W)':<10} {'实验值':<12} {'预测值':<12} {'绝对误差':<12} {'相对误差(%)':<15}")
        lines.append("-" * 100)
        for i, power in enumerate(power_points):
            exp_val = exp_values[i, 1]
            pred_val = pred[i, 1]
            abs_err = pred_val - exp_val
            rel_err = 100 * abs_err / exp_val
            lines.append(f"{power:<10.0f} {exp_val:<12.2f} {pred_val:<12.2f} {abs_err:<12.2f} {rel_err:<15.2f}")

        lines.append("")

        # 面积
        lines.append("面积 (μm²):")
        lines.append(f"{'功率(W)':<10} {'实验值':<12} {'预测值':<12} {'绝对误差':<12} {'相对误差(%)':<15}")
        lines.append("-" * 100)
        for i, power in enumerate(power_points):
            exp_val = exp_values[i, 2]
            pred_val = pred[i, 2]
            abs_err = pred_val - exp_val
            rel_err = 100 * abs_err / exp_val
            lines.append(f"{power:<10.0f} {exp_val:<12.2f} {pred_val:<12.2f} {abs_err:<12.2f} {rel_err:<15.2f}")

        lines.append(f"\n汇总统计:")
        lines.append(f"  MAE:  宽度={iter_data['prediction_mae'][0]:.2f}μm, "
                    f"深度={iter_data['prediction_mae'][1]:.2f}μm, "
                    f"面积={iter_data['prediction_mae'][2]:.2f}μm²")
        lines.append(f"  RMSE: 宽度={iter_data['prediction_rmse'][0]:.2f}μm, "
                    f"深度={iter_data['prediction_rmse'][1]:.2f}μm, "
                    f"面积={iter_data['prediction_rmse'][2]:.2f}μm²")

    lines.append(f"\n{'='*100}\n")

    report_text = "\n".join(lines)
    report_path = output_dir / "prediction_error_detailed.txt"
    report_path.write_text(report_text)
    print(f"✓ 详细误差对比表已保存: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="从迭代日志绘制预测误差演化（无需重新仿真）"
    )
    parser.add_argument("log_file", type=Path, help="迭代日志文件")
    parser.add_argument("experimental_data", type=Path, help="实验数据文件")
    parser.add_argument("--output-dir", type=Path, default=None,
                       help="输出目录（默认：日志文件所在目录）")

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
    print("预测误差演化可视化（从日志文件）")
    print(f"{'='*70}\n")

    # 加载数据
    print("加载数据...")
    log_data = load_iteration_log(args.log_file)
    exp_data = load_experimental_data(args.experimental_data)

    print(f"迭代次数: {len(log_data['iterations'])}")
    print(f"实验数据点数: {len(exp_data)}\n")

    # 检查是否包含预测数据
    if not check_prediction_data_available(log_data):
        print("[错误] 日志文件中未找到预测数据")
        print("请确保使用包含预测功能的 iterative_calibration.py 运行")
        return

    print("✓ 日志包含预测数据\n")

    # 生成可视化
    print("生成可视化图表...")
    plot_error_evolution_by_power(log_data, exp_data, output_dir)
    plot_mae_rmse_evolution(log_data, output_dir)
    plot_error_heatmap_combined(log_data, exp_data, output_dir)
    generate_error_comparison_table(log_data, exp_data, output_dir)

    print(f"\n{'='*70}")
    print("可视化完成!")
    print(f"{'='*70}")
    print(f"所有图表已保存至: {output_dir}/\n")
    print("生成的文件:")
    print("  - prediction_error_by_power.png    (每个功率点的误差演化)")
    print("  - mae_rmse_evolution.png           (MAE/RMSE 演化)")
    print("  - prediction_error_heatmap.png     (误差热力图)")
    print("  - prediction_error_detailed.txt    (详细对比表)")


if __name__ == "__main__":
    main()

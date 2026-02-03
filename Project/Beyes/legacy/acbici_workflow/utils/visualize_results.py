#!/usr/bin/env python3
"""
ACBICI结果可视化脚本

读取ACBICI校准结果并生成可视化图表：Corner图、Trace图、统计报告
用法:
    python visualize_results.py meltpool_calibration_known_error.out
    python visualize_results.py --all  # 可视化所有.out目录
"""

import argparse
import sys
from pathlib import Path

import corner
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_samples(result_dir: Path):
    """加载MCMC样本"""
    samples_file = result_dir / "samples.npy"
    if not samples_file.exists():
        raise FileNotFoundError(f"未找到样本文件: {samples_file}")
    samples = np.load(samples_file)
    print(f"加载样本: {samples.shape}")
    return samples


def extract_param_names(log_file: Path):
    """从log文件中提取参数名称"""
    param_names, in_param, in_hyperparam = [], False, False

    with open(log_file, 'r') as f:
        for line in f:
            if "Parameters to calibrate and prior distribution:" in line:
                in_param, in_hyperparam = True, False
            elif "Hyperparameters to calibrate and prior distribution:" in line:
                in_param, in_hyperparam = False, True
            elif "Known std of experimental error:" in line or "Process report:" in line:
                break
            elif (in_param or in_hyperparam) and line.strip().startswith("+"):
                param_names.append(line.split("+")[1].strip())

    return param_names


def plot_corner(samples, param_names, output_file):
    """绘制corner图"""
    print("\n生成corner图...")
    fig = corner.corner(samples, labels=param_names, quantiles=[0.16, 0.5, 0.84],
                       show_titles=True, title_kwargs={"fontsize": 12},
                       label_kwargs={"fontsize": 14})
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  保存至: {output_file}")
    plt.close()


def plot_trace(samples, param_names, output_file):
    """绘制trace图"""
    print("\n生成trace图...")
    n_params = samples.shape[1]
    n_cols = min(3, n_params)
    n_rows = (n_params + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 3*n_rows))
    axes = axes.reshape(1, -1) if n_rows == 1 else axes

    for i in range(n_params):
        ax = axes[i // n_cols, i % n_cols]
        ax.plot(samples[:, i], alpha=0.7, linewidth=0.5)
        ax.set_ylabel(param_names[i], fontsize=12)
        ax.set_xlabel('Iteration', fontsize=10)
        ax.grid(alpha=0.3)

    # 隐藏多余的子图
    for i in range(n_params, n_rows * n_cols):
        axes[i // n_cols, i % n_cols].axis('off')

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  保存至: {output_file}")
    plt.close()


def compute_statistics(samples, param_names):
    """计算统计量"""
    stats = []
    for i, name in enumerate(param_names):
        col = samples[:, i]
        mean, median, std = np.mean(col), np.median(col), np.std(col)
        q025, q975 = np.percentile(col, [2.5, 97.5])

        # 近似MAP（使用直方图的峰值）
        hist, bins = np.histogram(col, bins=50)
        max_bin = np.argmax(hist)
        map_approx = (bins[max_bin] + bins[max_bin+1]) / 2

        stats.append({
            'parameter': name, 'mean': mean, 'median': median,
            'std': std, 'MAP': map_approx, 'CI_2.5%': q025, 'CI_97.5%': q975
        })

    return pd.DataFrame(stats)


def save_statistics(stats_df, output_file):
    """保存统计报告"""
    print("\n生成统计报告...")

    with open(output_file, 'w') as f:
        f.write(f"{'='*80}\nACBICI 贝叶斯校准结果统计报告\n{'='*80}\n\n总样本数: {len(stats_df)}\n\n")
        f.write(f"{'-'*80}\n{'参数':<15} {'均值':<12} {'中位数':<12} {'MAP':<12} {'标准差':<12} {'95% CI':<20}\n{'-'*80}\n")

        for _, row in stats_df.iterrows():
            ci_str = f"[{row['CI_2.5%']:.3e}, {row['CI_97.5%']:.3e}]"
            f.write(f"{row['parameter']:<15} {row['mean']:<12.3e} {row['median']:<12.3e} "
                   f"{row['MAP']:<12.3e} {row['std']:<12.3e} {ci_str:<20}\n")

        f.write(f"{'-'*80}\n")

    # 同时保存CSV格式
    csv_file = output_file.with_suffix('.csv')
    stats_df.to_csv(csv_file, index=False)

    print(f"  文本报告: {output_file}")
    print(f"  CSV报告: {csv_file}")


def visualize_result_dir(result_dir: Path):
    """可视化单个结果目录"""
    print(f"\n{'='*80}\n处理结果目录: {result_dir.name}\n{'='*80}")

    # 加载数据
    samples = load_samples(result_dir)

    # 提取参数名称
    log_file = result_dir / "acbici.log"
    param_names = (extract_param_names(log_file) if log_file.exists()
                  else [f"param_{i}" for i in range(samples.shape[1])])
    if not log_file.exists():
        print("警告: 未找到acbici.log，使用默认参数名")
    else:
        print(f"参数名称: {param_names}")

    # 生成图表和统计
    plot_corner(samples, param_names, result_dir / "corner_plot.png")
    plot_trace(samples, param_names, result_dir / "trace_plot.png")
    stats_df = compute_statistics(samples, param_names)
    save_statistics(stats_df, result_dir / "statistics.txt")

    print(f"\n{'='*80}\n可视化完成!\n{'='*80}\n\n生成的文件:")
    print(f"  📊 corner_plot.png\n  📈 trace_plot.png\n  📄 statistics.txt\n  📄 statistics.csv\n")

    # 打印统计摘要
    print("参数后验估计:")
    print(stats_df[['parameter', 'mean', 'std', 'CI_2.5%', 'CI_97.5%']].to_string(index=False))
    print()


def main():
    parser = argparse.ArgumentParser(description="ACBICI结果可视化")
    parser.add_argument('result_dir', nargs='?', type=Path, help='结果目录路径（.out目录）')
    parser.add_argument('--all', action='store_true', help='可视化当前目录下所有.out结果')
    args = parser.parse_args()

    if args.all:
        result_dirs = list(Path.cwd().glob("*.out"))
        if not result_dirs:
            sys.exit("未找到任何.out结果目录")

        print(f"找到 {len(result_dirs)} 个结果目录")
        for result_dir in result_dirs:
            try:
                visualize_result_dir(result_dir)
            except Exception as e:
                print(f"错误: 处理 {result_dir} 时失败: {e}")

    elif args.result_dir:
        if not args.result_dir.exists():
            sys.exit(f"错误: 目录不存在: {args.result_dir}")
        visualize_result_dir(args.result_dir)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

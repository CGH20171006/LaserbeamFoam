#!/usr/bin/env python3
"""
简化版ACBICI结果可视化

不依赖ACBICI和corner包，仅使用numpy和matplotlib生成基本图表
用法: python plot_results_simple.py meltpool_calibration_known_error.out
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def extract_param_names(log_file: Path):
    """从acbici.log中提取参数名称"""
    if not log_file.exists():
        return []

    param_names, in_section = [], False
    with open(log_file, 'r') as f:
        for line in f:
            if "Parameters to calibrate" in line or "Hyperparameters to calibrate" in line:
                in_section = True
            elif "Known std" in line or "Process report" in line:
                break
            elif in_section and line.strip().startswith("+"):
                param_names.append(line.split("+")[1].strip())
    return param_names


def plot_trace(samples, param_names, output_file):
    """生成trace图"""
    n_params = samples.shape[1]
    fig, axes = plt.subplots(n_params, 1, figsize=(12, 2.5*n_params))
    axes = [axes] if n_params == 1 else axes

    for i, ax in enumerate(axes):
        ax.plot(samples[:, i], alpha=0.6, color='#FF6B35', linewidth=0.5)
        ax.set_ylabel(param_names[i], fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3, linestyle='--')
        ax.tick_params(labelsize=10)

    axes[-1].set_xlabel('Iteration', fontsize=12, fontweight='bold')
    plt.suptitle('MCMC Trace Plot', fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {output_file.name}")


def plot_posteriors(samples, param_names, output_file):
    """生成后验分布直方图"""
    n_params = samples.shape[1]
    n_cols = min(3, n_params)
    n_rows = (n_params + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 4*n_rows))
    axes = np.atleast_2d(axes).reshape(n_rows, n_cols)

    for i in range(n_params):
        ax = axes[i // n_cols, i % n_cols]

        # 统计量
        mean, median, std = np.mean(samples[:, i]), np.median(samples[:, i]), np.std(samples[:, i])
        q2_5, q97_5 = np.percentile(samples[:, i], [2.5, 97.5])

        # 绘图
        ax.hist(samples[:, i], bins=40, density=True, alpha=0.7, color='#4ECDC4', edgecolor='black', linewidth=0.5)
        ax.axvline(mean, color='red', linestyle='--', linewidth=2.5, label='Mean', alpha=0.8)
        ax.axvline(median, color='#FF6B35', linestyle=':', linewidth=2.5, label='Median', alpha=0.8)
        ax.axvline(q2_5, color='gray', linestyle='-.', linewidth=1.5, alpha=0.6)
        ax.axvline(q97_5, color='gray', linestyle='-.', linewidth=1.5, alpha=0.6)

        ax.set_xlabel(param_names[i], fontsize=11, fontweight='bold')
        ax.set_ylabel('Density', fontsize=11)
        ax.set_title(f'μ={mean:.3e}, σ={std:.3e}\n95% CI=[{q2_5:.3e}, {q97_5:.3e}]', fontsize=9)
        ax.legend(fontsize=9, loc='best')
        ax.grid(alpha=0.2, linestyle='--')

    # 隐藏多余子图
    for i in range(n_params, n_rows * n_cols):
        axes[i // n_cols, i % n_cols].axis('off')

    plt.suptitle('Posterior Distributions', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {output_file.name}")


def plot_pairwise(samples, param_names, output_file):
    """生成参数pairwise散点图（简化版corner图）"""
    n_params = samples.shape[1]
    if n_params < 2:
        print("  ⚠ 参数少于2个，跳过pairwise图")
        return

    fig, axes = plt.subplots(n_params, n_params, figsize=(2.5*n_params, 2.5*n_params))

    for i in range(n_params):
        for j in range(n_params):
            ax = axes[i, j]

            if i == j:
                ax.hist(samples[:, i], bins=25, density=True, alpha=0.7, color='#4ECDC4', edgecolor='black')
            elif i > j:
                ax.hexbin(samples[:, j], samples[:, i], gridsize=30, cmap='Blues', mincnt=1)
            else:
                ax.axis('off')
                continue

            if i == n_params - 1:
                ax.set_xlabel(param_names[j], fontsize=10, fontweight='bold')
            else:
                ax.set_xticklabels([])

            if j == 0 and i > 0:
                ax.set_ylabel(param_names[i], fontsize=10, fontweight='bold')
            elif i != j:
                ax.set_yticklabels([])

            ax.tick_params(labelsize=8)

    plt.suptitle('Parameter Correlations', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {output_file.name}")


def save_statistics(samples, param_names, output_file):
    """保存统计报告"""
    with open(output_file, 'w') as f:
        f.write(f"{'='*90}\nACBICI 贝叶斯校准统计报告\n{'='*90}\n\n")
        f.write(f"总样本数: {samples.shape[0]}\n参数数量: {samples.shape[1]}\n\n")
        f.write(f"{'-'*90}\n{'参数':<15} {'均值':<15} {'中位数':<15} {'标准差':<15} {'95% 置信区间':<25}\n{'-'*90}\n")

        for i in range(samples.shape[1]):
            mean, median, std = np.mean(samples[:, i]), np.median(samples[:, i]), np.std(samples[:, i])
            q2_5, q97_5 = np.percentile(samples[:, i], [2.5, 97.5])
            ci_str = f"[{q2_5:.5e}, {q97_5:.5e}]"
            f.write(f"{param_names[i]:<15} {mean:<15.5e} {median:<15.5e} {std:<15.5e} {ci_str:<25}\n")

        f.write(f"{'-'*90}\n\n")

        # 相关系数矩阵
        if samples.shape[1] > 1:
            f.write(f"参数相关系数矩阵:\n{'-'*90}\n")
            corr = np.corrcoef(samples.T)
            f.write(f"{'':>15}" + "".join(f"{name:>15}" for name in param_names) + "\n")
            for i, name in enumerate(param_names):
                f.write(f"{name:>15}" + "".join(f"{corr[i,j]:>15.3f}" for j in range(len(param_names))) + "\n")
            f.write(f"{'-'*90}\n")

    print(f"  ✓ {output_file.name}")


def main():
    parser = argparse.ArgumentParser(description="生成ACBICI结果可视化（简化版）")
    parser.add_argument('result_dir', type=Path, help='结果目录路径（.out目录）')
    args = parser.parse_args()

    if not args.result_dir.exists():
        sys.exit(f"❌ 错误: 目录不存在: {args.result_dir}")

    print(f"\n{'='*70}\n📊 ACBICI结果可视化: {args.result_dir.name}\n{'='*70}")

    # 加载样本
    samples_file = args.result_dir / "samples.npy"
    if not samples_file.exists():
        sys.exit(f"❌ 错误: 未找到样本文件: {samples_file}")

    samples = np.load(samples_file)
    print(f"\n📁 加载样本: {samples.shape[0]} 样本 × {samples.shape[1]} 参数")

    # 提取参数名称
    param_names = extract_param_names(args.result_dir / "acbici.log")
    if len(param_names) != samples.shape[1]:
        print("⚠ 警告: 参数名称数量不匹配，使用默认名称")
        param_names = [f"param_{i}" for i in range(samples.shape[1])]

    print(f"📝 参数名称: {', '.join(param_names)}\n\n🎨 生成可视化图表...")

    # 生成图表
    plot_trace(samples, param_names, args.result_dir / "trace.png")
    plot_posteriors(samples, param_names, args.result_dir / "posteriors.png")
    plot_pairwise(samples, param_names, args.result_dir / "pairwise.png")
    save_statistics(samples, param_names, args.result_dir / "statistics.txt")

    print(f"\n{'='*70}\n✅ 可视化完成!\n{'='*70}\n\n生成的文件位于: {args.result_dir}/")
    print("  📈 trace.png       - MCMC收敛性trace图\n  📊 posteriors.png  - 参数后验分布")
    print("  🔗 pairwise.png    - 参数相关性图\n  📄 statistics.txt  - 统计摘要报告\n")

    # 打印简要统计
    print(f"📊 参数后验估计 (均值 ± 标准差):\n{'-'*70}")
    for i, name in enumerate(param_names):
        mean, std = np.mean(samples[:, i]), np.std(samples[:, i])
        print(f"  {name:<15}: {mean:.5e} ± {std:.5e}")
    print()


if __name__ == "__main__":
    main()

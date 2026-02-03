#!/usr/bin/env python3
"""
手动生成ACBICI结果图表

这个脚本直接调用ACBICI内置的绘图函数来生成可视化图表。
适用于校准完成但图表未生成的情况。

用法:
    python generate_plots.py meltpool_calibration_known_error.out
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import numpy as np

# 导入ACBICI
sys.path.append(str(Path(__file__).parent / "ACBICI" / "src"))
from ACBICI import calibrator


def generate_plots_from_directory(result_dir: Path):
    """
    从结果目录读取数据并生成图表

    直接使用ACBICI的绘图函数
    """
    print(f"\n处理结果目录: {result_dir}")
    print("=" * 70)

    # 检查必需文件
    samples_file = result_dir / "samples.npy"
    if not samples_file.exists():
        print(f"错误: 未找到样本文件 {samples_file}")
        return False

    log_file = result_dir / "acbici.log"
    if not log_file.exists():
        print(f"警告: 未找到日志文件 {log_file}")

    # 读取样本
    print(f"\n读取MCMC样本...")
    samples = np.load(samples_file)
    print(f"  样本形状: {samples.shape}")
    print(f"  参数数量: {samples.shape[1]}")
    print(f"  样本数量: {samples.shape[0]}")

    # 解析参数名称
    param_names = []
    if log_file.exists():
        with open(log_file, 'r') as f:
            in_param = False
            in_hyper = False
            for line in f:
                if "Parameters to calibrate" in line:
                    in_param = True
                    continue
                elif "Hyperparameters to calibrate" in line:
                    in_param = False
                    in_hyper = True
                    continue
                elif "Known std" in line or "Process report" in line:
                    break

                if (in_param or in_hyper) and line.strip().startswith("+"):
                    name = line.split("+")[1].strip()
                    param_names.append(name)

        print(f"\n参数名称: {param_names}")

    # 如果没有找到参数名，使用默认名称
    if len(param_names) != samples.shape[1]:
        param_names = [f"param_{i}" for i in range(samples.shape[1])]
        print(f"  使用默认参数名: {param_names}")

    # 生成trace图
    print(f"\n生成trace图...")
    try:
        n_params = samples.shape[1]
        fig, axes = plt.subplots(n_params, 1, figsize=(10, 2*n_params))
        if n_params == 1:
            axes = [axes]

        for i in range(n_params):
            axes[i].plot(samples[:, i], alpha=0.5, color='orange', linewidth=0.5)
            axes[i].set_ylabel(param_names[i], fontsize=10)
            axes[i].grid(alpha=0.3)
        axes[-1].set_xlabel('Sample number', fontsize=10)

        plt.tight_layout()
        trace_file = result_dir / "trace.png"
        plt.savefig(trace_file, dpi=150)
        print(f"  ✓ 保存至: {trace_file}")
        plt.close()
    except Exception as e:
        print(f"  ✗ 生成trace图失败: {e}")

    # 生成corner图 (使用matplotlib的简单版本)
    print(f"\n生成corner图...")
    try:
        import corner as corner_pkg
        fig = corner_pkg.corner(
            samples,
            labels=param_names,
            quantiles=[0.16, 0.5, 0.84],
            show_titles=True,
            title_kwargs={"fontsize": 12},
        )
        corner_file = result_dir / "corner.png"
        plt.savefig(corner_file, dpi=150, bbox_inches='tight')
        print(f"  ✓ 保存至: {corner_file}")
        plt.close()
    except ImportError:
        print(f"  ⚠ corner包未安装，使用简化版本...")
        # 简化的pairwise图
        n_params = samples.shape[1]
        fig, axes = plt.subplots(n_params, n_params, figsize=(12, 12))

        for i in range(n_params):
            for j in range(n_params):
                ax = axes[i, j]
                if i == j:
                    # 对角线：直方图
                    ax.hist(samples[:, i], bins=30, density=True, alpha=0.7, color='orange')
                    ax.set_ylabel('Density')
                elif i > j:
                    # 下三角：散点图
                    ax.scatter(samples[:, j], samples[:, i], alpha=0.3, s=1, color='blue')
                else:
                    # 上三角：留空
                    ax.axis('off')

                # 设置标签
                if i == n_params - 1:
                    ax.set_xlabel(param_names[j], fontsize=9)
                if j == 0 and i > 0:
                    ax.set_ylabel(param_names[i], fontsize=9)

        plt.tight_layout()
        corner_file = result_dir / "corner.png"
        plt.savefig(corner_file, dpi=150, bbox_inches='tight')
        print(f"  ✓ 保存至: {corner_file} (简化版)")
        plt.close()
    except Exception as e:
        print(f"  ✗ 生成corner图失败: {e}")

    # 生成后验分布直方图
    print(f"\n生成后验分布图...")
    try:
        n_params = samples.shape[1]
        n_cols = min(3, n_params)
        n_rows = (n_params + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4*n_rows))
        if n_rows == 1:
            axes = axes.reshape(1, -1)

        for i in range(n_params):
            row = i // n_cols
            col = i % n_cols
            ax = axes[row, col]

            # 直方图
            ax.hist(samples[:, i], bins=30, density=True, alpha=0.7, color='orange', edgecolor='black')

            # 添加统计信息
            mean = np.mean(samples[:, i])
            median = np.median(samples[:, i])
            q2_5, q97_5 = np.percentile(samples[:, i], [2.5, 97.5])

            ax.axvline(mean, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean:.3e}')
            ax.axvline(median, color='green', linestyle=':', linewidth=2, label=f'Median: {median:.3e}')

            ax.set_xlabel(param_names[i], fontsize=11)
            ax.set_ylabel('Density', fontsize=11)
            ax.legend(fontsize=8)
            ax.set_title(f'95% CI: [{q2_5:.3e}, {q97_5:.3e}]', fontsize=9)
            ax.grid(alpha=0.3)

        # 隐藏多余子图
        for i in range(n_params, n_rows * n_cols):
            row = i // n_cols
            col = i % n_cols
            axes[row, col].axis('off')

        plt.tight_layout()
        posterior_file = result_dir / "posteriors.png"
        plt.savefig(posterior_file, dpi=150, bbox_inches='tight')
        print(f"  ✓ 保存至: {posterior_file}")
        plt.close()
    except Exception as e:
        print(f"  ✗ 生成后验分布图失败: {e}")

    # 生成统计报告
    print(f"\n生成统计报告...")
    try:
        stats_file = result_dir / "statistics.txt"
        with open(stats_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("ACBICI贝叶斯校准统计报告\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"总样本数: {samples.shape[0]}\n")
            f.write(f"参数数量: {samples.shape[1]}\n\n")

            f.write("-" * 80 + "\n")
            f.write(f"{'参数':<15} {'均值':<12} {'中位数':<12} {'标准差':<12} {'95% 置信区间':<30}\n")
            f.write("-" * 80 + "\n")

            for i in range(samples.shape[1]):
                mean = np.mean(samples[:, i])
                median = np.median(samples[:, i])
                std = np.std(samples[:, i])
                q2_5, q97_5 = np.percentile(samples[:, i], [2.5, 97.5])

                ci_str = f"[{q2_5:.4e}, {q97_5:.4e}]"
                f.write(f"{param_names[i]:<15} {mean:<12.4e} {median:<12.4e} {std:<12.4e} {ci_str:<30}\n")

            f.write("-" * 80 + "\n")

        print(f"  ✓ 保存至: {stats_file}")
    except Exception as e:
        print(f"  ✗ 生成统计报告失败: {e}")

    print("\n" + "=" * 70)
    print("图表生成完成!")
    print("=" * 70)
    return True


def main():
    parser = argparse.ArgumentParser(description="生成ACBICI结果图表")
    parser.add_argument('result_dir', type=Path, help='结果目录路径（.out目录）')

    args = parser.parse_args()

    if not args.result_dir.exists():
        print(f"错误: 目录不存在: {args.result_dir}")
        sys.exit(1)

    if not args.result_dir.is_dir():
        print(f"错误: {args.result_dir} 不是目录")
        sys.exit(1)

    success = generate_plots_from_directory(args.result_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

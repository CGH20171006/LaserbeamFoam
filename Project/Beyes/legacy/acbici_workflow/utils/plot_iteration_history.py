#!/usr/bin/env python3
"""
迭代校准历史可视化工具

读取迭代日志文件，生成参数收敛历史图和不确定性演化图。

用法:
    python plot_iteration_history.py ../iterative_calibration_results/iteration_log.json
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_iteration_log(log_file: Path) -> dict:
    """加载迭代日志"""
    with open(log_file, 'r') as f:
        return json.load(f)


def plot_parameter_convergence(log_data: dict, output_dir: Path):
    """绘制参数收敛历史"""
    iterations_data = log_data['iterations']
    n_iters = len(iterations_data)

    # 提取数据
    iter_nums = [d['iteration'] for d in iterations_data]
    map_estimates = np.array([d['map_estimate'] for d in iterations_data])
    posterior_means = np.array([d['posterior_mean'] for d in iterations_data])
    posterior_stds = np.array([d['posterior_std'] for d in iterations_data])

    param_names = [r'$\sigma$', r'$\gamma$', r'$T_s$ [K]']
    n_params = map_estimates.shape[1]

    # 创建子图
    fig, axes = plt.subplots(n_params, 1, figsize=(10, 3 * n_params))
    if n_params == 1:
        axes = [axes]

    for i, (ax, name) in enumerate(zip(axes, param_names)):
        # MAP 估计
        ax.plot(iter_nums, map_estimates[:, i], 'o-', label='MAP Estimate',
                linewidth=2, markersize=8)

        # 后验均值 ± 标准差
        ax.plot(iter_nums, posterior_means[:, i], 's--', label='Posterior Mean',
                linewidth=1.5, markersize=6, alpha=0.7)
        ax.fill_between(iter_nums,
                        posterior_means[:, i] - posterior_stds[:, i],
                        posterior_means[:, i] + posterior_stds[:, i],
                        alpha=0.2, label='±1 Std')

        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel(name, fontsize=12)
        ax.set_title(f'Parameter Convergence: {name}', fontsize=13, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "parameter_convergence.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 参数收敛图已保存: {output_path}")
    plt.close()


def plot_uncertainty_evolution(log_data: dict, output_dir: Path):
    """绘制不确定性演化"""
    iterations_data = log_data['iterations']

    iter_nums = [d['iteration'] for d in iterations_data]
    posterior_stds = np.array([d['posterior_std'] for d in iterations_data])

    param_names = [r'$\sigma$', r'$\gamma$', r'$T_s$']

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, name in enumerate(param_names):
        ax.plot(iter_nums, posterior_stds[:, i], 'o-', label=name,
                linewidth=2, markersize=8)

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Posterior Standard Deviation', fontsize=12)
    ax.set_title('Uncertainty Evolution', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "uncertainty_evolution.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 不确定性演化图已保存: {output_path}")
    plt.close()


def plot_data_size_growth(log_data: dict, output_dir: Path):
    """绘制数据集增长"""
    iterations_data = log_data['iterations']

    iter_nums = [d['iteration'] for d in iterations_data]
    data_sizes = [d['synthetic_data_size'] for d in iterations_data]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(iter_nums, data_sizes, 'o-', linewidth=2, markersize=8, color='steelblue')

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Synthetic Data Size', fontsize=12)
    ax.set_title('Training Data Growth', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "data_size_growth.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 数据增长图已保存: {output_path}")
    plt.close()


def plot_elapsed_time(log_data: dict, output_dir: Path):
    """绘制每轮耗时"""
    iterations_data = log_data['iterations']

    iter_nums = [d['iteration'] for d in iterations_data]
    elapsed_times = [d['elapsed_time_s'] / 60 for d in iterations_data]  # 转为分钟

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(iter_nums, elapsed_times, color='coral', alpha=0.7, edgecolor='black')

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Elapsed Time (minutes)', fontsize=12)
    ax.set_title('Computation Time per Iteration', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = output_dir / "elapsed_time.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 耗时图已保存: {output_path}")
    plt.close()


def generate_summary_report(log_data: dict, output_dir: Path):
    """生成文本摘要报告"""
    iterations_data = log_data['iterations']
    final_iter = iterations_data[-1]

    report_lines = [
        "=" * 70,
        "迭代校准摘要报告",
        "=" * 70,
        "",
        f"总迭代次数: {final_iter['iteration']}",
        f"收敛状态: {'已收敛' if final_iter['converged'] else '未收敛'}",
        f"收敛原因: {final_iter['convergence_reason']}",
        "",
        "最终 MAP 估计:",
        f"  sigma:           {final_iter['map_estimate'][0]:.6f}",
        f"  Marangoni:       {final_iter['map_estimate'][1]:.6e}",
        f"  substrate_temp:  {final_iter['map_estimate'][2]:.2f} K",
        "",
        "最终后验均值:",
        f"  sigma:           {final_iter['posterior_mean'][0]:.6f}",
        f"  Marangoni:       {final_iter['posterior_mean'][1]:.6e}",
        f"  substrate_temp:  {final_iter['posterior_mean'][2]:.2f} K",
        "",
        "最终后验标准差:",
        f"  sigma:           {final_iter['posterior_std'][0]:.6f}",
        f"  Marangoni:       {final_iter['posterior_std'][1]:.6e}",
        f"  substrate_temp:  {final_iter['posterior_std'][2]:.2f} K",
        "",
        f"最终数据集大小: {final_iter['synthetic_data_size']}",
        f"总计算时间: {sum(d['elapsed_time_s'] for d in iterations_data) / 60:.1f} 分钟",
        "",
        "=" * 70,
    ]

    report_text = "\n".join(report_lines)
    report_path = output_dir / "iteration_summary.txt"
    report_path.write_text(report_text)
    print(f"✓ 摘要报告已保存: {report_path}")

    # 同时打印到终端
    print(f"\n{report_text}")


def main():
    parser = argparse.ArgumentParser(description="可视化迭代校准历史")
    parser.add_argument("log_file", type=Path, help="迭代日志文件路径")
    parser.add_argument("--output-dir", type=Path, default=None,
                       help="输出目录 (默认: 日志文件所在目录)")

    args = parser.parse_args()

    if not args.log_file.exists():
        print(f"[错误] 日志文件不存在: {args.log_file}")
        return

    output_dir = args.output_dir or args.log_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n加载迭代日志: {args.log_file}")
    log_data = load_iteration_log(args.log_file)

    print(f"\n生成可视化图表...")
    plot_parameter_convergence(log_data, output_dir)
    plot_uncertainty_evolution(log_data, output_dir)
    plot_data_size_growth(log_data, output_dir)
    plot_elapsed_time(log_data, output_dir)

    generate_summary_report(log_data, output_dir)

    print(f"\n✓ 所有图表已保存至: {output_dir}/")


if __name__ == "__main__":
    main()

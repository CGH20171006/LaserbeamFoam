#!/usr/bin/env python3
"""
批量提取 results_sweep_framework 中不同功率下的熔池深宽结果
"""
import pandas as pd
from pathlib import Path

def extract_meltpool_metrics(results_dir):
    """
    从 results_sweep_framework 目录中提取所有功率点的熔池指标

    Parameters
    ----------
    results_dir : Path
        结果目录路径 (results_sweep_framework)

    Returns
    -------
    pd.DataFrame
        汇总结果，包含功率、宽度、深度、面积
    """
    results = []

    # 查找所有功率目录
    power_dirs = sorted([d for d in results_dir.iterdir()
                        if d.is_dir() and d.name.endswith('W')])

    print(f"找到 {len(power_dirs)} 个功率目录:")
    for power_dir in power_dirs:
        print(f"  - {power_dir.name}")

    print("\n开始提取数据...\n")

    for power_dir in power_dirs:
        # 提取功率值 (例如 "140W" -> 140)
        power_str = power_dir.name.replace('W', '')
        try:
            power = float(power_str)
        except ValueError:
            print(f"警告: 无法解析功率值 '{power_dir.name}', 跳过")
            continue

        # 读取横截面统计文件
        stats_file = power_dir / "cross_sections_statistics.csv"

        if not stats_file.exists():
            print(f"警告: {power_dir.name} 缺少 cross_sections_statistics.csv, 跳过")
            continue

        try:
            df = pd.read_csv(stats_file)

            # 计算平均值 (单位转换: m -> μm, m² -> μm²)
            width_mean = df['width'].mean() * 1e6  # m -> μm
            depth_mean = df['depth'].mean() * 1e6  # m -> μm

            # 检查是否有 area 列
            if 'area' in df.columns:
                area_mean = df['area'].mean() * 1e12  # m² -> μm²
            else:
                area_mean = float('nan')

            results.append({
                'power_W': power,
                'width_um': width_mean,
                'depth_um': depth_mean,
                'area_um2': area_mean
            })

            print(f"{power_dir.name}:")
            print(f"  宽度: {width_mean:.2f} μm")
            print(f"  深度: {depth_mean:.2f} μm")
            if not pd.isna(area_mean):
                print(f"  面积: {area_mean:.2f} μm²")
            print()

        except Exception as e:
            print(f"错误: 处理 {power_dir.name} 时出错: {e}")
            continue

    # 创建汇总DataFrame
    summary_df = pd.DataFrame(results)
    summary_df = summary_df.sort_values('power_W')

    return summary_df


def main():
    # 结果目录
    case_dir = Path(__file__).parent
    results_dir = case_dir / "results_sweep_framework"

    if not results_dir.exists():
        print(f"错误: 结果目录不存在: {results_dir}")
        return 1

    print("=" * 60)
    print("批量提取熔池深宽结果")
    print("=" * 60)
    print(f"结果目录: {results_dir}")
    print()

    # 提取数据
    summary_df = extract_meltpool_metrics(results_dir)

    if summary_df.empty:
        print("错误: 未提取到任何数据")
        return 1

    # 保存汇总结果
    output_file = results_dir / "sweep_summary.csv"
    summary_df.to_csv(output_file, index=False)

    print("=" * 60)
    print("汇总结果:")
    print("=" * 60)
    print(summary_df.to_string(index=False))
    print()
    print(f"结果已保存到: {output_file}")

    # 额外: 保存到当前目录方便查看
    local_output = case_dir / "sweep_summary.csv"
    summary_df.to_csv(local_output, index=False)
    print(f"副本已保存到: {local_output}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

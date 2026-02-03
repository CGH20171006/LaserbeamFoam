#!/usr/bin/env python3
"""
生成ACBICI Type B校准所需的合成数据

该脚本使用拉丁超立方采样(LHS)在参数空间中采样，
运行OpenFOAM仿真生成合成数据，用于构建高斯过程代理模型。

合成数据格式: [功率, sigma, Marangoni, substrate_temp, 宽度, 深度, 面积]

作者: 基于ACBICI示例改编
日期: 2025-01-02
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from pyDOE import lhs

# 导入自定义模型
from acbici_model import MeltpoolModel


def generate_synthetic_data(
    model: MeltpoolModel,
    n_samples: int,
    output_file: Path,
    power_range: tuple = (140.0, 260.0),
    seed: int = 42,
):
    """
    生成合成数据用于ACBICI Type B校准

    Parameters
    ----------
    model : MeltpoolModel
        熔池仿真模型
    n_samples : int
        生成的样本数量
    output_file : Path
        输出文件路径
    power_range : tuple
        功率范围 (最小值, 最大值)，单位: W
    seed : int
        随机种子
    """
    print("=" * 70)
    print("生成ACBICI Type B校准所需的合成数据")
    print("=" * 70)
    print(f"样本数量: {n_samples}")
    print(f"功率范围: {power_range[0]}-{power_range[1]} W")
    print(f"输出文件: {output_file}")
    print()

    # 设置随机种子
    np.random.seed(seed)

    # 输入维度: 功率 (1D)
    # 参数维度: sigma, Marangoni, substrate_temp, absorptivity (4D)
    total_dim = 1 + 4  # x + p

    # 使用拉丁超立方采样
    print(f"使用拉丁超立方采样生成 {n_samples} 个样本...")
    lhs_samples = lhs(total_dim, n_samples)

    # 功率范围
    power_min, power_max = power_range
    x_samples = lhs_samples[:, 0] * (power_max - power_min) + power_min
    x_samples = x_samples.reshape(-1, 1)

    # 参数范围（从模型的先验分布中获取）
    # sigma: 1.0 - 2.0
    # Marangoni: -8e-4 - -4e-6
    # substrate_temp: 300.0 - 800.0
    # absorptivity: 0.5 - 3.0
    p_samples = np.zeros((n_samples, 4))
    p_samples[:, 0] = lhs_samples[:, 1] * (2.0 - 1.0) + 1.0  # sigma
    p_samples[:, 1] = lhs_samples[:, 2] * (-4e-6 - (-8e-4)) + (-8e-4)  # Marangoni
    p_samples[:, 2] = lhs_samples[:, 3] * (800.0 - 300.0) + 300.0  # substrate_temp
    p_samples[:, 3] = lhs_samples[:, 4] * (3.0 - 0.5) + 0.5  # absorptivity

    print(f"\n参数范围:")
    print(f"  sigma: [{p_samples[:, 0].min():.4f}, {p_samples[:, 0].max():.4f}]")
    print(f"  Marangoni: [{p_samples[:, 1].min():.4e}, {p_samples[:, 1].max():.4e}]")
    print(f"  substrate_temp: [{p_samples[:, 2].min():.1f}, {p_samples[:, 2].max():.1f}] K")
    print(f"  absorptivity: [{p_samples[:, 3].min():.3f}, {p_samples[:, 3].max():.3f}]")
    print()

    # 运行模型生成输出
    print("开始运行OpenFOAM仿真生成合成数据...")
    print("这可能需要较长时间，请耐心等待...\n")

    y_samples = model.symbolicModel(x_samples, p_samples)

    # 检查是否有失败的样本
    valid_mask = ~np.isnan(y_samples).any(axis=1)
    n_valid = valid_mask.sum()
    n_failed = n_samples - n_valid

    if n_failed > 0:
        print(f"\n[警告] {n_failed}/{n_samples} 个样本仿真失败")
        print(f"保留 {n_valid} 个有效样本")

        # 过滤掉失败的样本
        x_samples = x_samples[valid_mask]
        p_samples = p_samples[valid_mask]
        y_samples = y_samples[valid_mask]

    # 组合数据: [功率, sigma, Marangoni, substrate_temp, absorptivity, 宽度, 深度, 面积]
    synthetic_data = np.hstack([x_samples, p_samples, y_samples])

    # 保存数据
    output_file.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(output_file, synthetic_data, header="power sigma Marangoni substrate_temp absorptivity width depth area")

    print("\n" + "=" * 70)
    print("合成数据生成完成!")
    print("=" * 70)
    print(f"有效样本数: {n_valid}")
    print(f"数据已保存至: {output_file}")
    print(f"数据形状: {synthetic_data.shape} (samples x features)")
    print(f"特征: [功率, sigma, Marangoni, substrate_temp, absorptivity, 宽度, 深度, 面积]")
    print()

    # 显示统计信息
    print("合成数据统计:")
    print(f"  功率 (W):         [{x_samples.min():.1f}, {x_samples.max():.1f}]")
    print(f"  sigma:            [{p_samples[:, 0].min():.4f}, {p_samples[:, 0].max():.4f}]")
    print(f"  Marangoni:        [{p_samples[:, 1].min():.4e}, {p_samples[:, 1].max():.4e}]")
    print(f"  substrate_temp:   [{p_samples[:, 2].min():.1f}, {p_samples[:, 2].max():.1f}] K")
    print(f"  absorptivity:     [{p_samples[:, 3].min():.3f}, {p_samples[:, 3].max():.3f}]")
    print(f"  宽度 (μm):        [{y_samples[:, 0].min():.2f}, {y_samples[:, 0].max():.2f}]")
    print(f"  深度 (μm):        [{y_samples[:, 1].min():.2f}, {y_samples[:, 1].max():.2f}]")
    print(f"  面积 (μm²):       [{y_samples[:, 2].min():.2f}, {y_samples[:, 2].max():.2f}]")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="生成ACBICI Type B校准所需的合成数据"
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=20,
        help="生成的样本数量（默认: 20）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../data/synthetic_data.dat"),
        help="输出文件路径（默认: ../data/synthetic_data.dat）",
    )
    parser.add_argument(
        "--power-min",
        type=float,
        default=140.0,
        help="最小功率 (W)（默认: 140）",
    )
    parser.add_argument(
        "--power-max",
        type=float,
        default=260.0,
        help="最大功率 (W)（默认: 260）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（默认: 42）",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("../config.yaml"),
        help="配置文件路径（默认: ../config.yaml）",
    )

    args = parser.parse_args()

    # 创建模型
    print(f"加载配置文件: {args.config}")
    model = MeltpoolModel(config_path=args.config)

    # 生成合成数据
    generate_synthetic_data(
        model=model,
        n_samples=args.n_samples,
        output_file=args.output,
        power_range=(args.power_min, args.power_max),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

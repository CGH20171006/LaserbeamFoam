#!/usr/bin/env python3
"""
为已有的合成数据添加吸收率列

将旧格式:
[power, sigma, Marangoni, substrate_temp, width, depth, area]

转换为新格式:
[power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]

默认吸收率设为 1.0 (无修正)
"""

import argparse
import numpy as np
from pathlib import Path


def add_absorptivity_column(input_file: Path, output_file: Path, absorptivity: float = 1.0):
    """
    为数据文件添加吸收率列

    Parameters
    ----------
    input_file : Path
        输入数据文件 (7列: power, sigma, Marangoni, substrate_temp, width, depth, area)
    output_file : Path
        输出数据文件 (8列: 在第5列插入absorptivity)
    absorptivity : float
        要添加的吸收率值 (默认: 1.0)
    """
    print(f"\n{'='*70}")
    print("为合成数据添加吸收率列")
    print(f"{'='*70}\n")

    # 读取旧数据
    print(f"读取输入文件: {input_file}")
    data = np.loadtxt(input_file)

    n_rows, n_cols = data.shape
    print(f"  数据形状: {n_rows} 行 × {n_cols} 列")

    if n_cols != 7:
        print(f"[错误] 预期 7 列数据，但找到 {n_cols} 列")
        print("预期格式: [power, sigma, Marangoni, substrate_temp, width, depth, area]")
        return False

    # 分离参数和输出
    # 列 0-3: power, sigma, Marangoni, substrate_temp
    # 列 4-6: width, depth, area
    param_part = data[:, :4]  # 前 4 列
    output_part = data[:, 4:]  # 后 3 列 (宽度/深度/面积)

    # 创建吸收率列 (全部设为指定值)
    absorptivity_col = np.full((n_rows, 1), absorptivity)

    # 拼接: [power, sigma, Marangoni, substrate_temp] + [absorptivity] + [width, depth, area]
    new_data = np.hstack([param_part, absorptivity_col, output_part])

    print(f"\n添加吸收率列:")
    print(f"  吸收率值: {absorptivity}")
    print(f"  新数据形状: {new_data.shape[0]} 行 × {new_data.shape[1]} 列")

    # 保存新数据
    print(f"\n保存输出文件: {output_file}")
    np.savetxt(
        output_file,
        new_data,
        fmt='%.18e',
        header="power sigma Marangoni substrate_temp absorptivity width depth area",
        comments='# '
    )

    # 验证
    print("\n验证数据格式...")
    print(f"前 3 行预览:")
    print(f"{'列名':<25} | 旧数据 (前3行) | 新数据 (前3行)")
    print("-" * 70)

    labels_old = ['power', 'sigma', 'Marangoni', 'substrate_temp', 'width', 'depth', 'area']
    labels_new = ['power', 'sigma', 'Marangoni', 'substrate_temp', 'absorptivity', 'width', 'depth', 'area']

    # 映射旧列到新列
    old_to_new = {
        0: 0,  # power -> power
        1: 1,  # sigma -> sigma
        2: 2,  # Marangoni -> Marangoni
        3: 3,  # substrate_temp -> substrate_temp
        4: 5,  # width -> width (跳过吸收率列)
        5: 6,  # depth -> depth
        6: 7   # area -> area
    }

    for old_idx, new_idx in old_to_new.items():
        old_val = data[0, old_idx]
        new_val = new_data[0, new_idx]
        match = "✓" if np.isclose(old_val, new_val) else "✗"
        print(f"{labels_old[old_idx]:<25} | {old_val:11.4e} | {new_val:11.4e} {match}")

    # 显示新添加的吸收率列
    print(f"{'absorptivity (新增)':<25} | {'N/A':>11} | {new_data[0, 4]:11.4e} ⭐")

    print(f"\n{'='*70}")
    print("✓ 数据转换完成!")
    print(f"{'='*70}\n")

    print("文件对比:")
    print(f"  旧文件: {input_file} ({n_cols} 列)")
    print(f"  新文件: {output_file} ({new_data.shape[1]} 列)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="为已有合成数据添加吸收率列",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认值 (absorptivity=1.0)
  python add_absorptivity_to_data.py \\
      ../../data/synthetic_data.dat \\
      ../../data/synthetic_data_with_absorptivity.dat

  # 自定义吸收率值
  python add_absorptivity_to_data.py \\
      ../../data/synthetic_data.dat \\
      ../../data/synthetic_data_with_absorptivity.dat \\
      --absorptivity 1.2

注意:
  - 旧数据文件必须是 7 列格式
  - 新数据文件将是 8 列格式 (在第5列插入absorptivity)
  - 建议先备份原数据文件
        """
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="输入数据文件 (7列格式)"
    )
    parser.add_argument(
        "output_file",
        type=Path,
        help="输出数据文件 (8列格式)"
    )
    parser.add_argument(
        "--absorptivity",
        type=float,
        default=1.0,
        help="要添加的吸收率值 (默认: 1.0)"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="自动备份输入文件为 .backup"
    )

    args = parser.parse_args()

    # 检查输入文件
    if not args.input_file.exists():
        print(f"[错误] 输入文件不存在: {args.input_file}")
        return 1

    # 可选备份
    if args.backup:
        backup_file = args.input_file.with_suffix(args.input_file.suffix + '.backup')
        print(f"备份原文件: {backup_file}")
        import shutil
        shutil.copy(args.input_file, backup_file)

    # 执行转换
    success = add_absorptivity_column(
        args.input_file,
        args.output_file,
        args.absorptivity
    )

    if success:
        print("\n建议后续步骤:")
        print("1. 检查新数据文件格式是否正确")
        print("2. 用新文件替换旧文件 (或更新校准脚本中的路径)")
        print("3. 运行校准验证 4 参数模型")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())

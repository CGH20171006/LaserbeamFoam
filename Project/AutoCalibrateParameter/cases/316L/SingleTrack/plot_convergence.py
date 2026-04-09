#!/usr/bin/env python3
"""
收敛曲线可视化脚本
用法：python3 plot_convergence.py
      python3 plot_convergence.py --history runs/bayes_history.csv --n-initial 20
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

# 自动定位 src 目录
SCRIPT_DIR = Path(__file__).parent
SRC_DIR = SCRIPT_DIR / "../../../src"
sys.path.insert(0, str(SRC_DIR.resolve()))

from PyMeltpoolCalib.postprocess.convergence import save_convergence_plot, plot_parameter_evolution


def parse_args():
    parser = argparse.ArgumentParser(description="贝叶斯优化收敛曲线可视化")
    parser.add_argument(
        "--history",
        default="runs/bayes_history.csv",
        help="历史记录 CSV 路径 (默认: runs/bayes_history.csv)",
    )
    parser.add_argument(
        "--n-initial",
        type=int,
        default=20,
        help="初始采样点数，用于在图中标注分界线 (默认: 20)",
    )
    parser.add_argument(
        "--output-dir",
        default="convergence_plots",
        help="图表输出目录 (默认: convergence_plots)",
    )
    parser.add_argument(
        "--title",
        default="316L SingleTrack Bayesian Optimization",
        help="图表标题前缀",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    history_path = SCRIPT_DIR / args.history
    if not history_path.exists():
        print(f"错误：找不到历史文件 {history_path}")
        sys.exit(1)

    rows = []
    with open(history_path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("status", "").strip() == "ok" and r.get("objective", "").strip():
                rows.append(r)

    if not rows:
        print("错误：历史文件中没有有效数据")
        sys.exit(1)

    costs = [float(r["objective"]) for r in rows]

    # 自动检测 CSV 中存在的参数列（按优化顺序）
    candidate_params = [
        ("sigma",               "sigma"),
        ("Marangoni_Constant",  "Marangoni_Constant"),
        ("recoilCoeff",         "recoilCoeff"),
        ("radius_flavour",      "radius_flavour"),
        ("laser_radius",        "laser_radius"),
    ]
    present = [(label, col) for label, col in candidate_params if col in rows[0]]
    param_names = [label for label, _ in present]
    params = np.array([
        [float(r[col]) for _, col in present]
        for r in rows
    ])

    out = SCRIPT_DIR / args.output_dir
    out.mkdir(exist_ok=True)

    p1 = save_convergence_plot(
        out, costs,
        n_initial=args.n_initial,
        title=f"{args.title} Convergence ({len(rows)} runs)",
    )
    p2 = plot_parameter_evolution(
        out, params,
        param_names=param_names,
        title=f"{args.title} Parameter Evolution ({len(rows)} runs)",
    )

    best_idx = int(np.argmin(costs))
    print(f"总轮数：{len(rows)}")
    print(f"当前最优：run{best_idx + 1}，objective={costs[best_idx]:.4f}")
    print(f"  sigma={params[best_idx, 0]:.4f}  marangoni={params[best_idx, 1]:.2e}  recoilCoeff={params[best_idx, 2]:.4f}")
    print(f"图已保存到 {out}/")
    print(f"  {p1.name}")
    print(f"  {p2.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ACBICI Type B 贝叶斯校准主脚本

使用expensiveCalibrator进行材料参数的贝叶斯校准，
该方法构建高斯过程代理模型，适用于计算昂贵的OpenFOAM仿真。

校准参数: sigma, Marangoni_Constant, substrate_temp, absorptivity
实验数据: 5个功率点 (140-260W)，观测量：宽度、深度、面积
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from acbici_model import MeltpoolModel

sys.path.append(str(Path(__file__).parent.parent / "ACBICI" / "src"))
from ACBICI import expensiveCalibrator, HalfCauchy


def prepare_experimental_data_multivariate(exp_csv: Path) -> np.ndarray:
    """准备多变量实验数据为ACBICI格式: [功率, 宽度, 深度, 面积]"""
    print(f"读取实验数据（多变量格式）: {exp_csv}")
    df = pd.read_csv(exp_csv)
    experiments = df[["power_W", "width_um", "depth_um", "area_um2"]].values
    print(f"实验数据形状: {experiments.shape}, 功率点数: {len(experiments)}\n")
    return experiments


def run_visualization(name: str):
    """运行可视化脚本"""
    try:
        result_dir = Path(f"{name}.out")
        if result_dir.exists():
            plot_script = Path(__file__).parent / "utils" / "plot_results_simple.py"
            print("\n使用自定义可视化生成图表...")
            result = subprocess.run([sys.executable, str(plot_script), str(result_dir)],
                                  capture_output=False, text=True)
            if result.returncode != 0:
                print("⚠ 可视化脚本返回错误")
    except Exception as e:
        print(f"⚠ 注意: 自定义可视化失败: {e}")
        print(f"  您可以稍后手动运行: python utils/plot_results_simple.py {name}.out")


def run_calibration(model, experiments, synthetic_data, name, kernel,
                   nsteps, burn, nwalkers, error_type, **kwargs):
    """
    统一的校准函数

    Parameters
    ----------
    error_type : str
        'known' 或 'unknown'
    kwargs : dict
        'known': std_value (float)
        'unknown': std_prior_sigma (float)
    """
    # 打印配置
    error_info = (f"已知实验误差 (σ_exp = {kwargs.get('std_value', 0)} μm)"
                  if error_type == 'known'
                  else f"未知实验误差 (HalfCauchy σ={kwargs.get('std_prior_sigma', 0)})")
    print(f"\n{'='*70}\nType B 校准 - {error_info}\n{'='*70}")
    print(f"核函数: {kernel}, MCMC: {nsteps} steps, {nwalkers} walkers, burn-in {burn*100}%\n")

    # 配置校准器
    cal = expensiveCalibrator(model, name=name, kernel=kernel)
    if error_type == 'known':
        cal.setExperimentalSTDValue(kwargs['std_value'])
    else:
        cal.setExperimentalSTDPrior(HalfCauchy(mu=0, sigma=kwargs['std_prior_sigma']))
    cal.storeExperimentalData(experiments)
    cal.storeSyntheticData(synthetic_data)

    # 运行校准
    print("开始MCMC采样...")
    cal.calibrate(nsteps=nsteps, burn=burn, nwalkers=nwalkers)

    # 生成报告和可视化
    print("\n生成报告和可视化...")
    cal.printReport()
    cal.plot(trace=True, corner=True, dumpfiles=True)

    run_visualization(name)
    print(f"\n结果已保存至目录: {name}.out/")
    return cal


def main():
    parser = argparse.ArgumentParser(description="ACBICI Type B 贝叶斯校准 - 熔池仿真参数")

    # 数据参数
    parser.add_argument("--config", type=Path, default=Path("../config.yaml"),
                       help="OpenFOAM配置文件（默认: ../config.yaml）")
    parser.add_argument("--experimental-data", type=Path, default=Path("../experimental_data.csv"),
                       help="实验数据CSV（默认: ../experimental_data.csv）")
    parser.add_argument("--synthetic-data", type=Path, default=Path("../data/synthetic_data.dat"),
                       help="合成数据文件（默认: ../data/synthetic_data.dat）")

    # 校准选项
    parser.add_argument("--calibration-type", choices=["known-error", "unknown-error", "both"],
                       default="both", help="校准类型（默认: both）")
    parser.add_argument("--kernel", choices=["expo", "matern32", "matern52", "ratquad"],
                       default="matern32", help="高斯过程核函数（默认: matern32）")

    # MCMC参数
    parser.add_argument("--nsteps", type=int, default=500, help="MCMC总步数（默认: 500）")
    parser.add_argument("--burn", type=float, default=0.2, help="燃烧期比例（默认: 0.2）")
    parser.add_argument("--nwalkers", type=int, default=16, help="MCMC walker数量（默认: 16，推荐≥3×参数维度）")

    # 误差参数
    parser.add_argument("--exp-std", type=float, default=5.0,
                       help="已知实验误差标准差/μm（默认: 5.0）")
    parser.add_argument("--exp-std-prior-sigma", type=float, default=10.0,
                       help="未知误差先验尺度参数（默认: 10.0）")
    parser.add_argument("--name", type=str, default="meltpool_calibration",
                       help="校准器基础名称（默认: meltpool_calibration）")

    args = parser.parse_args()
    start_time = time.time()

    # 初始化
    print(f"\n{'='*70}\nACBICI Type B 贝叶斯校准\n熔池仿真材料参数校准\n{'='*70}\n")
    print("初始化模型...")
    model = MeltpoolModel(config_path=args.config)
    print(f"参数维度: {model.getNParam()}, 名称: {model.paramLabels}")
    print(f"输入维度: {model.xdim} (功率), 输出维度: {model.ydim} (宽度/深度/面积)\n")

    # 加载数据
    experiments = prepare_experimental_data_multivariate(args.experimental_data)
    if not args.synthetic_data.exists():
        sys.exit(f"[错误] 合成数据不存在: {args.synthetic_data}\n"
                f"请运行: python generate_synthetic_data.py --n-samples 20")
    synthetic_data = np.loadtxt(args.synthetic_data)
    print(f"加载合成数据: {args.synthetic_data}, 形状: {synthetic_data.shape}\n")

    # 运行校准
    calibrators = []
    cal_params = {
        'model': model, 'experiments': experiments, 'synthetic_data': synthetic_data,
        'kernel': args.kernel, 'nsteps': args.nsteps, 'burn': args.burn,
        'nwalkers': args.nwalkers
    }

    if args.calibration_type in ["known-error", "both"]:
        cal = run_calibration(name=f"{args.name}_known_error", error_type='known',
                            std_value=args.exp_std, **cal_params)
        calibrators.append(cal)

    if args.calibration_type in ["unknown-error", "both"]:
        cal = run_calibration(name=f"{args.name}_unknown_error", error_type='unknown',
                            std_prior_sigma=args.exp_std_prior_sigma, **cal_params)
        calibrators.append(cal)

    # 总结
    elapsed = time.time() - start_time
    print(f"\n{'='*70}\n校准完成!\n{'='*70}")
    print(f"总耗时: {elapsed/60:.1f} 分钟 ({elapsed:.1f} 秒)")
    print(f"完成 {len(calibrators)} 个校准任务\n结果目录:")
    for cal in calibrators:
        print(f"  - {cal.name}/")
    print("\n包含: corner图(参数后验分布)、trace图(MCMC收敛性)、统计报告\n")


if __name__ == "__main__":
    main()

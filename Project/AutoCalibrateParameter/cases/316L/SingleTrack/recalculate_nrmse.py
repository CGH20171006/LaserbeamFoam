#!/usr/bin/env python
"""
重新计算 bayes_history.csv 中的正确 NRMSE 值

修复前的 NRMSE 计算没有应用 output_weights，导致 area 的误差主导了目标值。
此脚本应用正确的 output_weights 重新计算所有历史记录的 NRMSE。
"""

import numpy as np
import pandas as pd
from pathlib import Path

# 配置
OUTPUT_WEIGHTS = [1.0, 1.0, 0.0]  # [width, depth, area]
PENALTY_VALUE = 1e8

# 文件路径
exp_csv = "SingleTrackExperimentalData.csv"
history_csv = "bayes_history.csv"
output_csv = "bayes_history_corrected.csv"

# 加载实验数据
print(f"正在加载实验数据: {exp_csv}")
exp_df = pd.read_csv(exp_csv)

# 列名映射
alt_mapping = {
    "power_W": ["power", "Power", "P"],
    "width_um": ["width", "Width", "w"],
    "depth_um": ["depth", "Depth", "d"],
}

for col, alts in alt_mapping.items():
    if col not in exp_df.columns:
        for alt in alts:
            if alt in exp_df.columns:
                exp_df = exp_df.rename(columns={alt: col})
                break

# 提取功率点和观测值
power_points = exp_df["power_W"].values
observations = exp_df[["width_um", "depth_um"]].values

# 如果实验数据没有area，创建一个全0的列
if len(observations[0]) == 2:
    observations = np.column_stack([observations, np.zeros(len(observations))])

print(f"实验数据: {len(power_points)} 个功率点")
print(f"功率点: {power_points}")
print(f"观测值形状: {observations.shape}")

# 加载历史记录
print(f"\n正在加载历史记录: {history_csv}")
history_df = pd.read_csv(history_csv)
print(f"历史记录: {len(history_df)} 条")

# 功率点列名映射
power_cols_map = {}
for power in power_points:
    w_col = f"width_um_{int(power)}W"
    d_col = f"depth_um_{int(power)}W"
    a_col = f"area_um2_{int(power)}W"
    power_cols_map[power] = (w_col, d_col, a_col)

# 检查是否所有功率点的列都存在
has_all_cols = all(
    all(c in history_df.columns for c in cols)
    for cols in power_cols_map.values()
)

if not has_all_cols:
    print("错误: CSV 中缺少预测数据列")
    exit(1)

# 重新计算每一行的 NRMSE
print(f"\n重新计算 NRMSE (应用 output_weights: {OUTPUT_WEIGHTS})...")
new_objectives = []
old_objectives = []

for idx, row in history_df.iterrows():
    # 提取预测值
    predictions = []
    for power in power_points:
        w_col, d_col, a_col = power_cols_map[power]
        predictions.append([row[w_col], row[d_col], row[a_col]])

    predictions = np.array(predictions)

    # 计算残差
    residuals = predictions - observations

    # 处理 NaN
    nan_mask = np.isnan(residuals)
    if np.any(nan_mask):
        residuals[nan_mask] = PENALTY_VALUE

    # 归一化
    scales = np.mean(np.abs(observations), axis=0)
    scales = np.where(scales < 1e-10, 1.0, scales)
    normalized_residuals = residuals / scales

    # 应用 output_weights
    weights = np.array(OUTPUT_WEIGHTS)
    active_mask = weights > 0

    if np.any(active_mask):
        active_residuals = normalized_residuals[:, active_mask]
        nrmse = float(np.sqrt(np.mean(active_residuals**2)) * 100)
    else:
        nrmse = float(np.sqrt(np.mean(normalized_residuals**2)) * 100)

    new_objectives.append(nrmse)
    old_objectives.append(row["objective"])

# 更新 objective 列
history_df["objective_old"] = old_objectives
history_df["objective"] = new_objectives

# 显示统计信息
print(f"\n统计信息:")
print(f"  旧 NRMSE 范围: {min(old_objectives):.2f} - {max(old_objectives):.2f}")
print(f"  新 NRMSE 范围: {min(new_objectives):.2f} - {max(new_objectives):.2f}")
print(f"  平均变化: {np.mean(old_objectives):.2f} -> {np.mean(new_objectives):.2f}")

# 找到最优解
best_idx_old = np.argmin(old_objectives)
best_idx_new = np.argmin(new_objectives)

print(f"\n最优解变化:")
print(f"  旧最优: Job {best_idx_old + 1}, NRMSE = {old_objectives[best_idx_old]:.2f}")
print(f"    参数: sigma={history_df.iloc[best_idx_old]['sigma']:.4f}, "
      f"marangoni={history_df.iloc[best_idx_old]['Marangoni_Constant']:.2e}, "
      f"recoilCoeff={history_df.iloc[best_idx_old].get('recoilCoeff', history_df.iloc[best_idx_old].get('damper', float('nan'))):.3f}")

print(f"  新最优: Job {best_idx_new + 1}, NRMSE = {new_objectives[best_idx_new]:.2f}")
print(f"    参数: sigma={history_df.iloc[best_idx_new]['sigma']:.4f}, "
      f"marangoni={history_df.iloc[best_idx_new]['Marangoni_Constant']:.2e}, "
      f"recoilCoeff={history_df.iloc[best_idx_new].get('recoilCoeff', history_df.iloc[best_idx_new].get('damper', float('nan'))):.3f}")

# 显示前5个最优解
print(f"\n新的前5个最优解:")
sorted_indices = np.argsort(new_objectives)
for i in range(min(5, len(sorted_indices))):
    idx = sorted_indices[i]
    print(f"  {i+1}. Job {idx + 1}: NRMSE = {new_objectives[idx]:.2f}% "
          f"(旧值: {old_objectives[idx]:.2f}%)")
    print(f"     sigma={history_df.iloc[idx]['sigma']:.4f}, "
          f"marangoni={history_df.iloc[idx]['Marangoni_Constant']:.2e}, "
          f"recoilCoeff={history_df.iloc[idx].get('recoilCoeff', history_df.iloc[idx].get('damper', float('nan'))):.3f}")

# 保存到新文件
print(f"\n保存修正后的数据到: {output_csv}")
# 移除 objective_old 列，只保留新的 objective
history_df_output = history_df.drop(columns=["objective_old"])
history_df_output.to_csv(output_csv, index=False)

# 可选：备份旧文件并覆盖原文件
backup_csv = "bayes_history_backup.csv"
print(f"备份原文件到: {backup_csv}")
import shutil
shutil.copy(history_csv, backup_csv)

print(f"覆盖原文件: {history_csv}")
history_df_output.to_csv(history_csv, index=False)

print("\n完成！")
print(f"  - 原文件已备份到: {backup_csv}")
print(f"  - 修正后的数据已保存到: {history_csv}")
print(f"  - 修正后的数据副本: {output_csv}")

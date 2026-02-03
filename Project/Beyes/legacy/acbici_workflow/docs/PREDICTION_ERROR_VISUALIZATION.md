# 预测误差可视化指南

## 📊 功能说明

展示每轮迭代中，**使用 MAP 估计参数预测实验数据的误差演化**，直观体现校准精度的提升。

---

## 🎯 可视化内容

### 1. 误差演化图（按功率点）
- **文件**: `prediction_error_by_power.png`
- **内容**: 3 个子图（宽度/深度/面积），每个子图显示所有功率点的相对误差随迭代的变化
- **作用**: 查看每个实验条件下的拟合改进

### 2. MAE/RMSE 演化图
- **文件**: `mae_rmse_evolution.png`
- **内容**: 平均绝对误差 (MAE) 和均方根误差 (RMSE) 的演化
- **作用**: 汇总所有功率点，展示整体拟合精度提升

### 3. 误差热力图
- **文件**: `prediction_error_heatmap.png`
- **内容**: 功率点 × 迭代次数的二维热力图，颜色表示相对误差
- **作用**: 快速识别哪些条件难以校准

### 4. 详细对比表
- **文件**: `prediction_error_detailed.txt`
- **内容**: 每轮、每个功率点的实验值、预测值、绝对误差、相对误差
- **作用**: 精确数值参考，可用于论文表格

---

## 🚀 使用方法

### 方法 1: 从日志文件直接生成（推荐）⭐

**前提**: 使用更新版的 `iterative_calibration.py`（包含自动预测误差计算）

```bash
# 运行迭代校准
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 3

# 可视化预测误差（快速，无需重新仿真）
python utils/plot_prediction_error_from_log.py \
    ../iterative_calibration_results/iteration_log.json \
    ../experimental_data.csv
```

**优点**:
- ✅ 快速（几秒钟）
- ✅ 无需重新运行 OpenFOAM
- ✅ 使用最近邻插值从合成数据估计

**缺点**:
- ⚠️ 预测精度取决于合成数据密度
- ⚠️ 不是真实 OpenFOAM 仿真结果

---

### 方法 2: 重新运行仿真（高精度）

```bash
python utils/plot_prediction_error_evolution.py \
    ../iterative_calibration_results/iteration_log.json \
    ../experimental_data.csv \
    --config ../config.yaml
```

**优点**:
- ✅ 使用真实 OpenFOAM 仿真
- ✅ 精度最高

**缺点**:
- ⚠️ 非常慢（每轮需要运行 5 次仿真）
- ⚠️ 如果有 N 轮迭代，需要 5N 次仿真

**适用场景**: 最终结果验证、论文图表生成

---

### 方法 3: 使用 GP 代理模型（待实现）

```bash
python utils/plot_prediction_error_evolution.py \
    ... \
    --use-gp
```

**原理**: 从每轮的 ACBICI 校准器中提取训练好的 GP 模型，快速预测

**状态**: 🚧 功能开发中（需要 ACBICI 支持导出 GP 模型）

---

## 📈 示例输出

### 误差演化图示例

```
Width: Prediction Error vs Iteration
  10% ┐
      │  ●━━━○━━━○━━━○  140W (误差逐渐减小)
   5% │  ■╌╌╌□╌╌╌□╌╌╌□  170W
      │  ▲╍╍╍△╍╍╍△╍╍╍△  200W
   0% ├─────────────────── (目标: 0% 误差)
      │  ◆┅┅┅◇┅┅┅◇┅┅┅◇  230W
  -5% │  ★⋯⋯⋯☆⋯⋯⋯☆⋯⋯⋯☆  260W
      │
 -10% └─────────────────────→ Iteration
        1    2    3    4
```

### MAE 演化示例

```
Mean Absolute Error
  15 μm ┐
        │  ●━━━●━━━●━━━○  Width (从 12→8→5→3 μm)
  10 μm │  ■╌╌╌■╌╌╌■╌╌╌□  Depth
        │  ▲╍╍╍▲╍╍╍▲╍╍╍△  Area
   5 μm │   ↘  ↘  ↘  ↘  (持续下降)
        │
   0 μm └─────────────────→ Iteration
```

---

## 🔍 结果解读

### 理想情况

1. **误差演化图**: 所有曲线向 0 收敛
2. **MAE/RMSE**: 单调递减
3. **热力图**: 颜色从深红/深蓝 → 白色（接近 0）

### 常见模式

#### 模式 1: 快速收敛
```
MAE: 15 → 8 → 4 → 3 → 3  (第 3-4 轮趋于稳定)
结论: 校准成功，可提前停止
```

#### 模式 2: 缓慢改进
```
MAE: 15 → 13 → 11 → 10 → 9  (持续但缓慢下降)
结论: 继续迭代或增加每轮采样数
```

#### 模式 3: 振荡不稳定
```
MAE: 15 → 8 → 12 → 9 → 11  (上下波动)
结论: 采样策略过激，改用 map_only 或减小采样范围
```

#### 模式 4: 某些功率点误差大
```
140W: -2%
170W: +1%
200W: +15%  ← 异常
230W: -3%
260W: +2%
```
**可能原因**:
- 该条件下实验数据噪声大
- 模型在该区域不准确
- 参数空间采样不足

**解决方案**:
- 检查实验数据质量
- 增加该功率点附近的合成数据
- 考虑模型物理假设是否合理

---

## 📊 输出文件汇总

运行可视化后，会生成：

```
iterative_calibration_results/
├── iteration_log.json                      # 原始日志（包含预测数据）
├── prediction_error_by_power.png           # ⭐ 主要误差演化图
├── mae_rmse_evolution.png                  # ⭐ 汇总精度指标
├── prediction_error_heatmap.png            # 热力图视图
└── prediction_error_detailed.txt           # 详细数值表格
```

---

## 💡 最佳实践

### 1. 什么时候生成误差图？

- ✅ **每次迭代校准完成后**：验证收敛效果
- ✅ **论文撰写时**：展示方法有效性
- ✅ **调试时**：诊断校准问题

### 2. 如何选择可视化方法？

| 场景 | 推荐方法 | 耗时 |
|------|----------|------|
| **日常检查** | 方法 1 (从日志) | < 10 秒 |
| **最终验证** | 方法 2 (真实仿真) | ~ 每轮 20 分钟 |
| **论文图表** | 方法 2 (真实仿真) | ~ 每轮 20 分钟 |

### 3. 图表放在哪里？

**论文主文:**
- `prediction_error_by_power.png` (展示拟合改进)
- `mae_rmse_evolution.png` (量化精度提升)

**补充材料:**
- `prediction_error_heatmap.png`
- `prediction_error_detailed.txt`

---

## 🔧 技术细节

### 预测方法

#### 方法 1 (从日志)
```python
# 最近邻插值
for each power_point:
    # 从合成数据中找到功率相同、参数最接近 MAP 的样本
    closest_sample = find_nearest(synthetic_data, MAP_params, power)
    prediction = closest_sample.output
```

**精度**: 取决于合成数据密度
- 初始（20 样本）：较粗糙
- 迭代后（80+ 样本）：较精确

#### 方法 2 (真实仿真)
```python
# 直接运行 OpenFOAM
for each power_point:
    prediction = model.symbolicModel(power, MAP_params)
```

**精度**: 最高（与实际使用一致）

---

## 📚 相关文档

- [迭代校准主文档](ITERATIVE_CALIBRATION_GUIDE.md)
- [单轮 vs 迭代对比](COMPARISON_SINGLE_VS_ITERATIVE.md)
- [主 README](../README.md)

---

## ❓ 常见问题

### Q1: 日志中没有预测数据怎么办？

**A**: 确保使用更新版的 `iterative_calibration.py`。可以重新运行校准，或使用方法 2 手动计算。

### Q2: 预测误差比预期大？

**A**: 可能原因：
1. 合成数据不足（增加初始样本数）
2. 使用了近似插值而非真实仿真（切换到方法 2）
3. 模型本身与实验不匹配（检查物理假设）

### Q3: 某些迭代的误差突然增大？

**A**: 检查该轮的 MAP 估计是否异常。可能是 MCMC 采样问题，查看 trace 图诊断。

### Q4: 如何导出为论文格式？

**A**:
```bash
# 生成高分辨率图像
python utils/plot_prediction_error_from_log.py ... --dpi 300

# 转换为 PDF
convert prediction_error_by_power.png prediction_error_by_power.pdf
```

---

**文档更新**: 2025-01-13

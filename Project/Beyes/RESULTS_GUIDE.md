# ACBICI校准结果查看指南

本文档说明如何查看和解读ACBICI贝叶斯校准的结果。

## 结果文件位置

运行校准后，结果保存在 `.out` 目录中：

```
meltpool_calibration_known_error.out/
├── acbici.log           # ACBICI运行日志和统计摘要
├── samples.npy          # MCMC后验样本（numpy数组）
├── logprob.npy          # 对数后验概率
├── logprior.npy         # 对数先验概率
├── trace.png            # MCMC收敛性trace图
├── posteriors.png       # 参数后验分布直方图
├── pairwise.png         # 参数两两相关性图
└── statistics.txt       # 统计报告（均值、置信区间等）
```

## 主要结果文件说明

### 1. acbici.log - 校准日志

**位置**: `meltpool_calibration_known_error.out/acbici.log`

**内容**:
- 校准器配置信息（参数、先验、核函数等）
- MCMC采样统计（步数、acceptance rate等）
- **参数后验统计摘要**（均值、中位数、MAP、95%置信区间）

**如何查看**:
```bash
cat meltpool_calibration_known_error.out/acbici.log
```

**关键部分**:
```
Summary statistics (4800 samples)

 Parameter     Mean     Median     app-MAP    Variance       95%-credible
---------------------------------------------------------------------------
 $\sigma$   1.076e+00  1.069e+00  1.007e+00  3.374e-03  [1.002e+00, 1.218e+00]
 $\gamma$   -4.135e-04  -3.856e-04  -7.846e-04  5.402e-08  [-7.927e-04, -5.211e-05]
 $T_s$      3.473e+02  3.344e+02  3.046e+02  1.721e+03  [3.016e+02, 4.442e+02]
```

### 2. statistics.txt - 详细统计报告

**位置**: `meltpool_calibration_known_error.out/statistics.txt`

**内容**:
- 每个参数的均值、中位数、标准差
- 95%置信区间
- **参数相关系数矩阵**

**如何查看**:
```bash
cat meltpool_calibration_known_error.out/statistics.txt
```

**解读相关系数矩阵**:
```
参数相关系数矩阵:
                  $\sigma$   $\gamma$    $T_s$
$\sigma$            1.000      0.410     0.099
$\gamma$            0.410      1.000     0.433
$T_s$               0.099      0.433     1.000
```

- 对角线为1（自相关）
- 正值：参数正相关（一起增大或减小）
- 负值：参数负相关（一个增大另一个减小）
- |r| > 0.7：强相关，说明参数可能难以独立估计

### 3. trace.png - MCMC收敛性图

**位置**: `meltpool_calibration_known_error.out/trace.png`

**用途**: 检查MCMC采样是否收敛

**如何解读**:

✅ **收敛良好的迹象**:
- 图像呈"毛毛虫"状，在某个区域稳定波动
- 没有明显的趋势（上升或下降）
- 燃烧期后快速稳定

❌ **未收敛的迹象**:
- 持续上升或下降的趋势
- 剧烈跳跃或卡在某个值
- 不同walker之间差异很大

**示例**:
```
σ参数的trace:
  ┃
1.2┃    ╱╲╱╲╱╲╱╲╱╲╱╲╱╲    ← 良好：稳定波动
  ┃   ╱  ╲  ╲  ╲  ╲  ╲
1.0┃──────────────────────
  └──────────────────────→ 迭代
```

### 4. posteriors.png - 后验分布图

**位置**: `meltpool_calibration_known_error.out/posteriors.png`

**用途**: 可视化每个参数的后验概率分布

**如何解读**:

**分布形状**:
- **尖峰型**：参数被数据良好约束，不确定度小
- **宽平型**：参数不确定度大，数据信息不足
- **多峰型**：可能存在多个局部最优解

**图上标注**:
- 红色虚线：均值（mean）
- 橙色点线：中位数（median）
- 灰色线：95%置信区间边界
- 标题：μ=均值, σ=标准差, 95% CI=[下界, 上界]

### 5. pairwise.png - 参数相关性图

**位置**: `meltpool_calibration_known_error.out/pairwise.png`

**用途**: 显示参数两两之间的联合分布和相关性

**如何解读**:

**图的布局**:
```
        σ          γ         T_s
σ    [hist]    [scatter]  [scatter]
γ    [scatter]  [hist]   [scatter]
T_s  [scatter] [scatter]  [hist]
```

- **对角线**：单个参数的直方图
- **下三角**：参数两两散点图（hexbin密度图）
- **上三角**：空白

**散点图形状**:
- **椭圆形**：参数有相关性
  - 斜向右上：正相关
  - 斜向右下：负相关
- **圆形**：参数独立
- **香蕉形**：强非线性相关

### 6. samples.npy - 原始后验样本

**位置**: `meltpool_calibration_known_error.out/samples.npy`

**用途**: 原始MCMC样本数据，可用于自定义分析

**如何读取**:
```python
import numpy as np

samples = np.load("meltpool_calibration_known_error.out/samples.npy")
# samples.shape = (4800, 6)  # 4800个样本，6个参数

# 提取第1个参数（sigma）的所有样本
sigma_samples = samples[:, 0]

# 计算自定义统计量
import numpy as np
mean_sigma = np.mean(sigma_samples)
std_sigma = np.std(sigma_samples)
```

## 快速检查清单

完成校准后，按以下顺序检查结果：

### ✅ 步骤1: 检查MCMC收敛性

```bash
# 查看acbici.log中的警告
grep -A 5 "WARNING" meltpool_calibration_known_error.out/acbici.log
```

如果看到：
```
WARNING: Chain may be too short, results may not have converged.
```

**解决方案**: 增加MCMC步数，重新运行：
```bash
python acbici_calibration.py --nsteps 20000
```

### ✅ 步骤2: 查看trace图

```bash
# 在图片查看器中打开
xdg-open meltpool_calibration_known_error.out/trace.png
```

确认：
- [ ] 没有明显趋势
- [ ] 呈"毛毛虫"状稳定波动
- [ ] 燃烧期后快速稳定

### ✅ 步骤3: 检查参数估计

```bash
# 查看统计报告
cat meltpool_calibration_known_error.out/statistics.txt
```

关注：
- [ ] 95%置信区间是否合理
- [ ] 参数估计值是否在先验范围内
- [ ] 标准差是否过大（说明不确定度高）

### ✅ 步骤4: 查看参数相关性

```bash
xdg-open meltpool_calibration_known_error.out/pairwise.png
```

检查：
- [ ] 是否有强相关参数（|r| > 0.7）
- [ ] 相关性是否合理（物理上有意义）

## 常见问题与解决方案

### Q1: 为什么参数估计值很接近先验边界？

**可能原因**:
1. 先验范围设置过窄
2. 数据支持参数在边界附近
3. 模型与数据不匹配

**解决方案**:
- 扩大先验范围（编辑 [acbici_model.py](acbici_model.py:272-274)）
- 检查实验数据质量
- 考虑使用Type C或D校准（考虑模型差异）

### Q2: 95%置信区间很宽，怎么办？

**原因**: 参数不确定度大，数据信息不足以精确估计

**解决方案**:
1. 增加实验数据点
2. 提高实验数据质量（减小测量误差）
3. 增加合成数据样本数（改进GP代理模型）
4. 检查参数是否对观测量敏感

### Q3: 两个参数高度相关（|r| > 0.9），正常吗？

**可能原因**:
1. 参数物理上耦合（如σ和γ都影响表面张力）
2. 数据不足以区分两个参数的独立作用
3. 过参数化（参数冗余）

**影响**:
- 参数单独估计不准确
- 但参数组合的预测可能仍然准确

**解决方案**:
- 增加实验设计的多样性（不同功率点、不同工况）
- 考虑固定其中一个参数
- 使用参数变换（如估计参数比值而非单独值）

### Q4: MCMC trace图显示未收敛

**解决方案**:
```bash
# 增加MCMC步数
python acbici_calibration.py --nsteps 50000 --burn 0.3

# 增加walker数量
python acbici_calibration.py --nwalkers 32
```

### Q5: 后验分布是多峰的

**原因**:
- 参数空间有多个局部最优解
- 可能是物理上合理的多解问题

**处理**:
1. 运行更长的MCMC链，确保探索整个空间
2. 查看pairwise图，理解多峰结构
3. 如果多峰明显分离，可能需要更多数据区分
4. 可以报告多个模式的参数估计

## 如何手动重新生成图表

如果图表缺失或需要重新生成：

```bash
# 使用简化版可视化脚本
python plot_results_simple.py meltpool_calibration_known_error.out

# 为所有结果目录生成图表
for dir in *.out; do
    python plot_results_simple.py "$dir"
done
```

## 与旧系统结果对比

如果您之前使用 `bayes_opt.py`，可以对比结果：

```python
import json
import numpy as np

# 旧系统最优值
with open('bayes_best.json', 'r') as f:
    old_result = json.load(f)
print("旧系统最优值:", old_result['best_params'])

# 新系统后验均值
samples = np.load('meltpool_calibration_known_error.out/samples.npy')
new_result = {
    'sigma': np.mean(samples[:, 0]),
    'Marangoni': np.mean(samples[:, 1]),
    'substrate_temp': np.mean(samples[:, 2]),
}
print("新系统后验均值:", new_result)

# 对比
for key in old_result['best_params']:
    old_val = old_result['best_params'][key]
    new_val = new_result[key]
    diff_pct = abs(new_val - old_val) / old_val * 100
    print(f"{key}: {old_val:.4e} -> {new_val:.4e} (差异 {diff_pct:.1f}%)")
```

## 安装corner包（可选，获得更美观的图表）

如果想使用ACBICI内置的完整可视化功能，需要安装corner包：

```bash
# 使用pip安装
pip install corner

# 或使用conda
conda install -c conda-forge corner
```

安装后，ACBICI的plot方法会自动使用corner生成更专业的可视化图表。

## 进一步分析

### 预测不确定度传播

使用后验样本进行预测，获得预测的不确定度：

```python
import numpy as np
from acbici_model import MeltpoolModel

# 加载模型和样本
model = MeltpoolModel()
samples = np.load('meltpool_calibration_known_error.out/samples.npy')
params_samples = samples[:, :3]  # 前3个是物理参数

# 对特定功率（如200W）进行预测
power = 200.0
x = np.array([[power]])

# 使用后验样本进行预测（可能需要较长时间）
n_samples = 100  # 使用部分样本加速
predictions = []
for i in range(n_samples):
    p = params_samples[i::len(samples)//n_samples][:1]
    y_pred = model.symbolicModel(x, p)
    predictions.append(y_pred[0])

predictions = np.array(predictions)

# 预测的均值和不确定度
pred_mean = np.mean(predictions, axis=0)
pred_std = np.std(predictions, axis=0)

print(f"200W功率下的预测:")
print(f"  宽度: {pred_mean[0]:.2f} ± {pred_std[0]:.2f} μm")
print(f"  深度: {pred_mean[1]:.2f} ± {pred_std[1]:.2f} μm")
print(f"  面积: {pred_mean[2]:.2f} ± {pred_std[2]:.2f} μm²")
```

## 参考资料

- ACBICI文档: https://acbici.readthedocs.io
- Corner图解读: https://corner.readthedocs.io
- MCMC诊断: [Gelman & Rubin (1992)](https://projecteuclid.org/journals/statistical-science/volume-7/issue-4/Inference-from-Iterative-Simulation-Using-Multiple-Sequences/10.1214/ss/1177011136.full)

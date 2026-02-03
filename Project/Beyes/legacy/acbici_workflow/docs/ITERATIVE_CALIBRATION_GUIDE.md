# 迭代贝叶斯校准使用指南

## 📖 概述

迭代贝叶斯校准是对标准 ACBICI 校准的增强版本，通过多轮自适应采样逐步改进参数估计精度。

### 核心思想

```
传统方法 (单轮):
初始数据 → GP + MCMC → 参数后验分布

迭代方法 (多轮):
初始数据 → GP + MCMC → 提取最优参数 → 运行新仿真 → 更新数据集 → 重复
```

### 优势

1. **自适应改进**: 在高概率参数区域增加采样密度
2. **减少不确定性**: 聚焦于后验分布的峰值区域
3. **加速收敛**: 比盲目 LHS 采样更高效
4. **鲁棒性**: 自动判断收敛，避免过度拟合

---

## 🚀 快速开始

### 前置条件

确保已生成初始合成数据：
```bash
cd /home/cgh/LaserbeamFoam/Project/Beyes/acbici_workflow
python generate_synthetic_data.py --n-samples 20
```

### 基础用法

```bash
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 3 \
    --sampling-strategy hybrid
```

这将：
- 最多运行 5 轮迭代
- 每轮在最优参数附近采样 3 个新点
- 使用混合采样策略（50% 利用 + 50% 探索）

---

## 📊 工作流程详解

### 第 1 轮迭代

```
1. 加载初始合成数据 (20 个 LHS 样本)
2. 训练高斯过程代理模型
3. MCMC 采样得到参数后验分布
4. 提取 MAP 估计: θ₁* = [σ*, γ*, T_s*]
5. 在 θ₁* 附近采样 3 个新参数点
6. 运行 3 × 5 = 15 次新仿真 (3 参数点 × 5 功率点)
7. 更新合成数据集: 20 → 35 样本
```

### 第 2 轮迭代

```
1. 加载更新后的合成数据 (35 样本)
2. 重新训练 GP 模型 (在 θ₁* 附近精度更高)
3. MCMC 采样得到更精确的后验分布
4. 提取 MAP 估计: θ₂*
5. 检查收敛:
   - 参数变化: ||θ₂* - θ₁*|| / ||θ₁*|| < 1% ?
   - 后验标准差: std(θ) < 0.05 ?
6. 如果未收敛,继续采样和仿真
```

### 收敛条件 (满足任一即停止)

| 条件 | 公式 | 默认阈值 | 含义 |
|------|------|----------|------|
| 参数相对变化 | `‖θᵢ - θᵢ₋₁‖ / ‖θᵢ₋₁‖` | < 0.01 | 参数变化小于 1% |
| 后验标准差 | `max(std(σ), std(γ), std(T_s))` | < 0.05 | 不确定性足够小 |
| 最大迭代次数 | `i` | ≥ 5 | 防止无限循环 |

---

## ⚙️ 参数配置

### 核心参数

#### `--max-iterations` (默认: 5)
最大迭代次数。推荐值:
- 快速测试: 3
- 标准使用: 5-7
- 精细校准: 10

#### `--n-new-samples` (默认: 3)
每轮新采样的参数点数量。推荐值:
- 快速收敛: 2-3 (每轮 10-15 次仿真)
- 平衡策略: 4-5 (每轮 20-25 次仿真)
- 高精度: 6-8 (每轮 30-40 次仿真)

**计算量估算**:
```
每轮仿真次数 = n_new_samples × n_power_points
总仿真次数 ≈ 初始样本 + max_iterations × n_new_samples × n_power_points
```

例如: 20 + 5 × 3 × 5 = 95 次仿真

#### `--sampling-strategy`

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `map_only` | 仅在 MAP 估计附近紧密采样 | 后验分布单峰且尖锐 |
| `posterior` | 按后验标准差采样 | 不确定性较大时 |
| `hybrid` ⭐ | 50% 利用 + 50% 探索 | 通用场景(推荐) |

采样公式:
```python
# map_only
θ_new ~ N(θ_MAP, 0.3 × σ_posterior)

# posterior
θ_new ~ N(θ_MAP, σ_posterior)

# hybrid
50% ~ N(θ_MAP, 0.3 × σ_posterior)  # 利用
50% ~ N(θ_MAP, σ_posterior)        # 探索
```

### 收敛参数

#### `--tol-param-change` (默认: 0.01)
参数相对变化阈值。
- 宽松: 0.05 (5% 变化即停止)
- 标准: 0.01 (1% 变化)
- 严格: 0.005 (0.5% 变化)

#### `--tol-std` (默认: 0.05)
后验标准差阈值（归一化值）。
- 宽松: 0.1
- 标准: 0.05
- 严格: 0.01

### MCMC 参数

```bash
--kernel matern32       # GP 核函数
--nsteps 1000           # MCMC 步数
--burn 0.2              # Burn-in 比例
--nwalkers 16           # Walker 数量
```

推荐配置:
- 快速测试: `--nsteps 500 --nwalkers 12`
- 标准使用: `--nsteps 1000 --nwalkers 16`
- 高精度: `--nsteps 5000 --nwalkers 24`

---

## 📁 输出文件

### 目录结构

```
iterative_calibration_results/
├── iteration_log.json              # 迭代历史日志
├── iteration_summary.txt           # 文本摘要报告
├── parameter_convergence.png       # 参数收敛图
├── uncertainty_evolution.png       # 不确定性演化图
├── data_size_growth.png            # 数据集增长图
├── elapsed_time.png                # 每轮耗时统计
└── iterative_calibration_results_iter01.out/  # 第 1 轮校准结果
    ├── corner_plot.png
    ├── trace_plot.png
    └── ...
└── iterative_calibration_results_iter02.out/  # 第 2 轮校准结果
    └── ...
```

### iteration_log.json 格式

```json
{
  "config": {
    "max_iterations": 5,
    "n_new_samples_per_iter": 3,
    "kernel": "matern32",
    "sampling_strategy": "hybrid",
    "convergence_params": {
      "tol_param_change": 0.01,
      "tol_std": 0.05
    }
  },
  "iterations": [
    {
      "iteration": 1,
      "map_estimate": [1.4523, -2.34e-4, 512.3],
      "posterior_mean": [1.4501, -2.38e-4, 510.8],
      "posterior_std": [0.0823, 1.25e-5, 45.2],
      "converged": false,
      "convergence_reason": "未收敛",
      "elapsed_time_s": 1245.6,
      "synthetic_data_size": 35
    },
    ...
  ]
}
```

---

## 📈 结果可视化

### 自动生成可视化

迭代完成后，使用可视化工具：

```bash
python utils/plot_iteration_history.py \
    iterative_calibration_results/iteration_log.json
```

### 生成的图表

#### 1. 参数收敛图 (parameter_convergence.png)
- 每个参数的 MAP 估计演化
- 后验均值 ± 标准差区间
- 判断是否收敛到稳定值

#### 2. 不确定性演化图 (uncertainty_evolution.png)
- 后验标准差随迭代次数的变化
- 理想情况: 单调递减

#### 3. 数据集增长图 (data_size_growth.png)
- 合成数据集大小的增长
- 验证采样策略

#### 4. 耗时统计图 (elapsed_time.png)
- 每轮迭代的计算时间
- 帮助优化资源分配

---

## 🎯 使用场景与示例

### 场景 1: 快速原型验证

目标: 快速测试迭代框架是否工作

```bash
python iterative_calibration.py \
    --max-iterations 3 \
    --n-new-samples 2 \
    --nsteps 500 \
    --sampling-strategy hybrid
```

预期耗时: ~30 分钟

### 场景 2: 标准生产运行

目标: 平衡精度和计算成本

```bash
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 3 \
    --nsteps 1000 \
    --nwalkers 16 \
    --tol-param-change 0.01 \
    --tol-std 0.05 \
    --sampling-strategy hybrid
```

预期耗时: ~2-3 小时

### 场景 3: 高精度校准

目标: 最小化不确定性

```bash
python iterative_calibration.py \
    --max-iterations 10 \
    --n-new-samples 5 \
    --nsteps 5000 \
    --nwalkers 24 \
    --tol-param-change 0.005 \
    --tol-std 0.01 \
    --sampling-strategy hybrid
```

预期耗时: ~8-12 小时

### 场景 4: 后验分布探索

目标: 充分探索参数空间（不确定性大时）

```bash
python iterative_calibration.py \
    --max-iterations 7 \
    --n-new-samples 4 \
    --sampling-strategy posterior \
    --tol-std 0.03
```

---

## 🔍 故障排查

### 问题 1: 参数振荡不收敛

**现象**: MAP 估计在迭代间大幅波动

**原因**:
- 采样策略过于随机
- MCMC 步数不足

**解决方案**:
```bash
--sampling-strategy map_only  # 减少探索
--nsteps 2000                 # 增加 MCMC 步数
--tol-param-change 0.02       # 放宽收敛条件
```

### 问题 2: 不确定性不降低

**现象**: 后验标准差停滞不变

**原因**:
- 新采样点未覆盖高不确定性区域
- GP 模型欠拟合

**解决方案**:
```bash
--n-new-samples 5             # 增加采样点
--sampling-strategy posterior # 切换到基于不确定性的采样
--kernel matern52             # 尝试更灵活的核函数
```

### 问题 3: 仿真失败率高

**现象**: 新仿真经常失败 (NaN 结果)

**原因**:
- 采样到不物理的参数组合
- OpenFOAM 数值不稳定

**解决方案**:
```bash
--sampling-strategy map_only  # 仅在已验证区域采样
--n-new-samples 2             # 减少冒险尝试
```

并检查参数边界是否合理 ([acbici_model.py](../acbici_model.py:217-219))

### 问题 4: 计算时间过长

**解决方案**:
```bash
--max-iterations 3            # 减少迭代次数
--n-new-samples 2             # 减少每轮采样
--nsteps 500                  # 减少 MCMC 步数
```

或使用 HPC 集群并行运行 OpenFOAM。

---

## 🧪 进阶技巧

### 1. 手动设置初始参数

如果有先验知识，可修改 [acbici_model.py](../acbici_model.py:217-219) 的先验分布：

```python
# 收窄搜索范围
self.addParameter(label=r'$\sigma$', prior=Uniform(a=1.2, b=1.6))  # 原: 1.0-2.0
```

### 2. 分阶段迭代

先快速收敛，再精细调整：

**阶段 1: 粗略搜索**
```bash
python iterative_calibration.py \
    --max-iterations 3 \
    --n-new-samples 4 \
    --tol-param-change 0.05
```

**阶段 2: 精细优化** (使用阶段 1 生成的更新后的 synthetic_data.dat)
```bash
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 2 \
    --tol-param-change 0.005 \
    --sampling-strategy map_only
```

### 3. 监控实时进度

使用 `tail` 实时查看日志：
```bash
tail -f iterative_calibration_results/iteration_log.json
```

### 4. 中断后恢复

如果中断，脚本会自动使用更新后的 `synthetic_data.dat`，只需重新运行：
```bash
python iterative_calibration.py --max-iterations 5
```

---

## 📚 理论背景

### 为什么迭代有效？

**高斯过程的局部性**:
GP 模型在训练数据密集的区域预测更准确。通过在 MAP 估计附近增加样本，可以：
- 减少该区域的 GP 方差
- 提高 MCMC 采样的置信度
- 加速参数收敛

**数学表达**:
```
GP 预测方差: Var[y*|X, y, x*] = k(x*, x*) - k(x*, X) K⁻¹ k(X, x*)

当 x* 接近 X 中的点时，Var ↓
```

### 采样策略对比

| 策略 | 探索性 | 利用性 | 适用阶段 |
|------|--------|--------|----------|
| LHS (初始) | 高 | 低 | 第 0 轮 |
| Posterior | 中 | 中 | 第 1-2 轮 |
| Hybrid | 中 | 高 | 第 2-4 轮 |
| MAP only | 低 | 极高 | 第 5+ 轮 |

---

## 🔗 相关文档

- [README.md](../README.md) - 主文档
- [README_ACBICI.md](README_ACBICI.md) - ACBICI 框架说明
- [acbici_model.py](../acbici_model.py) - 模型实现
- [iterative_calibration.py](../iterative_calibration.py) - 主脚本

---

## 📝 示例输出

### 终端输出
```
######################################################################
# 迭代 1/5
######################################################################

加载合成数据: ../data/synthetic_data.dat, 形状 (100, 7)

======================================================================
校准: iterative_calibration_results_iter01
======================================================================
开始 MCMC 采样...
100%|██████████| 1000/1000 [05:23<00:00, 3.09it/s]

迭代 1 后验统计:
  MAP 估计: σ=1.4523, γ=-2.34e-04, T_s=512.3
  后验均值: σ=1.4501, γ=-2.38e-04, T_s=510.8
  后验标差: σ=0.0823, γ=1.25e-05, T_s=45.2

收敛检查: 未收敛

生成新采样点 (策略: hybrid)...
新参数采样范围:
  sigma: [1.4201e+00, 1.4876e+00]
  Marangoni: [-2.4512e-04, -2.2103e-04]
  substrate_temp: [4.9823e+02, 5.2945e+02]

运行新仿真: 3 个参数点 × 5 个功率点 = 15 次仿真
...
✓ 数据已更新: ../data/synthetic_data.dat, 新形状 (115, 7)

迭代 1 完成，耗时 8.5 分钟
```

---

## 💡 最佳实践

1. **初始数据质量**: 确保初始 LHS 样本覆盖完整参数空间 (推荐 20-30 样本)

2. **逐步收紧**: 先用宽松的收敛条件快速找到大致区域，再精细调整

3. **监控不确定性**: 如果后验标准差停滞，考虑增加采样点或切换核函数

4. **验证物理性**: 定期检查 MAP 估计是否符合物理直觉

5. **保存中间结果**: 每轮自动生成 corner 图和 trace 图，及时检查

6. **备份数据**: `synthetic_data.dat` 会自动备份为 `.backup`，但建议手动保存初始版本

---

**文档更新**: 2025-01-13

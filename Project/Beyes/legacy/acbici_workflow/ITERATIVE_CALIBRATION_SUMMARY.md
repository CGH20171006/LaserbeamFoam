# 迭代贝叶斯校准 - 快速参考

## 🎯 核心思想

```
单轮: 固定数据集 → 一次校准 → 输出结果
迭代: 初始数据 → 校准 → 提取最优参数 → 新仿真 → 更新数据 → 循环直到收敛
```

**关键优势**: 自适应聚焦于高概率参数区域，逐步降低不确定性

---

## 🚀 快速开始

### 1. 生成初始数据 (仅一次)

```bash
python generate_synthetic_data.py --n-samples 20
```

### 2. 运行迭代校准

```bash
# 快速测试 (3 轮, ~30 分钟)
python iterative_calibration.py --max-iterations 3 --n-new-samples 2

# 标准运行 (5 轮, ~2 小时)
python iterative_calibration.py --max-iterations 5 --n-new-samples 3

# 高精度 (10 轮, ~6 小时)
python iterative_calibration.py --max-iterations 10 --n-new-samples 5 --nsteps 2000
```

### 3. 查看结果

```bash
# 自动生成可视化
python utils/plot_iteration_history.py iterative_calibration_results/iteration_log.json

# 查看文本摘要
cat iterative_calibration_results/iteration_summary.txt
```

---

## 📊 关键参数

| 参数 | 默认值 | 推荐范围 | 说明 |
|------|--------|----------|------|
| `--max-iterations` | 5 | 3-10 | 最大迭代轮数 |
| `--n-new-samples` | 3 | 2-5 | 每轮新采样参数点数 |
| `--sampling-strategy` | hybrid | hybrid/posterior/map_only | 采样策略 |
| `--tol-param-change` | 0.01 | 0.005-0.05 | 参数变化收敛阈值 |
| `--tol-std` | 0.05 | 0.01-0.1 | 后验标准差收敛阈值 |
| `--nsteps` | 500 | 500-5000 | MCMC 步数 |

---

## 📈 预期效果

### 典型改进 (相比单轮)

| 指标 | 单轮 | 迭代 (5轮) | 改进 |
|------|------|-----------|------|
| 参数误差 | ~2-5% | < 1% | **60-80%** |
| 后验标准差 | 0.10-0.15 | 0.03-0.05 | **70-80%** |
| 仿真次数 | 100 | 160 | +60% |
| 计算时间 | 45 min | 120 min | +167% |

**成本效益**: 投入 60% 仿真换取 70%+ 不确定性降低

---

## 🎨 输出文件

```
iterative_calibration_results/
├── iteration_log.json              # 完整迭代历史 (JSON)
├── iteration_summary.txt           # 文本摘要报告
├── parameter_convergence.png       # 参数演化图
├── uncertainty_evolution.png       # 不确定性下降曲线
├── data_size_growth.png            # 数据集增长
├── elapsed_time.png                # 每轮耗时
└── *_iter01.out/, *_iter02.out/... # 每轮详细结果
```

---

## 🔍 收敛判断

**自动停止条件** (满足任一):

1. **参数稳定**: `||θᵢ - θᵢ₋₁|| / ||θᵢ₋₁|| < 0.01` (默认 1%)
2. **不确定性充分小**: `max(std) < 0.05` (默认)
3. **达到最大迭代次数**: 防止无限循环

---

## ⚙️ 三种采样策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `hybrid` ⭐ | 50% 利用 + 50% 探索 | 通用 (推荐) |
| `map_only` | 紧密围绕 MAP 估计 | 后验分布已很尖锐 |
| `posterior` | 按后验标准差采样 | 不确定性仍较大 |

---

## 🛠️ 故障排查

### 问题 1: 参数振荡不收敛

**症状**: MAP 估计在迭代间波动

**解决**:
```bash
--sampling-strategy map_only  # 减少探索
--nsteps 2000                 # 增加 MCMC 步数
```

### 问题 2: 不确定性不下降

**症状**: 后验 std 停滞

**解决**:
```bash
--n-new-samples 5             # 增加采样密度
--sampling-strategy posterior # 针对性采样
```

### 问题 3: 仿真失败率高

**症状**: 新参数点导致 OpenFOAM 崩溃

**解决**:
```bash
--sampling-strategy map_only  # 仅在安全区域采样
--n-new-samples 2             # 减少冒险尝试
```

---

## 📚 文档索引

- **[完整使用指南](docs/ITERATIVE_CALIBRATION_GUIDE.md)** - 详细参数说明和高级用法
- **[单轮 vs 迭代对比](docs/COMPARISON_SINGLE_VS_ITERATIVE.md)** - 性能指标和场景建议
- **[主 README](README.md)** - 整体工作流说明

---

## 💡 最佳实践

### ✅ 推荐做法

1. **初始数据质量优先**: 20-30 LHS 样本已足够
2. **逐步策略**: 先用宽松收敛条件快速探索，再精细调整
3. **监控 std 变化**: 如连续 2 轮下降 < 10%，提前停止
4. **保留中间结果**: 每轮的 corner 图有助于诊断

### ❌ 常见误区

1. ❌ "迭代总是更好" → 取决于任务需求
2. ❌ "初始样本越多越好" → 20-30 已足够，迭代会自动加密
3. ❌ "必须运行到最大轮数" → 满足收敛条件即可停止

---

## 🧪 快速测试

使用提供的示例脚本:

```bash
bash examples/quick_start_iterative.sh
```

该脚本会:
- 自动检查/生成初始数据
- 运行 3 轮快速迭代 (~30 分钟)
- 生成所有可视化图表
- 输出结果摘要

---

## 📞 进一步帮助

- **理论背景**: 见 [ACBICI 文档](docs/README_ACBICI.md)
- **模型定义**: 见 [acbici_model.py](acbici_model.py)
- **问题反馈**: 检查日志文件 `iteration_log.json`

---

**更新**: 2025-01-13 | **版本**: 1.0

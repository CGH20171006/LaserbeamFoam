# ACBICI 贝叶斯校准系统

使用ACBICI框架进行OpenFOAM熔池仿真材料参数的贝叶斯校准。

## 概述

本系统使用**ACBICI Type B校准**（expensiveCalibrator），专为计算昂贵的OpenFOAM仿真设计。它通过构建高斯过程代理模型加速校准过程，并提供完整的不确定度量化。

### 校准参数

- **sigma**: 表面张力系数 (1.0-2.0)
- **Marangoni_Constant**: Marangoni效应常数 (-8e-4 to -4e-6)
- **substrate_temp**: 基板温度 (300-800 K)

### 实验数据

- 5个功率点: 140, 170, 200, 230, 260 W
- 观测量: 熔池宽度、深度、面积 (μm, μm²)

## 文件结构

```
.
├── acbici_model.py              # OpenFOAM模型的ACBICI封装
├── acbici_calibration.py        # 主校准脚本
├── generate_synthetic_data.py   # 生成合成数据脚本
├── config.yaml                  # OpenFOAM运行配置
├── experimental_data.csv        # 实验观测数据
├── ACBICI/                      # ACBICI框架源代码
└── data/                        # 数据目录
    └── synthetic_data.dat       # 合成数据（需生成）
```

## 安装依赖

### 1. 安装ACBICI

```bash
cd ACBICI
pip install -e .
```

### 2. 安装其他依赖

```bash
pip install numpy pandas pyyaml matplotlib seaborn
```

## 使用流程

### 步骤 1: 生成合成数据

Type B校准需要合成数据来构建高斯过程代理模型。使用拉丁超立方采样在参数空间中采样：

```bash
# 生成20个合成样本（推荐，但计算时间较长）
python generate_synthetic_data.py --n-samples 20

# 快速测试（5个样本）
python generate_synthetic_data.py --n-samples 5 --output data/synthetic_test.dat

# 自定义功率范围和随机种子
python generate_synthetic_data.py \
    --n-samples 15 \
    --power-min 150 \
    --power-max 250 \
    --seed 123
```

**注意**: 生成合成数据需要运行多次完整的OpenFOAM仿真，可能需要数小时。建议：
- 在HPC集群上运行
- 先用少量样本（5-10个）测试流程
- 生产环境使用20-30个样本

合成数据将保存为: `data/synthetic_data.dat`

格式: `[功率, sigma, Marangoni, substrate_temp, 宽度, 深度, 面积]`

### 步骤 2: 运行贝叶斯校准

有两种校准模式：

#### 模式 A: 已知实验误差

适用于实验误差已通过重复测量估计的情况：

```bash
python acbici_calibration.py \
    --calibration-type known-error \
    --exp-std 5.0 \
    --nsteps 10000 \
    --kernel matern32
```

#### 模式 B: 未知实验误差

同时估计参数和实验误差：

```bash
python acbici_calibration.py \
    --calibration-type unknown-error \
    --exp-std-prior-sigma 10.0 \
    --nsteps 15000 \
    --kernel matern52
```

#### 同时运行两种模式（推荐）

```bash
python acbici_calibration.py \
    --calibration-type both \
    --nsteps 10000
```

### 步骤 3: 查看结果

校准完成后，结果保存在以下目录：

```
meltpool_calibration_known_error/
├── corner_plot.png              # 参数后验分布联合图
├── trace_plot.png               # MCMC收敛性trace图
├── posterior_samples.csv        # 后验样本
├── statistics.txt               # 统计摘要
└── ...

meltpool_calibration_unknown_error/
└── ...
```

**关键结果文件**:
- **corner_plot.png**: 显示所有参数的边缘分布和两两相关性
- **statistics.txt**: 包含参数的均值、中位数、MAP估计、95%置信区间
- **posterior_samples.csv**: 后验样本，可用于进一步分析

## 参数说明

### generate_synthetic_data.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--n-samples` | 20 | 生成的合成样本数量 |
| `--output` | data/synthetic_data.dat | 输出文件路径 |
| `--power-min` | 140.0 | 最小功率 (W) |
| `--power-max` | 260.0 | 最大功率 (W) |
| `--seed` | 42 | 随机种子 |
| `--config` | config.yaml | OpenFOAM配置文件 |

### acbici_calibration.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--experimental-data` | experimental_data.csv | 实验数据文件 |
| `--synthetic-data` | data/synthetic_data.dat | 合成数据文件 |
| `--calibration-type` | both | 校准类型: known-error, unknown-error, both |
| `--kernel` | matern32 | GP核函数: expo, matern32, matern52, ratquad |
| `--nsteps` | 10000 | MCMC总步数 |
| `--burn` | 0.2 | 燃烧期比例 (0-1) |
| `--nwalkers` | 16 | MCMC walker数量 |
| `--exp-std` | 5.0 | 已知实验标准差 (μm) |
| `--exp-std-prior-sigma` | 10.0 | 未知误差先验尺度参数 |
| `--name` | meltpool_calibration | 校准器名称前缀 |

## 核函数选择建议

ACBICI支持多种高斯过程核函数：

- **expo**: 指数核，适合不太光滑的函数
- **matern32**: Matérn 3/2核，**推荐**，适合中等光滑度
- **matern52**: Matérn 5/2核，适合较光滑的函数
- **ratquad**: 有理二次核，非常灵活但计算稍慢

**建议**: 先用 `matern32` 测试，如果拟合不佳可尝试 `matern52` 或 `expo`。

## MCMC收敛性建议

### 检查收敛性

1. **查看trace图**: 参数应该在燃烧期后稳定在某个区域，像"毛毛虫"
2. **检查acceptance rate**: 通常在20-50%之间为佳
3. **运行多条链**: 使用多个walker确保探索整个后验空间

### 调整建议

如果MCMC未收敛：
- 增加 `--nsteps` (如20000, 50000)
- 增加 `--burn` (如0.3, 0.5)
- 增加 `--nwalkers` (如32, 64)
- 检查先验分布是否合理

## 与旧版本的差异

### bayes_opt.py（旧）vs ACBICI（新）

| 特性 | bayes_opt.py | ACBICI Type B |
|------|--------------|---------------|
| **方法** | 贝叶斯优化 | 贝叶斯推断 |
| **输出** | 最优参数点估计 | 完整后验分布 |
| **不确定度** | 无 | 完整UQ分析 |
| **采样器** | 自定义GP+LCB | emcee MCMC |
| **代理模型** | 简单RBF核 | 多种GP核可选 |
| **模型差异** | 未考虑 | Type C/D可处理 |
| **科学严谨性** | 工程优化 | 科学发表标准 |

### 迁移说明

**已移除的功能**:
- `SimpleBO` 类（替换为ACBICI的GP代理模型）
- 基于LCB的采集函数（替换为MCMC采样）
- `bayes_history.csv` 格式（替换为后验样本）

**保留的功能**:
- OpenFOAM仿真运行逻辑
- 参数更新机制
- 后处理脚本调用
- config.yaml配置系统

## 常见问题

### Q1: 合成数据生成失败怎么办？

A: 检查：
1. OpenFOAM环境是否正确配置（`config.yaml`）
2. 仿真是否能正常运行（先手动测试一次）
3. 参数范围是否合理（避免极端值导致仿真崩溃）

### Q2: MCMC采样很慢？

A: 这是正常的，贝叶斯推断需要大量采样。建议：
1. 先用少量步数（如1000）测试
2. 使用HPC集群或多核并行
3. 检查GP代理模型是否训练良好（合成数据质量）

### Q3: 如何解读corner图？

A:
- **对角线**: 每个参数的边缘后验分布（直方图）
- **非对角线**: 参数间的两两联合分布（散点图）
- **峰值明显**: 参数被数据良好约束
- **宽平分布**: 参数不确定度大，需要更多数据

### Q4: 参数后验分布很宽怎么办？

A: 可能原因：
1. 实验数据不足以约束参数
2. 参数对观测量不敏感
3. 模型存在形式误差（考虑Type C或D）
4. 先验分布过宽

## 高级用法

### 使用自定义先验分布

编辑 [acbici_model.py](acbici_model.py:272-274)：

```python
# 将Uniform先验替换为Normal先验
self.addParameter(label=r'$\sigma$', prior=Normal(mu=1.5, sigma=0.2))
```

ACBICI支持的先验：`Uniform`, `Normal`, `LogNormal`, `HalfCauchy`, `Gamma` 等

### 添加更多输出维度

修改 [acbici_model.py](acbici_model.py:268)：

```python
self.ydim = 4  # 例如添加熔池长度
```

并在 `symbolicModel` 中返回对应维度的结果。

### 切换到Type C或Type D校准

如果怀疑模型存在形式误差，可以使用：

```python
from ACBICI import discrepancyCalibrator  # Type C
from ACBICI import KOHCalibrator          # Type D

# Type C示例
theCalibrator = discrepancyCalibrator(model, name="typeC", kernel="matern52")
```

Type D (KOH) 是最完整的贝叶斯框架，能分离参数不确定度、模型差异和观测误差。

## 参考文献

- ACBICI文档: https://acbici.readthedocs.io
- ACBICI仓库: https://gitlab.com/schenkch/ACBICI
- emcee采样器: https://emcee.readthedocs.io

## 联系与支持

如有问题，请查看：
1. ACBICI示例: `ACBICI/examples/`
2. ACBICI文档（需本地编译）
3. 提交issue到ACBICI GitLab仓库

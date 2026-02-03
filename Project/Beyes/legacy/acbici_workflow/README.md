# ACBICI 校准工作流

本目录包含基于 ACBICI (A Calibration and Bayesian Inversion Code for Icepack) 框架的贝叶斯校准工作流的所有相关代码和文档。

## 目录结构

```
acbici_workflow/
├── README.md                      # 本文件
├── acbici_calibration.py          # 主校准脚本
├── acbici_model.py                # OpenFOAM 模型封装
├── generate_synthetic_data.py     # 合成数据生成脚本
├── docs/                          # 文档目录
│   ├── README_ACBICI.md          # ACBICI 使用说明
│   └── MIGRATION_GUIDE_ACBICI.md # 迁移指南
└── utils/                         # 工具脚本
    ├── plot_results_simple.py    # 简化版结果可视化
    ├── visualize_results.py      # 完整版结果可视化
    └── generate_plots.py         # 图表生成工具
```

## 快速开始

### 1. 生成合成数据

首先需要生成训练高斯过程代理模型所需的合成数据：

```bash
cd /home/cgh/LaserbeamFoam/Project/Beyes/acbici_workflow
python generate_synthetic_data.py --n-samples 20
```

默认参数：
- `--config ../config.yaml` - OpenFOAM 配置文件
- `--n-samples 20` - 采样点数量
- `--output ../data/synthetic_data.dat` - 输出文件路径

### 2. 运行贝叶斯校准

生成合成数据后，可以运行校准：

```bash
python acbici_calibration.py \
    --calibration-type both \
    --nsteps 10000 \
    --nwalkers 16
```

主要参数：
- `--config ../config.yaml` - OpenFOAM 配置文件
- `--experimental-data ../experimental_data.csv` - 实验数据
- `--synthetic-data ../data/synthetic_data.dat` - 合成数据
- `--calibration-type {known-error|unknown-error|both}` - 校准类型
- `--kernel {expo|matern32|matern52|ratquad}` - 高斯过程核函数
- `--nsteps 10000` - MCMC 步数
- `--nwalkers 16` - MCMC walker 数量

### 3. 查看结果

校准完成后，结果保存在输出目录中（默认在父目录下）：
- `meltpool_calibration_known_error.out/` - 已知误差校准结果
- `meltpool_calibration_unknown_error.out/` - 未知误差校准结果

每个结果目录包含：
- Corner 图 - 参数后验分布
- Trace 图 - MCMC 收敛性分析
- 统计报告文件

### 4. 迭代校准（推荐）

如果需要更精确的结果，可使用迭代贝叶斯校准：

```bash
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 3 \
    --sampling-strategy hybrid
```

迭代校准会：
- 自动在最优参数附近采样新点
- 运行新仿真更新数据集
- 逐步减小不确定性直到收敛
- 自动计算每轮的预测误差

详见 [**迭代校准使用指南**](docs/ITERATIVE_CALIBRATION_GUIDE.md)

### 5. 可视化预测误差演化

查看每轮校准后模型预测与实验数据的拟合改进：

```bash
python utils/plot_prediction_error_from_log.py \
    iterative_calibration_results/iteration_log.json \
    ../experimental_data.csv
```

生成的图表包括：
- 每个功率点的误差演化曲线
- MAE/RMSE 随迭代的下降趋势
- 误差热力图

详见 [**预测误差可视化指南**](docs/PREDICTION_ERROR_VISUALIZATION.md)

## 核心脚本说明

### acbici_calibration.py

主校准脚本，实现两种 Type B 贝叶斯校准：

1. **已知实验误差校准** - 当你知道实验测量的标准差时使用
2. **未知实验误差校准** - 使用 Half-Cauchy 先验估计实验误差

该脚本会：
- 加载实验数据和合成数据
- 构建高斯过程代理模型
- 运行 MCMC 采样获得参数后验分布
- 生成可视化结果和统计报告

### acbici_model.py

OpenFOAM 熔池仿真模型的封装，实现了 ACBICI 的 `ACBICImodel` 接口。

**模型接口：**
- 输入维度 (xdim=1): 激光功率 (W)
- 参数维度 (pdim=4): sigma, Marangoni_Constant, substrate_temp, absorptivity
- 输出维度 (ydim=3): 宽度 (μm), 深度 (μm), 面积 (μm²)

**校准参数说明：**
- **sigma** (σ): 表面张力系数 (N/m)
- **Marangoni_Constant** (γ): Marangoni 对流系数 (N/m·K)
- **substrate_temp** (T_s): 基板温度 (K)
- **absorptivity** (η): 激光能量吸收率系数 (0.5-3.0，无量纲)

### generate_synthetic_data.py

使用拉丁超立方采样 (LHS) 在参数空间中采样，运行 OpenFOAM 仿真生成合成数据集。

这些数据用于训练高斯过程代理模型，避免在 MCMC 采样过程中重复运行昂贵的 OpenFOAM 仿真。

### iterative_calibration.py

**多轮自适应贝叶斯校准脚本**，实现迭代优化流程：

```
初始数据 → GP+MCMC → 提取最优参数 → 新仿真 → 更新数据集 → 循环
```

**核心功能：**
- 自动在 MAP 估计附近采样新参数点
- 支持三种采样策略（map_only / posterior / hybrid）
- 智能收敛判断（参数变化率 + 后验标准差）
- 生成迭代历史日志和可视化

**相比单轮校准的优势：**
- 更高精度：聚焦于高概率区域
- 更低不确定性：自适应增加局部采样密度
- 更快收敛：比盲目 LHS 采样高效

## 文档

详细文档位于 `docs/` 目录：

- [**README_ACBICI.md**](docs/README_ACBICI.md) - ACBICI 框架完整使用指南
- [**MIGRATION_GUIDE_ACBICI.md**](docs/MIGRATION_GUIDE_ACBICI.md) - 从 bayes_opt.py 迁移到 ACBICI 的指南
- [**ITERATIVE_CALIBRATION_GUIDE.md**](docs/ITERATIVE_CALIBRATION_GUIDE.md) - 迭代校准详细使用指南 ⭐
- [**PREDICTION_ERROR_VISUALIZATION.md**](docs/PREDICTION_ERROR_VISUALIZATION.md) - 预测误差可视化指南

## 工具脚本

`utils/` 目录包含结果可视化和分析工具：

- **plot_results_simple.py** - 简化版结果可视化（自动调用）
- **visualize_results.py** - 完整版结果可视化
- **generate_plots.py** - 通用图表生成工具
- **plot_iteration_history.py** - 迭代校准历史可视化（生成参数收敛图、不确定性演化图等）
- **plot_prediction_error_from_log.py** - 预测误差演化可视化（从日志文件快速生成）⭐

## 依赖项

- Python 3.7+
- NumPy, Pandas
- PyDOE (拉丁超立方采样)
- emcee (MCMC 采样)
- scikit-learn (高斯过程)
- Matplotlib, Seaborn (可视化)
- ACBICI 框架（位于父目录的 `ACBICI/` 中）

## 注意事项

1. **路径设置**：所有脚本的默认路径都已配置为相对于父目录（`../`），因为配置文件和数据文件仍在父目录中
2. **工作目录**：建议在 `acbici_workflow/` 目录下运行脚本
3. **结果输出**：校准结果会保存在父目录下的 `.out/` 文件夹中

## 相关文件（父目录）

这些文件仍在父目录 `/home/cgh/LaserbeamFoam/Project/Beyes/` 中：

- `config.yaml` - OpenFOAM 配置文件
- `experimental_data.csv` - 实验数据
- `data/synthetic_data.dat` - 合成数据（生成后）
- `ACBICI/` - ACBICI 框架库
- OpenFOAM 仿真文件（0/, constant/, system/ 等）

## 许可证

基于 ACBICI 框架开发，遵循相应的开源协议。

# Beyes 熔池参数校准工具使用教程

本教程介绍如何使用 Beyes 程序进行激光熔池参数的贝叶斯优化校准。

---

## 一、环境准备

### 1.1 编译 LaserbeamFoam

首先确保已成功编译 LaserbeamFoam：

```bash
cd ~/LaserbeamFoam
./Allwmake
```

### 1.2 安装后处理工具的 Python 环境

后处理脚本需要特定的 Python 环境，请按以下步骤安装：

```bash
# 使用 conda 创建环境
conda env create -f $FOAM_USER_APPBIN/postProcessing/environment.yml
```

> **提示**：如果上述命令提示找不到文件，可以直接使用源码目录中的文件
> conda env create -f ~/LaserbeamFoam/applications/scripts/postProcessing/environment.yml

> 详细说明请参阅：`applications/scripts/postProcessing/README.md`

# 激活环境
conda activate meltpool-postproc

### 1.3 安装 PyMeltpoolCalib 依赖

进入 Beyes 目录，安装优化所需的 Python 包：

```bash
cd ~/LaserbeamFoam/Project/Beyes
pip install -r requirements.txt
```

---

## 二、配置参数

### 2.1 修改配置文件 `config.yaml`

根据你的环境修改 `config.yaml`：

```yaml
# OpenFOAM 环境相关
foam_runner: of2506              # OpenFOAM 启动命令（仅 HPC 模式需要，个人电脑可设为 null）
n_proc: 12                       # 并行计算核数（根据你的 CPU 调整）

# 优化参数
iters: 100                       # 总迭代次数
n_initial: 3                     # 初始随机采样数
kappa: 2.0                       # LCB 探索/开发系数

# 后处理设置
postproc_python: python          # Python 解释器
pvpython: pvpython               # ParaView Python 路径
```

### 2.2 准备实验数据 `experimental_data.csv`

实验数据文件格式如下：

```csv
power_W,depth_um,width_um,area_um2
140,78.95,93.56,4755.50
170,99.58,98.12,6791.33
200,126.02,119.97,12527.46
230,153.98,137.69,15313.96
260,187.40,134.32,18752.95
```

**字段说明**：
- `power_W`：激光功率 (W)
- `depth_um`：熔池深度 (μm)
- `width_um`：熔池宽度 (μm)
- `area_um2`：熔池截面积 (μm²)

### 2.3 调整材料与激光参数（可选）

如需修改材料属性，编辑 `constant/transportProperties`：

```
metal
{
    nu              8e-07;        // 运动粘度
    rho             6965.9;       // 密度
    Tsolidus        1658;         // 固相线温度
    Tliquidus       1723;         // 液相线温度
    LatentHeat      2.6e5;        // 潜热
    ...
}
```

激光参数在 `constant/LaserProperties` 中：

```
laserRadius     35e-6;            // 激光半径
absorptivity    2.56;             // 吸收率（优化目标之一）
```

---

## 三、运行优化

### 3.1 选择优化方法

程序支持三种优化方法：

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| `bayes` | 贝叶斯优化 | 推荐，平衡效率与精度 |
| `acbici` | MCMC 后验采样 | 需要不确定性量化 |
| `gradient` | 梯度优化 | 快速收敛，可能陷入局部最优 |

### 3.2 运行命令

**贝叶斯优化（推荐）**：

```bash
python main.py --method bayes --n-batches 50 --batch-size 5
```

**MCMC 后验采样**：

```bash
python main.py --method acbici --nsteps 500 --nwalkers 16
```

**梯度优化**：

```bash
python main.py --method gradient --n-directions 8 --max-nfev 300
```

### 3.3 常用参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | `config.yaml` |
| `--n-proc` | 并行核数 | 配置文件中的值 |
| `--verbose` | 详细输出 | 关闭 |
| `--n-initial-points` | 初始采样点数（贝叶斯） | 15 |
| `--n-batches` | 优化批次数（贝叶斯） | 50 |

---

## 四、查看结果

### 4.1 输出文件

运行完成后，结果保存在 `runs/` 目录下：

```
runs/
└── bayes_<timestamp>/
    ├── config.yaml          # 运行配置
    ├── result.json          # 优化结果
    └── plots/               # 可视化图表
        ├── comparison.png   # 预测 vs 实验对比
        └── predictions.png  # 预测结果
```

### 4.2 历史记录

优化过程记录在 `bayes_history.csv` 中，包含每次迭代的参数和误差。

### 4.3 熔池几何分析

后处理生成的熔池分析结果：

- `cross_sections_statistics.csv`：各截面的宽度、深度、高度、孔隙率
- `results_plots/`：熔池几何参数沿扫描方向的变化图

---

## 五、快速开始示例

```bash
# 1. 进入项目目录
cd ~/LaserbeamFoam/Project/Beyes

# 2. 激活 Python 环境
conda activate meltpool-postproc

# 3. 运行贝叶斯优化（使用 12 核并行）
python main.py --method bayes --n-proc 12 --n-batches 20

# 4. 查看结果
cat runs/bayes_*/result.json
```

---

## 六、常见问题

**Q: 提示找不到 `pvpython`？**

A: 确保 ParaView 已安装且 `pvpython` 在 PATH 中：
```bash
which pvpython
# 如果没有，添加到 PATH 或在 config.yaml 中指定完整路径
```

**Q: OpenFOAM 命令无法执行？**

A: 检查 `config.yaml` 中的 `foam_runner` 设置是否正确，确保能通过该命令启动 OpenFOAM 环境。

**Q: 如何从上次中断处继续？**

A: 使用 `--warmstart-csv` 参数加载历史数据：
```bash
python main.py --method bayes --warmstart-csv bayes_history.csv
```

---

## 七、参考资料

- 后处理工具文档：`applications/scripts/postProcessing/README.md`
- 完整工作流说明：`CALIBRATOR_WORKFLOW.md`
- 结果分析指南：`RESULTS_GUIDE.md`

# 贝叶斯优化统一脚本使用指南

## 概述

`bayes_opt_HPC.py` 是一个统一的贝叶斯优化脚本，支持两种运行模式：

- **个人电脑模式**（默认）：适用于本地开发和测试
- **HPC 模式**（`--hpc`）：适用于高性能计算集群，支持自定义运行器和环境配置

两种模式功能完全一致，包括：
- ✅ 贝叶斯优化参数搜索
- ✅ 多功率点模拟
- ✅ 自动续跑功能（中断后可继续）
- ✅ 结果归档和历史记录

## 快速开始

### 个人电脑模式

```bash
# 使用默认配置
python bayes_opt_HPC.py

# 使用自定义配置文件
python bayes_opt_HPC.py --config my_config.yaml

# 指定迭代次数和并行核数
python bayes_opt_HPC.py --iters 10 --n-proc 16
```

### HPC 模式

```bash
# 启用 HPC 模式
python bayes_opt_HPC.py --hpc

# HPC 模式 + 自定义配置
python bayes_opt_HPC.py --hpc --config hpc_config.yaml

# HPC 模式 + 命令行参数
python bayes_opt_HPC.py --hpc --foam-runner of2506 --postproc-runner of2506
```

## 两种模式的区别

| 特性 | 个人电脑模式 | HPC 模式 |
|------|-------------|----------|
| 命令执行方式 | `bash -lc` 直接执行 | 通过 `foam_runner` 包装器执行 |
| 默认后处理路径 | `/home/cgh/LaserbeamFoam/...` | 相对于项目根目录 |
| 环境变量支持 | 基础环境变量 | 支持 `POSTPROC_RUNNER`, `PVPYTHON` |
| 适用场景 | 本地开发、调试 | 容器化环境、作业调度系统 |

**功能一致性**：两种模式的核心功能（优化算法、续跑、归档等）完全相同。

## 配置文件示例

创建 `config.yaml`：

```yaml
# 运行模式（可选，也可用 --hpc 参数）
# hpc: true

# 基本设置
case_dir: "."
experimental_data: "experimental_data.csv"
iters: 5
n_initial: 3
n_proc: 12
seed: 42
kappa: 2.0

# OpenFOAM 环境
foam_bashrc: "/usr/lib/openfoam/openfoam2506/etc/bashrc"

# MPI 设置
mpirun_flags:
  - "--oversubscribe"

# HPC 模式专用（仅在 --hpc 时生效）
# foam_runner: "of2506"
# postproc_runner: "of2506"
# pvpython: "/path/to/pvpython"
```

## 命令行参数

### 基本参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--hpc` | 启用 HPC 模式 | `False` |
| `--config` | 配置文件路径 | `config.yaml` |
| `--case-dir` | 案例目录 | 脚本所在目录 |
| `--iters` | 迭代次数 | `5` |
| `--n-initial` | 初始随机样本数 | `3` |
| `--n-proc` | MPI 并行核数 | `12` |
| `--seed` | 随机种子 | `42` |
| `--kappa` | LCB 探索系数 | `2.0` |

### OpenFOAM 相关

| 参数 | 说明 |
|------|------|
| `--foam-bashrc` | OpenFOAM 环境脚本路径 |
| `--mpirun-flags` | mpirun 额外参数（如 `--oversubscribe`） |

### HPC 模式专用

| 参数 | 说明 |
|------|------|
| `--foam-runner` | 求解器外部命令包装器（如 `of2506`） |
| `--postproc-runner` | 后处理外部命令包装器 |
| `--pvpython` | ParaView Python 路径 |

### 后处理相关

| 参数 | 说明 |
|------|------|
| `--postproc-python` | Python 解释器 | `python` |
| `--postproc-script` | 后处理脚本路径 |
| `--experimental-data` | 实验数据 CSV | `experimental_data.csv` |

## 续跑功能

脚本会自动检测历史记录并支持续跑：

1. **完整迭代续跑**：读取 `bayes_history.csv`，从下一次迭代开始
2. **部分迭代续跑**：检测未完成的功率点，仅运行缺失的部分

```bash
# 中断后重新运行，会自动续跑
python bayes_opt_HPC.py
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `bayes_history.csv` | 优化历史记录（每次迭代的参数和目标值） |
| `bayes_power_metrics.csv` | 每个功率点的详细指标 |
| `bayes_best.json` | 最优参数和目标值 |
| `results_plots_archive/` | 归档的可视化结果 |

## 使用示例

### 示例 1：本地快速测试

```bash
python bayes_opt_HPC.py \
  --iters 3 \
  --n-proc 4 \
  --n-initial 2
```

### 示例 2：HPC 集群运行

```bash
python bayes_opt_HPC.py \
  --hpc \
  --foam-runner of2506 \
  --postproc-runner of2506 \
  --iters 20 \
  --n-proc 48 \
  --mpirun-flags --bind-to none
```

### 示例 3：使用配置文件

创建 `my_config.yaml`，然后运行：

```bash
python bayes_opt_HPC.py --config my_config.yaml
```

## 迁移指南

### 从旧版本迁移

如果你之前使用 `bayes_opt.py`（个人电脑版本）：

```bash
# 旧命令
python bayes_opt.py

# 新命令（等价，默认就是个人电脑模式）
python bayes_opt_HPC.py
```

如果你之前使用旧的 `bayes_opt_HPC.py`：

```bash
# 旧命令
python bayes_opt_HPC.py --foam-runner of2506

# 新命令（需添加 --hpc 参数）
python bayes_opt_HPC.py --hpc --foam-runner of2506
```

## 故障排查

### 问题：个人电脑模式找不到后处理脚本

检查默认路径是否正确：
```bash
ls /home/cgh/LaserbeamFoam/applications/scripts/postProcessing/characterise_meltpool.py
```

或手动指定：
```bash
python bayes_opt_HPC.py --postproc-script /path/to/characterise_meltpool.py
```

### 问题：HPC 模式命令执行失败

确保 `foam_runner` 可执行：
```bash
which of2506
```

检查日志输出中的 `[cmd]` 行，确认执行的命令正确。

## 最佳实践

1. **首次运行**：使用较少的迭代次数测试（如 `--iters 2`）
2. **配置文件**：复杂配置推荐使用 YAML 文件而非命令行参数
3. **结果备份**：定期备份 `bayes_history.csv` 和 `bayes_best.json`
4. **续跑测试**：在正式运行前测试续跑功能是否正常

## 参数搜索空间

当前优化的参数及范围：

| 参数 | 范围 | 单位 |
|------|------|------|
| `sigma` | 1.0 ~ 2.0 | - |
| `Marangoni_Constant` | -8e-4 ~ -4e-6 | - |
| `substrate_temp` | 300 ~ 800 | K |

功率点：140, 170, 200, 230, 260 W

目标函数：宽度、深度、面积的相对误差平方均值

# 批量可视化 OpenFOAM 熔池结果

## 概述

这些脚本可以自动化 ParaView 的可视化流程，批量处理 `runs/` 目录下的所有仿真结果。

## 前置要求

1. 安装 ParaView（包含 pvpython）
2. 确保 `pvpython` 在系统 PATH 中，或者知道其完整路径

检查 ParaView 安装：
```bash
which pvpython
# 或者
/path/to/paraview/bin/pvpython --version
```

## 使用方法

### 方法 1: 批量处理所有结果（推荐）

```bash
cd /home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/316L/SingleTrack

# 使用默认设置（可视化 meltHistory 字段）
pvpython batch_visualize_simple.py

# 指定不同的字段
pvpython batch_visualize_simple.py --field T

# 同时导出 VTK 文件
pvpython batch_visualize_simple.py --vtk

# 指定输出目录
pvpython batch_visualize_simple.py --output my_visualizations
```

### 方法 2: 处理单个案例

```bash
# 处理特定的案例
pvpython batch_visualize_simple.py --case runs/27/260W
```

### 方法 3: 使用完整版脚本

```bash
pvpython batch_visualize_meltpool.py
```

## 输出结果

脚本会在 `visualization_output/` 目录下创建以下结构：

```
visualization_output/
├── 1/
│   ├── 140W_meltHistory.png
│   ├── 200W_meltHistory.png
│   └── 260W_meltHistory.png
├── 2/
│   ├── 140W_meltHistory.png
│   └── ...
└── ...
```

## 可视化的字段

常用字段：
- `meltHistory`: 熔化历史（默认）
- `T`: 温度场
- `alpha.metal`: 金属体积分数
- `U`: 速度场

## 自定义脚本

如果需要更复杂的可视化（如切片、等值面等），可以修改脚本中的 `process_single_case` 函数。

## 故障排除

### 问题 1: pvpython 未找到

```bash
# 找到 ParaView 安装路径
find /usr -name pvpython 2>/dev/null
find /opt -name pvpython 2>/dev/null

# 使用完整路径运行
/path/to/paraview/bin/pvpython batch_visualize_simple.py
```

### 问题 2: 内存不足

如果案例太多，可以分批处理：

```bash
# 只处理特定 run ID
for run_id in 1 2 3 4 5; do
    pvpython batch_visualize_simple.py --case runs/$run_id/260W
done
```

### 问题 3: 缺少字段

确保时间目录（如 `0.00034/`）中包含要可视化的字段文件。

## 性能提示

- 批量处理大量案例时，建议在后台运行：
  ```bash
  nohup pvpython batch_visualize_simple.py > visualization.log 2>&1 &
  ```

- 如果只需要数据而不需要图像，使用 `--vtk` 选项导出 VTK 文件，然后在 ParaView GUI 中交互式查看。

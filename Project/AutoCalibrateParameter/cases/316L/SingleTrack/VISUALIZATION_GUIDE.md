# OpenFOAM 熔池可视化自动化指南

## 快速开始

### 最简单的方法（推荐）

```bash
cd /home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/316L/SingleTrack

# 批量处理所有结果
pvpython visualize_meltpool.py
```

这将：
1. 自动扫描 `runs/` 目录下的所有案例
2. 为每个案例创建必要的符号链接（指向 `constant/` 和 `system/`）
3. 应用 isoVolume 过滤器（threshold on alpha.metal > 0.5）
4. 可视化 meltHistory 字段
5. 保存高分辨率截图到 `visualization_output/` 目录

### 输出结构

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

## 其他可用脚本

### 1. visualize_meltpool.py（推荐）
- **最简单**，开箱即用
- 自动处理所有案例
- 自动创建符号链接

```bash
pvpython visualize_meltpool.py
```

### 2. batch_visualize_v2.py（高级选项）
- 支持命令行参数
- 可以选择不同的字段
- 可以导出 VTK 文件

```bash
# 默认使用
pvpython batch_visualize_v2.py

# 可视化温度场
pvpython batch_visualize_v2.py --field T

# 同时导出 VTK 文件
pvpython batch_visualize_v2.py --vtk

# 处理单个案例
pvpython batch_visualize_v2.py --case runs/27/260W
```

### 3. test_visualization.py（测试脚本）
- 用于测试 ParaView 设置是否正确
- 在单个案例上验证功能

```bash
pvpython test_visualization.py
```

## 自定义可视化

如果你需要修改可视化设置，编辑 `visualize_meltpool.py` 中的 `visualize_case` 函数：

```python
# 修改分辨率
view.ViewSize = [3840, 2160]  # 4K

# 修改背景颜色
view.Background = [0, 0, 0]  # 黑色背景

# 修改颜色映射
lut.ApplyPreset('Viridis', True)  # 使用 Viridis 配色

# 修改阈值范围
threshold.ThresholdRange = [0.3, 1.0]  # 显示更多区域
```

## 可视化其他字段

常用字段：
- `meltHistory` - 熔化历史（默认）
- `T` - 温度场
- `alpha.metal` - 金属体积分数
- `U` - 速度场
- `Qv` - 体积热源
- `liquidMetalCells` - 液态金属单元

修改脚本中的 `field` 参数即可。

## 故障排除

### 问题 1: pvpython 未找到

```bash
# 检查 pvpython 位置
which pvpython

# 如果未找到，使用完整路径
/home/cgh/miniconda3/bin/pvpython visualize_meltpool.py
```

### 问题 2: 无法读取 OpenFOAM 案例

确保：
1. `constant/` 和 `system/` 目录存在于主案例目录
2. 时间目录（如 `0.00034/`）包含所需字段文件
3. 脚本会自动创建符号链接

### 问题 3: 内存不足

如果案例太多，可以分批处理：

```bash
# 方法 1: 只处理特定 run
for run_id in 1 2 3 4 5; do
    for power in 140W 200W 260W; do
        pvpython batch_visualize_v2.py --case runs/$run_id/$power
    done
done

# 方法 2: 后台运行
nohup pvpython visualize_meltpool.py > visualization.log 2>&1 &
```

### 问题 4: 符号链接已存在

如果符号链接已经存在但指向错误位置：

```bash
# 删除所有符号链接
find runs/ -type l -name "constant" -delete
find runs/ -type l -name "system" -delete

# 重新运行脚本
pvpython visualize_meltpool.py
```

## 性能提示

1. **并行处理**：ParaView 脚本是串行的，但你可以手动并行运行多个实例：
   ```bash
   # 终端 1
   pvpython batch_visualize_v2.py --case runs/1/140W &
   # 终端 2
   pvpython batch_visualize_v2.py --case runs/2/140W &
   ```

2. **减少分辨率**：如果只是预览，可以降低分辨率：
   ```python
   view.ViewSize = [1280, 720]  # HD
   SaveScreenshot(..., ImageResolution=[1280, 720])
   ```

3. **只导出数据**：如果不需要图像，只导出 VTK：
   ```bash
   pvpython batch_visualize_v2.py --vtk
   ```

## 进阶：在 ParaView GUI 中查看

如果你想在 ParaView GUI 中交互式查看：

1. 打开 ParaView
2. File → Open → 选择 `runs/27/260W/260W.foam`
3. 确保符号链接已创建（运行一次脚本即可）
4. Apply → 选择 meltHistory 字段
5. 添加 Threshold 过滤器（alpha.metal > 0.5）

## 批量后处理工作流

完整的工作流程：

```bash
# 1. 运行所有仿真（假设已完成）

# 2. 批量可视化
pvpython visualize_meltpool.py

# 3. 查看结果
ls -lh visualization_output/

# 4. 如果需要，导出 VTK 用于进一步分析
pvpython batch_visualize_v2.py --vtk

# 5. 在 ParaView GUI 中交互式查看特定案例
paraview runs/27/260W/260W.foam
```

## 脚本说明

### visualize_meltpool.py
- **用途**：最简单的批量可视化脚本
- **特点**：无需参数，自动处理所有案例
- **输出**：PNG 截图

### batch_visualize_v2.py
- **用途**：高级批量可视化，支持自定义选项
- **特点**：命令行参数，灵活配置
- **输出**：PNG 截图 + 可选 VTK 文件

### test_visualization.py
- **用途**：测试 ParaView 环境和单个案例
- **特点**：诊断工具，验证设置
- **输出**：终端输出，无文件生成

## 联系与支持

如果遇到问题：
1. 检查 ParaView 版本：`pvpython --version`
2. 查看错误日志
3. 确认 OpenFOAM 案例结构正确

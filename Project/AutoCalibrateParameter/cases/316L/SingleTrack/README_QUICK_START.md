# 快速开始：批量可视化 OpenFOAM 熔池结果

## ✅ 已验证可用！

脚本已在你的系统上测试通过，成功处理了 84 个案例。

## 🚀 一键运行

```bash
cd /home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/316L/SingleTrack

# 批量处理所有结果
pvpython visualize_meltpool.py
```

## 📊 输出结果

脚本会自动：
1. ✓ 扫描 `runs/` 目录下的所有案例（84 个）
2. ✓ 为每个案例创建符号链接到 `constant/` 和 `system/`
3. ✓ 应用 isoVolume 过滤器（threshold: alpha.metal > 0.5）
4. ✓ 可视化 meltHistory 字段
5. ✓ 保存高分辨率截图（1920x1080）

输出位置：
```
visualization_output/
├── 1/
│   ├── 140W_meltHistory.png  (139 KB)
│   ├── 200W_meltHistory.png  (144 KB)
│   └── 260W_meltHistory.png  (144 KB)
├── 2/
│   └── ...
└── 30/
    └── ...
```

## ⚡ 处理时间

- 每个案例约 2-3 秒
- 84 个案例总共约 3-5 分钟

## 🎨 可视化设置

当前配置：
- **字段**: meltHistory
- **过滤器**: alpha.metal > 0.5（只显示金属区域）
- **颜色映射**: Rainbow Desaturated
- **分辨率**: 1920x1080
- **背景**: 白色

## 📝 自定义选项

### 修改可视化字段

编辑 `visualize_meltpool.py`，修改第 95 行：

```python
# 可选字段：
# - meltHistory (默认)
# - T (温度)
# - alpha.metal (金属体积分数)
# - U (速度)
# - Qv (体积热源)

if visualize_case(case['path'], output_file, field='T'):  # 改为温度场
```

### 修改分辨率

编辑第 60 行：

```python
view.ViewSize = [3840, 2160]  # 4K
# 或
view.ViewSize = [1280, 720]   # HD（更快）
```

### 修改颜色映射

编辑第 68 行：

```python
lut.ApplyPreset('Viridis', True)      # Viridis
lut.ApplyPreset('Jet', True)          # Jet
lut.ApplyPreset('Cool to Warm', True) # Cool to Warm
```

## 🔧 高级用法

### 使用高级脚本（支持命令行参数）

```bash
# 可视化温度场
pvpython batch_visualize_v2.py --field T

# 同时导出 VTK 文件（用于进一步分析）
pvpython batch_visualize_v2.py --vtk

# 只处理单个案例
pvpython batch_visualize_v2.py --case runs/27/260W

# 指定输出目录
pvpython batch_visualize_v2.py --output my_results
```

### 并行处理（加速）

如果你有多个 CPU 核心，可以并行运行：

```bash
# 终端 1
pvpython batch_visualize_v2.py --case runs/1/140W &

# 终端 2
pvpython batch_visualize_v2.py --case runs/2/140W &

# 终端 3
pvpython batch_visualize_v2.py --case runs/3/140W &
```

## 📂 文件说明

| 文件 | 用途 | 推荐度 |
|------|------|--------|
| `visualize_meltpool.py` | **最简单**，一键批量处理 | ⭐⭐⭐⭐⭐ |
| `batch_visualize_v2.py` | 高级选项，命令行参数 | ⭐⭐⭐⭐ |
| `batch_visualize_simple.py` | 简化版，支持参数 | ⭐⭐⭐ |
| `test_visualization.py` | 测试脚本，诊断问题 | ⭐⭐ |
| `VISUALIZATION_GUIDE.md` | 详细文档 | 📖 |

## ✅ 验证结果

查看生成的图像：

```bash
# 列出所有生成的图像
find visualization_output/ -name "*.png" | wc -l

# 查看特定案例
eog visualization_output/1/140W_meltHistory.png  # Linux
# 或
open visualization_output/1/140W_meltHistory.png  # macOS
```

## 🐛 故障排除

### 问题：脚本运行很慢

**解决方案**：降低分辨率或并行处理

```python
# 在 visualize_meltpool.py 中修改
view.ViewSize = [1280, 720]  # 从 1920x1080 降低到 720p
```

### 问题：内存不足

**解决方案**：分批处理

```bash
# 只处理前 10 个 run
for i in {1..10}; do
    pvpython batch_visualize_v2.py --case runs/$i/140W
done
```

### 问题：某些案例失败

**解决方案**：检查日志，确保时间目录和字段文件存在

```bash
# 检查特定案例
ls runs/27/260W/0.00034/meltHistory
ls runs/27/260W/constant
ls runs/27/260W/system
```

## 🎯 下一步

1. **查看结果**：浏览 `visualization_output/` 目录
2. **导出数据**：使用 `--vtk` 选项导出 VTK 文件用于进一步分析
3. **交互式查看**：在 ParaView GUI 中打开 `.foam` 文件进行交互式探索

```bash
# 在 ParaView GUI 中打开
paraview runs/27/260W/260W.foam
```

## 📞 需要帮助？

- 查看详细文档：`VISUALIZATION_GUIDE.md`
- 测试环境：`pvpython test_visualization.py`
- 检查 ParaView 版本：`pvpython --version`

---

**提示**：脚本会自动创建符号链接，不会修改原始数据。所有输出都保存在 `visualization_output/` 目录中。

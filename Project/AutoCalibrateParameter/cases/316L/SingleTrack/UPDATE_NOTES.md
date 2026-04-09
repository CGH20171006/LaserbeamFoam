# 可视化脚本更新说明

## ✅ 已实现的功能

脚本已按照你的要求进行了以下修改：

### 1. ✅ 白色背景
```python
view.Background = [1, 1, 1]  # 白色背景
```

### 2. ✅ meltHistory 显示范围 0-1
```python
lut.RescaleTransferFunction(0.0, 1.0)  # 设置颜色映射范围为 0-1
```

### 3. ✅ Y 轴切片（Y=0.0004）
```python
slice_filter = Slice(Input=threshold)
slice_filter.SliceType = 'Plane'
slice_filter.SliceType.Origin = [0.0, 0.0004, 0.0]
slice_filter.SliceType.Normal = [0.0, 1.0, 0.0]  # Y 轴法向
```

### 4. ✅ 显示 XZ 平面
```python
view.CameraPosition = [0.0, 0.01, 0.0]  # 相机位置（从 +Y 方向看）
view.CameraFocalPoint = [0.0, 0.0004, 0.0]  # 焦点在切片上
view.CameraViewUp = [0.0, 0.0, 1.0]  # Z 轴向上
```

## 📊 测试结果

✅ 脚本已测试通过
- 成功生成切片可视化
- 文件大小约 29 KB（比之前的 140 KB 小，因为是 2D 切片）
- 输出格式：PNG 1920x1080

## 🚀 使用方法

```bash
cd /home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/316L/SingleTrack

# 批量处理所有案例（使用新的切片可视化）
pvpython visualize_meltpool.py
```

## 📁 输出示例

```
visualization_output/
├── 1/
│   ├── 140W_meltHistory.png  (29 KB) - Y=0.0004 切片，XZ 平面视图
│   ├── 200W_meltHistory.png  (29 KB)
│   └── 260W_meltHistory.png  (29 KB)
└── ...
```

## 🎨 可视化特性

- **视图**: XZ 平面（从 Y 轴正方向看）
- **切片位置**: Y = 0.0004 m（中部区域）
- **颜色范围**: meltHistory 0-1
- **背景**: 白色
- **分辨率**: 1920x1080
- **过滤**: 只显示金属区域（alpha.metal > 0.5）

## 🔧 自定义选项

### 修改切片位置

编辑 `visualize_meltpool.py` 第 68 行：

```python
slice_filter.SliceType.Origin = [0.0, 0.0005, 0.0]  # 改为 Y=0.0005
```

### 修改颜色范围

编辑第 80 行：

```python
lut.RescaleTransferFunction(0.0, 2.0)  # 改为 0-2 范围
```

### 修改相机角度

编辑第 84-86 行：

```python
# 从上方看（俯视图）
view.CameraPosition = [0.0, 0.0004, 0.01]
view.CameraFocalPoint = [0.0, 0.0004, 0.0]
view.CameraViewUp = [0.0, 1.0, 0.0]
```

## 📝 技术细节

### 处理流程

1. 读取 OpenFOAM 案例
2. 应用 Threshold 过滤器（alpha.metal > 0.5）
3. 应用 Slice 过滤器（Y=0.0004 平面）
4. 设置颜色映射（meltHistory 0-1）
5. 设置相机视角（XZ 平面）
6. 保存截图

### 与之前版本的区别

| 特性 | 旧版本 | 新版本 |
|------|--------|--------|
| 视图类型 | 3D 体积 | 2D 切片 |
| 文件大小 | ~140 KB | ~29 KB |
| 显示平面 | 3D | XZ 平面 |
| 切片位置 | 无 | Y=0.0004 |
| 颜色范围 | 自动 | 固定 0-1 |

## ⚡ 性能

- 处理速度: 约 2-3 秒/案例（与之前相同）
- 文件更小，加载更快
- 更适合批量对比分析

## 🎯 下一步

如果需要其他修改：
- 不同的切片位置
- 多个切片（X、Y、Z 方向）
- 不同的颜色映射
- 添加网格线或标注

请告诉我，我可以继续修改脚本！

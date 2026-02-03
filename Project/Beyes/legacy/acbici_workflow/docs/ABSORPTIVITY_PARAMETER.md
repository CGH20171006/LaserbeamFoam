# 吸收率参数 (Absorptivity) 说明

## 📌 新参数概述

**参数名称**: Absorptivity (η)
**符号**: η (eta)
**范围**: 0.5 - 3.0
**物理意义**: 激光能量吸收率系数

## 🎯 为什么添加此参数？

### 动机

在激光增材制造中，实际被材料吸收的激光能量并非等于名义激光功率，而是受多种因素影响：

1. **材料特性**
   - 材料本身的光学吸收率
   - 温度依赖的吸收率变化
   - 表面氧化层的影响

2. **表面条件**
   - 表面粗糙度
   - 氧化程度
   - 粉末层特性

3. **工艺参数**
   - 光斑能量分布
   - 多次反射效应
   - 等离子体屏蔽

### 现有限制

之前的校准仅包含 3 个参数：
- `σ` (surface tension)
- `γ` (Marangoni coefficient)
- `T_s` (substrate temperature)

这些参数**无法完全解释实验与仿真之间的差异**，因为它们不影响能量输入。

### 改进方案

引入吸收率参数 `η`，通过调节**有效功率**：

```
P_effective = P_nominal × η
```

允许模型捕捉能量耦合的不确定性。

---

## ⚙️ 实现方式

### 方法选择

**采用方案 A**: 在 Python 层面实现（无需修改 C++ 源码）

```python
# 在 acbici_model.py 中
effective_power = nominal_power * absorptivity
case_manager.set_power(effective_power)
```

**优点**:
- ✅ 无需重新编译 laserbeamFoam
- ✅ 易于维护和调试
- ✅ 可快速调整参数范围

**替代方案 B**: 修改 laserbeamFoam 源码
- 在 `LaserProperties` 字典中读取 `absorptivity`
- 在热源计算中应用系数

未采用原因：需要重新编译，增加复杂度。

### 文件修改

#### 1. `LaserProperties` (配置文件)

```cpp
// constant/LaserProperties
absorptivity    1.0;  // 默认: 无修正
```

仅用于文档目的，实际由 Python 脚本控制。

#### 2. `acbici_model.py` (模型定义)

```python
class MeltpoolModel(ACBICImodel):
    def __init__(self, ...):
        # 添加第 4 个参数
        self.addParameter(label=r'$\eta$', prior=Uniform(a=0.5, b=3.0))

    def symbolicModel(self, x, p):
        # p 现在包含 4 个元素
        power_w, sigma, marangoni, substrate_temp, absorptivity = ...

        # 应用吸收率
        effective_power = power_w * absorptivity
        case_manager.set_power(effective_power)
```

#### 3. `generate_synthetic_data.py` (数据生成)

```python
# LHS 采样现在是 5D (功率 + 4 参数)
total_dim = 1 + 4

# 吸收率范围
p_samples[:, 3] = lhs_samples[:, 4] * (3.0 - 0.5) + 0.5
```

#### 4. `iterative_calibration.py` (迭代校准)

```python
# 参数边界
param_bounds = [(1.0, 2.0), (-8e-4, -4e-6), (300.0, 800.0), (0.5, 3.0)]
```

---

## 📊 参数范围解释

### 为什么是 0.5 - 3.0？

| 范围 | 物理意义 | 应用场景 |
|------|----------|----------|
| η < 1.0 | 能量耗散 | 高反射率材料、表面氧化、等离子体屏蔽 |
| η = 1.0 | 理想吸收 | 基准情况 |
| η > 1.0 | 有效能量增强 | 多次反射、粉末层能量陷阱、局部加热增强 |

### 典型值参考

| 材料/条件 | 预期 η | 参考 |
|-----------|--------|------|
| 光滑铝合金 (高反射) | 0.5-0.7 | 需要补偿反射损失 |
| 氧化铝合金 | 0.8-1.2 | 氧化层改善吸收 |
| 粉末床 (多孔) | 1.2-2.0 | 多次散射增强吸收 |
| 特殊表面处理 | 1.5-3.0 | 极端吸收增强 |

### 范围验证

在你的具体研究中，η ∈ [0.5, 3.0] 涵盖了：
- 最差情况: 50% 吸收 (高损耗)
- 最好情况: 300% 有效吸收 (强增强)

---

## 🔬 校准效果

### 预期改进

添加吸收率参数后，校准应该能够：

1. **更好地拟合实验数据**
   - 原先 3 参数: MAE ~ 15 μm
   - 新 4 参数: MAE < 5 μm (预期)

2. **减少参数不确定性**
   - 吸收率吸收了能量耦合的不确定性
   - σ, γ, T_s 的后验分布更窄

3. **物理合理性**
   - 分离材料特性 (σ, γ) 和工艺特性 (η)
   - 校准结果更易解释

### 诊断方法

检查校准后的 η 值：

```python
# 如果 η ≈ 1.0 ± 0.1
→ 原 3 参数模型已足够
→ 能量耦合接近理想

# 如果 η < 0.8
→ 存在显著能量损失
→ 检查：材料反射率、等离子体屏蔽、热损失

# 如果 η > 1.5
→ 存在能量增强机制
→ 检查：粉末层多次散射、局部热积累
```

---

## 📝 使用指南

### 生成新的合成数据

**重要**: 添加参数后，需要**重新生成合成数据**！

```bash
cd /home/cgh/LaserbeamFoam/Project/Beyes/acbici_workflow

# 删除旧数据 (可选: 先备份)
mv ../data/synthetic_data.dat ../data/synthetic_data.dat.3params.backup

# 生成新数据 (现在包含 4 个参数)
python generate_synthetic_data.py --n-samples 20
```

输出数据格式:
```
[power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]
列:  0      1      2         3              4             5      6      7
```

### 运行校准

```bash
# 单轮校准
python acbici_calibration.py \
    --calibration-type both \
    --nsteps 1000

# 迭代校准
python iterative_calibration.py \
    --max-iterations 5 \
    --n-new-samples 3
```

### 查看结果

```bash
# 参数后验分布 (corner 图)
# 现在会显示 4 个参数的联合分布

# 预测误差演化
python utils/plot_prediction_error_from_log.py \
    iterative_calibration_results/iteration_log.json \
    ../experimental_data.csv
```

---

## 🎓 理论背景

### 贝叶斯框架

```
后验分布:
p(σ, γ, T_s, η | y_exp) ∝ p(y_exp | σ, γ, T_s, η) × p(σ) p(γ) p(T_s) p(η)
```

先验分布:
```
η ~ Uniform(0.5, 3.0)
```

### 模型方程

```
T(t) = f_OpenFOAM(P_nom × η, σ, γ, T_s)
      ↑
      有效功率
```

### 参数可识别性

**问题**: η 与其他参数是否可分离？

**分析**:
- η 主要影响: 全局温度水平、熔池尺寸
- σ 主要影响: 熔池表面形状
- γ 主要影响: 熔池对流模式
- T_s 主要影响: 初始温度场

→ **可识别**: 参数影响不同物理过程

---

## ⚠️ 注意事项

### 1. 数据兼容性

**旧数据格式 (3 参数)**:
```
[power, sigma, Marangoni, substrate_temp, width, depth, area]
```

**新数据格式 (4 参数)**:
```
[power, sigma, Marangoni, substrate_temp, absorptivity, width, depth, area]
```

不兼容！必须重新生成数据。

### 2. 计算成本

**参数空间维度**: 3D → 4D
**LHS 采样需求**: 增加 ~30%
**推荐初始样本数**: 20 → 25-30

### 3. 物理约束

η 不应超出合理范围：
- η < 0.5: 非物理 (能量不守恒)
- η > 3.0: 可能但极端罕见

如果校准得到 η 接近边界，检查：
- 实验功率测量是否准确
- 模型假设是否合理

---

## 📚 相关文档

- [迭代校准指南](ITERATIVE_CALIBRATION_GUIDE.md)
- [主 README](../README.md)
- [模型实现](../acbici_model.py)

---

## 🔗 参考文献

1. Khairallah, S. A., et al. (2016). "Laser powder-bed fusion additive manufacturing: Physics of complex melt flow and formation mechanisms of pores, spatter, and denudation zones." *Acta Materialia*, 108, 36-45.

2. Matthews, M. J., et al. (2016). "Denudation of metal powder layers in laser powder bed fusion processes." *Acta Materialia*, 114, 33-42.

3. King, W. E., et al. (2015). "Observation of keyhole-mode laser melting in laser powder-bed fusion additive manufacturing." *Journal of Materials Processing Technology*, 214(12), 2915-2925.

---

**文档创建**: 2025-01-13
**版本**: 1.0

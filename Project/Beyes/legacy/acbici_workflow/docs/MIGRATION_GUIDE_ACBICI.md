# 迁移指南：从 bayes_opt.py 到 ACBICI

本文档说明如何从旧的贝叶斯优化系统迁移到新的ACBICI贝叶斯校准框架。

## 为什么要迁移？

### 旧系统（bayes_opt.py）的局限性

1. **仅提供点估计**：只给出最优参数值，无不确定度信息
2. **非标准方法**：自定义的简化高斯过程实现
3. **缺乏可解释性**：无法量化参数的置信区间
4. **不适合科学发表**：缺少完整的UQ分析

### 新系统（ACBICI）的优势

1. **完整的后验分布**：不仅有最优值，还有概率分布
2. **行业标准框架**：基于emcee的MCMC采样
3. **不确定度量化**：95%置信区间、方差等
4. **科学严谨性**：适合论文发表的贝叶斯推断
5. **灵活的模型**：支持模型差异处理（Type C/D）

## 概念对比

| 概念 | bayes_opt.py | ACBICI Type B |
|------|--------------|---------------|
| 目标 | 找到最优参数 | 估计参数分布 |
| 方法 | 贝叶斯优化 | 贝叶斯推断 |
| 输出 | 单个最优点 | 后验样本 |
| 探索策略 | LCB采集函数 | MCMC采样 |
| 代理模型 | 简单RBF核GP | 多种核函数GP |
| 不确定度 | 无 | 完整UQ |

## 文件对照表

| 功能 | 旧文件 | 新文件 |
|------|--------|--------|
| 主脚本 | bayes_opt.py | acbici_calibration.py |
| 模型定义 | bayes_opt.py中 | acbici_model.py |
| 数据生成 | 无 | generate_synthetic_data.py |
| 配置 | config.yaml | config.yaml (保持不变) |
| 实验数据 | experimental_data.csv | experimental_data.csv (保持不变) |
| 历史记录 | bayes_history.csv | posterior_samples.csv |
| 结果 | bayes_best.json | statistics.txt + corner图 |

## 代码迁移步骤

### 1. 保留原有配置

**无需修改的文件**：
- `config.yaml` - OpenFOAM运行配置
- `experimental_data.csv` - 实验数据

这两个文件可以直接在新系统中使用。

### 2. 理解参数定义的变化

**旧代码**（bayes_opt.py）：
```python
PARAM_BOUNDS = {
    "sigma": (1.0, 2.0),
    "Marangoni_Constant": (-8e-4, -4e-6),
    "substrate_temp": (300.0, 800.0),
}
```

**新代码**（acbici_model.py）：
```python
class MeltpoolModel(ACBICImodel):
    def __init__(self):
        self.addParameter(label=r'$\sigma$', prior=Uniform(a=1.0, b=2.0))
        self.addParameter(label=r'$\gamma$', prior=Uniform(a=-8e-4, b=-4e-6))
        self.addParameter(label=r'$T_s$', prior=Uniform(a=300.0, b=800.0))
```

**差异**：
- 旧系统使用字典定义范围
- 新系统使用先验分布对象（更灵活，可用Normal、LogNormal等）

### 3. 理解模型评估的变化

**旧代码**（bayes_opt.py）：
```python
# SimpleBO自动在参数空间采样
bo = SimpleBO(bounds=PARAM_BOUNDS)
params = bo.suggest()  # 获得下一个候选点
```

**新代码**（acbici_model.py）：
```python
# 显式定义模型
class MeltpoolModel(ACBICImodel):
    def symbolicModel(self, x, p):
        # x: 输入（功率）
        # p: 参数（sigma, Marangoni, substrate_temp）
        # 运行OpenFOAM仿真
        results = self.case_manager.run_and_postprocess(x, p)
        return results
```

**差异**：
- 旧系统隐式调用仿真
- 新系统显式定义前向模型接口

### 4. 理解输出格式的变化

**旧系统输出**（bayes_history.csv）：
```csv
sigma,Marangoni_Constant,substrate_temp,width_um_140W,depth_um_140W,...,objective
1.234,-5.6e-4,500.0,95.2,80.1,...,0.0234
```

**新系统输出**（posterior_samples.csv）：
```csv
sigma,Marangoni_Constant,substrate_temp,log_posterior
1.245,-5.4e-4,498.2,-123.45
1.238,-5.5e-4,502.1,-123.67
...（数千个后验样本）
```

**差异**：
- 旧系统：每行一次迭代，记录目标函数值
- 新系统：每行一个后验样本，记录对数后验概率

### 5. 理解结果解读的变化

**旧系统**：
```json
// bayes_best.json
{
  "best_objective": 0.0234,
  "best_params": {
    "sigma": 1.234,
    "Marangoni_Constant": -5.6e-4,
    "substrate_temp": 500.0
  }
}
```

**新系统**：
```
// statistics.txt
Parameter     Mean       Median     MAP        Variance    95% Credible
sigma         1.245      1.243      1.240      0.0012      [1.21, 1.28]
Marangoni    -5.5e-4    -5.4e-4    -5.6e-4     2.3e-8     [-6.1e-4, -4.9e-4]
substrate_T   501.2      500.8      498.5      25.6       [490, 512]
```

**差异**：
- 旧系统：单个最优值
- 新系统：均值、中位数、MAP、置信区间等完整统计信息

## 实际迁移示例

### 场景：已有旧系统的运行结果

假设您已经运行过 `bayes_opt.py`，有以下文件：
- `bayes_history.csv` - 22次迭代的历史记录
- `bayes_best.json` - 最优参数

**迁移步骤**：

#### 步骤 1: 安装ACBICI

```bash
cd ACBICI
pip install -e .
```

#### 步骤 2: 生成合成数据

```bash
# 使用20个样本（推荐）
python generate_synthetic_data.py --n-samples 20

# 或快速测试5个样本
python generate_synthetic_data.py --n-samples 5
```

**注意**：这是Type B校准必需的步骤，旧系统没有合成数据概念。

#### 步骤 3: 运行ACBICI校准

```bash
# 基础运行
python acbici_calibration.py

# 或使用快速开始脚本
./quick_start.sh
```

#### 步骤 4: 对比结果

**旧系统最优值**（从 bayes_best.json）：
```
sigma = 1.234
Marangoni_Constant = -5.6e-4
substrate_temp = 500.0
```

**新系统后验估计**（从 statistics.txt）：
```
sigma = 1.245 ± 0.035  (95% CI: [1.21, 1.28])
Marangoni = -5.5e-4 ± 1.5e-5  (95% CI: [-6.1e-4, -4.9e-4])
substrate_temp = 501.2 ± 5.1  (95% CI: [490, 512])
```

**解读**：
- 新系统的均值与旧系统的最优值应该接近
- 置信区间给出了参数的不确定度范围
- 如果置信区间很宽，说明数据不足以精确估计该参数

## 常见问题

### Q1: 我能直接使用旧的 bayes_history.csv 吗？

**A**: 不能直接使用。两个系统的数据格式不同：
- 旧系统：迭代优化历史
- 新系统：需要合成数据（参数空间的LHS采样）

但是，旧的历史记录可以帮助：
1. 确定合成数据的采样范围
2. 作为先验分布的参考
3. 验证新系统结果的合理性

### Q2: 新系统运行时间更长吗？

**A**: 取决于阶段：
- **生成合成数据**：需要额外时间（20个样本 ≈ 旧系统20次迭代）
- **MCMC采样**：可能更快，因为使用GP代理模型而非实际仿真

**总体**：初次运行需要更长时间，但得到更丰富的信息。

### Q3: 如何选择合成数据的样本数？

**A**: 建议：
- **快速测试**：5-10个样本
- **一般应用**：20-30个样本
- **高精度**：50+个样本

样本数越多，GP代理模型越准确，但生成时间越长。

### Q4: 旧系统的目标函数在新系统中如何体现？

**A**:
- **旧系统**：最小化相对误差平方和
  ```python
  objective = mean((width_err² + depth_err² + area_err²))
  ```

- **新系统**：最大化后验概率（包含似然函数）
  ```
  posterior ∝ likelihood × prior
  likelihood = P(data | params)
  ```

新系统隐式包含了误差最小化（通过似然函数），但更科学严谨。

### Q5: 如何将旧系统的最优值作为新系统的先验？

编辑 `acbici_model.py`：

```python
from ACBICI import Normal

# 使用旧系统的最优值作为先验均值
self.addParameter(
    label=r'$\sigma$',
    prior=Normal(mu=1.234, sigma=0.1)  # mu来自bayes_best.json
)
```

这种"信息先验"可以加速MCMC收敛。

## 保留旧系统的建议

建议**不要删除**旧系统文件，原因：

1. **对比验证**：新旧结果对比可验证正确性
2. **快速原型**：某些情况下优化比推断更快
3. **备份方案**：如果新系统遇到问题，可回退

可以将旧文件重命名：
```bash
mv bayes_opt.py bayes_opt_legacy.py
mv bayes_opt_ACBICI.py bayes_opt_ACBICI_legacy.py
```

## 混合使用策略

您可以结合两个系统的优势：

1. **初步探索**：用旧系统快速找到参数大致范围
2. **精细校准**：用新系统获得完整的不确定度量化

工作流程：
```bash
# 第1步：快速优化（旧系统）
python bayes_opt_legacy.py --iters 10

# 第2步：分析结果，调整先验分布（根据bayes_best.json）

# 第3步：完整贝叶斯校准（新系统）
./quick_start.sh
```

## 总结

| 方面 | 建议 |
|------|------|
| **配置文件** | 直接复用 config.yaml |
| **实验数据** | 直接复用 experimental_data.csv |
| **旧结果** | 保留作为对比参考 |
| **学习曲线** | 先运行快速测试（./quick_start.sh --test） |
| **生产使用** | 生成足够合成数据（20+样本） |
| **结果验证** | 对比新旧系统的参数估计值 |

迁移到ACBICI需要一定学习成本，但带来的科学严谨性和不确定度量化能力值得投入。建议先在测试模式下熟悉流程，再进行完整校准。

# ACBICI Calibrator 运行流程详解

本文档详细讲解ACBICI Type B (expensiveCalibrator) 的完整运行流程，从初始化到MCMC采样再到结果输出。

## 目录

1. [整体流程概览](#整体流程概览)
2. [初始化阶段](#初始化阶段)
3. [数据准备阶段](#数据准备阶段)
4. [校准核心阶段](#校准核心阶段)
5. [MCMC采样细节](#mcmc采样细节)
6. [结果输出阶段](#结果输出阶段)
7. [数学原理](#数学原理)

---

## 整体流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACBICI Type B 校准流程                          │
└─────────────────────────────────────────────────────────────────┘

1. 初始化 (Initialization)
   ├─ 创建模型实例 (MeltpoolModel)
   ├─ 定义参数先验分布
   ├─ 创建校准器 (expensiveCalibrator)
   └─ 选择GP核函数 (MultiTask for ydim>1)

2. 数据准备 (Data Preparation)
   ├─ 加载实验数据 (storeExperimentalData)
   │   └─ xExp, yExp: 输入和观测值
   ├─ 生成/加载合成数据 (storeSyntheticData)
   │   └─ xSyn, tSyn, ySyn: 输入、参数、输出
   └─ 设置误差模型
       ├─ 已知误差: setExperimentalSTDValue(σ)
       └─ 未知误差: setExperimentalSTDPrior(HalfCauchy)

3. 校准执行 (Calibration)
   ├─ calibrate() 入口
   ├─ 设置超参数先验 (setDefaultHyperparametersPriors)
   ├─ 打印配置信息 (printInfo)
   └─ 调用 genericCalibration()

4. MCMC采样 (MCMC Sampling)
   ├─ 初始化emcee采样器 (EnsembleSampler)
   ├─ 随机初始化walker (randomize)
   ├─ 循环采样 (run_mcmc)
   │   ├─ 对每个walker计算 logPosterior
   │   │   ├─ logPrior: 先验概率
   │   │   └─ logLikelihood_vect: 似然函数
   │   │       └─ 构建协方差矩阵 Σ (GP + 误差)
   │   └─ Metropolis-Hastings更新
   └─ 燃烧期后收集样本

5. 结果保存 (Results)
   ├─ samples.npy: 后验样本
   ├─ logprob.npy: 对数后验概率
   ├─ logprior.npy: 对数先验概率
   └─ acbici.log: 统计摘要

6. 可视化 (Visualization)
   ├─ plot() 调用
   ├─ 生成trace图、corner图等
   └─ 或使用 plot_results_simple.py
```

---

## 初始化阶段

### 1.1 创建模型 ([acbici_model.py:253-276](acbici_model.py:253-276))

```python
# 用户代码
model = MeltpoolModel(config_path="config.yaml")
```

**内部执行**:

```python
class MeltpoolModel(ACBICImodel):
    def __init__(self, config_path):
        # 1. 设置输入输出维度
        self.xdim = 1  # 激光功率
        self.ydim = 3  # 宽度、深度、面积

        # 2. 添加参数及先验分布
        self.addParameter(label=r'$\sigma$',
                         prior=Uniform(a=1.0, b=2.0))
        self.addParameter(label=r'$\gamma$',
                         prior=Uniform(a=-8e-4, b=-4e-6))
        self.addParameter(label=r'$T_s$',
                         prior=Uniform(a=300.0, b=800.0))

        # 3. 初始化OpenFOAM案例管理器
        self.case_manager = OpenFOAMCaseManager(...)
```

**关键数据结构**:
- `self.parameters`: 参数列表 [σ, γ, T_s]
- `self.priors`: 对应的先验分布对象
- `self.xdim`, `self.ydim`: 输入输出维度

### 1.2 创建校准器 ([calibrator.py:1800-1851](ACBICI/src/ACBICI/calibrator.py:1800-1851))

```python
# 用户代码
theCalibrator = expensiveCalibrator(model, name="meltpool", kernel="matern32")
```

**内部执行**:

```python
def __init__(self, aModel, *, name="acbiciB", kernel="sqexp"):
    self.model = aModel
    ydim = self.model.getOutputDimension()

    # 1. 选择核函数
    if ydim > 1:
        self.kernel = MultiTask()  # 多输出任务核
    elif kernel == "matern32":
        self.kernel = Matern32()
    # ...

    # 2. 创建输出目录
    self.odirectory = self.name + ".out"
    os.makedirs(self.odirectory, exist_ok=True)

    # 3. 添加GP超参数 (后面会自动设置先验)
    self.addHyperparameter(r'$\beta_x$',   None)  # 输入空间长度尺度
    self.addHyperparameter(r'$\beta_t$',   None)  # 参数空间长度尺度
    self.addHyperparameter(r'$\lambda_x$', None)  # 信号方差
```

**为什么多输出用MultiTask核？**

对于 `ydim=3`（宽度、深度、面积），需要建模：
- 输出之间的相关性
- 每个输出的GP特性

MultiTask核函数形式：
```
K((x,t), (x',t')) = K_x(x, x') ⊗ K_t(t, t')
```
其中 `⊗` 是Kronecker积，允许不同任务共享结构。

---

## 数据准备阶段

### 2.1 存储实验数据

```python
# 用户代码 (acbici_calibration.py)
experiments = prepare_experimental_data_multivariate("experimental_data.csv")
# experiments shape: (5, 4) = [功率, 宽度, 深度, 面积]

theCalibrator.storeExperimentalData(experiments)
```

**内部存储**:
```python
def storeExperimentalData(self, data):
    self.xExp = data[:, :self.model.xdim]     # (5, 1): 功率
    self.yExp = data[:, self.model.xdim:]     # (5, 3): 观测值
    self.nExp = len(self.xExp)                # 5
```

**数据示例**:
```
xExp (功率):          yExp (观测):
[[140],              [[93.56,  78.96,  4755.5],
 [170],               [98.12,  99.58,  6791.3],
 [200],               [119.97, 126.02, 12527.5],
 [230],               [137.69, 153.98, 15314.0],
 [260]]               [134.32, 187.40, 18752.9]]
```

### 2.2 存储/生成合成数据

**合成数据的作用**: 在参数空间采样，为GP代理模型提供训练数据

```python
# 用户代码 (generate_synthetic_data.py)
# 使用LHS在 (x, θ) 空间采样，运行OpenFOAM得到 y
synthetic_data = generate_synthetic_data(model, n_samples=20)
# synthetic_data shape: (20, 7) = [功率, σ, γ, T_s, 宽度, 深度, 面积]

theCalibrator.storeSyntheticData(synthetic_data)
```

**内部存储**:
```python
def storeSyntheticData(self, data):
    xdim = self.model.xdim
    pdim = self.model.getNParam()

    self.xSyn = data[:, :xdim]                    # (20, 1): 功率
    self.tSyn = data[:, xdim:xdim+pdim]          # (20, 3): 参数
    self.ySyn = data[:, xdim+pdim:]              # (20, 3): 仿真输出
    self.nSyn = len(self.xSyn)                   # 20
```

**数据示例**:
```
xSyn:     tSyn (σ, γ, T_s):              ySyn:
[[156],   [1.34, -3.2e-4, 456],         [[105.2, 89.3, 8234],
 [203],   [1.67, -1.5e-4, 678],          [128.5, 134.6, 14567],
 ...]     ...]                            ...]
```

### 2.3 设置误差模型

**已知误差模式**:
```python
theCalibrator.setExperimentalSTDValue(5.0)  # σ_exp = 5μm
```

**未知误差模式**:
```python
from ACBICI import HalfCauchy
theCalibrator.setExperimentalSTDPrior(HalfCauchy(mu=0, sigma=10.0))
```

**影响**:
- 已知误差：`σ_exp` 固定，不参与MCMC采样
- 未知误差：`σ_exp` 作为额外参数采样

---

## 校准核心阶段

### 3.1 calibrate() 入口 ([calibrator.py:1868-1882](ACBICI/src/ACBICI/calibrator.py:1868-1882))

```python
def calibrate(self, *, nsteps=10000, burn=0.2, thin=1, nwalkers=16, nsynthetic=30):
    # 1. 如果没有合成数据，自动生成
    if self.nSyn < 1:
        self.generateSyntheticData(npoints=nsynthetic)
        sd = np.loadtxt(self.odirectory+"/synthetic.dat")
        self.storeSyntheticData(sd)

    # 2. 初始化协方差矩阵 Σ (N+M) × (N+M)
    N = self.nExp  # 实验点数: 5
    M = self.nSyn  # 合成点数: 20
    self.Sigma = np.zeros((N+M, N+M))  # (25, 25)

    # 3. 设置超参数的默认先验
    self.setDefaultHyperparametersPriors()

    # 4. 打印配置信息到 acbici.log
    self.printInfo()

    # 5. 调用通用MCMC采样
    self.genericCalibration(nsteps=nsteps, burn=burn, thin=thin, nwalkers=nwalkers)
```

### 3.2 设置超参数先验

```python
def setDefaultHyperparametersPriors(self):
    xdim = self.model.getInputDimension()  # 1
    pdim = self.model.getNParam()          # 3

    # 基于数据范围估计合理的超参数先验
    avg_dist_x = average_pairwise_distance(self.xExp)  # 功率的平均距离
    avg_dist_p = average_pairwise_distance(self.tSyn)  # 参数的平均距离

    # β_x: 输入空间长度尺度
    alpha = 5
    beta_val = alpha / avg_dist_x
    self.replaceHyperparameterPrior(r'$\beta_x$', Gamma(alpha=alpha, beta=beta_val))

    # β_t: 参数空间长度尺度
    beta_val = alpha / avg_dist_p
    self.replaceHyperparameterPrior(r'$\beta_t$', Gamma(alpha=alpha, beta=beta_val))

    # λ_x: 信号方差
    avg_dist_y = average_pairwise_distance(self.yExp)
    beta_val = alpha / avg_dist_y**2
    self.replaceHyperparameterPrior(r'$\lambda_x$', Gamma(alpha=alpha, beta=beta_val))
```

**超参数物理意义**:
- `β_x`: 功率变化多快会导致输出相关性衰减
- `β_t`: 参数变化多快会导致输出相关性衰减
- `λ_x`: GP输出的整体变化幅度

---

## MCMC采样细节

### 4.1 genericCalibration ([calibrator.py:532-621](ACBICI/src/ACBICI/calibrator.py:532-621))

```python
def genericCalibration(self, *, nsteps=10000, burn=0.2, thin=1, nwalkers=16, ...):
    # 1. 确定总参数数量
    nph = self.getNPHE()  # Parameters + Hyperparameters + ExpError
    # 对于已知误差: nph = 3 (θ) + 3 (超参数) = 6
    # 对于未知误差: nph = 3 + 3 + 1 = 7

    # 2. 创建emcee采样器
    sampler = emcee.EnsembleSampler(
        nwalkers,      # 12 (默认)
        nph,           # 6 或 7
        self.logPosterior,  # 后验概率函数
        args=[]
    )

    # 3. 初始化walker位置 (从先验分布随机采样)
    p0 = np.empty([nwalkers, nph])
    for i in range(nwalkers):
        p0[i, :] = self.randomize().reshape((nph,))
        # randomize(): 从每个参数的先验分布采样

    # 4. 运行MCMC
    sampler.run_mcmc(
        p0,                           # 初始位置
        nsteps,                       # 10000 步
        thin_by=thin,                 # 稀疏化因子
        progress=True,                # 显示进度条
        skip_initial_state_check=False
    )

    # 5. 燃烧期后提取样本
    nBurn = math.ceil(nsteps * burn)  # 0.2 * 10000 = 2000
    posterior = sampler.get_chain(flat=True, thin=thin, discard=nBurn)
    # posterior shape: (12 * (10000-2000), 6) = (96000, 6)
    # 但通常会自动稀疏化到更少

    # 6. 保存结果
    np.save(self.odirectory + '/samples.npy', posterior)
    np.save(self.odirectory + '/logprob.npy', logprob)
    np.save(self.odirectory + '/logprior.npy', logprior)
```

**Walker初始化示例**:
```
Walker 0: [σ=1.23, γ=-5.2e-4, T_s=487, β_x=234, β_t=0.25, λ_x=3456]
Walker 1: [σ=1.67, γ=-2.1e-4, T_s=623, β_x=198, β_t=0.31, λ_x=4123]
...
Walker 11: [σ=1.45, γ=-6.8e-4, T_s=356, β_x=267, β_t=0.19, λ_x=2987]
```

### 4.2 logPosterior 计算 ([calibrator.py:776-795](ACBICI/src/ACBICI/calibrator.py:776-795))

每次MCMC迭代，对每个walker的每个候选位置，都要计算后验概率：

```python
def logPosterior(self, PHE):
    """PHE = [θ, hyperparams, σ_exp (if unknown)]"""

    # 1. 存储当前参数值到模型
    self.storePHE(PHE)
    # 将 PHE 向量分解为:
    #   self.model.param = [σ, γ, T_s]
    #   hyperparams = [β_x, β_t, λ_x]
    #   (可选) self.expSTD = σ_exp

    # 2. 计算先验概率
    logPrior = np.sum(self.logPriors())
    # logPriors() 返回每个参数/超参数的 log(prior(value))
    # 例如: log(U(σ|1,2)) + log(U(γ|-8e-4,-4e-6)) + ...

    if math.isinf(logPrior):
        return -np.inf  # 参数超出先验支撑，直接拒绝

    # 3. 计算似然函数
    logLike = self.logLikelihood_vect()

    # 4. 返回后验 = 似然 + 先验
    return logLike + logPrior
```

### 4.3 logLikelihood_vect - 核心数学 ([calibrator.py:1948-2004](ACBICI/src/ACBICI/calibrator.py:1948-2004))

**Type B的关键假设**:
- 实验观测 `y_exp` 和合成数据 `y_syn` 联合服从高斯过程
- 协方差由GP核函数 + 观测误差组成

```python
def logLikelihood_vect(self):
    N = self.nExp  # 5
    M = self.nSyn  # 20

    # 1. 准备数据
    θ = self.model.param              # [σ, γ, T_s]
    θ_x = np.tile(θ, (N, 1))          # 复制N份: 实验点使用相同θ (待估计)

    x_exp = self.xExp                 # 实验输入 (5, 1)
    x_syn = self.xSyn                 # 合成输入 (20, 1)
    θ_syn = self.tSyn                 # 合成参数 (20, 3)

    # 2. 构建 (25×25) 协方差矩阵 Σ
    Σ = self.Sigma

    # Block (1,1): Cov(y_exp, y_exp) - N×N
    K_x_11 = covx(x_exp, x_exp)       # 输入空间协方差
    K_θ_11 = covt(θ_x, θ_x)           # 参数空间协方差
    Σ[:N, :N] = K_x_11 * K_θ_11
    # 添加观测噪声
    np.fill_diagonal(Σ[:N, :N], np.diag(Σ[:N, :N]) + σ_exp²)

    # Block (1,2): Cov(y_exp, y_syn) - N×M
    K_x_12 = covx(x_exp, x_syn)
    K_θ_12 = covt(θ_x, θ_syn)
    Σ[:N, N:N+M] = K_x_12 * K_θ_12

    # Block (2,1): 对称
    Σ[N:N+M, :N] = Σ[:N, N:N+M].T

    # Block (2,2): Cov(y_syn, y_syn) - M×M
    K_x_22 = covx(x_syn, x_syn)
    K_θ_22 = covt(θ_syn, θ_syn)
    Σ[N:N+M, N:N+M] = K_x_22 * K_θ_22

    # 3. 计算log-likelihood
    μ = np.zeros(N + M)  # 零均值GP
    z = np.concatenate([self.yExp, self.ySyn])  # (25, 3)

    ll = gaussianLogLikelihood(z, μ, Σ)
    # ll = -0.5 * [log|Σ| + (z-μ)ᵀΣ⁻¹(z-μ) + (N+M)*log(2π)]

    return ll
```

**协方差矩阵结构**:
```
       y_exp (5×3)        y_syn (20×3)
     ┌─────────────┬──────────────────┐
     │             │                  │
y_exp│  K_11 + σ²I │      K_12        │  5×3
     │             │                  │
     ├─────────────┼──────────────────┤
     │             │                  │
y_syn│    K_21     │       K_22       │  20×3
     │             │                  │
     └─────────────┴──────────────────┘

总大小: (25×3) × (25×3) = 75 × 75 (对于多输出)
```

**核函数计算** ([calibrator.py:1884-1945](ACBICI/src/ACBICI/calibrator.py:1884-1945)):
```python
def covx(self, x1, x2):
    """输入空间协方差 K_x"""
    β_x = self.hyperParam[0]      # 长度尺度
    λ_x = self.hyperParam[2]      # 信号方差

    K = self.kernel.K(x1, x2, β_x)  # 核函数计算
    return λ_x * K

def covt(self, θ1, θ2):
    """参数空间协方差 K_θ"""
    β_t = self.hyperParam[1]

    K = self.kernel.K(θ1, θ2, β_t)
    return K
```

**Matern32核示例**:
```python
K(x, x') = (1 + √3·d/β) · exp(-√3·d/β)
其中 d = ||x - x'||
```

### 4.4 MCMC迭代过程

```
步骤 1: 初始化
┌─────────────────────────────────────────┐
│ Walker 0: θ⁰ = [1.23, -5.2e-4, 487, ...] │
│ Walker 1: θ¹ = [1.67, -2.1e-4, 623, ...] │
│ ...                                      │
│ Walker 11: θ¹¹ = [1.45, -6.8e-4, 356, ...]│
└─────────────────────────────────────────┘

步骤 2-10000: MCMC采样
For step t = 1 to 10000:
  For each walker w:
    1. 提出候选 θ* (基于其他walkers)
    2. 计算 logPosterior(θ*)
    3. 计算接受率 α = min(1, P(θ*)/P(θ_current))
    4. 以概率α接受，否则保持原位置

  每100步显示进度条

步骤 11: 燃烧期处理
丢弃前2000步 (burn=0.2)
保留后8000步 × 12 walkers = 96000个样本
(实际可能稀疏化)

步骤 12: 保存结果
samples.npy: (4800, 6) - 后验样本
logprob.npy: (4800,)   - 对数后验概率值
```

**收敛诊断**:
```python
# ACBICI自动计算autocorrelation time
try:
    tau = sampler.get_autocorr_time()
    # 如果 chain长度 < 50 * tau，发出警告
except emcee.autocorr.AutocorrError as e:
    print("WARNING: Chain may be too short")
```

---

## 结果输出阶段

### 5.1 printReport() ([calibrator.py:600-621](ACBICI/src/ACBICI/calibrator.py:600-621))

```python
def printReport(self):
    with open(self.logfilename, 'a') as f:
        # 1. 打印运行信息
        f.write("\n Process report:\n")
        f.write(f"   - Chain length: {nsteps}\n")
        f.write(f"   - Burn in: {nBurn}\n")
        f.write(f"   - N walkers: {nwalkers}\n")

        # 2. 打印acceptance fraction
        mean_accept = np.mean(sampler.acceptance_fraction)
        f.write(f"   - Mean acceptance fraction: {mean_accept:.3f}\n")

        # 3. 检查autocorrelation
        try:
            tau = sampler.get_autocorr_time()
            # 检查 N/50 > tau
        except:
            f.write("   - WARNING: Chain may be too short\n")

        # 4. 打印参数统计
        posterior = np.load(self.odirectory + "/samples.npy")
        printStatistics(param_names, posterior, file=f)
```

**输出到 acbici.log**:
```
Summary statistics (4800 samples)

 Parameter     Mean     Median     app-MAP    Variance       95%-credible
---------------------------------------------------------------------------
 $\sigma$   1.076e+00  1.069e+00  1.007e+00  3.374e-03  [1.002e+00, 1.218e+00]
 $\gamma$   -4.135e-04  -3.856e-04  -7.846e-04  5.402e-08  [-7.927e-04, -5.211e-05]
 $T_s$      3.473e+02  3.344e+02  3.046e+02  1.721e+03  [3.016e+02, 4.442e+02]
```

### 5.2 plot() 可视化

**ACBICI内置plot** ([calibrator.py:2007-2033](ACBICI/src/ACBICI/calibrator.py:2007-2033)):
```python
def plot(self, *, trace=True, corner=True, ...):
    if trace:
        self.plotTrace(...)       # 生成 trace.png
    if corner:
        self.plotCorner(...)      # 生成 corner.png (需要corner包)
    if prior:
        self.plotPriorsPosteriors(...)  # 生成 priors.png
    # ...
```

**备用方案** (我们的 plot_results_simple.py):
- 不依赖corner包
- 直接读取 samples.npy
- 生成 trace.png, posteriors.png, pairwise.png

---

## 数学原理

### 6.1 贝叶斯推断框架

**目标**: 估计参数 θ 的后验分布

$$
P(\theta | y_{exp}) \propto P(y_{exp} | \theta) \cdot P(\theta)
$$

- `P(θ)`: 先验分布（Uniform, Normal等）
- `P(y_exp | θ)`: 似然函数（数据给定参数的概率）
- `P(θ | y_exp)`: 后验分布（参数给定数据的概率）

**Type B特点**: 使用GP代理模型加速

### 6.2 Kennedy-O'Hagan (KOH) 框架

**假设**: 真实物理过程 + 计算机模型 + 观测误差

$$
y_{exp}(x) = \eta(x, \theta) + \delta(x) + \epsilon
$$

其中:
- `η(x, θ)`: 计算机模型（OpenFOAM）
- `δ(x)`: 模型差异（Type D会估计，Type B假设为0）
- `ε ~ N(0, σ²)`: 观测误差

**GP先验**:
$$
\eta(x, \theta) \sim GP(0, K_x(x,x') \cdot K_\theta(\theta, \theta'))
$$

**联合分布**:
$$
\begin{bmatrix} y_{exp} \\ y_{syn} \end{bmatrix} \sim N\left(0,
\begin{bmatrix}
K_{11} + \sigma^2 I & K_{12} \\
K_{21} & K_{22}
\end{bmatrix}\right)
$$

### 6.3 核函数

**Matérn 3/2 核** (您使用的):
$$
K(r) = (1 + \frac{\sqrt{3}r}{\ell}) \exp\left(-\frac{\sqrt{3}r}{\ell}\right)
$$

其中:
- `r = ||x - x'||`: 欧氏距离
- `ℓ = 1/β`: 长度尺度

**性质**:
- 一次可微
- 介于光滑（Matérn 5/2）和粗糙（指数）之间
- 适合大多数物理过程

### 6.4 MCMC采样

**Affine Invariant Ensemble Sampler** (emcee):

```
对于walker i:
1. 随机选择另一个walker j
2. 提出候选: θ* = θ_j + Z(θ_i - θ_j)
   其中 Z ~ g(z) (特殊分布)
3. 计算接受率: α = min(1, Z^(d-1) · P(θ*)/P(θ_i))
4. 以概率α接受θ*
```

**优点**:
- 自适应步长
- 对参数空间的线性变换不变
- 并行效率高

---

## 常见问题

### Q1: 为什么需要合成数据？

**A**: Type B使用GP代理模型，需要在参数空间采样来训练GP。

- **实验数据**: 固定θ（未知），多个x点
- **合成数据**: 已知θ，多个(x, θ)组合

### Q2: 超参数 β_x, β_t, λ_x 是什么？

**A**: GP核函数的超参数，控制协方差结构

- `β_x`: 输入空间相关性衰减速度
- `β_t`: 参数空间相关性衰减速度
- `λ_x`: GP输出的整体方差

它们也被当作随机变量，与θ一起在MCMC中采样。

### Q3: 为什么trace图很重要？

**A**: Trace图直观显示MCMC是否收敛

- ✅ 平稳波动 → 已收敛
- ❌ 持续趋势 → 未收敛，需要更多步数

### Q4: 如何理解95%置信区间？

**A**: 后验分布的分位数

```
CI = [q_2.5%, q_97.5%]
```

表示：有95%的概率，真实参数在此区间内。

### Q5: 相关系数矩阵说明什么？

**A**: 参数之间的线性相关性

```
corr(σ, γ) = 0.41  (中度正相关)
```

意味着：σ增大时，γ也倾向于增大（向更负的方向）。

---

## 流程图（ASCII艺术）

```
╔════════════════════════════════════════════════════════════════╗
║                    用户代码 (acbici_calibration.py)             ║
╚════════════════════════════════════════════════════════════════╝
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 1. 创建模型 MeltpoolModel()           │
          │    - xdim=1, ydim=3                 │
          │    - 添加参数先验 (σ, γ, T_s)        │
          └──────────────────────────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 2. 创建校准器 expensiveCalibrator()   │
          │    - 选择MultiTask核                 │
          │    - 添加超参数 (β_x, β_t, λ_x)      │
          └──────────────────────────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 3. 准备数据                          │
          │    - storeExperimentalData(5 points) │
          │    - storeSyntheticData(20 points)   │
          │    - setExperimentalSTDValue(5.0)    │
          └──────────────────────────────────────┘
                              │
                              ▼
╔════════════════════════════════════════════════════════════════╗
║                    calibrate() - 校准入口                       ║
╚════════════════════════════════════════════════════════════════╝
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 4. 初始化协方差矩阵 Σ (25×25)         │
          │    设置超参数先验 (基于数据范围)      │
          └──────────────────────────────────────┘
                              │
                              ▼
╔════════════════════════════════════════════════════════════════╗
║              genericCalibration() - MCMC核心                   ║
╚════════════════════════════════════════════════════════════════╝
                              │
          ┌───────────────────┴─────────────────┐
          │                                     │
          ▼                                     ▼
  ┌──────────────┐                    ┌─────────────────┐
  │ 5. 初始化    │                    │ 6. MCMC循环     │
  │ - 12 walkers │                    │ (10000 steps)   │
  │ - 从先验采样  │                    └─────────────────┘
  └──────────────┘                             │
          │                                     │
          └───────────────────┬─────────────────┘
                              ▼
          ┌──────────────────────────────────────┐
          │ logPosterior(θ, hyperparams)         │
          │  │                                   │
          │  ├─> logPriors()                     │
          │  │    └─ Σ log P(param_i)            │
          │  │                                   │
          │  └─> logLikelihood_vect()            │
          │       ├─ 构建协方差 Σ:               │
          │       │   K_x ⊗ K_θ + noise          │
          │       │                               │
          │       └─ 计算高斯似然:                │
          │           -0.5[log|Σ| + z^T Σ^{-1} z]│
          └──────────────────────────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 7. Metropolis-Hastings 接受/拒绝     │
          │    - 计算接受率 α                    │
          │    - 更新walker位置                  │
          └──────────────────────────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 8. 燃烧期处理 (丢弃前20%)            │
          │    - 保留8000×12样本                 │
          │    - (可能稀疏化到4800)              │
          └──────────────────────────────────────┘
                              │
                              ▼
╔════════════════════════════════════════════════════════════════╗
║                    结果保存与可视化                            ║
╚════════════════════════════════════════════════════════════════╝
                              │
          ┌───────────────────┴─────────────────┐
          │                                     │
          ▼                                     ▼
  ┌──────────────┐                    ┌─────────────────┐
  │ 9. 保存数据  │                    │ 10. 生成报告    │
  │ - samples.npy│                    │  - acbici.log   │
  │ - logprob.npy│                    │  - statistics   │
  └──────────────┘                    └─────────────────┘
                              │
                              ▼
          ┌──────────────────────────────────────┐
          │ 11. 可视化                           │
          │  - plot_results_simple.py            │
          │    ├─ trace.png                      │
          │    ├─ posteriors.png                 │
          │    └─ pairwise.png                   │
          └──────────────────────────────────────┘
```

---

## 总结

ACBICI Type B校准器的核心流程：

1. **初始化**: 定义模型、参数先验、GP核函数
2. **数据准备**: 实验数据 + 合成数据（LHS采样）
3. **MCMC采样**: 使用emcee在后验分布中采样
4. **似然计算**: 基于GP协方差矩阵的高斯似然
5. **结果输出**: 后验样本、统计报告、可视化图表

**关键数学**:
- 贝叶斯定理：posterior ∝ likelihood × prior
- 高斯过程：联合高斯分布建模
- MCMC：探索高维后验空间

**Type B的优势**:
- 使用GP代理模型，避免每次MCMC都运行OpenFOAM
- 仅需少量合成数据（20个）即可训练GP
- 提供完整的不确定度量化

希望这个详细的流程讲解对您有帮助！

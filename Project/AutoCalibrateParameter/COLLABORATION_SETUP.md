# AutoCalibrateParameter 协作复现说明

这份文档写给已经有本地 `LaserbeamFoam` 源码、但需要复现本项目标定流程的协作者。

核心结论很简单：

1. 同步 [`Project/AutoCalibrateParameter`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter) 项目文件。
2. 在上层 `LaserbeamFoam` 仓库里修改 2 个 solver 源码文件。
3. 重新编译 `laserbeamFoam` solver。
4. 用相同的 case、配置和实验数据运行标定。

如果上层 solver 不同步，协作者即使拿到了相同的 Python 标定代码和 case 文件，也不一定能得到与你一致的结果。

## 适用对象

这份文档适用于下面这种情况：

- 已经有 `LaserbeamFoam` 源码仓库；
- 会打开并修改源码文件；
- 不一定熟悉 OpenFOAM solver 的重新编译流程；
- 希望和当前项目使用完全一致的物理模型与标定流程。

## 为什么不只同步 `AutoCalibrateParameter`

这个项目不只改了 [`Project/AutoCalibrateParameter`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter) 下面的 Python 和 case 文件，还改了上层 `LaserbeamFoam` 求解器源码：

- [`applications/solvers/laserbeamFoam/UEqn.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/UEqn.H)
- [`applications/solvers/laserbeamFoam/createFields.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/createFields.H)

这两个改动会直接影响求解器的行为。协作者如果使用原版 solver：

- 可能仍然能运行标定，但底层物理含义和你现在的不一致；
- 也可能出现“项目参数语义”和“solver 实现语义”不一致的问题，导致结果不可比。

当前项目中，回弹压力应该由 `recoilCoeff` 控制，而不是继续和 `damperCoeff` 绑定在一起。这个行为是在 solver 源码里实现的，所以不能只同步项目目录而不修改上层 solver。

## 最小同步方案

如果你不想把整个 `LaserbeamFoam` 库都发给对方，最省事的做法是只同步下面三部分：

1. [`Project/AutoCalibrateParameter`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter) 的完整项目文件，或者至少同步到同一个分支/提交。
2. 上层 solver 的 2 个修改文件，或者一份只包含这两个文件差异的 patch。
3. 这份文档。

这样协作者只需要在自己已有的 `LaserbeamFoam` 仓库上补两处源码改动，再重新编译即可。

## 需要修改的上层 solver 文件

### 1. 修改 `createFields.H`

编辑 [`applications/solvers/laserbeamFoam/createFields.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/createFields.H) 中靠近第 536-559 行的位置，确保其中定义了 `recoilCoeff`，形式如下：

```cpp
// Read recoil coefficient from transportProperties.
// Backward compatible: fall back to legacy key "damper" when recoilCoeff is absent.
const scalar recoilCoeffValue
(
    transportProperties.lookupOrDefault<scalar>
    (
        "recoilCoeff",
        transportProperties.lookupOrDefault<scalar>("damper", 1.0)
    )
);

const dimensionedScalar recoilCoeff
(
    "recoilCoeff",
    dimless,
    recoilCoeffValue
);

const dimensionedScalar damperCoeff
(
    "damper",
    dimless,
    transportProperties.lookupOrDefault<scalar>("damper", 1.0)
);
```

这段修改的作用是：

- 新增一个 solver 侧参数 `recoilCoeff`；
- 如果 case 里没有显式提供 `recoilCoeff`，则自动回退到旧参数 `damper`；
- 同时保留 `damperCoeff` 给原来的 damping 逻辑继续使用。

也就是说，这个修改兼顾了新语义和旧 case 的兼容性。

### 2. 修改 `UEqn.H`

编辑 [`applications/solvers/laserbeamFoam/UEqn.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/UEqn.H) 中靠近第 48 行的位置，确保回弹压力使用的是 `recoilCoeff`：

```cpp
pVap = recoilCoeff * 0.54*p0*Foam::exp(LatentHeatVap*Mm*((T - Tvap)/(R*T*Tvap)));
```

关键点只有一个：

- 这里必须使用 `recoilCoeff`
- 不能继续使用 `damperCoeff`

## 这些文件在仓库中的位置

以下路径均相对于 `LaserbeamFoam` 仓库根目录：

```text
LaserbeamFoam/
├── applications/
│   └── solvers/
│       └── laserbeamFoam/
│           ├── UEqn.H
│           └── createFields.H
└── Project/
    └── AutoCalibrateParameter/
```

如果协作者已经有自己的 `LaserbeamFoam` 源码树，只需要把对应修改放到同名路径下即可。

## 如何重新编译 solver

修改完上层源码后，必须重新编译 `laserbeamFoam`，否则运行的仍然是旧二进制。

### 方案一：重新编译整个仓库

在 `LaserbeamFoam` 根目录执行：

```bash
source /path/to/OpenFOAM/etc/bashrc
cd /path/to/LaserbeamFoam
./Allwmake -j
```

说明：

- `source /path/to/OpenFOAM/etc/bashrc` 是为了先加载 OpenFOAM 环境；
- `./Allwmake -j` 会编译 `src/` 下的库和 `applications/` 下的应用；
- 当前仓库的 `Allwmake` 脚本会检查 OpenFOAM 是否已加载；
- 当前 `Allwmake` 脚本允许的版本是 `v2412` 和 `v2506`。

### 方案二：只重编译 `laserbeamFoam` solver

如果只改了 `laserbeamFoam` 求解器源码，通常可以直接在 solver 目录下重编译：

```bash
source /path/to/OpenFOAM/etc/bashrc
cd /path/to/LaserbeamFoam/applications/solvers/laserbeamFoam
wmake
```

这个方案通常更快，也更适合协作者只同步少量源码改动的场景。

## 如何确认编译成功

建议至少检查下面几项：

1. 编译命令退出码为 0，没有中断。
2. 如果使用的是 `./Allwmake`，日志里没有出现 `Error` 或 `Stop.`。
3. 当前 shell 实际调用到的是刚刚编译出来的 `laserbeamFoam` 可执行文件。
4. 用一个小 case 或目标 case 试跑，确认 solver 可以正常启动。

常用检查命令：

```bash
which laserbeamFoam
laserbeamFoam -help
```

如果 `which laserbeamFoam` 指向的是另一个 OpenFOAM 环境里的旧二进制，就会出现“源码改了、也编译了，但运行结果没变”的假象。遇到这种情况，应先确认环境变量和可执行文件路径。

## 推荐给协作者的实际操作顺序

对于已经有 `LaserbeamFoam` 的协作者，推荐顺序如下：

1. 获取最新的 [`Project/AutoCalibrateParameter`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter) 文件。
2. 在上层 `LaserbeamFoam` 仓库中修改 [`UEqn.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/UEqn.H) 和 [`createFields.H`](/home/cgh/LaserbeamFoam/applications/solvers/laserbeamFoam/createFields.H)。
3. 重新编译 `laserbeamFoam`。
4. 检查 case 配置、实验数据和运行脚本是否与项目版本一致。
5. 再开始运行标定流程。

## 技术说明：为什么这两个改动是必要的

这两个源码修改的本质，是把原本混在一起的两个物理控制量分开：

- `damperCoeff`：用于 damping 相关行为；
- `recoilCoeff`：用于回弹压力缩放。

修改前，回弹压力这一项实际上乘的是 `damperCoeff`。这会带来一个问题：当你想单独调回弹压力时，实际上还把它和另一个物理控制量绑在了一起，语义不清晰，也不利于参数标定。

修改后：

- 回弹压力由 `recoilCoeff` 单独控制；
- damping 逻辑仍然保留 `damperCoeff`；
- 老 case 如果只有 `damper` 而没有 `recoilCoeff`，solver 仍然可以通过回退机制继续运行。

因此，这并不是一次“代码风格优化”，而是一次会影响模型语义和标定一致性的 solver 行为修改。

## 建议你发给协作者的内容

最实用的一套材料是：

1. [`Project/AutoCalibrateParameter`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter) 的分支、压缩包或 patch；
2. 上层 solver 两个文件的修改版，或者一份小 patch；
3. 这份 [`COLLABORATION_SETUP.md`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/COLLABORATION_SETUP.md)。

这样不需要让对方重新获取一整套完整库，也能保证她和你使用的是同一套项目逻辑与 solver 语义。

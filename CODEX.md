# CODEX 工作约定

本文件用于提醒后续所有 LLM/Codex 会话：在本仓库执行测试、脚本和校准任务时，必须使用正确的 `conda` 环境。

## 强制规则

- 不要在系统默认 Python 环境中直接运行测试或校准脚本。
- 在执行任何 `python`、`pytest`、优化脚本前，先进入对应 `conda` 环境，或使用 `conda run -n <env>`。

## 当前项目默认环境

- `Project/AutoCalibrateParameter`（包含 `cases/316L/SingleTrack`）统一使用：`meltpool-postproc`

## 推荐执行方式

### 方式 1：先激活环境（交互式）

```bash
conda activate meltpool-postproc
cd /home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/cases/316L/SingleTrack
python main.py
```

### 方式 2：单条命令执行（非交互式，推荐给自动化/LLM）

```bash
conda run -n meltpool-postproc python main.py
```

## 给后续 LLM 的要求

- 每次准备运行测试前，先说明将使用的 `conda` 环境名称。
- 如果检测到当前不在目标环境中，先切换环境再继续。
- 若环境不存在，先停止执行并提示用户确认环境名或先创建环境。

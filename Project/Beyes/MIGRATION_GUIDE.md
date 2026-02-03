# 代码统一迁移指南

## 变更说明

原本有两个独立的贝叶斯优化脚本：
- `bayes_opt.py` - 个人电脑版本
- `bayes_opt_HPC.py` - HPC 服务器版本

现在统一为单个脚本 `bayes_opt_HPC.py`，通过 `--hpc` 参数切换模式。

## 主要改进

1. **统一代码库**：不再需要维护两个版本的代码
2. **功能一致**：两种模式都支持完整的续跑、归档等功能
3. **灵活切换**：仅需一个参数即可在两种模式间切换
4. **向后兼容**：现有配置文件和使用方式基本不变

## 迁移步骤

### 从个人电脑版本迁移

**之前的命令：**
```bash
python bayes_opt.py --config config.yaml
```

**新命令（完全兼容）：**
```bash
python bayes_opt_HPC.py --config config.yaml
```

或者更明确：
```bash
python bayes_opt_HPC.py --config config.yaml  # 默认就是个人电脑模式
```

### 从 HPC 版本迁移

**之前的命令：**
```bash
python bayes_opt_HPC.py --foam-runner of2506 --postproc-runner of2506
```

**新命令（需添加 --hpc）：**
```bash
python bayes_opt_HPC.py --hpc --foam-runner of2506 --postproc-runner of2506
```

## 配置文件迁移

### 个人电脑配置

旧的 `config.yaml` 无需修改，直接使用即可。

### HPC 配置

在配置文件顶部添加（可选）：
```yaml
hpc: true  # 或者使用命令行 --hpc 参数
```

或者保持配置文件不变，运行时添加 `--hpc`：
```bash
python bayes_opt_HPC.py --hpc --config config.yaml
```

## 两种模式的技术差异

### 个人电脑模式（默认）

- 使用 `bash -lc` 直接执行 OpenFOAM 命令
- 默认后处理脚本路径：`/home/cgh/LaserbeamFoam/applications/scripts/postProcessing/characterise_meltpool.py`
- 不需要 `foam_runner` 或 `postproc_runner`

### HPC 模式（`--hpc`）

- 通过 `_run_script` 函数和可选的 `foam_runner` 执行命令
- 默认后处理脚本路径：相对于项目根目录的 `applications/scripts/postProcessing/characterise_meltpool.py`
- 支持 `POSTPROC_RUNNER` 和 `PVPYTHON` 环境变量
- 适用于容器化环境或作业调度系统

## 验证迁移

### 测试个人电脑模式

```bash
# 运行少量迭代测试
python bayes_opt_HPC.py --iters 1 --n-initial 1

# 检查输出应显示
[info] 运行在个人电脑模式
```

### 测试 HPC 模式

```bash
# 运行少量迭代测试
python bayes_opt_HPC.py --hpc --iters 1 --n-initial 1

# 检查输出应显示
[info] 运行在 HPC 模式
```

## 常见问题

### Q: 我需要修改现有的历史记录文件吗？

**A:** 不需要。`bayes_history.csv` 格式完全兼容，可以直接续跑。

### Q: 两种模式可以共享历史记录吗？

**A:** 可以，但不推荐。虽然格式兼容，但路径配置可能不同，建议分开使用。

### Q: 如何知道当前运行在哪种模式？

**A:** 脚本启动时会打印：
- `[info] 运行在个人电脑模式`
- `[info] 运行在 HPC 模式`

### Q: 我可以删除旧的 bayes_opt.py 吗？

**A:** 建议先保留一段时间作为备份，确认新脚本运行正常后再删除。

## 推荐工作流

1. **本地开发/调试**：使用个人电脑模式（默认）
   ```bash
   python bayes_opt_HPC.py --iters 2
   ```

2. **提交到 HPC 集群**：添加 `--hpc` 参数
   ```bash
   python bayes_opt_HPC.py --hpc --iters 50
   ```

3. **配置文件管理**：
   - `config_pc.yaml` - 个人电脑配置
   - `config_hpc.yaml` - HPC 配置（包含 `hpc: true`）

   使用时：
   ```bash
   python bayes_opt_HPC.py --config config_pc.yaml   # 本地
   python bayes_opt_HPC.py --config config_hpc.yaml  # HPC（配置中有 hpc: true）
   ```

## 获取帮助

查看所有可用参数：
```bash
python bayes_opt_HPC.py --help
```

参考详细文档：
- [README_unified.md](README_unified.md) - 完整使用指南
- [config_example.yaml](config_example.yaml) - 配置文件示例

#!/bin/bash
# 迭代贝叶斯校准快速入门示例
#
# 用法: bash examples/quick_start_iterative.sh

set -e  # 遇到错误立即退出

echo "======================================================================"
echo "迭代贝叶斯校准快速入门"
echo "======================================================================"
echo ""

# 进入工作目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOW_DIR="$(dirname "$SCRIPT_DIR")"
cd "$WORKFLOW_DIR"

echo "工作目录: $(pwd)"
echo ""

# ========== 步骤 1: 检查/生成初始合成数据 ==========
SYNTHETIC_DATA="../data/synthetic_data.dat"

if [ -f "$SYNTHETIC_DATA" ]; then
    echo "✓ 发现已有合成数据: $SYNTHETIC_DATA"
    echo "  如需重新生成，请删除该文件后重新运行"
else
    echo "生成初始合成数据 (20 个 LHS 样本)..."
    python generate_synthetic_data.py \
        --n-samples 20 \
        --config ../config.yaml \
        --output "$SYNTHETIC_DATA"
    echo "✓ 合成数据生成完成"
fi
echo ""

# ========== 步骤 2: 运行迭代校准 (快速模式) ==========
echo "======================================================================"
echo "开始迭代校准 (快速测试模式)"
echo "======================================================================"
echo "配置:"
echo "  - 最大迭代次数: 3"
echo "  - 每轮新采样: 2 个参数点"
echo "  - MCMC 步数: 500"
echo "  - 采样策略: hybrid (混合)"
echo ""

python iterative_calibration.py \
    --config ../config.yaml \
    --experimental-data ../experimental_data.csv \
    --synthetic-data "$SYNTHETIC_DATA" \
    --max-iterations 3 \
    --n-new-samples 2 \
    --sampling-strategy hybrid \
    --kernel matern32 \
    --nsteps 500 \
    --burn 0.2 \
    --nwalkers 12 \
    --error-type known \
    --exp-std 5.0 \
    --tol-param-change 0.02 \
    --tol-std 0.08 \
    --output-dir ../iterative_calibration_quick_test

echo ""
echo "✓ 迭代校准完成"
echo ""

# ========== 步骤 3: 生成可视化 ==========
echo "======================================================================"
echo "生成可视化图表"
echo "======================================================================"

python utils/plot_iteration_history.py \
    ../iterative_calibration_quick_test/iteration_log.json

echo ""
echo "✓ 可视化生成完成"
echo ""

# ========== 总结 ==========
echo "======================================================================"
echo "快速入门完成!"
echo "======================================================================"
echo ""
echo "结果文件位置:"
echo "  - 迭代日志: ../iterative_calibration_quick_test/iteration_log.json"
echo "  - 摘要报告: ../iterative_calibration_quick_test/iteration_summary.txt"
echo "  - 可视化图表: ../iterative_calibration_quick_test/*.png"
echo ""
echo "查看结果:"
echo "  cat ../iterative_calibration_quick_test/iteration_summary.txt"
echo ""
echo "如需运行完整的高精度校准，请使用:"
echo "  python iterative_calibration.py --max-iterations 5 --nsteps 1000"
echo ""

#!/bin/bash
# ACBICI 校准工作流快速启动脚本

set -e  # 遇到错误时退出

echo "=========================================="
echo "ACBICI 贝叶斯校准工作流"
echo "=========================================="
echo ""

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 检查必需文件
echo "检查必需文件..."
if [ ! -f "../config.yaml" ]; then
    echo "错误: 未找到 config.yaml，请确保在正确的目录运行"
    exit 1
fi

if [ ! -f "../experimental_data.csv" ]; then
    echo "错误: 未找到 experimental_data.csv"
    exit 1
fi

# 检查合成数据是否存在
if [ ! -f "../data/synthetic_data.dat" ]; then
    echo "合成数据不存在，开始生成..."
    python generate_synthetic_data.py --n-samples 20
    echo ""
else
    echo "发现已存在的合成数据，跳过生成步骤"
    echo "如需重新生成，请删除 ../data/synthetic_data.dat"
    echo ""
fi

# 运行校准
echo "=========================================="
echo "开始贝叶斯校准..."
echo "=========================================="
echo ""

# 默认参数
CALIBRATION_TYPE=${1:-both}
NSTEPS=${2:-500}
NWALKERS=${3:-12}

echo "校准类型: $CALIBRATION_TYPE"
echo "MCMC 步数: $NSTEPS"
echo "Walker 数量: $NWALKERS"
echo ""

python acbici_calibration.py \
    --calibration-type "$CALIBRATION_TYPE" \
    --nsteps "$NSTEPS" \
    --nwalkers "$NWALKERS" \
    --kernel matern32

echo ""
echo "=========================================="
echo "校准完成！"
echo "=========================================="
echo ""
echo "结果保存在父目录下的 .out/ 文件夹中"
echo "- 已知误差: ../meltpool_calibration_known_error.out/"
echo "- 未知误差: ../meltpool_calibration_unknown_error.out/"
echo ""

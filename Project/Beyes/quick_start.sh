#!/bin/bash
###############################################################################
# ACBICI 贝叶斯校准快速开始脚本
#
# 该脚本自动完成整个校准流程：
# 1. 检查依赖
# 2. 生成合成数据（可选）
# 3. 运行贝叶斯校准
#
# 用法:
#   ./quick_start.sh               # 完整流程（生成合成数据 + 校准）
#   ./quick_start.sh --skip-synth  # 跳过合成数据生成（使用已有数据）
#   ./quick_start.sh --test        # 测试模式（少量样本快速验证）
###############################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
SKIP_SYNTHETIC=false
TEST_MODE=false
N_SYNTHETIC=20
N_MCMC_STEPS=10000

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-synth)
            SKIP_SYNTHETIC=true
            shift
            ;;
        --test)
            TEST_MODE=true
            N_SYNTHETIC=5
            N_MCMC_STEPS=1000
            shift
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --skip-synth    跳过合成数据生成"
            echo "  --test          测试模式（少量样本）"
            echo "  --help          显示此帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ACBICI 贝叶斯校准快速开始${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}*** 测试模式 ***${NC}"
    echo -e "${YELLOW}合成样本: $N_SYNTHETIC (快速验证)${NC}"
    echo -e "${YELLOW}MCMC步数: $N_MCMC_STEPS${NC}"
    echo ""
fi

# 步骤 1: 检查依赖
echo -e "${GREEN}[1/3] 检查依赖...${NC}"
echo ""

# 检查Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}错误: 未找到python命令${NC}"
    exit 1
fi
echo "  ✓ Python: $(python --version)"

# 检查必需的Python包
echo "  检查Python包..."
python -c "import numpy, pandas, yaml, emcee" 2>/dev/null || {
    echo -e "${RED}  ✗ 缺少必需的Python包${NC}"
    echo "  请运行: pip install numpy pandas pyyaml emcee"
    exit 1
}
echo "  ✓ NumPy, Pandas, PyYAML, emcee"

# 检查ACBICI
python -c "import sys; sys.path.append('ACBICI/src'); from ACBICI import expensiveCalibrator" 2>/dev/null || {
    echo -e "${RED}  ✗ ACBICI未安装${NC}"
    echo "  请运行: cd ACBICI && pip install -e ."
    exit 1
}
echo "  ✓ ACBICI"

# 检查文件
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}  ✗ 缺少 config.yaml${NC}"
    exit 1
fi
echo "  ✓ config.yaml"

if [ ! -f "experimental_data.csv" ]; then
    echo -e "${RED}  ✗ 缺少 experimental_data.csv${NC}"
    exit 1
fi
echo "  ✓ experimental_data.csv"

echo ""
echo -e "${GREEN}所有依赖检查通过!${NC}"
echo ""

# 步骤 2: 生成合成数据
if [ "$SKIP_SYNTHETIC" = false ]; then
    echo -e "${GREEN}[2/3] 生成合成数据...${NC}"
    echo ""
    echo "  样本数量: $N_SYNTHETIC"
    echo "  输出文件: data/synthetic_data.dat"
    echo ""

    if [ "$TEST_MODE" = true ]; then
        echo -e "${YELLOW}  注意: 测试模式使用少量样本，结果仅供验证流程${NC}"
    else
        echo -e "${YELLOW}  警告: 生成合成数据需要运行多次OpenFOAM仿真${NC}"
        echo -e "${YELLOW}        可能需要数小时，请确保有足够时间${NC}"
    fi
    echo ""

    # 运行生成脚本
    python generate_synthetic_data.py --n-samples $N_SYNTHETIC || {
        echo -e "${RED}生成合成数据失败!${NC}"
        exit 1
    }

    echo ""
    echo -e "${GREEN}合成数据生成完成!${NC}"
    echo ""
else
    echo -e "${YELLOW}[2/3] 跳过合成数据生成（使用已有数据）${NC}"
    echo ""

    if [ ! -f "data/synthetic_data.dat" ]; then
        echo -e "${RED}错误: data/synthetic_data.dat 不存在${NC}"
        echo "请先生成合成数据或移除 --skip-synth 参数"
        exit 1
    fi
    echo "  ✓ 找到现有合成数据: data/synthetic_data.dat"
    echo ""
fi

# 步骤 3: 运行贝叶斯校准
echo -e "${GREEN}[3/3] 运行贝叶斯校准...${NC}"
echo ""
echo "  校准类型: known-error + unknown-error"
echo "  核函数: matern32"
echo "  MCMC步数: $N_MCMC_STEPS"
echo "  Walkers: 16"
echo ""

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}  注意: 测试模式使用少量MCMC步数${NC}"
    echo -e "${YELLOW}        结果仅供验证流程，不保证收敛${NC}"
    echo ""
fi

echo "开始MCMC采样..."
echo ""

# 运行校准
python acbici_calibration.py \
    --calibration-type both \
    --kernel matern32 \
    --nsteps $N_MCMC_STEPS \
    --burn 0.2 \
    --nwalkers 16 || {
    echo -e "${RED}校准失败!${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}校准完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "结果保存在以下目录:"
echo "  📁 meltpool_calibration_known_error/"
echo "  📁 meltpool_calibration_unknown_error/"
echo ""
echo "查看关键结果文件:"
echo "  📊 corner_plot.png     - 参数后验分布"
echo "  📈 trace_plot.png      - MCMC收敛性"
echo "  📄 statistics.txt      - 统计摘要"
echo ""

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}提醒: 这是测试运行，使用少量样本和MCMC步数${NC}"
    echo -e "${YELLOW}      完整校准需要更多样本和步数，请参考 README_ACBICI.md${NC}"
    echo ""
fi

echo -e "${BLUE}下一步:${NC}"
echo "  1. 查看 corner 图了解参数后验分布"
echo "  2. 检查 trace 图确认 MCMC 收敛"
echo "  3. 阅读 statistics.txt 获取参数估计值"
echo "  4. 详细文档请参考 README_ACBICI.md"
echo ""

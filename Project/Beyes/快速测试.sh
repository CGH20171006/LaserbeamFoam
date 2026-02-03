#!/bin/bash
# 快速测试脚本 - 2个功率点，一半模拟时间

cd /home/cgh/LaserbeamFoam/Project/Beyes

echo "=========================================="
echo "快速测试配置 (预计总耗时: 20-40分钟)"
echo "=========================================="
echo "功率点: 140W, 170W (仅2个)"
echo "模拟时间: 350 μs (原来的一半)"
echo "网格尺寸: 40×120×40 (原来: 60×160×60)"
echo "总加速比: ~15倍"
echo ""
echo "运行测试..."
echo ""

python main.py --method bayes --n-batches 1 --batch-size 1 --n-proc 12 --verbose

echo ""
echo "=========================================="
echo "测试完成！检查结果："
echo "=========================================="

# 检查是否生成了归档目录
if ls runs/*/140W 2>/dev/null | head -1; then
    echo "✓ 归档功能正常 - 发现 140W 目录"
    latest_run=$(ls -td runs/*/ 2>/dev/null | head -1)
    echo "  最新运行: $latest_run"
    ls -lh "$latest_run"
else
    echo "✗ 未找到归档目录"
fi

# 检查CSV
if [ -f bayes_history.csv ]; then
    echo ""
    echo "✓ 优化历史已更新"
    echo "  总记录数: $(wc -l < bayes_history.csv)"
    echo "  最后一行:"
    tail -1 bayes_history.csv | cut -d',' -f1-5
fi

echo ""
echo "=========================================="
echo "记得测试完成后运行: ./恢复测试配置.sh"
echo "=========================================="

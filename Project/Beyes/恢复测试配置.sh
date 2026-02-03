#!/bin/bash
# 恢复原始配置脚本

echo "正在恢复原始配置..."

# 恢复实验数据（5个功率点）
cp experimental_data.csv.backup experimental_data.csv
echo "✓ 恢复 experimental_data.csv (5个功率点)"

# 恢复模拟时间（700e-6）
cp system/controlDict.backup system/controlDict
echo "✓ 恢复 system/controlDict (endTime=700e-6)"

# 恢复网格配置（60×160×60）
cp system/blockMeshDict.backup system/blockMeshDict
echo "✓ 恢复 system/blockMeshDict (60×160×60 = 576,000 单元)"

echo ""
echo "原始配置已恢复！"
echo "  - 功率点: 140, 170, 200, 230, 260 W"
echo "  - 模拟时间: 700 μs"
echo "  - 网格尺寸: 60×160×60 (576,000 单元)"

# 显示差异
echo ""
echo "实验数据对比:"
echo "备份文件 (原始):"
head -3 experimental_data.csv.backup
echo "当前文件:"
head -3 experimental_data.csv

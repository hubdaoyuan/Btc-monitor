#!/bin/bash
# BTC价格监控运行脚本

# 设置脚本目录为工作目录
cd "$(dirname "$0")"

# 检查Python环境
echo "🔍 检查Python环境..."

# 尝试使用python3
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "❌ 错误：未找到Python环境"
    exit 1
fi

echo "✅ 使用Python: $PYTHON_CMD"

# 安装依赖
echo "📦 安装依赖..."
$PYTHON_CMD -m pip install -q requests pandas numpy matplotlib 2>/dev/null || pip install -q requests pandas numpy matplotlib 2>/dev/null

# 加载环境变量
if [ -f .env ]; then
    echo "📋 加载环境变量..."
    export $(grep -v '^#' .env | xargs)
fi

# 运行监控脚本
echo "🚀 启动BTC监控..."
echo "================================"
$PYTHON_CMD btc_monitor.py

echo ""
echo "================================"
echo "✅ 监控完成"

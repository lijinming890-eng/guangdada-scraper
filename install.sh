#!/bin/bash
set -e

echo "============================================"
echo "  广大大买量素材爬虫 - 一键安装"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 未安装！请先安装 Python 3.10+"
    exit 1
fi

echo "[1/3] 安装 Python 依赖..."
pip3 install -r requirements.txt

echo ""
echo "[2/3] 安装 Playwright 浏览器..."
python3 -m playwright install chromium

echo ""
echo "[3/3] 创建配置文件..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "已创建 .env 文件，请编辑填入你的账号信息"
else
    echo ".env 文件已存在，跳过"
fi

echo ""
echo "============================================"
echo "  安装完成！"
echo "============================================"
echo ""
echo "下一步："
echo "  1. 编辑 .env 文件，填入广大大账号"
echo "  2. 运行: python3 -m src.cli login"
echo "  3. 测试: python3 -m src.cli scrape --media-type '图片' --top 5 --chat-output"
echo ""
echo "详细说明请查看 README.md"

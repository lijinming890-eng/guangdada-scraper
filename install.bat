@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   广大大买量素材爬虫 - 一键安装
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装！请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/3] 安装 Playwright 浏览器...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Playwright 浏览器安装失败
    pause
    exit /b 1
)

echo.
echo [3/3] 创建配置文件...
if not exist ".env" (
    copy .env.example .env
    echo 已创建 .env 文件，请编辑填入你的账号信息
) else (
    echo .env 文件已存在，跳过
)

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 下一步：
echo   1. 编辑 .env 文件，填入广大大账号
echo   2. 运行: python -m src.cli login
echo   3. 测试: python -m src.cli scrape --media-type "图片" --top 5 --chat-output
echo.
echo 详细说明请查看 README.md
echo.
pause

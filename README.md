# 广大大买量素材爬虫 (Guangdada Ad Creative Scraper)

自动爬取 [广大大](https://guangdada.net) 展示广告买量素材，按展示估值排序取 TOP N，支持：

- 图片/视频素材爬取
- AI 视觉创意分析（Kimi）
- 飞书消息卡片推送（带图片嵌入）
- 飞书文档导出
- 每日定时自动爬取（通过 OpenClaw cron）

---

## 快速开始

### 1. 环境要求

- **Python 3.10+**
- **Windows / macOS / Linux**

### 2. 一键安装

**Windows:**
```bat
install.bat
```

**macOS / Linux:**
```bash
chmod +x install.sh && ./install.sh
```

**手动安装:**
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. 配置账号

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env` 文件，填入广大大账号：
```
GDD_USERNAME=你的广大大账号
GDD_PASSWORD=你的广大大密码
```

然后登录保存凭据（加密存储在本地）：
```bash
python -m src.cli login
```

### 4. 开始爬取

```bash
# 图片 TOP20
python -m src.cli scrape --media-type "图片" --top 20 --chat-output

# 视频 TOP10
python -m src.cli scrape --media-type "视频" --top 10 --chat-output

# 图片 + AI 分析
python -m src.cli scrape --media-type "图片" --top 10 --analyze --chat-output
```

---

## 目录结构

```
guangdada-scraper/
├── src/                     # 核心源码
│   ├── cli.py               # CLI 入口
│   ├── scraper.py           # Playwright 爬虫核心
│   ├── image_downloader.py  # 图片下载
│   ├── ai_analyzer.py       # Kimi AI 视觉分析
│   ├── analyzer.py          # 数据分析报告
│   ├── feishu_publisher.py  # 飞书文档发布
│   ├── credential_store.py  # 加密凭据存储
│   ├── config.py            # 配置加载
│   └── library_pusher.py    # 图库推送
├── daily_push.py            # 定时推送脚本（爬取+飞书发送一键完成）
├── send_to_feishu.py        # 独立飞书发送工具
├── SKILL.md                 # OpenClaw 技能定义
├── config.yaml              # 爬虫配置
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板
├── install.bat              # Windows 一键安装
├── install.sh               # Linux/Mac 一键安装
└── README.md                # 本文件
```

---

## CLI 命令参考

```bash
# 登录
python -m src.cli login

# 爬取素材
python -m src.cli scrape [OPTIONS]

# 搜索游戏
python -m src.cli search "游戏名" --top 10
```

### scrape 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-n, --top` | 抓取数量，0=全部 | 0 |
| `-m, --media-type` | 素材类型：图片/视频/轮播/html | 全部 |
| `-s, --saved-filter` | 筛选预设名称 | 自动（图片→买量筛选，视频→买量视频） |
| `--analyze` | 启用 AI 视觉分析 | 关闭 |
| `--chat-output` | 输出 JSON 格式（推荐） | 关闭 |
| `--export-feishu` | 导出飞书文档 | 关闭 |
| `--no-download` | 跳过图片下载 | 关闭 |
| `--no-headless` | 显示浏览器窗口（调试） | 关闭 |

---

## 飞书推送配置

如果需要自动推送结果到飞书，需要配置飞书应用：

### 1. 创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. 添加权限：
   - `im:message:send_as_bot` （发送消息）
   - `im:image` （上传图片）
4. 记录 App ID 和 App Secret

### 2. 获取用户 Open ID

在飞书开放平台的 API 调试工具中，调用获取用户信息接口，获取你的 `open_id`（格式：`ou_xxxx`）

### 3. 配置环境变量

编辑 `.env` 文件：
```
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxx
FEISHU_USER_OPEN_ID=ou_xxxx
```

### 4. 测试推送

```bash
# 爬取 + 自动推送到飞书（带图片）
python daily_push.py --media-type "图片" --top 5
```

---

## AI 分析配置

使用 Kimi AI 进行视觉创意分析，需要 API Key：

1. 注册 [Kimi 开放平台](https://platform.moonshot.cn/)
2. 获取 API Key
3. 在 `.env` 中配置：
   ```
   KIMI_API_KEY=your_api_key
   ```
4. 爬取时加 `--analyze` 参数

---

## OpenClaw 集成

### 方式一：作为 OpenClaw 技能使用

1. 将整个 `guangdada-scraper` 文件夹复制到 OpenClaw 的 skills 目录：
   ```
   ~/.openclaw/workspace/skills/guangdada-scraper/
   ```

2. 确保 `SKILL.md` 在目录根部

3. OpenClaw 会自动识别并加载技能

4. 在飞书/Slack 对话中直接说：
   - "爬取买量图片 TOP20"
   - "分析买量素材"
   - "设置每日定时爬取"

### 方式二：配置定时爬取（cron）

`daily_push.py` 是完全独立的一键脚本，不依赖 AI 模型编排：

```bash
# 图片 TOP20 → 飞书推送
python daily_push.py --media-type "图片" --top 20

# 视频 TOP20 → 飞书推送
python daily_push.py --media-type "视频" --top 20
```

#### 通过 OpenClaw cron 定时：

```bash
# 每天 9:00 图片 TOP20
openclaw cron add \
  --name "daily-guangdada-image" \
  --cron "0 9 * * *" \
  --tz "Asia/Shanghai" \
  --timeout-seconds 600 \
  --message "用exec工具执行: python daily_push.py --media-type 图片 --top 20, working_directory设为skills/guangdada-scraper的绝对路径"

# 每天 9:15 视频 TOP20
openclaw cron add \
  --name "daily-guangdada-video" \
  --cron "15 9 * * *" \
  --tz "Asia/Shanghai" \
  --timeout-seconds 600 \
  --message "用exec工具执行: python daily_push.py --media-type 视频 --top 20, working_directory设为skills/guangdada-scraper的绝对路径"
```

#### 通过系统任务计划（不依赖 OpenClaw）：

**Windows 任务计划程序：**
```bat
schtasks /create /tn "guangdada-image" /tr "python C:\path\to\daily_push.py --media-type 图片 --top 20" /sc daily /st 09:00
schtasks /create /tn "guangdada-video" /tr "python C:\path\to\daily_push.py --media-type 视频 --top 20" /sc daily /st 09:15
```

**Linux crontab：**
```bash
# crontab -e
0 9 * * * cd /path/to/guangdada-scraper && python3 daily_push.py --media-type "图片" --top 20
15 9 * * * cd /path/to/guangdada-scraper && python3 daily_push.py --media-type "视频" --top 20
```

---

## 常见问题

### Q: 爬取时间太长？
- 默认爬取 30 页（约 1000 条数据），耗时 4-7 分钟
- 可以减少 `--top` 数量加快速度

### Q: 视频 URL 提取失败？
- 视频 URL 通过点击卡片提取，成功率约 85%
- 部分视频可能因页面动态变化而提取失败，属正常现象

### Q: 登录失败？
- 确认广大大账号密码正确
- 尝试 `python -m src.cli login` 重新登录
- 使用 `--no-headless` 查看浏览器界面排查

### Q: 飞书推送失败？
- 确认 App ID / App Secret 正确
- 确认应用有 `im:message:send_as_bot` 和 `im:image` 权限
- 确认 Open ID 正确（`ou_` 开头）

---

## License

MIT

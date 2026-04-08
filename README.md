# 广大大买量素材爬虫 (Guangdada Scraper)

> 🎯 手游买量广告素材爬取工具 — 自动登录广大大，智能筛选买量素材，一键生成飞书文档报告。

## 功能特性

- **智能买量筛选**：自动应用"买量筛选/买量视频"预设，精准过滤游戏广告素材
- **全局数据排序**：爬取最多 15 页数据，按展示估值从高到低排序，取最优 Top N
- **视频原生播放**：自动提取 .mp4 链接，上传飞书云盘，文档内可直接播放
- **AI 创意分析**：Kimi k2p5 视觉模型 8 维度专业分析（素材类型、视觉风格、核心卖点、综合评分等）
- **飞书文档输出**：一键生成结构化飞书云文档，完成后自动返回链接
- **凭据加密存储**：Fernet (AES-128-CBC) 加密，密钥与密文分离

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| Playwright | 浏览器自动化爬取 |
| Kimi k2p5 | AI 视觉创意分析 |
| 飞书 Docx API | 文档创建与发布 |
| 飞书 Drive API | 视频上传云盘 |
| Fernet | 凭据加密存储 |
| Click + Rich | CLI 交互与美化输出 |

## 快速开始

### 前置要求

- [OpenClaw](https://github.com/nicepkg/openclaw) 已安装并运行
- Python 3.10+
- 广大大账号（guangdada.net）
- Kimi API Key（AI 分析功能可选）

### 安装步骤

**1. 克隆仓库到 OpenClaw skills 目录**

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/lijinming890-eng/guangdada-scraper.git
cd guangdada-scraper
```

**2. 安装依赖**

```bash
pip install -r requirements.txt
playwright install chromium
```

**3. 存储广大大登录凭据**

```bash
python -m src.cli login --username 你的邮箱 --password 你的密码
```

**4. 配置 Kimi API Key（可选，AI 分析需要）**

编辑 `~/.openclaw/agents/main/agent/auth-profiles.json`：

```json
{
  "profiles": {
    "kimi-coding:default": {
      "key": "你的 Kimi API Key"
    }
  }
}
```

**5. 验证安装**

```bash
python -m src.cli doctor
python -m src.cli check-auth
```

### 飞书配置

确认 `~/.openclaw/openclaw.json` 中飞书已启用：

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "你的飞书 App ID",
      "appSecret": "你的飞书 App Secret"
    }
  }
}
```

飞书应用需要的权限：`docx:document`、`drive:drive`

## 使用说明

### 通过飞书对话（推荐）

在飞书中对 OpenClaw 机器人发消息即可触发：

| 你说 | 效果 |
|------|------|
| "帮我爬取广大大买量素材" | 图片 Top 10 → 飞书文档 |
| "抓取视频素材 Top 10" | 视频 Top 10 → 飞书文档 |
| "分析图片素材" | 图片 Top 10 + AI 分析 → 飞书文档 |
| "爬取视频素材并分析" | 视频 Top 10 + AI 分析 → 飞书文档 |

完成后 AI 自动返回飞书文档链接。

### 命令行执行

```bash
# 图片素材 Top 10
python -m src.cli scrape --media-type "图片" --top 10 --export-feishu

# 视频素材 Top 10
python -m src.cli scrape --media-type "视频" --top 10 --export-feishu

# 图片 + AI 分析
python -m src.cli scrape --media-type "图片" --top 10 --analyze --export-feishu

# 仅本地报告（不导出飞书）
python -m src.cli scrape --media-type "图片" --top 10
```

### 自动筛选规则

| 媒体类型 | 自动预设 | 排序方式 |
|---------|---------|---------|
| 图片 | "买量筛选" | 展示估值 ↓ |
| 视频 | "买量视频" | 展示估值 ↓ |

### 执行时间

| 场景 | 耗时 |
|------|------|
| 图片 Top 10 | 2-4 分钟 |
| 视频 Top 10 | 4-8 分钟 |
| + AI 分析 | 额外 1-3 分钟 |

## 项目结构

```
guangdada-scraper/
├── SKILL.md                  # OpenClaw 技能定义
├── DEVLOG.md                 # 开发日志
├── README.md                 # 项目说明
├── requirements.txt          # Python 依赖
├── config.yaml.template      # 配置模板
├── src/
│   ├── cli.py                # CLI 入口（编排全流程）
│   ├── scraper.py            # Playwright 爬虫核心
│   ├── ai_analyzer.py        # Kimi AI 视觉分析
│   ├── analyzer.py           # Markdown 报告生成
│   ├── feishu_publisher.py   # 飞书文档发布 + 视频上传
│   ├── image_downloader.py   # 图片下载器
│   ├── credential_store.py   # 凭据加密管理
│   └── config.py             # 配置加载器
├── output/                   # 爬取结果（自动生成）
└── test/                     # 单元测试
```

## 工作原理

1. **登录**：使用加密凭据自动登录广大大，Cookie 复用免重复登录
2. **筛选**：根据媒体类型自动应用"买量筛选"或"买量视频"预设
3. **爬取**：Playwright 翻页爬取（最多 15 页），模拟滚动加载懒加载内容
4. **排序**：全部数据按展示估值降序排列，取 Top N 条
5. **下载**：下载素材图片到本地；视频额外提取 .mp4 播放链接
6. **AI 分析（可选）**：将图片以 base64 发送给 Kimi k2p5 视觉模型，获取 8 维度创意分析
7. **生成报告**：输出结构化 Markdown 报告
8. **发布飞书**：视频先上传飞书云盘，再创建飞书云文档，返回链接

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| Browser not found | `playwright install chromium` |
| 登录出现验证码 | 加 `--no-headless` 手动验证 |
| AI 分析报错 | 检查 `auth-profiles.json` 中 Kimi API Key |
| 视频无法播放 | 确认飞书应用有 `drive:drive` 权限 |
| OpenClaw 不执行命令 | 重启 gateway，确认 SKILL.md 存在 |

## 更新

```bash
cd ~/.openclaw/workspace/skills/guangdada-scraper
git pull origin master
pip install -r requirements.txt
```

## 许可证

MIT

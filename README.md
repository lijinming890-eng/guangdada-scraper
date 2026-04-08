# guangdada-scraper

广大大 (guangdada.net / SocialPeta) 手游买量素材爬虫，封装为 [OpenClaw](https://github.com/nicepkg/openclaw) Skill。

自动登录广大大 → 应用买量筛选预设 → 多页爬取素材 → 按展示估值排序 → 下载图片/视频 → AI 创意分析 → 生成报告并导入飞书文档。

## 功能特性

- **智能爬取**：自动应用买量筛选预设，爬取最多 15 页数据，按展示估值全局排序取 Top N
- **图片/视频支持**：图片直接下载，视频提取 .mp4 播放链接并上传飞书云盘
- **AI 创意分析**：使用 Kimi k2p5 视觉模型，8 维度专业分析（素材类型、视觉风格、核心卖点、文字信息、目标受众、创意亮点、优化建议、综合评分）
- **飞书集成**：自动创建飞书云文档，视频在文档内可直接点击播放
- **凭据加密**：Fernet (AES-128-CBC + HMAC-SHA256) 加密存储账号密码
- **Cookie 复用**：首次登录后保存浏览器状态，后续免重复登录
- **反爬策略**：随机延时、UA 伪装、模拟滚动、验证码 headful 降级

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 存储登录凭据

```bash
python -m src.cli login --username your_email@example.com --password your_password
```

### 3. 运行爬虫

```bash
# 图片素材 Top 10，导出飞书文档
python -m src.cli scrape --media-type "图片" --top 10 --export-feishu

# 视频素材 Top 10，导出飞书文档
python -m src.cli scrape --media-type "视频" --top 10 --export-feishu

# 图片素材 + AI 创意分析
python -m src.cli scrape --media-type "图片" --top 10 --analyze --export-feishu

# 视频素材 + AI 创意分析
python -m src.cli scrape --media-type "视频" --top 10 --analyze --export-feishu
```

### 4. 环境诊断

```bash
python -m src.cli doctor
```

## 自动筛选规则

| 媒体类型 | 自动选择预设 |
|---------|------------|
| 图片 | "买量筛选" |
| 视频 | "买量视频" |

- 抓取全部页面后按**展示估值**从高到低排序，取前 N 条
- 不是简单取前 N 条，而是从所有数据中筛选最优

## 作为 OpenClaw Skill 使用

已内置为 OpenClaw 技能。在飞书中对 AI 说以下任意关键词即可触发：

- "帮我爬取广大大买量素材"
- "抓取本周图片素材 Top 10"
- "分析视频买量素材"
- "创意分析素材"

AI 会自动调用 exec 工具执行对应命令。

## CLI 命令参考

### 凭据管理

```bash
python -m src.cli login --username xxx --password yyy   # 加密存储凭据
python -m src.cli logout                                 # 清除凭据
python -m src.cli check-auth                             # 验证凭据有效性
```

### 爬取参数

| 参数 | 说明 | 默认值 |
|------|------|-------|
| `--media-type` | "图片" 或 "视频" | 全部 |
| `--top` | 取排名前 N 条 | 10 |
| `--analyze` | 启用 AI 视觉分析 | 关 |
| `--export-feishu` | 导出到飞书文档 | 关 |
| `--no-headless` | 有头模式（调试用） | 无头 |
| `--no-download` | 不下载图片 | 下载 |
| `--output-dir` | 输出目录 | output/guangdada |
| `--saved-filter` | 筛选预设名 | 自动 |
| `--period` | 时间维度 | weekly |
| `--time-range` | 时间范围 | - |

## 执行时间预估

| 场景 | 预估时间 |
|------|---------|
| 图片素材 | 2-4 分钟 |
| 视频素材 | 4-8 分钟 |
| +AI 分析 | 额外 1-3 分钟 |

## 项目结构

```
guangdada-scraper/
├── README.md                    # 本文件
├── SKILL.md                     # OpenClaw Skill 定义
├── DEVLOG.md                    # 开发日志
├── requirements.txt             # Python 依赖
├── config.yaml.template         # 配置模板
├── src/
│   ├── __init__.py
│   ├── __main__.py              # python -m src 入口
│   ├── cli.py                   # CLI 编排（登录/爬取/分析/发布）
│   ├── config.py                # 配置加载器
│   ├── credential_store.py      # Fernet 加密凭据管理
│   ├── scraper.py               # Playwright 浏览器自动化爬虫
│   ├── image_downloader.py      # 图片下载
│   ├── analyzer.py              # Markdown 报告生成
│   ├── ai_analyzer.py           # Kimi AI 视觉创意分析
│   └── feishu_publisher.py      # 飞书文档发布 + 视频云盘上传
├── test/                        # 单元测试
├── examples/                    # 配置示例
└── output/                      # 爬取结果输出
```

## 架构

```
┌─────────────────────────────────────────────────┐
│                     CLI (cli.py)                 │
│   login | scrape | analyze | publish | doctor    │
└──────────────────┬──────────────────────────────┘
                   │
     ┌─────────────┼──────────────┐
     ▼             ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│Credential│ │ Scraper  │ │ AI Analyzer  │
│  Store   │ │(Playwright)│ │  (Kimi k2p5) │
└──────────┘ └────┬─────┘ └──────────────┘
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│  Image   │ │ Markdown │ │    Feishu    │
│Downloader│ │  Report  │ │  Publisher   │
└──────────┘ └──────────┘ └──────────────┘
```

## 依赖

| 包 | 用途 |
|---|------|
| playwright | 浏览器自动化 |
| click | CLI 框架 |
| rich | 终端美化输出 |
| requests | 图片下载 / API 调用 |
| cryptography | Fernet 加密凭据存储 |
| Pillow | 图片分析 |
| PyYAML | 配置文件解析 |

Python 3.9+（推荐 3.10+）

## 常见问题

**Q: 报 "Browser not found"**
A: 运行 `playwright install chromium`

**Q: 登录时出现验证码**
A: 使用 `--no-headless` 以有头模式运行，手动完成验证

**Q: 爬取超时**
A: 检查网络连接，或尝试减少 `--top` 数量

**Q: AI 分析报 API 错误**
A: 检查 `auth-profiles.json` 中的 Kimi API key 是否有效

**Q: 视频在飞书文档中无法播放**
A: 视频会自动上传到飞书云盘并生成链接，点击链接即可播放

## License

MIT

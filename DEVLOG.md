# 开发日志 (DEVLOG)

> 广大大买量素材爬虫 - 完整开发记录
> 由 Cursor IDE 聊天记录整理，2026-04-07

---

## v5.0.0 (2026-04-03) — AI 创意视觉分析

### 新增文件
- `src/ai_analyzer.py` — AI 视觉分析模块

### 功能
- **AI 视觉分析**：使用 Kimi k2p5 视觉模型对素材图片做 8 维度专业分析
  - 素材类型（截图/角色/UGC/漫画/真人/对比/数据展示等）
  - 视觉风格（配色/构图/感受）
  - 核心卖点（画面/玩法/福利/情感等）
  - 文字信息（内容/占比/排版）
  - 目标受众
  - 创意亮点
  - 优化建议
  - 综合评分（1-10 分）
- CLI 新增 `--analyze` 标志
- 分析结果嵌入 Markdown 报告和飞书文档

### 技术实现
- Kimi API: `https://api.kimi.com/coding/v1/messages`
- 认证: 从 `auth-profiles.json` 读取 Kimi API key
- 图片编码: base64 + media_type 自动检测
- 请求格式: Anthropic messages API (`x-api-key` + `anthropic-version: 2023-06-01`)
- 超时: 120 秒
- 错误处理: 超时、HTTP 错误、通用异常均有 fallback

### 修改的文件
- `src/cli.py`: 添加 `--analyze` option，集成 AI 分析步骤
- `src/analyzer.py`: 报告中追加 AI 分析结果块
- `SKILL.md`: 更新到 v5.0.0，新增 AI 分析命令模式

---

## v4.0.0 (2026-04-02) — 视频播放 + 飞书云盘上传

### 问题
飞书文档中视频显示为静态图片，无法播放

### 解决方案
1. **视频 URL 提取** (`scraper.py`):
   - `_enrich_video_urls` 重构：每个 item 记录原始页码 `_page`
   - 按页分组，只回访有视频的页面
   - `_goto_page`: 支持按钮点击和 quick-jumper 输入框跳转
   - `_click_card_extract_video`: 点击卡片 → 弹窗中提取 video src → 关闭弹窗
   - 同一页多个视频之间加 scroll-to-top + 500ms 延迟

2. **飞书云盘上传** (`feishu_publisher.py`):
   - `_get_root_folder_token`: 获取根目录 token
   - `_upload_file_to_drive`: 上传 .mp4 到飞书云盘 (`drive/v1/files/upload_all`)
   - `_replace_video_urls_with_drive`: 预处理 Markdown，将 CDN URL 替换为 `https://feishu.cn/file/{token}`
   - 在 `import_markdown_to_feishu` 中先做 URL 替换再构建 blocks

3. **链接格式** (`feishu_publisher.py`):
   - `_text_elements` 中所有 URL 使用 `urllib.parse.quote` 编码
   - Markdown `[text](url)` 正确解析为飞书可点击链接

### 放弃的方案
- ~~飞书 Docx API block_type: 23 (file block)~~ → API 返回 "invalid param"
- ~~block_type: 33~~ → 同样不支持
- 最终采用：上传云盘 + 链接引用

---

## v3.0.0 (2026-04-01) — 全局排序 + 多页爬取

### 问题
1. 只取前 10 条，不是数据最好的 10 条
2. 排序用的是人气值，应该用展示估值

### 解决方案
1. **多页爬取**: `_extract_with_pagination` 最多爬 15 页
2. **全局排序**: `_sort_by_impressions` 按展示估值降序
3. **懒加载处理**: `_scroll_to_load_all` 滚动加载所有卡片
4. **数值解析增强**: `_parse_numeric` 支持 K/M/万/亿 后缀
5. **卡片提取容错**: 即使图片未加载也提取其他数据

---

## v2.0.0 (2026-04-01) — 买量筛选 + 动态标签

### 问题
爬虫返回通用广告（博彩、新闻等），不是游戏买量素材

### 解决方案
1. **自动筛选预设**: 根据 `--media-type` 自动设置 `--saved-filter`
   - 图片 → "买量筛选"
   - 视频 → "买量视频"
2. **表格显示**: 始终显示"展示估值"和"人气值"列

---

## 架构

```
用户请求 (飞书/CLI)
    │
    ▼
cli.py (编排)
    │
    ├── scraper.py
    │   ├── 登录 (Cookie 复用)
    │   ├── 应用筛选预设
    │   ├── 多页爬取 + 懒加载
    │   ├── 全局排序 (展示估值)
    │   └── 视频 URL 提取 (翻页回溯)
    │
    ├── image_downloader.py
    │   └── 下载图片/缩略图到本地
    │
    ├── ai_analyzer.py (可选)
    │   └── Kimi k2p5 视觉分析
    │
    ├── analyzer.py
    │   └── 生成 Markdown 报告
    │
    └── feishu_publisher.py
        ├── 视频上传飞书云盘
        ├── Markdown → Docx blocks
        └── 创建飞书文档
```

## 关键配置路径

| 项目 | 路径 |
|------|------|
| 技能目录 | `~/.openclaw/workspace/skills/guangdada-scraper/` |
| 凭据存储 | `~/.openclaw/credentials/guangdada.*` |
| Cookie 状态 | `~/.openclaw/guangdada_state/` |
| Kimi API Key | `~/.openclaw/agents/main/agent/auth-profiles.json` → `profiles.kimi-coding:default.key` |
| 飞书 App | openclaw.json → `channels.feishu` |
| 输出目录 | `~/.openclaw/workspace/skills/guangdada-scraper/output/guangdada/` |

## 踩坑记录

### 1. OpenClaw exec 工具不执行
- **现象**: AI 收到请求后只回复文字，不执行命令
- **原因**: SKILL.md 中命令太复杂（含 `cd` + `&&` 链式命令）
- **解决**: 简化为单条 `python -m src.cli ...`，用 `working_directory` 参数指定目录

### 2. 飞书视频 block 创建失败
- **现象**: `block_type: 23` (file) 和 `block_type: 33` 均返回 "invalid param"
- **原因**: 飞书 Docx API 不支持通过 children create 接口创建文件类型 block
- **解决**: 改为上传到飞书云盘，用链接引用

### 3. 页面翻页卡住
- **现象**: 爬取超过 12 分钟无响应
- **原因**: `top=0` 时试图爬取所有页面（可能上百页）
- **解决**: 限制最多 15 页

### 4. 同一页多视频提取失败
- **现象**: 同一页有多个视频时，第 2+ 个提取失败
- **原因**: 关闭弹窗后页面滚动位置不对，找不到下一个卡片
- **解决**: 每次关闭弹窗后 `window.scrollTo(0, 0)` + 500ms 等待

### 5. Windows 控制台中文乱码
- **现象**: AI 分析结果打印时 UnicodeEncodeError
- **解决**: 使用 `errors="replace"` 包装 stdout

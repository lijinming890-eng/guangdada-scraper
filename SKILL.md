---
name: guangdada-scraper
description: |
  爬取广大大展示广告素材，直接在聊天中展示数据和图片，支持 AI 创意视觉分析和每日定时爬取。
  当用户提到"广大大"、"买量素材"、"爬取素材"、"抓取素材"、
  "分析素材"、"创意分析"、"素材分析"、"定时爬取"、"每日爬取"时，
  你必须立刻调用 exec 工具执行命令，不要只回复文字说明。
version: 7.0.0
tags: [guangdada, scraper, ad-creative, socialpeta, feishu, ai-analysis, cron]
---

# 广大大买量素材爬虫

## 重要：必须用 exec 工具执行

收到用户关于广大大/买量素材的请求时，**必须调用 exec 工具**，参数如下：

- command: 下方对应的 python 命令
- working_directory: 本 SKILL.md 所在目录（即 `guangdada-scraper` 目录的绝对路径）

## 命令对照表

### 图片素材（最常用）
```
python -m src.cli scrape --media-type "图片" --top 10 --chat-output
```

### 视频素材
```
python -m src.cli scrape --media-type "视频" --top 10 --chat-output
```

### 图片素材前20条
```
python -m src.cli scrape --media-type "图片" --top 20 --chat-output
```

### 全部素材
```
python -m src.cli scrape --chat-output
```

### 图片素材 + AI 分析
```
python -m src.cli scrape --media-type "图片" --top 10 --analyze --chat-output
```

### 视频素材 + AI 分析
```
python -m src.cli scrape --media-type "视频" --top 10 --analyze --chat-output
```

### 导出到飞书文档（用户明确要求时才用）
```
python -m src.cli scrape --media-type "图片" --top 10 --export-feishu
```

### 搜索游戏
```
python -m src.cli search "游戏名" --top 10
```

## 执行后的反馈流程（重要！必须带图片！）

命令执行完成后，你**必须**按以下步骤操作：

### 第1步：读取结果文件
用 exec 工具执行：
```
python -c "import json; data=json.load(open('output/guangdada/chat_output.json','r',encoding='utf-8')); print(json.dumps(data, ensure_ascii=False))"
```
working_directory 同上。

### 第2步：发送带图片的结果（核心！）

先发一条总览消息：

**📊 广大大买量素材 TOP{N} — {media_type}**
生成时间：{generated_at} | 共 {total} 条素材

然后**逐条发送每个素材**，每条素材包含**文字+图片**：

对每条素材，用 **message** 工具发送，内容格式：

```
**第{rank}名 | {title}**
广告主：{advertiser} | 展示估值：{impressions}
人气值：{popularity} | 投放天数：{days}
时间：{date_range}
```

**发送图片的方法（必须执行！）**：

如果 `local_image` 字段有值（本地图片路径），用 message 工具发送这个图片文件：
- 调用 message 工具，附带图片文件路径 `local_image` 的值
- 例如：message 工具参数中设置 image 或 file 为 local_image 的路径

如果 `local_image` 为空但 `image_url` 有值，把 image_url 作为图片链接发送。

如果有 `video_url`，在文字中附带视频链接。

如果有 `ai_analysis` 字段，追加：
🤖 AI 创意分析：{ai_analysis}

**注意：不要把所有素材合并成一条长消息！每 1-3 条素材发一次消息+图片，让用户能看到图片。**

### 第3步：最后给出总结
发一条汇总消息，简要总结 TOP 素材的趋势（哪些游戏/广告主占比高、创意类型等）。

## 📅 定时爬取设置（cron）— 图片+视频双推送

当用户说"设置定时爬取"、"每天自动爬取"、"定时抓取"时，**必须连续调用 2 次 cron 工具**，分别创建图片和视频任务。

### 任务1：每日 9:00 图片 TOP20

调用 **cron** 工具：

```json
{
  "action": "create",
  "name": "daily-guangdada-image",
  "schedule": "0 9 * * *",
  "prompt": "你是买量素材定时爬取助手。请执行以下步骤：\n\n1. 用 exec 工具执行：python -m src.cli scrape --media-type \"图片\" --top 20 --chat-output\n   working_directory: C:\\Users\\Administrator\\.openclaw\\workspace\\skills\\guangdada-scraper\n\n2. 等待完成后，用 exec 读取结果：python -c \"import json; data=json.load(open('output/guangdada/chat_output.json','r',encoding='utf-8')); print(json.dumps(data, ensure_ascii=False))\"\n   working_directory 同上\n\n3. 用 message 工具发送给用户，格式：\n   📊 每日买量素材 TOP20 — 图片（自动推送）\n   ⏰ {generated_at}\n   逐条展示：排名、标题、广告主、展示估值、人气值、投放天数、图片链接\n   最后一句简短总结\n\n4. 如果失败发送错误提示",
  "channel": "feishu",
  "timezone": "Asia/Shanghai"
}
```

### 任务2：每日 9:05 视频 TOP20

再次调用 **cron** 工具（间隔 5 分钟，避免同时运行冲突）：

```json
{
  "action": "create",
  "name": "daily-guangdada-video",
  "schedule": "5 9 * * *",
  "prompt": "你是买量素材定时爬取助手。请执行以下步骤：\n\n1. 用 exec 工具执行：python -m src.cli scrape --media-type \"视频\" --top 20 --chat-output\n   working_directory: C:\\Users\\Administrator\\.openclaw\\workspace\\skills\\guangdada-scraper\n\n2. 等待完成后，用 exec 读取结果：python -c \"import json; data=json.load(open('output/guangdada/chat_output.json','r',encoding='utf-8')); print(json.dumps(data, ensure_ascii=False))\"\n   working_directory 同上\n\n3. 用 message 工具发送给用户，格式：\n   📊 每日买量素材 TOP20 — 视频（自动推送）\n   ⏰ {generated_at}\n   逐条展示：排名、标题、广告主、展示估值、人气值、投放天数、图片链接、视频链接\n   最后一句简短总结\n\n4. 如果失败发送错误提示",
  "channel": "feishu",
  "timezone": "Asia/Shanghai"
}
```

### 修改定时爬取时间

用户说"改成每天下午2点"，需要更新两个任务：
```json
{"action": "update", "name": "daily-guangdada-image", "schedule": "0 14 * * *"}
```
```json
{"action": "update", "name": "daily-guangdada-video", "schedule": "5 14 * * *"}
```

### 停止定时爬取

用户说"停止定时爬取"，需要删除两个任务：
```json
{"action": "delete", "name": "daily-guangdada-image"}
```
```json
{"action": "delete", "name": "daily-guangdada-video"}
```

### 查看当前定时任务

```json
{"action": "list"}
```

### 常用 cron 时间表达式

| 需求 | 表达式 |
|------|--------|
| 每天早上 9:00 | `0 9 * * *` |
| 每天下午 2:00 | `0 14 * * *` |
| 工作日早上 9:00 | `0 9 * * 1-5` |
| 每周一早上 9:00 | `0 9 * * 1` |
| 每 6 小时一次 | `0 */6 * * *` |

## 自动筛选规则

- 图片 → 自动选"买量筛选"预设
- 视频 → 自动选"买量视频"预设
- 抓取所有页面（无页数限制）后按展示估值从高到低排序，取前 N 条

## 关于 --analyze 参数

- 加上 `--analyze` 后会用 AI 视觉模型分析每张素材图片
- 分析维度：素材类型、视觉风格、核心卖点、文字信息、目标受众、创意亮点、优化建议、综合评分
- 当用户提到"分析素材"、"创意分析"、"素材分析"时，必须加 `--analyze`

## 关于 --chat-output vs --export-feishu

- `--chat-output`（默认推荐）：生成 JSON 文件，由你在聊天中直接展示数据+图片
- `--export-feishu`：生成飞书文档（用户明确要求"导出飞书"或"生成文档"时使用）
- 两者不要同时使用

## 注意

- 图片素材执行时间约 2-4 分钟
- 视频素材执行时间约 4-8 分钟（含视频下载上传飞书云盘）
- 加 `--analyze` 会额外增加 1-3 分钟（每张图片约 10-15 秒）
- 完成后直接在聊天中展示结果，不需要额外链接
- 如果用户说"导出飞书"或"生成文档"，改用 `--export-feishu` 并回复飞书链接
- 定时任务：图片 9:00、视频 9:05（间隔 5 分钟避免冲突），用户可以修改时间

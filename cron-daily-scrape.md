# 每日买量素材定时推送

## 任务一：图片 TOP20（9:00）

cron 工具参数：

```json
{
  "action": "create",
  "name": "daily-guangdada-image",
  "schedule": "0 9 * * *",
  "prompt": "你是买量素材定时爬取助手。请执行以下步骤：\n\n1. 用 exec 工具执行：python -m src.cli scrape --media-type \"图片\" --top 20 --chat-output\n   working_directory: C:\\Users\\Administrator\\.openclaw\\workspace\\skills\\guangdada-scraper\n\n2. 等待完成后，用 exec 读取结果：python -c \"import json; data=json.load(open('output/guangdada/chat_output.json','r',encoding='utf-8')); print(json.dumps(data, ensure_ascii=False))\"\n   working_directory 同上\n\n3. 用 message 工具发送给用户，格式：\n   📊 每日买量素材 TOP20 — 图片（自动推送）\n   ⏰ {generated_at}\n   逐条展示：排名、标题、广告主、展示估值、人气值、投放天数、图片链接\n   最后一句总结\n\n4. 如果失败发送错误提示",
  "channel": "feishu",
  "timezone": "Asia/Shanghai"
}
```

## 任务二：视频 TOP20（9:05）

```json
{
  "action": "create",
  "name": "daily-guangdada-video",
  "schedule": "5 9 * * *",
  "prompt": "你是买量素材定时爬取助手。请执行以下步骤：\n\n1. 用 exec 工具执行：python -m src.cli scrape --media-type \"视频\" --top 20 --chat-output\n   working_directory: C:\\Users\\Administrator\\.openclaw\\workspace\\skills\\guangdada-scraper\n\n2. 等待完成后，用 exec 读取结果：python -c \"import json; data=json.load(open('output/guangdada/chat_output.json','r',encoding='utf-8')); print(json.dumps(data, ensure_ascii=False))\"\n   working_directory 同上\n\n3. 用 message 工具发送给用户，格式：\n   📊 每日买量素材 TOP20 — 视频（自动推送）\n   ⏰ {generated_at}\n   逐条展示：排名、标题、广告主、展示估值、人气值、投放天数、图片链接、视频链接\n   最后一句总结\n\n4. 如果失败发送错误提示",
  "channel": "feishu",
  "timezone": "Asia/Shanghai"
}
```

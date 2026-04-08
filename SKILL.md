---
name: guangdada-scraper
description: |
  爬取广大大展示广告素材并导入飞书文档，支持 AI 创意视觉分析。
  当用户提到"广大大"、"买量素材"、"爬取素材"、"抓取素材"、
  "分析素材"、"创意分析"、"素材分析"时，
  你必须立刻调用 exec 工具执行命令，不要只回复文字说明。
version: 5.0.0
tags: [guangdada, scraper, ad-creative, socialpeta, feishu, ai-analysis]
---

# 广大大买量素材爬虫

## 重要：必须用 exec 工具执行

收到用户关于广大大/买量素材的请求时，**必须调用 exec 工具**，参数如下：

- command: 下方对应的 python 命令
- working_directory: `C:\Users\Administrator\.openclaw\workspace\skills\guangdada-scraper`

## 命令对照表

### 图片素材（最常用）
```
python -m src.cli scrape --media-type "图片" --top 10 --export-feishu
```

### 视频素材
```
python -m src.cli scrape --media-type "视频" --top 10 --export-feishu
```

### 图片素材前20条
```
python -m src.cli scrape --media-type "图片" --top 20 --export-feishu
```

### 全部素材
```
python -m src.cli scrape --export-feishu
```

### 图片素材 + AI 分析
```
python -m src.cli scrape --media-type "图片" --top 10 --analyze --export-feishu
```

### 视频素材 + AI 分析
```
python -m src.cli scrape --media-type "视频" --top 10 --analyze --export-feishu
```

### 搜索游戏
```
python -m src.cli search "游戏名" --top 10
```

## 自动筛选规则

- 图片 → 自动选"买量筛选"预设
- 视频 → 自动选"买量视频"预设
- 抓取全部页面后按展示估值从高到低排序，取前 N 条

## 关于 --analyze 参数

- 加上 `--analyze` 后会用 AI 视觉模型分析每张素材图片
- 分析维度：素材类型、视觉风格、核心卖点、文字信息、目标受众、创意亮点、优化建议、综合评分
- 分析结果直接嵌入飞书文档中每个素材下方
- 当用户提到"分析素材"、"创意分析"、"素材分析"时，必须加 `--analyze`

## 注意

- 图片素材执行时间约 2-4 分钟
- 视频素材执行时间约 4-8 分钟（含视频下载上传飞书云盘）
- 加 `--analyze` 会额外增加 1-3 分钟（每张图片约 10-15 秒）
- 视频会自动上传到飞书云盘，在飞书文档中可直接点击播放
- 完成后把飞书文档链接回复给用户

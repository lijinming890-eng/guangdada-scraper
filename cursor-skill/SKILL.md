---
name: guangdada-scraper
description: |
  爬取广大大展示广告素材并导入飞书文档。
  当用户提到"广大大"、"买量素材"、"爬取素材"、"抓取素材"时，
  你必须立刻调用 exec 工具执行命令，不要只回复文字说明。
version: 4.2.0
tags: [guangdada, scraper, ad-creative, socialpeta, feishu]
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

### 搜索游戏
```
python -m src.cli search "游戏名" --top 10
```

## 自动筛选规则

- 图片 → 自动选"买量筛选"预设
- 视频 → 自动选"买量视频"预设
- 抓取全部页面后按展示估值从高到低排序，取前 N 条

## 注意

- 执行时间 2-6 分钟，请耐心等待不要超时
- 完成后把飞书文档链接回复给用户

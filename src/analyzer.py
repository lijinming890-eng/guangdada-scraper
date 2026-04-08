"""Image analysis and Markdown report generation."""

import os
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml.template"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def analyze_image(image_path: str) -> dict:
    """Extract basic metadata from an image file."""
    info = {"path": image_path, "exists": False}
    p = Path(image_path)
    if not p.exists():
        return info

    info["exists"] = True
    info["size_bytes"] = p.stat().st_size
    info["size_kb"] = round(p.stat().st_size / 1024, 1)

    try:
        with Image.open(p) as img:
            info["width"], info["height"] = img.size
            info["format"] = img.format
            info["mode"] = img.mode
            info["aspect_ratio"] = round(img.size[0] / img.size[1], 2) if img.size[1] else 0
    except Exception:
        pass

    return info


def analyze_items(items: list[dict]) -> list[dict]:
    """Analyze all downloaded images and attach metadata."""
    for item in items:
        local = item.get("local_image", "")
        if local and Path(local).exists():
            item["image_analysis"] = analyze_image(local)
        else:
            item["image_analysis"] = {"exists": False}
    return items


def generate_report(items: list[dict], output_dir: str | None = None) -> str:
    """Generate a Markdown report for analyzed creatives.

    Images are referenced by their original public URLs so that the report
    can be directly written to a Feishu doc via feishu_doc write action
    (Feishu will download and embed them automatically).
    """
    config = _load_config()
    base_dir = Path(output_dir or config["analysis"]["output_dir"])
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = base_dir / f"report_{timestamp}.md"

    lines = [
        f"# 广大大买量素材 TOP{len(items)} 分析报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 概览",
        "",
        f"- 素材总数: **{len(items)}**",
    ]

    with_images = [i for i in items if i.get("image_analysis", {}).get("exists")]
    lines.append(f"- 已下载图片: **{len(with_images)}**")

    if with_images:
        widths = [i["image_analysis"]["width"] for i in with_images if "width" in i.get("image_analysis", {})]
        heights = [i["image_analysis"]["height"] for i in with_images if "height" in i.get("image_analysis", {})]
        if widths:
            lines.append(f"- 平均尺寸: **{int(sum(widths)/len(widths))} x {int(sum(heights)/len(heights))}**")

    sizes = [i["image_analysis"].get("size_kb", 0) for i in with_images]
    if sizes:
        lines.append(f"- 平均文件大小: **{round(sum(sizes)/len(sizes), 1)} KB**")

    lines += ["", "## 素材详情", ""]

    has_popularity = any(item.get("popularity") for item in items)
    if has_popularity:
        lines.append("| 排名 | 标题 | 广告主 | 人气值 | 投放天数 |")
        lines.append("|------|------|--------|--------|----------|")
    else:
        lines.append("| 排名 | 标题 | 广告主 | 展示估值 | 热度 |")
        lines.append("|------|------|--------|----------|------|")

    for item in items:
        rank = item.get("rank", "-")
        title = (item.get("title", "-") or "-")[:35]
        advertiser = (item.get("advertiser", "-") or "-")[:25]
        if has_popularity:
            col3 = item.get("popularity", "-") or "-"
            col4 = item.get("days", "-") or "-"
        else:
            col3 = item.get("impressions", "-") or "-"
            col4 = item.get("heat", "-") or "-"
        lines.append(f"| {rank} | {title} | {advertiser} | {col3} | {col4} |")

    lines += ["", "## 素材预览", ""]
    for item in items:
        img_url = item.get("image_url", "")
        title = item.get("title", "未知")
        rank = item.get("rank", "?")

        if not img_url:
            continue

        lines.append(f"### #{rank} - {title[:40]}")
        lines.append("")
        lines.append(f"![{title[:30]}]({img_url})")
        lines.append("")
        video_url = item.get("video_url", "")
        if video_url:
            lines.append(f"- **[▶ 播放视频]({video_url})**")
        if item.get("advertiser"):
            lines.append(f"- 广告主: {item['advertiser']}")
        lines.append(f"- 展示估值: {item.get('impressions', '-')}")
        lines.append(f"- 人气值: {item.get('popularity', '-')}")
        lines.append(f"- 投放天数: {item.get('days', '-')}")
        if item.get("date_range"):
            lines.append(f"- 投放时间: {item['date_range']}")
        if item.get("heat"):
            lines.append(f"- 热度: {item['heat']}")
        if item.get("last_seen"):
            lines.append(f"- 最后看见: {item['last_seen']}")
        if item.get("ai_tags"):
            lines.append(f"- AI标签: {item['ai_tags']}")

        ai = item.get("ai_analysis")
        if ai:
            lines.append("")
            lines.append("**AI 创意分析：**")
            lines.append("")
            for ai_line in ai.split("\n"):
                stripped = ai_line.strip()
                if stripped:
                    lines.append(stripped)
            lines.append("")

        lines.append("")

    report_content = "\n".join(lines)
    report_path.write_text(report_content, encoding="utf-8")
    return str(report_path)

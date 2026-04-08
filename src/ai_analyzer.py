"""AI vision analysis for ad creatives using Kimi API."""

import base64
import json
from pathlib import Path

import requests

_AUTH_PATH = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
_API_BASE = "https://api.kimi.com/coding"


def _load_api_key() -> str:
    if not _AUTH_PATH.exists():
        raise FileNotFoundError("OpenClaw auth-profiles.json not found")
    data = json.loads(_AUTH_PATH.read_text(encoding="utf-8"))
    key = data.get("profiles", {}).get("kimi-coding:default", {}).get("key", "")
    if not key:
        raise ValueError("Kimi API key not found in auth-profiles.json")
    return key


def _image_to_base64(image_path: str) -> tuple[str, str]:
    """Read image file and return (base64_data, media_type)."""
    p = Path(image_path)
    data = p.read_bytes()
    b64 = base64.standard_b64encode(data).decode("ascii")

    ext = p.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".webp": "image/webp", ".gif": "image/gif"}
    media_type = media_map.get(ext, "image/jpeg")
    return b64, media_type


_ANALYSIS_PROMPT = """你是一位资深的手游买量广告创意分析师。请分析这张广告素材图片，按以下维度给出简洁专业的分析：

1. **素材类型**：是什么类型的创意素材？（如：游戏画面截图、角色展示、UGC风格、漫画风格、真人实拍、对比图、数据展示等）
2. **视觉风格**：配色风格、画面构图、整体视觉感受
3. **核心卖点**：这张素材在传达什么卖点/吸引点？（如：画面精美、玩法展示、福利诱导、情感共鸣等）
4. **文字信息**：图中有哪些文字内容？文字占比和排版如何？
5. **目标受众**：这类素材最可能吸引什么样的玩家？
6. **创意亮点**：有什么值得参考借鉴的创意技巧？
7. **优化建议**：如果要优化这个素材，有什么改进方向？
8. **综合评分**：从买量效果角度，给出 1-10 分评价并简述理由

请直接输出分析结果，每个维度用 1-2 句话概括，保持精炼。"""


def analyze_creative(image_path: str, title: str = "",
                     extra_context: str = "") -> dict:
    """Analyze a single creative image using Kimi vision API.

    Returns {"analysis": str, "error": str | None}.
    """
    api_key = _load_api_key()
    b64_data, media_type = _image_to_base64(image_path)

    prompt = _ANALYSIS_PROMPT
    if title:
        prompt += f"\n\n素材标题: {title}"
    if extra_context:
        prompt += f"\n附加信息: {extra_context}"

    payload = {
        "model": "k2p5",
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }

    try:
        resp = requests.post(
            f"{_API_BASE}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        analysis_text = "\n".join(text_parts).strip()

        return {"analysis": analysis_text, "error": None}

    except requests.exceptions.Timeout:
        return {"analysis": "", "error": "API 请求超时"}
    except requests.exceptions.HTTPError as e:
        return {"analysis": "", "error": f"API 错误: {e.response.status_code}"}
    except Exception as e:
        return {"analysis": "", "error": str(e)}


def analyze_all_creatives(items: list[dict],
                          on_progress=None) -> list[dict]:
    """Analyze all creatives that have local images.

    Adds 'ai_analysis' field to each item.
    """
    total = sum(1 for it in items if it.get("local_image") and Path(it["local_image"]).exists())
    done = 0

    for item in items:
        local = item.get("local_image", "")
        if not local or not Path(local).exists():
            item["ai_analysis"] = None
            continue

        title = item.get("title", "")
        context_parts = []
        if item.get("impressions"):
            context_parts.append(f"展示估值: {item['impressions']}")
        if item.get("popularity"):
            context_parts.append(f"人气值: {item['popularity']}")
        if item.get("days"):
            context_parts.append(f"投放天数: {item['days']}")

        done += 1
        if on_progress:
            on_progress(f"AI 分析 {done}/{total}: {title[:20]}...")

        result = analyze_creative(
            local, title=title, extra_context=", ".join(context_parts),
        )
        item["ai_analysis"] = result.get("analysis") or None

        if result.get("error") and on_progress:
            on_progress(f"  ⚠ {result['error']}")

    return items

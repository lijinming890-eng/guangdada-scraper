"""Push scraped images to the one-click image generation library."""

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Callable

import aiohttp


DEFAULT_API = "http://localhost:3000"


async def push_items_to_library(
    items: list[dict],
    category: str = "reference",
    api_base: str = DEFAULT_API,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """Push scraped items to the one-click image library via batch API.

    Each item should have:
      - image_url (str): remote image URL from guangdada
      - local_image (str, optional): local downloaded file path
      - title (str, optional): used as description
      - rank (int, optional): used in originalName
      - advertiser (str, optional): added to tags
    """
    batch = []
    for item in items:
        image_url = item.get("image_url", "")
        local_path = item.get("local_image", "")
        title = item.get("title", "") or ""
        rank = item.get("rank", 0)
        advertiser = item.get("advertiser", "") or ""
        impressions = item.get("impressions", "") or ""

        tags = [t for t in ["广大大", advertiser, impressions] if t]
        name = f"rank{rank}_{title[:50]}" if title else f"rank{rank}"

        entry: dict = {
            "originalName": name + ".jpg",
            "category": category,
            "tags": tags,
            "description": title,
            "source": "guangdada",
        }

        if local_path and Path(local_path).exists():
            file_path = Path(local_path)
            raw = file_path.read_bytes()
            entry["base64"] = base64.b64encode(raw).decode("ascii")
            entry["mimeType"] = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
        elif image_url:
            entry["imageUrl"] = image_url
        else:
            continue

        batch.append(entry)

    if not batch:
        return {"success": 0, "failed": 0, "total": 0}

    if on_progress:
        on_progress(f"准备推送 {len(batch)} 张图片到图库...")

    chunk_size = 20
    total_success = 0
    total_failed = 0
    total_skipped = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i:i + chunk_size]
            if on_progress:
                on_progress(f"推送第 {i + 1}-{i + len(chunk)} 张 (共 {len(batch)} 张)...")

            try:
                async with session.post(
                    f"{api_base}/api/library/batch",
                    json={"images": chunk},
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        total_success += data.get("success", 0)
                        total_failed += data.get("failed", 0)
                        total_skipped += data.get("skipped", 0)
                    else:
                        total_failed += len(chunk)
                        if on_progress:
                            text = await resp.text()
                            on_progress(f"  批次失败 (HTTP {resp.status}): {text[:200]}")
            except Exception as e:
                total_failed += len(chunk)
                if on_progress:
                    on_progress(f"  批次异常: {e}")

    return {"success": total_success, "failed": total_failed, "skipped": total_skipped, "total": len(batch)}


async def push_directory_to_library(
    directory: str,
    category: str = "reference",
    api_base: str = DEFAULT_API,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """Push all images from a local directory to the library."""
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    image_files = sorted([
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    ])

    if not image_files:
        return {"success": 0, "failed": 0, "total": 0}

    items = []
    for i, f in enumerate(image_files, 1):
        items.append({
            "rank": i,
            "title": f.stem,
            "local_image": str(f),
        })

    return await push_items_to_library(
        items, category=category, api_base=api_base, on_progress=on_progress
    )


def push_items_sync(items: list[dict], **kwargs) -> dict:
    return asyncio.run(push_items_to_library(items, **kwargs))


def push_directory_sync(directory: str, **kwargs) -> dict:
    return asyncio.run(push_directory_to_library(directory, **kwargs))

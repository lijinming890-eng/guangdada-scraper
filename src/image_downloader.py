"""Async batch image downloader for scraped creatives."""

import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import aiofiles
import yaml


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml.template"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)[:100]


async def download_image(session: aiohttp.ClientSession, url: str, dest: Path, timeout: int = 30) -> bool:
    if not url or not url.startswith("http"):
        return False
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 200:
                content = await resp.read()
                async with aiofiles.open(dest, "wb") as f:
                    await f.write(content)
                return True
    except Exception:
        pass
    return False


async def download_all(items: list[dict], output_dir: str | None = None) -> list[dict]:
    """Download all images from scraped items, returns updated items with local paths."""
    config = _load_config()
    base_dir = Path(output_dir or config["download"]["image_dir"])
    base_dir.mkdir(parents=True, exist_ok=True)
    max_concurrent = config["download"]["max_concurrent"]
    timeout = config["download"]["timeout"]

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _download_one(item: dict) -> dict:
        url = item.get("image_url", "")
        if not url:
            item["local_image"] = ""
            return item

        ext = Path(urlparse(url).path).suffix or ".jpg"
        filename = _sanitize_filename(f"rank{item['rank']}_{item.get('title', 'untitled')}{ext}")
        dest = base_dir / filename

        async with semaphore:
            ok = await download_image(session, url, dest, timeout)

        item["local_image"] = str(dest) if ok else ""
        return item

    async with aiohttp.ClientSession() as session:
        tasks = [_download_one(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]

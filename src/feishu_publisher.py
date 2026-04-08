"""Publish analysis reports to Feishu (飞书/Lark) via webhook or Feishu Doc API."""

import io
import json
import re as _re
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
import yaml

BASE_URL = "https://open.feishu.cn/open-apis"


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml.template"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_feishu_creds() -> tuple[str, str]:
    """Load appId / appSecret from OpenClaw config."""
    oc_config = Path.home() / ".openclaw" / "openclaw.json"
    if not oc_config.exists():
        raise FileNotFoundError("openclaw.json not found — cannot read Feishu credentials")
    data = json.loads(oc_config.read_text(encoding="utf-8"))
    ch = data.get("channels", {}).get("feishu", {})
    app_id = ch.get("appId", "")
    app_secret = ch.get("appSecret", "")
    if not app_id or not app_secret:
        raise ValueError("Feishu appId/appSecret not configured in openclaw.json")
    return app_id, app_secret


def _get_tenant_token() -> str:
    app_id, app_secret = _load_feishu_creds()
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant token: {data.get('msg')}")
    return data["tenant_access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_feishu_doc(title: str, folder_token: str | None = None) -> dict:
    """Create a new Feishu document. Returns {"document_id": ..., "title": ...}."""
    token = _get_tenant_token()
    body: dict = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token
    resp = requests.post(
        f"{BASE_URL}/docx/v1/documents",
        headers=_headers(token),
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Create doc failed: {data.get('msg')}")
    doc = data["data"]["document"]
    return {"document_id": doc["document_id"], "title": doc["title"]}


def _text_elements(text: str) -> list[dict]:
    """Build text_run elements, converting bold **x** and links [t](url) to Feishu styles."""
    TOKEN_RE = _re.compile(
        r"(\*\*(?:(?!\*\*).)+\*\*)"
        r"|(\[([^\]]+)\]\((https?://[^)]+)\))"
    )
    elements: list[dict] = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            elements.append({"text_run": {"content": text[pos:m.start()]}})
        if m.group(1):
            inner = m.group(1)[2:-2]
            link_m = _re.match(r"\[([^\]]+)\]\((https?://[^)]+)\)", inner)
            if link_m:
                link_url = quote(link_m.group(2), safe='')
                elements.append({
                    "text_run": {
                        "content": link_m.group(1),
                        "text_element_style": {"bold": True, "link": {"url": link_url}},
                    }
                })
            else:
                elements.append({
                    "text_run": {"content": inner, "text_element_style": {"bold": True}},
                })
        elif m.group(2):
            link_url = quote(m.group(4), safe='')
            elements.append({
                "text_run": {
                    "content": m.group(3),
                    "text_element_style": {"link": {"url": link_url}},
                }
            })
        pos = m.end()
    if pos < len(text):
        elements.append({"text_run": {"content": text[pos:]}})
    return elements or [{"text_run": {"content": text}}]


def _download_file(url: str) -> tuple[bytes, str, str] | None:
    """Download file from URL. Returns (bytes, file_name, content_type) or None."""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except Exception:
        return None

    data = resp.content
    if len(data) < 100:
        return None

    content_type = resp.headers.get("Content-Type", "application/octet-stream")

    parsed = urlparse(url)
    path_name = Path(parsed.path).name or "file"
    # Strip query params from filename
    if "?" in path_name:
        path_name = path_name.split("?")[0]

    return data, path_name, content_type


def _download_image(image_url: str) -> tuple[bytes, str, str] | None:
    """Download image from URL. Returns (bytes, file_name, content_type) or None."""
    result = _download_file(image_url)
    if not result:
        return None

    data, fname, content_type = result
    if "image" not in content_type:
        content_type = "image/jpeg"

    ext = "jpg"
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"
    elif "gif" in content_type:
        ext = "gif"

    stem = Path(fname).stem[:30] or "image"
    return data, f"{stem}.{ext}", content_type


def _get_root_folder_token(token: str) -> str | None:
    """Get the Feishu Drive root folder token."""
    resp = requests.get(
        f"{BASE_URL}/drive/explorer/v2/root_folder/meta",
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data.get("data", {}).get("token")


def _upload_file_to_drive(token: str, file_bytes: bytes, file_name: str,
                           folder_token: str) -> str | None:
    """Upload a file to Feishu Drive. Returns file_token or None."""
    resp = requests.post(
        f"{BASE_URL}/drive/v1/files/upload_all",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "file_name": file_name,
            "parent_type": "explorer",
            "parent_node": folder_token,
            "size": str(len(file_bytes)),
        },
        files={"file": (file_name, io.BytesIO(file_bytes), "video/mp4")},
        timeout=180,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data.get("data", {}).get("file_token")


def _replace_video_urls_with_drive(md_content: str, token: str,
                                    on_progress=None) -> str:
    """Find .mp4 URLs in Markdown, upload to Feishu Drive, replace with Drive links."""
    video_re = _re.compile(r'(https?://[^\s)]+\.mp4)')
    urls = list(set(video_re.findall(md_content)))
    if not urls:
        return md_content

    root_token = _get_root_folder_token(token)
    if not root_token:
        return md_content

    for i, video_url in enumerate(urls):
        if on_progress:
            on_progress(f"视频 {i + 1}/{len(urls)} 下载中...")

        dl = _download_file(video_url)
        if not dl:
            continue
        video_bytes, fname, _ = dl
        if not fname.endswith(".mp4"):
            fname = Path(fname).stem + ".mp4"

        if on_progress:
            on_progress(f"视频 {i + 1}/{len(urls)} 上传飞书云盘 ({len(video_bytes) // 1024}KB)...")

        file_token = _upload_file_to_drive(token, video_bytes, fname, root_token)
        if not file_token:
            continue

        drive_url = f"https://feishu.cn/file/{file_token}"
        md_content = md_content.replace(video_url, drive_url)

        if on_progress:
            on_progress(f"视频 {i + 1}/{len(urls)} 已上传飞书云盘")

    return md_content


def _upload_image_to_block(token: str, block_id: str, img_bytes: bytes,
                            file_name: str, content_type: str,
                            doc_token: str) -> str | None:
    """Upload image to a specific Feishu docx image block.

    Uses parent_node=block_id (the empty image block) per Feishu API requirement.
    Returns file_token or None.
    """
    resp = requests.post(
        f"{BASE_URL}/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "file_name": file_name,
            "parent_type": "docx_image",
            "parent_node": block_id,
            "size": str(len(img_bytes)),
            "extra": json.dumps({"drive_route_token": doc_token}),
        },
        files={"file": (file_name, io.BytesIO(img_bytes), content_type)},
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != 0:
        return None
    return data.get("data", {}).get("file_token")


def _patch_image_block(token: str, document_id: str, block_id: str, file_token: str) -> bool:
    """Set the image token on an existing empty image block via PATCH."""
    resp = requests.patch(
        f"{BASE_URL}/docx/v1/documents/{document_id}/blocks/{block_id}",
        headers=_headers(token),
        json={"replace_image": {"token": file_token}},
        timeout=15,
    )
    if resp.status_code != 200:
        return False
    return resp.json().get("code") == 0



def _md_to_blocks(md_content: str) -> tuple[list[dict], list[tuple[int, str]]]:
    """Convert Markdown to Feishu docx blocks.

    Returns (blocks, image_slots) where image_slots is a list of
    (block_index, image_url) for empty image blocks that need post-processing.
    """
    blocks: list[dict] = []
    image_slots: list[tuple[int, str]] = []
    lines = md_content.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("### "):
            blocks.append({
                "block_type": 5,
                "heading3": {"elements": _text_elements(stripped[4:]), "style": {}},
            })
        elif stripped.startswith("## "):
            blocks.append({
                "block_type": 4,
                "heading2": {"elements": _text_elements(stripped[3:]), "style": {}},
            })
        elif stripped.startswith("# "):
            blocks.append({
                "block_type": 3,
                "heading1": {"elements": _text_elements(stripped[2:]), "style": {}},
            })
        elif stripped.startswith("> "):
            blocks.append({
                "block_type": 15,
                "quote": {"elements": _text_elements(stripped[2:]), "style": {}},
            })
        elif stripped.startswith("- "):
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": _text_elements(stripped[2:]), "style": {}},
            })
        elif _re.match(r"^!\[.*\]\(https?://.*\)$", stripped):
            m = _re.match(r"^!\[(.*?)\]\((https?://[^)]+)\)$", stripped)
            if m:
                url = m.group(2)
                image_slots.append((len(blocks), url))
                blocks.append({"block_type": 27, "image": {}})
        elif stripped.startswith("|"):
            if set(stripped.replace("|", "").replace("-", "").strip()) <= set(" "):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            blocks.append({
                "block_type": 2,
                "text": {"elements": _text_elements("  |  ".join(cells)), "style": {}},
            })
        elif stripped in ("---", "***", "___"):
            blocks.append({"block_type": 22, "divider": {}})
        else:
            blocks.append({
                "block_type": 2,
                "text": {"elements": _text_elements(stripped), "style": {}},
            })

    return blocks, image_slots


def import_markdown_to_feishu(md_content: str, file_name: str = "report.md",
                               folder_token: str | None = None,
                               on_progress=None) -> dict:
    """Create a Feishu document and write Markdown content with embedded images.

    Flow (per Feishu API requirement):
      1. Create document
      2. Insert all blocks (images as empty block_type=27)
      3. For each image block: download → upload with block_id → PATCH to set token

    Returns {"document_id": ..., "url": ..., "images_uploaded": ..., "images_failed": ...}.
    """
    token = _get_tenant_token()
    hdrs = _headers(token)

    title = md_content.split("\n")[0].replace("#", "").strip() or file_name.replace(".md", "")
    body: dict = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token

    resp = requests.post(f"{BASE_URL}/docx/v1/documents", headers=hdrs, json=body, timeout=15)
    resp.raise_for_status()
    doc_data = resp.json()
    if doc_data.get("code") != 0:
        raise RuntimeError(f"Create doc failed: {doc_data.get('msg')}")

    doc = doc_data["data"]["document"]
    document_id = doc["document_id"]

    # Pre-process: upload .mp4 videos to Feishu Drive and replace URLs
    md_content = _replace_video_urls_with_drive(md_content, token, on_progress)

    blocks, image_slots = _md_to_blocks(md_content)

    # Step 1: Insert all blocks (images as empty placeholders).
    all_created_blocks: list[dict] = []
    BATCH = 50
    for start in range(0, len(blocks), BATCH):
        batch = blocks[start:start + BATCH]
        resp = requests.post(
            f"{BASE_URL}/docx/v1/documents/{document_id}/blocks/{document_id}/children",
            headers=hdrs,
            json={"children": batch, "index": -1},
            params={"document_revision_id": -1},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 0:
            raise RuntimeError(
                f"Insert blocks failed (batch {start}): {result.get('msg')} "
                f"(code={result.get('code')})"
            )
        created = result.get("data", {}).get("children", [])
        all_created_blocks.extend(created)

    # Step 2: Find image block_ids (block_type 27).
    image_block_ids: list[str] = []
    for blk in all_created_blocks:
        if blk.get("block_type") == 27:
            image_block_ids.append(blk["block_id"])

    # Step 3: For each image slot, download → upload → patch.
    uploaded = 0
    failed = 0
    total = min(len(image_slots), len(image_block_ids))

    for i in range(total):
        _, img_url = image_slots[i]
        block_id = image_block_ids[i]

        dl = _download_image(img_url)
        if not dl:
            failed += 1
            continue

        img_bytes, fname, ctype = dl
        file_token = _upload_image_to_block(token, block_id, img_bytes, fname, ctype, document_id)
        if not file_token:
            failed += 1
            continue

        ok = _patch_image_block(token, document_id, block_id, file_token)
        if ok:
            uploaded += 1
            if on_progress:
                on_progress(f"图片 {uploaded}/{total} 嵌入成功")
        else:
            failed += 1

    doc_url = f"https://feishu.cn/docx/{document_id}"
    return {
        "document_id": document_id,
        "url": doc_url,
        "images_uploaded": uploaded,
        "images_failed": failed,
    }


# ---------- Legacy webhook methods ----------

def publish_to_feishu(report_path: str, webhook_url: str | None = None) -> bool:
    """Send a report summary to Feishu via incoming webhook."""
    config = _load_config()
    url = webhook_url or config["feishu"].get("webhook_url", "")
    if not url:
        raise ValueError(
            "Feishu webhook URL not configured. "
            "Set it in config.yaml under feishu.webhook_url"
        )

    report = Path(report_path)
    if not report.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    content = report.read_text(encoding="utf-8")
    title_line = content.split("\n")[0].replace("#", "").strip() if content else "广大大素材报告"
    preview = content[:2000]

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title_line},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": preview},
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看完整报告"},
                        "type": "primary",
                        "url": f"file:///{report_path.replace(chr(92), '/')}",
                    }],
                },
            ],
        },
    }

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    return result.get("code", -1) == 0 or result.get("StatusCode", -1) == 0


def publish_text(text: str, webhook_url: str | None = None) -> bool:
    """Send a plain text message to Feishu."""
    config = _load_config()
    url = webhook_url or config["feishu"].get("webhook_url", "")
    if not url:
        raise ValueError("Feishu webhook URL not configured.")

    payload = {"msg_type": "text", "content": {"text": text}}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    return result.get("code", -1) == 0 or result.get("StatusCode", -1) == 0

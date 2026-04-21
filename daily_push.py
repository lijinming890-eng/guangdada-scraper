"""Daily push: scrape + send to Feishu with images. No AI model needed."""
import asyncio
import io
import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import requests

BASE_URL = "https://open.feishu.cn/open-apis"


def _load_env():
    """Load .env file if present."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _load_feishu_creds():
    """Load Feishu credentials: env vars first, then openclaw.json fallback."""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if app_id and app_secret:
        return app_id, app_secret
    oc = Path.home() / ".openclaw" / "openclaw.json"
    if oc.exists():
        data = json.loads(oc.read_text(encoding="utf-8"))
        ch = data.get("channels", {}).get("feishu", {})
        return ch.get("appId", ""), ch.get("appSecret", "")
    return "", ""


def _get_user_open_id():
    return os.environ.get("FEISHU_USER_OPEN_ID", "ou_3eabd73ce2e9eacaa4246f789701ebd1")


def _get_token():
    app_id, app_secret = _load_feishu_creds()
    if not app_id or not app_secret:
        print("ERROR: Feishu credentials not found. Set FEISHU_APP_ID/FEISHU_APP_SECRET or configure openclaw.json")
        sys.exit(1)
    r = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                      json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    return r.json()["tenant_access_token"]


def _upload_image(token, image_path):
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": f},
                timeout=30,
            )
        data = r.json()
        if data.get("code") == 0:
            return data["data"]["image_key"]
    except Exception as e:
        print(f"  Image upload error: {e}")
    return None


def _send_card(token, elements, header_text=None):
    user_id = _get_user_open_id()
    card = {"config": {"wide_screen_mode": True}, "elements": elements}
    if header_text:
        card["header"] = {"title": {"tag": "plain_text", "content": header_text}}
    r = requests.post(
        f"{BASE_URL}/im/v1/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"receive_id_type": "open_id"},
        json={"receive_id": user_id, "msg_type": "interactive",
              "content": json.dumps(card, ensure_ascii=False)},
        timeout=15,
    )
    return r.json().get("code") == 0


def _send_results(token, items, media_type, generated_at):
    total = len(items)
    label = "图片" if media_type == "图片" else "视频"

    _send_card(token, [
        {"tag": "div", "text": {"tag": "plain_text",
                                "content": f"共 {total} 条素材，按展示估值从高到低排序"}}
    ], header_text=f"📊 每日买量素材 TOP{total} — {label}（{generated_at}）")
    print(f"  Header sent")

    batch_size = 5
    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        elements = []
        for item in batch:
            rank = item.get("rank", "")
            title = item.get("title", "")
            adv = item.get("advertiser", "")
            imp = item.get("impressions", "")
            pop = item.get("popularity", "")
            days = item.get("days", "")
            dr = item.get("date_range", "")
            vid = item.get("video_url", "")

            text = f"**第{rank}名 | {title}**\n广告主：{adv}\n展示估值：{imp} | 人气值：{pop} | 投放天数：{days}\n时间：{dr}"
            if vid:
                text += f"\n视频：{vid}"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text}})

            local_img = item.get("local_image", "")
            if local_img and Path(local_img).exists():
                img_key = _upload_image(token, local_img)
                if img_key:
                    elements.append({"tag": "img", "img_key": img_key,
                                     "alt": {"tag": "plain_text", "content": title}})
            elif item.get("image_url"):
                elements.append({"tag": "div", "text": {"tag": "lark_md",
                                                         "content": f"[查看图片]({item['image_url']})"}})
            elements.append({"tag": "hr"})

        ok = _send_card(token, elements)
        ranks = [str(it["rank"]) for it in batch]
        print(f"  {'OK' if ok else 'FAIL'} Batch #{','.join(ranks)}")

    print(f"  All {total} items sent to Feishu")


def main():
    """Scrape + push to Feishu with images (one command, no AI model)."""
    _load_env()
    media_type = "图片"
    top = 20
    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("--media-type", "-m") and i + 1 < len(sys.argv) - 1:
            media_type = sys.argv[i + 2]
        if arg in ("--top", "-n") and i + 1 < len(sys.argv) - 1:
            try:
                top = int(sys.argv[i + 2])
            except ValueError:
                pass
    from src.scraper import run_scrape
    from src.image_downloader import download_all
    from src import credential_store

    creds = credential_store.load_credentials()
    if not creds:
        print("ERROR: No credentials. Run: python -m src.cli login")
        sys.exit(1)

    saved_filter = "买量视频" if media_type == "视频" else "买量筛选"
    print(f"=== Daily Push: {media_type} TOP{top} ===")

    print(f"[1/4] Scraping {media_type} (max 30 pages)...")
    items = asyncio.run(run_scrape(
        top=top, period="weekly", headless=True,
        media_type=media_type, saved_filter=saved_filter,
        on_progress=lambda msg: print(f"  {msg}"),
        max_pages=30,
    ))
    if not items:
        print("ERROR: No items scraped")
        sys.exit(1)
    print(f"  Scraped {len(items)} items")

    print("[2/4] Downloading images...")
    items = asyncio.run(download_all(items))
    downloaded = sum(1 for i in items if i.get("local_image"))
    print(f"  Downloaded {downloaded}/{len(items)} images")

    print("[3/4] Getting Feishu token...")
    token = _get_token()

    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    chat_items = []
    for item in items:
        local_img = item.get("local_image", "")
        if local_img:
            local_img = str(Path(local_img).resolve())
        chat_items.append({
            "rank": item.get("rank", 0),
            "title": item.get("title", ""),
            "advertiser": item.get("advertiser", ""),
            "impressions": item.get("impressions", ""),
            "popularity": item.get("popularity", ""),
            "days": item.get("days", ""),
            "date_range": item.get("date_range", ""),
            "image_url": item.get("image_url", ""),
            "local_image": local_img,
            "video_url": item.get("video_url", ""),
        })

    print(f"[4/4] Sending to Feishu with images...")
    _send_results(token, chat_items, media_type, generated_at)
    print("=== Done ===")


if __name__ == "__main__":
    main()

"""Send chat_output.json results to Feishu with embedded images."""
import io
import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

BASE_URL = "https://open.feishu.cn/open-apis"


def _load_creds():
    oc = Path.home() / ".openclaw" / "openclaw.json"
    data = json.loads(oc.read_text(encoding="utf-8"))
    ch = data["channels"]["feishu"]
    return ch["appId"], ch["appSecret"]


def _get_token():
    app_id, app_secret = _load_creds()
    r = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal",
                      json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    return r.json()["tenant_access_token"]


def _upload_image(token, image_path):
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
    print(f"  Upload failed: {data.get('msg')}", file=sys.stderr)
    return None


def _send_msg(token, chat_id, content, msg_type="interactive"):
    r = requests.post(
        f"{BASE_URL}/im/v1/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"receive_id_type": "open_id"},
        json={"receive_id": chat_id, "msg_type": msg_type, "content": json.dumps(content, ensure_ascii=False)},
        timeout=15,
    )
    data = r.json()
    if data.get("code") != 0:
        print(f"  Send failed: {data.get('msg')}", file=sys.stderr)
    return data.get("code") == 0


def main():
    token = _get_token()
    user_open_id = "ou_3eabd73ce2e9eacaa4246f789701ebd1"

    output_file = Path("output/guangdada/chat_output.json")
    data = json.loads(output_file.read_text(encoding="utf-8"))
    items = data["items"]
    generated_at = data["generated_at"]
    total = data["total"]

    print(f"Sending {total} items to Feishu...")

    header_card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": f"📊 每日买量素材 TOP{total}（{generated_at}）"}},
        "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": f"共 {total} 条素材，按展示估值从高到低排序"}}],
    }
    _send_msg(token, user_open_id, header_card)
    print("✓ Header sent")

    batch_size = 5
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        elements = []
        for item in batch:
            rank = item["rank"]
            title = item["title"]
            adv = item["advertiser"]
            imp = item["impressions"]
            pop = item["popularity"]
            days = item["days"]
            dr = item["date_range"]
            vid = item.get("video_url", "")

            text = f"**第{rank}名 | {title}**\n广告主：{adv}\n展示估值：{imp} | 人气值：{pop} | 投放天数：{days}\n时间：{dr}"
            if vid:
                text += f"\n🎬 视频：{vid}"

            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text}})

            local_img = item.get("local_image", "")
            if local_img and Path(local_img).exists():
                img_key = _upload_image(token, local_img)
                if img_key:
                    elements.append({"tag": "img", "img_key": img_key, "alt": {"tag": "plain_text", "content": title}})
            elif item.get("image_url"):
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"[查看图片]({item['image_url']})"}})

            elements.append({"tag": "hr"})

        card = {
            "config": {"wide_screen_mode": True},
            "elements": elements,
        }
        ok = _send_msg(token, user_open_id, card)
        batch_ranks = [str(it["rank"]) for it in batch]
        status = "✓" if ok else "✗"
        print(f"  {status} Batch #{','.join(batch_ranks)} sent")

    print("✓ All done!")


if __name__ == "__main__":
    main()

"""Playwright-based scraper for guangdada.net ad creatives."""

import asyncio
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

import yaml
from playwright.async_api import async_playwright, Page, Browser

from . import credential_store

URLS = {
    "login": "https://www.guangdada.net/user/login",
    "display_ads": "https://guangdada.net/modules/creative/display-ads",
    "hot_charts": "https://guangdada.net/modules/creative/charts/hot-charts",
    "surge_charts": "https://guangdada.net/modules/creative/charts/surge-charts",
    "new_charts": "https://guangdada.net/modules/creative/charts/new-charts",
}


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml.template"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class GuangdadaScraper:
    def __init__(self, headless: bool | None = None):
        self.config = _load_config()
        self.headless = headless if headless is not None else self.config["scraper"]["headless"]
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.results: list[dict] = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def start(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        ctx = await self.browser.new_context(
            user_agent=self.config["scraper"]["user_agent"],
            viewport={"width": 1920, "height": 1080},
        )
        self.page = await ctx.new_page()
        self.page.set_default_timeout(self.config["scraper"]["timeout"])

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()

    async def login(self) -> bool:
        creds = credential_store.load_credentials()
        if not creds:
            raise RuntimeError("No credentials found. Run: python -m src.cli login")

        page = self.page
        await page.goto(URLS["login"], wait_until="networkidle")
        await page.wait_for_timeout(2000)

        email_input = page.locator(
            'input[type="text"], input[name="email"], '
            'input[placeholder*="邮箱"], input[placeholder*="email"], '
            'input[placeholder*="Email"], input[placeholder*="账号"]'
        ).first
        pwd_input = page.locator('input[type="password"]').first

        await email_input.fill(creds["username"])
        await pwd_input.fill(creds["password"])

        submit = page.locator(
            'button[type="submit"], button:has-text("登录"), button:has-text("Login")'
        ).first
        await submit.click()

        await page.wait_for_timeout(3000)
        if "login" not in page.url.lower():
            return True

        await page.wait_for_url(re.compile(r"(?!.*login)"), timeout=10000)
        return True

    # ------------------------------------------------------------------
    # Main entry: scrape display-ads with optional filters
    # ------------------------------------------------------------------

    async def scrape_top_creatives(self, top: int = 0, period: str = "weekly",
                                    filter_tag: str | None = None,
                                    time_range: str | None = None,
                                    media_type: str | None = None,
                                    saved_filter: str | None = None,
                                    on_progress=None) -> list[dict]:
        page = self.page

        if on_progress:
            on_progress("正在导航到展示广告页面...")
        await page.goto(URLS["display_ads"], wait_until="networkidle")
        await page.wait_for_timeout(3000)

        if on_progress:
            on_progress("正在应用筛选条件...")
        await self._apply_filters(
            page,
            filter_tag=filter_tag,
            time_range=time_range,
            media_type=media_type,
            saved_filter=saved_filter,
        )

        if on_progress:
            on_progress("正在抓取素材数据...")
        items = await self._extract_with_pagination(page, 0, on_progress=on_progress)

        items = self._sort_by_impressions(items)

        if top > 0:
            items = items[:top]

        for i, item in enumerate(items, 1):
            item["rank"] = i

        if media_type == "视频" and items:
            if on_progress:
                on_progress(f"正在提取 {len(items)} 条视频的播放地址...")
            items = await self._enrich_video_urls(page, items, saved_filter=saved_filter)
            enriched = sum(1 for it in items if it.get("video_url"))
            if on_progress:
                on_progress(f"视频提取完成: {enriched}/{len(items)} 条获得播放地址")

        self.results = items
        return items

    @staticmethod
    def _parse_numeric(raw: str) -> float:
        """Parse strings like '1538', '42万', '1.2亿', '12K', '8.8K', '2.3M'."""
        raw = (raw or "").replace(",", "").replace(" ", "").strip()
        if not raw or raw in ("-", "--"):
            return 0
        suffixes = {"亿": 1e8, "万": 1e4, "M": 1e6, "K": 1e3, "k": 1e3, "m": 1e6}
        for suffix, mult in suffixes.items():
            if raw.endswith(suffix):
                try:
                    return float(raw[:-len(suffix)]) * mult
                except ValueError:
                    return 0
        try:
            return float(raw)
        except ValueError:
            return 0

    @classmethod
    def _sort_by_impressions(cls, items: list[dict]) -> list[dict]:
        """Sort items by impressions (展示估值) descending, fallback to popularity."""
        def _key(item):
            imp = cls._parse_numeric(item.get("impressions", ""))
            if imp > 0:
                return imp
            return cls._parse_numeric(item.get("popularity", ""))
        return sorted(items, key=_key, reverse=True)

    # ------------------------------------------------------------------
    # Filters: media type, filter tag, time range, saved filter preset
    # ------------------------------------------------------------------

    async def _apply_filters(self, page: Page,
                              filter_tag: str | None = None,
                              time_range: str | None = None,
                              media_type: str | None = None,
                              saved_filter: str | None = None):
        if media_type:
            try:
                type_btn = page.locator(
                    f'label.ant-radio-button-wrapper:has-text("{media_type}")'
                ).first
                is_checked = await type_btn.evaluate(
                    "el => el.classList.contains('ant-radio-button-wrapper-checked')"
                )
                if not is_checked:
                    await type_btn.click(timeout=5000)
                    await page.wait_for_timeout(3000)
                    await page.wait_for_load_state("networkidle")
            except Exception:
                pass

        if saved_filter:
            try:
                trigger = page.locator('.ant-dropdown-trigger:has-text("常用筛选")').first
                await trigger.click(timeout=5000)
                await page.wait_for_timeout(1500)

                menu_item = page.locator(
                    f'.ant-dropdown-menu-item:has-text("{saved_filter}")'
                ).first
                await menu_item.click(timeout=5000)
                await page.wait_for_timeout(5000)
                await page.wait_for_load_state("networkidle")
            except Exception:
                pass

        if filter_tag:
            tag_btn = page.locator(
                f'.ant-btn:has-text("{filter_tag}"), '
                f'span:has-text("{filter_tag}"), '
                f'a:has-text("{filter_tag}"), '
                f'div:has-text("{filter_tag}")'
            ).first
            try:
                await tag_btn.click(timeout=5000)
                await page.wait_for_timeout(3000)
                await page.wait_for_load_state("networkidle")
            except Exception:
                pass

        if time_range:
            radio = page.locator(
                f'label.ant-radio-button-wrapper:has-text("{time_range}")'
            ).first
            try:
                is_checked = await radio.evaluate(
                    "el => el.classList.contains('ant-radio-button-wrapper-checked')"
                )
                if not is_checked:
                    await radio.click(timeout=5000)
                    await page.wait_for_timeout(3000)
                    await page.wait_for_load_state("networkidle")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Pagination: click next page until we have enough items
    # ------------------------------------------------------------------

    async def _scroll_to_load_all(self, page: Page):
        """Scroll down the page to trigger lazy-loading of images."""
        prev_height = 0
        for _ in range(20):
            cur_height = await page.evaluate("() => document.body.scrollHeight")
            if cur_height == prev_height:
                break
            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(800)
            prev_height = cur_height
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)

    async def _extract_with_pagination(self, page: Page, top: int,
                                        on_progress=None) -> list[dict]:
        """Extract cards across multiple pages.

        Args:
            top: Max items to collect. 0 means scrape up to ~15 pages for sorting.
        """
        items: list[dict] = []
        seen_keys: set[str] = set()
        unlimited = top == 0
        max_pages = 15 if unlimited else (top // 3) + 5
        extract_limit = 500 if unlimited else top * 2

        for page_num in range(max_pages):
            if on_progress:
                on_progress(f"  第 {page_num + 1}/{max_pages} 页, 已收集 {len(items)} 条...")
            await self._scroll_to_load_all(page)

            batch = await self._extract_display_ads(page, extract_limit)
            new_in_batch = 0
            for item in batch:
                key = f"{item.get('title', '')}|{item.get('date_range', '')}|{item.get('image_url', '')}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    item["rank"] = len(items) + 1
                    item["_page"] = page_num + 1
                    items.append(item)
                    new_in_batch += 1

            if not unlimited and len(items) >= top:
                break

            if new_in_batch == 0 and page_num > 0:
                break

            next_btn = page.locator(
                '.ant-pagination-next:not(.ant-pagination-disabled)'
            ).first
            try:
                is_visible = await next_btn.is_visible(timeout=3000)
                if not is_visible:
                    break
                is_disabled = await next_btn.evaluate(
                    "el => el.classList.contains('ant-pagination-disabled')"
                )
                if is_disabled:
                    break
                await next_btn.click(timeout=5000)
                await page.wait_for_timeout(2000)
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                break

        return items if unlimited else items[:top]

    # ------------------------------------------------------------------
    # Video URL enrichment: click card → extract <video> src from modal
    # ------------------------------------------------------------------

    async def _goto_page(self, page: Page, target: int):
        """Navigate to a specific pagination page number."""
        for sel in [
            f'.ant-pagination-item-{target}',
            f'.ant-pagination-item[title="{target}"]',
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click(timeout=5000)
                    await page.wait_for_timeout(2000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except Exception:
                continue

        # Fallback: use the pagination jump input if available
        try:
            jump_input = page.locator('.ant-pagination-options-quick-jumper input').first
            if await jump_input.is_visible(timeout=1000):
                await jump_input.fill(str(target))
                await jump_input.press("Enter")
                await page.wait_for_timeout(2000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True
        except Exception:
            pass

        return False

    async def _click_card_extract_video(self, page: Page, stem: str) -> dict | None:
        """Find a card by image stem, click it, extract video info from modal."""
        try:
            img_el = page.locator(f'img[src*="{stem}"]').first
            if not await img_el.is_visible(timeout=2000):
                return None

            await img_el.click(force=True, timeout=5000)
            await page.wait_for_timeout(2000)

            for _ in range(5):
                has_video = await page.evaluate("() => !!document.querySelector('video')")
                if has_video:
                    break
                await page.wait_for_timeout(1000)

            video_info = await page.evaluate("""() => {
                const v = document.querySelector('video');
                if (!v) return null;
                let src = v.src || '';
                if (!src) {
                    const source = v.querySelector('source');
                    if (source) src = source.src || '';
                }
                return { src: src, poster: v.poster || '' };
            }""")

            # Close modal
            closed = False
            for sel in ['.ant-modal-close', '.ant-drawer-close',
                        'button[aria-label="Close"]']:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=500):
                        await btn.click(timeout=2000)
                        closed = True
                        break
                except Exception:
                    continue
            if not closed:
                await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)

            if video_info and video_info.get("src"):
                return video_info
        except Exception:
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
            except Exception:
                pass
        return None

    async def _enrich_video_urls(self, page: Page, items: list[dict],
                                  saved_filter: str | None = None) -> list[dict]:
        """Extract real .mp4 video URLs by clicking each item's card.

        Uses the _page field recorded during initial scrape to jump directly
        to the right page instead of searching sequentially from page 1.
        """
        # Build lookup: stem → item index, grouped by page
        page_items: dict[int, list[tuple[str, int]]] = {}
        for i, item in enumerate(items):
            img_url = item.get("image_url", "")
            if not img_url:
                continue
            path = urlparse(img_url).path
            fname = path.rsplit("/", 1)[-1] if "/" in path else path
            stem = fname.rsplit(".", 1)[0] if "." in fname else fname
            if stem:
                pg = item.get("_page", 1)
                page_items.setdefault(pg, []).append((stem, i))

        if not page_items:
            return items

        # Re-navigate and re-apply filters
        await page.goto(URLS["display_ads"], wait_until="networkidle")
        await page.wait_for_timeout(3000)

        await self._apply_filters(
            page, media_type="视频", saved_filter=saved_filter,
        )

        enriched = 0
        for target_page in sorted(page_items.keys()):
            stems_on_page = page_items[target_page]

            if target_page > 1:
                ok = await self._goto_page(page, target_page)
                if not ok:
                    continue

            await self._scroll_to_load_all(page)

            for j, (stem, idx) in enumerate(stems_on_page):
                if j > 0:
                    await page.evaluate("() => window.scrollTo(0, 0)")
                    await page.wait_for_timeout(500)
                    await self._scroll_to_load_all(page)

                video_info = await self._click_card_extract_video(page, stem)
                if video_info:
                    items[idx]["video_url"] = video_info["src"]
                    if video_info.get("poster"):
                        items[idx]["image_url"] = video_info["poster"]
                    enriched += 1

        return items

    # ------------------------------------------------------------------
    # DOM card extraction for display-ads page
    # ------------------------------------------------------------------

    async def _extract_display_ads(self, page: Page, top: int) -> list[dict]:
        data = await page.evaluate("""(top) => {
            const items = [];
            const invalidTitles = new Set([
                'Welcome to tengine!', 'Welcome to nginx!', '404 Not Found',
                '', '应用信息',
            ]);

            const allCards = document.querySelectorAll('div[class*="shadow-common"]');
            for (const card of allCards) {
                if (items.length >= top) break;

                const fullText = card.innerText || '';
                if (!fullText.includes('人气值') || !fullText.match(/\\d{4}-\\d{2}-\\d{2}~/)) continue;

                const creativeImg = card.querySelector('img[src*="sp2cdn-idea-global"]');
                const iconImg = card.querySelector('img[src*="appcdn-global"]');

                const zones = [...card.children].map(c => (c.innerText || '').trim());

                const headerLines = (zones[0] || '').split('\\n').map(l => l.trim()).filter(Boolean);
                let headerTitle = headerLines[0] || '';
                let headerAdv = headerLines[1] || '';

                const statsText = zones[2] || '';
                const statsLines = statsText.split('\\n').map(l => l.trim()).filter(Boolean);
                let statsAppName = statsLines[0] || '';

                let title = '';
                let advertiser = '';
                if (!invalidTitles.has(headerTitle) && headerTitle.length > 1) {
                    title = headerTitle;
                    advertiser = headerAdv;
                } else {
                    title = statsAppName;
                    advertiser = '';
                }

                if (!title || invalidTitles.has(title)) continue;

                let popularity = '', days = '', lastSeen = '', impressions = '', heat = '';
                let dateRange = '';
                const allLines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
                for (let i = 0; i < allLines.length; i++) {
                    const l = allLines[i];
                    if (/^\\d{4}-\\d{2}-\\d{2}~\\d{4}-\\d{2}-\\d{2}$/.test(l) && !dateRange) dateRange = l;
                    if (l === '人气值' && i + 1 < allLines.length) popularity = allLines[i + 1];
                    if (l === '投放天数' && i + 1 < allLines.length) days = allLines[i + 1];
                    if (l === '最后看见' && i + 1 < allLines.length) lastSeen = allLines[i + 1];
                    if (l.startsWith('展示估值')) impressions = l.replace(/展示估值[:：]?/, '').trim();
                    if (l.startsWith('热度')) heat = l.replace(/热度[:：]?/, '').trim();
                }

                items.push({
                    rank: items.length + 1,
                    title: title,
                    advertiser: advertiser,
                    date_range: dateRange,
                    popularity: popularity,
                    days: days,
                    last_seen: lastSeen,
                    impressions: impressions,
                    heat: heat,
                    image_url: creativeImg ? creativeImg.src : '',
                    icon_url: iconImg ? iconImg.src : '',
                    scraped_at: new Date().toISOString(),
                });
            }
            return items;
        }""", top)
        return data


    async def search_creatives(self, keyword: str, top: int = 20) -> list[dict]:
        from urllib.parse import quote
        page = self.page
        url = f"{URLS['display_ads']}?keyword={quote(keyword)}"
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        no_data = await page.evaluate(
            "() => (document.body.innerText || '').includes('暂无数据')"
        )
        if no_data:
            self.results = []
            return []

        items = await self._extract_display_ads(page, top)
        self.results = items
        return items


async def run_scrape(top: int = 0, period: str = "weekly", headless: bool = True,
                     filter_tag: str | None = None, time_range: str | None = None,
                     media_type: str | None = None,
                     saved_filter: str | None = None,
                     on_progress=None) -> list[dict]:
    async with GuangdadaScraper(headless=headless) as scraper:
        await scraper.login()
        return await scraper.scrape_top_creatives(
            top=top, period=period,
            filter_tag=filter_tag, time_range=time_range,
            media_type=media_type, saved_filter=saved_filter,
            on_progress=on_progress,
        )


async def run_search(keyword: str, top: int = 20, headless: bool = True) -> list[dict]:
    async with GuangdadaScraper(headless=headless) as scraper:
        await scraper.login()
        return await scraper.search_creatives(keyword=keyword, top=top)

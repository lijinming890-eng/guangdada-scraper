"""Playwright-based scraper for guangdada.net ad-creative rankings.

Navigates to the weekly hot-charts page inside the SPA at::

    https://guangdada.net/modules/creative/charts/hot-charts

and extracts metadata + image URLs for the TOP-N items.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.config import ScraperConfig

logger = logging.getLogger(__name__)

_BASE_URL = "https://guangdada.net"
_LOGIN_URL = f"{_BASE_URL}/modules/auth/login"

# Actual SPA routes discovered from the live site
_CHART_URLS = {
    "weekly": f"{_BASE_URL}/modules/creative/charts/hot-charts",
    "daily": f"{_BASE_URL}/modules/creative/charts/hot-charts",
    "surge": f"{_BASE_URL}/modules/creative/charts/surge-charts",
    "new": f"{_BASE_URL}/modules/creative/charts/new-charts",
    "monthly": f"{_BASE_URL}/modules/creative/charts/hot-charts",
}

_STATE_DIR_NAME = "guangdada_state"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Selectors matched against the real DOM (Ant Design + TailwindCSS SPA)
SELECTORS = {
    "login_username": 'input[type="text"][placeholder*="邮箱"], input[type="text"][placeholder*="email"], input[type="email"], input[name="username"], input[name="email"]',
    "login_password": 'input[type="password"]',
    "login_submit": 'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
    "login_success_indicator": '[class*="avatar"], [class*="userInfo"], [class*="user-name"]',
    # Each ranking row is a 150px-tall card with rounded border
    "chart_card": 'div.rounded-lg.border',
    # Thumbnail image inside LazyLoad container
    "card_image": 'img.object-cover[src*="zingfront.com"], img.object-cover[src*="cdn"], img.object-cover[loading="lazy"]',
    # Title text
    "card_title": '.text-base.font-medium, .text-sm.font-medium',
    # Channel / platform tags
    "card_tag": '.ant-tag',
    # Duration / days info
    "card_duration": '.text-xs.text-\\[\\#666\\], .text-xs.text-\\[\\#999\\]',
}


@dataclass
class CreativeItem:
    """A single ad-creative entry from the ranking page."""
    rank: int = 0
    title: str = ""
    image_url: str = ""
    days: str = ""
    channel: str = ""
    detail_url: str = ""
    extra: dict = field(default_factory=dict)


def _state_dir() -> Path:
    base = os.environ.get("GDD_CREDENTIAL_DIR")
    if base:
        return Path(base) / _STATE_DIR_NAME
    return Path.home() / ".openclaw" / _STATE_DIR_NAME


def _random_delay(lo: float = 0.5, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


def _pick_ua(config_ua: str) -> str:
    return config_ua if config_ua else random.choice(_USER_AGENTS)


class GuangdadaScraper:
    """High-level facade around Playwright for guangdada.net."""

    def __init__(self, config: ScraperConfig, debug_dir: Optional[Path] = None) -> None:
        self._cfg = config
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._debug_dir = debug_dir
        self._debug_step = 0

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def _debug_snapshot(self, label: str) -> None:
        if not self._debug_dir or not self._page:
            return
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        self._debug_step += 1
        prefix = f"{self._debug_step:02d}_{label}"
        try:
            self._page.screenshot(path=str(self._debug_dir / f"{prefix}.png"), full_page=True)
        except Exception:
            pass
        try:
            (self._debug_dir / f"{prefix}.html").write_text(self._page.content(), encoding="utf-8")
        except Exception:
            pass
        logger.info("[debug] %s  url=%s", prefix, self._page.url)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._pw = sync_playwright().start()
        ua = _pick_ua(self._cfg.user_agent)
        state_path = _state_dir()

        self._browser = self._pw.chromium.launch(headless=self._cfg.headless)

        ctx_kwargs: dict = {
            "user_agent": ua,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
        }
        if self._cfg.cookie_reuse and (state_path / "state.json").is_file():
            ctx_kwargs["storage_state"] = str(state_path / "state.json")
            logger.info("Reusing saved browser state")

        self._context = self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(self._cfg.timeout_ms)
        self._page = self._context.new_page()

    def stop(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._page = self._context = self._browser = self._pw = None

    def _save_state(self) -> None:
        if not self._context:
            return
        state_path = _state_dir()
        state_path.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(state_path / "state.json"))

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> bool:
        assert self._page is not None
        page = self._page

        page.goto(_LOGIN_URL, wait_until="networkidle")
        _random_delay(1, 2)
        self._debug_snapshot("login_page")

        # Already logged in?  Check by visiting dashboard
        if "login" not in page.url.lower() and "auth" not in page.url.lower():
            logger.info("Already logged in")
            return True

        try:
            page.locator(SELECTORS["login_success_indicator"]).first.is_visible(timeout=2000)
            logger.info("Already logged in (avatar visible)")
            return True
        except Exception:
            pass

        logger.info("Filling login form...")
        page.locator(SELECTORS["login_username"]).first.click()
        page.locator(SELECTORS["login_username"]).first.fill(username)
        _random_delay(0.3, 0.8)

        page.locator(SELECTORS["login_password"]).first.click()
        page.locator(SELECTORS["login_password"]).first.fill(password)
        _random_delay(0.3, 0.6)

        page.locator(SELECTORS["login_submit"]).first.click()
        logger.info("Submitting...")

        # Wait for URL to change away from login/auth
        try:
            page.wait_for_url("**/modules/**", timeout=15000)
        except Exception:
            self._debug_snapshot("login_timeout")
            if not self._cfg.headless:
                logger.info("Waiting for manual captcha (60s)...")
                try:
                    page.wait_for_url("**/modules/**", timeout=60000)
                except Exception:
                    logger.error("Login timeout")
                    return False
            else:
                logger.error("Login failed (headless). Use --no-headless for captcha.")
                return False

        logger.info("Login success!")
        self._debug_snapshot("login_success")
        self._save_state()
        return True

    # ------------------------------------------------------------------
    # Scrape charts
    # ------------------------------------------------------------------

    def scrape_top_creatives(
        self,
        top_n: int = 20,
        period: str = "weekly",
    ) -> list[CreativeItem]:
        assert self._page is not None
        page = self._page

        chart_url = _CHART_URLS.get(period, _CHART_URLS["weekly"])
        logger.info("Navigating to %s", chart_url)
        page.goto(chart_url, wait_until="networkidle")
        _random_delay(2, 3)
        self._debug_snapshot("chart_page")

        # Scroll to load all items
        self._scroll_to_load(page, rounds=8)
        self._debug_snapshot("after_scroll")

        # Extract items via JavaScript for reliability
        items = self._extract_items_js(page, top_n)

        if not items:
            logger.warning("JS extraction returned 0 items, trying DOM selectors...")
            items = self._extract_items_dom(page, top_n)

        self._save_state()
        logger.info("Extracted %d items", len(items))
        return items

    def _scroll_to_load(self, page: Page, rounds: int = 8) -> None:
        for _ in range(rounds):
            page.evaluate("window.scrollBy(0, 600)")
            _random_delay(0.3, 0.8)

    def _extract_items_js(self, page: Page, top_n: int) -> list[CreativeItem]:
        """Use JavaScript to extract items directly from the DOM."""
        try:
            raw = page.evaluate("""(topN) => {
                // Each chart card is a rounded-lg border div with h-[150px]
                const cards = document.querySelectorAll('div.rounded-lg.border');
                const results = [];
                let rank = 0;
                for (const card of cards) {
                    if (rank >= topN) break;
                    // Must contain an image to be a real card
                    const imgs = card.querySelectorAll('img[src*="zingfront"], img[src*="cdn"], img.object-cover');
                    if (imgs.length === 0) continue;
                    rank++;
                    // Pick the first substantial image (not app icon)
                    let imgSrc = '';
                    for (const img of imgs) {
                        const src = img.src || '';
                        if (src.includes('sp2cdn') || src.includes('sp_opera') || (img.classList.contains('object-cover') && src.length > 40)) {
                            imgSrc = src;
                            break;
                        }
                    }
                    if (!imgSrc && imgs[0]) imgSrc = imgs[0].src || '';

                    // Title: look for font-medium text
                    let title = '';
                    const titleEls = card.querySelectorAll('.font-medium');
                    for (const t of titleEls) {
                        const txt = t.textContent.trim();
                        if (txt.length > 2 && txt.length < 100) { title = txt; break; }
                    }

                    // Tags (channel info)
                    const tags = [];
                    card.querySelectorAll('.ant-tag').forEach(t => {
                        const txt = t.textContent.trim();
                        if (txt) tags.push(txt);
                    });

                    // Duration / stats text
                    let stats = '';
                    card.querySelectorAll('.text-xs').forEach(el => {
                        const txt = el.textContent.trim();
                        if (txt.includes('天') || txt.includes('day')) stats = txt;
                    });

                    // Detail link
                    let detailUrl = '';
                    const link = card.querySelector('a[href]');
                    if (link) detailUrl = link.href || '';

                    results.push({
                        rank: rank,
                        title: title,
                        imgSrc: imgSrc,
                        tags: tags.join(', '),
                        stats: stats,
                        detailUrl: detailUrl,
                    });
                }
                return results;
            }""", top_n)
        except Exception as e:
            logger.warning("JS extraction error: %s", e)
            return []

        items: list[CreativeItem] = []
        for r in raw:
            src = r.get("imgSrc", "")
            if src.startswith("//"):
                src = "https:" + src
            items.append(CreativeItem(
                rank=r.get("rank", 0),
                title=r.get("title", ""),
                image_url=src,
                days=r.get("stats", ""),
                channel=r.get("tags", ""),
                detail_url=r.get("detailUrl", ""),
            ))
        return items

    def _extract_items_dom(self, page: Page, top_n: int) -> list[CreativeItem]:
        """Fallback: use Playwright locators."""
        cards = page.locator("div.rounded-lg.border").all()
        logger.info("DOM fallback: found %d rounded-lg.border divs", len(cards))
        items: list[CreativeItem] = []
        rank = 0

        for card in cards:
            if rank >= top_n:
                break
            try:
                img = card.locator("img.object-cover").first
                src = img.get_attribute("src") or ""
                if not src or len(src) < 30:
                    continue
            except Exception:
                continue

            rank += 1
            if src.startswith("//"):
                src = "https:" + src

            item = CreativeItem(rank=rank, image_url=src)
            try:
                item.title = card.locator(".font-medium").first.inner_text().strip()
            except Exception:
                pass
            try:
                tags = card.locator(".ant-tag").all_inner_texts()
                item.channel = ", ".join(t.strip() for t in tags if t.strip())
            except Exception:
                pass
            try:
                texts = card.locator(".text-xs").all_inner_texts()
                for t in texts:
                    if "天" in t or "day" in t.lower():
                        item.days = t.strip()
                        break
            except Exception:
                pass
            items.append(item)

        return items

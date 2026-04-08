"""CLI entry point for guangdada-scraper skill."""

import asyncio
import io
import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import credential_store
from .scraper import run_scrape, run_search
from .image_downloader import download_all
from .analyzer import analyze_items, generate_report
from .feishu_publisher import publish_to_feishu

console = Console(force_terminal=True)


@click.group()
def cli():
    """广大大买量素材 TOP20 爬虫 — OpenClaw Skill"""
    pass


@cli.command()
@click.option("--username", "-u", prompt="Email / Username", help="广大大账号邮箱")
@click.option("--password", "-p", prompt=True, hide_input=True, help="密码")
def login(username: str, password: str):
    """保存广大大登录凭证 (Fernet 加密存储)"""
    credential_store.save_credentials(username, password)
    console.print("[green]✓ 凭证已加密保存[/green]")


@cli.command()
def logout():
    """清除已保存的凭证"""
    credential_store.clear_credentials()
    console.print("[yellow]✓ 凭证已清除[/yellow]")


@cli.command()
@click.option("--top", "-n", default=0, show_default=True, help="抓取素材数量，0=全部")
@click.option("--all", "scrape_all", is_flag=True, help="抓取筛选条件下的全部素材")
@click.option("--period", "-p", default="weekly", type=click.Choice(["daily", "weekly", "monthly"]), help="时间范围")
@click.option("--filter-tag", "-f", default=None, help="热门筛选标签 (新广告/Top创意/新广告主)")
@click.option("--time-range", "-t", default=None, help="时间范围 (7天/30天/90天/近1年)")
@click.option("--media-type", "-m", default=None, type=click.Choice(["图片", "视频", "轮播", "HTML"], case_sensitive=False), help="素材类型")
@click.option("--saved-filter", "-s", default=None, help="常用筛选预设 (如 '买量筛选')")
@click.option("--no-download", is_flag=True, help="跳过图片下载")
@click.option("--no-headless", is_flag=True, help="显示浏览器窗口 (调试用)")
@click.option("--output-dir", "-o", default=None, help="输出目录")
@click.option("--export-feishu", is_flag=True, help="爬取完自动输出到飞书文档")
@click.option("--analyze", is_flag=True, help="启用 AI 视觉分析（对每张素材图片做创意分析）")
def scrape(top: int, scrape_all: bool, period: str, filter_tag: str, time_range: str,
           media_type: str, saved_filter: str,
           no_download: bool, no_headless: bool, output_dir: str, export_feishu: bool,
           analyze: bool):
    """抓取广大大买量素材"""
    creds = credential_store.load_credentials()
    if not creds:
        console.print("[red]✗ 未找到凭证，请先运行: python -m src.cli login[/red]")
        sys.exit(1)

    if scrape_all:
        top = 0

    # Auto-select saved filter based on media type
    if not saved_filter:
        if media_type == "视频":
            saved_filter = "买量视频"
        elif media_type == "图片" or not media_type:
            saved_filter = "买量筛选"

    label_parts = ["全部" if top == 0 else f"TOP {top}"]
    if saved_filter:
        label_parts.append(f"预设:{saved_filter}")
    if filter_tag:
        label_parts.append(filter_tag)
    if time_range:
        label_parts.append(time_range)
    if media_type:
        label_parts.append(media_type)
    console.print(Panel(f"[bold]抓取广大大素材 ({', '.join(label_parts)})[/bold]", style="blue"))

    def _scrape_progress(msg):
        console.print(f"  [dim]{msg}[/dim]")

    console.print("[bold green]正在启动浏览器并登录...[/bold green]")
    items = asyncio.run(run_scrape(
        top=top, period=period, headless=not no_headless,
        filter_tag=filter_tag, time_range=time_range,
        media_type=media_type, saved_filter=saved_filter,
        on_progress=_scrape_progress,
    ))

    if not items:
        console.print("[red]✗ 未抓取到任何素材[/red]")
        sys.exit(1)

    console.print(f"[green]✓ 抓取到 {len(items)} 条素材[/green]")

    if not no_download:
        with console.status("[bold green]正在下载图片..."):
            items = asyncio.run(download_all(items, output_dir))
        downloaded = sum(1 for i in items if i.get("local_image"))
        console.print(f"[green]✓ 下载完成: {downloaded}/{len(items)} 张图片[/green]")

    if analyze and not no_download:
        from .ai_analyzer import analyze_all_creatives

        def _ai_progress(msg):
            console.print(f"  [dim]{msg}[/dim]")

        console.print("[bold green]正在进行 AI 创意分析...[/bold green]")
        items = analyze_all_creatives(items, on_progress=_ai_progress)
        analyzed = sum(1 for i in items if i.get("ai_analysis"))
        console.print(f"[green]✓ AI 分析完成: {analyzed}/{len(items)} 条素材[/green]")

    _show_table(items)

    items = analyze_items(items)
    report = generate_report(items, output_dir)
    console.print(f"\n[green]✓ 报告已生成: {report}[/green]")

    if export_feishu:
        _export_to_feishu(report)


@cli.command()
@click.argument("keyword")
@click.option("--top", "-n", default=20, show_default=True, help="最多返回条数")
@click.option("--no-download", is_flag=True, help="跳过图片下载")
@click.option("--output-dir", "-o", default=None, help="输出目录")
def search(keyword: str, top: int, no_download: bool, output_dir: str):
    """按关键词搜索广大大广告素材 (APP名/广告主/文案)"""
    creds = credential_store.load_credentials()
    if not creds:
        console.print("[red]✗ 未找到凭证，请先运行: python -m src.cli login[/red]")
        sys.exit(1)

    console.print(Panel(f'[bold]搜索广大大: "{keyword}" (TOP {top})[/bold]', style="blue"))

    with console.status("[bold green]正在搜索..."):
        items = asyncio.run(run_search(keyword=keyword, top=top))

    if not items:
        console.print("[red]✗ 未搜索到相关素材[/red]")
        sys.exit(1)

    console.print(f"[green]✓ 搜索到 {len(items)} 条素材[/green]")

    if not no_download:
        with console.status("[bold green]正在下载图片..."):
            items = asyncio.run(download_all(items, output_dir))
        downloaded = sum(1 for i in items if i.get("local_image"))
        console.print(f"[green]✓ 下载完成: {downloaded}/{len(items)} 张图片[/green]")

    _show_table(items)

    items = analyze_items(items)
    report = generate_report(items, output_dir)
    console.print(f"\n[green]✓ 报告已生成: {report}[/green]")


@cli.command()
@click.option("--dir", "-d", "input_dir", required=True, help="素材图片目录")
@click.option("--output-dir", "-o", default=None, help="报告输出目录")
def analyze(input_dir: str, output_dir: str):
    """分析已下载的素材图片并生成报告"""
    from .analyzer import analyze_image

    input_path = Path(input_dir)
    if not input_path.exists():
        console.print(f"[red]✗ 目录不存在: {input_dir}[/red]")
        sys.exit(1)

    images = list(input_path.glob("*.jpg")) + list(input_path.glob("*.png")) + list(input_path.glob("*.webp"))
    if not images:
        console.print(f"[red]✗ 未找到图片文件[/red]")
        sys.exit(1)

    items = []
    for i, img_path in enumerate(images, 1):
        analysis = analyze_image(str(img_path))
        items.append({
            "rank": i,
            "title": img_path.stem,
            "local_image": str(img_path),
            "image_analysis": analysis,
            "advertiser": "",
            "platform": "",
            "impressions": "",
        })

    report = generate_report(items, output_dir or str(input_path.parent))
    console.print(f"[green]✓ 分析完成，报告: {report}[/green]")


@cli.command()
@click.option("--report", "-r", required=True, help="报告文件路径 (.md)")
@click.option("--webhook", "-w", default=None, help="飞书 webhook URL (可选，默认用 config.yaml)")
def publish(report: str, webhook: str):
    """发布报告到飞书"""
    try:
        ok = publish_to_feishu(report, webhook)
        if ok:
            console.print("[green]✓ 报告已发布到飞书[/green]")
        else:
            console.print("[yellow]⚠ 发布请求已发送，但返回状态不确定[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ 发布失败: {e}[/red]")
        sys.exit(1)


@cli.command()
def doctor():
    """检查环境和配置是否就绪"""
    console.print(Panel("[bold]环境检查[/bold]", style="blue"))

    # Python
    console.print(f"  Python: [green]{sys.version.split()[0]}[/green]")

    # Playwright
    try:
        from playwright.sync_api import sync_playwright
        console.print("  Playwright: [green]已安装[/green]")
    except ImportError:
        console.print("  Playwright: [red]未安装[/red] → pip install playwright && playwright install chromium")

    # Chromium
    try:
        import subprocess
        result = subprocess.run(["playwright", "install", "--dry-run"], capture_output=True, text=True)
        console.print("  Chromium: [green]可用[/green]")
    except Exception:
        console.print("  Chromium: [yellow]状态未知[/yellow]")

    # Credentials
    creds = credential_store.load_credentials()
    if creds:
        console.print(f"  凭证: [green]已配置 ({creds['username']})[/green]")
    else:
        console.print("  凭证: [yellow]未配置[/yellow] → python -m src.cli login")

    # Config
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        console.print(f"  配置文件: [green]{config_path}[/green]")
    else:
        template = Path(__file__).parent.parent / "config.yaml.template"
        console.print(f"  配置文件: [yellow]使用模板 ({template})[/yellow]")
        console.print("    → 复制 config.yaml.template 为 config.yaml 进行自定义配置")


def _export_to_feishu(report_path: str):
    """Import the Markdown report into a Feishu document with embedded images."""
    from .feishu_publisher import import_markdown_to_feishu

    report = Path(report_path)
    if not report.exists():
        console.print(f"[red]✗ 报告文件不存在: {report_path}[/red]")
        return

    md_content = report.read_text(encoding="utf-8")
    title_line = md_content.split("\n")[0].replace("#", "").strip() or "广大大素材报告"
    file_name = f"{title_line}.md"

    console.print(f"\n[bold blue]正在导入飞书文档 (图片将直接嵌入)...[/bold blue]")
    console.print(f"  标题: {title_line}")

    def _progress(msg):
        console.print(f"  [dim]{msg}[/dim]")

    try:
        result = import_markdown_to_feishu(
            md_content, file_name=file_name, on_progress=_progress,
        )
        doc_url = result.get("url", "")
        uploaded = result.get("images_uploaded", 0)
        failed = result.get("images_failed", 0)
        console.print(f"  [green]✓ 飞书文档已创建![/green]")
        console.print(f"  [green]  图片嵌入: {uploaded} 张成功[/green]", end="")
        if failed:
            console.print(f"[yellow], {failed} 张失败[/yellow]")
        else:
            console.print()
        if doc_url:
            console.print(f"  [bold blue]文档链接: {doc_url}[/bold blue]")
    except Exception as e:
        console.print(f"  [red]✗ 飞书导入失败: {e}[/red]")


def _show_table(items: list[dict]):
    table = Table(title="抓取结果", show_lines=True)
    table.add_column("排名", style="bold cyan", width=6)
    table.add_column("标题", style="white", max_width=30)
    table.add_column("广告主", style="green", max_width=20)
    table.add_column("展示估值", style="magenta", max_width=12)
    table.add_column("人气值", style="yellow", max_width=10)
    table.add_column("投放天数", style="yellow", max_width=8)
    table.add_column("图片", style="dim", width=4)

    for item in items:
        has_img = "✓" if item.get("local_image") else "✗"
        table.add_row(
            str(item.get("rank", "")),
            (item.get("title", "") or "-")[:30],
            (item.get("advertiser", "") or "-")[:20],
            (item.get("impressions", "") or "-")[:12],
            (item.get("popularity", "") or "-")[:10],
            (item.get("days", "") or "-")[:8],
            has_img,
        )

    console.print(table)


@cli.command()
@click.option("--top", "-n", default=20, show_default=True, help="抓取数量")
@click.option("--period", "-p", default="weekly", type=click.Choice(["daily", "weekly", "monthly"]))
@click.option("--publish-feishu", is_flag=True, help="自动发布到飞书")
def run(top: int, period: str, publish_feishu: bool):
    """一键运行: 抓取 → 下载 → 分析 → (可选)发布"""
    creds = credential_store.load_credentials()
    if not creds:
        console.print("[red]✗ 请先运行: python -m src.cli login[/red]")
        sys.exit(1)

    console.print(Panel(f"[bold]一键运行: TOP {top} ({period})[/bold]", style="blue"))

    with console.status("[bold green]Step 1/3: 抓取素材..."):
        items = asyncio.run(run_scrape(top=top, period=period))
    console.print(f"[green]✓ 抓取 {len(items)} 条[/green]")

    with console.status("[bold green]Step 2/3: 下载图片..."):
        items = asyncio.run(download_all(items))
    console.print(f"[green]✓ 下载完成[/green]")

    items = analyze_items(items)
    report = generate_report(items)
    console.print(f"[green]✓ Step 3/3: 报告 → {report}[/green]")

    _show_table(items)

    if publish_feishu:
        try:
            publish_to_feishu(report)
            console.print("[green]✓ 已发布到飞书[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ 飞书发布失败: {e}[/yellow]")


if __name__ == "__main__":
    cli()

import asyncio
import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright
from app.config import EVIDENCE_DIR

logger = logging.getLogger(__name__)

async def capture_screenshot(url: str, investigation_id: str, hit_id: int) -> Optional[str]:
    """
    Captures a full-page headless Chromium screenshot for a hit URL (§4).
    Saves screenshot under data/evidence/{investigation_id}/{hit_id}/screenshot.png.
    """
    if not url or not url.startswith("http"):
        return None

    target_dir = EVIDENCE_DIR / str(investigation_id) / str(hit_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    screenshot_file = target_dir / "screenshot.png"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(screenshot_file), full_page=False)
            await browser.close()

            relative_path = f"evidence/{investigation_id}/{hit_id}/screenshot.png"
            logger.info("Captured screenshot for hit #%d at %s", hit_id, relative_path)
            return relative_path

    except Exception as e:
        logger.warning("Failed to capture screenshot for %s: %s", url, e)
        return None

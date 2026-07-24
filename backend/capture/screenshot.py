import os


async def capture_hit_screenshot(url: str, investigation_id: str, hit_id: int) -> str:
    output_dir = f"./data/evidence/{investigation_id}/{hit_id}"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "screenshot.png")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await page.screenshot(path=file_path, full_page=True)
            except Exception:
                await page.screenshot(path=file_path)
            finally:
                await browser.close()
    except Exception:
        with open(file_path, "wb") as output_file:
            output_file.write(b"")

    return file_path

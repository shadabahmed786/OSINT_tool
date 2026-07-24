import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOT_DIR = Path("data/evidence/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

async def test_full_chrome_suite():
    print("=== STARTING FULL CHROME AUTOMATED UI TEST ===")

    async with async_playwright() as p:
        # Launch Chromium (headless or headed)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # Step 1: Open Local Server
        print("1. Navigating to http://127.0.0.1:8000 ...")
        response = await page.goto("http://127.0.0.1:8000")
        assert response.status == 200, f"Expected HTTP 200, got {response.status}"

        # Verify Title & Navbar
        title = await page.title()
        print(f"   Page Title: '{title}'")
        assert "OSINT Investigation Platform" in title

        status_text = await page.inner_text("#status-text")
        print(f"   System Status: '{status_text}'")
        assert "LOCAL SYSTEM READY" in status_text

        await page.screenshot(path=str(SCREENSHOT_DIR / "01_homepage_initial.png"))
        print("   Saved screenshot: 01_homepage_initial.png")

        # Step 2: Test Selector Auto-Detection
        print("2. Testing Selector Type Auto-Detection...")
        target_input = page.locator("#target-input")
        badge = page.locator("#detected-badge")

        await target_input.fill("test@example.com")
        await page.wait_for_timeout(300)
        print(f"   Input 'test@example.com' -> Badge text: '{await badge.inner_text()}'")
        assert "EMAIL" in await badge.inner_text()

        await target_input.fill("+14155552671")
        await page.wait_for_timeout(300)
        print(f"   Input '+14155552671' -> Badge text: '{await badge.inner_text()}'")
        assert "PHONE" in await badge.inner_text()

        await target_input.fill("octocat")
        await page.wait_for_timeout(300)
        print(f"   Input 'octocat' -> Badge text: '{await badge.inner_text()}'")
        assert "USERNAME" in await badge.inner_text()

        await page.screenshot(path=str(SCREENSHOT_DIR / "02_selector_autodetect.png"))

        # Step 3: Run Pivot Investigation
        print("3. Running Live Pivot Search for 'octocat'...")
        submit_btn = page.locator("#submit-btn")
        await submit_btn.click()

        # Wait for results section to be displayed
        results_section = page.locator("#results-section")
        await results_section.wait_for(state="visible", timeout=10000)

        # Wait until progress finishes (total hits > 0)
        print("   Waiting for background enumeration checks to complete...")
        for _ in range(15):
            total_text = await page.inner_text("#stat-total")
            if int(total_text) > 0:
                break
            await asyncio.sleep(1)

        total_hits = await page.inner_text("#stat-total")
        high_hits = await page.inner_text("#stat-high")
        overall_rating = await page.inner_text("#stat-overall")

        print(f"   Investigation Finished!")
        print(f"   - Total Hits Discovered: {total_hits}")
        print(f"   - High Confidence Hits: {high_hits}")
        print(f"   - Overall Case Rating: {overall_rating}")

        assert int(total_hits) > 0, "Expected at least 1 finding hit"

        await page.screenshot(path=str(SCREENSHOT_DIR / "03_investigation_results.png"))
        print("   Saved screenshot: 03_investigation_results.png")

        # Step 4: Test Findings Card Interaction & Filter Pills
        print("4. Testing Findings Grid & Confidence Filters...")
        high_filter = page.locator(".filter-btn[data-filter='HIGH']")
        await high_filter.click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_filter_high.png"))

        all_filter = page.locator(".filter-btn[data-filter='ALL']")
        await all_filter.click()

        # Step 5: Test Evidence Audit Log Table
        print("5. Testing Evidence Audit Log Tab...")
        timeline_tab_btn = page.locator(".tab-btn[data-tab='timeline-tab']")
        await timeline_tab_btn.click()
        await page.wait_for_timeout(500)

        log_rows = await page.locator("#evidence-table-body tr").count()
        print(f"   Audit Log Entries Count: {log_rows}")
        assert log_rows > 0, "Expected non-empty audit log table"

        await page.screenshot(path=str(SCREENSHOT_DIR / "05_evidence_audit_log.png"))
        print("   Saved screenshot: 05_evidence_audit_log.png")

        # Step 6: Test Free HIBP Password Exposure Tool
        print("6. Testing Free HIBP Password Exposure Tool...")
        pwd_input = page.locator("#pwd-input")
        pwd_btn = page.locator("#pwd-check-btn")
        pwd_result = page.locator("#pwd-result")

        await pwd_input.fill("123456")
        await pwd_btn.click()

        for _ in range(10):
            res_text = await pwd_result.inner_text()
            if "BREACH DETECTED" in res_text or "CLEAN" in res_text:
                break
            await asyncio.sleep(0.5)

        safe_res = res_text.encode("ascii", "ignore").decode("ascii")
        print(f"   Password Exposure Result: '{safe_res}'")
        assert "BREACH DETECTED" in res_text or "found" in res_text.lower()

        await page.screenshot(path=str(SCREENSHOT_DIR / "06_hibp_password_tool.png"))
        print("   Saved screenshot: 06_hibp_password_tool.png")

        # Step 7: Verify History Drawer
        print("7. Verifying History Drawer...")
        history_items = await page.locator(".history-item").count()
        print(f"   Recent Investigation Runs Recorded: {history_items}")
        assert history_items > 0, "Expected recent run in history list"

        await browser.close()
        print("\n=== ALL CHROME BROWSER TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(test_full_chrome_suite())

from playwright.sync_api import sync_playwright

def log(*a):
    print(*a, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-quic"])
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    page.goto("https://v2.auth.mistral.ai/login", timeout=90000, wait_until="domcontentloaded")
    # reload up to 3 times to let static chunks load through flaky connection
    for attempt in range(3):
        page.wait_for_timeout(5000)
        failed = page.evaluate("() => performance.getEntriesByType('resource').filter(r => r.responseStatus && r.responseStatus >= 400).length")
        log(f"attempt {attempt}: failed resources = {failed}")
        if failed == 0:
            break
        try:
            page.reload(timeout=90000, wait_until="domcontentloaded")
        except Exception as e:
            log("reload fail:", repr(e))
    page.wait_for_timeout(4000)
    try:
        print(page.locator("main").aria_snapshot())
    except Exception as e:
        log("aria fail:", repr(e))
    log("--- buttons detail ---")
    btns = page.locator("button")
    for i in range(btns.count()):
        b = btns.nth(i)
        log(i, "visible:", b.is_visible(), "text:", repr(b.inner_text()[:60]), "aria:", b.get_attribute("aria-label"))
    browser.close()

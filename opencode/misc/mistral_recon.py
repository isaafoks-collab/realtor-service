from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    for url in ["https://console.mistral.ai/", "https://auth.mistral.ai/ui/registration"]:
        try:
            resp = page.goto(url, timeout=60000, wait_until="domcontentloaded")
            print(f"URL {url} -> status {resp.status if resp else 'none'}")
            page.wait_for_timeout(6000)
            print("FINAL URL:", page.url)
            print("TITLE:", page.title())
            text = page.inner_text("body")
            print("---BODY TEXT (first 1500)---")
            print(text[:1500])
            page.screenshot(path="opencode/misc/mistral_recon.png", full_page=True)
            print("---SCREENSHOT saved---")
            break
        except Exception as e:
            print(f"FAIL {url}: {e}")
    browser.close()

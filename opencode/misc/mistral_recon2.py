import sys
from playwright.sync_api import sync_playwright

def log(*a):
    print(*a, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    url = "https://console.mistral.ai/"
    log("goto", url)
    try:
        resp = page.goto(url, timeout=45000, wait_until="domcontentloaded")
        log("status", resp.status if resp else "none")
    except Exception as e:
        log("goto fail:", repr(e))
    log("final url:", page.url)
    try:
        page.wait_for_timeout(5000)
        log("title:", page.title())
        log(page.inner_text("body")[:1200])
        page.screenshot(path="opencode/misc/mistral_recon.png", full_page=True)
        log("screenshot ok")
    except Exception as e:
        log("post fail:", repr(e))
    browser.close()

from playwright.sync_api import sync_playwright
import re

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
    log("goto login")
    try:
        page.goto("https://v2.auth.mistral.ai/login", timeout=90000, wait_until="domcontentloaded")
        log("loaded")
    except Exception as e:
        log("goto fail:", repr(e))
    page.wait_for_timeout(8000)
    log("url:", page.url)
    try:
        html = page.content()
        with open("opencode/misc/mistral_login.html", "w", encoding="utf-8") as f:
            f.write(html)
        links = re.findall(r'href="([^"]+)"', html)
        log("--- links ---")
        for l in set(links):
            log(l)
        log("--- text ---")
        try:
            log(page.inner_text("body")[:800])
        except Exception as e:
            log("body fail:", repr(e))
        page.screenshot(path="opencode/misc/mistral_login.png", full_page=True)
        log("screenshot ok")
    except Exception as e:
        log("dump fail:", repr(e))
    browser.close()

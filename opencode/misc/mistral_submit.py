from playwright.sync_api import sync_playwright

def log(*a):
    print(*a, flush=True)

EMAIL = "isaafoks@gmail.com"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-quic"])
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    log("goto login")
    page.goto("https://v2.auth.mistral.ai/login", timeout=90000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    inputs = page.locator("input")
    log("inputs:", inputs.count())
    for i in range(inputs.count()):
        log(f"input[{i}]", inputs.nth(i).get_attribute("name"), inputs.nth(i).get_attribute("type"))
    btns = page.locator("button")
    log("buttons:", btns.count())
    for i in range(btns.count()):
        log(f"button[{i}]", btns.nth(i).inner_text())
    page.fill("input[name=email]", EMAIL)
    log("email filled")
    page.screenshot(path="opencode/misc/mistral_filled.png")
    page.locator("button").first.click()
    log("submitted, waiting...")
    page.wait_for_timeout(10000)
    log("url after submit:", page.url)
    try:
        log("text:", page.inner_text("body")[:1000])
    except Exception as e:
        log("text fail:", repr(e))
    page.screenshot(path="opencode/misc/mistral_after_submit.png", full_page=True)
    log("screenshot ok")
    browser.close()

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
    page.wait_for_timeout(7000)
    inp = page.locator("input[name=email]")
    log("disabled attr:", inp.get_attribute("disabled"), "aria-disabled:", inp.get_attribute("aria-disabled"))
    # try clicking then typing
    try:
        inp.click(timeout=5000)
        log("clicked")
    except Exception as e:
        log("click fail:", repr(e)[:200])
    page.keyboard.type("isaafoks@gmail.com", delay=50)
    page.wait_for_timeout(2000)
    log("value now:", inp.input_value())
    log("aria-disabled now:", inp.get_attribute("aria-disabled"))
    # look for consent checkbox / terms
    boxes = page.locator("input[type=checkbox]")
    log("checkboxes:", boxes.count())
    page.screenshot(path="opencode/misc/mistral_typed.png", full_page=True)
    # try Enter
    page.keyboard.press("Enter")
    page.wait_for_timeout(8000)
    log("url:", page.url)
    try:
        log("text:", page.inner_text("body")[:600])
    except Exception as e:
        log("text fail:", repr(e)[:150])
    page.screenshot(path="opencode/misc/mistral_after_enter.png", full_page=True)
    browser.close()

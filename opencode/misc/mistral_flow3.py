from playwright.sync_api import sync_playwright

def log(*a):
    print(*a, flush=True)

def goto_retry(page, url, attempts=5):
    for i in range(attempts):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            log(f"goto ok attempt {i+1}: {page.url}")
            return True
        except Exception as e:
            log(f"goto fail {i+1}: {str(e)[:100]}")
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-quic"])
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    ok = goto_retry(page, "https://auth.mistral.ai/self-service/login/browser?email=isaafoks@gmail.com")
    if not ok:
        log("ABORT")
        browser.close()
        raise SystemExit(1)
    page.wait_for_timeout(6000)
    log("url:", page.url)
    inputs = page.locator("input")
    log("inputs:", inputs.count())
    for i in range(inputs.count()):
        el = inputs.nth(i)
        log(f"input[{i}]", "name:", el.get_attribute("name"), "type:", el.get_attribute("type"),
            "disabled:", el.get_attribute("disabled"), "aria-dis:", el.get_attribute("aria-disabled"),
            "value:", el.input_value())
    btns = page.locator("button")
    log("buttons:", btns.count())
    for i in range(btns.count()):
        b = btns.nth(i)
        log(f"button[{i}]", "visible:", b.is_visible(), "aria:", b.get_attribute("aria-label"),
            "text:", repr(b.inner_text()[:50]), "disabled:", b.get_attribute("disabled"))
    try:
        log("text:", page.inner_text("body")[:700])
    except Exception as e:
        log("text fail:", repr(e)[:120])
    page.screenshot(path="opencode/misc/mistral_flow2.png", full_page=True)
    log("screenshot ok")
    browser.close()

from playwright.sync_api import sync_playwright

def log(*a):
    print(*a, flush=True)

def goto_retry(page, url, attempts=4):
    for i in range(attempts):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            log(f"goto ok on attempt {i+1}: {page.url}")
            return True
        except Exception as e:
            log(f"goto fail {i+1}: {str(e)[:120]}")
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-quic"])
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    if not goto_retry(page, "https://v2.auth.mistral.ai/login"):
        log("ABORT: cannot load login page")
        browser.close()
        raise SystemExit(1)
    page.wait_for_timeout(5000)
    inp = page.locator("input[name=email]")
    log("aria-disabled:", inp.get_attribute("aria-disabled"))
    inp.evaluate("el => { el.disabled = false; el.removeAttribute('aria-disabled'); }")
    inp.fill("isaafoks@gmail.com", timeout=10000)
    log("filled:", inp.input_value())
    # watch network for the submit result
    responses = []
    page.on("response", lambda r: responses.append((r.status, r.url[:100])) if "self-service" in r.url or "login" in r.url else None)
    page.keyboard.press("Enter")
    page.wait_for_timeout(10000)
    log("url after submit:", page.url)
    try:
        log("text:", page.inner_text("body")[:500])
    except Exception as e:
        log("text fail:", repr(e)[:120])
    log("--- relevant responses ---")
    for s, u in responses[-10:]:
        log(s, u)
    page.screenshot(path="opencode/misc/mistral_email_submit.png", full_page=True)
    log("screenshot ok")
    browser.close()

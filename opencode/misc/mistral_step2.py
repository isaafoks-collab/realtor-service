from playwright.sync_api import sync_playwright
import sys

def log(*a):
    print(*a, flush=True)

def goto_retry(page, url, attempts=5):
    for i in range(attempts):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            log(f"goto ok attempt {i+1}: {page.url}")
            return True
        except Exception as e:
            log(f"goto fail {i+1}: {str(e)[:90]}")
    return False

def dump_state(page):
    try:
        inputs = page.locator("input")
        n = inputs.count()
        log("inputs:", n)
        for i in range(n):
            el = inputs.nth(i)
            log(f"  input[{i}]", "name:", el.get_attribute("name"), "type:", el.get_attribute("type"),
                "disabled:", el.get_attribute("disabled"), "aria-dis:", el.get_attribute("aria-disabled"))
        btns = page.locator("button")
        log("buttons:", btns.count())
        for i in range(btns.count()):
            b = btns.nth(i)
            log(f"  button[{i}]", "aria:", b.get_attribute("aria-label"), "text:", repr(b.inner_text()[:40]))
        try:
            log("text:", page.inner_text("body", timeout=8000)[:400])
        except Exception as e:
            log("  text fail:", repr(e)[:80])
    except Exception as e:
        log("dump fail:", repr(e)[:120])

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-quic"])
    ctx = browser.new_context(
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    if not goto_retry(page, "https://v2.auth.mistral.ai/login"):
        log("ABORT")
        browser.close()
        raise SystemExit(1)
    page.wait_for_timeout(6000)
    log("=== state before submit ===")
    dump_state(page)
    inp = page.locator("input[name=email]")
    inp.evaluate("el => { el.disabled = false; el.removeAttribute('aria-disabled'); }")
    inp.fill("isaafoks@gmail.com", timeout=10000)
    log("filled:", inp.input_value())
    page.keyboard.press("Enter")
    log("submitted, polling for new page...")
    for t in range(12):
        page.wait_for_timeout(5000)
        try:
            u = page.url
            ni = page.locator("input").count()
            log(f"t={t}: url={u[:80]} inputs={ni}")
            if ni > 0 and ("flow=" in u):
                dump_state(page)
                page.screenshot(path="opencode/misc/mistral_step2.png", full_page=True)
                log("screenshot ok")
                break
        except Exception as e:
            log(f"t={t} poll fail:", repr(e)[:100])
    browser.close()

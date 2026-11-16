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

    log("=== try Ory registration endpoint ===")
    try:
        page.goto("https://v2.auth.mistral.ai/self-service/registration/browser", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        log("url:", page.url)
        try:
            log("text:", page.inner_text("body")[:400])
        except Exception as e:
            log("text fail:", repr(e)[:150])
    except Exception as e:
        log("fail:", repr(e)[:200])

    log("=== force-enable email field ===")
    page.goto("https://v2.auth.mistral.ai/login", timeout=90000, wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    inp = page.locator("input[name=email]")
    inp.evaluate("el => { el.disabled = false; el.removeAttribute('aria-disabled'); }")
    inp.fill("isaafoks@gmail.com", timeout=10000)
    log("filled:", inp.input_value())
    # find any submit button inside email form
    forms = page.locator("form")
    log("forms:", forms.count())
    for i in range(forms.count()):
        log(f"form[{i}] action:", forms.nth(i).get_attribute("action"))
        fb = forms.nth(i).locator("button")
        for j in range(fb.count()):
            log(f"  button[{j}]:", repr(fb.nth(j).inner_text()[:40]), "type:", fb.nth(j).get_attribute("type"))
    page.keyboard.press("Enter")
    page.wait_for_timeout(8000)
    log("url after:", page.url)
    try:
        log("text:", page.inner_text("body")[:600])
    except Exception as e:
        log("text fail:", repr(e)[:150])
    page.screenshot(path="opencode/misc/mistral_forced_email.png", full_page=True)
    browser.close()

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
    reqs = []
    page.on("requestfailed", lambda r: reqs.append(("FAIL", r.url[:110], r.failure)))
    page.on("response", lambda r: reqs.append((r.status, r.url[:110], "")))
    for url in ["https://auth.mistral.ai/ui/registration", "https://v2.auth.mistral.ai/ui/registration"]:
        log("goto", url)
        try:
            page.goto(url, timeout=90000, wait_until="commit")
            log("committed, waiting...")
            page.wait_for_timeout(15000)
            log("final url:", page.url)
            log("title:", page.title())
            try:
                log(page.inner_text("body")[:1500])
            except Exception as e:
                log("body fail:", repr(e))
            page.screenshot(path="opencode/misc/mistral_reg.png", full_page=True)
            log("screenshot ok")
            break
        except Exception as e:
            log("goto fail:", repr(e))
    log("--- last 25 requests ---")
    for s, u, f in reqs[-25:]:
        log(s, u, str(f)[:60])
    browser.close()

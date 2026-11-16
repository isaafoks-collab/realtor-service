import re
html = open(r"opencode\misc\mistral_login.html", encoding="utf-8").read()
btns = re.findall(r"<button[^>]*>.*?</button>", html, re.S)
print("count:", len(btns))
for b in btns[:12]:
    t = re.sub(r"<[^>]+>", " ", b)
    cls = re.search(r'class="([^"]{0,200})', b)
    print("TEXT:", repr(t.strip()[:120]))
    print("  class:", (cls.group(1) if cls else "")[:160])
print("--- svg/social hints ---")
for m in re.findall(r'(google|github|sso|oidc|consent|accept|tos|terms)', html, re.I):
    print(m)

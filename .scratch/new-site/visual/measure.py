"""Замеры вёрстки: горизонтальное переполнение и поля контейнеров."""

import json

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8009"
PAGES = ["/", "/contacts/", "/works/", "/about/", "/catalog/zerkala/",
         "/catalog/zerkala/aura/", "/delivery/", "/privacy/", "/cart/",
         "/favorites/", "/zerkala-s-podsvetkoy/", "/catalog/"]
WIDTHS = [1440, 1024, 390]

SCRIPT = """() => {
  const out = {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    wraps: [],
    overflow: [],
  };
  document.querySelectorAll('.wrap').forEach((el) => {
    const r = el.getBoundingClientRect();
    out.wraps.push({
      cls: el.className,
      left: Math.round(r.left),
      right: Math.round(r.right),
    });
  });
  document.querySelectorAll('*').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1)) {
      out.overflow.push({
        tag: el.tagName,
        cls: String(el.className).slice(0, 40),
        left: Math.round(r.left),
        right: Math.round(r.right),
      });
    }
  });
  out.overflow = out.overflow.slice(0, 8);
  return out;
}"""

with sync_playwright() as p:
    browser = p.firefox.launch()
    for width in WIDTHS:
        page = browser.new_page(viewport={"width": width, "height": 900})
        for path in PAGES:
            page.goto(BASE + path, wait_until="networkidle")
            data = page.evaluate(SCRIPT)
            flag = "OVERFLOW" if data["scrollWidth"] > data["innerWidth"] else "ok"
            print(f"{width} {path} {flag} "
                  f"scroll={data['scrollWidth']} wraps={json.dumps(data['wraps'][:3], ensure_ascii=False)}")
            for item in data["overflow"]:
                print("    ", json.dumps(item, ensure_ascii=False))
        page.close()
    browser.close()

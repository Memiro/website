"""Плитки главной: кадр блока на трёх ширинах + разбор ссылок и порядка."""
import pathlib, sys
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.firefox.launch()
    for w in (1440, 1024, 390):
        page = b.new_page(viewport={"width": w, "height": 900})
        page.goto("http://127.0.0.1:8009/", wait_until="networkidle")
        grid = page.locator(".tiles-grid").first
        grid.scroll_into_view_if_needed()
        page.wait_for_timeout(900)
        grid.screenshot(path=OUT / f"tiles-{w}.png")
        print(w, page.evaluate("""() => {
          const g = document.querySelector('.tiles-grid');
          const s = getComputedStyle(g);
          return {cols: s.gridTemplateColumns,
            tiles: [...g.querySelectorAll('.tile')].map(t => ({
              href: t.getAttribute('href'),
              label: t.querySelector('.label')?.textContent.trim(),
              img: !!t.querySelector('img')?.getAttribute('src'),
              h: Math.round(t.getBoundingClientRect().height)}))};
        }"""))
        page.close()
    # корень каталога: по решению тикета — редирект в единственную категорию
    page = b.new_page(viewport={"width": 1440, "height": 900})
    r = page.goto("http://127.0.0.1:8009/catalog/", wait_until="networkidle")
    print("catalog root ->", r.url, r.status)
    page.close()
    b.close()

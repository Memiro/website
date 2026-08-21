"""Скриншоты витрины на трёх ширинах через headless Firefox (playwright)."""

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8009"
OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "home": "/",
    "about": "/about/",
    "delivery": "/delivery/",
    "contacts": "/contacts/",
    "privacy": "/privacy/",
    "works": "/works/",
    "catalog": "/catalog/",
    "category": "/catalog/zerkala/",
    "product": "/catalog/zerkala/aura/",
    "landing": "/zerkala-s-podsvetkoy/",
    "cart": "/cart/",
    "favorites": "/favorites/",
}

WIDTHS = [1440, 1024, 390]

with sync_playwright() as p:
    browser = p.firefox.launch()
    for width in WIDTHS:
        page = browser.new_page(
            viewport={"width": width, "height": 900},
            device_scale_factor=1,
        )
        for name, path in PAGES.items():
            response = page.goto(BASE + path, wait_until="networkidle")
            status = response.status if response else "?"
            page.screenshot(
                path=OUT / f"{name}-{width}.png", full_page=True
            )
            print(f"{width} {name} {status}")
        page.close()
    browser.close()

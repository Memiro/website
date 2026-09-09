# Design — Memiro

Locked design system. Future Hallmark runs read this file first; pages defer
to it. Amend intentionally — the file is the rule.

<!-- Hallmark · design.md · studied: yes · DNA-source: url ×3 · locked 2026-09-09 -->

## System
- Genre · modern-minimal
- Macrostructure · Catalogue (home) · every page is an index of things, not a narrative
- Theme · studied-DNA — white paper, near-black ink, one cool-blue signal, uppercase grotesk display, mono labels
- Axes · light / geometric-sans-uppercase / cool-blue
- Logo · `Memiro Logotype` kit (SVG, outlined). Nav = Logo3 (mark + word, 26 px), footer = Logo4 (with rule + tagline), favicon/mask-icon = Logo7 (mark). White versions on dark blocks. ® is registered — show it once in the footer legal line, never in the nav.

## Provenance
Extracted 2026-09-09 as public references for the owner's own brand from
`https://crystacell.store/`, `https://www.newgroundcoffee.com/`,
`https://xiztdevops.com/` (URL mode: exact fonts and colours read from CSS;
rhythm judged from full-page screenshots). `erikk-template.webflow.io` is a
Webflow marketplace template — used as a taste signal only, nothing extracted.
The DNA is structural; tokens were regenerated for Memiro (Cyrillic-capable
faces, own accent) rather than copied. Confidence: tokens exact, fonts exact,
rhythm judged visually.

## Tokens (canonical · `frontend/app/styles/tokens.css` is the source of truth)
```css
:root {
  --color-paper:      oklch(100% 0 0);
  --color-paper-2:    oklch(97%  0.002 250);
  --color-ink:        oklch(15%  0.005 250);
  --color-ink-2:      oklch(32%  0.005 250);
  --color-muted:      oklch(52%  0.006 250);
  --color-rule:       oklch(88%  0.003 250);
  --color-accent:     oklch(38%  0.15  258);
  --color-accent-ink: oklch(100% 0 0);
  --color-focus:      oklch(48%  0.19  258);

  --font-display: "Golos Text", ui-sans-serif, system-ui, sans-serif;   /* 800, uppercase, tracking -0.02em */
  --font-body:    "Golos Text", ui-sans-serif, system-ui, sans-serif;   /* 400 */
  --font-outlier: "JetBrains Mono", ui-monospace, monospace;            /* labels · prices · nav · captions */

  /* 4-pt spacing scale, named: --space-3xs … --space-4xl. See tokens.css. */
  /* Type scale, 1.25 (major-third) ratio: --text-xs … --text-display.     */

  --ease-out: cubic-bezier(0.165, 0.84, 0.44, 1);
  --dur-micro: 120ms;  --dur-short: 240ms;  --dur-long: 400ms;

  --radius-card: 0;  --radius-pill: 0;  --radius-input: 0;
}
```

## Structure vocabulary
- Nav · N1b three-section: logo left · mono uppercase links centre · phone + filled «Заявка» right. Solid paper, 1 px rule below, sticky. Mobile: logo + «Заявка» + burger.
- Hero (home) · H2 split 6/6 — uppercase display left with one accent word, lede ≤ 46ch, two buttons, facts strip with hairline; photo + hairline category index right.
- Ticker · one, between hero and first section. Mono uppercase, accent ✱ separators, 48 s linear, off under reduced-motion.
- Section head · S2 hanging: mono label `01 / …` ABOVE the uppercase heading (never beside — gate 54), ghost button right.
- Category block · F1 bento, 4 columns, spans 2×2 / 1×1 / 2×1, 8 px gap, white label chips `01 ФИГУРНЫЕ` top-left.
- Product block · F6 grid 4-up (3 / 2 / 1 on narrower widths), photo 1:1.08 on paper-2, uppercase name, mono «от 12 900 ₽» tabular-nums, small filled button.
- Footer · Ft1 mast-headed: Logo4, one-sentence tagline, mono contact column right, legal line with ®.
- Dark block («О мастерской», cookie banner) · paper ↔ ink inverted, white logo, same type.

## CTA voice
- Primary · ink fill · radius 0 · 44 px / 36 px small · label + mono `→` trailing · hover = accent fill
- Secondary · ghost, 1 px ink border · same radius · hover = ink fill
- Links in lists · mono uppercase row + trailing `→` in muted, ink on hover
- Markers · arrows only. No squares, no icons; the logo mark appears only as logo.

## Copy voice
- Headlines uppercase, ≤ 3 lines, one accent word max.
- Labels and captions in mono uppercase: `01 / ШЕСТЬ КАТЕГОРИЙ`, `HALO MOON · АРКА С ПОДСВЕТКОЙ`.
- Only real numbers: prices from the catalogue API, «от 1 раб. дня», «1 год», «с 2021». No invented stats.

## Motion stance
- motion-cut · ticker + 1.02 scale on tiles + colour transitions. Nothing reveals on scroll.
- Reduced-motion fallback · ticker stops, transitions ≤ 10 ms.

## Notes — do NOT carry over from the references
- Number beside the heading in a two-column head (Crystacell `КАТАЛОГ … 01/`) — stack vertically instead.
- Three equal rounded feature cards (Xizt) — gate 3.
- Sitemap footer with four link columns + social row (NewGround) — gate 43.
- Pill buttons and 3D renders (Xizt) — wrong register for a workshop; keep square, keep photography.
- Inter as body (NewGround) — banned default; Golos Text carries both roles.

## Exports
`frontend/app/styles/tokens.css` is the source of truth. For Tailwind v4
`@theme`, DTCG `tokens.json`, or shadcn/ui CSS variables, ask *"extend
design.md with Tailwind exports"* — Hallmark will append them.

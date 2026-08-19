# memiro · промпты для генерации дизайн-референсов

Пайплайн taste-skill: **сначала картинки → анализ → код** (skill `imagegen-frontend-web`).
В этой сессии Claude Code нет генератора картинок, поэтому промпты запускаешь ты:
в Claude.ai (генерация изображений), ChatGPT (GPT-4o), Midjourney, FLUX или Recraft.

## Как пользоваться

1. **Этап 1 (выбор направления).** Сгенерируй 4 hero-картинки ниже (по одному промпту за раз,
   формат 16:9). Выбери направление, которое цепляет.
2. **Этап 2 (полный сет).** Возьми блок BRAND WORLD выбранного направления, подставь его
   в каждый из 8 секционных промптов этапа 2 вместо `{BRAND_WORLD}` и сгенерируй 8 картинок.
3. Пришли картинки в Claude Code. Дальше я работаю по скиллу `image-to-code`:
   анализирую и верстаю максимально близко к референсам.

Замечание про кириллицу: современные модели (GPT-4o, Recraft, FLUX 1.1) сносно рисуют
русский текст. Если текст ломается, добавь в конец промпта:
`If Cyrillic text renders poorly, use clean placeholder lines instead of readable text.`

---

## Этап 1 · четыре hero-направления

### 1 · Галерея света (BRAND WORLD A)

```
Website hero section UI design, 16:9, high-end ecommerce for "memiro", a St. Petersburg
studio that manufactures custom interior mirrors. Pristine light mode: paper-white and
cool fog-grey surfaces, graphite near-black text, polished chrome as the only metallic
accent. Composition anchor: image-as-canvas. A full-bleed, art-directed photograph of a
sunlit minimalist bedroom where a tall silver-framed mirror reflects a window; soft
daylight, long shadows, editorial interior photography grade. Text overlaid in a clean
safe area bottom-left: small lowercase wordmark "memiro", short confident Russian
headline "Зеркала под ваш интерьер" in a refined grotesk (Neue-Montreal-like), tight
tracking, one short subline, one dark pill button "Смотреть каталог". Generous negative
space, no badges, no stats, no clutter. Premium, breathable, Awwwards-level art
direction. No purple gradients, no glow, no glassmorphism.
```

### 2 · Ночная витрина (BRAND WORLD B)

```
Website hero section UI design, 16:9, premium ecommerce for "memiro", custom interior
mirrors with LED backlight. Deep dark mode: charcoal #101014 room, the ONLY light source
is the warm amber LED halo glowing behind a large round wall mirror, cinematic long
exposure mood, tactile shadows. Composition anchor: centered low, text in the lower 40%.
Giant statement typography: wide display grotesk (Monument-like), Russian headline
"Свет там, где вы его хотите", tiny lowercase wordmark "memiro" top-left, one amber pill
button "Смотреть каталог". Amber #E3A857 used ONLY for the halo and the button. Elegant,
quiet luxury, gallery-at-night atmosphere. No neon, no purple, no sci-fi glow spam, no
dashboard elements.
```

### 3 · Петербургская классика (BRAND WORLD C)

```
Website hero section UI design, 16:9, editorial luxury ecommerce for "memiro", handmade
interior mirrors from St. Petersburg. Quiet premium neutral palette: pale stone, smoke
grey, ink text, one muted brass detail carried by the photography only. Composition
anchor: editorial side-image 40/60. Right two-thirds: atmospheric photograph of a tall
arched mirror leaning against a classical St. Petersburg interior wall with high
mouldings and morning window light, museum-like stillness, film photography grade. Left
third: calm column with small wordmark "memiro", elegant serif display headline in
Russian "Отражение вашего дома" (Tiempos-like serif), short sans subline, understated
underlined text link "Смотреть каталог →". Archive / dossier mood, hairline rules,
enormous whitespace. No beige-brass cliché overload, no ornament clipart, no gradients.
```

### 4 · Цветной блок (BRAND WORLD D)

```
Website hero section UI design, 16:9, bold modernist ecommerce for "memiro", custom
interior mirrors. Bold studio solid theme: color-blocked diptych, left field in deep
cobalt #2743C7, right field in off-white; a striking cut-out product photo of a round
mirror with black metal frame sits exactly on the seam, casting a soft real shadow
across both fields. Composition anchor: top-left lead, support bottom-right. Compressed
statement typography (Monument-like), Russian headline "88 зеркал. Любой размер." in
off-white on the cobalt field, small wordmark "memiro" top-left, bottom-right a compact
white rectangular button "Смотреть каталог" with sharp corners. Swiss poster energy,
crisp edges, zero gradients, zero decorative blobs, radius 0 everywhere. Premium print
poster feeling, not a template.
```

---

## Этап 2 · полный сет из 8 секций (для выбранного направления)

Перед каждым промптом подставь вместо `{BRAND_WORLD}` абзац стиля из выбранного
hero-промпта (палитра, типографика, настроение) и добавь фразу:
`Same brand world, palette, typography and image grade as the hero. One horizontal image, one section only.`

1. **Hero** — уже есть с этапа 1.
2. **Полоса акции** (16:10):
   `{BRAND_WORLD} Slim full-width promo strip section for the mirror store: short Russian text "Весенние скидки на зеркала с подсветкой" and one small button "К акции". Flat color band using the accent, mini minimalist section, lots of air.`
3. **Категории каталога** (16:9):
   `{BRAND_WORLD} Category section: pristine gapless bento grid of 5 asymmetric photographic tiles (framed mirrors, backlit mirrors, round, figured, floor), each tile a real interior photo with a small Russian label chip. One tile clearly larger. No empty cells.`
4. **Популярные товары** (16:9):
   `{BRAND_WORLD} Product row section: 4 product cards of mirrors on subtle surfaces, Russian names and ruble prices ("11 795 ₽"), one card marked "Акция". Cards share one radius language. Horizontal scroll implied by a cropped 5th card at the edge.`
5. **Как оформить заказ** (16:10):
   `{BRAND_WORLD} Process section: 4 quiet numbered columns in Russian - Выбор, Согласование, Изготовление, Доставка и установка - typographic, thin hairlines, no icons clipart, no cards. Calm, editorial.`
6. **Отзывы** (16:10):
   `{BRAND_WORLD} Testimonial section: two short Russian quotes with client names, asymmetric layout, one small interior photo crop as counterweight. Max 3 lines per quote.`
7. **Финальный CTA** (16:9):
   `{BRAND_WORLD} Closing CTA section: full-bleed atmospheric mirror photograph with tonal overlay, short Russian line "Сделаем по вашему эскизу" and two buttons "Написать в WhatsApp" (primary) and "Написать в Telegram" (secondary). Mini minimalist, decisive.`
8. **Карточка товара** (16:9):
   `{BRAND_WORLD} Ecommerce product page section: left large gallery photo of a crescent backlit mirror with 2 thumbnails, right column in Russian - title "Зеркало месяц Halo Moon", price "11 795 ₽", short spec list, size calculator with two inputs "Ширина, мм / Высота, мм" and a recalculated price, primary button "В корзину". Implementation-friendly, clear hierarchy.`

---

## Что потом

Сгенерированные картинки сложи в `design/imagegen/refs/` (или просто пришли в чат).
Я проанализирую их и сверстаю макеты по референсам через `image-to-code`.

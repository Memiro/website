import { productPath } from "./navigation.ts";

// The catalogue of the WordPress site this storefront replaced. Its products
// kept their slugs but gained a category in the path, and the table below is
// the only place that knows which. It is a table and not a call to the API on
// purpose: a redirect has to work while the backend is down, or an outage
// turns 88 indexed addresses into dead ones (ADR-0015).
// Collected from https://memiro.ru/catalog-sitemap.xml on 2026-09-08 against
// the catalogue of the running contour; all 88 products were found, so no
// product is gone.
const LEGACY_PRODUCT_CATEGORY: Record<string, string> = {
  "aura": "zerkala",
  "brand-vue": "zerkala",
  "bronzovoe-zerkalo-dual-metallic": "zerkala",
  "capsule-metal-led": "zerkala",
  "cres": "zerkala",
  "dentin": "zerkala",
  "duet": "zerkala",
  "dvoynaya-zerkalnaya-arka-gemini": "zerkala",
  "ember": "zerkala",
  "figurnoe-zerkalo-echo": "zerkala",
  "figurnoe-zerkalo-lepus": "zerkala",
  "figurnoe-zerkalo-mickey-front-glow": "zerkala",
  "figurnoe-zerkalo-mickey-glow": "zerkala",
  "figurnoe-zerkalo-s-konturnoy-podsvetkoy-lumiform": "zerkala",
  "figurnoe-zerkalo-sinuous": "zerkala",
  "fioletovoe-zerkalo-amethyst": "zerkala",
  "grimernoe-zerkalo-makeup-lux-white": "zerkala",
  "hazel": "zerkala",
  "kombinatsiya-iz-zerkal-ridge": "zerkala",
  "kombinatsiya-zerkal-dlya-prihozhey-trinity": "zerkala",
  "kompozitsiya-iz-zerkal-orbit": "zerkala",
  "kompozitsiya-zerkal-quartet": "zerkala",
  "kompozitsiya-zerkal-v-spalnyu-aurum": "zerkala",
  "krugloe-zerkalo-kolo": "zerkala",
  "krugloe-zerkalo-s-frontalnoy-podsvetkoy-rim-led": "zerkala",
  "krugloe-zerkalo-s-konturnoy-podsvetkoy-solara": "zerkala",
  "lume-slice": "zerkala",
  "mir-portal": "zerkala",
  "napolnyy-trelyazh-triad": "zerkala",
  "panno-iz-zerkal-blacky": "zerkala",
  "polukrugloe-zerkalo-velumis": "zerkala",
  "pryamougolnoe-zerkalo-kov-duo-graph": "zerkala",
  "pryamougolnoe-zerkalo-lira": "zerkala",
  "pryamougolnoe-zerkalo-noble": "zerkala",
  "pryamougolnoe-zerkalo-panel": "zerkala",
  "pryamougolnoe-zerkalo-slot": "zerkala",
  "pryamougolnoe-zerkalo-smoke": "zerkala",
  "pryamougolnoe-zerkalo-v-rame-luxor": "zerkala",
  "radial-glow": "zerkala",
  "reflex": "zerkala",
  "slice": "zerkala",
  "sostarennoe-zerkalo-solid-black": "zerkala",
  "trelyazh-ternion": "zerkala",
  "uglovoe-zerkalo-s-podsvetkoy-apex": "zerkala",
  "uglovoe-zerkalo-wing": "zerkala",
  "zerkala-v-spalnyu-lull": "zerkala",
  "zerkalnaya-kompozitsiya-grid": "zerkala",
  "zerkalnaya-kompozitsiya-noir": "zerkala",
  "zerkalnaya-kompozitsiya-shine": "zerkala",
  "zerkalo-arka-grand-arc": "zerkala",
  "zerkalo-arka-rosy": "zerkala",
  "zerkalo-arka-s-paryashchey-podsvetkoy-arch-led": "zerkala",
  "zerkalo-arka-s-podsvetkoy-nave": "zerkala",
  "zerkalo-arka-s-vyrezom-grand-arc-cut": "zerkala",
  "zerkalo-dlya-prihozhey-gap": "zerkala",
  "zerkalo-dlya-vannoy-beam": "zerkala",
  "zerkalo-edge-deluxe": "zerkala",
  "zerkalo-iz-dvuh-chastey-glint": "zerkala",
  "zerkalo-kaplya-dew-glow": "zerkala",
  "zerkalo-kapsula-nebula": "zerkala",
  "zerkalo-mesyats-halo-moon": "zerkala",
  "zerkalo-na-dver-full-view": "zerkala",
  "zerkalo-na-dver-view-match": "zerkala",
  "zerkalo-na-shkaf-slide": "zerkala",
  "zerkalo-okno-black-line": "zerkala",
  "zerkalo-okno-v-serebryanoy-rame-silver-line": "zerkala",
  "zerkalo-polukrug-s-frontalnoy-podsvetkoy-eclipse-led": "zerkala",
  "zerkalo-polukrug-s-frontalnoy-podsvetkoy-rimglow-led": "zerkala",
  "zerkalo-polukrug-s-konturnoy-podsvetkoy-halo-led": "zerkala",
  "zerkalo-s-dvumya-liniyami-twin": "zerkala",
  "zerkalo-s-falsh-ramoy-covert": "zerkala",
  "zerkalo-s-frontalnoy-podsvetkoy-capsule-front-led": "zerkala",
  "zerkalo-s-frontalnoy-podsvetkoy-luminor": "zerkala",
  "zerkalo-s-frontalnoy-podsvetkoy-neonix": "zerkala",
  "zerkalo-s-konturnoy-podsvetkoy-i-vyrezom-aeris": "zerkala",
  "zerkalo-s-konturnoy-podsvetkoy-inframe": "zerkala",
  "zerkalo-s-konturnoy-podsvetkoy-v-chernoy-alyuminievoy-rame-blacklume": "zerkala",
  "zerkalo-s-konturnoy-podsvetkoy-v-chernoy-alyuminievoy-rame-s-vyrezom-matrix": "zerkala",
  "zerkalo-s-uzorom-veil": "zerkala",
  "zerkalo-s-vyrezom-nook": "zerkala",
  "zerkalo-trelyazh-golden-glance": "zerkala",
  "zerkalo-v-alyuminievoy-rame-s-vyrezom-modis": "zerkala",
  "zerkalo-v-beloy-alyuminievoy-rame-kov-white": "zerkala",
  "zerkalo-v-chernoy-alyuminievoy-rame-kov-black": "zerkala",
  "zerkalo-v-golubom-bagete-deep-blue": "zerkala",
  "zerkalo-v-rame-falsie": "zerkala",
  "zerkalo-v-serebryanoy-alyuminievoy-rame-kov-silver": "zerkala",
  "zerkalo-v-zolotoy-alyuminievoy-rame-kov-gold": "zerkala",
};

/** Pages that only changed address. What kept its address is absent and stays untouched. */
const MOVED_PAGES: Record<string, string> = {
  "/about-us/": "/about/",
  "/delivery-payment-and-services/": "/delivery/",
  "/privacy-policy/": "/privacy/",
};

// What the old site published and the new one does not: a WordPress sample page,
// its sample post and its default rubric. They are answered 410 rather than
// redirected to a listing — a redirect there reads as a soft 404, saves no
// weight and costs trust (ADR-0015).
export const GONE_PATHS = ["/testovaya-stranicza/", "/privet-mir/", "/category/bez-rubriki/"];

// A union and not one shape with a nullable field: 301 always carries a target
// and 410 never does, and saying so lets the caller stop re-checking.
export type LegacyAnswer =
  | { status: 301; location: string }
  | { status: 410; location: null };

/** The answer an address of the old site earns, or null when it is not one. */
export function legacyResponse(pathname: string): LegacyAnswer | null {
  const path = pathname.endsWith("/") ? pathname : `${pathname}/`;
  if (GONE_PATHS.includes(path)) {
    return { status: 410, location: null };
  }
  const moved = MOVED_PAGES[path];
  if (moved !== undefined) {
    return { status: 301, location: moved };
  }
  const slug = path.startsWith("/mirrors/") ? path.slice("/mirrors/".length, -1) : "";
  const category = LEGACY_PRODUCT_CATEGORY[slug];
  return category === undefined ? null : { status: 301, location: productPath(category, slug) };
}

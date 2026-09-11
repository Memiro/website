import { walkCatalog, type WalkableCatalog, type WalkedProduct } from "./catalog-walk.ts";
import { mediaUrl } from "./media.ts";
import { categoryPath, landingPath, productPath } from "./navigation.ts";
import { escapeXml, xmlLink } from "./xml.ts";

/** The pages that exist without the catalogue. `/cart/`, 404 and 500 are closed and absent. */
export const STATIC_PATHS = ["/", "/catalog/", "/works/", "/about/", "/delivery/", "/contacts/", "/privacy/"];

export interface SitemapImage {
  path: string;
  title: string;
}

export interface SitemapEntry {
  path: string;
  images: SitemapImage[];
  // The day the page last changed, or null for a page written by hand: an
  // invented date is worse than none, a crawler acts on it.
  lastmod: string | null;
}

/** What the sitemap needs of the catalogue — the slice `CatalogApi` already offers. */
export interface SitemapCatalog extends WalkableCatalog {
  landings: () => Promise<{ items: { slug: string, updated_at: string }[] }>;
}

/** The day of the newest stamp given, in the W3C form `lastmod` takes. */
export function newestDay(stamps: string[]): string | null {
  const days = stamps.map((stamp) => Date.parse(stamp)).filter((time) => !Number.isNaN(time));
  return days.length === 0 ? null : new Date(Math.max(...days)).toISOString().slice(0, 10);
}

function pageWithoutImages(path: string, lastmod: string | null = null): SitemapEntry {
  return { path, images: [], lastmod };
}

/** Captioned the way the gallery captions its thumbnails: the name, then the name with a number. */
export function productImages(product: WalkedProduct): SitemapImage[] {
  return product.image_keys.map((key, index) => ({
    path: mediaUrl(key),
    title: index === 0 ? product.name : `${product.name} — фото ${index + 1}`,
  }));
}

/** Every address a crawler may index, in reading order, each with the photographs it shows. */
export async function sitemapEntries(api: SitemapCatalog): Promise<SitemapEntry[]> {
  const [catalog, landings] = await Promise.all([walkCatalog(api), api.landings()]);
  const everyStamp = [
    ...catalog.flatMap(({ category, products }) => [category.updated_at, ...products.map((item) => item.updated_at)]),
    ...landings.items.map((landing) => landing.updated_at),
  ];
  // The home page and the catalogue index show whatever the catalogue holds,
  // so they are as fresh as its freshest row; the pages written by hand carry
  // no stamp at all. Only these two of the static paths are dated.
  const catalogueDay = newestDay(everyStamp);
  const entries: SitemapEntry[] = STATIC_PATHS.map((path) =>
    pageWithoutImages(path, path === "/" || path === "/catalog/" ? catalogueDay : null)
  );
  for (const { category, products } of catalog) {
    entries.push(pageWithoutImages(
      categoryPath(category.slug),
      newestDay([category.updated_at, ...products.map((product) => product.updated_at)]),
    ));
    entries.push(...products.map((product) => ({
      path: productPath(category.slug, product.slug),
      images: productImages(product),
      lastmod: newestDay([product.updated_at]),
    })));
  }
  return [
    ...entries,
    ...landings.items.map((landing) => pageWithoutImages(landingPath(landing.slug), newestDay([landing.updated_at]))),
  ];
}

function imageXml(site: URL, image: SitemapImage): string {
  return `<image:image><image:loc>${xmlLink(site, image.path)}</image:loc><image:title>${escapeXml(image.title)}</image:title></image:image>`;
}

// No changefreq and no priority: Google ignores both. Photographs carry loc and
// title only — caption and geo_location are read by neither Google nor Yandex.
export function sitemapXml(site: URL | undefined, entries: SitemapEntry[]): string | null {
  if (site === undefined) {
    return null;
  }
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ...entries.map((entry) => {
      const images = entry.images.map((image) => imageXml(site, image)).join("");
      const lastmod = entry.lastmod === null ? "" : `<lastmod>${entry.lastmod}</lastmod>`;
      return `  <url><loc>${xmlLink(site, entry.path)}</loc>${lastmod}${images}</url>`;
    }),
    "</urlset>",
    "",
  ].join("\n");
}

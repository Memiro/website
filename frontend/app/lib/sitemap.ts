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
}

/** What the sitemap needs of the catalogue — the slice `CatalogApi` already offers. */
export interface SitemapCatalog extends WalkableCatalog {
  landings: () => Promise<{ items: { slug: string }[] }>;
}

function pageWithoutImages(path: string): SitemapEntry {
  return { path, images: [] };
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
  const entries: SitemapEntry[] = STATIC_PATHS.map(pageWithoutImages);
  for (const { category, products } of catalog) {
    entries.push(pageWithoutImages(categoryPath(category.slug)));
    entries.push(...products.map((product) => ({
      path: productPath(category.slug, product.slug),
      images: productImages(product),
    })));
  }
  return [...entries, ...landings.items.map((landing) => pageWithoutImages(landingPath(landing.slug)))];
}

function imageXml(site: URL, image: SitemapImage): string {
  return `<image:image><image:loc>${xmlLink(site, image.path)}</image:loc><image:title>${escapeXml(image.title)}</image:title></image:image>`;
}

// No lastmod: the API carries no updated_at for any of these. No changefreq and
// no priority: Google ignores both. Photographs carry loc and title only —
// caption and geo_location are read by neither Google nor Yandex.
export function sitemapXml(site: URL | undefined, entries: SitemapEntry[]): string | null {
  if (site === undefined) {
    return null;
  }
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ...entries.map((entry) => {
      const images = entry.images.map((image) => imageXml(site, image)).join("");
      return `  <url><loc>${xmlLink(site, entry.path)}</loc>${images}</url>`;
    }),
    "</urlset>",
    "",
  ].join("\n");
}

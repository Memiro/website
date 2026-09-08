import { productPath } from "./navigation.ts";
import { absoluteUrl } from "./seo.ts";

/** The pages that exist without the catalogue. `/cart/`, 404 and 500 are closed and absent. */
export const STATIC_PATHS = ["/", "/catalog/", "/works/", "/about/", "/delivery/", "/contacts/", "/privacy/"];

interface Paged<Item> {
  items: Item[];
}

interface Listing {
  items: { slug: string }[];
  pages: number;
}

/** What the sitemap needs of the catalogue — the slice `CatalogApi` already offers. */
export interface SitemapCatalog {
  categories: () => Promise<Paged<{ slug: string }>>;
  landings: () => Promise<Paged<{ slug: string }>>;
  categoryProducts: (slug: string, search?: string) => Promise<Listing>;
}

async function categoryPaths(api: SitemapCatalog, slug: string): Promise<string[]> {
  const paths = [`/catalog/${slug}/`];
  const first = await api.categoryProducts(slug, "");
  for (let page = 1; page <= first.pages; page += 1) {
    const listing = page === 1 ? first : await api.categoryProducts(slug, `page=${page}`);
    paths.push(...listing.items.map((product) => productPath(slug, product.slug)));
  }
  return paths;
}

/**
 * Every address a crawler may index, in reading order. The listing is walked
 * page by page: a catalogue that outgrows one page would otherwise lose its
 * tail without anything failing.
 */
export async function sitemapPaths(api: SitemapCatalog): Promise<string[]> {
  const [categories, landings] = await Promise.all([api.categories(), api.landings()]);
  const catalog: string[] = [];
  for (const category of categories.items) {
    catalog.push(...await categoryPaths(api, category.slug));
  }
  return [...STATIC_PATHS, ...catalog, ...landings.items.map((landing) => `/${landing.slug}/`)];
}

// No lastmod: the API carries no updated_at for any of these. No changefreq and
// no priority: Google ignores both.
export function sitemapXml(site: URL | undefined, paths: string[]): string | null {
  const locations = paths.map((path) => absoluteUrl(site, path));
  if (locations.some((location) => location === null)) {
    return null;
  }
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...locations.map((location) => `  <url><loc>${location}</loc></url>`),
    "</urlset>",
    "",
  ].join("\n");
}

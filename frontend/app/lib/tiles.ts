import type { CatalogApi } from "./catalog-api.ts";

export interface Tile {
  href: string;
  label: string;
}

/**
 * The tiles of the storefront: landings the owner wrote, and the categories
 * themselves while he has written none.
 */
export async function catalogTiles(api: CatalogApi): Promise<Tile[]> {
  const landings = (await api.landings()).items;
  if (landings.length > 0) {
    return landings.map((landing) => ({ href: `/${landing.slug}/`, label: landing.heading }));
  }
  const categories = (await api.categories()).items;
  return categories.map((category) => ({ href: `/catalog/${category.slug}/`, label: category.name }));
}

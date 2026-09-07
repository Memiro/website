import type { CatalogApi, LandingSummary } from "./catalog-api.ts";

/** What the tiles need of the catalogue: the two listings they are built from. */
export type TileSource = Pick<CatalogApi, "landings" | "categories">;

export interface Tile {
  href: string;
  label: string;
}

/**
 * The tiles of the home page: the landings the owner wrote.
 *
 * A landing is the entrance worth showing on the storefront (ADR-0003): it has
 * its own address, heading and text, and it is what the search index carries.
 * A category is a kind of product, not a shop-window heading — "round" and
 * "with a backlight" are not categories — so while the owner has written no
 * landing, the home page falls back to the categories themselves.
 */
export async function landingTiles(api: TileSource): Promise<Tile[]> {
  const landings = (await api.landings()).items;
  if (landings.length > 0) {
    return landings.map(landingTile);
  }
  return categoryTiles(api);
}

/**
 * The tiles of the catalogue root: the categories.
 *
 * The root keeps its own structure. The landings stand on the home page and on
 * the category each of them narrows; the root is where the sections live.
 */
export async function categoryTiles(api: TileSource): Promise<Tile[]> {
  const categories = (await api.categories()).items;
  return categories.map((category) => ({ href: `/catalog/${category.slug}/`, label: category.name }));
}

/** The landings of one category, in the owner's order: how a visitor and a crawler reach them. */
export function landingsOfCategory(landings: LandingSummary[], categorySlug: string): Tile[] {
  return landings.filter((landing) => landing.category_slug === categorySlug).map(landingTile);
}

function landingTile(landing: LandingSummary): Tile {
  return { href: `/${landing.slug}/`, label: landing.heading };
}

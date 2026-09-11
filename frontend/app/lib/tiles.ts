import type { CatalogApi, ProductImage } from "./catalog-api.ts";
import { categoryPath, landingPath } from "./navigation.ts";

export interface Tile {
  href: string;
  label: string;
  /** The mirror this tile leads to, or nothing while its products are unphotographed. */
  image: ProductImage | null;
}

/**
 * The tiles of the storefront: landings the owner wrote, and the categories
 * themselves while he has written none.
 */
export async function catalogTiles(api: CatalogApi): Promise<Tile[]> {
  const landings = (await api.landings()).items;
  if (landings.length > 0) {
    return landings.map((landing) => ({ href: landingPath(landing.slug), label: landing.heading, image: landing.image }));
  }
  const categories = (await api.categories()).items;
  return categories.map((category) => ({ href: categoryPath(category.slug), label: category.name, image: category.image }));
}

export type TileSpan = "2x2" | "1x1" | "2x1";

// Composed for six tiles on four columns so no cell stays empty; larger
// sets repeat the pattern.
const BENTO: readonly TileSpan[] = ["2x2", "1x1", "1x1", "2x1", "2x1", "2x1"];

export function tileSpan(index: number): TileSpan {
  return BENTO[index % BENTO.length];
}

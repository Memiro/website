import type { CategoryPage, ProductCard, ProductSummary } from "./catalog-api.ts";
import { EMPTY_QUERY, FIRST_PAGE, catalogSearch } from "./catalog-query.ts";

export const RELATED_SIZE = 4;
// The attribute is matched by its name: attributes are rows of the owner's
// dictionary, per category, and "Форма" is the one every mirror declares.
export const SHAPE_ATTRIBUTE = "Форма";

export interface CategoryReader {
  categoryProducts(slug: string, search?: string): Promise<CategoryPage>;
}

/** The dictionary row this mirror's shape is, or null when it declares none. */
export function shapeValueId(product: ProductCard): string | null {
  const shape = product.attributes.find((attribute) => attribute.name === SHAPE_ATTRIBUTE);
  return shape?.declared_value_id ?? null;
}

/** How many items after `index` the neighbours want: half of `size`, plus what the start of the list cannot supply. */
function wantedAfter(index: number, size: number): number {
  return size - Math.min(index, Math.floor(size / 2));
}

/** Up to `size` items around `slug` in list order — half after, half before, the edges borrowing from the other side; the head when `slug` is absent. */
export function neighbours<Item extends { slug: string }>(items: readonly Item[], slug: string, size: number): Item[] {
  const index = items.findIndex((item) => item.slug === slug);
  if (index === -1) {
    return items.slice(0, size);
  }
  const after = Math.min(items.length - index - 1, wantedAfter(index, size));
  const before = Math.min(index, size - after);
  return [...items.slice(index - before, index), ...items.slice(index + 1, index + 1 + after)];
}

/** Mirrors of the same shape standing next to this one in the category listing; the category itself without a shape. */
export async function relatedProducts(reader: CategoryReader, categorySlug: string, product: ProductCard): Promise<ProductSummary[]> {
  const shape = shapeValueId(product);
  const values = shape === null ? [] : [shape];
  const items: ProductSummary[] = [];
  let index = -1;
  let page = FIRST_PAGE;
  let pages = 1; // one page until the listing says how many
  // The listing arrives one page at a time; walk it until this mirror is on it
  // with enough items after it, so the neighbours are the real alphabetical
  // ones and not the first page's. A mirror missing from its own listing
  // (a shape row renamed under it) walks every page and falls back to the head.
  while (page <= pages && (index === -1 || items.length - index - 1 < wantedAfter(index, RELATED_SIZE))) {
    const listing = await reader.categoryProducts(categorySlug, catalogSearch({ ...EMPTY_QUERY, values, page }));
    items.push(...listing.items);
    index = items.findIndex((item) => item.slug === product.slug);
    pages = listing.pages;
    page += 1;
  }
  return neighbours(items, product.slug, RELATED_SIZE);
}

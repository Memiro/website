import type { CategoryPage, ProductCard, ProductSummary } from "./catalog-api.ts";
import { FIRST_PAGE, catalogSearch } from "./catalog-query.ts";

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

/** Up to `size` items closest to `slug` in list order, the next ones first; the whole head when `slug` is absent. */
export function neighbours<Item extends { slug: string }>(items: readonly Item[], slug: string, size: number): Item[] {
  const index = items.findIndex((item) => item.slug === slug);
  if (index === -1) {
    return items.slice(0, size);
  }
  const after = items.slice(index + 1);
  const before = items.slice(0, index).reverse();
  const picked: Item[] = [];
  while (picked.length < size && (after.length > 0 || before.length > 0)) {
    const takeAfter = after.length > 0 && (picked.length % 2 === 0 || before.length === 0);
    const next = takeAfter ? after.shift() : before.shift();
    if (next !== undefined) {
      picked.push(next);
    }
  }
  return picked.sort((left, right) => items.indexOf(left) - items.indexOf(right));
}

/** Mirrors of the same shape standing next to this one in the category listing; the category itself without a shape. */
export async function relatedProducts(reader: CategoryReader, categorySlug: string, product: ProductCard): Promise<ProductSummary[]> {
  const shape = shapeValueId(product);
  const values = shape === null ? [] : [shape];
  const items: ProductSummary[] = [];
  let page = FIRST_PAGE;
  let pages = FIRST_PAGE;
  // The listing arrives one page at a time; walk it until this mirror is on it,
  // so the neighbours are the real alphabetical ones and not the first page's.
  while (page <= pages && !items.some((item) => item.slug === product.slug)) {
    const listing = await reader.categoryProducts(categorySlug, catalogSearch({ values, priceMin: "", priceMax: "", sort: "name", page }));
    items.push(...listing.items);
    pages = listing.pages;
    page += 1;
  }
  return neighbours(items, product.slug, RELATED_SIZE);
}

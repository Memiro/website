export interface WalkedCategory {
  slug: string;
  name: string;
}

export interface WalkedProduct {
  slug: string;
  name: string;
  price_from: string | null;
  image_keys: string[];
}

/** What a walk needs of the catalogue — the slice `CatalogApi` already offers. */
export interface WalkableCatalog {
  categories: () => Promise<{ items: WalkedCategory[] }>;
  categoryProducts: (slug: string, search?: string) => Promise<{ items: WalkedProduct[]; pages: number }>;
}

export interface CategoryProducts {
  category: WalkedCategory;
  products: WalkedProduct[];
}

// The listing is walked page by page: a catalogue that outgrows one page
// would otherwise lose its tail without anything failing.
async function everyProductOf(api: WalkableCatalog, category: WalkedCategory): Promise<CategoryProducts> {
  const first = await api.categoryProducts(category.slug, "");
  const products = [...first.items];
  for (let page = 2; page <= first.pages; page += 1) {
    products.push(...(await api.categoryProducts(category.slug, `page=${page}`)).items);
  }
  return { category, products };
}

/** Every published product of every category, in the owner's order. */
export async function walkCatalog(api: WalkableCatalog): Promise<CategoryProducts[]> {
  const categories = await api.categories();
  const walked: CategoryProducts[] = [];
  for (const category of categories.items) {
    walked.push(await everyProductOf(api, category));
  }
  return walked;
}

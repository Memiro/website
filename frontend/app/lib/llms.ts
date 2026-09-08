import { absoluteUrl } from "./seo.ts";
import { SITE_NAME } from "./site.ts";

interface Named {
  slug: string;
}

/** What the document needs of the catalogue — the slice `CatalogApi` already offers. */
export interface LlmsCatalog {
  categories: () => Promise<{ items: (Named & { name: string })[] }>;
  landings: () => Promise<{ items: (Named & { heading: string })[] }>;
}

function link(site: URL, label: string, path: string): string {
  return `- [${label}](${absoluteUrl(site, path)})`;
}

/**
 * The site as a language model would rather read it. No large crawler reads
 * llms.txt today — what actually carries this storefront into an assistant's
 * answer is the server-rendered HTML and the JSON-LD. This is a cheap bet on
 * the proposal catching on, and it is the lowest priority of the SEO work.
 */
export async function llmsText(site: URL | undefined, api: LlmsCatalog): Promise<string | null> {
  if (site === undefined) {
    return null;
  }
  const [categories, landings] = await Promise.all([api.categories(), api.landings()]);
  return [
    `# ${SITE_NAME}`,
    "",
    "Производство интерьерных зеркал на заказ в Санкт-Петербурге: изготовление,",
    "доставка и установка. Размер, форма, подсветка и рама выбираются под",
    "интерьер; цена считается по конфигурации, готовых к отгрузке позиций нет.",
    "",
    "## Каталог",
    "",
    link(site, "Все зеркала", "/catalog/"),
    ...categories.items.map((category) => link(site, category.name, `/catalog/${category.slug}/`)),
    "",
    "## Подборки",
    "",
    ...landings.items.map((landing) => link(site, landing.heading, `/${landing.slug}/`)),
    "",
    "## О студии",
    "",
    link(site, "О нас", "/about/"),
    link(site, "Наши работы — фотографии установок у клиентов", "/works/"),
    link(site, "Доставка, установка, оплата и возврат", "/delivery/"),
    link(site, "Контакты и адрес шоурума", "/contacts/"),
    "",
  ].join("\n");
}

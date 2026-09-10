import { walkCatalog, type WalkableCatalog, type WalkedProduct } from "./catalog-walk.ts";
import { mediaUrl } from "./media.ts";
import { productPath } from "./navigation.ts";
import { escapeXml, xmlLink } from "./xml.ts";

/** The format allows ten pictures per offer; the rest of a gallery stays on the card. */
export const MAX_PICTURES = 10;
/** In YML `available="false"` already means "to order"; the note says what the price is. */
export const SALES_NOTES = "Цена от, изготовление под заказ";
const CURRENCY = "RUB";
// Cards are read a few at a time: one by one is slow for a hundred, all at
// once is a burst the API has no reason to take from its own storefront.
const CARDS_AT_ONCE = 4;

export interface YmlCategory {
  id: number;
  name: string;
}

export interface YmlShop {
  name: string;
  company: string;
  categories: YmlCategory[];
}

export interface YmlOffer {
  id: string;
  path: string;
  price: string;
  categoryId: number;
  pictures: string[];
  name: string;
  description: string;
}

/** What the feed needs of the catalogue: the walk plus the card, which alone carries the description. */
export interface YmlCatalog extends WalkableCatalog {
  product: (slug: string) => Promise<{ description: string }>;
}

export interface YmlContent {
  categories: YmlCategory[];
  offers: YmlOffer[];
}

interface PricedProduct extends WalkedProduct {
  price_from: string;
}

function isPriced(product: WalkedProduct): product is PricedProduct {
  return product.price_from !== null;
}

async function inBatches<Item, Result>(items: Item[], size: number, work: (item: Item) => Promise<Result>): Promise<Result[]> {
  const results: Result[] = [];
  for (let start = 0; start < items.length; start += size) {
    results.push(...await Promise.all(items.slice(start, start + size).map(work)));
  }
  return results;
}

/** Every priced published product as an offer, in the owner's order; a product without a price has nothing to feed. */
export async function ymlContent(api: YmlCatalog): Promise<YmlContent> {
  const walked = await walkCatalog(api);
  const categories = walked.map(({ category }, index) => ({ id: index + 1, name: category.name }));
  const priced = walked.flatMap(({ category, products }, index) =>
    products.filter(isPriced).map((product) => ({ categorySlug: category.slug, categoryId: categories[index].id, product })));
  const offers = await inBatches(priced, CARDS_AT_ONCE, async ({ categorySlug, categoryId, product }) => ({
    id: product.slug,
    path: productPath(categorySlug, product.slug),
    price: product.price_from,
    categoryId,
    pictures: product.image_keys.slice(0, MAX_PICTURES).map(mediaUrl),
    name: product.name,
    description: (await api.product(product.slug)).description,
  }));
  return { categories, offers };
}

function element(name: string, text: string): string {
  return `<${name}>${escapeXml(text)}</${name}>`;
}

function offerXml(site: URL, offer: YmlOffer): string {
  return [
    `    <offer id="${escapeXml(offer.id)}" available="false">`,
    `      <url>${xmlLink(site, offer.path)}</url>`,
    `      <price>${Number(offer.price)}</price>`,
    `      <currencyId>${CURRENCY}</currencyId>`,
    `      <categoryId>${offer.categoryId}</categoryId>`,
    ...offer.pictures.map((picture) => `      <picture>${xmlLink(site, picture)}</picture>`),
    `      ${element("name", offer.name)}`,
    `      ${element("description", offer.description)}`,
    `      ${element("sales_notes", SALES_NOTES)}`,
    "    </offer>",
  ].join("\n");
}

// The "Товары и цены" feed of Yandex.Webmaster, which puts a price and a
// picture into the search snippet. Honest about the shop: the price is the
// "from" price of the cheapest configuration, and nothing is in stock.
export function ymlText(site: URL | undefined, shop: YmlShop, offers: YmlOffer[], now: Date): string | null {
  if (site === undefined) {
    return null;
  }
  const date = now.toISOString().replace(/\.\d{3}Z$/, "+00:00");
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<yml_catalog date="${date}">`,
    "  <shop>",
    `    ${element("name", shop.name)}`,
    `    ${element("company", shop.company)}`,
    `    <url>${xmlLink(site, "/")}</url>`,
    `    <currencies><currency id="${CURRENCY}" rate="1"/></currencies>`,
    "    <categories>",
    ...shop.categories.map((category) => `      <category id="${category.id}">${escapeXml(category.name)}</category>`),
    "    </categories>",
    "    <offers>",
    ...offers.map((offer) => offerXml(site, offer)),
    "    </offers>",
    "  </shop>",
    "</yml_catalog>",
    "",
  ].join("\n");
}

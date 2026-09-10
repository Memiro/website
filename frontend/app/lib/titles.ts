import { modelPlural } from "./plural.ts";

const CITY = "в Санкт-Петербурге";
const BRAND_SUFFIX = " — Memiro";
const CYRILLIC = /[Ѐ-ӿ]/;
// Only the first ". " ends a sentence: a decimal such as "4.5 мм" does not.
const FIRST_SENTENCE = /^[\s\S]*?\.(?=\s|$)/;
const SENTENCE_END = /[.!?…]$/;

/** The rouble sum the way the card prints it: thousands separated the Russian way. */
function roubles(amount: string): string {
  return `${new Intl.NumberFormat("ru-RU").format(Number(amount))} ₽`;
}

// Eight names are bare ("Aura"), eighty already say what they are ("Зеркало в
// раме Falsie"): a name without Cyrillic is the one that needs the noun.
function mirrorName(name: string): string {
  return CYRILLIC.test(name) ? name : `Зеркало ${name}`;
}

function firstSentence(text: string): string {
  const sentence = (FIRST_SENTENCE.exec(text.trim())?.[0] ?? text.trim()).trim();
  return SENTENCE_END.test(sentence) ? sentence : `${sentence}.`;
}

export function productTitle(name: string): string {
  return `${mirrorName(name)} на заказ ${CITY}${BRAND_SUFFIX}`;
}

export function productDescription(name: string, priceFrom: string | null, description: string): string {
  const price = priceFrom === null ? "" : `${mirrorName(name)} на заказ от ${roubles(priceFrom)}. `;
  return `${price}${firstSentence(description)} Изготовление, доставка и монтаж ${CITY}.`;
}

/** A page past the first is its own address and names its number, before the brand when the title ends with one. */
export function pagedTitle(title: string, page: number): string {
  if (page <= 1) {
    return title;
  }
  const brand = /\s—\s[Mm]emiro$/.exec(title);
  return brand === null
    ? `${title} — страница ${page}`
    : `${title.slice(0, brand.index)} — страница ${page}${brand[0]}`;
}

export function listingTitle(name: string, page: number): string {
  return pagedTitle(`${name} на заказ ${CITY}${BRAND_SUFFIX}`, page);
}

export function listingDescription(name: string, total: number, cheapest: string | null): string {
  const from = cheapest === null ? "" : ` от ${roubles(cheapest)}`;
  return `${name} на заказ: ${total} ${modelPlural(total)}${from}. Размер, форма, подсветка и рама под ваш интерьер. Собственное производство, доставка и монтаж.`;
}

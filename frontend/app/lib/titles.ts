import { modelPlural } from "./plural.ts";

const CITY = "в Санкт-Петербурге";
const BRAND_SUFFIX = " — Memiro";
const CYRILLIC = /[Ѐ-ӿ]/;
// A sentence ends at the first stop followed by a space or the end: a decimal
// such as "4.5 мм" does not end one.
const FIRST_SENTENCE = /^[\s\S]*?[.!?…](?=\s|$)/;
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

/** The first sentence of the copy, with its stop; empty copy gives nothing. */
function firstSentence(text: string): string {
  const trimmed = text.trim();
  if (trimmed === "") {
    return "";
  }
  const sentence = (FIRST_SENTENCE.exec(trimmed)?.[0] ?? trimmed).trim();
  return SENTENCE_END.test(sentence) ? sentence : `${sentence}.`;
}

function orderTitle(subject: string): string {
  return `${subject} на заказ ${CITY}${BRAND_SUFFIX}`;
}

export function productTitle(name: string): string {
  return orderTitle(mirrorName(name));
}

export function productDescription(name: string, priceFrom: string | null, description: string): string {
  const price = priceFrom === null ? "" : `${mirrorName(name)} на заказ от ${roubles(priceFrom)}.`;
  return [price, firstSentence(description), `Изготовление, доставка и монтаж ${CITY}.`]
    .filter((part) => part !== "")
    .join(" ");
}

/** A page past the first is its own address and names its number, before the brand when the title ends with one. */
export function pagedTitle(title: string, page: number): string {
  if (page <= 1) {
    return title;
  }
  // The owner's landing titles spell the brand in lowercase until he fixes them.
  const brand = /\s—\s[Mm]emiro$/.exec(title);
  return brand === null
    ? `${title} — страница ${page}`
    : `${title.slice(0, brand.index)} — страница ${page}${brand[0]}`;
}

export function listingTitle(name: string, page: number): string {
  return pagedTitle(orderTitle(name), page);
}

export function listingDescription(name: string, total: number, cheapest: string | null): string {
  const from = cheapest === null ? "" : ` от ${roubles(cheapest)}`;
  return `${name} на заказ: ${total} ${modelPlural(total)}${from}. Размер, форма, подсветка и рама под ваш интерьер. Собственное производство, доставка и монтаж.`;
}

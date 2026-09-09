type Forms = readonly [one: string, few: string, many: string];

const PRODUCT: Forms = ["товар", "товара", "товаров"];
const CATEGORY: Forms = ["категория", "категории", "категорий"];

/** Russian plural of "товар" for a counter the storefront prints beside a heading. */
export function productPlural(count: number): string {
  return declension(count, PRODUCT);
}

/** Russian plural of "категория" for the label above the catalogue heading. */
export function categoryPlural(count: number): string {
  return declension(count, CATEGORY);
}

function declension(count: number, [one, few, many]: Forms): string {
  const tail = Math.abs(count) % 100;
  const last = tail % 10;
  if (tail > 10 && tail < 20) {
    return many;
  }
  if (last > 1 && last < 5) {
    return few;
  }
  return last === 1 ? one : many;
}

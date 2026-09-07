/** Russian plural of "товар" for a counter the storefront prints beside a heading. */
export function productPlural(count: number): string {
  const tail = Math.abs(count) % 100;
  const last = tail % 10;
  if (tail > 10 && tail < 20) {
    return "товаров";
  }
  if (last > 1 && last < 5) {
    return "товара";
  }
  return last === 1 ? "товар" : "товаров";
}

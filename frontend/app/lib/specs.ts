import type { ProductAttribute } from "./catalog-api.ts";

export interface Spec {
  name: string;
  value: string;
}

function declaredValue(attribute: ProductAttribute): string | null {
  if (attribute.kind === "number") {
    // The single row of a numeric attribute carries the declared count.
    const [row] = attribute.values;
    return row?.quantity === null || row?.quantity === undefined ? null : `${Number(row.quantity)} шт.`;
  }
  const declared = attribute.values.find((value) => value.id === attribute.declared_value_id);
  return declared?.name ?? null;
}

/** What the product is made of, in the owner's attribute order, skipping what it never declared. */
export function productSpecs(attributes: readonly ProductAttribute[]): Spec[] {
  const specs: Spec[] = [];
  for (const attribute of attributes) {
    const value = declaredValue(attribute);
    if (value !== null) {
      specs.push({ name: attribute.name, value });
    }
  }
  return specs;
}

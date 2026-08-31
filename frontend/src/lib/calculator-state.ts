import type { CalculatedPrice, ProductCard } from "./catalog-api";

export interface CalculatorSelection {
  attributeId: string;
  valueId: string | null;
  quantity: string | null;
}

export interface CalculatorState {
  widthMm: number;
  heightMm: number;
  selections: CalculatorSelection[];
}

export interface PricePresentation {
  kind: "priced" | "wish" | "hidden" | "unavailable";
  total: string | null;
  message: string | null;
}

export function initialCalculatorState(product: ProductCard): CalculatorState {
  const variant = product.variants[0];
  if (variant === undefined) {
    throw new Error("A calculator product must have a variant");
  }
  return {
    widthMm: variant.width_mm,
    heightMm: variant.height_mm,
    selections: variant.overrides.map((override) => ({
      attributeId: override.attribute_id,
      valueId: override.value_id,
      quantity: override.quantity,
    })),
  };
}

export function pricePresentation(result: CalculatedPrice): PricePresentation {
  switch (result.verdict) {
    case "BEYOND_LIMITS":
      return {
        kind: "wish",
        total: null,
        message: "Этот размер изготовим по индивидуальному пожеланию.",
      };
    case "HIDDEN":
      return {
        kind: "hidden",
        total: null,
        message: "Стоимость этой конфигурации уточнит менеджер.",
      };
    case "NOT_PRICEABLE":
      return {
        kind: "unavailable",
        total: null,
        message: "Эту конфигурацию пока нельзя рассчитать.",
      };
    case "PRICED":
      return { kind: "priced", total: result.total, message: null };
  }
}

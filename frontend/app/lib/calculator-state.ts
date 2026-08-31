import type { CalculatedPrice, CalculateRequest, ProductCard } from "./catalog-api";

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
  deltas: PriceDelta[];
}

export interface PriceDelta {
  attributeId: string;
  valueId: string | null;
  amount: string;
}

export function initialCalculatorState(product: ProductCard): CalculatorState {
  return calculatorStateForVariant(product, 0);
}

export function calculatorStateForVariant(product: ProductCard, index: number): CalculatorState {
  const variant = product.variants[index];
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

export function toCalculateRequest(productId: string, state: CalculatorState): CalculateRequest {
  return {
    product_id: productId,
    width_mm: state.widthMm,
    height_mm: state.heightMm,
    selections: state.selections.map((selection) => ({
      attribute_id: selection.attributeId,
      value_id: selection.valueId,
      quantity: selection.quantity,
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
        deltas: [],
      };
    case "HIDDEN":
      return {
        kind: "hidden",
        total: null,
        message: "Стоимость этой конфигурации уточнит менеджер.",
        deltas: [],
      };
    case "NOT_PRICEABLE":
      return {
        kind: "unavailable",
        total: null,
        message: "Эту конфигурацию пока нельзя рассчитать.",
        deltas: [],
      };
    case "PRICED":
      return {
        kind: "priced",
        total: result.total,
        message: null,
        deltas: result.selection_deltas.map((delta) => ({
          attributeId: delta.attribute_id,
          valueId: delta.value_id,
          amount: delta.delta,
        })),
      };
  }
}

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

// A product may legitimately carry no ready sizes: the owner priced none yet,
// or removed the last one. Then there is no size to open on and the customer
// types his own — the calculator must not refuse to exist.
export function initialCalculatorState(product: ProductCard): CalculatorState | null {
  return product.variants.length === 0 ? null : calculatorStateForVariant(product, 0);
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

export type CalculatePrice = (request: CalculateRequest) => Promise<CalculatedPrice>;

export type PriceRequest =
  | { status: "idle" }
  | { status: "invalid"; fields: string[] }
  | { status: "loading" }
  | { status: "done"; price: PricePresentation }
  | { status: "error" };

export const WIDTH_FIELD = "widthMm";
export const HEIGHT_FIELD = "heightMm";

export class Calculator {
  public widthText: string;
  public heightText: string;
  public selections: CalculatorSelection[];
  public request: PriceRequest;
  public priced: CalculatorState | null;
  private readonly product: ProductCard;
  private readonly calculate: CalculatePrice;
  private generation: number;

  public constructor(product: ProductCard, calculate: CalculatePrice) {
    const state = initialCalculatorState(product);
    this.product = product;
    this.calculate = calculate;
    this.widthText = state === null ? "" : String(state.widthMm);
    this.heightText = state === null ? "" : String(state.heightMm);
    this.selections = state === null ? [] : state.selections;
    this.request = { status: "idle" };
    this.priced = null;
    this.generation = 0;
  }

  /** The ready size the current configuration stands on, or null for a size the customer typed. */
  public get variantIndex(): number | null {
    const configuration = this.configuration();
    if (configuration === null) {
      return null;
    }
    const index = this.product.variants.findIndex(
      (variant) => variant.width_mm === configuration.widthMm && variant.height_mm === configuration.heightMm,
    );
    return index === -1 ? null : index;
  }

  public chosenValue(attributeId: string): string {
    return this.selectionOf(attributeId)?.valueId ?? "";
  }

  public chosenQuantity(attributeId: string): string {
    return this.selectionOf(attributeId)?.quantity ?? "";
  }

  public isInvalid(field: string): boolean {
    return this.request.status === "invalid" && this.request.fields.includes(field);
  }

  public async chooseVariant(index: number): Promise<void> {
    if (this.product.variants[index] === undefined) {
      return;
    }
    const state = calculatorStateForVariant(this.product, index);
    this.widthText = String(state.widthMm);
    this.heightText = String(state.heightMm);
    this.selections = state.selections;
    await this.refresh();
  }

  public async setWidth(text: string): Promise<void> {
    this.widthText = text;
    await this.refresh();
  }

  public async setHeight(text: string): Promise<void> {
    this.heightText = text;
    await this.refresh();
  }

  public async chooseValue(attributeId: string, valueId: string): Promise<void> {
    this.selections = withSelection(this.selections, attributeId, valueId === "" ? null : { attributeId, valueId, quantity: null });
    await this.refresh();
  }

  public async setQuantity(attributeId: string, quantity: string): Promise<void> {
    const typed = quantity.trim();
    this.selections = withSelection(this.selections, attributeId, typed === "" ? null : { attributeId, valueId: null, quantity: typed });
    await this.refresh();
  }

  public async refresh(): Promise<void> {
    const generation = this.generation + 1;
    this.generation = generation;
    const configuration = this.configuration();
    if (configuration === null) {
      this.request = { status: "invalid", fields: this.invalidFields() };
      return;
    }
    this.request = { status: "loading" };
    try {
      const price = pricePresentation(await this.calculate(toCalculateRequest(this.product.id, configuration)));
      if (generation !== this.generation) {
        return;
      }
      this.priced = configuration;
      this.request = { status: "done", price };
    } catch {
      if (generation !== this.generation) {
        return;
      }
      this.request = { status: "error" };
    }
  }

  private selectionOf(attributeId: string): CalculatorSelection | undefined {
    return this.selections.find((selection) => selection.attributeId === attributeId);
  }

  private configuration(): CalculatorState | null {
    if (this.invalidFields().length > 0) {
      return null;
    }
    return {
      widthMm: Number(this.widthText),
      heightMm: Number(this.heightText),
      selections: this.selections.map((selection) => ({ ...selection })),
    };
  }

  private invalidFields(): string[] {
    const fields: string[] = [];
    if (!isSize(this.widthText)) {
      fields.push(WIDTH_FIELD);
    }
    if (!isSize(this.heightText)) {
      fields.push(HEIGHT_FIELD);
    }
    for (const selection of this.selections) {
      if (selection.quantity !== null && !isQuantity(selection.quantity)) {
        fields.push(selection.attributeId);
      }
    }
    return fields;
  }
}

function withSelection(
  selections: CalculatorSelection[],
  attributeId: string,
  selection: CalculatorSelection | null,
): CalculatorSelection[] {
  const kept = selections.filter((current) => current.attributeId !== attributeId);
  return selection === null ? kept : [...kept, selection];
}

function isSize(text: string): boolean {
  return /^\d+$/.test(text.trim()) && Number(text) > 0;
}

function isQuantity(text: string): boolean {
  return /^\d+(\.\d+)?$/.test(text.trim());
}

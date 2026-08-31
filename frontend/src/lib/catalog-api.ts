export type PricingVerdict = "PRICED" | "BEYOND_LIMITS" | "NOT_PRICEABLE" | "HIDDEN";

export interface Category {
  name: string;
  slug: string;
}

export interface ProductSummary {
  name: string;
  slug: string;
  price_from: string | null;
  image_keys: string[];
}

export interface ProductAttributeValue {
  id: string | null;
  name: string;
  quantity: string | null;
}

export interface ProductAttribute {
  id: string;
  name: string;
  values: ProductAttributeValue[];
}

export interface VariantOverride {
  attribute_id: string;
  value_id: string | null;
  quantity: string | null;
}

export interface ProductVariant {
  width_mm: number;
  height_mm: number;
  price: string;
  overrides: VariantOverride[];
}

export interface ProductCard extends ProductSummary {
  description: string;
  attributes: ProductAttribute[];
  variants: ProductVariant[];
}

export interface CalculateSelection {
  attribute_id: string;
  value_id: string | null;
  quantity: string | null;
}

export interface CalculateRequest {
  product_id: string;
  width_mm: number;
  height_mm: number;
  selections: CalculateSelection[];
}

export interface SelectionDelta {
  attribute_id: string;
  value_id: string | null;
  delta: string;
}

export interface CalculatedPrice {
  verdict: PricingVerdict;
  total: string | null;
  selection_deltas: SelectionDelta[];
  size_surcharge_from_long_side_mm?: number | null;
}

export class ApiResponseError extends Error {
  public readonly status: number;

  public constructor(status: number) {
    super(`The public API returned HTTP ${status}`);
    this.status = status;
  }
}

export class CatalogApi {
  private readonly baseUrl: string;

  public constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  public async categories(): Promise<Category[]> {
    return this.get<Category[]>("/catalog/categories");
  }

  public async categoryProducts(slug: string): Promise<ProductSummary[]> {
    return this.get<ProductSummary[]>(`/catalog/categories/${encodeURIComponent(slug)}/products`);
  }

  public async product(slug: string): Promise<ProductCard> {
    return this.get<ProductCard>(`/catalog/products/${encodeURIComponent(slug)}`);
  }

  private async get<ResponseBody>(path: string): Promise<ResponseBody> {
    const response = await fetch(new URL(path, this.baseUrl));
    if (!response.ok) {
      throw new ApiResponseError(response.status);
    }
    return (await response.json()) as ResponseBody;
  }
}

export async function calculate(request: CalculateRequest): Promise<CalculatedPrice> {
  const response = await fetch("/api/calculate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new ApiResponseError(response.status);
  }
  return (await response.json()) as CalculatedPrice;
}

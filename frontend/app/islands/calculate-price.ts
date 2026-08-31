import type { CalculateRequest, CalculatedPrice } from "../lib/catalog-api";

export class PriceRequestError extends Error {
  public constructor(status: number) {
    super(`The pricing API returned HTTP ${status}`);
  }
}

export async function calculatePrice(
  request: CalculateRequest,
  apiBaseUrl = window.location.origin,
): Promise<CalculatedPrice> {
  const response = await fetch(new URL("/api/calculate", apiBaseUrl), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new PriceRequestError(response.status);
  }
  return (await response.json()) as CalculatedPrice;
}

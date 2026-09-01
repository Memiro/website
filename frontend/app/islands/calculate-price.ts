import { type CalculateRequest, type CalculatedPrice, isCalculatedPrice } from "../lib/catalog-api.ts";
import { requestJson } from "../lib/http.ts";

export async function calculatePrice(
  request: CalculateRequest,
  apiBaseUrl = window.location.origin,
): Promise<CalculatedPrice> {
  return requestJson({ url: new URL("/api/calculate", apiBaseUrl), post: request, isBody: isCalculatedPrice });
}

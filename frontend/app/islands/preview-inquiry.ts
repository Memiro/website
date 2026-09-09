import { requestJson } from "../lib/http.ts";
import { isInquiryPreview } from "../lib/inquiry-state.ts";
import type { InquiryPreview, PreviewInquiryRequest } from "../lib/inquiry-state.ts";

export async function previewInquiry(
  request: PreviewInquiryRequest,
  apiBaseUrl = window.location.origin,
): Promise<InquiryPreview> {
  return requestJson({ url: new URL("/api/inquiries/preview", apiBaseUrl), post: request, isBody: isInquiryPreview });
}

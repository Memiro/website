import type { APIRoute } from "astro";

import { internalCatalogApi } from "../lib/catalog-api.ts";
import { llmsText } from "../lib/llms.ts";

export const GET: APIRoute = async ({ site }) => {
  let text: string | null;
  try {
    text = await llmsText(site, internalCatalogApi());
  } catch {
    return new Response("llms.txt unavailable", { status: 503 });
  }
  return text === null
    ? new Response("llms.txt unavailable", { status: 503 })
    : new Response(text, { headers: { "content-type": "text/plain; charset=utf-8" } });
};

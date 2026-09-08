import type { APIRoute } from "astro";

import { internalCatalogApi } from "../lib/catalog-api.ts";
import { sitemapPaths, sitemapXml } from "../lib/sitemap.ts";

// A catalogue that refuses is answered with 503, never with a valid document
// missing every product: a crawler reads the second as "the catalogue is gone".
export const GET: APIRoute = async ({ site }) => {
  let xml: string | null;
  try {
    xml = sitemapXml(site, await sitemapPaths(internalCatalogApi()));
  } catch {
    return new Response("sitemap unavailable", { status: 503 });
  }
  return xml === null
    ? new Response("sitemap unavailable", { status: 503 })
    : new Response(xml, { headers: { "content-type": "application/xml; charset=utf-8" } });
};

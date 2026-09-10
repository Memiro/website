import type { APIRoute } from "astro";

import { internalCatalogApi } from "../lib/catalog-api.ts";
import { SITE_NAME } from "../lib/site.ts";
import { readSite } from "../lib/site-api.ts";
import { ymlContent, ymlText } from "../lib/yml.ts";

// A catalogue that refuses is answered with 503, never with a valid feed
// without a single offer: Yandex reads the second as "nothing for sale".
export const GET: APIRoute = async ({ site }) => {
  let xml: string | null;
  try {
    const [content, siteData] = await Promise.all([ymlContent(internalCatalogApi()), readSite()]);
    const company = siteData.seller.find((requisite) => requisite.kind === "name")?.value ?? SITE_NAME;
    xml = ymlText(site, { name: SITE_NAME, company, categories: content.categories }, content.offers, new Date());
  } catch {
    return new Response("feed unavailable", { status: 503 });
  }
  return xml === null
    ? new Response("feed unavailable", { status: 503 })
    : new Response(xml, { headers: { "content-type": "application/xml; charset=utf-8" } });
};

import { siteOrigin } from "./seo.ts";

/**
 * The narrowings of the catalog listing: they show the same category under
 * another address, so Yandex is told to fold them away (ADR-0003). `page` is
 * absent on purpose — it changes the content, and folding it would hide every
 * product past the first page.
 */
export const CLEAN_PARAMS = ["value", "price_min", "price_max", "sort"];

/**
 * Crawlers that answer questions with a language model. They are named to be
 * allowed, never to be refused: a workshop selling locally gains more from
 * appearing in an assistant's answer than it loses by being read.
 */
export const AI_CRAWLERS = [
  "GPTBot",
  "OAI-SearchBot",
  "ChatGPT-User",
  "ClaudeBot",
  "PerplexityBot",
  "Google-Extended",
  "YandexAdditional",
];

/** Addresses with nothing to index behind them. Photographs are not among them. */
const CLOSED = ["/cart/", "/api/", "/admin/", "/admin-static/"];

function block(agent: string): string[] {
  return [`User-agent: ${agent}`, ...CLOSED.map((path) => `Disallow: ${path}`)];
}

export function robotsText(site: URL | undefined): string {
  const origin = siteOrigin(site);
  const lines = [
    ...block("*"),
    "",
    ...block("Yandex"),
    `Clean-param: ${CLEAN_PARAMS.join("&")}`,
    "",
    ...AI_CRAWLERS.flatMap((crawler) => [`User-agent: ${crawler}`, "Allow: /", ""]),
  ];
  if (origin !== null) {
    lines.push(`Sitemap: ${origin}/sitemap.xml`);
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

import { defineMiddleware } from "astro:middleware";

import { legacyResponse } from "./lib/legacy-redirects.ts";
import { redirectTarget } from "./lib/navigation.ts";
import { slashRedirect } from "./lib/trailing-slash.ts";

// Whether the page carries the Metrika counter depends on the consent cookie
// (ADR-0006), so any caching layer has to tell those answers apart. Static
// assets are answered by nginx and never depend on it.
function varyOnCookie(response: Response): Response {
  const isHtml = response.headers.get("content-type")?.startsWith("text/html") === true;
  const alreadyVaries = /(^|,)\s*cookie\s*(,|$)/i.test(response.headers.get("Vary") ?? "");
  if (isHtml && !alreadyVaries) {
    response.headers.append("Vary", "Cookie");
  }
  return response;
}

// The old site's addresses are answered before routing: the new storefront has
// no page under them, and without this they would all become 404 on the day the
// domain switches (ADR-0015). They go first because their answer already ends
// with a slash; the slash rule after them would otherwise make a chain of two.
export const onRequest = defineMiddleware(async (context, next) => {
  const answer = legacyResponse(context.url.pathname);
  if (answer !== null) {
    return answer.status === 410
      ? new Response("Gone", { status: 410 })
      : context.redirect(redirectTarget(answer.location, context.url.search), answer.status);
  }
  const slashed = slashRedirect(context.url.pathname);
  if (slashed !== null) {
    return context.redirect(redirectTarget(slashed, context.url.search), 301);
  }
  return varyOnCookie(await next());
});

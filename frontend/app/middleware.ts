import { defineMiddleware } from "astro:middleware";

import { legacyResponse, redirectTarget } from "./lib/legacy-redirects.ts";

// The old site's addresses are answered before routing: the new storefront has
// no page under them, and without this they would all become 404 on the day the
// domain switches (ADR-0015).
export const onRequest = defineMiddleware((context, next) => {
  const answer = legacyResponse(context.url.pathname);
  if (answer === null) {
    return next();
  }
  return answer.status === 410
    ? new Response("Gone", { status: 410 })
    : context.redirect(redirectTarget(answer.location, context.url.search), answer.status);
});

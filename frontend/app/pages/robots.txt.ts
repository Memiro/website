import type { APIRoute } from "astro";

import { robotsText } from "../lib/robots.ts";

// An endpoint rather than a file in public/: the Sitemap line is absolute, and
// the origin belongs to the contour (PUBLIC_SITE_URL), not to the repository.
export const GET: APIRoute = ({ site }) =>
  new Response(robotsText(site), { headers: { "content-type": "text/plain; charset=utf-8" } });

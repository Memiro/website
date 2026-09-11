import node from "@astrojs/node";
import vue from "@astrojs/vue";
import { defineConfig } from "astro/config";

// Canonical and og:url are absolute or absent, so the public origin is part
// of the build. The contour overrides it through PUBLIC_SITE_URL.
const site = process.env.PUBLIC_SITE_URL ?? "https://memiro.ru";

export default defineConfig({
  adapter: node({ mode: "standalone" }),
  // The layout's styles are a small sheet on the critical path: fetched
  // separately they block the first paint and stand before the fonts in
  // the discovery chain, so the build puts them into the document.
  build: { inlineStylesheets: "always" },
  site,
  integrations: [vue()],
  output: "server",
  srcDir: "./app",
});

import node from "@astrojs/node";
import vue from "@astrojs/vue";
import { defineConfig } from "astro/config";

// Canonical and og:url are absolute or absent, so the public origin is part
// of the build. The contour overrides it through PUBLIC_SITE_URL.
const site = process.env.PUBLIC_SITE_URL ?? "https://memiro.ru";

export default defineConfig({
  adapter: node({ mode: "standalone" }),
  site,
  integrations: [vue()],
  output: "server",
  srcDir: "./app",
});

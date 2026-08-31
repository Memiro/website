import node from "@astrojs/node";
import vue from "@astrojs/vue";
import { defineConfig } from "astro/config";

export default defineConfig({
  adapter: node({ mode: "standalone" }),
  integrations: [vue()],
  output: "server",
});

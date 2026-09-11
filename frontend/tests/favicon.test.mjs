import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const layout = readFileSync(fileURLToPath(new URL("../app/layouts/BaseLayout.astro", import.meta.url)), "utf8");
const icon = readFileSync(fileURLToPath(new URL("../public/favicon.ico", import.meta.url)));

test("the icon crawlers ask for at the root is a real ico, not a renamed svg", () => {
  assert.deepEqual([...icon.subarray(0, 4)], [0, 0, 1, 0]);
});

test("the ico carries the three sizes a browser picks between", () => {
  assert.deepEqual([...icon.subarray(6, 7)], [16]);
  assert.equal(icon.readUInt16LE(4), 3);
});

test("every page offers both icons, the svg last so it wins where it is understood", () => {
  assert.ok(layout.indexOf('href="/favicon.ico"') < layout.indexOf('href="/favicon.svg"'));
});

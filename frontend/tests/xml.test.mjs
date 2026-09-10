import assert from "node:assert/strict";
import test from "node:test";

import { escapeXml, xmlLink } from "../app/lib/xml.ts";

test("the five characters XML minds are escaped", () => {
  assert.equal(escapeXml("<a href=\"x\">Неф & Co's</a>"), "&lt;a href=&quot;x&quot;&gt;Неф &amp; Co&apos;s&lt;/a&gt;");
});

test("control characters XML cannot spell are dropped, line breaks and tabs stay", () => {
  assert.equal(escapeXml("a\u0000b\u000Bc\td\ne"), "abc\td\ne");
});

test("a link is absolute on the site and escaped like any other text", () => {
  assert.equal(xmlLink(new URL("https://memiro.ru/ignored/"), "/media/a&b.jpg"), "https://memiro.ru/media/a&amp;b.jpg");
});

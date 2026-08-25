import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("admin UI reads Fluent controls through querySelector", async () => {
  const source = await readFile(new URL("../src/admin.js", import.meta.url), "utf8");

  assert.match(source, /function formControl\(form, name\)/);
  assert.match(source, /form\.querySelector\(`\[name="\$\{name\}"\]`\)/);
  assert.doesNotMatch(source, /form\.elements\./);
  assert.doesNotMatch(source, /currentTarget\.elements\./);
});

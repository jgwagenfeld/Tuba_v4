import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const viewerRoot = new URL("..", import.meta.url);

async function readViewerFile(...parts) {
  return readFile(new URL(path.posix.join(...parts), viewerRoot), "utf8");
}

// The dev server hands the stylesheet to the browser unparsed, so a malformed
// selector renders fine and every unit and e2e run passes. The production build
// minifies with lightningcss, which does parse it - and rejected a rule that
// deleting a selector out of a grouped list had fused with the rule below it:
//
//   [data-embed="true"]body[data-embed="true"] .app-shell { ... }
//
// That reached main and surfaced as five failing packaging tests in the Python
// suite, minutes away from the change. This runs the same parser in the
// viewer's own suite, in milliseconds, with no build side effects.
test("the stylesheet parses under the production minifier", async () => {
  const { transform } = require("lightningcss");
  const code = Buffer.from(await readViewerFile("src/styles.css"), "utf8");

  assert.doesNotThrow(
    () => transform({ filename: "styles.css", code, minify: true }),
    "src/styles.css must parse under lightningcss, or `vite build` fails"
  );
});

test("the stylesheet check actually rejects a fused selector", () => {
  // Guards the guard: a check that cannot fail is worse than no check, and the
  // bug this exists for looked like valid CSS to everything else in the loop.
  const { transform } = require("lightningcss");
  const fused = Buffer.from('a, [data-x="1"]body[data-x="1"] .b { color: red; }', "utf8");

  assert.throws(() => transform({ filename: "fused.css", code: fused, minify: true }));
});

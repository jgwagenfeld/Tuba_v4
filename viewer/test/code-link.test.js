import assert from "node:assert/strict";
import test from "node:test";

import {
  lineAtOffset,
  lineCount,
  lineStartOffset,
  replaceScriptLine,
  runLengthLiteral,
  scriptLine,
  withRunLength
} from "../src/codeLink.js";

const script = [
  'with model.pipe(section="DN100", material="Steel") as builder:',
  "    builder.run(4.0)",
  "    builder.run(L / 2)",
  ""
].join("\n");

test("a literal run length is editable and keeps its spelling", () => {
  assert.equal(runLengthLiteral("    builder.run(4.0)"), 4);
  assert.equal(runLengthLiteral("    builder.run(3.5)  # riser"), 3.5);
  assert.equal(withRunLength("    builder.run(4.0)", 4.5), "    builder.run(4.5)");
  assert.equal(withRunLength("    builder.run(3.5)  # riser", 5), "    builder.run(5.0)  # riser");
});

test("computed and keyword lengths are left to the editor", () => {
  assert.equal(runLengthLiteral("    builder.run(L / 2)"), null);
  assert.equal(runLengthLiteral("    builder.run(length=4.0)"), null);
  assert.equal(runLengthLiteral('    builder.bend(radius=0.3, angle=90.0, plane="XY")'), null);
});

test("line helpers address model.py by 1-based line number", () => {
  assert.equal(lineCount(script), 4);
  assert.equal(scriptLine(script, 2), "    builder.run(4.0)");
  assert.equal(replaceScriptLine(script, 2, "    builder.run(9.0)").split("\n")[1], "    builder.run(9.0)");
  assert.equal(replaceScriptLine(script, 99, "x"), script);
  assert.equal(lineAtOffset(script, lineStartOffset(script, 3)), 3);
});

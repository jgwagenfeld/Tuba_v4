import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

test("viewer identity ignores checkout line endings but detects source changes", () => {
  const root = mkdtempSync(join(tmpdir(), "tuba-viewer-identity-"));
  const config = new URL("../vite.config.js", import.meta.url).href;
  try {
    mkdirSync(join(root, "src"));
    const identity = (newline, value = 1) => {
      writeFileSync(join(root, "src/app.js"), `const value = ${value};${newline}`);
      writeFileSync(join(root, "src/style.css"), `body { color: red; }${newline}`);
      writeFileSync(join(root, "index.html"), `<html>${newline}</html>${newline}`);
      const result = spawnSync(process.execPath, ["--input-type=module", "--eval",
        `import config from ${JSON.stringify(config)}; process.stdout.write(config({ command: "build" }).define.__TUBA_VIEWER_BUILD__);`],
      { cwd: root, encoding: "utf8" });
      assert.equal(result.status, 0, result.stderr);
      return result.stdout;
    };
    const lf = identity("\n");
    assert.equal(identity("\r\n"), lf);
    assert.notEqual(identity("\n", 2), lf);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

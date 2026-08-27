import assert from "node:assert/strict";
import test from "node:test";

let importSequence = 0;

async function loadConfig(siteRoot) {
  const previous = process.env.TUBA_PAGES_SITE_ROOT;
  if (siteRoot === undefined) {
    delete process.env.TUBA_PAGES_SITE_ROOT;
  } else {
    process.env.TUBA_PAGES_SITE_ROOT = siteRoot;
  }

  try {
    const url = new URL("../playwright.config.js", import.meta.url);
    url.searchParams.set("test", String(importSequence++));
    return (await import(url.href)).default;
  } finally {
    if (previous === undefined) {
      delete process.env.TUBA_PAGES_SITE_ROOT;
    } else {
      process.env.TUBA_PAGES_SITE_ROOT = previous;
    }
  }
}

test("Playwright serves the built Pages artifact or an explicit prebuilt root", async () => {
  const defaultConfig = await loadConfig(undefined);
  assert.equal(
    defaultConfig.snapshotPathTemplate,
    "{testDir}/snapshots/{testFilePath}/{platform}/{arg}{ext}",
  );
  assert.match(
    defaultConfig.webServer.command,
    /scripts\/build_pages\.py pages --output \.build\/pages-check/,
  );
  assert.match(defaultConfig.webServer.command, /\.\.\/\.build\/pages-check/);

  const prebuiltConfig = await loadConfig("../_site");
  assert.match(prebuiltConfig.webServer.command, /\.\.\/_site/);
  assert.match(prebuiltConfig.webServer.command, /configFile: false/);
  assert.doesNotMatch(prebuiltConfig.webServer.command, /scripts\/build_pages\.py/);
});

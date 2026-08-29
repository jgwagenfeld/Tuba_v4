// Screenshot each published review for its gallery card.
//
// Driven by scripts/docs/generate_gallery_thumbnails.py, which builds the dev
// bundles into viewer/public/ first. Kept out of the Pages build on purpose:
// the images are committed, so releasing never needs a browser.
//
//   node viewer/scripts/gallery-thumbnails.mjs <out-dir> <id> [<id> ...]

import { mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { createServer } from "vite";

const viewerRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [outDir, ...bundleIds] = process.argv.slice(2);

if (!outDir || bundleIds.length === 0) {
  console.error("usage: node viewer/scripts/gallery-thumbnails.mjs <out-dir> <id> [<id> ...]");
  process.exit(2);
}

let server;
let browser;
try {
  await mkdir(outDir, { recursive: true });
  server = await createServer({
    root: viewerRoot,
    logLevel: "error",
    server: { host: "127.0.0.1", port: 15975, strictPort: false }
  });
  await server.listen();
  const baseUrl = server.resolvedUrls.local[0];

  browser = await chromium.launch({ headless: true });
  // 16:10 matches the card's aspect-ratio, so the shot is never re-cropped.
  const page = await browser.newPage({ viewport: { height: 800, width: 1280 } });
  page.setDefaultTimeout(30_000);

  for (const bundleId of bundleIds) {
    const url = new URL("/", baseUrl);
    url.searchParams.set("bundle", bundleId);
    // embed=1 drops the header, docks and status chrome, leaving the model.
    url.searchParams.set("embed", "1");
    await page.goto(url.toString(), { waitUntil: "load" });
    // Wait for real geometry, not just for the page: an empty canvas is a
    // thumbnail that silently says nothing.
    await page.waitForFunction(
      () => (window.__tubaViewer?.lastRender?.objectIds ?? []).length > 0
    );
    // ponytail: shot at the review's own default view, reaction arrows and all.
    // On a small model drawn beside engineering-scale arrows (the 3D tee) the
    // camera fits the arrows and the pipework ends up small. Framing it better
    // means hiding layers, and the layer list is not in embed mode - upgrade
    // path is a shot-specific view preset in the scene, not UI driving here.
    const target = join(outDir, `${bundleId}.png`);
    await page.locator("[data-canvas]").screenshot({ path: target });
    console.log(`wrote ${target}`);
  }
} finally {
  await browser?.close();
  await server?.close();
}

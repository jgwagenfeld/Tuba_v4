import { defineConfig } from "@playwright/test";

const prebuiltSiteRoot = process.env.TUBA_PAGES_SITE_ROOT?.trim();
const siteRoot = prebuiltSiteRoot || "../.build/pages-check";
const buildPages = prebuiltSiteRoot
  ? ""
  : "cd .. && uv run python scripts/build_pages.py pages --output .build/pages-check && cd viewer && ";
const serveStatic =
  `node --input-type=module --eval "import { createServer } from 'vite'; ` +
  `const server = await createServer({ root: process.argv[1], configFile: false, logLevel: 'error', ` +
  `server: { host: '127.0.0.1', port: 4173, strictPort: true } }); await server.listen();" ` +
  JSON.stringify(siteRoot);

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../.build/playwright-results",
  snapshotPathTemplate: "{testDir}/snapshots/{testFilePath}/{platform}/{arg}{ext}",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    colorScheme: "dark",
    deviceScaleFactor: 1,
    locale: "en-US",
    reducedMotion: "reduce",
    timezoneId: "UTC",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 900 }
  },
  webServer: {
    command: buildPages + serveStatic,
    url: "http://127.0.0.1:4173/viewer/",
    reuseExistingServer: false,
    timeout: 120_000
  }
});

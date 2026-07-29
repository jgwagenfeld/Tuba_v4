import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../.build/playwright-results",
  snapshotPathTemplate: "{testDir}/snapshots/{testFilePath}/{arg}{ext}",
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
    command:
      "cd .. && uv run python scripts/build_pages.py pages --output .build/pages-check && vite .build/pages-check --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173/viewer/",
    reuseExistingServer: false,
    timeout: 120_000
  }
});

import { chromium } from "@playwright/test";

const url = process.argv[2] ?? "http://localhost:5199/?bundle=autorouted-expansion-loop";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
page.on("console", (m) => { if (m.type() === "error") console.log("PAGE ERROR:", m.text()); });
page.on("pageerror", (e) => console.log("PAGE EXCEPTION:", e.message));
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);

const info = await page.evaluate(() => {
  const out = { hooks: Object.keys(window).filter((k) => /tuba|viewer|scene|state/i.test(k)) };
  const canvas = document.querySelector("canvas");
  out.canvas = canvas ? { w: canvas.width, h: canvas.height } : null;
  out.title = document.title;
  out.heading = document.querySelector("[data-scene-title]")?.textContent ?? null;
  return out;
});
console.log(JSON.stringify(info, null, 2));
await page.screenshot({ path: "d:/tmp/shot5199.png" });
await browser.close();

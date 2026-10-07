// Run with: node scripts/security-browser-check.mjs (uses the shared Playwright cache).
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
import { createHash } from "node:crypto";

const token = "c".repeat(43);
const requests = [];
const modules = new Map(await Promise.all(["localAuth.js", "reportView.js"].map(async name =>
  ["/" + name, await readFile(new URL("../src/" + name, import.meta.url))])));
const server = createServer((request, response) => {
  requests.push({ url: request.url, authorization: request.headers.authorization });
  if (modules.has(request.url)) {
    response.setHeader("Content-Type", "text/javascript");
    response.end(modules.get(request.url));
  } else if (request.url === "/") {
    response.setHeader("Content-Type", "text/html");
    response.end(`<button id="open">Open report</button><script type="module">
      import { initializeLocalAuth, previewProtocols } from '/localAuth.js';
      import { openReport } from '/reportView.js';
      initializeLocalAuth(); window.ready = true; window.previewProtocols = previewProtocols;
      document.querySelector('#open').onclick=()=>openReport('/report/index.html');</script>`);
  } else if (request.headers.authorization !== "Bearer " + token) {
    response.writeHead(403); response.end("denied");
  } else if (request.url === "/report/index.html") {
    response.setHeader("Content-Type", "text/html");
    response.end(`<html><head><style>p{margin:0;font:12px serif}</style>
      <meta http-equiv="refresh" content="0;url=/evil-refresh"></head><body>
      <script>window.parent.__pwned=true; fetch('/evil-fetch')</script>
      <img src="/evil-img" onerror="window.parent.__pwned=true">
      <iframe src="/evil-frame"></iframe>
      <a href="javascript:window.parent.__pwned=true">evil link</a>
      <a href="reports/table.csv">Download table CSV</a>
      ${Array.from({length:240}, (_, i) => `<p>Engineering row ${i}</p>`).join("")}
      <p>LAST_REPORT_LINE</p></body></html>`);
  } else if (request.url === "/report/reports/table.csv") {
    response.setHeader("Content-Type", "text/csv"); response.end("id,value\nN1,123\n");
  } else { response.writeHead(404); response.end(); }
});
server.on("upgrade", (request, socket) => {
  const protocols = request.headers["sec-websocket-protocol"]?.split(",").map(value => value.trim()) ?? [];
  if (!protocols.includes("tuba-preview") || !protocols.includes("tuba-auth." + token)) {
    socket.end("HTTP/1.1 403 Forbidden\r\n\r\n"); return;
  }
  const accept = createHash("sha1").update(request.headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\nSec-WebSocket-Protocol: tuba-preview\r\n\r\n`);
  socket.on("data", () => socket.end(Buffer.from([0x88, 0])));
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  await page.goto(origin + "/#tuba_token=" + token);
  await page.waitForFunction(() => window.ready);
  assert.equal(new URL(page.url()).hash, "");
  assert.equal(await page.evaluate(() => new Promise((resolve, reject) => {
    const url = 'ws' + location.origin.slice(4) + '/preview/ws';
    const socket = new WebSocket(url, window.previewProtocols(url));
    socket.onopen = () => { resolve(socket.protocol); socket.close(); };
    socket.onerror = () => reject(Error('Authenticated WebSocket did not open'));
  })), "tuba-preview");
  const popupPromise = page.waitForEvent("popup");
  await page.click("#open");
  const popup = await popupPromise;
  await popup.locator("iframe").waitFor();
  assert.equal(await popup.locator("iframe").getAttribute("sandbox"), "allow-downloads");
  const frame = popup.frameLocator("iframe");
  await frame.getByText("LAST_REPORT_LINE", { exact: true }).waitFor();
  assert.equal(await popup.evaluate(() => window.__pwned), undefined);
  assert.equal(await page.evaluate(() => window.__pwned), undefined);
  assert.equal(await popup.evaluate(() => window.opener), null);
  assert.ok(!requests.some(request => request.url.startsWith("/evil")));
  const downloadPromise = popup.waitForEvent("download");
  await frame.getByRole("link", { name: "Download table CSV" }).click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), "table.csv");
  assert.equal(await readFile(await download.path(), "utf-8"), "id,value\nN1,123\n");
  const output = new URL("../../.tmp/security-auth/", import.meta.url);
  await mkdir(output, { recursive: true });
  await writeFile(new URL("report-print.pdf", output), await popup.pdf());
  assert.ok(requests.filter(request => request.url.startsWith("/report/")).every(request => request.authorization === "Bearer " + token));
  console.log("Browser capability handoff, passive report, authenticated CSV download and PDF rendering passed.");
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}

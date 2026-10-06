// Fresh native Studio + source Vite qualification; both test hosts close in finally.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { createServer } from "vite";
import { chromium } from "playwright";

const [nativeUrl, output] = process.argv.slice(2);
const viewerRoot=resolve("viewer");
process.chdir(viewerRoot);
mkdirSync(output, {recursive:true});
const proxy=Object.fromEntries(["/api","/build","/review"].map(path=>[path,{target:nativeUrl}]));
proxy["/preview"]={target:nativeUrl,ws:true};
const vite=await createServer({root:viewerRoot,configFile:resolve(viewerRoot,"vite.config.js"),server:{host:"127.0.0.1",port:0,strictPort:false,proxy}});
let browser;
const summary={served:[],errors:[]};
try {
  await vite.listen();
  const base=vite.resolvedUrls.local[0];
  const url=new URL(base);
  url.searchParams.set("bundle","build");
  url.searchParams.set("preview_ws",new URL("/preview/ws",base).href.replace(/^http/,"ws"));
  summary.viewer_url=url.href;
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1600,height:1100}});
  page.on("pageerror",error=>summary.errors.push(error.message));
  page.on("response",response=>{if(/\/api\/mesh|\/build\/scene.json|\/src\/meshReview.js/.test(new URL(response.url()).pathname))summary.served.push({url:response.url(),status:response.status(),content_type:response.headers()["content-type"]});});
  const reply=await page.goto(url.href);
  summary.served.push({url:url.href,status:reply.status(),content_type:reply.headers()["content-type"]});
  const panel=page.locator("[data-mesh-review]");
  // The panel lives in the dock the status strip's mesh toggle opens.
  const openMeshDetail=async()=>{
    await page.waitForFunction(()=>document.querySelector("[data-analysis-summary]")?.hidden===false);
    if(await page.locator("[data-analysis-summary]").getAttribute("aria-expanded")!=="true")await page.locator("[data-analysis-summary]").click();
  };
  await openMeshDetail();
  await panel.waitFor({state:"visible"});
  await page.waitForFunction(()=>document.querySelector('[data-focus-key="mesh-converge"]')?.disabled===false);
  await panel.getByRole("button",{name:"Run convergence",exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[data-mesh-status]')?.dataset.meshState==="running");
  await page.screenshot({path:join(output,"01-running.png"),fullPage:true});
  await page.waitForFunction(()=>document.querySelector('[data-mesh-status]')?.dataset.meshState==="succeeded",null,{timeout:120000});
  summary.job=await (await page.request.get(new URL("/api/mesh",base).href)).json();
  assert.equal(summary.job.mode,"convergence");
  assert.equal(summary.job.current,true);
  assert.equal(summary.job.comparison.status,"completed");
  assert.equal(summary.job.comparison.all_available_changes_within_tolerance,false);
  await page.waitForFunction(()=>document.querySelector(".mesh-comparison")?.innerText.includes("TUYAU"));
  summary.panel=await panel.innerText();
  assert.match(summary.panel,/outside configured tolerance/);
  assert.match(summary.panel,/Unavailable/);
  await page.screenshot({path:join(output,"02-completed.png"),fullPage:true});
  await panel.evaluate(node=>{node.parentElement.scrollTop=node.parentElement.scrollHeight;});
  await page.screenshot({path:join(output,"02b-changes.png"),fullPage:true});
  await page.reload();
  await openMeshDetail();
  await page.waitForFunction(()=>document.querySelector(".mesh-comparison")?.innerText.includes("TUYAU"));
  assert.match(await panel.innerText(),/Completed Code_Aster mesh comparison/);
  await page.screenshot({path:join(output,"03-reopened.png"),fullPage:true});
  assert.deepEqual(summary.errors,[]);
  summary.passed=true;
} finally {
  writeFileSync(join(output,"summary.json"),JSON.stringify(summary,null,2));
  if(browser)await browser.close();
  await vite.close();
}

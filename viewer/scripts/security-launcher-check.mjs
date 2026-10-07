// Run after building: node scripts/security-launcher-check.mjs <built-viewer-directory>
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const root = fileURLToPath(new URL("../../", import.meta.url));
const assets = resolve(process.argv[2]);
const owned = fileURLToPath(new URL("../../.tmp/security-auth/launcher-check/", import.meta.url));
const child = spawn(process.env.TUBA_BUILD_PYTHON || "D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe", ["-c", `
import json, sys
from pathlib import Path
from tuba.studio_launcher import StudioLauncher, create_project
root = Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True)
project = root / "project"
if not project.exists(): create_project(project)
launcher = StudioLauncher(root / "state", port=0).start()
try:
    print(json.dumps({"url": launcher.launch_url, "project": str(project)}), flush=True)
    sys.stdin.readline()
finally:
    launcher.stop()
`, owned], { cwd: root, env: { ...process.env, PYTHONPATH: root, TUBA_VIEWER_ASSETS: assets }, stdio: "pipe" });
const lines = createInterface({ input: child.stdout });
// Capability handoff stays inside this private process pipe; never write it to evidence.
const launch = await new Promise((resolve, reject) => {
  lines.once("line", line => resolve(JSON.parse(line)));
  child.once("exit", code => reject(Error(`Launcher child exited before ready (${code}).`)));
});
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  const launcher = await context.newPage();
  await launcher.goto(launch.url);
  await launcher.locator("#project-path").fill(launch.project);
  const popupPromise = launcher.waitForEvent("popup");
  await launcher.locator("#open").click();
  const studio = await popupPromise;
  await studio.waitForFunction(() => !location.hash && sessionStorage.getItem("tuba:access"));
  assert.equal(await studio.evaluate(async () => {
    const response = await fetch("/api/script");
    return response.status;
  }), 200);
  await studio.locator("[data-projects-link]").waitFor();
  const projectsPromise = studio.waitForEvent("popup");
  await studio.locator("[data-projects-link]").click();
  const projects = await projectsPromise;
  await projects.locator("#project-path").waitFor();
  assert.equal(await projects.evaluate(async () => (await fetch("/api/projects", {
    headers: { Authorization: "Bearer " + sessionStorage.getItem("tuba:access") }
  })).status), 200);
  assert.equal(new URL(projects.url()).hash, "");
  console.log("Actual launcher→Studio→Projects capability handoff passed (geometry-only fixture, no solve).");
} finally {
  await browser.close();
  lines.close();
  child.stdin.end("\n");
  await new Promise(resolve => child.once("exit", resolve));
}

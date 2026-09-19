import { spawn, spawnSync } from "node:child_process";
import { createReadStream, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { defineConfig } from "vite";

const PUBLIC_DIR = "public";
const LICENSE_FILES = ["font-notices.txt", "OFL-1.1.txt"];

// A bundle is any public/ subdirectory that carries a scene.json. Listing them
// here means the viewer's example dropdown reflects what is actually on disk -
// drop in a new example folder and it appears, no code change.
function listBundles() {
  return readdirSync(PUBLIC_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && existsSync(join(PUBLIC_DIR, entry.name, "scene.json")))
    .map((entry) => entry.name)
    .sort();
}

const REPO_ROOT = join(process.cwd(), "..");
// Shot on demand into .build/, never committed: the Pages build photographs
// the bundles it produces, and dev photographs the bundles already sitting in
// public/. Solving a review costs ~48s, which is why the published images used
// to be baked by hand - but dev is not solving anything, it is screenshotting
// what is already built, and that is about a second each.
const THUMBNAIL_DIR = join(REPO_ROOT, ".build", "gallery-thumbnails");
const SHOOTER = join(REPO_ROOT, "viewer", "scripts", "gallery-thumbnails.mjs");

// The published gallery describes each review by the engineering question it
// answers, with a summary, an evidence badge and a thumbnail. That catalog is
// built by scripts/official_gallery.py and, until now, only ever existed on the
// Pages build - so everyone working locally saw bare title chips and the copy
// nobody could see drifted unnoticed. The dev server asks the same module.
let cachedCatalog;
function officialCatalog() {
  if (cachedCatalog !== undefined) return cachedCatalog;
  const python = [
    join(REPO_ROOT, ".venv", "Scripts", "python.exe"),
    join(REPO_ROOT, ".venv", "bin", "python"),
    "python3",
    "python"
  ].find((candidate) => !candidate.includes("venv") || existsSync(candidate));
  const run = spawnSync(python, ["-m", "scripts.official_gallery"], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    timeout: 30_000
  });
  try {
    cachedCatalog = new Map(JSON.parse(run.stdout).map((entry) => [entry.id, entry]));
  } catch {
    // Dev must still start without a working Python environment; the gallery
    // falls back to the bare id list it used to show.
    cachedCatalog = null;
  }
  return cachedCatalog;
}

let shootInFlight = null;
// An id that fails to shoot is not retried on every request. The dev-only mesh
// review renders no objects, so its shot never succeeds, and a missing card
// image is a lesser problem than a server that never answers.
const thumbnailFailures = new Set();
function shootMissingThumbnails() {
  if (shootInFlight) return shootInFlight;
  const catalog = officialCatalog();
  const wanted = [...(catalog?.keys() ?? [])].filter(
    (id) => !existsSync(join(THUMBNAIL_DIR, `${id}.png`)) && !thumbnailFailures.has(id)
  );
  if (wanted.length === 0) return Promise.resolve();
  mkdirSync(THUMBNAIL_DIR, { recursive: true });
  shootInFlight = new Promise((resolve) => {
    // Spawn, never spawnSync: a browser launch must not hold the dev server's
    // event loop, or every other request stalls behind it.
    const child = spawn(process.execPath, [SHOOTER, THUMBNAIL_DIR, ...wanted], {
      cwd: join(REPO_ROOT, "viewer"),
      stdio: ["ignore", "ignore", "pipe"]
    });
    const timer = setTimeout(() => child.kill(), 180_000);
    let stderr = "";
    child.stderr?.on("data", (chunk) => { stderr += chunk; });
    child.on("exit", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        for (const id of wanted) {
          if (!existsSync(join(THUMBNAIL_DIR, `${id}.png`))) thumbnailFailures.add(id);
        }
        console.warn("[tuba] gallery thumbnails unavailable:", stderr.trim());
      }
      resolve();
    });
  }).finally(() => {
    shootInFlight = null;
  });
  return shootInFlight;
}

function bundleManifest() {
  // An id with no catalog entry (a scratch bundle, a fixture) stays a plain
  // string: normalizeCatalog turns that into a title-only card.
  const payload = () => {
    const catalog = officialCatalog();
    return JSON.stringify(listBundles().map((id) => catalog?.get(id) ?? id));
  };
  return {
    name: "tuba-bundle-manifest",
    transformIndexHtml(html) {
      return html.replace(/\r\n/g, "\n");
    },
    configureServer(server) {
      server.middlewares.use("/bundles.json", (_request, response) => {
        response.setHeader("content-type", "application/json");
        response.end(payload());
      });
      // Thumbnails are produced by the Pages build now, not committed, so this
      // serves whatever a local shoot has left behind and 404s otherwise - the
      // card drops its image rather than showing a broken one. To see the real
      // pictures locally, run the shooter:
      //   node viewer/scripts/gallery-thumbnails.mjs .build/gallery-thumbnails <id>
      server.middlewares.use("/gallery", (request, response, next) => {
        const name = (request.url ?? "").split("?")[0].replace(/^\//, "");
        if (!/^[\w.-]+\.png$/.test(name)) return next();
        const file = join(THUMBNAIL_DIR, name);
        if (!existsSync(file)) {
          // Shoot in the background - one batch for the whole gallery rather
          // than a browser launch per card - and let this request fall through
          // so the card drops its image instead of every request waiting on a
          // browser launch.
          void shootMissingThumbnails();
          return next();
        }
        response.setHeader("content-type", "image/png");
        createReadStream(file).pipe(response);
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "bundles.json", source: "[]" });
      this.emitFile({
        type: "asset",
        fileName: "favicon.svg",
        source: readFileSync(join(PUBLIC_DIR, "favicon.svg"))
      });
      for (const fileName of LICENSE_FILES) {
        this.emitFile({
          type: "asset",
          fileName: `licenses/${fileName}`,
          source: readFileSync(join(PUBLIC_DIR, "licenses", fileName))
        });
      }
    }
  };
}

export default defineConfig(({ command }) => ({
  root: ".",
  base: "./",
  publicDir: command === "serve" ? PUBLIC_DIR : false,
  plugins: [bundleManifest()],
  build: {
    outDir: "../tuba/visualization/_viewer",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1024
  },
  server: {
    host: "0.0.0.0",
    port: 5173
  },
  preview: {
    host: "0.0.0.0",
    port: 4173
  }
}));

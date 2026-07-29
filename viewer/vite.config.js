import { existsSync, readFileSync, readdirSync } from "node:fs";
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

function bundleManifest() {
  const payload = () => JSON.stringify(listBundles());
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

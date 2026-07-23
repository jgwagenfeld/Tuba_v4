import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { defineConfig } from "vite";

const PUBLIC_DIR = "public";

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
    configureServer(server) {
      server.middlewares.use("/bundles.json", (_request, response) => {
        response.setHeader("content-type", "application/json");
        response.end(payload());
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "bundles.json", source: payload() });
    }
  };
}

export default defineConfig({
  root: ".",
  base: "./",
  plugins: [bundleManifest()],
  build: {
    outDir: "dist",
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
});

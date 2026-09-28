let worker;
let activeJob;

export function runBrowserModel(code, onProgress) {
  activeJob?.cancel();
  let rejectRun;
  let timer;
  let settled = false;
  const promise = new Promise((resolve, reject) => {
    const finish = (error, scene) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (worker) worker.onmessage = worker.onerror = null;
      // Stop really interrupts Python; failed runs also discard their state.
      if (error) { worker?.terminate(); worker = null; }
      activeJob = null;
      if (error) reject(error);
      else resolve(scene);
    };
    rejectRun = error => finish(error);
    try {
      worker ??= new Worker(new URL("./browserPython.worker.js", import.meta.url), { type: "module" });
      timer = setTimeout(() => finish(new Error("Geometry preview timed out. Shorten the script and try again.")), 120_000);
      worker.onerror = event => finish(new Error(event.message || "The browser Python worker could not start."));
      worker.onmessage = ({ data }) => {
        if (data.status) onProgress(data.status);
        else if (data.ok) finish(null, data.scene);
        else finish(Object.assign(new Error(data.error), { line: data.line }));
      };
      worker.postMessage({ code, runtimeUrl: new URL("./tuba-browser.zip", document.baseURI).href });
    } catch (error) { finish(error); }
  });
  const job = { promise, cancel: () => rejectRun(new DOMException("Preview stopped", "AbortError")) };
  if (!settled) activeJob = job;
  return job;
}

export function browserSceneBundle(scene) {
  // The browser only builds geometry. Never attach the published result fields
  // or review to a changed model, even if object IDs happen to match.
  return {
    scene, objects: scene.objects, objectMap: {}, overlays: scene.overlays,
    geometryAssets: scene.geometry_assets,
    geometryPayloads: scene.geometry_assets.map(asset => ({ ...asset, asset_id: asset.id })),
    review: null, reviewDiagnostics: [], legacyReview: false
  };
}

export function runBrowserModel(code, onProgress) {
  // A fresh worker per run prevents one script's imports/global mutations from
  // contaminating the next example. Termination also stops infinite loops.
  let worker;
  let rejectRun;
  let timer;
  const promise = new Promise((resolve, reject) => {
    rejectRun = reject;
    worker = new Worker(new URL("./browserPython.worker.js", import.meta.url), { type: "module" });
    timer = setTimeout(() => reject(new Error("Geometry preview timed out. Shorten the script and try again.")), 120_000);
    worker.onerror = event => reject(new Error(event.message || "The browser Python worker could not start."));
    worker.onmessage = ({ data }) => {
      if (data.status) onProgress(data.status);
      else if (data.ok) resolve(data.scene);
      else reject(Object.assign(new Error(data.error), { line: data.line }));
    };
    worker.postMessage({ code, runtimeUrl: new URL("./tuba-browser.zip", document.baseURI).href });
  }).finally(() => { clearTimeout(timer); worker?.terminate(); });
  return { promise, cancel: () => rejectRun(new DOMException("Preview stopped", "AbortError")) };
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

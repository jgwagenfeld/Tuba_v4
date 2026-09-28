// Python 3.12 matches Tuba's supported interpreter. NumPy here is preview-only:
// solver identities and engineering results always come from native Code_Aster.
const INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";

self.onmessage = async ({ data: { code, runtimeUrl } }) => {
  try {
    self.postMessage({ status: "Loading Python…" });
    const { loadPyodide } = await import(/* @vite-ignore */ `${INDEX_URL}pyodide.mjs`);
    const python = await loadPyodide({ indexURL: INDEX_URL, stdout() {}, stderr() {} });
    await python.loadPackage(["numpy", "jsonschema"]);
    const response = await fetch(runtimeUrl, { cache: "no-cache" });
    if (!response.ok) throw new Error(`Could not load Tuba (${response.status}). Reload and try again.`);
    python.unpackArchive(await response.arrayBuffer(), "zip", { extractDir: "/home/pyodide" });
    python.globals.set("_browser_code", code);
    self.postMessage({ status: "Building geometry…" });
    const result = python.runPython(`
import json, sys
from pathlib import Path
sys.path.insert(0, '/home/pyodide')
from tuba.project import run_model_script
from tuba.validation import validate_model
from tuba.visualization import SceneRequest, build_visualization_scene

def _browser_preview(code):
    path = Path('/home/pyodide/model.py')
    try:
        path.write_text(code, encoding='utf-8')
        model = run_model_script(path)['model']
        validate_model(model)
        scene = build_visualization_scene(SceneRequest(model, include_analysis_mesh=False))
        scene.validate()
        return json.dumps({'ok': True, 'scene': scene.to_dict()}, allow_nan=False)
    except BaseException as error:
        if isinstance(error, ModuleNotFoundError) and error.name in {'gmsh', 'meshio', 'ifcopenshell', 'h5py', 'pyvista'}:
            return json.dumps({'ok': False, 'error': f'This script needs {error.name}, a native package unavailable in the browser. Download model.py and run it in Tuba.'})
        line = getattr(error, 'lineno', None) if isinstance(error, SyntaxError) else None
        tb = error.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == str(path):
                line = tb.tb_lineno
            tb = tb.tb_next
        return json.dumps({'ok': False, 'error': f'{type(error).__name__}: {error}'[:2000], 'line': line})

_browser_preview(_browser_code)
`);
    self.postMessage(JSON.parse(result));
  } catch (error) {
    self.postMessage({ ok: false, error: error.message });
  }
};

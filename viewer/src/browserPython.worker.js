// Python 3.12 matches Tuba's supported interpreter. NumPy here is preview-only:
// solver identities and engineering results always come from native Code_Aster.
const INDEX_URL = new URL(/* @vite-ignore */ "../pyodide/", import.meta.url).href;
let python;

self.onmessage = async ({ data: { code, runtimeUrl } }) => {
  try {
    if (!python) {
      self.postMessage({ status: "Loading Python (first update)…" });
      const { loadPyodide } = await import(/* @vite-ignore */ `${INDEX_URL}pyodide.mjs`);
      python = await loadPyodide({ indexURL: INDEX_URL, stdout() {}, stderr() {} });
      await python.loadPackage(["numpy", "jsonschema"]);
      self.postMessage({ status: "Loading Tuba…" });
      const response = await fetch(runtimeUrl, { cache: "no-cache" });
      if (!response.ok) throw new Error(`Could not load Tuba (${response.status}). Reload and try again.`);
      python.unpackArchive(await response.arrayBuffer(), "zip", { extractDir: "/home/pyodide" });
    }
    self.postMessage({ status: "Building geometry…" });
    const globals = python.toPy({ _browser_code: code });
    try {
      const result = python.runPython(`
import json, sys, os
from pathlib import Path
from tempfile import TemporaryDirectory
# Keep the interpreter/packages warm, but reimport project code so model/module
# globals cannot leak into the next run (including when switching examples).
for name in list(sys.modules):
    if name == 'tuba' or name.startswith('tuba.') or name == 'examples' or name.startswith('examples.'):
        del sys.modules[name]
if '/home/pyodide' not in sys.path:
    sys.path.insert(0, '/home/pyodide')
from tuba.project import run_model_script
from tuba.validation import validate_model
from tuba.visualization import SceneRequest, build_visualization_scene

def _browser_preview(code):
    directory = TemporaryDirectory()
    path = Path(directory.name) / 'model.py'
    previous_cwd, previous_path = os.getcwd(), sys.path[:]
    try:
        os.chdir(directory.name)
        path.write_text(code, encoding='utf-8')
        model = run_model_script(path)['model']
        validate_model(model)
        scene = build_visualization_scene(SceneRequest(model, include_analysis_mesh=False))
        scene.validate()
        return json.dumps({'ok': True, 'scene': scene.to_dict()}, allow_nan=False)
    except BaseException as error:
        if isinstance(error, ModuleNotFoundError) and error.name in {'gmsh', 'meshio', 'ifcopenshell', 'h5py', 'pyvista'}:
            return json.dumps({'ok': False, 'error': f'This script needs {error.name}, a native package unavailable in the browser. Download model.py and run it in Tuba.'})
        # A command-line tool (argparse in main()) exits when the preview runs it
        # with no arguments. Said plainly rather than as "SystemExit: 2".
        if isinstance(error, SystemExit):
            return json.dumps({'ok': False, 'error': 'This script reads command-line arguments (a file to import, an output folder), which the browser preview cannot give it. Download model.py and run it in Tuba.'})
        line = getattr(error, 'lineno', None) if isinstance(error, SyntaxError) else None
        tb = error.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == str(path):
                line = tb.tb_lineno
            tb = tb.tb_next
        return json.dumps({'ok': False, 'error': f'{type(error).__name__}: {error}'[:2000], 'line': line})
    finally:
        os.chdir(previous_cwd)
        sys.path[:] = previous_path
        directory.cleanup()

_browser_preview(_browser_code)
`, { globals });
      self.postMessage(JSON.parse(result));
    } finally { globals.destroy(); }
  } catch (error) {
    self.postMessage({ ok: false, error: error.message });
  }
};

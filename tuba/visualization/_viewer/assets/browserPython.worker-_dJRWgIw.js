const e=`https://cdn.jsdelivr.net/pyodide/v0.27.7/full/`;let t;self.onmessage=async({data:{code:n,runtimeUrl:r}})=>{try{if(!t){self.postMessage({status:`Loading Python (first update)…`});let{loadPyodide:n}=await import(
/* @vite-ignore */
`${e}pyodide.mjs`);t=await n({indexURL:e,stdout(){},stderr(){}}),await t.loadPackage([`numpy`,`jsonschema`]),self.postMessage({status:`Loading Tuba…`});let i=await fetch(r,{cache:`no-cache`});if(!i.ok)throw Error(`Could not load Tuba (${i.status}). Reload and try again.`);t.unpackArchive(await i.arrayBuffer(),`zip`,{extractDir:`/home/pyodide`})}self.postMessage({status:`Building geometry…`});let i=t.toPy({_browser_code:n});try{let e=t.runPython(`
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
`,{globals:i});self.postMessage(JSON.parse(e))}finally{i.destroy()}}catch(e){self.postMessage({ok:!1,error:e.message})}};
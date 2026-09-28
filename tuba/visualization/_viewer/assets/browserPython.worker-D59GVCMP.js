const e=`https://cdn.jsdelivr.net/pyodide/v0.27.7/full/`;self.onmessage=async({data:{code:t,runtimeUrl:n}})=>{try{self.postMessage({status:`Loading Python…`});let{loadPyodide:r}=await import(`${e}pyodide.mjs`),i=await r({indexURL:e,stdout(){},stderr(){}});await i.loadPackage([`numpy`,`jsonschema`]);let a=await fetch(n,{cache:`no-cache`});if(!a.ok)throw Error(`Could not load Tuba (${a.status}). Reload and try again.`);i.unpackArchive(await a.arrayBuffer(),`zip`,{extractDir:`/home/pyodide`}),i.globals.set(`_browser_code`,t),self.postMessage({status:`Building geometry…`});let o=i.runPython(`
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
`);self.postMessage(JSON.parse(o))}catch(e){self.postMessage({ok:!1,error:e.message})}};
"""Model Context Protocol (MCP) server for generative piping modeling in Tuba v4.

Exposes tools for AI coding agents to create, inspect, route, and solve piping models.
Point ``init_session`` at a ``model.py`` in its own folder and open that folder in the
studio (``python -m tuba.cli_studio <folder>``): every change is saved to the script and
the studio reruns it, so the model builds up live in the viewer.
"""

from __future__ import annotations

import contextlib
import copy
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("tuba-piping")
except ImportError as _error:
    FastMCP = Any  # type: ignore[assignment,misc]
    _MCP_IMPORT_ERROR = _error  # the except target is unbound once this block ends

    class _DummyFastMCP:  # type: ignore[no-redef]
        def tool(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(fn: Any) -> Any:
                return fn
            return decorator

        def run(self) -> None:
            raise ImportError(
                "The Tuba MCP server needs the mcp package below version 2. Install the mcp "
                "extra (uv sync --all-extras, or pip install '.[mcp]'). "
                f"Importing it failed: {_MCP_IMPORT_ERROR}"
            ) from _MCP_IMPORT_ERROR

    mcp = _DummyFastMCP()

from tuba.builder import BuildStep, PipeRunRecipe
from tuba.model import TubaModel
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project import run_model_script
from tuba.project.script import AuthoredModelScript, ModelScriptChanged, is_generated, write_model_script

# Global session state
_ACTIVE_MODEL: Optional[TubaModel] = None
_ACTIVE_PATH: Optional[Path] = None
#: The text a session last wrote to, or read from, its model.py. A save refuses to
#: overwrite anything else: that is an edit made in the studio or an editor.
_SCRIPT_TEXT: Optional[str] = None

T = TypeVar("T")


def get_active_model() -> TubaModel:
    """Return the session's model."""
    if _ACTIVE_MODEL is None:
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    return _ACTIVE_MODEL


def _ensure_default_specs(model: TubaModel) -> None:
    """Populate default standard materials and pipe sections if empty."""
    if not model.materials:
        model.add_material(
            name="P265GH",
            E=2.1e11,
            nu=0.3,
            rho=7850.0,
            alpha=1.2e-5,
            allowable_stress={20.0: 170e6, 100.0: 160e6, 200.0: 140e6},
        )
    if not model.sections:
        model.add_pipe_section("DN100_SCH40", OD=0.1143, WT=0.00602)
        model.add_pipe_section("DN150_SCH40", OD=0.1683, WT=0.00711)
        model.add_pipe_section("DN200_SCH40", OD=0.2191, WT=0.00818)


def _edit(change: Callable[[TubaModel], T]) -> T:
    """Apply *change* to a copy of the session's model and write that copy to model.py.

    The session moves on only once the script is written: a change that raises, or a save
    refused because model.py changed, even by another edit that landed while *change* ran,
    leaves the session's model and its script as they were.
    A deleted model.py is not refused: it holds no edit to lose, and the session's model is
    then its only copy, so the save writes it again.
    """
    global _ACTIVE_MODEL, _SCRIPT_TEXT
    model = copy.deepcopy(get_active_model())
    last_text = _SCRIPT_TEXT if _ACTIVE_PATH.exists() else None
    result = change(model)
    try:
        text = write_model_script(_ACTIVE_PATH, model, last_text=last_text)
    except (ModelScriptChanged, AuthoredModelScript) as exc:
        raise RuntimeError(f"{exc} Call init_session with load_existing=True to continue from the edited file.") from exc
    _ACTIVE_MODEL, _SCRIPT_TEXT = model, text
    return result


@mcp.tool()
def init_session(
    project_name: str = "Generative Piping",
    standard: str = "ASME B31.3",
    file_path: str = "model.py",
    load_existing: bool = True,
) -> Dict[str, Any]:
    """Initialize or load a piping analysis model session.

    Parameters:
    - project_name: Human-readable name for the engineering project.
    - standard: Piping code standard (e.g. 'ASME B31.3', 'EN 13480').
    - file_path: The model.py the model is saved to after every change; a file with any
      other name is refused. Its folder is the project the studio opens
      (python -m tuba.cli_studio <folder>) to show each change as it happens. An existing
      model.py is only taken over if this server generated it.
    - load_existing: If True and the file exists, loads the existing model.
    """
    global _ACTIVE_MODEL, _ACTIVE_PATH, _SCRIPT_TEXT
    target = Path(file_path).resolve()
    if target.name != "model.py":
        raise ValueError(
            f"{target} is not a model.py: a session saves to the model.py in its project folder, "
            "which the studio opens."
        )
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    if existing is not None and not is_generated(existing):
        raise ValueError(
            f"{target} was not generated by this server and may hold hand-written code. "
            "Edit it directly, or pass the path of a new model.py."
        )

    if load_existing and existing is not None:
        with contextlib.redirect_stdout(sys.stderr):  # stdout carries the MCP protocol
            model = run_model_script(target)["model"]
        # Only once the script ran: one that raises leaves the session and its edit guard as they were.
        _ACTIVE_MODEL = model
        _ACTIVE_PATH = target
        _SCRIPT_TEXT = existing
        return {
            "status": "loaded",
            "project_name": model.project_name,
            "standard": model.standard,
            "nodes_count": len(model.nodes),
            "elements_count": len(model.elements),
            "file_path": str(target),
        }

    model = TubaModel(project_name=project_name, standard=standard)
    _ensure_default_specs(model)
    text = write_model_script(target, model, last_text=existing)
    _ACTIVE_MODEL, _ACTIVE_PATH, _SCRIPT_TEXT = model, target, text
    return {
        "status": "initialized",
        "project_name": project_name,
        "standard": standard,
        "file_path": str(target),
    }


@mcp.tool()
def add_material(
    name: str,
    E: float,
    nu: float,
    rho: float = 7850.0,
    alpha: float = 1.2e-5,
    allowable_stress: Optional[Dict[float, float]] = None,
) -> Dict[str, Any]:
    """Define a material specification.

    Parameters:
    - name: Unique identifier for the material (e.g. 'P265GH', 'A106-B').
    - E: Young's Modulus in Pascals (e.g. 2.1e11 for steel).
    - nu: Poisson's ratio (e.g. 0.3).
    - rho: Density in kg/m3 (default 7850.0).
    - alpha: Thermal expansion coefficient in 1/K (default 1.2e-5).
    - allowable_stress: Optional dict mapping temperature [°C] to allowable stress [Pa].
    """
    material = _edit(
        lambda model: model.add_material(
            name=name, E=E, nu=nu, rho=rho, alpha=alpha, allowable_stress=allowable_stress or {}
        )
    )
    return {"status": "success", "material": material.name, "E": material.E, "nu": material.nu}


@mcp.tool()
def add_pipe_section(
    name: str,
    OD: float,
    WT: float,
    corrosion_allowance: float = 0.0,
) -> Dict[str, Any]:
    """Define a standard pipe cross-section.

    Parameters:
    - name: Identifier (e.g. 'DN100_SCH40').
    - OD: Outer diameter in meters.
    - WT: Wall thickness in meters.
    - corrosion_allowance: Corrosion allowance in meters.
    """
    section = _edit(
        lambda model: model.add_pipe_section(name=name, OD=OD, WT=WT, corrosion_allowance=corrosion_allowance)
    )
    return {"status": "success", "section": section.name, "OD": section.OD, "WT": section.WT}


@mcp.tool()
def build_pipe_run(
    section: str,
    material: str,
    steps: List[Dict[str, Any]],
    route_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Procedurally construct a continuous pipe run by advancing a cursor.

    Steps is an array of operations:
    - {'op': 'start', 'point': [x, y, z], 'support': 'anchor' (optional)}
    - {'op': 'run', 'length': float} (extends pipe forward in current direction)
    - {'op': 'bend', 'radius': float, 'angle': float, 'plane': 'XY'|'XZ'|'YZ'}
    - {'op': 'bend_to', 'point': [x, y, z], 'radius': float}
    - {'op': 'end', 'point': [x, y, z] (optional), 'support': 'guide' (optional)}

    Example:
    steps = [
        {"op": "start", "point": [0, 0, 0], "support": "anchor"},
        {"op": "run", "length": 5.0},
        {"op": "bend", "radius": 0.1524, "angle": 90.0, "plane": "XY"},
        {"op": "run", "length": 3.0},
        {"op": "end", "support": "anchor"}
    ]
    """
    parsed_steps = []
    for step in steps:
        op = step["op"]
        if "params" in step and isinstance(step["params"], dict):
            params = dict(step["params"])
        else:
            params = {k: v for k, v in step.items() if k != "op"}
        parsed_steps.append(BuildStep(op=op, params=params))

    recipe = PipeRunRecipe(
        section=section,
        material=material,
        steps=parsed_steps,
        route_id=route_id,
    )
    built = _edit(recipe.build)
    model = get_active_model()

    return {
        "status": "success",
        "created_node_ids": built.node_ids,
        "created_element_ids": built.element_ids,
        "total_nodes": len(model.nodes),
        "total_elements": len(model.elements),
    }


@mcp.tool()
def configure_load_case(
    name: str,
    internal_pressure_mpa: float,
    temperature_celsius: float,
    gravity: bool = True,
    ref_temperature_celsius: float = 20.0,
    nodal_forces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Define or update an operational piping load case.

    Parameters:
    - name: Name of the load case (e.g. 'Operating_Hot', 'Hydrotest').
    - internal_pressure_mpa: Internal design or operating pressure in MPa (converted to Pa).
    - temperature_celsius: Operating design temperature in degrees Celsius.
    - gravity: Whether self-weight gravity is active.
    - ref_temperature_celsius: Reference ambient installation temperature in °C.
    - nodal_forces: Optional list of concentrated loads:
      [{'node': 'N0', 'force': [Fx, Fy, Fz], 'moment': [Mx, My, Mz]}]
    """
    def configure(model: TubaModel) -> None:
        case = model.define_load_case(
            name=name,
            gravity=gravity,
            pressure=internal_pressure_mpa * 1e6,
            temperature=temperature_celsius,
            ref_temperature=ref_temperature_celsius,
        )
        for force in nodal_forces or []:
            case.add_nodal_force(
                node=force["node"],
                force=force.get("force", [0.0, 0.0, 0.0]),
                moment=force.get("moment", [0.0, 0.0, 0.0]),
            )

    _edit(configure)
    return {
        "status": "success",
        "load_case": name,
        "internal_pressure_mpa": internal_pressure_mpa,
        "temperature_celsius": temperature_celsius,
        "gravity": gravity,
    }


@mcp.tool()
def apply_model_patch(
    operations: List[Dict[str, Any]],
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply atomic, transactional mutations directly to the piping model.

    Operation types:
    - {'op': 'add_node', 'local_id': 'n_custom', 'coords': [x, y, z]}
    - {'op': 'add_element', 'local_id': 'e_custom', 'type': 'pipe_straight', 'n1': 'n1', 'n2': 'n2', 'section': 'DN100', 'material': 'P265GH'}
    - {'op': 'add_support', 'node': 'n1', 'type': 'anchor'|'guide'|'rest'|'spring'}
    - {'op': 'create_group', 'name': 'Loop1', 'elements': ['pipe_str_0', 'pipe_str_1']}
    """
    patch = ModelPatch.from_dict({
        "operations": operations,
        "provenance": provenance or {"source": "mcp_coding_agent"},
    })
    result = _edit(lambda model: ModelTransaction(model).apply(patch, validate=True))

    return {
        "status": "success",
        "created_node_ids": result.node_ids,
        "created_element_ids": result.element_ids,
        "support_count": result.support_count,
    }


@mcp.tool()
def inspect_model() -> Dict[str, Any]:
    """Inspect current model topology, elements, supports, and operational load cases."""
    model = get_active_model()
    return {
        "project_name": model.project_name,
        "standard": model.standard,
        "nodes": {nid: node.coords.tolist() for nid, node in model.nodes.items()},
        "elements": [
            {
                "id": e.id,
                "type": e.type,
                "n1": e.n1,
                "n2": e.n2,
                "section": e.section,
                "material": e.material,
                **({"bend_radius": e.bend_radius, "bend_angle": e.bend_angle} if e.type == "pipe_bend" else {}),
            }
            for e in model.elements
        ],
        "supports": [
            {"node": s.node, "type": s.type, **({"direction": s.direction} if s.direction else {})}
            for s in model.supports
        ],
        "load_cases": {
            name: {
                "internal_pressure_mpa": lc.internal_pressure / 1e6,
                "temperature_celsius": lc.temperature,
                "gravity": lc.gravity,
                "nodal_forces_count": len(lc.nodal_forces),
            }
            for name, lc in model.load_cases.items()
        },
        "materials": list(model.materials.keys()),
        "sections": list(model.sections.keys()),
    }


@mcp.tool()
def solve_model(
    load_case: Optional[str] = None,
    max_element_size: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate the active piping model with the Code_Aster FEA solver.

    Adheres strictly to the Tuba v4 contract: runs actual Code_Aster FEA and returns
    solver metrics and results artifacts. If Code_Aster is not available in the environment,
    fails loudly with actionable diagnostics.
    """
    model = get_active_model()
    if not model.elements:
        return {"status": "error", "message": "Cannot solve empty model: no elements defined."}
    if not model.supports:
        return {"status": "error", "message": "Cannot solve model without boundary conditions (supports)."}

    try:
        run = model.solve(load_case=load_case, max_element_size=max_element_size)
        return {
            "status": "success",
            "run_id": getattr(run, "run_id", "run_completed"),
            "load_case": load_case or (list(model.load_cases.keys())[0] if model.load_cases else "default"),
            "results_available": True,
            "message": "Code_Aster evaluation completed successfully.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "diagnostics": [
                "Code_Aster execution failed or Code_Aster runtime environment is not reachable.",
                "Ensure Code_Aster is installed and configured in system path/container.",
            ],
        }


@mcp.tool()
def export_python_script(output_path: str = "generated_pipeline.py") -> Dict[str, Any]:
    """Write a Python script reproducing the current model, plus its Code_Aster input files.

    An existing file at output_path is only overwritten if this server generated it.

    Beside the script, each load case gets code_aster/<load case>/ holding study.comm (the
    simulation commands), study.mail (the analysis mesh) and study.export (the run file),
    with study_manifest.json and study_tuba_fem.json tracing Code_Aster names back to the
    model. These are the inputs a solve would run, not results: nothing is solved here.
    """
    model = get_active_model()
    target = Path(output_path)
    if target.resolve() == _ACTIVE_PATH:
        _edit(lambda _model: None)  # the session's own script keeps its guard against outside edits
    else:
        current = target.read_text(encoding="utf-8") if target.exists() else None
        write_model_script(target, model, last_text=current)  # never overwrites an authored script
    from tuba.solver.aster import CodeAsterSolver

    decks: Dict[str, Any] = {}
    for lc_name in model.load_cases:
        # ponytail: punctuation becomes "_", so names differing only in punctuation share a folder
        folder = target.parent / "code_aster" / "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in lc_name)
        try:
            decks[lc_name] = CodeAsterSolver().export_analysis_study(model, lc_name, folder).input_files
        except Exception as exc:  # the script is already written; report why this deck is missing
            decks[lc_name] = {"error": f"{type(exc).__name__}: {exc}"}
    return {"status": "success", "file": str(target), "code_aster_inputs": decks}


def create_mcp_server() -> FastMCP:
    """Return configured FastMCP server instance."""
    return mcp


if __name__ == "__main__":
    mcp.run()

"""Model Context Protocol (MCP) server for generative piping modeling in Tuba v4.

Exposes tools for AI coding agents to create, inspect, route, and solve piping models.
Point ``init_session`` at a ``model.py`` in its own folder and open that folder in the
studio (``python -m tuba.cli_studio <folder>``): every change is saved to the script and
the studio reruns it, so the model builds up live in the viewer. The session also keeps
a managed ``study.py`` beside ``model.py`` so the studio's ``.comm`` tabs and Solve are
available without hand-wiring a study.
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

from tuba.assemblies import RackRow, check_unit_style
from tuba.builder import BuildStep, PipeRunRecipe
from tuba.model import TubaModel
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project import run_model_script
from tuba.project.script import (
    AuthoredModelScript,
    ModelScriptChanged,
    is_generated,
    project_on_path,
    prologue_namespace,
    prologue_nodes,
    write_model_script,
)
from tuba.project.study import ensure_study_file

# Global session state
_ACTIVE_MODEL: Optional[TubaModel] = None
_ACTIVE_PATH: Optional[Path] = None
#: The text a session last wrote to, or read from, its model.py. A save refuses to
#: overwrite anything else: that is an edit made in the studio or an editor.
_SCRIPT_TEXT: Optional[str] = None

#: Studio defaults, mirroring tuba.cli_studio's --host/--port: where the viewer URL
#: reported by init_session points. A studio on a custom host/port serves the same paths.
_STUDIO_HOST = "127.0.0.1"
_STUDIO_PORT = 8765

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


def _ensure_study_file(model: TubaModel) -> Dict[str, Any]:
    """Create the managed study.py beside the session's model.py, or sync its LOAD_CASES."""
    if _ACTIVE_PATH is None:  # pragma: no cover - callers hold a session
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    return ensure_study_file(
        _ACTIVE_PATH.parent / "study.py",
        project_name=model.project_name,
        cases=list(model.load_cases),
    )


def _studio_hint() -> Dict[str, str]:
    """How to see this session: the studio command and viewer URL for its project folder."""
    folder = str(_ACTIVE_PATH.parent) if _ACTIVE_PATH is not None else "."
    base = f"http://{_STUDIO_HOST}:{_STUDIO_PORT}/"
    return {
        "cmd": f"python -m tuba.cli_studio {folder}",
        "viewer_url": f"{base}?bundle=build&preview_ws=ws://{_STUDIO_HOST}:{_STUDIO_PORT}/preview/ws",
        "note": (
            "Start the studio on the project folder, then open the viewer URL in Build mode: "
            "model.py and each .comm tab sit side by side, and Solve runs Code_Aster."
        ),
    }


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

    Every session also ensures a study.py beside model.py: scaffolded (and LOAD_CASES-synced)
    while it carries the server's marker, left alone when user-owned. The response reports
    the study state and how to open the studio on this project.
    """
    global _ACTIVE_MODEL, _ACTIVE_PATH, _SCRIPT_TEXT
    target = Path(file_path).resolve()
    if target.name != "model.py":
        raise ValueError(
            f"{target} is not a model.py: a session saves to the model.py in its project folder, "
            "which the studio opens."
        )
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    if existing is not None and not load_existing and not is_generated(existing):
        raise ValueError(
            f"{target} was not generated by this server and holds hand-written code. "
            "Set load_existing=True to inspect or solve it, or pass the path of a new model.py."
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
            "authored": not is_generated(existing),
            "project_name": model.project_name,
            "standard": model.standard,
            "nodes_count": len(model.nodes),
            "elements_count": len(model.elements),
            "file_path": str(target),
            "study": _ensure_study_file(model),
            "studio": _studio_hint(),
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
        "study": _ensure_study_file(model),
        "studio": _studio_hint(),
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
def add_ibeam_section(
    name: str,
    profile_name: str,
) -> Dict[str, Any]:
    """Define a steel I-beam cross-section from the profile catalog.

    Parameters:
    - name: Identifier (e.g. 'RackColumnIPE').
    - profile_name: Catalog profile (e.g. 'IPE160', 'IPE140', 'IPE100').
    """
    section = _edit(lambda model: model.add_ibeam_section(name=name, profile_name=profile_name))
    return {"status": "success", "section": section.name, "profile": section.profile_name}


def _parse_shoe_specs(shoes: Optional[List[Dict[str, Any]]], bays: int) -> List[tuple]:
    """Shoe entries to ``(pipe node id, station)`` pairs, or a usage error."""
    shoe_specs: List[tuple] = []
    for entry in shoes or []:
        try:
            shoe_specs.append((entry["node"], int(entry["station"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Each shoe needs {{'node': <pipe node id>, 'station': <0..{bays}>}}, got {entry!r}.") from exc
    return shoe_specs


def _check_shoes_centred(model: TubaModel, row: Any, shoe_specs: List[tuple]) -> None:
    """Refuse pipe nodes that do not ride the row's hanger midpoints."""
    for pipe_node, station in shoe_specs:
        if pipe_node not in model.nodes:
            raise ValueError(f"Shoe pipe node {pipe_node!r} does not exist in the model.")
        here = model.nodes[pipe_node].coords
        want = row.station_point(station)
        if abs(float(here[0]) - want[0]) > 1e-3 or abs(float(here[1]) - want[1]) > 1e-3:
            raise ValueError(
                f"Pipe node {pipe_node!r} at [{here[0]:.4f}, {here[1]:.4f}] is not above "
                f"the rack midpoint at [{want[0]:.4f}, {want[1]:.4f}] (station {station}): "
                f"route the pipe along the rack centreline first."
            )


def _clash_warnings_for_new(
    model: TubaModel, *, element_ids: Any = (), node_ids: Any = ()
) -> List[Dict[str, Any]]:
    """Clash results touching freshly built records, for inline tool feedback.

    The agent acts on these immediately instead of discovering them later in
    the studio: a non-empty list means the last build overlapped something and
    must be corrected (move the row, use ``build_rack_corner`` for bends, or
    detail the joint by hand) before solving.
    """
    from tuba.clash import ClashEngine

    engine = ClashEngine()
    return [
        clash.to_dict()
        for clash in engine.check_new(model, new_element_ids=element_ids, new_node_ids=node_ids)
    ]


def _json_safe(value: Any) -> Any:
    """Best-effort JSON payload: literals pass through, anything else stringifies."""
    import json as _json

    try:
        _json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return repr(value)


@mcp.tool()
def build_rack(
    material: str,
    section: str,
    name_prefix: str = "rack",
    origin: Optional[List[float]] = None,
    direction: str = "X",
    bays: int = 1,
    bay_length: float = 2.0,
    width: float = 2.0,
    height: float = 3.0,
    level: float = 2.75,
    column_section: Optional[str] = None,
    longitudinal_section: Optional[str] = None,
    transverse_section: Optional[str] = None,
    shoes: Optional[List[Dict[str, Any]]] = None,
    friction_coefficient: float = 0.3,
    anchor_feet: bool = True,
    zone: Optional[str] = None,
) -> Dict[str, Any]:
    """Erect a row of steel pipe-rack bays, hanging pipe nodes from centred hangers.

    The row marches along *direction* ("X" or "Y") from *origin* (the feet of the
    first bay): ``bays`` bays of ``bay_length`` with ``width`` across. Adjacent bays
    share station nodes, so the row is one continuous frame; feet are anchored unless
    *anchor_feet* is False.

    The pipe runs MID-WIDTH (``origin + width / 2`` on the width axis): each station's
    cross beam is split into halves joined by a midpoint node, and each ``shoes`` entry
    (``{"node": <pipe node id>, "station": <0..bays>}``) hangs that node from the
    midpoint as a friction rest. A pipe routed anywhere else is refused with the
    centreline it must follow, instead of a silently floating shoe.

    Example: a 10 m run along X at y=1 needs ``origin=[-10, 0, -3]`` with ``width=2``
    (centreline y=1), ``bays=5``, and shoes for the six stations.

    A pipe bend needs an L-corner, not two overlapping rows: build the first
    row with this tool, then continue it with ``build_rack_corner``. The
    response carries ``clash_warnings`` for anything this row newly overlaps;
    a non-empty list must be corrected before solving (see ``check_clashes``).
    """
    base = tuple(origin) if origin is not None else (0.0, 0.0, 0.0)
    if len(base) != 3:
        raise ValueError(f"Rack origin must be [x, y, z], got {list(base)!r}.")
    shoe_specs = _parse_shoe_specs(shoes, bays)
    row = RackRow(
        name_prefix=name_prefix,
        origin=base,
        material=material,
        section=section,
        direction=direction,
        bays=bays,
        bay_length=bay_length,
        width=width,
        height=height,
        levels=(level,),
        shoe_level=level if shoe_specs else None,
        shoes=tuple(shoe_specs),
        anchor_feet=anchor_feet,
        friction_coefficient=friction_coefficient,
        zone=zone,
        column_section=column_section,
        longitudinal_section=longitudinal_section,
        transverse_section=transverse_section,
    )

    def build(model: TubaModel) -> Any:
        _check_shoes_centred(model, row, shoe_specs)
        return ModelTransaction(model).apply(row.to_patch(), validate=True)

    result = _edit(build)
    model = get_active_model()
    return {
        "status": "success",
        "bays": [f"{name_prefix}{bay}" for bay in range(bays)],
        "stations": [list(row.station_point(station)) for station in range(bays + 1)],
        "shoe_count": len(shoe_specs),
        "support_count": result.support_count,
        "total_nodes": len(model.nodes),
        "total_elements": len(model.elements),
        "clash_warnings": _clash_warnings_for_new(
            model,
            element_ids=result.element_ids.values(),
            node_ids=result.node_ids.values(),
        ),
    }


@mcp.tool()
def build_rack_corner(
    material: str,
    section: str,
    name_prefix: str = "rack_B",
    first_origin: Optional[List[float]] = None,
    first_direction: str = "X",
    first_bays: int = 1,
    first_bay_length: float = 2.0,
    first_width: float = 2.0,
    first_height: float = 3.0,
    first_level: float = 2.75,
    turn: str = "left",
    bays: int = 1,
    bay_length: Optional[float] = None,
    column_section: Optional[str] = None,
    longitudinal_section: Optional[str] = None,
    transverse_section: Optional[str] = None,
    shoes: Optional[List[Dict[str, Any]]] = None,
    friction_coefficient: float = 0.3,
    anchor_feet: bool = True,
    zone: Optional[str] = None,
) -> Dict[str, Any]:
    """Continue an already-built rack row around an L-corner without overlaps.

    Rows march toward +X/+Y only, so two corners are expressible: a first row
    along ``"X"`` turning ``"left"`` (this row marches +Y), or a first row
    along ``"Y"`` turning ``"right"`` (this row marches +X). The ``first_*``
    parameters describe the built first row (they are used for the corner
    geometry only; the row itself is never rebuilt): the corner post is looked
    up in the model, and a missing post refuses the build with the coordinates
    it expected, instead of stacking a silently overlapping row.

    The second row shares exactly the corner post, inherits the first row's
    widths, heights, levels, and sections, and starts open (no station-0
    columns, hangers, or feet). ``shoes`` entries (``{"node": ..., "station":
    <1..bays>}``) hang pipe nodes from the second row's own midpoints; the
    corner station itself carries no shoe.

    The response carries ``clash_warnings`` like :func:`build_rack`: empty
    means the corner is clean.
    """
    from tuba.assemblies import RackCorner, RackRow as _RackRow

    first_base = tuple(first_origin) if first_origin is not None else (0.0, 0.0, 0.0)
    if len(first_base) != 3:
        raise ValueError(f"First-row origin must be [x, y, z], got {list(first_base)!r}.")
    shoe_specs = _parse_shoe_specs(shoes, bays)
    first = _RackRow(
        name_prefix=f"{name_prefix}_first",
        origin=first_base,
        material=material,
        section=section,
        direction=first_direction,
        bays=first_bays,
        bay_length=first_bay_length,
        width=first_width,
        height=first_height,
        levels=(first_level,),
    )
    corner = RackCorner(
        name_prefix=name_prefix,
        first=first,
        turn=turn,
        bays=bays,
        bay_length=bay_length,
        shoes=tuple(shoe_specs),
        zone=zone,
        column_section=column_section,
        longitudinal_section=longitudinal_section,
        transverse_section=transverse_section,
        friction_coefficient=friction_coefficient,
        anchor_feet=anchor_feet,
    )
    second = corner.second_row()
    post = corner.corner_post()

    def build(model: TubaModel) -> Any:
        if model.find_node_by_point(post) is None:
            raise ValueError(
                f"No first-row corner post at [{post[0]:.4f}, {post[1]:.4f}, {post[2]:.4f}]: "
                "pass the built first row's origin/direction/bays so the corner lands on "
                "its end post instead of overlapping it."
            )
        _check_shoes_centred(model, second, shoe_specs)
        return ModelTransaction(model).apply(corner.second_patch(), validate=True)

    result = _edit(build)
    model = get_active_model()
    return {
        "status": "success",
        "corner_post": [float(value) for value in post],
        "direction": second.direction,
        "bays": [f"{name_prefix}{bay}" for bay in range(bays)],
        "stations": [list(second.station_point(station)) for station in range(bays + 1)],
        "shoe_count": len(shoe_specs),
        "support_count": result.support_count,
        "total_nodes": len(model.nodes),
        "total_elements": len(model.elements),
        "clash_warnings": _clash_warnings_for_new(
            model,
            element_ids=result.element_ids.values(),
            node_ids=result.node_ids.values(),
        ),
    }


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
    try:
        study = _ensure_study_file(get_active_model())
    except OSError as exc:
        raise RuntimeError(
            f"Load case {name!r} was saved to model.py, but study.py could not be synced ({exc}); "
            "add the case to study.py LOAD_CASES by hand so the studio shows its .comm tab."
        ) from exc
    return {
        "status": "success",
        "load_case": name,
        "internal_pressure_mpa": internal_pressure_mpa,
        "temperature_celsius": temperature_celsius,
        "gravity": gravity,
        "study": study,
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
    - {'op': 'add_support', 'node': 'n1', 'type': 'anchor'|'guide'|'rest'|'spring', 'attached_to': 'n2' (optional: the node the support acts against, left out for ground)}
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


def _project_dir() -> Optional[str]:
    """The session project folder, whose ``units/`` agent code may import."""
    return str(_ACTIVE_PATH.parent) if _ACTIVE_PATH is not None else None


def _unit_ref(name: str, func: str, where: str) -> str:
    return f"units.{name}:{func}" if where == "units" else func


@mcp.tool()
def save_unit(
    name: str,
    code: str,
    func: str = "build",
    where: str = "units",
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Save a reusable construction unit: a function taking ``(model, **params)``.

    *where* is ``"units"`` (importable ``units/<name>.py``, usable from any snippet as
    ``units.<name>:<func>``) or ``"model"`` (appended to model.py's own defs, usable as
    a bare ``<func>`` and replayed from there). Nothing is saved blindly: the code must
    compile, define a callable *func* taking ``(model, ...)`` with a docstring, pass a
    style gate (no prints, no bare excepts, ruff-clean), and — when *params* are given —
    dry-run through :func:`tuba.assemblies.assemble` against a copy of the session
    model, which must validate. A failed check saves nothing; see AGENTS.md,
    "Construction Units Style", for the standard being enforced.
    """
    global _SCRIPT_TEXT
    if where not in ("units", "model"):
        raise ValueError(f'Unit location must be "units" or "model", got {where!r}.')
    if not name.isidentifier():
        raise ValueError(f"Unit name must be a Python identifier, got {name!r}.")
    try:
        compile(code, f"<unit {name}>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Unit {name!r} does not parse: {exc}") from exc
    with project_on_path(_project_dir()):
        namespace: Dict[str, Any] = {}
        try:
            exec(compile(code, f"<unit {name}>", "exec"), namespace)
        except Exception as exc:
            raise ValueError(f"Unit {name!r} failed ({type(exc).__name__}: {exc}); nothing was saved.") from exc
    if not callable(namespace.get(func)):
        raise ValueError(f"Unit {name!r} defines no callable {func!r}; nothing was saved.")
    check_unit_style(name, code, func)
    ref = _unit_ref(name, func, where)
    if _ACTIVE_PATH is None:  # pragma: no cover - tools hold a session
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    written_unit: Path | None = None
    made_unit_dir = False
    if where == "units":
        # Written before the dry-run so the dry-run imports the real file; removed again on failure.
        target = _ACTIVE_PATH.parent / "units" / f"{name}.py"
        made_unit_dir = not target.parent.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code if code.endswith("\n") else code + "\n", encoding="utf-8", newline="")
        written_unit = target
    if params is not None:
        from tuba.assemblies import assemble
        from tuba.validation import validate_model

        trial = copy.deepcopy(get_active_model())
        try:
            with project_on_path(_project_dir()):
                assemble(trial, ref if where == "units" else func, _namespace=namespace, **params)
            validate_model(trial)
        except Exception as exc:
            if written_unit is not None:
                written_unit.unlink(missing_ok=True)
                if made_unit_dir:
                    import shutil as _shutil

                    _shutil.rmtree(written_unit.parent, ignore_errors=True)
            raise ValueError(f"Unit {ref!r} dry-run failed ({type(exc).__name__}: {exc}); nothing was saved.") from exc
    if where == "model":
        if func in prologue_namespace(_SCRIPT_TEXT):
            raise ValueError(f"model.py already defines {func!r}; edit or remove it by hand first.")
        current = _ACTIVE_PATH.read_text(encoding="utf-8") if _ACTIVE_PATH.exists() else None
        if current != _SCRIPT_TEXT:
            raise RuntimeError(f"{_ACTIVE_PATH} changed elsewhere; call init_session to continue from the edited file first.")
        # The def belongs to the prologue (leading imports/defs), where the writer carries
        # it over; appended after the state it would be rewritten away on the next save.
        _, insert_at, _, _ = prologue_nodes(current or "")
        before = (current or "").splitlines(keepends=True)
        head = "".join(before[:insert_at])
        rest = "".join(before[insert_at:]).lstrip("\n")
        if head and not head.endswith("\n"):
            head += "\n"
        updated = head + "\n" + code.strip("\n") + "\n\n" + rest
        _ACTIVE_PATH.write_text(updated, encoding="utf-8", newline="")
        try:
            with contextlib.redirect_stdout(sys.stderr):
                rebuilt = run_model_script(_ACTIVE_PATH)["model"]
            from tuba.project.script import same_model as _same

            if not _same(rebuilt, get_active_model()):
                raise ValueError("the appended defs changed the model")
        except Exception as exc:
            _ACTIVE_PATH.write_text(current or "", encoding="utf-8", newline="")
            raise ValueError(f"Appending the unit changed or broke the model ({exc}); model.py was left as it was.") from exc
        _SCRIPT_TEXT = updated
    return {"status": "saved", "ref": ref, "where": where, "dry_run": params is not None}


@mcp.tool()
def apply_unit(ref: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Apply a saved construction unit to the session model, transactionally.

    *ref* is a bare function name for a def in model.py itself, or
    ``"units.<module>:<func>"`` for an imported unit. The invocation is recorded, so
    the regenerated model.py replays it as the same call instead of flat records.
    A unit that raises, or params that are not plain literals, change nothing.
    The response carries ``clash_warnings`` for anything the unit newly overlaps
    (see ``check_clashes``); a non-empty list must be corrected before solving.
    """
    from tuba.assemblies import assemble

    with project_on_path(_project_dir()):
        namespace = prologue_namespace(_SCRIPT_TEXT)
        before = get_active_model()
        counts_before = (len(before.nodes), len(before.elements), len(before.supports))
        elements_before = {element.id for element in before.elements}
        nodes_before = set(before.nodes)
        calls_before = len(before.assembly_calls)
        result = _edit(lambda model: assemble(model, ref, _namespace=namespace, **(params or {})))
    after = get_active_model()
    counts_after = (len(after.nodes), len(after.elements), len(after.supports))
    return {
        "status": "success",
        "ref": ref,
        "added_nodes": counts_after[0] - counts_before[0],
        "added_elements": counts_after[1] - counts_before[1],
        "added_supports": counts_after[2] - counts_before[2],
        "invocations": len(after.assembly_calls) - calls_before,
        "result": str(result),
        "clash_warnings": _clash_warnings_for_new(
            after,
            element_ids={element.id for element in after.elements} - elements_before,
            node_ids=set(after.nodes) - nodes_before,
        ),
    }


@mcp.tool()
def run_model_code(code: str) -> Dict[str, Any]:
    """Run Python code against the session model; the script stays the basis.

    ``model.py`` remains the single source of truth: *code* runs against a copy of
    the session model (with ``model`` prebound, model.py's own defs callable, and
    ``assemble`` injected; import ``tuba.*`` freely, loops included), and only when
    it runs clean is the script regenerated from the result — singles stay unrolled,
    recorded unit invocations replay as calls, so studio line-linking keeps working.
    Nondestructive guarantees, same as every other tool:

    - failure (exception, or a rebound ``model`` that is not a TubaModel) changes
      neither the session nor ``model.py``;
    - a ``model.py`` saved elsewhere since (studio, editor) is never overwritten:
      the save is refused, telling you to ``init_session`` again first;
    - the regenerated script is proven to rebuild the model exactly before writing.

    The response carries ``clash_warnings`` for anything the code newly overlaps
    (see ``check_clashes``); a non-empty list must be corrected before solving.
    """
    from tuba.assemblies import assemble as _assemble

    before = get_active_model()
    counts_before = (len(before.nodes), len(before.elements), len(before.supports))
    elements_before = {element.id for element in before.elements}
    nodes_before = set(before.nodes)
    namespace: Dict[str, Any] = {"model": copy.deepcopy(before), "assemble": _assemble}
    namespace.update(prologue_namespace(_SCRIPT_TEXT))
    try:
        with project_on_path(_project_dir()):
            exec(compile(code, "<mcp run_model_code>", "exec"), namespace)
    except Exception as exc:
        raise RuntimeError(f"run_model_code failed ({type(exc).__name__}: {exc}); the session model and its script are unchanged.") from exc
    changed = namespace.get("model")
    if not isinstance(changed, TubaModel):
        raise RuntimeError(
            f"run_model_code must leave 'model' a TubaModel, got {type(changed).__name__}; "
            "the session model and its script are unchanged."
        )

    def adopt(_model: TubaModel) -> None:
        _model.replace_with(changed)

    _edit(adopt)
    after = get_active_model()
    counts_after = (len(after.nodes), len(after.elements), len(after.supports))
    return {
        "status": "success",
        "nodes": counts_after[0],
        "elements": counts_after[1],
        "supports": counts_after[2],
        "added_nodes": counts_after[0] - counts_before[0],
        "added_elements": counts_after[1] - counts_before[1],
        "added_supports": counts_after[2] - counts_before[2],
        "clash_warnings": _clash_warnings_for_new(
            after,
            element_ids={element.id for element in after.elements} - elements_before,
            node_ids=set(after.nodes) - nodes_before,
        ),
    }


@mcp.tool()
def inspect_model() -> Dict[str, Any]:
    """Inspect current model topology, elements, supports, and operational load cases.

    ``groups`` maps each clash's element ids back to the rack bay (or other
    group) that built them, and ``assembly_calls`` replays each recorded unit
    invocation with its parameters — together they tell which construction
    step to correct when ``check_clashes`` reports an overlap.
    """
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
        "groups": {
            name: {
                "nodes": list(group.get("nodes", [])),
                "elements": list(group.get("elements", [])),
                "metadata": _json_safe(dict(group.get("metadata", {}))),
            }
            for name, group in model.groups.items()
        },
        "assembly_calls": [
            {"ref": call.get("ref"), "params": _json_safe(dict(call.get("params", {})))}
            for call in model.assembly_calls
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
def check_clashes(
    clearance_m: float = 0.0,
    include_self: bool = True,
    include_duplicate_nodes: bool = True,
) -> Dict[str, Any]:
    """Check the session model for unintended clashes with join-aware reasoning.

    Reports element-vs-obstacle clashes plus element-vs-element overlaps that
    share no topological connection. Intended joins are excused: a shared node
    id (welded joint, tee, same-row bay), a support linking the two endpoints
    (pipe shoe on steel), or couplings sharing one port target. Near-duplicate
    nodes (different ids within 1 mm) are reported as merge-to-one-node fixes
    so the agent repairs the joint instead of the symptom.
    """
    from tuba.clash import ClashEngine

    model = get_active_model()
    engine = ClashEngine()
    obstacle: List[Dict[str, Any]] = []
    self_clashes: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    for clash in engine.check_all(model, clearance_m=clearance_m):
        kind = clash.metadata.get("check")
        if clash.right.kind == "obstacle":
            obstacle.append(clash.to_dict())
        elif kind == "duplicate_node":
            if include_duplicate_nodes:
                duplicates.append(clash.to_dict())
        elif include_self:
            self_clashes.append(clash.to_dict())
    return {
        "status": "success",
        "passed": not (obstacle or self_clashes or duplicates),
        "obstacle_clashes": obstacle,
        "self_clashes": self_clashes,
        "duplicate_nodes": duplicates,
        "counts": {
            "obstacle": len(obstacle),
            "self": len(self_clashes),
            "duplicate_nodes": len(duplicates),
        },
    }


@mcp.tool()
def solve_model(
    load_case: Optional[str] = None,
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
        run = model.solve(load_case=load_case)
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

"""Local stdio MCP inspection, verification and solving for Tuba project folders.

Use the same Tuba and filesystem environment as Studio and the project CLI.
``open_project_package`` extracts received ZIP/TGZ packages and binds their model;
``init_session(file_path="/path/to/project/model.py", load_existing=True)`` binds
an existing folder. Studio opens either with ``python -m tuba.cli_studio <path>``.
Authored Python is loaded for inspection and solving without being rewritten.
Generated-script mutations are saved to the shared folder and picked up by Studio.
The session preserves user-owned studies and scaffolds a managed ``study.py`` if absent.

``solve_model`` generates the required mesh and solves or reuses the study's evidence
in ``evidence/<operation>/``. Keep each complete evidence folder, including manifests
and execution attestation, when sharing saved results. A new solve requires Code_Aster;
existing verified artifacts can be imported without executing it again. Completed
scene.json bundles are review deliverables, not a replacement for editable source.
See docs/content/project-sharing.md for the general handoff guide.
"""

from __future__ import annotations

import contextlib
import copy
from functools import wraps
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    mcp = MCPServer("tuba-piping")
except ImportError as _error:
    _MCP_IMPORT_ERROR = _error  # the except target is unbound once this block ends

    class _MissingMCP:
        def tool(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(fn: Any) -> Any:
                return fn
            return decorator

        def run(self) -> None:
            raise ImportError(
                "The Tuba MCP server needs MCP SDK 2.2 or newer. Install the mcp extra with "
                "uv sync --extra mcp, or pip install '.[mcp]'. "
                f"Importing it failed: {_MCP_IMPORT_ERROR}"
            ) from _MCP_IMPORT_ERROR

    mcp = _MissingMCP()


from tuba.assemblies import RackRow, check_unit_style
from tuba.builder import BuildStep, PipeRunRecipe
from tuba.model import TubaModel
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project import load_project, run_model_script
from tuba.project.execution import project_namespace
from tuba.project.script import (
    AuthoredModelScript,
    ModelScriptChanged,
    is_generated,
    prologue_namespace,
    prologue_nodes,
    write_model_script,
)
from tuba.project.study import ensure_study_file
from tuba.project.source import SourceConflict, read_source, save_source, source_revision

# Global session state
_ACTIVE_MODEL: Optional[TubaModel] = None
_ACTIVE_PATH: Optional[Path] = None
#: The text a session last wrote to, or read from, its model.py. A save refuses to
#: overwrite anything else: that is an edit made in the studio or an editor.
_SCRIPT_TEXT: Optional[str] = None
# Reads may refresh the model, but do not acknowledge edits for subsequent writes.
_EDIT_FINGERPRINTS: dict[Path, str | None] = {}

T = TypeVar("T")


def _tool():
    """Register on the event loop, retaining callable Python helpers."""
    def register(fn):
        @wraps(fn)
        async def call(*args, **kwargs):
            # ponytail: one project session is serial; isolate server processes for parallel projects.
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get("status") == "error":
                    raise ToolError(json.dumps(result))
                return result
            except ToolError:
                raise
            except Exception as exc:
                # Local authored Python can fail in any way; agents need the concrete cause.
                raise ToolError(f"{type(exc).__name__}: {exc}") from exc
        mcp.tool()(call)
        return fn
    return register


def get_active_model() -> TubaModel:
    """Return the session's model."""
    if _ACTIVE_MODEL is None:
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    return _ACTIVE_MODEL


def _snapshot_fingerprints(namespace: dict[str, Any]) -> dict[Path, str | None]:
    """The Python/helper/CAD bytes that built this model, for mutation guards."""
    captured = {Path(path): digest.hex() for path, digest in namespace.get("__tuba_project_fingerprints__", ())}
    for path in namespace.get("__tuba_project_dependencies__", ()):
        captured.setdefault(Path(path), source_revision(path))
    for asset in namespace["model"].cad_assets.values():
        source = Path(asset.source_path)
        source = source.resolve() if source.is_absolute() else (_ACTIVE_PATH.parent / source).resolve()
        digest = str(asset.content_digest or "").removeprefix("sha256:")
        try:
            content = bytes.fromhex(digest).hex() if len(digest) == 64 else source_revision(source)
        except ValueError:
            content = source_revision(source)
        captured[source] = content
    return captured


def _require_unchanged_dependencies() -> None:
    for path, digest in _EDIT_FINGERPRINTS.items():
        # The writer separately guards model.py, including its existing deletion recovery.
        if path != _ACTIVE_PATH and source_revision(path) != digest:
            raise RuntimeError(
                f"{path} changed elsewhere; call init_session with load_existing=True "
                "to acknowledge the edited project before changing it."
            )


def _fresh_namespace() -> dict[str, Any]:
    """Rebuild the bound project for every read or solve, without accepting stale edits."""
    global _ACTIVE_MODEL
    get_active_model()  # provide the existing actionable no-session error
    with contextlib.redirect_stdout(sys.stderr):
        namespace = run_model_script(_ACTIVE_PATH)
    _ACTIVE_MODEL = namespace["model"]
    return namespace


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
    global _ACTIVE_MODEL, _SCRIPT_TEXT, _EDIT_FINGERPRINTS
    _require_unchanged_dependencies()
    model = copy.deepcopy(get_active_model())
    last_text = _SCRIPT_TEXT if _ACTIVE_PATH.exists() else None
    result = change(model)
    _require_unchanged_dependencies()
    try:
        text = write_model_script(_ACTIVE_PATH, model, last_text=last_text)
    except (ModelScriptChanged, AuthoredModelScript) as exc:
        raise RuntimeError(f"{exc} Call init_session with load_existing=True to continue from the edited file.") from exc
    _ACTIVE_MODEL, _SCRIPT_TEXT = model, text
    with contextlib.redirect_stdout(sys.stderr):
        namespace = run_model_script(_ACTIVE_PATH)
    _EDIT_FINGERPRINTS = _snapshot_fingerprints(namespace)
    return result


def _ensure_study_file(model: TubaModel) -> Dict[str, Any]:
    """Create the managed study.py beside the session's model.py, or sync its LOAD_CASES."""
    if _ACTIVE_PATH is None:  # pragma: no cover - callers hold a session
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    return ensure_study_file(
        _ACTIVE_PATH.parent / "study.py",
        project_name=model.project_name,
        cases=[*model.load_cases, *model.operations],
    )


def _studio_hint() -> Dict[str, Any]:
    """How to see this session: the studio command and viewer URL for its project folder."""
    from tuba.project.session import project_id, studio_session

    root = _ACTIVE_PATH.parent if _ACTIVE_PATH is not None else Path.cwd()
    command = ["python", "-m", "tuba.cli_studio", str(root)]
    running = studio_session(root)
    return {
        "cmd": subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command),
        "project_root": str(root),
        "project_id": project_id(root),
        "running": running is not None,
        "viewer_url": running["viewer_url"] if running else None,
        "base_url": running["base_url"] if running else None,
        "note": (
            "Open the running Studio URL." if running else
            "Start Studio with this command to inspect the bound project and solve with Code_Aster."
        ),
    }


@_tool()
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
    - file_path: Path to the project's model.py; any other filename is refused.
      For a received project, use open_project_package or extract its package and pass this file's local absolute
      path, retaining imported helpers and referenced CAD/data. Studio opens the
      containing folder with python -m tuba.cli_studio <folder>. Authored model.py
      can be inspected and solved but is never overwritten by generated edits.
    - load_existing: If True and the file exists, loads the existing model.

    Every session also ensures a study.py beside model.py: scaffolded (and LOAD_CASES-synced)
    while it carries the server's marker, left alone when user-owned. The response reports
    the study state and how to open the studio on this project. Studio and MCP share
    local project files, not a remote Studio connection; use the same filesystem environment.
    """
    global _ACTIVE_MODEL, _ACTIVE_PATH, _SCRIPT_TEXT, _EDIT_FINGERPRINTS
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
            namespace = run_model_script(target)
            model = namespace["model"]
        # Only once the script ran: one that raises leaves the session and its edit guard as they were.
        _ACTIVE_MODEL = model
        _ACTIVE_PATH = target
        _SCRIPT_TEXT = existing
        _EDIT_FINGERPRINTS = _snapshot_fingerprints(namespace)
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
    with contextlib.redirect_stdout(sys.stderr):
        _EDIT_FINGERPRINTS = _snapshot_fingerprints(run_model_script(target))
    return {
        "status": "initialized",
        "project_name": project_name,
        "standard": standard,
        "file_path": str(target),
        "study": _ensure_study_file(model),
        "studio": _studio_hint(),
    }


@_tool()
def export_project(output_path: str, include_results: bool = False) -> Dict[str, Any]:
    """Export saved project files: .tubaproject/.zip uses ZIP; .tgz/.tar.gz uses gzip/tar.

    Includes project-local Python helpers, CAD and data; excludes caches, runtime
    state, build output and previous archives. include_results requires complete,
    current verified Code_Aster evidence for every study operation. Never rewrites
    authored Python or overwrites an existing package. External dependencies must
    be installed by the recipient; reference project inputs with relative paths.
    """
    from tuba.project.package import export_project_package
    get_active_model()
    return export_project_package(_ACTIVE_PATH.parent, output_path, include_results=include_results)


@_tool()
def inspect_project_package(file_path: str) -> Dict[str, Any]:
    """Validate a ZIP/TGZ package and return its manifest without extracting or executing Python.

    Does not require or change the active project session. Checks every path,
    inventory entry and SHA-256; checksums do not establish the author's identity.
    """
    from tuba.project.package import inspect_project_package as inspect_package
    return inspect_package(file_path)


@_tool()
def open_project_package(file_path: str, destination: str) -> Dict[str, Any]:
    """Validate a ZIP/TGZ project package, extract to a NEW folder, and bind its model.py.

    Archive validation/extraction never executes code. Binding runs the project's
    Python as init_session does; open only projects you trust. destination must
    not exist. Keep the extracted folder to edit, solve and reopen in Studio.
    Packages with evidence reuse it only when current and verified. Source-only
    packages require Code_Aster to solve; meshes are generated by the workflow.
    """
    from tuba.project.package import unpack_project_package
    root = unpack_project_package(file_path, destination)
    return init_session(file_path=str(root / "model.py"), load_existing=True)


@_tool()
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


@_tool()
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


@_tool()
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


@_tool()
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


@_tool()
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


@_tool()
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


@_tool()
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


@_tool()
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


def _unit_ref(name: str, func: str, where: str) -> str:
    return f"units.{name}:{func}" if where == "units" else func


@_tool()
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
    _require_unchanged_dependencies()
    if where not in ("units", "model"):
        raise ValueError(f'Unit location must be "units" or "model", got {where!r}.')
    if not name.isidentifier():
        raise ValueError(f"Unit name must be a Python identifier, got {name!r}.")
    try:
        compile(code, f"<unit {name}>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Unit {name!r} does not parse: {exc}") from exc
    if _ACTIVE_PATH is None:  # pragma: no cover - tools hold a session
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    with project_namespace(_ACTIVE_PATH, run_name="tuba_unit_check") as namespace:
        try:
            exec(compile(code, f"<unit {name}>", "exec"), namespace)
        except Exception as exc:
            raise ValueError(f"Unit {name!r} failed ({type(exc).__name__}: {exc}); nothing was saved.") from exc
        if not callable(namespace.get(func)):
            raise ValueError(f"Unit {name!r} defines no callable {func!r}; nothing was saved.")
        check_unit_style(name, code, func)
        ref = _unit_ref(name, func, where)
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
            with project_namespace(_ACTIVE_PATH, run_name="tuba_unit_prologue_check") as prologue:
                if func in prologue_namespace(_SCRIPT_TEXT, prologue):
                    raise ValueError(f"model.py already defines {func!r}; edit or remove it by hand first.")
            source = read_source(_ACTIVE_PATH) if _ACTIVE_PATH.exists() else None
            current = source["code"] if source else None
            normalized_current = current.replace("\r\n", "\n").replace("\r", "\n") if current is not None else None
            if normalized_current != _SCRIPT_TEXT:
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
            try:
                revision = save_source(_ACTIVE_PATH, updated, source["source_revision"] if source else None)
            except SourceConflict as exc:
                raise RuntimeError(f"{exc} Call init_session to continue from the edited file first.") from exc
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    rebuilt = run_model_script(_ACTIVE_PATH)["model"]
                from tuba.project.script import same_model as _same

                if not _same(rebuilt, get_active_model()):
                    raise ValueError("the appended defs changed the model")
            except Exception as exc:
                try:
                    save_source(_ACTIVE_PATH, current or "", revision)
                except SourceConflict as conflict:
                    raise RuntimeError(
                        f"{conflict} The failed unit was not rolled back over the outside edit; call init_session."
                    ) from conflict
                raise ValueError(f"Appending the unit changed or broke the model ({exc}); model.py was left as it was.") from exc
            _SCRIPT_TEXT = updated.replace("\r\n", "\n").replace("\r", "\n")
        return {"status": "saved", "ref": ref, "where": where, "dry_run": params is not None}


@_tool()
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

    _require_unchanged_dependencies()
    with project_namespace(_ACTIVE_PATH, run_name="tuba_unit_apply") as namespace:
        prologue_namespace(_SCRIPT_TEXT, namespace)
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


@_tool()
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

    _require_unchanged_dependencies()
    before = get_active_model()
    counts_before = (len(before.nodes), len(before.elements), len(before.supports))
    elements_before = {element.id for element in before.elements}
    nodes_before = set(before.nodes)
    try:
        with project_namespace(_ACTIVE_PATH, run_name="tuba_model_code") as namespace:
            prologue_namespace(_SCRIPT_TEXT, namespace)
            namespace.update(model=copy.deepcopy(before), assemble=_assemble)
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


def _element_inspection(element) -> Dict[str, Any]:
    """One element in the builder's vocabulary: route and station range included."""
    view: Dict[str, Any] = {
        "id": element.id,
        "type": element.type,
        "n1": element.n1,
        "n2": element.n2,
        "section": element.section,
        "material": element.material,
    }
    if element.type == "pipe_bend":
        view["bend_radius"] = element.bend_radius
        view["bend_angle"] = element.bend_angle
    if element.route_id is not None:
        view["route_id"] = element.route_id
    if element.station_start is not None:
        view["station_start"] = element.station_start
    if element.station_end is not None:
        view["station_end"] = element.station_end
    return view


def _support_inspection(support) -> Dict[str, Any]:
    """One support named the way ``add_support`` names it."""
    view: Dict[str, Any] = {"id": support.id, "node": support.node, "type": support.type}
    if support.direction:
        view["direction"] = support.direction
    if support.attached_to is not None:
        view["attached_to"] = support.attached_to
        if support.attachment_mode != "rigid_offset":
            view["attachment_mode"] = support.attachment_mode
            view["blocked_dof"] = support.blocked_dof
    if support.friction_coefficient:
        view["friction_coefficient"] = support.friction_coefficient
    return view


def _route_inspection(model: TubaModel) -> Dict[str, Any]:
    """Route id -> its elements, section and material, and station span (min start, max end)."""
    routes: Dict[str, Any] = {}
    for element in model.elements:
        if element.route_id is None:
            continue
        route = routes.setdefault(
            element.route_id,
            {
                "elements": [],
                "section": element.section,
                "material": element.material,
                "station_start": None,
                "station_end": None,
            },
        )
        route["elements"].append(element.id)
        if element.station_start is not None:
            route["station_start"] = (
                element.station_start
                if route["station_start"] is None
                else min(route["station_start"], element.station_start)
            )
        if element.station_end is not None:
            route["station_end"] = (
                element.station_end
                if route["station_end"] is None
                else max(route["station_end"], element.station_end)
            )
    return routes


def _attachment_points_inspection(group) -> Dict[str, str]:
    """A group's named attachment points, with the ``node:`` ref prefix stripped."""
    points = group.get("metadata", {}).get("attachment_points", {})
    return {
        name: (ref.split(":", 1)[1] if isinstance(ref, str) and ":" in ref else ref)
        for name, ref in points.items()
    }


@_tool()
def inspect_model() -> Dict[str, Any]:
    """Inspect the model in the vocabulary it was authored in, so you can select by name.

    ``routes`` maps each route id to its elements, section, material and station
    span; elements carry ``route_id``, ``station_start`` and ``station_end``.
    Supports carry their ``id`` and, when attached, ``attached_to``. Each group
    carries its ``attachment_points`` (name -> node id, the ``node:`` ref
    stripped), so a rack's ``level_1_mid_left`` is a name, not a coordinate.

    ``groups`` maps each clash's element ids back to the rack bay (or other
    group) that built them, and ``assembly_calls`` replays each recorded unit
    invocation with its parameters — together they tell which construction
    step to correct when ``check_clashes`` reports an overlap.
    """
    model = _fresh_namespace()["model"]
    def mixed_records(records):
        return {
            key: {**record.to_dict(), **{
                field: getattr(record, field) for field in ("source_line", "source_call_line")
                if getattr(record, field, None) is not None
            }} for key, record in records.items()
        }
    return {
        "project_root": str(_ACTIVE_PATH.parent),
        "studio": _studio_hint(),
        "project_name": model.project_name,
        "standard": model.standard,
        "nodes": {nid: node.coords.tolist() for nid, node in model.nodes.items()},
        "elements": [_element_inspection(element) for element in model.elements],
        "supports": [_support_inspection(support) for support in model.supports],
        "routes": _route_inspection(model),
        "groups": {
            name: {
                "nodes": list(group.get("nodes", [])),
                "elements": list(group.get("elements", [])),
                "metadata": _json_safe(dict(group.get("metadata", {}))),
                **(
                    {"attachment_points": _attachment_points_inspection(group)}
                    if group.get("metadata", {}).get("attachment_points")
                    else {}
                ),
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
            for name, lc in {**model.load_cases, **model.operations}.items()
        },
        "materials": list(model.materials.keys()),
        "cad_assets": mixed_records(model.cad_assets),
        "imported_components": mixed_records(model.imported_components),
        "ports": mixed_records(model.ports),
        "analysis_regions": mixed_records(model.analysis_regions),
        "couplings": mixed_records(model.couplings),
        "mesh_groups": mixed_records(model.mesh_groups),
        "mesh_settings": _json_safe(model.mesh_settings),
        "mesh_refinements": _json_safe(model.mesh_refinements),
        "sections": list(model.sections.keys()),
    }


@_tool()
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

    model = _fresh_namespace()["model"]
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


@_tool()
def verify_model(clearance_m: float = 0.0) -> Dict[str, Any]:
    """Run the one cold-model verification gate before solving.

    Returns every blocking error (structural validation, hard clashes, error rules)
    and every advisory (clearance clashes, warning rules) in one report.
    ``solve_model`` refuses while a blocking error stands.
    """
    from tuba.verify import verify_model as _verify

    namespace = _fresh_namespace()
    return _verify(namespace["model"], clearance_m=clearance_m,
                   script=_ACTIVE_PATH.read_text(encoding="utf-8")).to_dict()


@_tool()
def generate_mesh(output_dir: str) -> Dict[str, Any]:
    """Generate and validate unsolved native diagnostic cells for the bound project.

    Uses model.py sizing and study.py formulations, like Studio Generate mesh.
    output_dir must be new; the response identifies its job directory and mesh
    quality report. No Code_Aster results are produced and source is unchanged.
    """
    from tuba.project.mesh import run_project_mesh
    get_active_model()
    return run_project_mesh(_ACTIVE_PATH.parent, output_dir)


@_tool()
def run_mesh_convergence(output_dir: str) -> Dict[str, Any]:
    """Run verified Code_Aster levels using the bound study's MESH_CONVERGENCE.

    Requires exactly one LOAD_CASES operation and a supported runtime. Holds the
    same project execution claim as Studio/solve_model. output_dir must be new.
    Returns independently verified levels and their measured-change verdicts;
    completing solves does not imply tolerance, accuracy or compliance. Normal
    project evidence is unchanged. Failures retain diagnostics and block results.
    """
    from tuba.project.mesh import run_project_mesh
    get_active_model()
    return run_project_mesh(_ACTIVE_PATH.parent, output_dir, mode="convergence")


@_tool()
def solve_model(
    load_case: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Evaluate the active piping model with the Code_Aster FEA solver.

    Adheres strictly to the Tuba v4 contract: runs actual Code_Aster FEA and returns
    solver metrics and results artifacts. If Code_Aster is not available in the environment,
    fails loudly with actionable diagnostics.

    Freshly loads the bound project and uses study.py's solver options and check hook.
    Every study operation is solved or reused together; *load_case*, when supplied,
    selects an operation to identify in the response, not a partial study solve.
    *force* reruns matching evidence; it never bypasses the cold-model gate.
    Unverified artifacts are reported but never advertised as engineering results.

    The required analysis mesh is generated from authored geometry and sizing.
    Saved runs live in the project's evidence/<operation>/ folders; include every
    file, manifests and study_execution.json when handing them to another machine.
    Matching verified evidence is reused without a new solver execution. An open
    Studio imports completed evidence into Review; share a complete scene.json bundle
    separately for result inspection without the editable project.
    """
    from tuba.project.solve import ProjectVerificationError, solve_project

    try:
        namespace = _fresh_namespace()
        project = load_project(_ACTIVE_PATH.parent)
        with contextlib.redirect_stdout(sys.stderr):
            settings = project.load_settings()
        if load_case is not None and load_case not in settings.operations:
            raise ValueError(f"study.py does not solve {load_case!r}; its LOAD_CASES are {settings.operations!r}.")
        # stdout is the stdio MCP protocol, including while project hooks execute.
        with contextlib.redirect_stdout(sys.stderr):
            outcome = solve_project(project, namespace, force=force)
        artifacts = {}
        for name, run in outcome.runs.items():
            folder = Path(run.study.work_dir).resolve()
            attestation = run.result_state.metadata.get("solve_attestation", {})
            artifacts[name] = {
                "study_id": run.study.id,
                "work_dir": str(folder),
                "files": {filename: str(folder / filename) for filename in attestation.get("artifacts", {})},
                "execution_attestation": str(folder / "study_execution.json"),
                "result_trust": run.result_state.metadata.get("result_trust"),
                "solver_input_identity": run.study.solver_input_identity.to_dict(),
            }
        return {
            "status": "success",
            "project_root": str(project.root),
            "load_case": load_case or (settings.operations[0] if len(settings.operations) == 1 else None),
            "solved": list(outcome.solved),
            "reused": list(outcome.reused),
            "unverified": list(outcome.unverified),
            "verification": outcome.verification.to_dict(),
            "artifacts": artifacts,
            "results_available": not outcome.unverified,
            "studio": _studio_hint(),
            "message": "Project study completed." if not outcome.unverified else
                       "Project study completed with unverified artifacts; engineering result publication is blocked.",
        }
    except ProjectVerificationError as exc:
        return {"status": "error", "message": str(exc), "verification": exc.report.to_dict()}
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "project_root": str(_ACTIVE_PATH.parent) if _ACTIVE_PATH else None,
        }


@_tool()
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
    for lc_name in [*model.load_cases, *model.operations]:
        # ponytail: punctuation becomes "_", so names differing only in punctuation share a folder
        folder = target.parent / "code_aster" / "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in lc_name)
        try:
            decks[lc_name] = CodeAsterSolver().export_analysis_study(model, lc_name, folder).input_files
        except Exception as exc:  # the script is already written; report why this deck is missing
            decks[lc_name] = {"error": f"{type(exc).__name__}: {exc}"}
    return {"status": "success", "file": str(target), "code_aster_inputs": decks}


if __name__ == "__main__":
    mcp.run()

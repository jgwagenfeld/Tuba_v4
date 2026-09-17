"""Reusable construction assemblies that generate model patches."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from typing import Any

from tuba.patches import AddElement, AddNode, AddSupport, AssignAttribute, CreateGroup, ModelPatch
from tuba.routing.types import Point3D


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """JSON-canonical params, so a recorded invocation replays byte-identically."""
    try:
        return json.loads(json.dumps(params))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Assembly params must be JSON-serializable literals, got {params!r}: {exc}") from exc


# Record collections a unit may extend besides nodes/elements/supports: keyed mappings
# (snapshot their key sets) and append-only lists (snapshot their lengths).
_CREATED_KEYED = (
    "groups", "placement_frames", "tees", "load_cases", "operations",
    "cad_assets", "imported_components", "analysis_regions", "ports", "mesh_groups", "couplings",
)
_CREATED_LISTS = ("attributes", "placement_assignments", "obstacles")


def _snapshot_scope(model) -> dict[str, Any]:
    """The identity-bearing state a unit call may extend, for replay skip-sets."""
    return {
        "keyed": {name: list(getattr(model, name)) for name in _CREATED_KEYED},
        "lists": {name: len(getattr(model, name)) for name in _CREATED_LISTS},
        "specs": {kind: list(entries) for kind, entries in model.specs.items()},
    }


def _created_scope(before: dict[str, Any], model) -> dict[str, Any]:
    """What appeared since *before*: created keys and list tails (units are additive)."""
    created: dict[str, Any] = {"keyed": {}, "lists": {}, "specs": {}}
    for name, keys in before["keyed"].items():
        new = [key for key in getattr(model, name) if key not in keys]
        if new:
            created["keyed"][name] = new
    for name, length in before["lists"].items():
        if len(getattr(model, name)) > length:
            created["lists"][name] = [length, len(getattr(model, name))]
    before_specs = before["specs"]
    current_specs = {kind: list(entries) for kind, entries in model.specs.items()}
    for kind, entries in current_specs.items():
        new = [key for key in entries if key not in before_specs.get(kind, [])]
        if new:
            created["specs"][kind] = new
    return created


def _resolve_unit(ref: str, namespace: dict[str, Any] | None):
    """The unit function behind *ref*: ``"name"`` from model.py's own defs, ``"units.mod:fn"`` by import."""
    if ":" in ref:
        module_name, _, func_name = ref.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise ValueError(f"Assembly {ref!r} cannot be imported: {exc}") from exc
        try:
            func = getattr(module, func_name)
        except AttributeError as exc:
            raise ValueError(f"Assembly module {module_name!r} defines no {func_name!r}.") from exc
        if not callable(func):
            raise ValueError(f"Assembly {ref!r} is not callable.")
        return func
    table = namespace
    if table is None:
        frame = sys._getframe(2)  # assemble -> caller (the model.py line invoking it)
        table = frame.f_globals if frame is not None else {}
    try:
        func = table[ref]
    except KeyError as exc:
        raise ValueError(
            f"Assembly {ref!r} is not defined in model.py and is not a 'units.mod:fn' reference."
        ) from exc
    if not callable(func):
        raise ValueError(f"Assembly {ref!r} is not callable.")
    return func


def assemble(model, ref: str, _namespace: dict[str, Any] | None = None, **params):
    """Apply the construction unit *ref* to *model* and record the invocation.

    *ref* is a ``"units.mod:fn"`` import or a bare function name defined in model.py
    itself; the function takes ``(model, **params)``. The invocation (ref, params and
    the record span it created) is recorded on the model, so a generated model.py
    writes it back as this same call. Units may nest: an invocation fully inside
    another replays as part of it. Records the unit left without a script line (units
    imported from ``units/``) are stamped with this call's line in model.py.
    """
    from tuba.codelink import script_lines as _script_lines

    params = _normalize_params(dict(params))
    func = _resolve_unit(ref, _namespace)
    node_ids = set(model.nodes)
    element_ids = {element.id for element in model.elements}
    supports = len(model.supports)
    scope = _snapshot_scope(model)
    result = func(model, **params)
    call: dict[str, Any] = {
        "ref": ref,
        "params": params,
        "node0": len(node_ids),
        "element0": len(element_ids),
        "support0": supports,
        "node1": len(model.nodes),
        "element1": len(model.elements),
        "support1": len(model.supports),
        "created": _created_scope(scope, model),
    }
    model.assembly_calls.append(call)
    line, _ = _script_lines()
    if line is not None:
        for node_id in model.nodes:
            if node_id not in node_ids:
                record = model.nodes[node_id]
                if record.source_line is None:
                    record.source_line = line
        for element in model.elements:
            if element.id not in element_ids:
                if element.source_line is None:
                    element.source_line = line
        for support in model.supports[supports:]:
            if support.source_line is None:
                support.source_line = line
    return result


def check_unit_style(name: str, code: str, func: str) -> None:
    """Refuse copy-paste construction units with a message that teaches the standard.

    A unit replays inside model.py on every studio run, so it must read like project
    code, not a throwaway snippet: documented, honest about its inputs, quiet, and
    statically clean. Each refusal names the rule and the fix.
    """
    import ast as _ast

    tree = _ast.parse(code)
    target = next(
        (node for node in tree.body if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == func),
        None,
    )
    if target is None:  # pragma: no cover - the callable check reports this case
        raise ValueError(f"Unit {name!r} defines no callable {func!r}; nothing was saved.")
    args = [arg.arg for arg in target.args.args]
    if not args or args[0] != "model":
        raise ValueError(
            f"Unit {func!r} must take the model as its first parameter, "
            f"as in 'def {func}(model, ...)', so calls read 'assemble(model, {func!r}, ...)'; nothing was saved."
        )
    if _ast.get_docstring(target) is None:
        raise ValueError(
            f"Unit {func!r} has no docstring: say what it builds and what each parameter means; nothing was saved."
        )
    for node in _ast.walk(target):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name) and node.func.id == "print":
            raise ValueError(
                f"Unit {func!r} calls print(): replayed units run inside model.py on every studio load, "
                "so logging belongs in the returned result, not on stdout; nothing was saved."
            )
        if isinstance(node, _ast.ExceptHandler) and node.type is None:
            raise ValueError(
                f"Unit {func!r} has a bare 'except:': catch what the unit can handle and let the "
                "session report the rest; nothing was saved."
            )
    lint_unit_code(name, code)


def lint_unit_code(name: str, code: str) -> None:
    """Run ruff over unit code when available; a dirty snippet is refused with its report."""
    import shutil as _shutil
    import subprocess as _subprocess

    ruff = _shutil.which("ruff")
    if ruff is None:
        return  # ruff is dev tooling, not a runtime dependency; the AST checks above still teach
    try:
        proc = _subprocess.run(
            [ruff, "check", "--isolated", "--select", "E9,F", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, _subprocess.SubprocessError):
        return
    if proc.returncode != 0:
        report = (proc.stdout or proc.stderr or "ruff reported issues").strip()
        raise ValueError(f"Unit {name!r} is not statically clean; nothing was saved:\n{report}")


@dataclass(frozen=True)
class RackBay:
    name: str
    origin: Point3D
    length: float
    width: float
    height: float
    levels: tuple[float, ...]
    section: str
    material: str
    zone: str | None = None
    column_section: str | None = None
    longitudinal_section: str | None = None
    transverse_section: str | None = None
    shoe_level: float | None = None

    def to_patch(self) -> ModelPatch:
        if self.length <= 0.0 or self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("RackBay dimensions must be positive.")
        z_values = sorted({0.0, self.height, *self.levels})
        for z in z_values:
            if z < 0.0 or z > self.height:
                raise ValueError(f"RackBay level {z!r} is outside rack height.")
        if self.shoe_level is not None and self.shoe_level not in self.levels:
            raise ValueError(f"RackBay shoe_level {self.shoe_level!r} is not one of its levels.")

        operations = []
        node_ids: list[str] = []
        element_ids: list[str] = []

        def node_name(ix: int, iy: int, iz: int) -> str:
            return f"{self.name}_n_{ix}_{iy}_{iz}"

        def point(ix: int, iy: int, z: float) -> Point3D:
            return (
                self.origin[0] + ix * self.length,
                self.origin[1] + iy * self.width,
                self.origin[2] + z,
            )

        for iz, z in enumerate(z_values):
            for ix in (0, 1):
                for iy in (0, 1):
                    local = node_name(ix, iy, iz)
                    node_ids.append(local)
                    operations.append(AddNode(local_id=local, coords=point(ix, iy, z), reuse_existing=False))

        def add_beam(local_id: str, n1: str, n2: str, section: str | None) -> None:
            element_ids.append(local_id)
            operations.append(
                AddElement(
                    local_id=local_id,
                    type="beam",
                    n1=n1,
                    n2=n2,
                    section=section or self.section,
                    material=self.material,
                    id_prefix=f"{self.name}_beam",
                )
            )

        beam_index = 0
        for iz in range(len(z_values) - 1):
            for ix in (0, 1):
                for iy in (0, 1):
                    add_beam(
                        f"{self.name}_col_{beam_index}",
                        node_name(ix, iy, iz),
                        node_name(ix, iy, iz + 1),
                        self.column_section,
                    )
                    beam_index += 1

        for level_number, z in enumerate(self.levels, start=1):
            iz = z_values.index(z)
            for iy in (0, 1):
                add_beam(
                    f"{self.name}_long_{level_number}_{iy}",
                    node_name(0, iy, iz),
                    node_name(1, iy, iz),
                    self.longitudinal_section,
                )
            if self.shoe_level is not None and abs(z - self.shoe_level) < 1e-9:
                for ix in (0, 1):
                    mid = f"{self.name}_mid_{ix}"
                    node_ids.append(mid)
                    operations.append(
                        AddNode(
                            local_id=mid,
                            coords=(
                                self.origin[0] + ix * self.length,
                                self.origin[1] + 0.5 * self.width,
                                self.origin[2] + z,
                            ),
                            reuse_existing=False,
                        )
                    )
                    add_beam(
                        f"{self.name}_cross_{level_number}_{ix}a",
                        node_name(ix, 0, iz),
                        mid,
                        self.transverse_section,
                    )
                    add_beam(
                        f"{self.name}_cross_{level_number}_{ix}b",
                        mid,
                        node_name(ix, 1, iz),
                        self.transverse_section,
                    )
            else:
                for ix in (0, 1):
                    add_beam(
                        f"{self.name}_cross_{level_number}_{ix}",
                        node_name(ix, 0, iz),
                        node_name(ix, 1, iz),
                        self.transverse_section,
                    )

        attachment_points = {}
        for level_number, z in enumerate(self.levels, start=1):
            iz = z_values.index(z)
            attachment_points[f"level_{level_number}_left"] = f"node:{node_name(0, 0, iz)}"
            attachment_points[f"level_{level_number}_right"] = f"node:{node_name(1, 0, iz)}"
            if self.shoe_level is not None and abs(z - self.shoe_level) < 1e-9:
                attachment_points[f"level_{level_number}_mid_left"] = f"node:{self.name}_mid_0"
                attachment_points[f"level_{level_number}_mid_right"] = f"node:{self.name}_mid_1"

        metadata = {
            "assembly_type": "rack_bay",
            "levels": list(self.levels),
            "attachment_points": attachment_points,
        }
        if self.zone is not None:
            metadata["zone"] = self.zone

        operations.append(
            CreateGroup(
                name=self.name,
                nodes=node_ids,
                elements=element_ids,
                metadata=metadata,
            )
        )
        if self.zone is not None:
            operations.append(AssignAttribute(target=f"group:{self.name}", key="rack.zone", value=self.zone))

        return ModelPatch(
            operations=operations,
            provenance={"assembly": self.name, "assembly_type": "rack_bay"},
        )


@dataclass(frozen=True)
class RackRow:
    """A row of rack bays marching along X or Y, with centred pipe hangers.

    Adjacent bays share their station nodes, so the row is one continuous frame.
    The pipe runs mid-width (``origin + width / 2`` on the width axis); at
    ``shoe_level`` each station's cross beam is split into halves joined by a
    midpoint node, and each ``shoes`` entry hangs its pipe node from that midpoint
    as a friction rest. A pipe routed anywhere else cannot be shoed: callers must
    centre it first (``station_point`` reports where each hanger sits).
    """

    name_prefix: str
    origin: Point3D
    material: str
    section: str
    direction: str = "X"
    bays: int = 1
    bay_length: float = 2.0
    width: float = 2.0
    height: float = 3.0
    levels: tuple[float, ...] = (2.75,)
    shoe_level: float | None = None
    shoes: tuple[tuple[str, int], ...] = ()
    anchor_feet: bool = True
    friction_coefficient: float = 0.3
    zone: str | None = None
    column_section: str | None = None
    longitudinal_section: str | None = None
    transverse_section: str | None = None
    open_start: bool = False
    """Leave station 0 open for a corner joint: its nodes are still created (so
    bay 0 longitudinals connect and coincident corner nodes merge on apply),
    but it gets no columns, cross beams, midpoints, anchors, or shoes. Use
    :class:`RackCorner` rather than setting this by hand."""

    def station_point(self, station: int) -> Point3D:
        """World coords of the shoe midpoint at *station* (0..bays)."""
        ox, oy, oz = self.origin
        level = self.shoe_level if self.shoe_level is not None else 0.0
        if self.direction == "X":
            return (ox + station * self.bay_length, oy + self.width / 2.0, oz + level)
        return (ox + self.width / 2.0, oy + station * self.bay_length, oz + level)

    def to_patch(self) -> ModelPatch:
        if self.direction not in ("X", "Y"):
            raise ValueError(f'RackRow direction must be "X" or "Y", got {self.direction!r}.')
        if self.bays < 1:
            raise ValueError("RackRow needs at least one bay.")
        if self.bay_length <= 0.0 or self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("RackRow dimensions must be positive.")
        z_values = sorted({0.0, self.height, *self.levels})
        for z in z_values:
            if z < 0.0 or z > self.height:
                raise ValueError(f"RackRow level {z!r} is outside rack height.")
        if self.shoe_level is not None and self.shoe_level not in self.levels:
            raise ValueError(f"RackRow shoe_level {self.shoe_level!r} is not one of its levels.")
        for _, station in self.shoes:
            if station not in range(self.bays + 1):
                raise ValueError(f"RackRow shoe station {station!r} is outside 0..{self.bays}.")
        if self.shoes and self.shoe_level is None:
            raise ValueError("RackRow shoes need a shoe_level to hang from.")
        if self.open_start:
            for _, station in self.shoes:
                if station == 0:
                    raise ValueError(
                        "RackRow with open_start takes no shoe at station 0: the corner "
                        "station carries no hanger, so hang the pipe from station 1 onwards."
                    )

        def point(station: int, across: float, z: float) -> Point3D:
            along = station * self.bay_length
            ox, oy, oz = self.origin
            if self.direction == "X":
                return (ox + along, oy + across, oz + z)
            return (ox + (self.width - across), oy + along, oz + z)

        def station_bays(station: int) -> set[int]:
            return {bay for bay in (station - 1, station) if 0 <= bay < self.bays}

        def node_name(station: int, side: int, iz: int) -> str:
            return f"{self.name_prefix}_n_{station}_{side}_{iz}"

        operations: list = []
        node_bays: dict[str, set[int]] = {}
        element_bays: dict[str, set[int]] = {}

        def track_node(local: str, bays: set[int]) -> None:
            node_bays.setdefault(local, set()).update(bays)

        def track_element(local: str, bays: set[int]) -> None:
            element_bays.setdefault(local, set()).update(bays)

        for iz, z in enumerate(z_values):
            for station in range(self.bays + 1):
                for side in (0, 1):
                    local = node_name(station, side, iz)
                    operations.append(AddNode(local_id=local, coords=point(station, side * self.width, z)))
                    track_node(local, station_bays(station))

        def add_beam(local_id: str, n1: str, n2: str, section: str | None, bays: set[int]) -> None:
            operations.append(
                AddElement(
                    local_id=local_id,
                    type="beam",
                    n1=n1,
                    n2=n2,
                    section=section or self.section,
                    material=self.material,
                    id_prefix=f"{self.name_prefix}_beam",
                )
            )
            track_element(local_id, bays)

        beam_index = 0
        for station in range(self.bays + 1):
            if self.open_start and station == 0:
                continue  # the corner joint keeps the first row's end posts
            for side in (0, 1):
                for iz in range(len(z_values) - 1):
                    add_beam(
                        f"{self.name_prefix}_col_{beam_index}",
                        node_name(station, side, iz),
                        node_name(station, side, iz + 1),
                        self.column_section,
                        station_bays(station),
                    )
                    beam_index += 1

        for level_number, z in enumerate(self.levels, start=1):
            iz = z_values.index(z)
            for bay in range(self.bays):
                for side in (0, 1):
                    add_beam(
                        f"{self.name_prefix}_long_{level_number}_{bay}_{side}",
                        node_name(bay, side, iz),
                        node_name(bay + 1, side, iz),
                        self.longitudinal_section,
                        {bay},
                    )
            if self.shoe_level is not None and z == self.shoe_level:
                continue  # split halves replace the full cross beams below
            for station in range(self.bays + 1):
                if self.open_start and station == 0:
                    continue  # the corner joint keeps the first row's end beam
                add_beam(
                    f"{self.name_prefix}_cross_{level_number}_{station}",
                    node_name(station, 0, iz),
                    node_name(station, 1, iz),
                    self.transverse_section,
                    station_bays(station),
                )

        mid_at_station: dict[int, str] = {}
        if self.shoe_level is not None:
            iz = z_values.index(self.shoe_level)
            for station in range(self.bays + 1):
                if self.open_start and station == 0:
                    continue  # no hanger on the corner station
                mid = f"{self.name_prefix}_mid_{station}"
                mid_at_station[station] = mid
                operations.append(
                    AddNode(local_id=mid, coords=point(station, self.width / 2.0, self.shoe_level))
                )
                track_node(mid, station_bays(station))
                for half, (a, b) in (
                    ("a", (node_name(station, 0, iz), mid)),
                    ("b", (mid, node_name(station, 1, iz))),
                ):
                    local = f"{self.name_prefix}_cross_shoe_{station}{half}"
                    operations.append(
                        AddElement(
                            local_id=local,
                            type="beam",
                            n1=a,
                            n2=b,
                            section=self.transverse_section or self.section,
                            material=self.material,
                            id_prefix=f"{self.name_prefix}_beam",
                        )
                    )
                    track_element(local, station_bays(station))

        for bay in range(self.bays):
            name = f"{self.name_prefix}{bay}"
            bay_nodes = sorted(local for local, bays in node_bays.items() if bay in bays)
            bay_elements = sorted(local for local, bays in element_bays.items() if bay in bays)
            metadata: dict = {
                "assembly_type": "rack_row_bay",
                "row": self.name_prefix,
                "bay_index": bay,
            }
            if self.zone is not None:
                metadata["zone"] = self.zone
            operations.append(CreateGroup(name=name, nodes=bay_nodes, elements=bay_elements, metadata=metadata))
            if self.zone is not None:
                operations.append(AssignAttribute(target=f"group:{name}", key="rack.zone", value=self.zone))

        if self.anchor_feet:
            for station in range(self.bays + 1):
                if self.open_start and station == 0:
                    continue  # the corner joint keeps the first row's feet
                for side in (0, 1):
                    operations.append(AddSupport(node=node_name(station, side, 0), type="anchor"))
        for pipe_node, station in self.shoes:
            operations.append(
                AddSupport(
                    node=pipe_node,
                    type="rest",
                    attached_to=mid_at_station[station],
                    friction_coefficient=self.friction_coefficient,
                )
            )

        return ModelPatch(
            operations=operations,
            provenance={"assembly": self.name_prefix, "assembly_type": "rack_row"},
        )


@dataclass(frozen=True)
class RackCorner:
    """An L-corner of two rack rows sharing exactly the corner post.

    Rows march toward +X / +Y only, so two L shapes are expressible: a row
    along ``"X"`` turning ``"left"`` (the second row marches +Y), and a row
    along ``"Y"`` turning ``"right"`` (the second row marches +X). Anything
    else raises, naming the feasible pair.

    The second row starts open (:attr:`RackRow.open_start`): its station-0
    nodes are still created, so coincident corner nodes merge with the first
    row's end nodes on apply, but it brings no station-0 columns, cross beams,
    hangers, or anchors. The one genuinely new post (the second row's other
    station-0 side) gets its columns and foot anchor from this patch. The
    result is clash-free by construction; hand-placing two overlapping rows
    instead is what element-versus-element clash detection reports.

    All structural parameters are inherited from *first* unless overridden
    (member sections, friction, feet); only the second row's extent is
    configurable. Shoes may hang at second-row stations
    ``1..bays`` (never 0: the corner station carries no hanger). The new
    corner-post column belongs to no bay group (groups are per-row spans);
    everything else is grouped with its own row.
    """

    name_prefix: str
    first: RackRow
    turn: str = "left"
    bays: int = 1
    bay_length: float | None = None
    shoes: tuple[tuple[str, int], ...] = ()
    zone: str | None = None
    column_section: str | None = None
    longitudinal_section: str | None = None
    transverse_section: str | None = None
    friction_coefficient: float | None = None
    anchor_feet: bool | None = None

    def second_direction(self) -> str:
        """The second row's marching direction for this turn."""
        if self.first.direction == "X" and self.turn == "left":
            return "Y"
        if self.first.direction == "Y" and self.turn == "right":
            return "X"
        raise ValueError(
            f"RackCorner of a {self.first.direction!r} row turning {self.turn!r} is not expressible: "
            'rows march toward +X/+Y only, so use ("X", "left") or ("Y", "right").'
        )

    def second_origin(self) -> Point3D:
        """The second row's origin: its start station shares the corner post."""
        ox, oy, oz = self.first.origin
        if self.first.direction == "X" and self.turn == "left":
            return (ox + self.first.bays * self.first.bay_length, oy + self.first.width, oz)
        if self.first.direction == "Y" and self.turn == "right":
            return (ox + self.first.width, oy + self.first.bays * self.first.bay_length, oz)
        raise ValueError(
            f"RackCorner of a {self.first.direction!r} row turning {self.turn!r} is not expressible: "
            'rows march toward +X/+Y only, so use ("X", "left") or ("Y", "right").'
        )

    def corner_post(self) -> Point3D:
        """Base coordinates of the shared corner post.

        By construction this is the second row's origin: its start station's
        shared side sits exactly on the first row's end post.
        """
        return self.second_origin()

    def _new_post_side(self) -> int:
        """The second row's station-0 side that is genuinely new (not shared)."""
        if self.first.direction == "X" and self.turn == "left":
            return 0
        if self.first.direction == "Y" and self.turn == "right":
            return 1
        raise ValueError(
            f"RackCorner of a {self.first.direction!r} row turning {self.turn!r} is not expressible: "
            'rows march toward +X/+Y only, so use ("X", "left") or ("Y", "right").'
        )

    def second_row(self) -> RackRow:
        """The open-start second row, positioned by :meth:`second_origin`."""
        if self.bays < 1:
            raise ValueError("RackCorner needs at least one bay.")
        bay_length = self.first.bay_length if self.bay_length is None else self.bay_length
        if bay_length <= 0.0:
            raise ValueError("RackCorner bay_length must be positive.")
        for _, station in self.shoes:
            if station not in range(1, self.bays + 1):
                raise ValueError(
                    f"RackCorner shoe station {station!r} is outside 1..{self.bays}: "
                    "the corner station 0 carries no hanger."
                )
        return RackRow(
            name_prefix=self.name_prefix,
            origin=self.second_origin(),
            material=self.first.material,
            section=self.first.section,
            direction=self.second_direction(),
            bays=self.bays,
            bay_length=bay_length,
            width=self.first.width,
            height=self.first.height,
            levels=self.first.levels,
            shoe_level=self.first.shoe_level if self.shoes else None,
            shoes=self.shoes,
            anchor_feet=self.first.anchor_feet if self.anchor_feet is None else self.anchor_feet,
            friction_coefficient=(
                self.first.friction_coefficient
                if self.friction_coefficient is None
                else self.friction_coefficient
            ),
            zone=self.zone if self.zone is not None else self.first.zone,
            column_section=(
                self.first.column_section if self.column_section is None else self.column_section
            ),
            longitudinal_section=(
                self.first.longitudinal_section
                if self.longitudinal_section is None
                else self.longitudinal_section
            ),
            transverse_section=(
                self.first.transverse_section
                if self.transverse_section is None
                else self.transverse_section
            ),
            open_start=True,
        )

    def second_patch(self) -> ModelPatch:
        """Patch for the second row plus the new corner-post members.

        Use this when the first row is already in the model (the repair shape):
        it never rebuilds the first row. :meth:`to_patch` is the fresh-build
        shape (first row plus this).
        """
        second = self.second_row()
        patch = second.to_patch()
        operations: list = list(patch.operations)
        side = self._new_post_side()
        z_values = sorted({0.0, second.height, *second.levels})
        for iz in range(len(z_values) - 1):
            operations.append(
                AddElement(
                    local_id=f"{self.name_prefix}_corner_col_{iz}",
                    type="beam",
                    n1=f"{self.name_prefix}_n_0_{side}_{iz}",
                    n2=f"{self.name_prefix}_n_0_{side}_{iz + 1}",
                    section=second.column_section or second.section,
                    material=second.material,
                    id_prefix=f"{self.name_prefix}_beam",
                )
            )
        if second.anchor_feet:
            operations.append(AddSupport(node=f"{self.name_prefix}_n_0_{side}_0", type="anchor"))
        return ModelPatch(
            operations=operations,
            provenance={
                "assembly": self.name_prefix,
                "assembly_type": "rack_corner",
                "first": self.first.name_prefix,
                "turn": self.turn,
            },
        )

    def to_patch(self) -> ModelPatch:
        """Fresh-build shape: the first row plus :meth:`second_patch`."""
        first_patch = self.first.to_patch()
        second_patch = self.second_patch()
        return ModelPatch(
            operations=[*first_patch.operations, *second_patch.operations],
            provenance={
                "assembly": self.name_prefix,
                "assembly_type": "rack_corner",
                "first": self.first.name_prefix,
                "turn": self.turn,
            },
        )

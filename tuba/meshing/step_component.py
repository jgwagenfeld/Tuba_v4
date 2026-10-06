"""Mesh STEP solids, authored shell panels and native members in one MED study."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import gmsh
import numpy as np

from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.geometry.step_analysis_importer import StepAnalysisImporter
from tuba.meshing._gmsh import gmsh_model
from tuba.meshing.policy import has_mesh_policy, has_legacy_refinements, resolve_mesh_policy, gmsh_policy
from tuba.meshing.quality import mesh_review
from tuba.refs import EntityRef
from tuba.solver.aster_sidecar import build_solver_name_map


@dataclass(frozen=True)
class GeneratedStepComponentMesh:
    analysis_mesh: AnalysisMesh
    groups: dict[str, tuple[str, ...]]
    gmsh_version: str
    settings: dict


def step_mesh_size(model, region, max_element_size=None):
    """Resolve a starting size in metres, preserving an explicit user size."""
    settings = getattr(model,"mesh_settings",{})
    authored = settings.get("region_sizes_m",{}).get(getattr(region,"id",None),settings.get("global_size_m"))
    if max_element_size is None and authored is not None:
        max_element_size = authored
    if region.role == "shell_2d":
        requested = max_element_size if max_element_size is not None else region.metadata.get("mesh_size", "auto")
        points = np.asarray(region.metadata["polygon_m"], dtype=float)
        automatic = float(np.max(np.ptp(points, axis=0))) / 20
    else:
        component = model.imported_components[region.owner.id]
        asset = model.cad_assets[component.asset.id]
        requested = max_element_size if max_element_size is not None else asset.metadata.get("mesh_size", "auto")
        bounds = asset.metadata.get("local_bounds", ())
        automatic = None
        if requested is None or requested == "auto":
            if len(bounds) != 6 or not all(math.isfinite(v) for v in bounds):
                raise ValueError("Automatic STEP sizing requires finite imported CAD bounds.")
            span = max(bounds[i + 3] - bounds[i] for i in range(3)) * asset.unit_scale_to_m
            sizes = [span / 20]
            for port in model.ports.values():
                if port.owner == region.owner and port.kind == "annular_face":
                    wall = port.radius - port.metadata.get("inner_radius_m", 0)
                    if math.isfinite(wall) and wall > 0:
                        sizes.append(wall / 2)
            automatic = min(sizes)
    if requested is None or requested == "auto":
        requested = automatic
    if isinstance(requested, bool) or not isinstance(requested, (int, float)) or not math.isfinite(requested) or requested <= 0:
        raise ValueError("STEP/shell mesh size must be 'auto' or positive and finite in metres.")
    return float(requested)


def step_line_modelisation(model):
    types = {element.type for element in model.elements}
    if types - {"pipe_straight", "beam"}:
        raise ValueError("STEP/shell meshing supports straight pipe and beam continuations only.")
    return "MIXED" if len(types) > 1 else ("POU_D_T" if types == {"beam"} else "TUYAU_3M")


def mesh_step_model(model, output_path, *, max_element_size=None, line_segments=None):
    """Generate a diagnostic mixed mesh without loads or Code_Aster execution."""
    from tuba.solver.code_aster_runtime import write_artifact_text
    output = Path(output_path).resolve()
    if output.suffix.lower() != ".med":
        raise ValueError("STEP mesh output_path must end in .med.")
    model.validate()
    generated = build_step_component_mesh(model, output, max_element_size=max_element_size, line_segments=line_segments)
    mesh = generated.analysis_mesh
    manifest = output.with_suffix(".mesh.json")
    mesh.files["mesh_manifest"] = str(manifest)
    write_artifact_text(manifest, json.dumps({
        "result_status": "mesh_only", "gmsh_version": generated.gmsh_version,
        "mesh_settings": generated.settings, "analysis_mesh": mesh.to_dict(),
    }, indent=2, allow_nan=False))
    return mesh


def build_step_component_mesh(model, output_path, *, region=None, max_element_size=None, line_modelisation=None, line_segments=None, mesh_policy=None):
    """Regenerate all regions and named patches; never replay OCC entity tags.

    The legacy single-region keywords remain accepted. Registered shells and
    references participate in that same study, while mixed lines keep their
    own TUYAU_3M or POU_D_T family per authored element.
    """
    from tuba.mixed import transform_axis, transform_point
    if line_segments is not None and (isinstance(line_segments, bool) or not isinstance(line_segments, int) or line_segments < 1):
        raise ValueError("line_segments must be a positive integer.")
    regions = list(model.analysis_regions.values())
    if region is not None and region not in regions:
        regions.insert(0, region)
    solids = [r for r in regions if getattr(r, "role", "solid_3d") == "solid_3d"]
    shells = [r for r in regions if getattr(r, "role", "") == "shell_2d"]
    references = [r for r in regions if getattr(r, "role", "") == "reference"]
    if any(getattr(r,"role","solid_3d") not in {"solid_3d","shell_2d","reference"} for r in regions):
        raise ValueError("Mixed meshing supports solid_3d, shell_2d and reference regions only.")
    if not solids and not shells:
        raise ValueError("Mixed meshing requires at least one solid_3d or shell_2d region.")
    if len({r.owner for r in solids}) != len(solids):
        raise ValueError("Each STEP component must have exactly one solid_3d region.")
    if any(r.element_order != 2 for r in solids):
        raise ValueError("STEP solids require element_order=2.")
    line_modelisation = step_line_modelisation(model)
    sizes = {r.id: step_mesh_size(model, r, max_element_size) for r in solids + shells if hasattr(r, "id")}
    policy = mesh_policy or resolve_mesh_policy(model,max_element_size=max_element_size)
    if has_mesh_policy(model):
        sizes = {r.id:policy.base_size(str(r.owner)) for r in solids+shells}
    if line_segments is not None and has_mesh_policy(model):
        raise ValueError("line_segments conflicts with authored mesh sizing; remove line_segments so local refinement controls native members.")
    # Portable entry-point interception can use a minimal legacy region record.
    if region is not None and not hasattr(region, "id"):
        if not isinstance(max_element_size, (int, float)) or not math.isfinite(max_element_size) or max_element_size <= 0:
            raise ValueError("STEP mesh size must be positive and finite in metres.")
        sizes["legacy"] = max_element_size
    maximum = max(sizes.values())
    assets, sources, refinements = {}, {}, {}
    for solid in solids:
        component = model.imported_components[solid.owner.id]
        asset = model.cad_assets[component.asset.id]
        source = Path(asset.source_path)
        if asset.source_format.upper() not in {"STEP", "STP"} or source.suffix.lower() not in {".step", ".stp"}:
            raise ValueError("Solved imported solids require a STEP file.")
        digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
        if asset.content_digest != digest:
            raise ValueError("STEP source changed since import; reimport and review its interfaces.")
        key = getattr(solid, "id", "legacy")
        assets[key] = asset
        sources[key] = (source, digest)
        authored = asset.metadata.get("interface_mesh_sizes", {})
        if not isinstance(authored, dict):
            raise ValueError("interface_mesh_sizes must map selected interface names to sizes in metres.")
        effective = {}
        for name, size in authored.items():
            port = model.ports.get(f"{component.id}_{name}")
            if port is None or port.owner != solid.owner or port.status != "confirmed":
                raise ValueError(f"Mesh refinement {name!r} must name a confirmed component interface.")
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
                raise ValueError("Interface mesh sizes must be positive and finite in metres.")
            effective[name] = min(float(size), sizes[key])
        refinements[key] = effective
    output = Path(output_path)
    temporary = output.with_name(f".{output.stem}-{uuid4().hex}.tmp.med")
    try:
        with gmsh_model(gmsh, "tuba_mixed_solve", initialize_args=["-noenv"], options={
            "General.Terminal": 0, "Geometry.OCCTargetUnit": "MM",
            "Mesh.MeshSizeMin": min([policy.minimum_size_m,*sizes.values(), *(s for values in refinements.values() for s in values.values())]),
            "Mesh.MeshSizeMax": max([maximum, *policy._data["base_sizes_m"].values()]),
            "Mesh.ElementOrder": 2, "Mesh.SecondOrderIncomplete": 0,
            "Mesh.RecombineAll": 0, "Mesh.SubdivisionAlgorithm": 0,
        }):
            raw_entities, descriptions, solid_entities, shell_entities = {}, {}, {}, {}
            patch_entities = {}
            face_bindings = {}
            def register(raw, dimension, entities, source_ref, role, expected):
                if raw in raw_entities:
                    raise ValueError(f"Mixed mesh group name {raw!r} collides with another generated group.")
                raw_entities[raw] = (dimension, tuple(entities))
                descriptions[raw] = (source_ref, role, expected)
            importer = StepAnalysisImporter()
            for solid in solids:
                asset = assets[solid.id]
                imported = gmsh.model.occ.importShapes(str(sources[solid.id][0]))
                gmsh.model.occ.synchronize()
                volumes = tuple(tag for dim, tag in imported if dim == 3)
                if not volumes:
                    raise ValueError("STEP analysis component contains no CAD solid.")
                boundary = tuple(dict.fromkeys(abs(tag) for dim, tag in gmsh.model.getBoundary([(3,v) for v in volumes], combined=False, oriented=False) if dim == 2))
                solid_entities[solid.id] = volumes
                register(solid.mesh_group, 3, volumes, solid.owner, "volume_cell", (2,10,4))
                register(f"G_SKIN_{solid.id}", 2, boundary, solid.owner, "volume_skin", (2,6,3))
                local_faces = {face["gmsh_face_tag"]: face for face in importer._describe_faces(imported)}
                for rule in policy._data["refinements"]:
                    cad = rule.get("cad_target")
                    if cad is not None and cad["component"] == str(solid.owner):
                        face_bindings[rule["id"]] = importer.resolve_face_selector(imported,cad["selector"])
                selected_faces = set()
                for port in model.ports.values():
                    if port.owner != solid.owner or port.status != "confirmed" or not port.face_group:
                        continue
                    selector = port.metadata.get("face_selector")
                    if not isinstance(selector, dict):
                        raise ValueError(f"Interface {port.id!r} needs a geometric face selector; reimport it.")
                    face_tag = importer.resolve_face_selector(imported, selector)
                    face = local_faces[face_tag]
                    tolerance = max(1e-8, face["radius"] * asset.unit_scale_to_m * 1e-5)
                    center = transform_point(face["position"], asset.unit_scale_to_m, asset.placement)
                    axis = transform_axis(face["axis"], asset.placement) if face["axis"] is not None else None
                    if axis is None or math.dist(center, port.position) > tolerance or math.dist(axis, port.axis) > 1e-6 or abs(face["radius"]*asset.unit_scale_to_m-port.radius) > tolerance or face["shape"] != port.kind:
                        raise ValueError(f"Interface {port.id!r} differs from its placed CAD face; reimport it.")
                    if "inner_radius_m" in port.metadata and abs(face["inner_radius"]*asset.unit_scale_to_m-port.metadata["inner_radius_m"]) > tolerance:
                        raise ValueError(f"Interface {port.id!r} bore differs from its CAD face; reimport it.")
                    if face_tag in selected_faces:
                        raise ValueError("STEP interfaces must not alias the same physical face.")
                    selected_faces.add(face_tag)
                    register(port.face_group, 2, [face_tag], solid.owner, "volume_skin", (2,6,3))
                pressure = solid.metadata.get("pressure_surfaces", [])
                if pressure:
                    register(f"G_PRESSURE_{solid.id}", 2, [importer.resolve_face_selector(imported,s) for s in pressure], solid.owner, "volume_skin", (2,6,3))
                for patch in model.couplings.values():
                    if patch.kind == "rigid_patch" and patch.target == solid.owner:
                        patch_entities[patch.id] = (2, tuple(importer.resolve_face_selector(imported,s) for s in patch.metadata["face_selectors"]))
                origin = np.asarray(transform_point((0,0,0),asset.unit_scale_to_m,asset.placement))
                columns = [np.asarray(transform_point(p,asset.unit_scale_to_m,asset.placement))-origin for p in ((1,0,0),(0,1,0),(0,0,1))]
                matrix = np.eye(4)
                matrix[:3,:3], matrix[:3,3] = np.column_stack(columns), origin
                gmsh.model.occ.affineTransform(list(imported), matrix.ravel().tolist())
                gmsh.model.occ.synchronize()
                points = gmsh.model.getBoundary(list(imported), combined=False, oriented=False, recursive=True)
                gmsh.model.mesh.setSize([(d,abs(t)) for d,t in points if d == 0], sizes[solid.id])
            node_entities = {node_id: gmsh.model.occ.addPoint(*node.coords, policy.base_size()) for node_id,node in model.nodes.items()}
            reference_nodes = {r.owner.id for r in references}
            shell_points, shell_edges, shell_point_sizes = {}, {}, {}
            for shell in shells:
                points = []
                for position in shell.metadata["polygon_m"]:
                    authored = [n for n,node in model.nodes.items() if n not in reference_nodes and math.dist(node.coords,position)<=1e-8]
                    if len(authored)>1:
                        raise ValueError("Shell polygon corner matches multiple authored native nodes; share one node explicitly.")
                    key = tuple(round(float(value), 12) for value in position)
                    if key not in shell_points:
                        shell_points[key] = node_entities[authored[0]] if authored else gmsh.model.occ.addPoint(*position,sizes[shell.id])
                    point = shell_points[key]
                    shell_point_sizes[point] = min(shell_point_sizes.get(point, sizes[shell.id]), sizes[shell.id])
                    points.append(point)
                edges, loop = [], []
                for a, b in zip(points, points[1:] + points[:1]):
                    key = tuple(sorted((a, b)))
                    if key not in shell_edges:
                        shell_edges[key] = gmsh.model.occ.addLine(*key)
                    edge = shell_edges[key]
                    edges.append(edge)
                    loop.append(edge if (a, b) == key else -edge)
                # Reuse the geometric boundary, so adjacent panels share all
                # edge DOFs rather than only touching at coincident corners.
                surface = gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(loop)])
                shell_entities[shell.id] = (surface,points,edges)
                register(shell.mesh_group, 2, [surface], shell.owner, "shell_cell", (1,3,3))
            line_entities = {e.id: gmsh.model.occ.addLine(node_entities[e.n1],node_entities[e.n2]) for e in model.elements}
            gmsh.model.occ.synchronize()
            if line_segments is not None:
                # Diagnostic Build meshes keep native lines independent of a
                # small solid's sizing. Solver exports retain their sizing policy.
                for entity in line_entities.values():
                    gmsh.model.mesh.setTransfiniteCurve(entity, line_segments + 1)
            for point, size in shell_point_sizes.items():
                gmsh.model.mesh.setSize([(0, point)], size)
            for reference in references:
                register(reference.mesh_group, 0, [node_entities[reference.owner.id]], reference.owner, "reference_carrier", (0,1,1))
            pipe_entities = [line_entities[e.id] for e in model.elements if e.type == "pipe_straight"]
            beam_entities = [line_entities[e.id] for e in model.elements if e.type == "beam"]
            if pipe_entities:
                register("G_TUBE", 1, pipe_entities, None, "native_element", (2,3,2))
            if beam_entities:
                register("G_FRAME" if pipe_entities else "G_TUBE", 1, beam_entities, None, "native_element", (1,2,2))
            for element in model.elements:
                expected = (1,2,2) if element.type == "beam" else (2,3,2)
                register(f"G_LINE_{element.id}", 1, [line_entities[element.id]], EntityRef("element",element.id), "native_element", expected)
            raw_node_names = [f"G_NODE_{n}" for n in node_entities]
            patch_names = [p.metadata["mesh_node_group"] for p in model.couplings.values() if p.kind == "rigid_patch"]
            if set(raw_entities).intersection(raw_node_names+patch_names) or len(set(patch_names)) != len(patch_names):
                raise ValueError("Mixed mesh node group collides with another generated group name.")
            name_map = build_solver_name_map([*raw_entities,*raw_node_names,*patch_names])
            for raw,(dimension,entities) in raw_entities.items():
                physical=gmsh.model.addPhysicalGroup(dimension,list(entities))
                gmsh.model.setPhysicalName(dimension,physical,name_map[raw])
            entity_sources = {(3,tag):str(r.owner) for r in solids for tag in solid_entities[r.id]}
            entity_sources.update({(2,shell_entities[r.id][0]):str(r.owner) for r in shells})
            entity_sources.update({(1,tag):f"element:{id}" for id,tag in line_entities.items()})
            with gmsh_policy(gmsh,policy,entity_sources,face_bindings=face_bindings) as bound:
                gmsh.model.mesh.generate(3 if solids else 2)
                # Sample while finite CAD bindings are alive; this is requested
                # sizing evidence, independent of result artifacts.
                size_preview = bound.preview()
            gmsh.model.mesh.setOrder(2)
            for entity in beam_entities:
                _linearize(entity,1,8,1,3,2)
            for surface,_,_ in shell_entities.values():
                _linearize(surface,2,9,2,6,3)
            node_groups = {f"G_NODE_{node_id}": _point_nodes(entity,node_id) for node_id,entity in node_entities.items()}
            for patch in model.couplings.values():
                if patch.kind != "rigid_patch":
                    continue
                selection = patch.metadata["selection"]
                if selection == "component_faces":
                    dimension,entities = patch_entities[patch.id]
                    selected = {int(t) for entity in entities for t in gmsh.model.mesh.getNodes(dimension,entity,includeBoundary=True)[0]}
                    if node_filter := patch.metadata.get("node_filter"):
                        from tuba.mixed import patch_node_filter_contains, transform_axis
                        component = model.imported_components[patch.target.id]
                        asset = model.cad_assets[component.asset.id]
                        w,x,y,z = asset.placement["rotation"]
                        inverse = {"rotation": [w,-x,-y,-z]}
                        origin = asset.placement["origin"]
                        def source_point(tag):
                            coordinates = gmsh.model.mesh.getNode(tag)[0]
                            local = transform_axis([float(v)-o for v,o in zip(coordinates,origin)],inverse)
                            return [v/asset.unit_scale_to_m for v in local]
                        selected = {tag for tag in selected if patch_node_filter_contains(source_point(tag),node_filter)}
                elif selection in {"shell_vertices","shell_edges"}:
                    shell = next(r for r in shells if r.owner == patch.target)
                    _,points,edges = shell_entities[shell.id]
                    dimension,entities = (0,[points[i] for i in patch.metadata["vertices"]]) if selection == "shell_vertices" else (1,[edges[i] for i in patch.metadata["edges"]])
                    selected = {int(t) for entity in entities for t in gmsh.model.mesh.getNodes(dimension,entity,includeBoundary=True)[0]}
                    # TRI3 panels have no midside DOFs after conversion.
                    used = set(int(n) for block in gmsh.model.mesh.getElements(2,shell_entities[shell.id][0])[2] for n in block)
                    selected &= used
                else:
                    selected = {t for n in patch.metadata["nodes"] for t in node_groups[f"G_NODE_{n}"]}
                reference_nodes = node_groups[f"G_NODE_{patch.source_node.id}"]
                selected.difference_update(reference_nodes)
                if not selected:
                    raise RuntimeError(f"Rigid patch {patch.id!r} selects no physical analysis nodes.")
                selected.update(reference_nodes)
                node_groups[patch.metadata["mesh_node_group"]] = tuple(sorted(selected))
            mesh,groups=_readback(model,output,regions,raw_entities,descriptions,line_entities,node_entities,node_groups,solid_entities)
            review = mesh_review(mesh,policy,gmsh=gmsh,output_path=output)
            review["size_preview"] = size_preview
            review["statistics"]["mesher_translation"] = {"sizing":"native_gmsh_fields",
                "cad_distance_sampling":100 if face_bindings else None,
                "interpretation":"Gmsh curvature and scoped fields control sizing; CAD distances use sampled finite faces."}
            mesh = replace(mesh,mesh_review=review)
            output.parent.mkdir(parents=True,exist_ok=True)
            _write_exact_med(temporary, mesh, set(node_groups), name_map)
            if not temporary.is_file() or not temporary.stat().st_size:
                raise RuntimeError("Gmsh produced an empty mixed MED mesh.")
            for source,digest in sources.values():
                if "sha256:"+hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    raise ValueError("STEP source changed during meshing; reimport it.")
            temporary.replace(output)
            settings={"element_family":"TETRA10" if solids else "TRI3","element_order":2 if solids else 1,
                "max_element_size":maximum,"region_mesh_sizes":sizes,
                "interface_mesh_sizes":next(iter(refinements.values())) if len(refinements)==1 else refinements,
                "mesh_size_request":next(iter(assets.values())).metadata.get("mesh_size","auto") if len(assets)==1 else {r.id:r.metadata.get("mesh_size","auto") for r in shells},
                "line_element_family":"mixed" if line_modelisation=="MIXED" else ("SEG2" if line_modelisation=="POU_D_T" else "SEG3")}
            if line_segments is not None:
                settings["line_segments"] = line_segments
            if has_mesh_policy(model) or has_legacy_refinements(model):
                settings["mesh_policy"] = policy.to_dict()
            return GeneratedStepComponentMesh(mesh,groups,str(gmsh.__version__),settings)
    finally:
        temporary.unlink(missing_ok=True)


def _linearize(entity,dimension,source_type,target_type,count,primary):
    types,tags,nodes=gmsh.model.mesh.getElements(dimension,entity)
    if list(types) != [source_type]:
        raise RuntimeError("Unexpected quadratic family before linear member conversion.")
    corners=np.asarray(nodes[0]).reshape(-1,count)[:,:primary].ravel()
    gmsh.model.mesh.removeElements(dimension,entity)
    gmsh.model.mesh.addElementsByType(entity,target_type,tags[0],corners)


def _point_nodes(entity,node_id):
    tags,_,_=gmsh.model.mesh.getNodes(0,entity)
    if len(tags) != 1:
        raise RuntimeError(f"Mixed mesh has no unique point node for {node_id!r}.")
    return tuple(int(tag) for tag in tags)


def _readback(model,output,regions,raw_entities,descriptions,line_entities,node_entities,node_groups,solid_entities):
    tags,coordinates,_=gmsh.model.mesh.getNodes()
    if not np.isfinite(coordinates).all() or len(set(map(int,tags))) != len(tags):
        raise RuntimeError("Mixed mesh contains non-finite or duplicate node coordinates/tags.")
    nodes={f"VN{int(t)}":tuple(float(v) for v in coordinates[i*3:i*3+3]) for i,t in enumerate(tags)}
    elements,sources,groups,node_sources={}, {}, {}, {}
    skin_faces=[]
    line_by_entity={entity:model.get_element(id) for id,entity in line_entities.items()}
    for raw,(dimension,entities) in raw_entities.items():
        ref,role,expected=descriptions[raw]
        members=[]
        for entity in entities:
            entity_ref=EntityRef("element",line_by_entity[entity].id) if dimension==1 else ref
            types,tag_blocks,node_blocks=gmsh.model.mesh.getElements(dimension,entity)
            for kind,cell_tags,connectivity in zip(types,tag_blocks,node_blocks):
                _,dim,order,count,_,primary=gmsh.model.mesh.getElementProperties(kind)
                if (order,count,primary) != expected or dim != dimension:
                    raise RuntimeError(f"Unsupported mixed mesh element family {kind} in {raw!r}.")
                for i,tag in enumerate(cell_tags):
                    prefix={"volume_cell":"VM","volume_skin":"VS","shell_cell":"SM","native_element":"LM","reference_carrier":"RC"}[role]
                    cell_id=f"{prefix}{int(tag)}"
                    cell_nodes=tuple(f"VN{int(n)}" for n in connectivity[i*count:i*count+count])
                    if len(cell_nodes)!=count or len(set(cell_nodes))!=count or any(n not in nodes for n in cell_nodes):
                        raise RuntimeError(f"Mixed mesh cell {cell_id!r} has invalid node connectivity.")
                    elements[cell_id]=cell_nodes
                    members.append(cell_id)
                    sources[cell_id]=MeshElementSource(cell_id,entity_ref,role,metadata={"solver_element_tag":int(tag)})
                    for node_id in cell_nodes:
                        node_role={"volume_cell":"volume_node","volume_skin":"volume_node","shell_cell":"shell_node","native_element":"generated_element_node","reference_carrier":"native_node"}[role]
                        if node_id not in node_sources:
                            node_sources[node_id]=MeshNodeSource(node_id,entity_ref,node_role)
                    if role=="volume_skin" and raw.startswith("G_SKIN_"):
                        skin_faces.append(cell_nodes[:3])
        if not members:
            raise RuntimeError(f"Mixed mesh group {raw!r} is empty.")
        groups[raw]=tuple(members)
    for region in regions:
        if region.role != "solid_3d":
            continue
        for volume in solid_entities[region.id]:
            _,blocks,_=gmsh.model.mesh.getElements(3,volume)
            volume_tags=[int(t) for block in blocks for t in block]
            # Measured quality is retained by mesh_review before publication.
            boundary=gmsh.model.getBoundary([(3,volume)],oriented=False)
            faces=[]
            for dim,face in boundary:
                if dim != 2:
                    continue
                _,_,node_blocks=gmsh.model.mesh.getElements(2,abs(face))
                faces.extend(tuple(f"VN{int(n)}" for n in block[i:i+6]) for block in node_blocks for i in range(0,len(block),6))
            _require_tetra_boundary([elements[f"VM{t}"] for t in volume_tags],faces)
    for raw,tags in node_groups.items():
        groups[raw]=tuple(f"VN{tag}" for tag in tags)
    for node_id,entity in node_entities.items():
        mesh_id=groups[f"G_NODE_{node_id}"][0]
        node_sources[mesh_id]=MeshNodeSource(mesh_id,EntityRef("node",node_id),"native_node")
    nodes={n:p for n,p in nodes.items() if n in node_sources}
    if any(n not in nodes for raw,members in groups.items() if raw in node_groups for n in members):
        raise RuntimeError("Rigid patch contains a node outside the analysis mesh.")
    skin_nodes=tuple(dict.fromkeys(n for face in skin_faces for n in face))
    indices={n:i for i,n in enumerate(skin_nodes)}
    modelisations={r.mesh_group:r.code_aster_modelisation for r in regions}
    pipes=any(e.type=="pipe_straight" for e in model.elements)
    beams=any(e.type=="beam" for e in model.elements)
    if pipes:
        modelisations["G_TUBE"]="TUYAU_3M"
    if beams:
        modelisations["G_FRAME" if pipes else "G_TUBE"]="POU_D_T"
    mesh=AnalysisMesh(id=f"step-solid-{uuid4().hex}",model_revision=int(getattr(model,"revision",0)),solver_name="Code_Aster",
        nodes=nodes,elements=elements,groups=groups,node_sources=node_sources,element_sources=sources,files={"med":str(output)},
        modelisations=modelisations,
        surface_mesh={"vertices":[nodes[n] for n in skin_nodes],"faces":[[indices[n] for n in face] for face in skin_faces],"node_ids":skin_nodes} if skin_faces else None)
    # Code_Aster numbers imported MED entities by serialized ordinal, ignoring
    # optional native NUM/NOM tags. Normalize only after all Gmsh quality checks.
    mesh = _normalize_med_ordinals(mesh)
    return mesh,mesh.groups


def _med_cell_family(nodes,source):
    family={"volume_cell":"tetra10", "volume_skin":"triangle6", "shell_cell":"triangle",
            "reference_carrier":"vertex"}.get(source.role)
    if source.role == "native_element":
        family="line3" if len(nodes)==3 else "line"
    if family is None:
        raise RuntimeError(f"Unsupported MED cell role {source.role!r}.")
    return family


def _normalize_med_ordinals(mesh):
    """Match the native MED import order while retaining original Gmsh lineage."""
    node_map={old:f"VN{i}" for i,old in enumerate(mesh.nodes,1)}
    # MED geometric codes: PO1=1, SE2=102, SE3=103, TR3=203, TR6=206, T10=310.
    families={family:[] for family in ("vertex","line","line3","triangle","triangle6","tetra10")}
    for cell,nodes in mesh.elements.items():
        families[_med_cell_family(nodes,mesh.element_sources[cell])].append(cell)
    ordered=(cell for cells in families.values() for cell in cells)
    cell_map={old:f"{old[:2]}{i}" for i,old in enumerate(ordered,1)}
    node_sources={}
    for old,source in mesh.node_sources.items():
        metadata=dict(source.metadata)
        metadata.setdefault("gmsh_node_tag",int(old[2:]))
        node_sources[node_map[old]]=replace(source,node_id=node_map[old],metadata=metadata)
    element_sources={}
    for old in cell_map:
        source=mesh.element_sources[old]
        metadata=dict(source.metadata)
        metadata.setdefault("gmsh_element_tag",int(old[2:]))
        metadata["solver_element_tag"]=int(cell_map[old][2:])
        element_sources[cell_map[old]]=replace(source,element_id=cell_map[old],metadata=metadata)
    identities={**node_map,**cell_map}
    surface=mesh.surface_mesh
    if surface is not None and "node_ids" in surface:
        surface={**surface,"node_ids":[node_map[node] for node in surface["node_ids"]]}
    return replace(mesh,
        nodes={node_map[old]:point for old,point in mesh.nodes.items()},
        elements={cell_map[old]:tuple(node_map[node] for node in mesh.elements[old]) for old in cell_map},
        groups={raw:tuple(identities[member] for member in members) for raw,members in mesh.groups.items()},
        node_sources=node_sources,element_sources=element_sources,surface_mesh=surface)


def _write_exact_med(output, mesh, node_group_names, name_map):
    """Serialize the actual validated mesh, preserving every family and label.

    Gmsh's MED writer conflates SEG2/SEG3 in mixed-order studies and exports
    physical points as cells. MED nodal families represent our node groups;
    only authored DIS_TR references become POI1 cells.
    """
    import h5py
    import meshio
    from meshio.med._med import meshio_to_med_type

    node_ids = list(mesh.nodes)
    indices = {n:i for i,n in enumerate(node_ids)}
    point_memberships = {n:[] for n in node_ids}
    cell_memberships = {c:[] for c in mesh.elements}
    for raw,members in mesh.groups.items():
        target = point_memberships if raw in node_group_names else cell_memberships
        for member in members:
            target[member].append(name_map[raw])
    def families(memberships, sign):
        family_ids, names, tags = {}, {}, {}
        for member,groups in memberships.items():
            key = tuple(sorted(set(groups)))
            if not key:
                tags[member] = 0
                continue
            family = family_ids.setdefault(key, sign*(len(family_ids)+1))
            names[family] = list(key)
            tags[member] = family
        return tags,names
    point_tags,point_names = families(point_memberships,1)
    cell_tags,cell_names = families(cell_memberships,-1)
    type_cells = {}
    for cell,nodes in mesh.elements.items():
        family = _med_cell_family(nodes,mesh.element_sources[cell])
        type_cells.setdefault(family,[]).append(cell)
    permutations = {"tetra10":(0,2,1,3,6,5,4,7,8,9)}
    blocks=[]
    for family,cell_ids in type_cells.items():
        data=[]
        for cell in cell_ids:
            nodes=mesh.elements[cell]
            order=permutations.get(family,range(len(nodes)))
            data.append([indices[nodes[i]] for i in order])
        blocks.append((family,np.asarray(data,dtype=np.int64)))
    exported=meshio.Mesh(np.asarray(list(mesh.nodes.values())),blocks,
        point_data={"point_tags":np.asarray([point_tags[n] for n in node_ids],dtype=np.int32)},
        cell_data={"cell_tags":[np.asarray([cell_tags[c] for c in cell_ids],dtype=np.int32) for cell_ids in type_cells.values()]})
    exported.point_tags,exported.cell_tags = point_names,cell_names
    meshio.write(output,exported,file_format="med")
    # Dense ordinal suffixes preserve the native compiler/result contract.
    def native_labels(ids):
        return [id[2:] for id in ids]
    def labels(group,names):
        names=native_labels(names)
        dataset=group.create_dataset("NOM",(len(names),),dtype="16int8")
        dataset.attrs["CGT"],dataset.attrs["NBR"] = 1,len(names)
        for name in names:
            if not name.isdigit() or len(name)>8:
                raise RuntimeError(f"MED entity label {name!r} must be a numeric tag of at most 8 characters.")
        dataset[:]=np.frombuffer("".join(name.ljust(16) for name in names).encode("ascii"),dtype=np.int8).reshape(len(names),16)
        # Keep standard NUM/NOM metadata consistent with the serialized ordinals.
        # Original sparse Gmsh tags remain in the analysis source metadata.
        numbers=group.create_dataset("NUM",data=np.asarray(names,dtype=np.int32))
        numbers.attrs["CGT"],numbers.attrs["NBR"] = np.int32(1),np.int32(len(names))
    with h5py.File(output,"r+") as file:
        # meshio concatenates every overlapping group into the MED family name.
        # A reference joining many patches can exceed libMED's name buffer and
        # abort native LIRE_MAILLAGE. Group membership lives in GRO/NOM; the
        # family only needs a short unique name and its unchanged NUM identity.
        for kind in ("NOEUD", "ELEME"):
            families = file["FAS"]["mesh"].get(kind)
            if families is not None:
                for old in list(families):
                    name = f"FAM_{int(families[old].attrs['NUM'])}"
                    if old != name:
                        families.move(old, name)
        ensemble=file["ENS_MAA"]["mesh"]
        step=ensemble[next(iter(ensemble))]
        # Native libMED reads GEO to identify cells, rather than their group name.
        # meshio omits it and the static mesh's next/previous time-step links.
        geometry_codes = {"PO1":1, "SE2":102, "SE3":103, "TR3":203, "TR6":206, "T10":310}
        for attribute in ("NXI", "NXT"):
            ensemble.attrs[attribute] = np.int32(-1)
        for attribute in ("NXI", "NXT", "PVI", "PVT"):
            step.attrs[attribute] = np.int32(-1)
        labels(step["NOE"],node_ids)
        for family,cell_ids in type_cells.items():
            med_type = meshio_to_med_type[family]
            cell_group = step["MAI"][med_type]
            cell_group.attrs["GEO"] = np.int32(geometry_codes[med_type])
            labels(cell_group,cell_ids)
    # Roundtrip all numerical connectivity, labels and overlapping families.
    actual=meshio.read(output)
    if not np.array_equal(actual.points,exported.points) or actual.point_tags != point_names or actual.cell_tags != cell_names:
        raise RuntimeError("MED roundtrip changed node coordinates or physical families.")
    if not np.array_equal(actual.point_data["point_tags"],exported.point_data["point_tags"]):
        raise RuntimeError("MED roundtrip changed physical node groups.")
    expected_blocks={block.type:block.data for block in exported.cells}
    actual_blocks={block.type:block.data for block in actual.cells}
    if set(actual_blocks)!=set(expected_blocks) or any(not np.array_equal(actual_blocks[k],expected_blocks[k]) for k in expected_blocks):
        raise RuntimeError("MED roundtrip changed an element family or its connectivity.")
    expected_cell_tags={block.type:tags for block,tags in zip(exported.cells,exported.cell_data["cell_tags"])}
    if any(not np.array_equal(tags,expected_cell_tags[block.type]) for block,tags in zip(actual.cells,actual.cell_data["cell_tags"])):
        raise RuntimeError("MED roundtrip changed physical cell groups.")
    with h5py.File(output) as file:
        ensemble=file["ENS_MAA"]["mesh"]
        step=ensemble[next(iter(ensemble))]
        def decoded(group):
            return [bytes(row).decode("ascii").rstrip(" ") for row in group["NOM"][()]]
        def numbered(group,ids):
            numbers=group["NUM"]
            return (numbers.dtype == np.dtype("int32") and numbers.attrs["CGT"] == 1
                    and numbers.attrs["NBR"] == len(ids)
                    and np.array_equal(numbers[()],np.asarray(native_labels(ids),dtype=np.int32)))
        if decoded(step["NOE"])!=native_labels(node_ids) or any(decoded(step["MAI"][meshio_to_med_type[family]])!=native_labels(cell_ids) for family,cell_ids in type_cells.items()):
            raise RuntimeError("MED roundtrip changed native node or element labels.")
        if not numbered(step["NOE"],node_ids) or any(not numbered(step["MAI"][meshio_to_med_type[family]],cell_ids) for family,cell_ids in type_cells.items()):
            raise RuntimeError("MED roundtrip changed native node or element numbers.")


def _require_tetra_boundary(cells, skin_faces):
    """Require one conformal solid whose exposed tetrahedron faces match its skin."""
    owners = {}
    neighbours = [set() for _ in cells]
    quadratic_faces = {}
    for index, nodes in enumerate(cells):
        for indices, mids in (((0,1,2),(4,5,6)), ((0,1,3),(4,9,7)), ((0,2,3),(6,8,7)), ((1,2,3),(5,8,9))):
            face = frozenset(nodes[i] for i in indices)
            if len(face) != 3:
                raise RuntimeError("STEP mesh contains a degenerate tetrahedron face.")
            previous = owners.setdefault(face, [])
            if len(previous) == 2:
                raise RuntimeError("STEP mesh contains a non-manifold tetrahedron face.")
            if len(nodes) == 10:
                full_face = face | frozenset(nodes[i] for i in mids)
                if len(full_face) != 6 or (face in quadratic_faces and quadratic_faces[face] != full_face):
                    raise RuntimeError("STEP mesh contains a non-conformal quadratic tetrahedron face.")
                quadratic_faces[face] = full_face
            for other in previous:
                neighbours[index].add(other)
                neighbours[other].add(index)
            previous.append(index)
    boundary = {face for face, indices in owners.items() if len(indices) == 1}
    skin = [frozenset(face[:3]) for face in skin_faces]
    if len(set(skin)) != len(skin) or set(skin) != boundary:
        raise RuntimeError("STEP mesh skin does not match every exposed tetrahedron face exactly once.")
    if quadratic_faces and any(len(face) != 6 or quadratic_faces[frozenset(face[:3])] != frozenset(face) for face in skin_faces):
        raise RuntimeError("STEP mesh quadratic skin nodes do not match its exposed tetrahedron faces.")
    visited = set()
    pending = [0] if cells else []
    while pending:
        index = pending.pop()
        if index not in visited:
            visited.add(index)
            pending.extend(neighbours[index] - visited)
    if not cells or len(visited) != len(cells):
        raise RuntimeError("STEP mesh contains a disconnected volume mesh.")

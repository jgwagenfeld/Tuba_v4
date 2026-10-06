"""Authored, metre-based sizing and a pure, deterministic meshing decision.

CAD selectors remain source-local identities here. Only a live mesher can bind
them to finite OCC faces; an unbound face never pretends to have a distance.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Any, Callable

import numpy as np

from tuba.canonical import canonical_digest


def _number(value, label, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{label} must be {'non-negative' if zero else 'positive'} and finite in metres.")
    return float(value)


def _vector(value, label):
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != 3:
        raise ValueError(f"{label} requires three finite coordinates in metres.")
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in value):
        raise ValueError(f"{label} requires three finite coordinates in metres.")
    return [float(v) for v in value]


def has_mesh_policy(model):
    return bool(model.mesh_settings or model.mesh_refinements)


def has_legacy_refinements(model):
    return any(model.cad_assets[c.asset.id].metadata.get("interface_mesh_sizes") for c in model.imported_components.values())


def set_mesh_size(model, size_m, *, region=None):
    size = _number(size_m, "mesh size")
    if region is None:
        model.mesh_settings["global_size_m"] = size
    else:
        key = str(region).removeprefix("analysis_region:")
        if key not in model.analysis_regions or model.analysis_regions[key].role not in {"solid_3d", "shell_2d"}:
            raise ValueError(f"Mesh size region {key!r} is missing or unsupported; select a solid_3d or shell_2d analysis region.")
        model.mesh_settings.setdefault("region_sizes_m", {})[key] = size


def set_mesh_size_factor(model, factor):
    """Dimensionless multiplier applied after automatic sizing and transitions resolve."""
    if isinstance(factor, bool) or not isinstance(factor, Real) or not math.isfinite(factor) or factor <= 0:
        raise ValueError("mesh size factor must be positive and finite (dimensionless).")
    model.mesh_settings["size_factor"] = float(factor)


def _target(model, target):
    from tuba.refs import EntityRef
    if isinstance(target,EntityRef):
        target = str(target)
    elif isinstance(target,dict) and set(target)=={"kind","id"}:
        target = str(EntityRef.from_dict(target))
    if isinstance(target, str):
        if ":" not in target:
            raise ValueError("Mesh target must be an entity reference such as 'element:pipe_0'.")
        kind, id = target.split(":", 1)
        if kind == "element":
            if not any(e.id == id for e in model.elements):
                raise ValueError(f"Mesh target element {id!r} is missing.")
        elif kind == "group":
            group = model.groups.get(id)
            shells = [r for r in model.analysis_regions.values() if r.owner.kind=="group" and r.owner.id==id and r.role=="shell_2d"]
            if group is None or (not group.get("elements") and not shells):
                raise ValueError(f"Mesh target group {id!r} is missing or empty; select a group of elements.")
            for element in group["elements"]:
                _target(model, f"element:{element}")
        elif kind == "analysis_region":
            region = model.analysis_regions.get(id)
            if region is None or region.role not in {"solid_3d", "shell_2d"}:
                raise ValueError(f"Mesh target analysis region {id!r} is missing or unsupported.")
        elif kind == "component":
            if id not in model.imported_components or not any(r.owner.kind == kind and r.owner.id == id and r.role == "solid_3d" for r in model.analysis_regions.values()):
                raise ValueError(f"Mesh target component {id!r} is missing or has no solid_3d analysis region.")
        elif kind == "port":
            port = model.ports.get(id)
            if port is None or port.status != "confirmed" or not port.metadata.get("face_selector"):
                raise ValueError(f"Mesh target port {id!r} is missing or unconfirmed; reimport and confirm its CAD face.")
            _target(model, {"kind": "face", "component": str(port.owner), "selector": port.metadata["face_selector"]})
        else:
            raise ValueError(f"Unsupported mesh target {target!r}; select elements, groups, regions, components, confirmed ports, faces, sphere or box.")
        return target
    if not isinstance(target, dict):
        raise ValueError("Unsupported mesh target; provide an entity reference or a sphere, box or face dictionary.")
    kind = target.get("kind")
    if kind == "sphere":
        if set(target) - {"kind", "center_m", "radius_m"}:
            raise ValueError("Unsupported sphere target fields.")
        return {"kind": kind, "center_m": _vector(target.get("center_m"), "sphere center_m"),
                "radius_m": _number(target.get("radius_m"), "sphere radius_m")}
    if kind == "box":
        if set(target) - {"kind", "min_m", "max_m"}:
            raise ValueError("Unsupported box target fields.")
        lo, hi = _vector(target.get("min_m"), "box min_m"), _vector(target.get("max_m"), "box max_m")
        if any(b <= a for a, b in zip(lo, hi)):
            raise ValueError("Box bounds must have positive width along every axis.")
        return {"kind": kind, "min_m": lo, "max_m": hi}
    if kind == "face":
        from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError
        if set(target) - {"kind", "component", "selector"}:
            raise ValueError("Unsupported face target fields; use source-local selector syntax.")
        component = str(target.get("component", ""))
        component = component if component.startswith("component:") else f"component:{component}"
        _target(model, component)
        try:
            selector = StepAnalysisImporter.validate_face_selector(target.get("selector"))
        except StepImportError as exc:
            raise ValueError(str(exc)) from exc
        return {"kind": kind, "component": component, "selector": selector}
    raise ValueError(f"Unsupported mesh target kind {kind!r}.")


def add_mesh_refinement(model, id, *, target, size_m, influence_distance_m=0.0, transition_distance_m=None):
    if not isinstance(id, str) or not id.strip():
        raise ValueError("Mesh refinement id must be a nonempty string.")
    if id in model.mesh_refinements:
        raise ValueError(f"Mesh refinement {id!r} already exists; remove it before replacing it.")
    size = _number(size_m, "size_m")
    influence = _number(influence_distance_m, "influence_distance_m", zero=True)
    transition = None if transition_distance_m is None else _number(transition_distance_m, "transition_distance_m")
    model.mesh_refinements[id] = {"id": id, "target": _target(model, target), "size_m": size,
                                   "influence_distance_m": influence, "transition_distance_m": transition}


def remove_mesh_refinement(model, id):
    if id not in model.mesh_refinements:
        raise ValueError(f"Mesh refinement {id!r} is missing.")
    del model.mesh_refinements[id]


def element_point(model, element, t):
    start = np.asarray(model.nodes[element.n1].coords, dtype=float)
    end = np.asarray(model.nodes[element.n2].coords, dtype=float)
    if element.type != "pipe_bend":
        return start + (end - start) * t
    # Use the same geometry fallback as the native compiler, including authored bends.
    from tuba.solver.aster_mesh import AsterMeshGenerator, _rotate_about_axis
    center, axis, radial, angle = AsterMeshGenerator()._get_bend_geometry(model, element)
    return center + _rotate_about_axis(radial, axis / np.linalg.norm(axis), angle * t)


def _element_shape(model, element):
    start, end = (_vector(model.nodes[n].coords, "element position") for n in (element.n1, element.n2))
    section = model.sections[element.section]
    radius = float(getattr(section, "OD", 0)) / 2
    if element.type == "pipe_bend":
        from tuba.solver.aster_mesh import AsterMeshGenerator
        center, axis, radial, angle = AsterMeshGenerator()._get_bend_geometry(model, element)
        return {"kind": "arc", "center_m": list(center), "axis": list(axis / np.linalg.norm(axis)),
                "radial_m": list(radial), "angle_rad": float(angle), "radius_m": radius}
    return {"kind": "cylinder", "start_m": start, "end_m": end, "radius_m": radius}


def _distance(shape, point):
    p = np.asarray(point, dtype=float)
    kind = shape["kind"]
    if kind == "sphere":
        return max(0.0, math.dist(point, shape["center_m"]) - shape["radius_m"])
    if kind == "box":
        return float(np.linalg.norm(np.maximum(np.maximum(np.asarray(shape["min_m"]) - p, p - np.asarray(shape["max_m"])), 0)))
    if kind == "cylinder":
        a, b = np.asarray(shape["start_m"]), np.asarray(shape["end_m"])
        length = float(np.linalg.norm(b-a))
        axis = (b-a) / length
        station = float(np.dot(p-a, axis))
        radial = float(np.linalg.norm(p-a-station*axis))
        return math.hypot(max(0., -station, station-length), max(0., radial-shape["radius_m"]))
    if kind == "arc":
        from tuba.solver.aster_mesh import _rotate_about_axis
        center, axis, radial = (np.asarray(shape[key]) for key in ("center_m", "axis", "radial_m"))
        q = p-center
        angle = math.atan2(float(np.dot(np.cross(radial,q),axis)), float(np.dot(radial,q)))
        sweep = shape["angle_rad"]
        candidates = [center+radial, center+_rotate_about_axis(radial,axis,sweep)]
        for a in (angle, angle+2*math.pi, angle-2*math.pi):
            if min(0,sweep) <= a <= max(0,sweep):
                candidates.append(center+_rotate_about_axis(radial,axis,a))
        return max(0., min(float(np.linalg.norm(p-c)) for c in candidates)-shape["radius_m"])
    raise ValueError(f"Unsupported distance geometry {kind!r}.")


@dataclass(frozen=True)
class ResolvedMeshPolicy:
    _data: dict[str, Any]
    _samples: tuple[dict[str, Any], ...] = field(default_factory=tuple,repr=False,compare=False)
    _cad_distances: dict[str, Callable] = field(default_factory=dict, repr=False, compare=False)

    @property
    def fingerprint(self):
        return canonical_digest(self._data)

    def to_dict(self):
        return {**deepcopy(self._data), "fingerprint": self.fingerprint}

    @property
    def minimum_size_m(self):
        return min([self._data["global_size_m"], *self._data["base_sizes_m"].values(),
                    *(r["size_m"] for r in self._data["refinements"])])

    def base_size(self, source_ref=None):
        return self._data["base_sizes_m"].get(str(source_ref), self._data["global_size_m"])

    def size_at(self, position, *, source_ref=None):
        point = _vector(position, "size_at position")
        source = None if source_ref is None else str(source_ref)
        base = self.base_size(source)
        effective = base
        for rule in self._data["refinements"]:
            if source is not None and rule["source_refs"] and source not in rule["source_refs"]:
                continue
            if rule.get("cad_target"):
                callback = self._cad_distances.get(rule["id"])
                if callback is None:
                    raise ValueError(f"Mesh refinement {rule['id']!r} requires exact CAD face binding before size_at; preview reports pending_cad_binding.")
                distance = float(callback(point))
            else:
                distance = min(_distance(shape, point) for shape in rule["geometry"])
            transition = rule.get("transition_distances_m",{}).get(source,rule["transition_distance_m"])
            fraction = min(1., max(0., (distance-rule["influence_distance_m"])/transition))
            effective = min(effective, rule["size_m"]+fraction*(base-rule["size_m"]))
        return effective

    def bind_cad(self, distances):
        return ResolvedMeshPolicy(deepcopy(self._data),self._samples,dict(distances))

    def preview(self, *, max_samples=256):
        if isinstance(max_samples, bool) or not isinstance(max_samples,int) or not 1 <= max_samples <= 2048:
            raise ValueError("max_samples must be an integer from 1 to 2048.")
        samples = self._samples
        chosen = samples if len(samples) <= max_samples else [samples[i] for i in np.linspace(0,len(samples)-1,max_samples,dtype=int)]
        result = []
        for sample in chosen:
            pending = [r["id"] for r in self._data["refinements"] if r.get("cad_target") and r["id"] not in self._cad_distances
                       and (not r["source_refs"] or sample["source_ref"] in r["source_refs"])]
            entry = dict(sample)
            if pending:
                entry.update(status="pending_cad_binding", pending_refinements=pending, size_m=None)
            else:
                entry.update(status="resolved", size_m=self.size_at(sample["position_m"],source_ref=sample["source_ref"]))
            result.append(entry)
        return {"label": "requested sizing", "units": "m", "sampling": "bounded geometry samples; not a cell-size or accuracy guarantee",
                "sample_count": len(result), "samples": result}


def resolve_mesh_policy(model, *, max_element_size=None, volume_geometry=None):
    """Resolve inputs without invoking Gmsh, creating files or mutating the model."""
    settings = deepcopy(model.mesh_settings)
    if set(settings)-{"global_size_m","region_sizes_m","size_factor"}:
        raise ValueError("Unsupported mesh_settings fields.")
    factor = settings.get("size_factor", 1.)
    if isinstance(factor, bool) or not isinstance(factor, Real) or not math.isfinite(factor) or factor <= 0:
        raise ValueError("mesh size factor must be positive and finite (dimensionless).")
    global_size = _number(settings["global_size_m"],"global_size_m") if "global_size_m" in settings else None
    override = None if max_element_size is None else _number(max_element_size,"max_element_size")
    region_sizes = settings.get("region_sizes_m",{})
    if not isinstance(region_sizes,dict):
        raise ValueError("region_sizes_m must map analysis region ids to positive finite metre sizes.")
    bases, geometry, samples, sources = {}, {}, [], {}
    for element in model.elements:
        ref = f"element:{element.id}"
        shape = _element_shape(model, element)
        geometry[ref] = [shape]
        sources[ref] = {"geometry":shape}
        length = (float(np.linalg.norm(np.asarray(shape["radial_m"]))) * abs(shape["angle_rad"]) if shape["kind"]=="arc"
                  else math.dist(shape["start_m"],shape["end_m"]))
        if length <= 0:
            raise ValueError(f"Mesh target element {element.id!r} has zero length.")
        bases[ref] = override or global_size or length/(16 if element.type=="pipe_bend" else 8)
        samples.extend({"position_m":list(element_point(model,element,float(t))),"source_ref":ref} for t in np.linspace(0,1,17))
    for region in model.analysis_regions.values():
        if region.role not in {"solid_3d","shell_2d"}:
            continue
        ref = str(region.owner)
        if region.id in region_sizes:
            size = _number(region_sizes[region.id],f"region_sizes_m {region.id!r}")
        else:
            from tuba.meshing.step_component import step_mesh_size
            size = global_size or step_mesh_size(model,region)
        bases[ref] = override or size
        bases[f"analysis_region:{region.id}"] = override or size
        if region.role == "shell_2d":
            polygon = [_vector(p,"shell polygon_m") for p in region.metadata["polygon_m"]]
            lo, hi = np.min(polygon,axis=0), np.max(polygon,axis=0)
            # Surface distance is evaluated by the mesher. Region selection refines the entire region.
            geometry[ref] = [{"kind":"box","min_m":lo.tolist(),"max_m":hi.tolist()}]
            samples.extend({"position_m":p,"source_ref":ref} for p in [*polygon,np.mean(polygon,axis=0).tolist()])
        else:
            component = model.imported_components[region.owner.id]
            asset = model.cad_assets[component.asset.id]
            from tuba.mixed import transform_point
            bounds = asset.metadata.get("local_bounds")
            if bounds is None or len(bounds)!=6 or not all(isinstance(v,Real) and not isinstance(v,bool) and math.isfinite(v) for v in bounds):
                raise ValueError(f"Component {component.id!r} requires finite imported CAD bounds; reimport it.")
            corners = [transform_point([bounds[i+3*bit] for i,bit in enumerate(bits)],asset.unit_scale_to_m,asset.placement)
                       for bits in ((a,b,c) for a in (0,1) for b in (0,1) for c in (0,1))]
            geometry[ref] = [{"kind":"box","min_m":np.min(corners,axis=0).tolist(),"max_m":np.max(corners,axis=0).tolist()}]
            sources[ref] = {"content_digest":asset.content_digest,"unit_scale_to_m":asset.unit_scale_to_m,"placement":asset.placement.to_dict() if hasattr(asset.placement,"to_dict") else deepcopy(asset.placement)}
            samples.extend({"position_m":list(p),"source_ref":ref} for p in [*corners,np.mean(corners,axis=0).tolist()])
    for id in region_sizes:
        if id not in model.analysis_regions or model.analysis_regions[id].role not in {"solid_3d","shell_2d"}:
            raise ValueError(f"Mesh size region {id!r} is missing or unsupported.")
    volume_base = None
    if volume_geometry is not None:
        volume_base = override or global_size or volume_geometry.wall_thickness_m/2
        for element_id in volume_geometry.element_ids:
            bases[f"element:{element_id}"] = volume_base
    base_global = override or global_size or volume_base or (max(bases.values()) if bases else .1)
    rules = []
    authored = deepcopy(model.mesh_refinements)
    # Legacy interface settings use exactly the same scope and transition law.
    for component in model.imported_components.values():
        asset = model.cad_assets[component.asset.id]
        legacy = asset.metadata.get("interface_mesh_sizes",{})
        if not isinstance(legacy,dict):
            raise ValueError("interface_mesh_sizes must map confirmed interfaces to positive finite sizes in metres.")
        for name,size in legacy.items():
            id = f"legacy:{component.id}:{name}"
            if id in authored:
                raise ValueError(f"Mesh refinement id {id!r} is reserved for interface_mesh_sizes.")
            authored[id] = {"id":id,"target":f"port:{component.id}_{name}","size_m":size,"influence_distance_m":0.,"transition_distance_m":None}
    for id,record in sorted(authored.items()):
        if record.get("id") != id:
            raise ValueError(f"Mesh refinement key {id!r} does not match its id.")
        if set(record)-{"id","target","size_m","influence_distance_m","transition_distance_m"}:
            raise ValueError(f"Unsupported fields in mesh refinement {id!r}.")
        target = _target(model,record.get("target"))
        scope, shapes, cad = [], [], None
        if isinstance(target,dict):
            if target["kind"]=="face":
                scope,cad = [target["component"]],target
            else:
                shapes = [target]
        else:
            kind,key = target.split(":",1)
            if kind=="group":
                scope = [f"element:{e}" for e in sorted(set(model.groups[key].get("elements",[])))]
                scope += [str(r.owner) for r in model.analysis_regions.values() if r.owner.kind=="group" and r.owner.id==key and r.role=="shell_2d"]
            elif kind=="analysis_region":
                scope = [str(model.analysis_regions[key].owner)]
            elif kind=="port":
                port = model.ports[key]
                scope = [str(port.owner)]
                cad = {"kind":"face","component":str(port.owner),"selector":deepcopy(port.metadata["face_selector"])}
            else:
                scope = [target]
            if cad is None:
                shapes = [shape for ref in scope for shape in geometry[ref]]
        base = min((bases[ref] for ref in scope),default=base_global)
        transition = record.get("transition_distance_m")
        transition = 3*base if transition is None else _number(transition,"transition_distance_m")
        rule = {"id":id,"target":target,"size_m":_number(record.get("size_m"),"size_m"),
                "influence_distance_m":_number(record.get("influence_distance_m",0),"influence_distance_m",zero=True),
                "transition_distance_m":transition,"source_refs":scope,"geometry":shapes}
        if record.get("transition_distance_m") is None:
            rule["transition_distances_m"] = {ref:3*size for ref,size in bases.items() if not scope or ref in scope}
        if cad is not None:
            rule["cad_target"] = cad
        if volume_geometry is not None:
            volume_refs = {f"element:{e}" for e in volume_geometry.element_ids}
            if set(scope)&volume_refs:
                # A tee is one fused OCC solid. Keep the authored run geometry
                # as the target while all selected runs share its finite field.
                rule["target_source_refs"] = list(scope)
                rule["source_refs"] = sorted(set(scope)|volume_refs)
        rules.append(rule)
    # Default transition extents above use unscaled, source-specific baseline sizes.
    # Physical targets/distances never participate in the dimensionless multiplier.
    if factor != 1.:
        base_global *= factor
        bases = {ref:size*factor for ref,size in bases.items()}
        for rule in rules:
            rule["size_m"] *= factor
    return ResolvedMeshPolicy({"schema":"tuba.mesh-policy.v1","units":"m","authored_settings":settings,
        "invocation_max_element_size_m":override,"global_size_m":base_global,"base_sizes_m":dict(sorted(bases.items())),
        "source_geometry":sources,"volume_geometry":volume_geometry.to_dict() if volume_geometry is not None else None,
        "refinements":rules},tuple(samples))


def line_stations(model, policy, *, minimum_segments=None):
    """Adaptive stations with conservative finite-box sizing between samples."""
    result = {}
    for element in model.elements:
        ref = f"element:{element.id}"
        shape = _element_shape(model,element)
        length = (np.linalg.norm(shape["radial_m"])*abs(shape["angle_rad"]) if shape["kind"]=="arc"
                  else math.dist(shape["start_m"],shape["end_m"]))
        count = (minimum_segments or {}).get(element.id,1)
        seeds = set(float(t) for t in np.linspace(0,1,count+1))
        box_rules = []
        # Include closest stations and exact spatial boundary crossings. This is
        # essential for a narrow plateau far from the original interval midpoint.
        for rule in policy._data["refinements"]:
            if rule["source_refs"] and ref not in rule["source_refs"]:
                continue
            for target in rule["geometry"]:
                seeds.update(_feature_stations(shape,target))
                if target["kind"]=="box":
                    box_rules.append((target,rule))
        seeds = sorted(seeds)
        pending = list(zip(seeds[:-1],seeds[1:]))
        stations = {0.,1.}
        while pending:
            a,b = pending.pop()
            requested = min(policy.size_at(element_point(model,element,t),source_ref=ref) for t in (a,(a+b)/2,b))
            if box_rules:
                lo,hi = _member_interval_bounds(shape,a,b)
                base = policy.base_size(ref)
                for target,rule in box_rules:
                    # Distance between enclosing boxes cannot exceed distance
                    # from any path point to the finite target. The resulting
                    # requested size therefore also covers unsampled narrow
                    # approaches to a finite edge or corner.
                    separation = np.maximum(np.maximum(np.asarray(target["min_m"])-hi,
                                                       lo-np.asarray(target["max_m"])),0.)
                    distance = float(np.linalg.norm(separation))
                    transition = rule.get("transition_distances_m",{}).get(ref,rule["transition_distance_m"])
                    fraction = min(1.,max(0.,(distance-rule["influence_distance_m"])/transition))
                    requested = min(requested,rule["size_m"]+fraction*(base-rule["size_m"]))
            if length*(b-a) > requested*(1+1e-12):
                if len(stations)+len(pending)>100000:
                    raise ValueError(f"Refinement of element {element.id!r} exceeds 100000 stations; increase size_m.")
                mid = (a+b)/2
                if mid==a or mid==b:
                    raise ValueError(f"Refinement size_m for element {element.id!r} is below coordinate resolution; increase the requested size.")
                pending.extend(((a,mid),(mid,b)))
            else:
                stations.update((float(a),float(b)))
        result[element.id] = sorted(stations)
    return result


def _member_interval_bounds(member, a, b):
    """Exact coordinate extrema of a finite straight or circular path interval."""
    if member["kind"]=="cylinder":
        start,end = np.asarray(member["start_m"]),np.asarray(member["end_m"])
        points = np.asarray([start+(end-start)*a,start+(end-start)*b])
    else:
        center,axis,radial = (np.asarray(member[key]) for key in ("center_m","axis","radial_m"))
        parallel = axis*np.dot(axis,radial)
        cosine,sine = radial-parallel,np.cross(axis,radial)
        first,last = sorted((member["angle_rad"]*a,member["angle_rad"]*b))
        angles = [first,last]
        for i in range(3):
            if cosine[i]==0 and sine[i]==0:
                continue
            phase = math.atan2(sine[i],cosine[i])
            angles.extend(phase+k*math.pi for k in range(math.ceil((first-phase)/math.pi),
                                                       math.floor((last-phase)/math.pi)+1))
        points = np.asarray([center+parallel+cosine*math.cos(theta)+sine*math.sin(theta) for theta in angles])
    # Expand by one representable coordinate so rounding does not shrink the
    # enclosing interval at a coordinate extremum.
    return np.nextafter(points.min(axis=0),-np.inf),np.nextafter(points.max(axis=0),np.inf)


def _feature_stations(member, target):
    points = []
    if target["kind"]=="sphere":
        points = [target["center_m"]]
    elif target["kind"]=="box":
        points = [(np.asarray(target["min_m"])+np.asarray(target["max_m"]))/2]
    else:
        return []
    result = []
    if member["kind"]=="cylinder":
        a,b = np.asarray(member["start_m"]),np.asarray(member["end_m"])
        direction = b-a
        for point in points:
            result.append(float(np.clip(np.dot(np.asarray(point)-a,direction)/np.dot(direction,direction),0,1)))
        if target["kind"]=="box":
            for axis in range(3):
                if abs(direction[axis])>1e-15:
                    for bound in (target["min_m"][axis],target["max_m"][axis]):
                        t = (bound-a[axis])/direction[axis]
                        if 0<t<1:
                            result.append(float(t))
    else:
        center,axis,radial = (np.asarray(member[key]) for key in ("center_m","axis","radial_m"))
        tangent = np.cross(axis,radial)
        sweep = member["angle_rad"]
        for point in points:
            q = np.asarray(point)-center
            angle = math.atan2(float(np.dot(q,tangent)),float(np.dot(q,radial)))
            for turn in (-2*math.pi,0,2*math.pi):
                if 0<(angle+turn)/sweep<1:
                    result.append((angle+turn)/sweep)
        if target["kind"]=="box":
            for i in range(3):
                amplitude = math.hypot(radial[i],tangent[i])
                if amplitude<=1e-15:
                    continue
                phase = math.atan2(tangent[i],radial[i])
                for bound in (target["min_m"][i],target["max_m"][i]):
                    v = (bound-center[i])/amplitude
                    if abs(v)<=1:
                        for angle in (phase+math.acos(v),phase-math.acos(v)):
                            for turn in (-2*math.pi,0,2*math.pi):
                                t = (angle+turn)/sweep
                                if 0<t<1:
                                    result.append(t)
    return result


@contextmanager
def gmsh_policy(gmsh, policy, entity_sources, *, face_bindings=None, size_scale=1.0):
    """Compile requested sizing into model-owned native Gmsh background fields.

    Exact OCC distances remain available for the bounded requested-size preview,
    but no Python callback or mutable query point participates in meshing.
    """
    bindings = face_bindings or {}
    missing = [r["id"] for r in policy._data["refinements"] if r.get("cad_target") and r["id"] not in bindings]
    if missing:
        raise ValueError(f"Exact CAD binding missing for mesh refinements {missing!r}; resolve source-local selectors before meshing.")
    query = gmsh.model.occ.addPoint(0,0,0) if bindings else None
    location = np.zeros(3)
    def distance(point, face):
        nonlocal location
        offset = np.asarray(point)-location
        gmsh.model.occ.translate([(0,query)],*offset)
        location = np.asarray(point)
        value = float(gmsh.model.occ.getDistance(0,query,2,face)[0])
        if not math.isfinite(value) or value<0:
            raise ValueError(f"Exact finite CAD face distance failed for face {face}.")
        return value
    distances = {id:(lambda point,face=face: distance(point,face)) for id,face in bindings.items()}
    bound = policy.bind_cad(distances)
    owners = {}
    for (dim,tag),refs in entity_sources.items():
        refs = [refs] if isinstance(refs,str) else list(refs)
        for entity in [(dim,tag), *[(d,abs(t)) for d,t in gmsh.model.getBoundary([(dim,tag)],combined=False,oriented=False,recursive=True)]]:
            owners.setdefault(entity,set()).update(refs)
        if dim>1:
            for entity in gmsh.model.getBoundary([(dim,tag)],combined=False,oriented=False):
                owners.setdefault((entity[0],abs(entity[1])),set()).update(refs)
                for edge in gmsh.model.getBoundary([(entity[0],abs(entity[1]))],combined=False,oriented=False):
                    owners.setdefault((edge[0],abs(edge[1])),set()).update(refs)
    fields = []
    def add(kind, **options):
        tag = gmsh.model.mesh.field.add(kind)
        fields.append(tag)
        for name,value in options.items():
            setter = (gmsh.model.mesh.field.setString if isinstance(value,str) else
                      gmsh.model.mesh.field.setNumbers if isinstance(value,list) else gmsh.model.mesh.field.setNumber)
            setter(tag,name,value)
        return tag
    def restrict(tag, entities):
        return add("Restrict", InField=tag, **{name:[t for d,t in entities if d==dim]
                   for dim,name in enumerate(("PointsList","CurvesList","SurfacesList","VolumesList"))})
    previous_options = {name:gmsh.option.getNumber(name) for name in
                        ("Mesh.MeshSizeFromPoints","Mesh.MeshSizeExtendFromBoundary","Mesh.MeshSizeMin")}
    try:
        active = []
        scopes = {}
        for ref in sorted({ref for refs in owners.values() for ref in refs}):
            base = policy.base_size(ref)
            applicable = tuple((i,rule.get("transition_distances_m",{}).get(ref,rule["transition_distance_m"]))
                for i,rule in enumerate(policy._data["refinements"])
                if (not rule["source_refs"] or ref in rule["source_refs"]) and rule["size_m"]<base)
            scopes.setdefault((base,applicable),set()).update(entity for entity,refs in owners.items() if ref in refs)
        for (base,applicable),entities in scopes.items():
            sizes = [add("MathEval",F=repr(size_scale*base))]
            for index,transition in applicable:
                rule = policy._data["refinements"][index]
                if rule.get("cad_target"):
                    # ponytail: Gmsh Distance samples finite CAD faces; exact OCC
                    # queries are preview-only. Qualify denser sampling if needed.
                    face = (2,bindings[rule["id"]])
                    distance_field = add("Distance",SurfacesList=[face[1]],Sampling=100)
                    # Sampling must not coarsen the requested size on the face itself.
                    face_entities = {face}
                    for edge in gmsh.model.getBoundary([face],oriented=False):
                        face_entities.add((edge[0],abs(edge[1])))
                        face_entities.update((d,abs(t)) for d,t in gmsh.model.getBoundary([edge],oriented=False))
                    active.append(restrict(add("MathEval",F=repr(size_scale*rule["size_m"])),sorted(face_entities)))
                elif rule["source_refs"] and set(rule.get("target_source_refs",rule["source_refs"])) >= set(rule["source_refs"]):
                    # A selected whole entity is inside its own target geometry.
                    sizes.append(add("MathEval",F=repr(size_scale*rule["size_m"])))
                    continue
                else:
                    distance_fields = [add("MathEval",F=_gmsh_distance_expression(shape)) for shape in rule["geometry"]]
                    distance_field = add("Min",FieldsList=distance_fields)
                sizes.append(add("Threshold",InField=distance_field,
                    SizeMin=size_scale*rule["size_m"],SizeMax=size_scale*base,
                    DistMin=rule["influence_distance_m"],DistMax=rule["influence_distance_m"]+transition))
            active.append(restrict(add("Min",FieldsList=sizes),sorted(entities)))
        if active:
            gmsh.model.mesh.field.setAsBackgroundMesh(add("Min",FieldsList=active))
        # Fields own entity sizes. A policy-wide minimum also couples unrelated
        # solids: adding one refinement must not change their curvature sizing.
        for name in previous_options:
            # HEXA20 subdivision needs Gmsh's native boundary-size extension.
            if name=="Mesh.MeshSizeExtendFromBoundary" and policy._data["volume_geometry"] is not None:
                continue
            gmsh.option.setNumber(name,0)
        yield bound
    finally:
        for tag in reversed(fields):
            gmsh.model.mesh.field.remove(tag)
        for name,value in previous_options.items():
            gmsh.option.setNumber(name,value)
        if query is not None:
            gmsh.model.occ.remove([(0,query)])


def _gmsh_distance_expression(shape):
    """Translate finite authored spatial targets for Gmsh's native MathEval."""
    def square(value):
        return f"({value})^2"
    if shape["kind"]=="sphere":
        offset = [f"({axis}-({value!r}))" for axis,value in zip("xyz",shape["center_m"])]
        return f"Max(0,Sqrt({'+'.join(map(square,offset))})-({shape['radius_m']!r}))"
    if shape["kind"]=="box":
        offset = [f"Max(0,Max(({lo!r})-{axis},{axis}-({hi!r})))"
                  for axis,lo,hi in zip("xyz",shape["min_m"],shape["max_m"])]
        return f"Sqrt({'+'.join(map(square,offset))})"
    if shape["kind"]=="cylinder":
        start,end = np.asarray(shape["start_m"]),np.asarray(shape["end_m"])
        length = float(np.linalg.norm(end-start))
        axis = (end-start)/length
        offset = [f"({coordinate}-({float(value)!r}))" for coordinate,value in zip("xyz",start)]
        station = '('+'+'.join(f"{q}*({float(v)!r})" for q,v in zip(offset,axis))+')'
        radial = f"Max(0,Sqrt(Max(0,{'+'.join(map(square,offset))}-{square(station)}))-({shape['radius_m']!r}))"
        axial = f"Max(0,Max(-{station},{station}-({length!r})))"
        return f"Sqrt({square(radial)}+{square(axial)})"
    raise ValueError(f"Unsupported Gmsh distance geometry {shape['kind']!r}.")

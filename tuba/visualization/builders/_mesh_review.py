"""Requested sizing and bounded problem locations, separate from solver fields."""
from __future__ import annotations

import math
import numpy as np

from tuba.visualization.builders._contract import SceneContribution
from tuba.visualization.scene import GeometryAsset, SceneObject, SceneLayer, SceneDiagnostic


def build_mesh_review_scene(model, meshes, volume_export=None):
    from tuba.meshing.policy import resolve_mesh_policy, has_mesh_policy, has_legacy_refinements
    from tuba.geometry.volume import build_volume_geometry

    reviews = [(mesh.id, mesh.mesh_review) for mesh in meshes if mesh.mesh_review is not None]
    preview_layer = None
    if not reviews and (has_mesh_policy(model) or has_legacy_refinements(model) or model.analysis_regions or volume_export):
        try:
            geometry = build_volume_geometry(model, volume_export["element_ids"]) if volume_export else None
            policy = resolve_mesh_policy(model, max_element_size=(volume_export or {}).get("max_element_size"), volume_geometry=geometry)
            review = {"schema": "tuba.mesh-review.v1", "policy": policy.to_dict(), "size_preview": policy.preview()}
            reviews = [("authored", review)]
            preview_layer = SceneLayer(id="analysis_mesh:identity:authored", category="analysis_mesh",
                label="Authored requested sizing", default_visible=False, extra={"mesh_identity": {"mesh_review": review}})
        except (ValueError, TypeError, OSError) as exc:
            return SceneContribution(diagnostics=(SceneDiagnostic(severity="error", code="mesh_review.policy_invalid", message=str(exc)),)), None
    objects, assets = [], []

    def add(id, kind, name, format, bounds, config, layer, **metadata):
        object_id, asset_id = f"object:{id}", f"geometry:{id}"
        objects.append(SceneObject(id=object_id, kind=kind, name=name, geometry_asset_id=asset_id,
                                   layer_ids=[f"analysis_mesh:review:{layer}"], metadata=metadata))
        assets.append(GeometryAsset(id=asset_id, format=format, bounds=bounds, object_ids=[object_id],
                                    generation_config={"source": "tuba.analysis_mesh.review", **config}))

    for mesh_id, review in reviews:
        samples = (review.get("size_preview") or {}).get("samples", [])[:256]
        values = [s["size_m"] for s in samples if s.get("size_m") is not None]
        low, high = (min(values), max(values)) if values else (0, 0)
        for index, sample in enumerate(samples):
            if sample.get("size_m") is None:
                continue  # exact CAD distance is explicitly pending until binding
            point, size = sample["position_m"], sample["size_m"]
            radius = max(size * .12, 1e-5)
            fraction = (size - low) / (high - low) if high > low else .5
            color = "#%02x%02x%02x" % (round(230*(1-fraction)+37*fraction), round(90*(1-fraction)+99*fraction), round(40*(1-fraction)+235*fraction))
            bounds = [*(x-radius for x in point), *(x+radius for x in point)]
            add(f"mesh_size:{mesh_id}:{index}", "mesh_size_sample", f"Requested size {size:g} m", "point", bounds,
                {"point": point, "radius_m": radius, "color": color}, "sizing", source_ref=sample.get("source_ref"), size_m=size)
        for rule in review.get("policy", {}).get("refinements", []):
            cad = rule.get("cad_target")
            if cad:
                # Reuse the imported source face partition, including placement
                # and source units. Display triangles are not exact OCC distances.
                from tuba.visualization.builders._mappings import _component_faces
                component = model.imported_components.get(cad["component"].split(":", 1)[1])
                parts, _ = _component_faces(model, component, [cad["selector"]]) if component else ([], [])
                for index, (format, config, points) in enumerate(parts):
                    bounds = [*np.min(points, axis=0).tolist(), *np.max(points, axis=0).tolist()]
                    add(f"mesh_target:{mesh_id}:{rule['id']}:face:{index}", "mesh_refinement_target", rule["id"],
                        format, bounds, {**config, "color":"#9333ea", "opacity":.3}, "targets",
                        refinement_id=rule["id"], source_refs=rule.get("source_refs", []), representation="imported_display_face")
            for index, shape in enumerate(rule.get("geometry", [])):
                prefix = f"mesh_target:{mesh_id}:{rule['id']}:{index}"
                kind = shape["kind"]
                if kind == "sphere":
                    center, radius = shape["center_m"], shape["radius_m"]
                    bounds = [*(x-radius for x in center), *(x+radius for x in center)]
                    format, config = "point", {"point": center, "radius_m": radius, "opacity": .15}
                elif kind == "box":
                    bounds = [*shape["min_m"], *shape["max_m"]]
                    format, config = "aabb", {"bounds": bounds, "opacity": .12}
                elif kind in {"cylinder", "arc"}:
                    if kind == "cylinder":
                        points = [shape["start_m"], shape["end_m"]]
                    else:
                        from tuba.solver.aster_mesh import _rotate_about_axis
                        points = [(np.asarray(shape["center_m"]) + _rotate_about_axis(np.asarray(shape["radial_m"]), np.asarray(shape["axis"]), shape["angle_rad"]*t)).tolist() for t in np.linspace(0,1,25)]
                    bounds = [*np.min(points, axis=0).tolist(), *np.max(points, axis=0).tolist()]
                    format, config = "polyline", {"points": points}
                else:
                    continue
                add(prefix, "mesh_refinement_target", rule["id"], format, bounds,
                    {"color": "#9333ea", **config}, "targets", refinement_id=rule["id"], source_refs=rule.get("source_refs", []))
        for location in (review.get("quality") or {}).get("problem_locations", [])[:100]:
            bounds = location.get("bounds_m")
            if not isinstance(bounds, list) or len(bounds) != 6 or not all(math.isfinite(x) for x in bounds):
                continue
            add(f"mesh_problem:{mesh_id}:{location['cell_id']}", "mesh_problem", f"Cell {location['cell_id']}", "aabb", bounds,
                {"bounds": bounds, "color": "#dc2626", "opacity": .25}, "problems",
                mesh_id=mesh_id, **location)
    return SceneContribution(objects=tuple(objects), assets=tuple(assets)), preview_layer

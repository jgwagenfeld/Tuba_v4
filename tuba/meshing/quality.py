"""Measured mesh geometry, with retained diagnostics before publication."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class MeshQualityError(ValueError):
    def __init__(self, review):
        self.mesh_review = review
        quality = review["quality"]
        super().__init__(f"{quality['invalid_count']} invalid mesh cells block publication: {quality['invalid_cell_ids'][:20]!r}; inspect the retained .quality.json diagnostic.")


def mesh_review(mesh, policy, *, gmsh=None, output_path=None):
    families, dimensions, measurements = {}, {}, {}
    volume_ids = [id for id,s in mesh.element_sources.items() if s.role=="volume_cell"]
    volume_quality = {}
    if volume_ids:
        if gmsh is None:
            raise ValueError("Solid quality requires actual Gmsh minSJ measurements.")
        tags = [mesh.element_sources[id].metadata.get("gmsh_element_tag",mesh.element_sources[id].metadata.get("solver_element_tag",int(id[2:]))) for id in volume_ids]
        volume_quality = dict(zip(volume_ids,map(float,gmsh.model.mesh.getElementQualities(tags,"minSJ"))))
        if len(volume_quality)!=len(volume_ids):
            raise ValueError("Gmsh quality count differs from the solid cell count.")
    for id,cell in mesh.elements.items():
        source = mesh.element_sources[id]
        role = source.role
        if role=="volume_cell":
            family,dimension,metric = ("HEXA20" if len(cell)==20 else "TETRA10"),3,"minSJ"
        elif role in {"volume_skin","shell_cell"}:
            family,dimension,metric = {3:("TRI3",2,"area_m2"),6:("TRI6",2,"area_m2"),8:("QUAD8",2,"area_m2")}[len(cell)]
        elif len(cell)==1:
            family,dimension,metric = "POI1",0,None
        else:
            family,dimension,metric = ("SEG3" if len(cell)==3 else "SEG2"),1,"length_m"
        families[family] = families.get(family,0)+1
        dimensions[str(dimension)] = dimensions.get(str(dimension),0)+1
        if metric is None:
            continue
        measurements.setdefault((metric,family),[]).append(id)
    metrics,invalid,poor,locations = [],[],[],[]
    for (metric,family),ids in measurements.items():
        if metric=="minSJ":
            values = np.asarray([volume_quality[id] for id in ids])
        else:
            corners = 2 if metric=="length_m" else (4 if family=="QUAD8" else 3)
            points = np.asarray([[mesh.nodes[n] for n in mesh.elements[id][:corners]] for id in ids])
            if metric=="length_m":
                values = np.linalg.norm(points[:,1]-points[:,0],axis=1)
            else:
                values = np.linalg.norm(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]),axis=1)/2
                if family=="QUAD8":
                    values += np.linalg.norm(np.cross(points[:,2]-points[:,0],points[:,3]-points[:,0]),axis=1)/2
        finite = values[np.isfinite(values)]
        threshold = .1 if metric=="minSJ" else None
        bad = np.flatnonzero(~np.isfinite(values) | (values<=0))
        low = np.flatnonzero(np.isfinite(values) & (values>0) & (values<threshold)) if threshold is not None else []
        invalid.extend(ids[i] for i in bad)
        poor.extend(ids[i] for i in low)
        for index in [*bad,*low]:
            if len(locations)<100:
                id, value = ids[index],float(values[index])
                points = np.asarray([mesh.nodes[n] for n in mesh.elements[id]])
                locations.append({"cell_id":id,"source_ref":str(mesh.element_sources[id].source_ref),"metric":metric,"value":value if np.isfinite(value) else None,
                                  "bounds_m":[*points.min(axis=0).tolist(),*points.max(axis=0).tolist()]})
        metrics.append({"metric":metric,"applicable_family":family,"minimum":float(finite.min()) if finite.size else None,
                        "quantiles":dict(zip(("p05","p50","p95"),map(float,np.quantile(finite,[.05,.5,.95])))) if finite.size else {},
                        "validity_threshold":0.,"diagnostic_threshold":threshold,"invalid_count":len(bad),"poor_count":len(low)})
    quality = {"metrics":metrics,"invalid_count":len(invalid),"poor_count":len(poor),"invalid_cell_ids":invalid,
               "poor_cell_ids":poor,"problem_locations":locations,"locations_truncated":len(invalid)+len(poor)>100,
               "interpretation":"Positive geometry is the publication gate; diagnostic thresholds are not compliance or accuracy verdicts."}
    review = {"schema":"tuba.mesh-review.v1","policy":policy.to_dict(),
              "statistics":{"node_count":len(mesh.nodes),"cell_count":len(mesh.elements),"by_family":families,"by_dimension":dimensions},
              "quality":quality,"size_preview":policy.preview()}
    if invalid:
        if output_path is not None:
            diagnostic = Path(output_path).with_suffix(".quality.json")
            diagnostic.parent.mkdir(parents=True,exist_ok=True)
            diagnostic.write_text(json.dumps(review,indent=2,allow_nan=False),encoding="utf-8")
        raise MeshQualityError(review)
    return review

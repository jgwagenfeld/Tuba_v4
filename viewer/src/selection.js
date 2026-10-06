import { getVisibleObjectIds } from "./sceneLoader.js";
import { getInterfaceMappings } from "./interfaceMappings.js";
import { relatedSelectionIds, resolveEntityObjectId, selectionRepresentative } from "./reviewSelection.js";

export function distance(first, second) {
  if (![first, second].every((point) => Array.isArray(point) && point.length === 3 &&
    point.every((value) => typeof value === "number" && Number.isFinite(value)))) {
    throw new TypeError("Measurement requires two finite 3D points in metres.");
  }
  return Math.hypot(...first.map((value, index) => value - second[index]));
}

export function selectObject(state, objectId, options = {}) {
  objectId = selectionRepresentative(state, objectId);
  if (!state.objects.some((obj) => obj.id === objectId)) {
    return state;
  }
  const current = state.selectedObjectIds ?? [];
  const selectedObjectIds = options.additive
    ? [...current.filter((id) => id !== objectId), objectId]
    : [objectId];
  return withVisibility({ ...state, selectedObjectIds });
}

export function hideSelected(state) {
  const hidden = new Set([...(state.hiddenObjectIds ?? []), ...relatedSelectionIds(state, state.selectedObjectIds ?? [])]);
  return withVisibility({ ...state, hiddenObjectIds: [...hidden] });
}

export function isolateSelection(state) {
  return withVisibility({ ...state, isolatedObjectIds: relatedSelectionIds(state, state.selectedObjectIds ?? []) });
}

export function restoreVisibility(state) {
  return withVisibility({ ...state, hiddenObjectIds: [], isolatedObjectIds: [], sectionBox: undefined, focusSelection: false });
}

export function getPropertySections(state, objectId) {
  const obj = state.objects.find((candidate) => candidate.id === objectId);
  if (!obj) {
    return [];
  }
  const asset = state.geometryAssets.find((candidate) => candidate.id === obj.geometry_asset_id);
  const attributes = { ...(obj.metadata?.attributes ?? {}) };
  if (obj.metadata?.insulation?.id) {
    attributes.insulation = obj.metadata.insulation.id;
    attributes.insulation_material = obj.metadata.insulation.material;
    attributes.insulation_thickness_m = obj.metadata.insulation.thickness_m;
  }
  const resultRows = resultRowsForObject(state, obj);
  const clashRows = clashRowsForObject(obj);
  const issueRows = issueRowsForObject(state, obj);
  const externalRows = externalRowsForObject(obj);
  const provenanceRows = provenanceRowsForObject(obj, asset);
  const profileRows = obj.metadata?.profile ?? {};
  // Where model.py defines each property, when the studio ran it as __main__.
  const propertyLines = obj.metadata?.property_lines ?? {};
  const attributeLines = propertyLines.attributes ?? {};

  return [
    {
      id: "identity",
      title: "Identity",
      rows: compactRows({ id: obj.id, entity_ref: obj.entity_ref, kind: obj.kind, name: obj.name })
    },
    {
      id: "geometry",
      title: "Geometry",
      rows: compactRows({ geometry_asset_id: obj.geometry_asset_id, asset_format: asset?.format, bounds: asset?.bounds })
    },
    {
      id: "attributes",
      title: "Attributes",
      rows: compactRows({ section: obj.metadata?.section, material: obj.metadata?.material, ...attributes }),
      sourceLines: compactRows({
        section: propertyLines.section,
        material: propertyLines.material,
        ...attributeLines,
        // The insulation rows spell out the one assignment behind them.
        insulation_material: attributeLines.insulation,
        insulation_thickness_m: attributeLines.insulation
      })
    },
    { id: "profile", title: "Profile", rows: compactRows(profileRows), sourceLine: propertyLines.section },
    { id: "physical", title: "Physical", rows: compactRows(obj.physical ?? {}) },
    { id: "quantities", title: "Quantities", rows: compactRows(obj.quantities ?? {}) },
    { id: "imported_geometry", title: "Imported geometry", rows: compactRows(importedGeometryRows(obj, asset)) },
    { id: "meshing", title: "Meshing", rows: compactRows(importedMeshingRows(obj, asset)) },
    { id: "structural_integration", title: "Structural integration", rows: compactRows(importedIntegrationRows(obj)) },
    ...getInterfaceMappings(state, objectId).map(mapping => ({
      id: `interface_mapping:${mapping.id}`, title: mapping.name ?? "Interface mapping",
      rows: compactRows({
        "Model coupling": mapping.metadata?.model_mapping,
        Interface: mapping.metadata?.interface_mapping,
        Source: mapping.metadata?.source_ref, Target: mapping.metadata?.target_ref,
        Method: mapping.metadata?.method,
        Status: mapping.metadata?.status === "meshed" ? "Resolved mesh group" : "Authored footprint; mesh membership unresolved",
        "Target geometry": mapping.metadata?.target_geometry_available === false ? "Unavailable; selected surface cannot be highlighted" : undefined,
        "Face group": mapping.metadata?.face_group, "Node group": mapping.metadata?.node_group,
        "Mapped cells": mapping.metadata?.status === "meshed" && Array.isArray(mapping.metadata.element_ids) ? mapping.metadata.element_ids.length : undefined,
        "Mapped nodes": mapping.metadata?.status === "meshed" && Array.isArray(mapping.metadata.node_ids) ? mapping.metadata.node_ids.length : undefined,
        "Attached restraints": mapping.metadata?.attachments?.map(link => `${link.id}: held ${(link.held_dof ?? []).join(", ") || "none"}; released ${(link.released_dof ?? []).join(", ") || "none"}; ${link.attachment_mode}`).join("; ")
      })
    })),
    { id: "connections", title: "Connection", rows: compactRows(connectionRows(obj)) },
    { id: "node_attachment", title: "Node attachment", rows: compactRows(attachmentRows(obj)) },
    { id: "result_values", title: "Result Values", rows: compactRows(resultRows) },
    { id: "clash", title: "Clash", rows: compactRows(clashRows) },
    { id: "issues", title: "Issues", rows: compactRows(issueRows) },
    { id: "external_refs", title: "External Refs", rows: compactRows(externalRows) },
    { id: "ifc", title: "IFC reference", rows: compactRows({
      guid: obj.source?.ifc_guid,
      class: obj.metadata?.ifc_class,
      reference: obj.source?.reference_id,
      ...Object.fromEntries(Object.entries(obj.metadata?.properties ?? {}).flatMap(([set, values]) =>
        Object.entries(values ?? {}).map(([name, value]) => [`${set}.${name}`, String(value)])))
    }) },
    { id: "provenance", title: "Provenance", rows: compactRows(provenanceRows) }
  ].filter((section) => Object.keys(section.rows).length > 0);
}

function importedMeshingRows(obj, asset) {
  if (obj.kind !== "imported_component") return {};
  const data = obj.metadata ?? {};
  const cad = data.cad_asset ?? {};
  const surface = cad.metadata ?? {};
  const regions = data.analysis_regions ?? [];
  const format = cad.source_format?.toUpperCase();
  const hasSourceSurface = data.geometry_representation !== "bounds_envelope";
  return {
    "Display mesh": data.geometry_representation === "bounds_envelope" ? "Bounds envelope; source surface unavailable"
      : format === "STL" ? "STL source triangles" : ["STEP", "STP"].includes(format) ? "STEP display tessellation" : "Source surface triangulation",
    "Source vertices": hasSourceSurface ? surface.mesh_vertices_local?.length ?? asset?.generation_config?.vertices?.length : undefined,
    "Source triangles": hasSourceSurface ? surface.mesh_faces?.length ?? asset?.generation_config?.faces?.length : undefined,
    "Solver mesh": regions.length ? "Separate analysis artifact; source triangles are not the solver FE mesh" : "No structural FE mesh defined",
    ...Object.fromEntries(regions.flatMap((region, index) => {
      const name = region.id ?? `Region ${index + 1}`;
      return [[`${name} material`, region.material], [`${name} modelisation`, region.code_aster_modelisation],
        [`${name} element order`, region.element_order], [`${name} mesh group`, region.mesh_group],
        [`${name} requested size (m)`, region.metadata?.mesh_size]];
    })),
    "Requested size (m)": regions.length ? surface.mesh_size : undefined,
    "Interface sizes (m)": regions.length && Object.keys(surface.interface_mesh_sizes ?? {}).length ? surface.interface_mesh_sizes : undefined
  };
}

function importedIntegrationRows(obj) {
  if (obj.kind !== "imported_component") return {};
  const data = obj.metadata ?? {};
  const regions = data.analysis_regions ?? [];
  const ports = data.ports ?? [];
  const couplings = data.couplings ?? [];
  return {
    Stiffness: regions.length ? `Defined by ${regions.map(region => region.id ?? region.code_aster_modelisation ?? region.role).join(", ")}` : "No structural stiffness; no analysis region assigned",
    Ports: ports.length ? `${ports.length} ports: ${ports.filter(port => port.status === "confirmed").length} confirmed; ${ports.filter(port => port.status !== "confirmed").length} candidates` : "0 ports defined",
    Connections: couplings.length ? couplings.map(coupling => `${coupling.id}: ${coupling.source ?? coupling.source_node ?? ""} → ${coupling.target ?? ""} (${coupling.code_aster_option ?? coupling.kind ?? ""})`).join("; ") : "0 structural couplings defined",
    "Connection rule": "Only authored couplings connect structural members; touching geometry does not create a connection"
  };
}

export function getGeometryRelations(state, objectId) {
  const objects = state.objects ?? [];
  const object = objects.find(candidate => candidate.id === objectId);
  if (!object) return [];
  const mappings = getInterfaceMappings(state, objectId);
  if (object.kind === "interface_mapping") {
    const refs = [object.metadata?.source_ref, object.metadata?.target_ref,
      ...(Array.isArray(object.metadata?.owner_refs) ? object.metadata.owner_refs : [])];
    const links = new Map();
    for (const ref of refs) {
      const id = resolveEntityObjectId(state, ref);
      if (id && id !== objectId && !links.has(id)) links.set(id, { id, label: `Inspect ${ref}` });
    }
    return [...links.values()];
  }
  const mappingLinks = mappings.map(mapping => ({ id: mapping.id, label: `Mapping ${mapping.name ?? mapping.id} · ${mapping.metadata?.interface_mapping ?? ""}` }));
  if (!["imported_component", "imported_port", "mixed_coupling"].includes(object.kind)) return mappingLinks;
  const data = object.metadata ?? {};
  const ports = new Map([...(data.ports ?? []), ...objects.filter(candidate => candidate.kind === "imported_port").map(candidate => candidate.metadata ?? {})].map(port => [port.id, port]));
  const couplings = new Map([...(data.couplings ?? []), ...objects.filter(candidate => candidate.kind === "mixed_coupling").map(candidate => candidate.metadata ?? {})].map(coupling => [coupling.id, coupling]));
  const links = new Map(mappingLinks.map(link => [link.id, link]));
  function add(ref, label) {
    const id = resolveEntityObjectId(state, ref);
    if (id && id !== objectId && !links.has(id)) links.set(id, { id, label });
  }
  function refLabel(ref) {
    return typeof ref === "string" ? ref.slice(ref.indexOf(":") + 1) : "";
  }
  function addCoupling(coupling) {
    const target = typeof coupling.target === "string" ? coupling.target : "";
    add(`coupling:${coupling.id}`, `Connection ${coupling.id}`);
    add(coupling.source_node, `Reference node ${refLabel(coupling.source_node)}`);
    add(coupling.source, `Source member ${refLabel(coupling.source)}`);
    add(target, `Target ${target}`);
    const port = target.startsWith("port:") ? ports.get(target.slice(5)) : null;
    if (port) add(port.owner, `Component ${refLabel(port.owner)}`);
    for (const support of coupling.attachments ?? []) {
      add(`support:${support.id}`, `Support ${support.id}`);
      add(`node:${support.attached_to}`, `Attached node ${support.attached_to}`);
    }
  }
  if (object.kind === "mixed_coupling") addCoupling(data);
  else if (object.kind === "imported_port") {
    add(data.owner, `Component ${refLabel(data.owner)}`);
    const ref = object.entity_ref ?? `port:${data.id}`;
    for (const coupling of couplings.values()) if (coupling.target === ref) addCoupling(coupling);
  } else {
    const ref = object.entity_ref ?? `component:${data.id}`;
    const ownedPortIds = new Set((data.ports ?? []).map(port => port.id));
    for (const port of ports.values()) if (port.owner === ref || ownedPortIds.has(port.id)) {
      ownedPortIds.add(port.id);
      add(`port:${port.id}`, `Port ${port.id} · ${port.status ?? "unreviewed"}`);
    }
    const ownedCouplingIds = new Set((data.couplings ?? []).map(coupling => coupling.id));
    for (const coupling of couplings.values()) if (ownedCouplingIds.has(coupling.id) || coupling.target === ref ||
      typeof coupling.target === "string" && coupling.target.startsWith("port:") && ownedPortIds.has(coupling.target.slice(5))) addCoupling(coupling);
  }
  return [...links.values()];
}

function importedGeometryRows(obj, asset) {
  if (obj.kind !== "imported_component") return {};
  const data = obj.metadata ?? {};
  const cad = data.cad_asset ?? {};
  const regions = data.analysis_regions ?? [];
  const surface = cad.metadata ?? {};
  return {
    role: regions.length ? `Analysis geometry: ${regions.map(region => region.code_aster_modelisation || region.role).join(", ")}` : data.role === "reference" ? "Reference geometry" : "Review geometry; no analysis region",
    status: data.status,
    source_file: cad.source_path,
    source_format: cad.source_format,
    clearance_coverage: cad.source_format?.toUpperCase() === "STL" ? "Native straight pipe/frame envelopes and solver operating polylines; shell/STEP bodies and reference pairs excluded" : undefined,
    source_digest: cad.content_digest,
    scale_to_metres: cad.unit_scale_to_m,
    placement: cad.placement,
    surface: data.geometry_representation,
    placed_bounds_m: data.placed_bounds_m ?? asset?.bounds,
    source_local_bounds: surface.local_bounds,
    vertices: surface.mesh_vertices_local?.length,
    triangles: surface.mesh_faces?.length,
    ...surface.inspection,
    ports: data.ports?.map(port => `${port.id}: ${port.status} (${port.kind})`).join("; "),
    couplings: data.couplings?.map(coupling => `${coupling.id}: ${coupling.code_aster_option || coupling.kind}`).join("; ")
  };
}

function connectionRows(obj) {
  const data = obj.metadata ?? {};
  if (obj.kind === "imported_port") return {
    interface: data.id, status: data.status, owner: data.owner, kind: data.kind,
    position_m: data.position, axis: data.axis, radius_m: data.radius,
    source_local_selector: data.metadata?.face_selector,
    intent: data.status === "confirmed" ? "Confirmed interface" : "Candidate interface; confirm in Python before connecting"
  };
  if (obj.kind !== "mixed_coupling") return {};
  return {
    kind: data.kind === "rigid_patch" ? "Rigid patch to reference" : data.continuation_family === "frame" ? "Beam to solid port" : "Pipe to solid port",
    method: data.code_aster_keyword, option: data.code_aster_option,
    source: data.source, reference_node: data.source_node, target: data.target,
    selected_geometry: data.metadata,
    node_links: data.attachments?.map(link => `${link.id}: held ${link.held_dof.join(", ") || "none"}; released ${link.released_dof.join(", ") || "none"}; ${link.attachment_mode}; offset (m) ${link.offset_m.join(", ")}`).join("; ")
  };
}

function attachmentRows(obj) {
  const data = obj.metadata ?? {};
  if (!["support", "support_link"].includes(obj.kind) || !data.attached_to) return {};
  const mode = data.attachment_mode ?? "rigid_offset";
  return {
    source_node: data.node, attached_to: data.attached_to,
    blocked_dof: data.blocked_dof,
    attachment_mode: mode,
    kinematics: mode === "dof_equality" ? "Equal global held DOFs; released DOFs remain free; no offset lever terms" : "Rigid offset includes rotational lever terms"
  };
}

// `maxSpan` clamps how far the camera pulls back. Fitting a selection to its
// full bounds is right for "show me this support" and wrong for "take me to the
// hot spot": a straight pipe element can be tens of metres long, so fitting it
// lands the camera outside the model with the offending millimetre somewhere in
// the middle. The clamp keeps the target at the selection's centre and caps the
// framed volume, which is what a finding walk needs.
export function fitSelection(state, options = {}) {
  const visible = new Set(state.visibleObjectIds ?? state.objects.map(o => o.id));
  const related = relatedSelectionIds(state, state.selectedObjectIds ?? []);
  const drawn = related.filter(id => visible.has(id));
  const selected = new Set(drawn.length ? drawn : state.selectedObjectIds ?? []);
  const selectedAssetIds = new Set(
    state.objects
      .filter((obj) => selected.has(obj.id))
      .map((obj) => obj.geometry_asset_id)
      .filter(Boolean)
  );
  const bounds = state.geometryAssets
    .filter((asset) => selectedAssetIds.has(asset.id) || (asset.object_ids ?? []).some((id) => selected.has(id)))
    .map((asset) => asset.bounds)
    .filter((bounds) => Array.isArray(bounds) && bounds.length === 6);
  if (bounds.length === 0) {
    return state;
  }
  const fitted = clampBoundsToSpan(mergeBounds(bounds), Number(options.maxSpan));
  const merged = fitted ?? mergeBounds(bounds);
  const target = [
    (merged[0] + merged[3]) / 2,
    (merged[1] + merged[4]) / 2,
    (merged[2] + merged[5]) / 2
  ];
  const distance = Math.max(Math.hypot(merged[3] - merged[0], merged[4] - merged[1], merged[5] - merged[2]), 1);
  const fitRequestId = Number(state.camera?.fitRequest?.id ?? 0) + 1;
  return {
    ...state,
    camera: {
      ...state.camera,
      target,
      distance,
      fitRequest: {
        id: fitRequestId, bounds: merged, objectIds: [...selected],
        ...(Number.isFinite(Number(options.maxSpan)) && Number(options.maxSpan) > 0 ? { maxSpan: Number(options.maxSpan) } : {})
      }
    }
  };
}

// Shrinks an axis-aligned box about its own centre until no side exceeds
// `maxSpan`. A box already inside the limit is returned untouched rather than
// rebuilt, so a normal "fit selection" is bit-identical to what it was.
export function clampBoundsToSpan(bounds, maxSpan) {
  if (!Number.isFinite(maxSpan) || maxSpan <= 0) {
    return null;
  }
  const center = [0, 1, 2].map((axis) => (bounds[axis] + bounds[axis + 3]) / 2);
  const clamped = [...center, ...center];
  let changed = false;
  for (let axis = 0; axis < 3; axis += 1) {
    const size = bounds[axis + 3] - bounds[axis];
    if (size > maxSpan) {
      clamped[axis] = center[axis] - maxSpan / 2;
      clamped[axis + 3] = center[axis] + maxSpan / 2;
      changed = true;
    }
  }
  return changed ? clamped : null;
}

// How close the camera should come when it is walking findings rather than
// framing a selection. A share of the scene diagonal, so the same fraction of
// the model is framed whether it is a bench or a plant, with a floor so a small
// scene does not put the lens inside the pipe it is pointing at.
export function findingFitSpan(state, fraction = 0.15, floor = 0.5) {
  const bounds = state.bounds;
  if (!Array.isArray(bounds) || bounds.length !== 6) {
    return null;
  }
  const diagonal = Math.hypot(bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2]);
  if (!Number.isFinite(diagonal) || diagonal <= 0) {
    return null;
  }
  return Math.max(diagonal * fraction, floor);
}

// Selecting and framing in one transition. Two dispatches would render twice and
// leave the camera pointing at wherever the previous selection was for a frame.
export function focusFinding(state, objectId) {
  const selected = selectObject(state, objectId);
  if (selected === state) {
    return state;
  }
  return fitSelection(selected, { maxSpan: findingFitSpan(state) });
}

function withVisibility(state) {
  return { ...state, visibleObjectIds: getVisibleObjectIds(state) };
}

function compactRows(rows) {
  return Object.fromEntries(
    Object.entries(rows).filter(([_key, value]) => value !== undefined && value !== null && value !== "")
  );
}

function resultRowsForObject(state, obj) {
  const rows = {};
  for (const overlay of state.overlays ?? []) {
    if (!["solver_result", "result_state"].includes(overlay.kind)) {
      continue;
    }
    const data = overlay.data ?? {};
    const field = data.field || data.result_type || overlay.name || overlay.id;
    if (data.values?.[obj.id] !== undefined) {
      rows[field] = data.values[obj.id];
      if (data.unit) {
        rows[`${field}_unit`] = data.unit;
      }
    }
    if (data.element_results?.[obj.id]) {
      Object.assign(rows, data.element_results[obj.id]);
    }
  }
  return rows;
}

function clashRowsForObject(obj) {
  const metadata = obj.metadata ?? {};
  const review = metadata.review ?? {};
  const clash = metadata.clash ?? metadata.clash_metadata ?? {};
  return {
    left: metadata.left ?? clash.left ?? review.object_pair?.[0],
    right: metadata.right ?? clash.right ?? review.object_pair?.[1],
    distance_m: metadata.distance_m ?? clash.distance_m,
    penetration_m: metadata.penetration_m ?? clash.penetration_m,
    cold_distance_m: metadata.cold_distance_m ?? clash.cold_distance_m,
    operating_distance_m: metadata.operating_distance_m ?? clash.operating_distance_m,
    envelope_type: metadata.envelope_type ?? clash.envelope_type ?? review.envelope_type
  };
}

function issueRowsForObject(state, obj) {
  const issueIds = (state.issues ?? [])
    .filter((issue) =>
      (issue.object_ids ?? []).includes(obj.id) ||
      (issue.entity_refs ?? []).includes(obj.entity_ref) ||
      issue.id === obj.metadata?.issue_id
    )
    .map((issue) => issue.id);
  return { issue_ids: issueIds.join(", ") };
}

function externalRowsForObject(obj) {
  return {
    ...(obj.external_refs ?? {}),
    ...(obj.metadata?.external_refs ?? {}),
    ifc_guid: obj.ifc_guid ?? obj.metadata?.ifc_guid ?? obj.external_refs?.ifc_guid ?? obj.metadata?.external_refs?.ifc_guid
  };
}

function provenanceRowsForObject(obj, asset) {
  return {
    source_ref: obj.metadata?.source_ref ?? asset?.generation_config?.source_ref ?? asset?.generation_config?.entity_ref,
    source: obj.metadata?.source ?? asset?.generation_config?.source,
    role: obj.metadata?.role ?? asset?.generation_config?.role,
    mesh_id: obj.metadata?.mesh_id ?? obj.source?.analysis_mesh?.id ?? asset?.generation_config?.mesh_id,
    member_type: obj.source?.analysis_mesh?.member_type,
    member_id: obj.source?.analysis_mesh?.member_id
  };
}

function mergeBounds(boundsList) {
  const mins = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY];
  const maxs = [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY];
  for (const bounds of boundsList) {
    for (let i = 0; i < 3; i += 1) {
      mins[i] = Math.min(mins[i], bounds[i]);
      maxs[i] = Math.max(maxs[i], bounds[i + 3]);
    }
  }
  return [...mins, ...maxs];
}

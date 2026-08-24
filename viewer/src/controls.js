import { getVisibleObjectIds } from "./sceneLoader.js";
import { bodyIdForLayerId } from "./bodies.js";

export function buildObjectTree(state, options = {}) {
  const groupBy = options.groupBy ?? "kind";
  const groups = new Map();
  for (const obj of state.objects) {
    const value = valueForGroup(obj, groupBy, state);
    const id = `${groupBy}:${value}`;
    if (!groups.has(id)) {
      groups.set(id, { id, label: value, objectIds: [], children: [] });
    }
    groups.get(id).objectIds.push(obj.id);
  }
  return { id: "root", label: "Scene", objectIds: [], children: [...groups.values()] };
}

// The fields a reader can actually see on a result row, in the order a match in
// them is worth reporting. Search used to run over JSON.stringify(obj), which
// matched coordinates, hashes and asset ids: "1" matched almost every object and
// the row gave no clue why. A match you cannot see is not a search result.
const SEARCH_FIELDS = Object.freeze([
  { key: "name", read: (obj) => obj.name },
  { key: "entity_ref", read: (obj) => refText(obj.entity_ref) },
  { key: "id", read: (obj) => obj.id },
  { key: "kind", read: (obj) => obj.kind },
  { key: "material", read: (obj) => obj.metadata?.material },
  { key: "route", read: (obj) => obj.metadata?.route ?? obj.metadata?.attributes?.route },
  { key: "group", read: (obj) => obj.group_ids?.[0] ?? obj.metadata?.groups?.[0] ?? obj.metadata?.group },
  { key: "insulation", read: (obj) => obj.metadata?.insulation?.material ?? obj.metadata?.insulation?.id },
  // Attributes are authored labels, so their string values are nameable things a
  // reviewer looks for. Numbers are excluded: they are the coordinates and
  // thicknesses that made the old whole-object match useless.
  { key: "attribute", read: (obj) => namedAttributeText(obj.metadata?.attributes) }
]);

function namedAttributeText(attributes) {
  if (!attributes || typeof attributes !== "object") return "";
  return Object.values(attributes)
    .filter((value) => typeof value === "string")
    .join(" ");
}

function refText(ref) {
  if (typeof ref === "string") return ref;
  return ref?.kind && ref?.id ? `${ref.kind}:${ref.id}` : "";
}

/**
 * Matches ranked by which field they landed in, so a name hit outranks a
 * material hit. Each match reports the field and the offsets, so the row can
 * both highlight the substring and say what it matched when the hit landed on
 * something the row does not otherwise display.
 */
export function rankObjectMatches(state, query) {
  const needle = String(query ?? "").trim().toLowerCase();
  if (!needle) {
    return (state.objects ?? []).map((object) => ({ object, field: null, start: -1, end: -1, rank: 0 }));
  }
  const matches = [];
  for (const object of state.objects ?? []) {
    for (let rank = 0; rank < SEARCH_FIELDS.length; rank += 1) {
      const field = SEARCH_FIELDS[rank];
      const text = field.read(object);
      if (typeof text !== "string" && typeof text !== "number") continue;
      const start = String(text).toLowerCase().indexOf(needle);
      if (start < 0) continue;
      matches.push({ object, field: field.key, start, end: start + needle.length, rank });
      break;
    }
  }
  return matches.sort((left, right) => left.rank - right.rank);
}

export function searchObjects(state, query) {
  return rankObjectMatches(state, query).map((match) => match.object);
}

export function filterObjects(state, criteria = {}) {
  return state.objects.filter((obj) => {
    if (criteria.kind && obj.kind !== criteria.kind) {
      return false;
    }
    for (const [key, expected] of Object.entries(criteria.metadata ?? {})) {
      if (obj.metadata?.[key] !== expected) {
        return false;
      }
    }
    return true;
  });
}

export function filterIssues(state, criteria = {}) {
  return (state.issues ?? []).filter((issue) => {
    if (criteria.type && issue.type !== criteria.type) {
      return false;
    }
    if (criteria.status && issue.status !== criteria.status) {
      return false;
    }
    if (criteria.severity && issue.severity !== criteria.severity) {
      return false;
    }
    const review = issueReviewData(state, issue);
    if (criteria.loadCase && review.load_case !== criteria.loadCase) {
      return false;
    }
    if (criteria.operatingOnly && !isOperatingOnlyIssue(review)) {
      return false;
    }
    return true;
  });
}

export function groupIssues(state, criteria = {}) {
  const groups = new Map();
  for (const issue of filterIssues(state, criteria)) {
    const review = issueReviewData(state, issue);
    const severity = issue.severity || "info";
    const loadCase = review.load_case || "no_load_case";
    const status = state.issueReviewState?.[issue.id]?.status || issue.status || "open";
    const id = `${severity}:${loadCase}:${status}`;
    if (!groups.has(id)) {
      groups.set(id, { id, severity, loadCase, status, issues: [] });
    }
    groups.get(id).issues.push(issue);
  }
  return [...groups.values()];
}

export function setOverlayVisibility(state, overlayId, visible) {
  const overlays = (state.overlays ?? []).map((overlay) =>
    overlay.id === overlayId ? { ...overlay, visible } : overlay
  );
  const visibleOverlayIds = overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id);
  return withVisibility({ ...state, overlays, visibleOverlayIds });
}

export function setRuntimeState(state, overlayId, timestamp) {
  const overlay = (state.overlays ?? []).find((candidate) => candidate.id === overlayId);
  if (!overlay || overlay.kind !== "runtime_state") {
    return state;
  }
  const objectStates = overlay.data?.states?.[timestamp] ?? {};
  return {
    ...state,
    activeRuntimeState: {
      overlayId,
      timestamp,
      objectStates
    }
  };
}

export function focusIssue(state, issueId) {
  const issue = (state.issues ?? []).find((candidate) => candidate.id === issueId);
  if (!issue) {
    return state;
  }
  const view = (state.views ?? []).find((candidate) => candidate.id === issue.view_id || candidate.issue_id === issue.id);
  const selectedObjectIds = view?.selected_object_ids?.length
    ? [...view.selected_object_ids]
    : objectIdsForIssue(state, issue);
  const activeOverlayIds = view?.active_overlay_ids?.length
    ? [...view.active_overlay_ids]
    : overlaysForIssue(state, issue.id).map((overlay) => overlay.id);
  return withVisibility({
    ...state,
    activeIssueId: issue.id,
    activeOverlayIds,
    selectedObjectIds,
    camera: view?.camera ?? state.camera,
    sectionBox: view?.section_box ?? state.sectionBox
  });
}

export function getIssueSummary(state, issueId) {
  const issue = (state.issues ?? []).find((candidate) => candidate.id === issueId);
  if (!issue) {
    return null;
  }
  const relatedObjects = objectIdsForIssue(state, issue)
    .map((objectId) => state.objects.find((obj) => obj.id === objectId))
    .filter(Boolean)
    .filter((obj) => obj.kind !== "clash_marker");
  return {
    id: issue.id,
    type: issue.type,
    title: issue.title,
    severity: issue.severity,
    status: state.issueReviewState?.[issue.id]?.status || issue.status,
    comment: state.issueReviewState?.[issue.id]?.comment || "",
    bcf: issue.external_refs?.bcf ?? null,
    review: issueReviewData(state, issue),
    relatedObjects
  };
}

export function measureDistanceBetweenObjects(state, fromId, toId) {
  const from = centerForObject(state, fromId);
  const to = centerForObject(state, toId);
  const distance = Math.hypot(from[0] - to[0], from[1] - to[1], from[2] - to[2]);
  return { from: fromId, to: toId, distance_m: round(distance), unit: "m" };
}

export function applySectionBox(state, sectionBox) {
  return withVisibility({ ...state, sectionBox });
}

export function sectionBoxDefaults(bounds) {
  const scale = Math.max(1, ...bounds.map((value) => Math.abs(Number(value))));
  const padding = scale * 0.000001;
  const min = bounds.slice(0, 3).map(Number);
  const max = bounds.slice(3, 6).map(Number);
  for (let index = 0; index < 3; index += 1) {
    if (min[index] === max[index]) {
      min[index] -= padding;
      max[index] += padding;
    }
  }
  return { min, max };
}

export function saveViewState(state, name) {
  return {
    id: `view:${slug(name)}`,
    name,
    camera: state.camera,
    selectedObjectIds: [...(state.selectedObjectIds ?? [])],
    hiddenObjectIds: [...(state.hiddenObjectIds ?? [])],
    isolatedObjectIds: [...(state.isolatedObjectIds ?? [])],
    sectionBox: state.sectionBox,
    visibleLayers: Object.fromEntries(Object.entries(state.layers).map(([id, layer]) => [id, layer.visible]))
  };
}

export function restoreViewState(state, view) {
  const layers = { ...state.layers };
  for (const [id, visible] of Object.entries(view.visibleLayers ?? {})) {
    if (layers[id]) {
      layers[id] = { ...layers[id], visible };
    }
  }
  return withVisibility({
    ...state,
    camera: view.camera ?? state.camera,
    selectedObjectIds: [...(view.selectedObjectIds ?? [])],
    hiddenObjectIds: [...(view.hiddenObjectIds ?? [])],
    isolatedObjectIds: [...(view.isolatedObjectIds ?? [])],
    sectionBox: view.sectionBox,
    layers
  });
}

function withVisibility(state) {
  return { ...state, visibleObjectIds: getVisibleObjectIds(state) };
}

function valueForGroup(obj, groupBy, state) {
  if (groupBy === "body") {
    // The finder's default axis. Vectors, clash markers and proposals belong to
    // no composited body, so they get a named bucket rather than vanishing -
    // three e2e scenarios reach for exactly those objects.
    for (const layerId of state?.objectLayerIds?.[obj.id] ?? []) {
      const bodyId = bodyIdForLayerId(layerId, state?.layers?.[layerId]?.category);
      if (bodyId) return bodyId;
    }
    return "other";
  }
  if (groupBy === "kind") {
    return obj.kind || "object";
  }
  if (groupBy === "material") {
    return obj.metadata?.material || "unassigned";
  }
  if (groupBy === "route") {
    return obj.metadata?.route || obj.metadata?.attributes?.route || "unassigned";
  }
  if (groupBy === "group") {
    return obj.group_ids?.[0] || obj.metadata?.groups?.[0] || obj.metadata?.group || "unassigned";
  }
  if (groupBy === "source") {
    return obj.source?.analysis_mesh?.id || obj.source?.model?.id || obj.metadata?.source || obj.metadata?.source_ref || "model";
  }
  return obj[groupBy] || obj.metadata?.[groupBy] || "unassigned";
}

function centerForObject(state, objectId) {
  const asset = assetForObject(state, objectId);
  if (!asset?.bounds || asset.bounds.length !== 6) {
    return [0, 0, 0];
  }
  return [
    (asset.bounds[0] + asset.bounds[3]) / 2,
    (asset.bounds[1] + asset.bounds[4]) / 2,
    (asset.bounds[2] + asset.bounds[5]) / 2
  ];
}

function assetForObject(state, objectId) {
  return state.geometryAssets.find((asset) => (asset.object_ids ?? []).includes(objectId));
}

function objectIdsForIssue(state, issue) {
  const objectIds = new Set();
  for (const objectId of issue.object_ids ?? []) {
    objectIds.add(objectId);
  }
  for (const ref of issue.entity_refs ?? []) {
    const obj = state.objects.find((candidate) => candidate.entity_ref === ref);
    if (obj) {
      objectIds.add(obj.id);
    }
  }
  for (const overlay of overlaysForIssue(state, issue.id)) {
    for (const objectId of overlay.object_ids ?? []) {
      objectIds.add(objectId);
    }
  }
  return [...objectIds];
}

function overlaysForIssue(state, issueId) {
  return (state.overlays ?? []).filter((overlay) => (overlay.data?.issue_ids ?? []).includes(issueId));
}

function issueReviewData(state, issue) {
  const marker = (state.objects ?? []).find(
    (obj) => obj.kind === "clash_marker" && (obj.metadata?.issue_id === issue.id || obj.entity_ref === issue.id || obj.entity_ref === `issue:${issue.id}`)
  );
  const markerMetadata = marker?.metadata ?? {};
  const markerReview = markerMetadata.review ?? {};
  const markerClash = markerMetadata.clash ?? markerMetadata.clash_metadata ?? {};
  return {
    ...(issue.metadata ?? {}),
    ...markerClash,
    ...markerReview,
    cold_distance_m: issue.metadata?.cold_distance_m ?? markerMetadata.cold_distance_m ?? markerClash.cold_distance_m ?? markerReview.cold_distance_m,
    operating_distance_m: issue.metadata?.operating_distance_m ?? markerMetadata.operating_distance_m ?? markerClash.operating_distance_m ?? markerReview.operating_distance_m,
    penetration_m: issue.metadata?.penetration_m ?? markerMetadata.penetration_m ?? markerClash.penetration_m ?? markerReview.penetration_m,
    envelope_type: issue.metadata?.envelope_type ?? markerMetadata.envelope_type ?? markerClash.envelope_type ?? markerReview.envelope_type,
    load_case: issue.metadata?.load_case ?? markerMetadata.load_case ?? markerClash.load_case ?? markerReview.load_case,
    introduced_by_deformation: Boolean(
      issue.metadata?.introduced_by_deformation ??
        markerMetadata.introduced_by_deformation ??
        markerClash.introduced_by_deformation ??
        markerReview.introduced_by_deformation
    )
  };
}

function isOperatingOnlyIssue(review) {
  return Boolean(
    review.introduced_by_deformation ||
      review.operating_only ||
      (review.operating_distance_m !== undefined &&
        review.cold_distance_m !== undefined &&
        Number(review.operating_distance_m) < Number(review.cold_distance_m))
  );
}

function round(value) {
  return Math.round(value * 1_000_000_000) / 1_000_000_000;
}

function slug(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

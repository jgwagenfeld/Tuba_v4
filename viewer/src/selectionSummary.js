// The Selected Evidence panel, as a description rather than a row dump.
//
// getPropertySections answers "what keys does this object carry". That is the
// wrong first question for a reviewer: selecting a support opened with nine
// rows, five of which spelled support_0 with a different prefix, and not one of
// them said what the support does. _build_support_object has carried
// support_type, node, direction, stiffness, blocked_dof, gap and friction all
// along - the Attributes section just never looked at them.
//
// So this leads with a sentence, then the restraint, then the measured facts,
// and folds the ids away at the bottom. The ids that survive folding are the
// ones nothing else derives: the object id and the geometry asset id are both
// `<prefix>:<entity_ref>`, so the ref is carried once and the two derived
// spellings are dropped.

import { contactRecords } from "./contactReview.js";
import { getActiveResultState } from "./resultReview.js";
import { getPropertySections } from "./selection.js";
import { DOF_AXES, supportDofStates } from "./supports.js";
import { displayUnit, formatNumber, formatQuantity, getUnitSystem, toDisplay } from "./units.js";

const SUPPORT_TITLES = Object.freeze({
  anchor: "Anchor",
  guide: "Guide",
  hanger: "Spring hanger",
  rest: "Rest",
  spring: "Spring hanger"
});

const KIND_TITLES = Object.freeze({
  analysis_mesh_element: "Mesh element",
  analysis_mesh_node: "Mesh node",
  clash_marker: "Clash",
  displacement_vector: "Displacement",
  obstacle: "Obstacle",
  pipe: "Pipe",
  reaction_vector: "Reaction",
  route_candidate: "Route candidate",
  support: "Support"
});

// Identity, Geometry and Provenance are the sections the panel used to open
// with. They are not deleted - they fold into Reference, shut by default.
const FOLDED_SECTIONS = new Set(["identity", "geometry", "provenance"]);

const MICRO = "µ";
const MIDDOT = "·";
const EMDASH = "—";

function titleCase(text) {
  const value = String(text ?? "");
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}

function compact(rows) {
  return Object.fromEntries(
    Object.entries(rows).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

function pointOf(asset) {
  const bounds = asset?.bounds;
  if (!Array.isArray(bounds) || bounds.length !== 6) return null;
  const point = [0, 1, 2].map((index) => (Number(bounds[index]) + Number(bounds[index + 3])) / 2);
  return point.every(Number.isFinite) ? point : null;
}

// A bundle may carry the support's keys on the object, on the asset, or both,
// and they agree - _build_support_object writes the same dict into each.
function supportConfig(obj, asset) {
  return { ...(asset?.generation_config ?? {}), ...(obj.metadata ?? {}) };
}

function componentsOf(source, key) {
  const raw = source?.[key];
  if (!Array.isArray(raw) || raw.length !== 3) return null;
  const values = raw.map(Number);
  return values.every(Number.isFinite) ? values : null;
}

function axesWith(states, wanted) {
  return DOF_AXES.filter((_axis, index) => states[index] === wanted);
}

const number = (value) => Number(value);
const positive = (value) => Number.isFinite(number(value)) && number(value) > 0;
const nonZero = (value) => Number.isFinite(number(value)) && number(value) !== 0;

function supportLede(config, states, node) {
  const at = node ? ` at node ${node}` : "";
  const fixed = axesWith(states, "fixed");
  const oneWay = axesWith(states, "one-way");
  const springs = axesWith(states, "spring");

  if (fixed.length === DOF_AXES.length) {
    return `Fixes all six degrees of freedom${at}.`;
  }
  if (oneWay.length > 0) {
    const extras = [];
    if (nonZero(config.gap)) extras.push(`${formatQuantity(config.gap, "m", "engineering")} gap`);
    if (positive(config.friction_coefficient)) {
      extras.push(`friction ${MICRO} ${formatNumber(config.friction_coefficient)}`);
    }
    const tail = extras.length > 0 ? ` ${titleCase(extras.join(", "))}.` : "";
    return `Carries compression only along ${oneWay.join(" and ")} and lifts off in tension.${tail}`;
  }
  if (springs.length > 0 && fixed.length === 0) {
    return `Spring on ${springs.join(" and ")}${at}. Carries no rigid restraint ${EMDASH} the solver adds a discrete spring element.`;
  }
  if (fixed.length === 0) {
    return `Holds no degree of freedom${at}.`;
  }
  const freeTranslations = axesWith(states, "free").filter((axis) => !axis.startsWith("R"));
  const rotationsFree = axesWith(states, "free").filter((axis) => axis.startsWith("R")).length === 3;
  const parts = [`Holds ${fixed.join(" and ")}${at}.`];
  if (freeTranslations.length > 0) {
    parts.push(`${freeTranslations.join(" and ")} ${freeTranslations.length === 1 ? "runs" : "run"} free${rotationsFree ? ", as do all three rotations" : ""}.`);
  } else if (rotationsFree) {
    parts.push("All three rotations run free.");
  }
  return parts.join(" ");
}

function definitionSection(config, state, system) {
  const lines = [];
  const push = (label, value) => lines.push({ kind: "row", label, value });

  const direction = componentsOf(config, "direction");
  if (direction) push("Direction", `[${direction.map((value) => formatNumber(value)).join(", ")}]`);

  const matrix = Array.isArray(config.stiffness_matrix) ? config.stiffness_matrix.map(Number) : [];
  matrix.forEach((value, index) => {
    if (!Number.isFinite(value) || value === 0) return;
    push(`Stiffness K${DOF_AXES[index].toLowerCase()}`, formatQuantity(value, index < 3 ? "N" : "N*m", system));
  });
  if (matrix.length === 0 && nonZero(config.stiffness)) {
    push("Stiffness", formatQuantity(config.stiffness, "N", system));
  }
  if (nonZero(config.gap)) push("Gap", formatQuantity(config.gap, "m", system));
  if (positive(config.friction_coefficient)) push("Friction", `${MICRO} ${formatNumber(config.friction_coefficient)}`);
  if (positive(config.mass)) push("Mass", `${formatNumber(config.mass)} kg`);

  const imposed = componentsOf(config, "imposed_displacement");
  if (imposed) push("Imposed displacement", imposed.map((value) => formatQuantity(value, "m", system)).join(", "));

  // Elements name their end nodes in metadata.nodes; older bundles spell them
  // n1/n2. Either way this answers "what is this support actually holding".
  const attached = (state.objects ?? [])
    .filter((candidate) => {
      const ends = candidate.metadata?.nodes ?? [candidate.metadata?.n1, candidate.metadata?.n2];
      return Array.isArray(ends) && ends.includes(config.node);
    })
    .map((candidate) => candidate.name)
    .filter(Boolean);
  if (attached.length > 0) push("Attached to", attached.join(", "));

  return lines.length > 0 ? [{ title: "Definition", lines }] : [];
}

// The vector results a node can carry, and how each one reads. Shared by the
// support panel, which pulls the reaction at its node, and by selecting the
// vector itself - moment-glyph-conventions.md requires that a selected moment
// expose Mx, My, Mz, magnitude, load case and node.
const RESULT_VECTORS = Object.freeze([
  { resultType: "reaction_force", key: "reaction_force_n", unit: "N", label: "Force", axes: ["Fx", "Fy", "Fz"] },
  { resultType: "reaction_moment", key: "reaction_moment_nm", unit: "N*m", label: "Moment", axes: ["Mx", "My", "Mz"] },
  { resultType: "displacement", key: "displacement_m", unit: "m", label: "Displacement", axes: ["Ux", "Uy", "Uz"] }
]);

// A result vector selected in its own right, rather than through its support.
function resultVectorSection(obj, asset, system) {
  const config = asset?.generation_config ?? {};
  const spec = RESULT_VECTORS.find((entry) => entry.resultType === config.result_type);
  const components = spec ? componentsOf(config, spec.key) : null;
  if (!spec || !components) return [];
  const lines = [
    { kind: "row", label: "Magnitude", value: formatQuantity(Math.hypot(...components), spec.unit, system) },
    {
      kind: "row",
      label: spec.axes.join(" / "),
      value: `${components.map((value) => formatNumber(toDisplay(value, spec.unit, system))).join(" / ")} ${displayUnit(spec.unit, system)}`
    }
  ];
  if (config.node_id) lines.push({ kind: "row", label: "Node", value: config.node_id });
  if (config.load_case) lines.push({ kind: "row", label: "Load case", value: config.load_case });
  return [{ title: spec.label, lines }];
}

// What the solver reported at this node, for the result state currently on
// screen. The asset carries the components in stored SI; the panel converts
// once, through the same unit chip every other readout follows.
function reactionSection(state, node, system) {
  if (!node) return [];
  const active = getActiveResultState(state);
  const stateId = active?.overlay?.data?.result_state_id;
  const lines = [];

  for (const { resultType, key, unit, label, axes } of RESULT_VECTORS) {
    const asset = (state.geometryAssets ?? []).find((candidate) => {
      const config = candidate.generation_config ?? {};
      return config.source === "tuba.result_state" && config.result_type === resultType &&
        config.node_id === node && (!stateId || config.result_state_id === stateId);
    });
    const components = componentsOf(asset?.generation_config, key);
    if (!components) continue;
    lines.push({ kind: "row", label, value: formatQuantity(Math.hypot(...components), unit, system) });
    lines.push({
      kind: "row",
      label: axes.join(" / "),
      value: `${components.map((value) => formatNumber(toDisplay(value, unit, system))).join(" / ")} ${displayUnit(unit, system)}`
    });
  }
  if (lines.length === 0) return [];
  const caseName = active?.overlay?.data?.load_case;
  return [{ title: caseName ? `Reactions ${MIDDOT} ${caseName}` : "Reactions", lines }];
}

function contactSection(state, obj, system) {
  const entry = Object.values(contactRecords(state)).find((record) =>
    `support:${record.support_id}` === obj.entity_ref ||
    record.support_id === obj.metadata?.support_id ||
    record.support_id === obj.name);
  if (!entry) return { section: null, badge: null };
  const magnitude = (vector) => Math.hypot(...vector);
  const lines = [
    { kind: "row", label: "Status", value: entry.status },
    { kind: "row", label: "Normal force", value: formatQuantity(entry.normal_force, "N", system) },
    { kind: "row", label: "Friction limit", value: formatQuantity(entry.friction_limit, "N", system) },
    { kind: "row", label: "|Ft|", value: formatQuantity(magnitude(entry.tangential_force), "N", system) },
    ...(entry.utilization === null
      ? []
      : [{ kind: "row", label: "Utilisation", value: formatNumber(entry.utilization) }]),
    { kind: "row", label: "Slip", value: formatQuantity(magnitude(entry.slip), "m", system) }
  ];
  return { section: { title: "Contact", lines }, badge: entry.status };
}

// The design gives every selection a sentence, not just supports. These stay
// strictly derived: a fact the bundle does not carry is left out of the
// sentence rather than guessed at, which is why each clause is conditional.
function elementLede(obj, system) {
  const metadata = obj.metadata ?? {};
  const length = Number(obj.quantities?.length_m);
  const ends = Array.isArray(metadata.nodes) ? metadata.nodes : [metadata.n1, metadata.n2].filter(Boolean);
  const parts = [metadata.section, metadata.material].filter(Boolean).join(" ");
  const span = [
    Number.isFinite(length) ? formatQuantity(length, "m", system) : null,
    ends.length === 2 ? `from ${ends[0]} to ${ends[1]}` : null
  ].filter(Boolean).join(" ");
  const sentence = [parts, span].filter(Boolean).join(", ");
  return sentence ? `${sentence}.` : "";
}

function clashLede(obj, system) {
  const metadata = obj.metadata ?? {};
  const clash = metadata.clash ?? metadata.clash_metadata ?? {};
  const left = metadata.left ?? clash.left;
  const right = metadata.right ?? clash.right;
  const penetration = Number(metadata.penetration_m ?? clash.penetration_m);
  if (!left || !right) return "";
  const overlap = Number.isFinite(penetration) && penetration > 0
    ? ` by ${formatQuantity(penetration, "m", system)}`
    : "";
  return `${left} overlaps ${right}${overlap}.`;
}

export function getSelectionSummary(state, objectId) {
  const obj = (state.objects ?? []).find((candidate) => candidate.id === objectId);
  if (!obj) return null;

  const asset = (state.geometryAssets ?? []).find((candidate) => candidate.id === obj.geometry_asset_id);
  const system = getUnitSystem(state);
  const isSupport = obj.kind === "support";
  const config = isSupport ? supportConfig(obj, asset) : {};
  const node = isSupport ? config.node : undefined;
  const dofStates = isSupport ? supportDofStates(config) : null;
  const contact = isSupport ? contactSection(state, obj, system) : { section: null, badge: null };
  const point = pointOf(asset);

  // Everything getPropertySections already knows how to build, minus the three
  // sections that moved into Reference.
  const generic = getPropertySections(state, objectId)
    .filter((section) => !FOLDED_SECTIONS.has(section.id))
    .map((section) => ({
      title: section.title,
      lines: Object.entries(section.rows).map(([label, value]) => ({ kind: "row", label, value }))
    }));

  return {
    objectId: obj.id,
    title: isSupport
      ? SUPPORT_TITLES[String(config.support_type ?? "").toLowerCase()] ?? titleCase(config.support_type ?? "Support")
      : KIND_TITLES[obj.kind] ?? titleCase(obj.kind ?? "Object"),
    badge: contact.badge,
    lede: isSupport
      ? supportLede(config, dofStates, node)
      : obj.kind === "clash_marker"
        ? clashLede(obj, system)
        : elementLede(obj, system),
    meta: [
      obj.name,
      node ? `node ${node}` : null,
      point ? `${point.map((value) => formatNumber(value)).join(", ")} m` : null
    ].filter(Boolean).join(` ${MIDDOT} `),
    dofs: dofStates ? DOF_AXES.map((axis, index) => ({ axis, state: dofStates[index] })) : null,
    sections: isSupport
      ? [
          ...definitionSection(config, state, system),
          ...reactionSection(state, node, system),
          ...(contact.section ? [contact.section] : []),
          ...generic
        ]
      : [...resultVectorSection(obj, asset, system), ...generic],
    reference: compact({
      entity_ref: obj.entity_ref,
      geometry: asset?.format,
      source: obj.metadata?.source ?? asset?.generation_config?.source
    })
  };
}

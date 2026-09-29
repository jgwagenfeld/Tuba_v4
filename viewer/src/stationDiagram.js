// Where along a run does it go bad?
//
// This is the plot the piping category does not have and the FEA category cannot
// do without. Every tool in the piping benchmark reviews in 3D and in tables -
// AutoPIPE, CAESAR II, CAEPIPE and START-PROF all have no path or station plot
// at all - while ANSYS, Abaqus, COMSOL, SALOME and Code_Aster's own POST_RELEVE_T
// all treat the X-Y diagram as primary. SALOME's curve mode is the closest
// precedent: one path, every result step overlaid, one curve per component.
//
// What it answers that a 3D contour cannot: a contour says an element is hot, and
// an element can be a metre of straight pipe. A station diagram says the moment
// peaks four metres from the anchor and falls to nothing at the bend, which is
// the sentence an engineer has to write before they can size anything.
//
// It needs no new data. Element geometry assets carry their sampled centreline as
// `generation_config.points` - two points for a straight element, sixteen for a
// bend - so arc length is the polyline's own length rather than an assumption
// about bends being straight. Element objects carry `metadata.nodes`, so the run
// is a graph walk. And the stress overlay's `element_results` already holds the
// value at *both* ends of every element, which is what a structural diagram is:
// two ordinates per member, joined, against a station axis.
//
// A single selected element is a degenerate run, and is refused. One ordinate
// pair is not a diagram, and offering it would be a plot that cannot show a peak.

export const DIAGRAM_COMPONENTS = Object.freeze([
  { id: "N", label: "N — axial force", unit: "N", index: 0 },
  { id: "VY", label: "VY — shear, local y", unit: "N", index: 1 },
  { id: "VZ", label: "VZ — shear, local z", unit: "N", index: 2 },
  { id: "MT", label: "MT — torsion", unit: "N·m", index: 3 },
  { id: "MFY", label: "MFY — bending about local y", unit: "N·m", index: 4 },
  { id: "MFZ", label: "MFZ — bending about local z", unit: "N·m", index: 5 }
]);

// A run is a chain of at least DIAGRAM_MIN_ELEMENTS elements joined node to
// node. Two is the smallest that can show a peak between its ends.
export const DIAGRAM_MIN_ELEMENTS = 2;

// Group the element objects into chains.
//
// An element whose geometry is not a plain pipe member - a tee whose display
// geometry is a joined wall, a volume analysis skin, a support - is not part of
// a run. Plotting it would put a fabricated ordinate on a real station axis.
export function findRuns(state) {
  const elements = (state.objects ?? []).filter((object) => isMemberObject(state, object));
  const byNode = new Map();
  for (const element of elements) {
    for (const node of element.metadata?.nodes ?? []) {
      if (!byNode.has(node)) byNode.set(node, []);
      byNode.get(node).push(element);
    }
  }
  const unvisited = new Set(elements.map((element) => element.id));
  const runs = [];
  while (unvisited.size > 0) {
    // Start at a terminus where possible, so a run is ordered from one end to
    // the other rather than from wherever the graph walk happened to begin.
    const seedId = [...unvisited].find((id) => {
      const element = elements.find((candidate) => candidate.id === id);
      const nodes = element.metadata?.nodes ?? [];
      return nodes.some((node) => (byNode.get(node) ?? []).length < 2);
    }) ?? unvisited.values().next().value;
    const chain = walkChain(elements, byNode, seedId, unvisited);
    if (chain.length >= DIAGRAM_MIN_ELEMENTS) {
      runs.push({
        id: runId(chain),
        elementIds: chain.map((element) => element.id),
        label: runLabel(chain)
      });
    }
  }
  return runs;
}

export function runForElement(state, objectId) {
  return findRuns(state).find((run) => run.elementIds.includes(objectId)) ?? null;
}

export function isMemberObject(state, object) {
  if (object?.kind !== "pipe" && !String(object?.metadata?.element_type ?? "").startsWith("pipe")) {
    return false;
  }
  // A tee wall, a deformed skin or a volume mesh is not a station member, and a
  // "display_geometry" override says the object is standing in for something
  // that is not a single member between two nodes.
  if (object.metadata?.display_geometry) {
    return false;
  }
  const nodes = object.metadata?.nodes;
  return Array.isArray(nodes) && nodes.length === 2 && nodes.every((node) => typeof node === "string");
}

function walkChain(elements, byNode, seedId, unvisited) {
  const chain = [];
  let current = elements.find((element) => element.id === seedId) ?? null;
  // The node the walk arrived by, null on the first step. It is what tells the
  // walk which end to leave from: through the node it did not come in on, so a
  // chain goes straight through instead of doubling back over itself.
  let arrivedFrom = null;
  while (current) {
    unvisited.delete(current.id);
    chain.push(current);
    const [first, second] = current.metadata.nodes;
    const exitNode = arrivedFrom === null
      // Nothing to have arrived from. The seed sits at a terminus, so leave by
      // the *connected* end - the higher-degree node - or the walk steps out
      // into open space and every run comes back a single element long.
      ? ((byNode.get(first)?.length ?? 0) >= (byNode.get(second)?.length ?? 0) ? first : second)
      : (first === arrivedFrom ? second : first);
    const next = (byNode.get(exitNode) ?? []).find((candidate) => unvisited.has(candidate.id));
    arrivedFrom = exitNode;
    current = next ?? null;
  }
  return chain;
}

function runId(chain) {
  return `run:${chain[0].metadata.nodes[0]}->${chain[chain.length - 1].metadata.nodes[1]}`;
}

function runLabel(chain) {
  const first = chain[0].name ?? chain[0].id;
  const last = chain[chain.length - 1].name ?? chain[chain.length - 1].id;
  return first === last ? `${first} (${chain.length} elements)` : `${first} to ${last} · ${chain.length} elements`;
}

// Cumulative arc length along the run, in metres.
//
// Straight from the polyline, so a bend contributes its true arc rather than the
// straight chord between its nodes - a 90-degree bend on a 0.3 m radius is
// 0.47 m of pipe, not 0.42 m, and a diagram that used the chord would
// systematically understate every station downstream of the first bend.
export function stationAxis(state, run) {
  const points = [];
  const stations = [];
  const elementStartStations = {};
  const elementEndStations = {};
  let station = 0;
  for (const [index, elementId] of run.elementIds.entries()) {
    const element = (state.objects ?? []).find((candidate) => candidate.id === elementId);
    const polyline = centrelineOf(state, element);
    if (!polyline || polyline.length < 2) {
      return null;
    }
    if (index > 0) {
      // The chain shares a node, so the run's polyline is continuous; carrying
      // station across the join is what makes the axis monotonic.
      station = stations[stations.length - 1] ?? 0;
      points.pop();
    }
    // The first point of this element's polyline sits at its n1 end, so its
    // station is both the run's running total and this element's n1 station.
    elementStartStations[elementId] = stations.length;
    for (const [step, point] of polyline.entries()) {
      if (step > 0) {
        station += distance(points[points.length - 1], point);
      }
      points.push(point);
      stations.push(station);
    }
    // The last point sits at the n2 end. This is not start+1: a bend carries
    // sixteen segments and its n2 end is sixteen stations on, so the ordinate
    // has to come from where the element actually ended.
    elementEndStations[elementId] = stations.length - 1;
  }
  return {
    stations,
    points,
    elementStartStations,
    elementEndStations,
    totalLength: stations[stations.length - 1] ?? 0,
    // The element each station belongs to, so a hover or an ordinate can name
    // the member it came from rather than a bare distance.
    elementIds: run.elementIds
  };
}

// { series, extent, component, unit, run }
//
// One ordinate per element end. Straight lines between an element's two ends and
// across the joint to the next element, which is how a structural diagram is
// drawn: the member carries its end forces, and the jump at a node is real.
export function buildDiagram(state, run, componentId, overlay = null) {
  const component = DIAGRAM_COMPONENTS.find((candidate) => candidate.id === componentId) ?? null;
  if (!component || !run) {
    return null;
  }
  const axis = stationAxis(state, run);
  if (!axis) {
    return null;
  }
  // Defaults to the overlay the active result and load case already select, so a
  // caller plotting a run does not have to re-derive which solve it is drawing.
  const source = overlay ?? internalForceOverlay(state);
  const elementResults = source?.data?.element_results ?? {};
  const points = [];
  let missing = 0;
  for (const elementId of run.elementIds) {
    const entry = elementResults[elementId];
    // The scene publishes one six-component vector per element end, in the
    // order Code_Aster's EFGE_ELNO writes them: N, VY, VZ, MT, MFY, MFZ. The
    // component picks the ordinate out of it rather than there being a key per
    // component, so all six diagrams read the same two arrays.
    const first = entry?.forces_n1;
    const second = entry?.forces_n2;
    if (!Array.isArray(first) || !Array.isArray(second)) {
      missing += 1;
      continue;
    }
    const n1 = Number(first[component.index]);
    const n2 = Number(second[component.index]);
    if (!Number.isFinite(n1) || !Number.isFinite(n2)) {
      missing += 1;
      continue;
    }
    const start = axis.elementStartStations?.[elementId];
    const end = axis.elementEndStations?.[elementId];
    if (start === undefined || end === undefined) {
      missing += 1;
      continue;
    }
    points.push({ station: axis.stations[start], value: n1, elementId, end: "n1" });
    points.push({ station: axis.stations[end], value: n2, elementId, end: "n2" });
  }
  if (points.length < 2) {
    return null;
  }
  points.sort((left, right) => left.station - right.station);
  const values = points.map((point) => point.value);
  return {
    run,
    component,
    unit: component.unit,
    points,
    missing,
    extent: {
      station: { min: axis.stations[0], max: axis.totalLength },
      value: { min: Math.min(0, ...values), max: Math.max(0, ...values) }
    }
  };
}

export function diagramComponentsFor(state, run) {
  const overlay = internalForceOverlay(state);
  if (!overlay) {
    return [];
  }
  const present = new Set();
  for (const elementId of run?.elementIds ?? []) {
    for (const component of DIAGRAM_COMPONENTS) {
      // A diagram is a pair of ordinates, so a component is offered only when
      // both ends of this member carry it. Offering a component whose far end is
      // missing would produce a plot that stops half way along the run and looks
      // like the load vanishes there.
      const entry = overlay.data?.element_results?.[elementId];
      if (Array.isArray(entry?.forces_n1) && Array.isArray(entry?.forces_n2)) {
        present.add(component.id);
      }
    }
  }
  return DIAGRAM_COMPONENTS.filter((component) => present.has(component.id));
}

export function internalForceOverlay(state) {
  return (state.overlays ?? []).find((overlay) => {
    if (overlay.kind !== "solver_result") return false;
    if (overlay.data?.result_type !== "internal_forces") return false;
    if (state.activeResultStateId && overlay.data?.result_state_id && overlay.data.result_state_id !== state.activeResultStateId) {
      return false;
    }
    if (state.activeLoadCase && overlay.data?.load_case && overlay.data.load_case !== state.activeLoadCase) {
      return false;
    }
    return true;
  }) ?? null;
}

// The SVG, as a string. A string rather than DOM so the shape of the diagram is
// testable without a canvas - the same reason the report layer emits CSV and
// HTML from pure data.
export function diagramSvg(diagram, options = {}) {
  if (!diagram) {
    return "";
  }
  const width = Math.max(Number(options.width) || 640, 240);
  const height = Math.max(Number(options.height) || 200, 120);
  const padding = { top: 12, right: 12, bottom: 30, left: 62 };
  const plotWidth = Math.max(width - padding.left - padding.right, 1);
  const plotHeight = Math.max(height - padding.top - padding.bottom, 1);
  const { station, value } = diagram.extent;
  const stationSpan = Math.max(station.max - station.min, 1e-9);
  const valueSpan = Math.max(value.max - value.min, 1e-9);
  const x = (metres) => padding.left + ((metres - station.min) / stationSpan) * plotWidth;
  const y = (units) => padding.top + (1 - (units - value.min) / valueSpan) * plotHeight;

  const path = diagram.points
    .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.station).toFixed(2)} ${y(point.value).toFixed(2)}`)
    .join(" ");

  const ticks = valueTicks(value.min, value.max);
  const label = `${diagram.component.label} along ${diagram.run.label}. `
    + `Station ${formatStation(station.min)} to ${formatStation(station.max)} metres, `
    + `peak ${formatUnits(Math.max(Math.abs(value.min), Math.abs(value.max)), diagram.unit)}.`;

  const ordinates = diagram.points
    .map((point) => `<circle class="diagram-ordinate" cx="${x(point.station).toFixed(2)}" cy="${y(point.value).toFixed(2)}" r="2.4">`
      + `<title>${escapeXml(`${point.elementId} ${point.end} at ${formatStation(point.station)} m: ${formatUnits(point.value, diagram.unit)}`)}</title>`
      + `</circle>`)
    .join("");

  return [
    `<svg class="station-diagram" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeXml(label)}" preserveAspectRatio="none">`,
    // The zero line, because every one of these components is signed and a
    // diagram without one cannot tell a reversal from a rise.
    `<line class="diagram-zero" x1="${padding.left}" y1="${y(0).toFixed(2)}" x2="${(width - padding.right).toFixed(2)}" y2="${y(0).toFixed(2)}" />`,
    ...ticks.map((tick) => [
      `<line class="diagram-grid" x1="${padding.left}" y1="${y(tick).toFixed(2)}" x2="${(width - padding.right).toFixed(2)}" y2="${y(tick).toFixed(2)}" />`,
      `<text class="diagram-tick" x="${padding.left - 6}" y="${(y(tick) + 3).toFixed(2)}" text-anchor="end">${escapeXml(formatUnits(tick, diagram.unit))}</text>`
    ].join("")),
    `<line class="diagram-grid" x1="${padding.left}" y1="${(padding.top + plotHeight).toFixed(2)}" x2="${(width - padding.right).toFixed(2)}" y2="${(padding.top + plotHeight).toFixed(2)}" />`,
    `<path class="diagram-path" d="${path}" />`,
    ordinates,
    `<text class="diagram-axis" x="${(padding.left + plotWidth / 2).toFixed(2)}" y="${(height - 6).toFixed(2)}" text-anchor="middle">Station along run (m)</text>`,
    `</svg>`
  ].join("");
}

function valueTicks(min, max) {
  const span = max - min;
  if (!(span > 0)) {
    return [min];
  }
  const target = 4;
  const raw = span / target;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const fraction = raw / magnitude;
  const step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * magnitude;
  const ticks = [];
  for (let tick = Math.ceil(min / step) * step; tick <= max + step * 1e-9; tick += step) {
    ticks.push(Number(tick.toPrecision(12)));
  }
  return ticks.length > 0 ? ticks : [min, max];
}

// Which station belongs to one end of one element, for callers that hold only
// the axis and an element id.
export function stationIndexFor(axis, elementId, endIndex) {
  const index = endIndex === 0
    ? axis?.elementStartStations?.[elementId]
    : axis?.elementEndStations?.[elementId];
  return index === undefined ? 0 : index;
}

function centrelineOf(state, element) {
  const asset = (state.geometryAssets ?? []).find((candidate) => candidate.id === element?.geometry_asset_id);
  const points = asset?.generation_config?.points;
  if (!Array.isArray(points) || points.length < 2) {
    return null;
  }
  const cleaned = points
    .map((point) => [Number(point?.[0]), Number(point?.[1]), Number(point?.[2])])
    .filter((point) => point.every(Number.isFinite));
  return cleaned.length >= 2 ? cleaned : null;
}

function distance(left, right) {
  return Math.hypot(left[0] - right[0], left[1] - right[1], left[2] - right[2]);
}

function formatStation(metres) {
  return Number(metres.toPrecision(4)).toString();
}

function formatUnits(value, unit) {
  return `${Number(value.toPrecision(4))} ${unit}`;
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

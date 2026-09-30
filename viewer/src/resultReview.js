import { getColoringLegend, getColoringValues } from "./coloring.js";
import { colorChannelOf } from "./workflowState.js";
import { bandCountOrZero, rampRatio, withScale } from "./legendScale.js";
import { formatNumber, formatNumberSeries } from "./units.js";

export function formatPseudoTime(value) {
  return Number.isFinite(value) ? formatNumber(value) : "unavailable";
}

export function getLoadCaseOptions(state) {
  const byLoadCase = new Map();
  for (const overlay of [...(state.resultStates ?? []), ...(state.geometryStates ?? []), ...solverResultOverlays(state), ...(state.overlays ?? []).filter((item) => item.kind === "load_case")]) {
    const data = overlay.data ?? {};
    const loadCase = data.load_case;
    if (!loadCase || byLoadCase.has(loadCase)) {
      continue;
    }
    byLoadCase.set(loadCase, {
      id: loadCase,
      label: loadCase,
      resultStateId: data.result_state_id ?? data.id ?? null
    });
  }
  return [...byLoadCase.values()];
}

export function getResultStateOptions(state) {
  const resultStates = state.resultStates ?? [];
  const times = formatNumberSeries(resultStates.map((overlay) => {
    const time = overlay.data?.metadata?.pseudo_time;
    return Number.isFinite(time) ? time : NaN;
  }));
  return resultStates.map((overlay, index) => {
    const data = overlay.data ?? {};
    return {
      id: data.id ?? overlay.id,
      label: data.metadata?.stage_label ? `${data.metadata.stage_label} / ${times[index] || "unavailable"}` : overlay.name || data.load_case || data.id || overlay.id,
      loadCase: data.load_case ?? null,
      stageIndex: Number.isFinite(data.metadata?.stage_index) ? data.metadata.stage_index : null,
      stageLabel: data.metadata?.stage_label ?? null,
      pseudoTime: Number.isFinite(data.metadata?.pseudo_time) ? data.metadata.pseudo_time : null,
      overlay
    };
  });
}

// The load path, grouped the way a reviewer thinks about it. A staged run
// publishes its stages in the contact findings, and the increments carry
// stage_index anyway, so the grouping is derived either way - the flat list of
// fifty-one options was the reason a five-stage cycle read as a wall of
// identical rows.
export function getStageGroups(state) {
  const options = getResultStateOptions(state);
  const findingsRun = state.contactFindings?.primary ?? null;
  const byStage = new Map();
  for (const option of options) {
    if (option.stageIndex == null) continue;
    if (!byStage.has(option.stageIndex)) byStage.set(option.stageIndex, []);
    byStage.get(option.stageIndex).push(option);
  }
  return [...byStage.entries()]
    .sort(([left], [right]) => left - right)
    .map(([index, members]) => {
      const published = findingsRun?.stages?.find((stage) => stage.index === index) ?? null;
      return {
        index,
        label: members[members.length - 1].stageLabel ?? `Stage ${index}`,
        pseudoTime: members[members.length - 1].pseudoTime ?? null,
        // The stage's end state is the one a reviewer means by "Hot": the
        // converged result, not the first increment after the load changed.
        resultStateId: published?.result_state_id ?? members[members.length - 1].id,
        firstResultStateId: members[0].id,
        resultStateIds: members.map((member) => member.id),
        incrementCount: members.length,
        findings: (findingsRun?.findings ?? []).filter((finding) =>
          (finding.stage_indices ?? [finding.stage_index]).includes(index)
        )
      };
    });
}

export function getActiveStageIndex(state) {
  const active = getActiveResultState(state);
  return Number.isFinite(active?.stageIndex) ? active.stageIndex : null;
}

export function coherentResultContext(previousState, nextState) {
  const options = getResultStateOptions(nextState);
  if (options.length === 0) {
    const cases = getLoadCaseOptions(nextState);
    const previousCase = previousState.activeLoadCase ?? previousState.coloring?.loadCase;
    return {
      activeResultStateId: null,
      activeLoadCase: cases.find(option => option.id === previousCase)?.id ??
        nextState.activeLoadCase ?? nextState.coloring?.loadCase ?? cases[0]?.id ?? null
    };
  }
  const previous = options.find(
    (option) =>
      option.id === previousState.activeResultStateId &&
      option.loadCase === previousState.activeLoadCase
  );
  if (previous) {
    return {
      activeResultStateId: previous.id,
      activeLoadCase: previous.loadCase
    };
  }

  const next =
    options.find((option) => option.loadCase === previousState.activeLoadCase) ??
    options.find(
      (option) =>
        option.id === nextState.activeResultStateId &&
        option.loadCase === nextState.activeLoadCase
    ) ??
    options.find((option) => option.id === nextState.activeResultStateId) ??
    options.find((option) => option.loadCase === nextState.activeLoadCase) ??
    options[0] ??
    null;
  return {
    activeResultStateId: next?.id ?? null,
    activeLoadCase: next?.loadCase ?? nextState.activeLoadCase ?? null
  };
}

export function getGeometryStateOptions(state, loadCase = state.activeLoadCase ?? null) {
  return (state.geometryStates ?? []).filter((overlay) => {
    const geometryLoadCase = overlay.data?.load_case ?? null;
    const owner = overlay.data?.result_state_id;
    return !loadCase || ((!geometryLoadCase || geometryLoadCase === loadCase) &&
      (!state.activeResultStateId || !owner || owner === state.activeResultStateId));
  }).map((overlay) => {
    const data = overlay.data ?? {};
    return {
      id: data.id ?? overlay.id,
      label: geometryStateLabel(overlay),
      loadCase: data.load_case ?? null,
      purpose: data.purpose ?? null,
      stateType: data.state_type ?? null,
      visualScale: data.visual_scale ?? data.displacement_scale ?? null,
      overlay
    };
  });
}

export function geometryStateLabel(overlay) {
  const data = overlay.data ?? {};
  const scale = Number(data.visual_scale ?? data.displacement_scale);
  const label = data.state_type === "operating" && data.purpose === "engineering"
    ? "actual deformation"
    : data.state_type === "deformed" || data.purpose === "visualization"
      ? `${scale > 1 ? "exaggerated" : "displayed"} deformation${Number.isFinite(scale) && scale > 0 ? ` (${formatNumber(scale)}×)` : ""}`
      : data.state_type === "cold" ? "reference geometry" :
        (data.state_type ?? overlay.name ?? "geometry").replaceAll("_", " ");
  return data.load_case ? `${data.load_case} — ${label}` : label[0].toUpperCase() + label.slice(1);
}

export function getActiveResultState(state) {
  const options = getResultStateOptions(state);
  return (
    options.find((option) => option.id === state.activeResultStateId) ??
    options.find((option) => option.loadCase === getActiveLoadCase(state)) ??
    options[0] ??
    null
  );
}

// A contact review is one whose study said so. Inferring it from the presence of
// contact records made every review that merely rests on a shoe a contact
// review, which cost it its scalar legend, its load and reaction arrows and its
// deformed state - seven of the twelve galleries, including a plain pressurised
// line that published with no stress legend at all.
export function isContactReview(state) {
  return state.reviewFocus === "contact";
}

// The one question four surfaces used to ask for themselves: is contact, not a
// scalar field, what is describing the scene right now?
export function contactColoringActive(state) {
  return state.contactNeutral !== false && isContactReview(state);
}

export function getActiveLoadCase(state) {
  return state.activeLoadCase ?? state.resultStates?.[0]?.data?.load_case ?? solverResultOverlays(state)[0]?.data?.load_case ?? null;
}

export function getActiveLoadCaseDefinition(state) {
  const activeLoadCase = getActiveLoadCase(state);
  return (state.overlays ?? []).find(
    (overlay) => overlay.kind === "load_case" && overlay.data?.load_case === activeLoadCase
  )?.data ?? null;
}

export function getSolverResultOverlays(state, resultType = null) {
  const activeState = getActiveResultState(state);
  const activeResultStateId = state.activeResultStateId ?? activeState?.id ?? null;
  const activeLoadCase = getActiveLoadCase(state);
  return solverResultOverlays(state).filter((overlay) => {
    const data = overlay.data ?? {};
    if (resultType && data.result_type !== resultType) {
      return false;
    }
    if (activeResultStateId && data.result_state_id && data.result_state_id !== activeResultStateId) {
      return false;
    }
    if (activeLoadCase && data.load_case && data.load_case !== activeLoadCase) {
      return false;
    }
    return overlay.visible !== false;
  });
}

export function getActiveScalarOverlay(state) {
  if (contactColoringActive(state)) return null;
  // When the scene carries a field catalogue the choice is explicit. The
  // priority chain below is the legacy path for bundles written before it.
  if ((state.resultFields ?? []).length > 0) {
    return getColoringLegend(state)?.overlay ?? null;
  }
  return (
    getSolverResultOverlays(state, "tuyau_subpoints")[0] ??
    getSolverResultOverlays(state, "stress")[0] ??
    getSolverResultOverlays(state).find((overlay) => hasNumericObjectValues(overlay.data?.values)) ??
    null
  );
}

// The scale the user has set for the field the legend is describing. Kept per
// field rather than globally: comparing a stress plot against a displacement
// plot on one shared scale is how a range ends up meaningless for both, and the
// override a reviewer types for 0-500 MPa has no business following them to a
// millimetre-scale displacement field.
export function getLegendScale(state, legend) {
  const key = legend?.fieldId ?? legend?.overlay?.id ?? null;
  return {
    bands: state.legendBands ?? 0,
    rangeOverride: key ? state.legendRanges?.[key] ?? null : null
  };
}

export function getScalarLegend(state) {
  // One legend at a time: the scalar legend belongs to the results channel. On
  // the model channel the model's own legend (or the base role colour) governs.
  if (colorChannelOf(state) !== "results") return null;
  if (contactColoringActive(state)) return null;
  if ((state.resultFields ?? []).length > 0) {
    const legend = getColoringLegend(state);
    return legend
      ? withScale(
          {
            ...legend,
            colorMap: legend.overlay?.data?.legend?.color_map ?? "cividis",
            ...scaleThresholds(state)
          },
          getLegendScale(state, legend)
        )
      : null;
  }
  const overlay = getActiveScalarOverlay(state);
  if (!overlay) {
    return null;
  }
  const data = overlay.data ?? {};
  const values = numericValues(data.values);
  const range = data.legend?.range ?? data.range ?? {
    min: Math.min(...values),
    max: Math.max(...values)
  };
  return withScale(
    {
      field: data.legend?.field ?? data.field ?? data.result_type ?? overlay.name ?? overlay.id,
      unit: data.legend?.unit ?? data.unit ?? "",
      range,
      colorMap: data.legend?.color_map ?? "cividis",
      ...scaleThresholds(state),
      declaredThresholds: data.legend?.thresholds ?? {},
      overlay
    },
    getLegendScale(state, { overlay })
  );
}

function scaleThresholds(state) {
  return {
    thresholds: {
      stress_min: numberOrNull(state.resultThreshold),
      utilization_min: numberOrNull(state.utilizationThreshold)
    }
  };
}

// Which numbers the active scalar legend is actually reading. A bundle with a
// field catalogue resolves a component; one written before it carries a single
// scalar per object on the overlay itself. Three callers need that answer - the
// hotspot list, the scene's own tint and the inspector probe - and the first
// two each carried their own copy of the ternary.
export function getScalarValues(state, overlay = getActiveScalarOverlay(state)) {
  if (!overlay) {
    return {};
  }
  return (state.resultFields ?? []).length > 0 ? getColoringValues(state) : overlay.data?.values ?? {};
}

export function getHotspots(state) {
  // A hotspot is a peak in the scalar field colouring the scene, so there are
  // none while the model channel owns the colours.
  if (colorChannelOf(state) !== "results") return [];
  const overlay = getActiveScalarOverlay(state);
  if (!overlay) {
    return [];
  }
  const data = overlay.data ?? {};
  const values = getScalarValues(state, overlay);
  const hotspots = Array.isArray(data.hotspots) && data.hotspots.length > 0
    ? data.hotspots
    : Object.entries(values).map(([objectId, value]) => ({
        object_id: objectId,
        value,
        unit: data.unit
      }));
  const stressMin = numberOrNull(state.resultThreshold);
  const utilizationMin = numberOrNull(state.utilizationThreshold);
  return hotspots
    .map((hotspot) => {
      const objectId = hotspot.object_id ?? hotspot.objectId;
      const object = (state.objects ?? []).find((candidate) => candidate.id === objectId);
      const value = Number(hotspot.value ?? values[objectId]);
      const utilization = numberOrNull(hotspot.utilization ?? data.utilization_values?.[objectId]);
      return {
        objectId,
        objectName: object?.name ?? objectId,
        elementId: hotspot.element_id ?? hotspot.elementId,
        rowIndex: hotspot.row_index ?? hotspot.rowIndex,
        subpointIndex: hotspot.subpoint_index ?? hotspot.subpointIndex,
        unit: hotspot.unit ?? data.unit ?? "",
        utilization,
        value
      };
    })
    .filter((hotspot) => Number.isFinite(hotspot.value))
    .filter((hotspot) => stressMin === null || hotspot.value >= stressMin)
    .filter((hotspot) => utilizationMin === null || (hotspot.utilization ?? 0) >= utilizationMin)
    .sort((left, right) => right.value - left.value);
}

// The walk a reviewer actually performs. AutoPIPE puts the crosshairs on the
// maximum ratio and steps to the next stressed point with the cursor keys;
// CAEPIPE cycles result items on Tab. Both are keyboard-first walks over a
// worst-first list, and neither has an equivalent here - the hotspot list could
// be clicked through but nothing moved the camera or reported "3 of 47".
//
// Index is derived from the object id rather than stored, so the walk cannot
// drift out of step with a list that re-filters as thresholds are moved.
// The reference stress: the value a given fraction of the wall-point population
// exceeds.
//
// This is the cheapest honest answer to the sharpest question in the product -
// "is that 640 MPa at the shoe real, or a mesh artefact?" - and the FEA
// literature converges on it. In a linear analysis a stress singularity grows
// with every refinement, so the maximum is not a number anyone can act on, and
// the folklore workaround (read the next contour down) makes the answer depend
// on the mesh. COMSOL's percentile method is the principled replacement: define
// a reference stress exceeded in a fixed fraction of a reference volume, and
// accept the design if it is under the limit. It is reported to be insensitive
// to notch radius and element type - the two things a peak is most sensitive to
// - which is exactly what a peak is worst at.
//
// Only offered for the sub-point field, because that is the only one whose
// population reaches the viewer at all. The cell FE field's values are one
// number per element, already reduced to a maximum, so a percentile of them
// would be a percentile of maxima and would say nothing about the peak problem
// it is meant to solve.
export const REFERENCE_STRESS_FRACTIONS = Object.freeze([0.01, 0.05]);

export function getReferenceStress(state, fractions = REFERENCE_STRESS_FRACTIONS) {
  const overlay = getSolverResultOverlays(state, "tuyau_subpoints")[0];
  if (!overlay) {
    return null;
  }
  const data = overlay.data ?? {};
  const population = subpointPopulation(state, overlay);
  if (population.length === 0) {
    return null;
  }
  const sorted = [...population].sort((left, right) => left - right);
  const declaredCount = Number(data.total_count ?? sorted.length);
  return {
    unit: data.unit ?? "Pa",
    count: sorted.length,
    // The bundle declares how many sub-points Code_Aster wrote. A payload that
    // carries fewer is a truncated population, and a percentile of a truncated
    // population is a percentile of an unknown selection - so the shortfall is
    // reported rather than absorbed.
    declaredCount: Number.isFinite(declaredCount) ? declaredCount : null,
    truncated: Number.isFinite(declaredCount) && declaredCount > sorted.length,
    max: sorted[sorted.length - 1],
    min: sorted[0],
    percentiles: fractions.map((fraction) => ({
      fraction,
      value: quantile(sorted, 1 - fraction)
    }))
  };
}

// Nearest-rank quantile on an ascending population. No interpolation: the
// population is a set of measured points, not a distribution, and inventing
// values between two of them is the same smoothing mistake as interpolating a
// piecewise-constant stress field into a continuous space.
function quantile(sorted, q) {
  if (sorted.length === 0) return null;
  const rank = Math.ceil(q * sorted.length);
  const index = Math.min(Math.max(rank - 1, 0), sorted.length - 1);
  return sorted[index];
}

// The sub-point values live in the per-asset geometry payload, not the overlay:
// the manifest carries a reduced config (count, range, payload_uri) and the
// full value array is fetched alongside it, because a tuyau subpoint asset
// holds tens of thousands of glyphs and must not be inlined in scene.json.
function subpointPopulation(state, overlay) {
  const wantedStateId = overlay.data?.result_state_id ?? null;
  const values = [];
  for (const payload of state.geometryPayloads ?? []) {
    const config = payload.generation_config ?? {};
    if (!Array.isArray(config.values)) {
      continue;
    }
    // Both sides carry a result state id, so a payload belonging to another
    // step is not silently read as this one's population. A payload with no id
    // at all is taken, because a legacy bundle that omitted it is still this
    // bundle's only payload and refusing it would lose the number for nothing.
    const payloadStateId = config.result_state_id ?? null;
    if (wantedStateId && payloadStateId && payloadStateId !== wantedStateId) {
      continue;
    }
    for (const value of config.values) {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        values.push(numeric);
      }
    }
  }
  return values;
}

export function getFindings(state) {
  return getHotspots(state);
}

export function getFindingIndex(state) {
  return getFindings(state).findIndex((finding) => finding.objectId === state.activeFindingObjectId);
}

export function stepFinding(state, direction) {
  const findings = getFindings(state);
  if (findings.length === 0) {
    return null;
  }
  const current = getFindingIndex(state);
  if (current === -1) {
    return findings[direction > 0 ? 0 : findings.length - 1];
  }
  // Circular, as CAEPIPE's item cycling is: a review that stops at the end is a
  // review that has to be re-entered from the top to confirm nothing was missed.
  const next = (current + direction + findings.length) % findings.length;
  return findings[next];
}

export function getObjectScalarColor(state, objectIds, valueIds = []) {
  // Only the results channel tints by a scalar. On the model channel the model
  // colour - or the base role colour - governs, so this yields.
  if (colorChannelOf(state) !== "results") {
    return null;
  }
  const overlay = getActiveScalarOverlay(state);
  if (!overlay) {
    return null;
  }
  const ids = Array.isArray(objectIds) ? objectIds : [objectIds];
  const values = getScalarValues(state, overlay);
  const relatedValueIds = (overlay.data?.vectors ?? [])
    .filter((vector) => (vector.object_ids ?? []).some((id) => ids.includes(id)))
    .map((vector) => vector.node_id)
    .filter(Boolean);
  const found = [...ids, ...valueIds, ...relatedValueIds]
    .map((id) => Number(values[id]))
    .filter((value) => Number.isFinite(value));
  if (found.length === 0) {
    return null;
  }
  return colorForScalarValue(Math.max(...found), getScalarLegend(state));
}

// Cividis. Lightness rises monotonically end to end, so ranking two values never
// depends on hue: a greyscale print and a colour-blind reader both still read the
// scale. The sRGB blue -> yellow -> red lerp this replaces peaked in lightness at
// mid-range instead, which left its two ends 1.07:1 apart in luminance - the
// lowest and the highest stress were the same shade on paper - and collapsed to
// a near-neutral grey (chroma 27/255) around 20% of range, where tens of MPa
// looked identical. "Blue is low" survives; the top end is now the brightest
// rather than the reddest.
const SCALAR_RAMP = Object.freeze([
  0x00204c, 0x00306f, 0x39486b, 0x575d6d, 0x707173,
  0x8a8779, 0xa69d75, 0xc4b56c, 0xffea46
]);

export function colorForScalarValue(value, legend) {
  if (!legend || !Number.isFinite(value)) {
    return null;
  }
  // The ratio comes from legendScale, which is also what draws the legend
  // gradient and places its ticks. A second copy of the min/max arithmetic here
  // is how the 3D tint and the bar beside it end up describing different scales.
  const ratio = rampRatio(value, legend);
  const span = ratio * (SCALAR_RAMP.length - 1);
  const index = Math.min(Math.floor(span), SCALAR_RAMP.length - 2);
  return interpolateHex(SCALAR_RAMP[index], SCALAR_RAMP[index + 1], span - index);
}

export function getResultVectorScale(state, vectorType) {
  const fromMap = state.resultVectorScales?.[vectorType];
  if (Number.isFinite(Number(fromMap))) {
    return Math.max(Number(fromMap), 0);
  }
  return 1;
}

export function getVisualDeformationDisplayScale(state) {
  const value = Number(state.visualDeformationScale ?? 1);
  return Number.isFinite(value) && value >= 0 ? value : 1;
}

export function setActiveLoadCase(state, loadCase) {
  const results = getResultStateOptions(state).filter((candidate) => candidate.loadCase === loadCase);
  const resultState = results.find((candidate) => candidate.id === state.activeResultStateId) ?? results[0];
  const activeGeometryState = getGeometryStateOptions(state, null).find(
    (candidate) => candidate.id === state.activeGeometryStateId
  );
  const next = { ...state, activeLoadCase: loadCase ?? null, activeResultStateId: resultState?.id ?? null };
  const geometryOptions = getGeometryStateOptions(next, loadCase);
  const geometryState =
    geometryOptions.find((candidate) => candidate.id === state.activeGeometryStateId) ??
    (activeGeometryState?.purpose
      ? geometryOptions.find((candidate) => candidate.purpose === activeGeometryState.purpose)
      : null) ??
    geometryOptions[0] ??
    null;
  return {
    ...next,
    activeGeometryStateId: geometryState?.id ?? null,
    visualDeformationScale:
      geometryState?.purpose === "visualization" && geometryState.visualScale != null
        ? Number(geometryState.visualScale)
        : state.visualDeformationScale
  };
}

export function setActiveResultState(state, resultStateId) {
  const option = getResultStateOptions(state).find((candidate) => candidate.id === resultStateId);
  if (option) {
    const next = setActiveLoadCase({ ...state, activeResultStateId: option.id }, option.loadCase);
    return {
      ...next,
      visualDeformationScale: state.visualDeformationScale
    };
  }
  return {
    ...state,
    activeResultStateId: resultStateId ?? null,
    activeLoadCase: option?.loadCase ?? state.activeLoadCase ?? null
  };
}

export function setActiveGeometryState(state, geometryStateId) {
  const option = getGeometryStateOptions(state).find((candidate) => candidate.id === geometryStateId);
  if (geometryStateId && !option) return state;
  return {
    ...state,
    activeGeometryStateId: geometryStateId ?? null,
    visualDeformationScale:
      option?.purpose === "visualization" && option.visualScale != null ? Number(option.visualScale) : state.visualDeformationScale
  };
}

export function setResultThreshold(state, threshold) {
  return { ...state, resultThreshold: Math.max(Number(threshold) || 0, 0) };
}

export function setUtilizationThreshold(state, threshold) {
  return { ...state, utilizationThreshold: Math.max(Number(threshold) || 0, 0) };
}

// The field the scale belongs to. Null when there is no legend to scale, which
// is the model channel and a contact review - in both the scale would have
// nothing to describe, so the actions stay no-ops rather than storing an
// override nobody can see or clear.
export function legendScaleKey(state) {
  const legend = getScalarLegend(state);
  return legend?.fieldId ?? legend?.overlay?.id ?? null;
}

// The band count is a display preference and follows the reviewer between
// fields; only the range is per-field, because a bound typed for 0-500 MPa is
// meaningless against a millimetre-scale displacement.
export function setLegendBands(state, bands) {
  if (!legendScaleKey(state)) {
    return state;
  }
  return { ...state, legendBands: bandCountOrZero(bands) };
}

export function setLegendRange(state, range) {
  const key = legendScaleKey(state);
  if (!key) {
    return state;
  }
  const ranges = { ...(state.legendRanges ?? {}) };
  const min = Number(range?.min);
  const max = Number(range?.max);
  if (Number.isFinite(min) && Number.isFinite(max) && max > min) {
    ranges[key] = { min, max };
  } else {
    delete ranges[key];
  }
  return { ...state, legendRanges: ranges };
}

export function resetLegendScale(state) {
  const key = legendScaleKey(state);
  if (!key) {
    return state;
  }
  const ranges = { ...(state.legendRanges ?? {}) };
  delete ranges[key];
  return { ...state, legendBands: 0, legendRanges: ranges };
}

export function setActiveFinding(state, objectId) {
  return { ...state, activeFindingObjectId: objectId ?? null };
}

export function setResultVectorScale(state, vectorType, scale) {
  const value = Math.max(Number(scale) || 0, 0);
  return {
    ...state,
    resultVectorScales: {
      ...(state.resultVectorScales ?? {}),
      [vectorType]: value
    }
  };
}

export function setVisualDeformationScale(state, scale) {
  const visualStates = getGeometryStateOptions(state).filter((option) => option.purpose === "visualization");
  const visualState = visualStates.find((option) => option.overlay.data?.result_state_id === state.activeResultStateId) ??
    visualStates.find((option) => option.id === state.activeGeometryStateId) ?? visualStates[0];
  return {
    ...state,
    activeGeometryStateId: visualState?.id ?? state.activeGeometryStateId,
    visualDeformationScale: Math.max(Number(scale) || 0, 0)
  };
}

function solverResultOverlays(state) {
  return (state.overlays ?? []).filter((overlay) => overlay.kind === "solver_result");
}

function hasNumericObjectValues(values) {
  return numericValues(values).length > 0;
}

function numericValues(values) {
  return Object.values(values ?? {})
    .map(Number)
    .filter((value) => Number.isFinite(value));
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function interpolateHex(start, end, ratio) {
  const sr = (start >> 16) & 0xff;
  const sg = (start >> 8) & 0xff;
  const sb = start & 0xff;
  const er = (end >> 16) & 0xff;
  const eg = (end >> 8) & 0xff;
  const eb = end & 0xff;
  const r = Math.round(sr + (er - sr) * ratio);
  const g = Math.round(sg + (eg - sg) * ratio);
  const b = Math.round(sb + (eb - sb) * ratio);
  return (r << 16) + (g << 8) + b;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function getLoadCaseOptions(state) {
  const byLoadCase = new Map();
  for (const overlay of [...(state.resultStates ?? []), ...(state.geometryStates ?? []), ...solverResultOverlays(state)]) {
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
  return (state.resultStates ?? []).map((overlay) => {
    const data = overlay.data ?? {};
    return {
      id: data.id ?? overlay.id,
      label: overlay.name || data.load_case || data.id || overlay.id,
      loadCase: data.load_case ?? null,
      overlay
    };
  });
}

export function getGeometryStateOptions(state) {
  return (state.geometryStates ?? []).map((overlay) => {
    const data = overlay.data ?? {};
    return {
      id: data.id ?? overlay.id,
      label: overlay.name || data.id || overlay.id,
      loadCase: data.load_case ?? null,
      purpose: data.purpose ?? null,
      stateType: data.state_type ?? null,
      visualScale: data.visual_scale ?? data.displacement_scale ?? null,
      overlay
    };
  });
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

export function getActiveLoadCase(state) {
  return state.activeLoadCase ?? state.resultStates?.[0]?.data?.load_case ?? solverResultOverlays(state)[0]?.data?.load_case ?? null;
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
  return (
    getSolverResultOverlays(state, "stress")[0] ??
    getSolverResultOverlays(state).find((overlay) => hasNumericObjectValues(overlay.data?.values)) ??
    null
  );
}

export function getScalarLegend(state) {
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
  return {
    field: data.legend?.field ?? data.field ?? data.result_type ?? overlay.name ?? overlay.id,
    unit: data.legend?.unit ?? data.unit ?? "",
    range,
    colorMap: data.legend?.color_map ?? "turbo",
    thresholds: {
      ...(data.legend?.thresholds ?? {}),
      stress_min: numberOrNull(state.resultThreshold),
      utilization_min: numberOrNull(state.utilizationThreshold)
    },
    overlay
  };
}

export function getHotspots(state) {
  const overlay = getActiveScalarOverlay(state);
  if (!overlay) {
    return [];
  }
  const data = overlay.data ?? {};
  const hotspots = Array.isArray(data.hotspots) && data.hotspots.length > 0
    ? data.hotspots
    : Object.entries(data.values ?? {}).map(([objectId, value]) => ({
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
      const value = Number(hotspot.value ?? data.values?.[objectId]);
      const utilization = numberOrNull(hotspot.utilization ?? data.utilization_values?.[objectId]);
      return {
        objectId,
        objectName: object?.name ?? objectId,
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

export function getObjectScalarColor(state, objectIds) {
  const overlay = getActiveScalarOverlay(state);
  if (!overlay) {
    return null;
  }
  const ids = Array.isArray(objectIds) ? objectIds : [objectIds];
  const data = overlay.data ?? {};
  const values = data.values ?? {};
  const found = ids
    .map((id) => Number(values[id]))
    .filter((value) => Number.isFinite(value));
  if (found.length === 0) {
    return null;
  }
  return colorForScalarValue(Math.max(...found), getScalarLegend(state));
}

export function colorForScalarValue(value, legend) {
  if (!legend || !Number.isFinite(value)) {
    return null;
  }
  const min = Number(legend.range?.min ?? value);
  const max = Number(legend.range?.max ?? value);
  const ratio = clamp((value - min) / Math.max(max - min, 1e-12), 0, 1);
  if (ratio < 0.5) {
    return interpolateHex(0x2563eb, 0xfacc15, ratio / 0.5);
  }
  return interpolateHex(0xfacc15, 0xdc2626, (ratio - 0.5) / 0.5);
}

export function getResultVectorScale(state, vectorType) {
  const fromMap = state.resultVectorScales?.[vectorType];
  if (Number.isFinite(Number(fromMap))) {
    return Math.max(Number(fromMap), 0);
  }
  if (vectorType === "reaction") {
    return Math.max(Number(state.reactionVectorScale ?? 1) || 0, 0);
  }
  if (vectorType === "displacement") {
    return Math.max(Number(state.displacementVectorScale ?? 1) || 0, 0);
  }
  return 1;
}

export function getVisualDeformationDisplayScale(state) {
  const value = Number(state.visualDeformationScale ?? 1);
  return Number.isFinite(value) && value > 0 ? value : 1;
}

export function setActiveLoadCase(state, loadCase) {
  const option = getResultStateOptions(state).find((candidate) => candidate.loadCase === loadCase);
  return {
    ...state,
    activeLoadCase: loadCase ?? null,
    activeResultStateId: option?.id ?? state.activeResultStateId ?? null
  };
}

export function setActiveResultState(state, resultStateId) {
  const option = getResultStateOptions(state).find((candidate) => candidate.id === resultStateId);
  return {
    ...state,
    activeResultStateId: resultStateId ?? null,
    activeLoadCase: option?.loadCase ?? state.activeLoadCase ?? null
  };
}

export function setActiveGeometryState(state, geometryStateId) {
  const option = getGeometryStateOptions(state).find((candidate) => candidate.id === geometryStateId);
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

export function setResultVectorScale(state, vectorType, scale) {
  const value = Math.max(Number(scale) || 0, 0);
  return {
    ...state,
    resultVectorScales: {
      ...(state.resultVectorScales ?? {}),
      [vectorType]: value
    },
    ...(vectorType === "displacement" ? { displacementVectorScale: value } : {}),
    ...(vectorType === "reaction" ? { reactionVectorScale: value } : {})
  };
}

export function setVisualDeformationScale(state, scale) {
  return { ...state, visualDeformationScale: Math.max(Number(scale) || 0, 0) };
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

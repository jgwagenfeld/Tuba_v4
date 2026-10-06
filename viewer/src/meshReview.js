// Diagnostic sizing and measured mesh geometry; this panel carries no result field.
const finite = value => typeof value === "number" && Number.isFinite(value);
const number = value => finite(value) ? Number(value.toPrecision(5)).toString() : "Unavailable";
const changeNumber = value => finite(value) && value !== 0 && Math.abs(value) < .0001 ? value.toExponential(4) : number(value);
const metres = value => finite(value) ? `${number(value)} m` : "Automatic";
const statusLabel = { idle: "Ready to generate", running: "Generating", succeeded: "Mesh ready", stale: "Mesh outdated", failed: "Generation failed", cancelled: "Generation cancelled" };
const stageLabel = { preparing: "Preparing input", generating: "Generating mesh", validating: "Checking geometry" };
const measurementKey = metric => JSON.stringify([metric.quantity,metric.field,metric.component,metric.support,metric.selection,metric.aggregation,metric.unit]);
export function measurementLabel(metric) {
  if (metric.quantity === "displacement") return "Displacement · FE nodes";
  if (metric.support?.startsWith("TUYAU")) return "Von Mises · TUYAU subpoints";
  if (metric.support?.startsWith("adjacent-element")) return "Von Mises · solid surface nodes";
  if (metric.support?.startsWith("shell")) return "Von Mises · shell thickness";
  return `${metric.quantity} · ${metric.support}`;
}

export function meshReviews(state) {
  const layers = Array.isArray(state?.layers) ? state.layers : Object.values(state?.layers ?? {});
  return layers.map(layer => layer.meshIdentity ?? layer.mesh_identity ?? layer.extra?.mesh_identity)
    .filter(identity => identity?.mesh_review?.schema === "tuba.mesh-review.v1");
}

export function meshReviewViewModel(state, native = {}) {
  const identities = meshReviews(state);
  const identity = identities.find(i => i.mesh_review?.statistics) ?? identities.find(i => i.mesh_review?.size_preview) ?? identities[0];
  const review = identity?.mesh_review ?? {};
  const policy = review.policy ?? {};
  const job = native.job;
  const busy = job?.busy || job?.state === "running";
  const current = identity?.result_status === "solver_input" || !native.available || Boolean(job?.mesh_current ?? job?.current);
  const statistics = current ? review.statistics : null;
  const quality = current ? review.quality : null;
  const preview = review.size_preview ?? {};
  const comparison = native.available ? (job?.comparison_current || (job?.current && job?.mode === "convergence") ? job.comparison : null)
    : identities.map(i => i.mesh_review?.comparison).find(Boolean);
  const sizes = (preview.samples ?? []).map(sample => sample.size_m).filter(finite);
  const metricUnit = metric => metric === "length_m" ? " m" : metric === "area_m2" ? " m²" : "";
  return {
    visible: identities.length > 0 || Boolean(native.available),
    nativeActions: Boolean(native.available),
    canGenerate: Boolean(native.available && native.sourceCurrent && !native.solving && !busy && !job?.source_error),
    canCancel: Boolean(native.available && (job?.state === "running" || job?.cleanup_pending) && job?.id),
    cleanupPending: Boolean(job?.cleanup_pending),
    capabilityReason: job?.convergence_capability?.reason ?? null,
    canConverge: Boolean(native.available && native.sourceCurrent && !native.solving && !busy && !job?.source_error && job?.convergence_config && job?.convergence_capability?.supported !== false),
    convergenceConfigured: Boolean(job?.convergence_config),
    comparison,
    levels: comparison?.levels ?? (job?.mode === "convergence" ? job.levels ?? [] : []),
    generateLabel: (job?.mesh_current ?? job?.current) ? "Regenerate mesh" : "Generate mesh",
    status: job ? (job.mode === "convergence" ? `Code_Aster comparison · ${{succeeded:"ready",failed:"failed",cancelled:"cancelled",stale:"outdated",running:"running"}[job.state] ?? job.state}${job.state === "running" ? ` · ${Math.round(job.elapsed_seconds ?? 0)} s` : ""}` : `${statusLabel[job.state] ?? "Ready to generate"}${job.state === "running" ? ` · ${stageLabel[job.stage] ?? "Preparing input"} · ${Math.round(job.elapsed_seconds ?? 0)} s` : ""}`) : (statistics ? "Generated mesh" : comparison ? "Comparison ready" : "Sizing preview"),
    error: native.error ?? job?.error ?? null,
    notice: comparison ? "Completed Code_Aster mesh comparison."
      : identity?.result_status === "solver_input"
      ? "Code_Aster analysis mesh. Mesh geometry metrics are diagnostics; Review displays processed solver results."
      : "Mesh diagnostic · unsolved. Solve runs Code_Aster for engineering results.",
    surfaceNotice: identity?.display_representation === "triangulated_surface"
      ? "Surface display uses triangles; cell counts describe the actual analysis element families." : null,
    globalSize: metres(policy.global_size_m),
    invocationSize: policy.invocation_max_element_size_m == null ? null : metres(policy.invocation_max_element_size_m),
    regions: Object.entries(policy.authored_settings?.region_sizes_m ?? {}).map(([id, size]) => `${id}: ${metres(size)}`),
    refinements: (policy.refinements ?? []).map(rule => ({ ...rule, size: metres(rule.size_m),
      influence: metres(rule.influence_distance_m), transition: metres(rule.transition_distance_m),
      targetLabel: typeof rule.target === "string" ? rule.target : `${rule.target?.kind ?? "spatial"}${rule.target?.id ? `:${rule.target.id}` : rule.target?.component ? ` on ${rule.target.component}` : ""}`,
      objectIds: (state?.objects ?? []).filter(object => object.kind === "mesh_refinement_target" && object.metadata?.refinement_id === rule.id).map(object => object.id) })),
    statistics: statistics ? `${statistics.node_count} nodes · ${statistics.cell_count} cells${Object.entries(statistics.by_family ?? {}).map(([family,count]) => ` · ${count} ${family}`).join("")}` : "Unavailable until generation",
    metrics: (quality?.metrics ?? []).map(metric => ({ ...metric,
      label: `${{ minSJ: "Scaled Jacobian (minSJ)", area_m2: "Corner area", length_m: "Chord length" }[metric.metric] ?? metric.metric}${metricUnit(metric.metric) ? ` (${metricUnit(metric.metric).trim()})` : ""}`,
      values: [metric.minimum, metric.quantiles?.p05, metric.quantiles?.p50, metric.quantiles?.p95].map(changeNumber),
      threshold: metric.diagnostic_threshold == null ? "None" : number(metric.diagnostic_threshold) })),
    qualitySummary: quality ? `${quality.invalid_count} invalid · ${quality.poor_count} poor cells` : "Quality unavailable until generation",
    qualityNotice: "Measured geometry and diagnostic thresholds do not establish accuracy or compliance.",
    problems: (quality?.problem_locations ?? []).map(location => ({ ...location, objectId: `object:mesh_problem:${identity.mesh_id}:${location.cell_id}` })),
    previewNotice: preview.sampling ?? "Requested sizing is a diagnostic preview, not measured cell size.",
    previewCount: preview.sample_count ?? 0,
    pendingCount: (preview.samples ?? []).filter(sample => sample.status === "pending_cad_binding").length,
    previewRange: sizes.length ? [Math.min(...sizes), Math.max(...sizes)] : null
  };
}

// The Build "Mesh" button: the one place a mesh is both made and shown. In a
// studio the Build scene carries only a mesh a job produced, so the button
// follows that job; a published bundle ships its mesh and the button is a
// plain toggle. A blocked button names its reason in the label, not a tooltip.
export function meshToggleViewModel(meshBody, native = {}) {
  const toggle = meshBody ? { action: "toggle", label: "Mesh", pressed: meshBody.visible,
    title: meshBody.visible ? "Hide FE mesh (Alt+M)" : "Show FE mesh elements and nodes (Alt+M)" } : null;
  if (!native.available) return toggle ?? { hidden: true };
  const job = native.job;
  if (job?.state === "running" && job.mode !== "convergence") {
    return { action: "none", label: `Meshing · ${Math.round(job.elapsed_seconds ?? 0)} s`, disabled: true, busy: true,
      title: "Generating the FE mesh. Cancel it under Mesh detail." };
  }
  if (job?.mesh_current) return toggle ?? { action: "none", label: "Mesh · loading", disabled: true, busy: true, title: "Loading the generated mesh." };
  const blocked = native.solving ? ["waiting for solve", "Meshing starts once the solve finishes."]
    : job?.busy || job?.state === "running" ? ["worker busy", "Another mesh job owns the worker; see Mesh detail."]
    : !native.sourceCurrent || job?.source_error ? ["run Python first", "Run model.py (Ctrl+Enter) so the mesh matches the source."]
    : null;
  if (blocked) return { action: "none", label: `Mesh · ${blocked[0]}`, disabled: true, title: blocked[1] };
  if (job?.state === "stale") return { action: "generate", label: "Mesh · outdated", title: "The model changed since this mesh was made. Regenerate and show it (Alt+M)." };
  if (job?.state === "failed") return { action: "generate", label: "Mesh · failed, retry", title: native.error ?? job.error ?? "Mesh generation failed; see Mesh detail." };
  return { action: "generate", label: "Mesh · generate", title: "Generate the FE mesh and show it (Alt+M)" };
}

export function renderMeshReview(root, state, native = {}, actions = {}) {
  const vm = meshReviewViewModel(state, native);
  root.hidden = !vm.visible;
  root.dataset.sourceRevision = String(native.job?.loaded_source_revision ?? "");
  root.replaceChildren();
  if (!vm.visible) return;
  const document = root.ownerDocument;
  const text = (tag, content, className) => {
    const node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  };
  const button = (label, key, callback, enabled = true) => {
    const node = text("button", label);
    node.type = "button";
    node.dataset.focusKey = `mesh-${key}`;
    node.disabled = !enabled;
    node.addEventListener("click", callback);
    return node;
  };
  // Three columns read side by side in the dock: what the job did, what was
  // asked of the mesher, and what the mesher measured. A comparison spans them.
  const group = title => {
    const node = text("section", "", "mesh-review-group");
    node.append(text("h3", title));
    root.append(node);
    return node;
  };
  const job = group("Generation");
  const status = text("p", vm.status, "mesh-status");
  status.dataset.meshStatus = "";
  status.dataset.meshState = native.job?.state ?? "static";
  job.append(status, text("p", vm.notice, "mesh-notice"));
  if (vm.error) job.append(text("p", vm.error, "mesh-error"));
  if (vm.nativeActions) {
    const controls = text("div", "", "mesh-actions");
    controls.append(button(vm.generateLabel, "generate", () => actions.generate?.(Boolean(native.job?.current)), vm.canGenerate));
    controls.append(button("Run convergence", "converge", () => actions.converge?.(), vm.canConverge));
    if (vm.canCancel) controls.append(button(vm.cleanupPending ? "Retry owned cleanup" : "Cancel mesh job", "cancel", () => actions.cancel?.(native.job.id)));
    job.append(controls);
    if (!native.sourceCurrent || native.job?.source_error) job.append(text("p", "Run current Python successfully before generating.", "mesh-notice"));
    if (!vm.convergenceConfigured) job.append(text("p", "Define MESH_CONVERGENCE and one LOAD_CASES operation in study.py to compare meshes.", "mesh-notice"));
    if (vm.capabilityReason) job.append(text("p", vm.capabilityReason, "mesh-notice"));
  }
  if (vm.levels.length) {
    const wide = text("section", "", "mesh-review-wide");
    root.append(wide);
    if (vm.comparison) wide.append(text("p", `${vm.comparison.distinct_successful_meshes} distinct meshes · tolerance ${number(vm.comparison.relative_tolerance * 100)}%. Available changes: ${vm.comparison.all_available_changes_within_tolerance == null ? "no verdict" : vm.comparison.all_available_changes_within_tolerance ? "within configured tolerance" : "outside configured tolerance"}. No accuracy or compliance certificate.`, "mesh-notice"));
    const allUnavailable = vm.comparison ? (vm.levels[0]?.measurements ?? []).filter(metric => vm.levels.every(level =>
      level.measurements?.some(other => measurementKey(other) === measurementKey(metric) && other.value == null))) : [];
    const unavailableKeys = new Set(allUnavailable.map(measurementKey));
    if (allUnavailable.length) {
      const details=document.createElement("details");
      details.append(text("summary",`Unavailable across all levels (${allUnavailable.length} quantities)`));
      for (const metric of allUnavailable) details.append(text("p",`${measurementLabel(metric)}: ${metric.unavailable_reason} Field ${metric.field}/${metric.component}; ${metric.support}; ${metric.selection}; ${metric.aggregation}; ${metric.unit}.`));
      wide.append(details);
    }
    const table = document.createElement("table");
    table.className = "mesh-comparison";
    const head = document.createElement("tr");
    for (const label of ["Mesh level", "Measured maximum", "Change"]) head.append(text("th", label));
    table.append(head);
    for (const level of vm.levels) {
      const measuredItems = (level.measurements ?? []).filter(metric => !unavailableKeys.has(measurementKey(metric)));
      const items = measuredItems.length ? measuredItems : [null];
      for (const [metricIndex,metric] of items.entries()) {
        const row = document.createElement("tr");
        const change = metric ? level.changes_from_previous?.find(c => c.quantity === metric.quantity && c.support === metric.support && c.selection === metric.selection) : null;
        const measured = metric ? `${measurementLabel(metric)}: ${metric.value == null ? "Unavailable" : `${number(metric.value)} ${metric.unit}`}` : (level.error ?? "Pending solver output");
        const changed = change ? `${change.absolute_change == null ? "Unavailable" : `${changeNumber(change.absolute_change)} ${metric.unit}`} · ${change.relative_change == null ? change.reason : `${changeNumber(change.relative_change * 100)}% · ${change.within_tolerance ? "within" : "outside"} tolerance`}` : "First level";
        if (metricIndex===0) {
          const cell=text("td","");cell.rowSpan=items.length;
          cell.append(text("div",`Scale ${number(level.scale)}`),text("div",{succeeded:"Solved",failed:"Failed",running:"Running",cancelled:"Cancelled"}[level.status] ?? level.status,"mesh-level-status"));
          cell.append(text("div",level.mesh ? `${level.mesh.node_count} nodes · ${level.mesh.cell_count} cells` : "Unavailable"));
          if(level.mesh)cell.append(text("div",Object.keys(level.mesh.by_family ?? {}).join(" / ")));
          row.append(cell);
        }
        const measuredCell=text("td","");
        if (metric) {
          const definition=`Field ${metric.field}/${metric.component}; support ${metric.support}; selection ${metric.selection}; aggregation ${metric.aggregation}; unit ${metric.unit}.${metric.unavailable_reason ? ` ${metric.unavailable_reason}` : ""}`;
          const details=document.createElement("details");details.title=definition;
          details.append(text("summary",measured),text("p",definition));measuredCell.append(details);
        } else measuredCell.textContent=measured;
        row.append(measuredCell,text("td",changed));
        table.append(row);
      }
    }
    wide.append(table);
  }
  const sizing = group("Requested sizing");
  sizing.append(text("p", `Base requested size: ${vm.globalSize}`));
  if (vm.invocationSize) sizing.append(text("p", `Study sizing override: ${vm.invocationSize}`));
  for (const region of vm.regions) sizing.append(text("p", region));
  for (const rule of vm.refinements) {
    const row = text("div", "", "mesh-refinement");
    row.append(button(`${rule.id} · ${rule.targetLabel}`, `target-${rule.id}`, () => actions.selectTarget?.(rule)),
      text("span", ` ${rule.size} · influence ${rule.influence} · transition ${rule.transition}`));
    if (rule.cad_target) row.append(text("p", rule.objectIds.length
      ? "Target highlight uses the imported CAD face display. Exact sizing binds to its source face during generation."
      : "Target selects its source component; CAD face display is unavailable. Exact sizing binds during generation.", "mesh-notice"));
    sizing.append(row);
  }
  const toggles = text("div", "", "mesh-visibility");
  for (const [suffix, label] of [["targets", "Refinement targets"], ["sizing", "Requested sizing"], ["problems", "Problem cells"]]) {
    const layer = Array.isArray(state.layers) ? state.layers.find(layer => layer.id === `analysis_mesh:review:${suffix}`) : state.layers?.[`analysis_mesh:review:${suffix}`];
    if (!layer) continue;
    const control = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = layer.visible ?? layer.default_visible ?? false;
    input.dataset.focusKey = `mesh-visible-${suffix}`;
    input.addEventListener("change", () => actions.toggleLayer?.(layer.id, input.checked));
    control.append(input, document.createTextNode(label));
    toggles.append(control);
  }
  sizing.append(toggles, text("p", `${vm.previewCount} requested-size samples. ${vm.previewNotice}`, "mesh-notice"));
  if (vm.pendingCount) sizing.append(text("p", `${vm.pendingCount} samples await exact CAD face binding during generation.`));
  if (vm.previewRange) {
    const uniform = vm.previewRange[0] === vm.previewRange[1];
    const legend = text("div", "", "mesh-size-legend");
    legend.dataset.uniform = String(uniform);
    legend.append(text("strong", "Requested element size"));
    const range = text("div", "", "mesh-size-range");
    range.append(text("span", uniform ? metres(vm.previewRange[0]) : `Finer · ${metres(vm.previewRange[0])}`));
    if (!uniform) range.append(text("span", `Coarser · ${metres(vm.previewRange[1])}`));
    legend.append(range, text("p", "Colored dots are sizing samples, not FE nodes. Marker size stays fixed as you zoom.", "mesh-notice"));
    sizing.append(legend);
  }
  const quality = group("Measured quality");
  quality.append(text("p", vm.statistics, "mesh-statistics"), text("p", vm.qualitySummary));
  if (vm.surfaceNotice) quality.append(text("p", vm.surfaceNotice, "mesh-notice"));
  if (vm.metrics.length) {
    const table = document.createElement("table");
    table.className = "mesh-metrics";
    const head = document.createElement("tr");
    for (const label of ["Family", "Measure", "Min", "p05", "p50", "p95", "Threshold"]) head.append(text("th", label));
    table.append(head);
    for (const metric of vm.metrics) {
      const row = document.createElement("tr");
      row.append(text("td", metric.applicable_family), text("td", metric.label), ...metric.values.map(value => text("td", value)), text("td", metric.threshold));
      table.append(row);
    }
    quality.append(table);
  }
  for (const location of vm.problems) quality.append(button(`Locate cell ${location.cell_id}`, `problem-${location.cell_id}`, () => actions.focusProblem?.(location.objectId)));
  quality.append(text("p", vm.qualityNotice, "mesh-notice"));
}

const WORKFLOW_TABLES = Object.freeze({
  summary: Object.freeze(["project_summary", "result_summary"]),
  model: Object.freeze(["nodes", "line_list", "section_schedule", "materials", "supports"]),
  "load-cases": Object.freeze(["load_cases", "studies"]),
  results: Object.freeze(["result_summary", "displacements", "reactions", "element_forces", "fe_stress"]),
  compliance: Object.freeze(["code_compliance"]),
  diagnostics: Object.freeze(["diagnostics"])
});

export function tableIdsForWorkflow(workflowId) {
  return [...(WORKFLOW_TABLES[workflowId] ?? [])];
}

export function tableViewModel(table) {
  const columns = (table?.columns ?? []).map((column) => ({
    id: column.id,
    label: column.unit ? `${column.label} [${column.unit}]` : column.label,
    unit: column.unit ?? null,
    description: column.description ?? null
  }));
  const rows = (table?.rows ?? []).map((row) => {
    const cells = columns.map((column) => cellViewModel(column.id, row?.[column.id]));
    return {
      cells,
      entityRef: rowEntityRef(row)
    };
  });
  return {
    id: table?.id ?? "",
    title: table?.title ?? table?.id ?? "Review table",
    source: table?.source ?? "",
    columns,
    rows,
    unavailableReason: table?.unavailable_reason ?? null
  };
}

export function workflowViewModel(review, workflowId) {
  const tables = tableIdsForWorkflow(workflowId)
    .map((id) => review?.tables?.[id])
    .filter(Boolean)
    .map(tableViewModel);

  if (tables.length > 0) {
    return { workflowId, tables, unavailableReason: null };
  }

  const unavailableReason = review?.analysis_status === "not_solved" && workflowId === "results"
    ? "Analysis has not been solved."
    : workflowId === "compliance"
      ? "Code compliance is unavailable because no ComplianceReport was supplied."
      : "No review data is available for this workflow.";
  return { workflowId, tables: [], unavailableReason };
}

export function cockpitStatusViewModel(review) {
  const unavailable = "Not available";
  const table = (id) => review?.tables?.[id] ?? null;
  const compliance = table("code_compliance");
  const complianceRows = compliance?.rows ?? [];
  const governing = complianceRows.reduce((best, row) => {
    const candidate = [row.sustained_ratio, row.expansion_ratio]
      .filter((value) => value !== null && value !== undefined && value !== "")
      .map(Number)
      .filter(Number.isFinite)
      .sort((left, right) => right - left)[0];
    return candidate !== undefined && (!best || candidate > best.ratio) ? { ratio: candidate, row } : best;
  }, null);
  const diagnostics = table("diagnostics");
  const complianceComplete = complianceRows.length > 0 && complianceRows.every(
    (row) => typeof row.sustained_pass === "boolean" && typeof row.expansion_pass === "boolean"
  );
  const compliancePassed = complianceRows.every((row) => row.sustained_pass === true && row.expansion_pass === true);
  const authoritativeGoverning = complianceComplete ? governing : null;
  return {
    analysisStatus: review?.analysis_status ?? unavailable,
    complianceStatus: complianceComplete ? compliancePassed ? "Pass" : "Fail" : unavailable,
    governingLoadCase: authoritativeGoverning?.row?.load_case ?? unavailable,
    warningCount: (diagnostics?.rows ?? []).filter((row) => row.severity === "warning").length,
    governingRatio: authoritativeGoverning ? String(authoritativeGoverning.ratio) : unavailable,
    governingLocation: authoritativeGoverning?.row?.entity_ref ?? unavailable
  };
}

function cellViewModel(columnId, value) {
  if (isPassColumn(columnId) && typeof value === "boolean") {
    return { columnId, text: value ? "PASS" : "FAIL", tone: value ? "pass" : "fail" };
  }
  if (columnId === "severity") {
    const severity = plainCellString(value).toUpperCase();
    return { columnId, text: severity, tone: severity.toLowerCase() || "info" };
  }
  const cell = { columnId, text: plainCellString(value) };
  if (isEntityReferenceColumn(columnId) && typeof value === "string" && value.length > 0) {
    cell.entityRef = value;
  }
  return cell;
}

function plainCellString(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (Array.isArray(value)) {
    return value.map(plainCellString).join(", ");
  }
  if (isMapping(value)) {
    return Object.keys(value)
      .sort()
      .map((key) => `${key}: ${plainCellString(value[key])}`)
      .join("; ");
  }
  return String(value);
}

function rowEntityRef(row) {
  for (const key of ["governing_entity_ref", "entity_ref"]) {
    if (typeof row?.[key] === "string" && row[key].length > 0) {
      return row[key];
    }
  }
  return null;
}

function isEntityReferenceColumn(columnId) {
  return columnId === "entity_ref" || columnId === "governing_entity_ref";
}

function isPassColumn(columnId) {
  return columnId === "passed" || columnId === "pass" || columnId.endsWith("_pass") || columnId.endsWith("_passed");
}

function isMapping(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

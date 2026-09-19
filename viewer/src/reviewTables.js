// What produced this review, in one line: the solver, the runtime it ran on and
// how many load cases it covered. Every fact is already in the provenance
// records - one per study, mesh and result state - but the only surface that
// read them rendered a PROVENANCE_ diagnostic row per artifact inside the
// Issues task, so "which Code_Aster, over which cases" took three clicks and a
// reading of ids. Nothing is inferred: a review whose records name no solver
// gets no line rather than a guessed one.
export function solverProvenanceLabel(review) {
  const records = review?.provenance ?? [];
  const solver = records.find((record) => record.solver_name)?.solver_name;
  if (!solver) return "";
  const version = records.map((record) => record.metadata?.runtime_version).find(Boolean);
  const cases = new Set(records.map((record) => record.load_case).filter(Boolean));
  return [
    version ? `${solver} ${version}` : solver,
    cases.size > 0 ? `${cases.size} case${cases.size === 1 ? "" : "s"}` : null
  ]
    .filter(Boolean)
    .join(" · ");
}

export function cockpitStatusViewModel(review) {
  const unavailable = "Not available";
  const table = (id) => review?.tables?.[id] ?? null;
  const diagnostics = table("diagnostics");
  return {
    analysisStatus: review?.analysis_status ?? unavailable,
    warningCount: (diagnostics?.rows ?? []).filter((row) => row.severity === "warning").length
  };
}

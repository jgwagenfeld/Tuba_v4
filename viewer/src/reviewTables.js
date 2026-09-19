export function cockpitStatusViewModel(review) {
  const unavailable = "Not available";
  const table = (id) => review?.tables?.[id] ?? null;
  const diagnostics = table("diagnostics");
  return {
    analysisStatus: review?.analysis_status ?? unavailable,
    warningCount: (diagnostics?.rows ?? []).filter((row) => row.severity === "warning").length
  };
}

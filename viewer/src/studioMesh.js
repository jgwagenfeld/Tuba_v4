// Native job transport; source remains authored Python.
export function createStudioMeshClient({ fetcher = fetch, onChange = () => {} } = {}) {
  let job = null;
  let timer = null;
  let error = null;
  let requestVersion = 0;
  async function request(options, path = "/api/mesh") {
    const version = ++requestVersion;
    try {
      const response = await fetcher(path, { cache: "no-store", ...options });
      const result = await response.json();
      if (version !== requestVersion) return job;
      if (!response.ok) throw new Error(result.error ?? `Mesh request failed (HTTP ${response.status}).`);
      job = result;
      error = null;
    } catch (failure) {
      if (version !== requestVersion) return job;
      error = failure.message;
    }
    clearTimeout(timer);
    onChange({ job, error });
    if (job?.busy && !job?.cleanup_pending) timer = setTimeout(() => void refresh(), 750);
    return job;
  }
  const refresh = () => request();
  return {
    refresh,
    snapshot: () => ({ job, error }),
    generate: force => request({ method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force, expected_source_revision: job?.loaded_source_revision }) }),
    converge: () => request({ method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force: true, expected_source_revision: job?.loaded_source_revision }) }, "/api/mesh/convergence"),
    cancel: id => request({ method: "DELETE" }, `/api/mesh/${encodeURIComponent(id)}`),
    close: () => { ++requestVersion; clearTimeout(timer); }
  };
}

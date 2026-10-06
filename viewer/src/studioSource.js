// Disk tokens belong to the source we read or saved, never a rejected draft.
export const editorSource = code => code.replace(/\r\n?/g, "\n");

export async function saveStudioSource(state, code, { fetcher = fetch } = {}) {
  const response = await fetcher("/api/script", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, expected_revision: state.sourceRevision })
  });
  const result = await response.json().catch(() => ({ ok: false, error: `Studio answered ${response.status}` }));
  state.saveConflict = response.status === 409 || result.conflict === true;
  if (!state.saveConflict && typeof result.source_revision === "string") {
    state.sourceRevision = result.source_revision;
    state.diskCode = code; // A saved script can still fail Python validation.
  }
  return result;
}

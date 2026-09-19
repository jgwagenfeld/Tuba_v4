// The origin of a published review: the model script and the Code_Aster .comm
// each load case produced. A Pages bundle ships both beside its scene, so a
// reader can see what the solver was actually asked to do. A studio generates
// the same pair live and can edit it; this is the read-only, static half.

// A study provenance record carries both halves of the mapping: its
// solver_input_identity.load_case names the tab and files.comm is the path.
function commsByLoadCase(review) {
  const byLoadCase = new Map();
  const provenance = Array.isArray(review?.provenance) ? review.provenance : [];
  for (const record of provenance) {
    if (record?.kind !== "study") continue;
    const loadCase = record?.metadata?.solver_input_identity?.load_case;
    const comm = record?.files?.comm;
    if (typeof loadCase === "string" && loadCase && typeof comm === "string" && comm) {
      if (!byLoadCase.has(loadCase)) byLoadCase.set(loadCase, { name: loadCase, uri: comm });
    }
  }
  return byLoadCase;
}

export function deriveBundleSource(scene, review) {
  const scriptUri = scene?.source_uri;
  if (typeof scriptUri !== "string" || !scriptUri) return null;
  const byLoadCase = commsByLoadCase(review);
  const loadCases = [];
  // The scene lists load cases in the study's own order; provenance order is the
  // fallback for a review that predates that list.
  const identities = Array.isArray(scene?.solver_input_identities) ? scene.solver_input_identities : [];
  for (const identity of identities) {
    const entry = typeof identity?.load_case === "string" ? byLoadCase.get(identity.load_case) : null;
    if (entry && !loadCases.includes(entry)) loadCases.push(entry);
  }
  for (const entry of byLoadCase.values()) {
    if (!loadCases.includes(entry)) loadCases.push(entry);
  }
  return { scriptUri, loadCases };
}

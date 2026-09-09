export const WORKFLOW_TABS = Object.freeze([
  { id: "summary", label: "Review", requiresReview: true },
  { id: "model", label: "Model", requiresReview: true },
  { id: "load-cases", label: "Load Cases", requiresReview: true },
  { id: "results", label: "Results", requiresReview: true },
  { id: "diagnostics", label: "Issues", requiresReview: false },
  { id: "3d", label: "Display", requiresReview: false },
  { id: "compliance", label: "Compliance", requiresReview: true }
]);

// The Results task owns the coloring channel now that the permanent bar above
// the viewport is gone, so a scene carrying fields or result states must offer
// it even without a review - otherwise there is no way left to pick what
// colours the model. Both visibility lists read this: the rail must never
// offer a task setWorkflowTab will reject.
function hasResultContent({ resultFields, resultStates } = {}) {
  return (resultFields ?? []).length > 0 || (resultStates ?? []).length > 0;
}

export function getVisibleWorkflowTabs(state = {}) {
  if (state.review) return WORKFLOW_TABS.map((tab) => tab.id);
  return hasResultContent(state) ? ["model", "results", "diagnostics"] : ["model", "diagnostics"];
}

export function getVisibleCockpitTaskIds(state = {}) {
  // No Review task any more: it fronted the evidence dock, and the review's
  // tables live in the generated report the header links to. What is left in
  // the rail is what you do to the scene - model, results, issues.
  if (state.review) return ["model", "results", "diagnostics"];
  return hasResultContent(state) ? ["model", "results", "diagnostics"] : ["model", "diagnostics"];
}

export function defaultWorkflowTab({ review, embed } = {}) {
  if (embed) return "3d";
  return "model";
}

const TASK_VISIBILITY_PRESETS = Object.freeze({
  summary: { design: true, analysis_mesh: false, results: true, annotations: true },
  model: { design: true, analysis_mesh: false, results: false, annotations: false },
  results: { design: true, analysis_mesh: false, results: true, annotations: true },
  diagnostics: { design: true, analysis_mesh: false, results: false, annotations: true }
});

export function visibilityPresetForTask(taskId) {
  return Object.hasOwn(TASK_VISIBILITY_PRESETS, taskId) ? TASK_VISIBILITY_PRESETS[taskId] : null;
}

export function createWorkflowState({ review = null, embed = false } = {}) {
  return {
    review,
    embed: Boolean(embed),
    activeTab: defaultWorkflowTab({ review, embed })
  };
}

export function setWorkflowTab(state, tabId) {
  const tab = WORKFLOW_TABS.find((candidate) => candidate.id === tabId);
  if (!tab) {
    throw new RangeError(`Unknown workflow tab: ${tabId}`);
  }
  if (!getVisibleWorkflowTabs(state).includes(tabId)) {
    throw new RangeError(`Workflow tab is not visible: ${tabId}`);
  }
  return { ...state, activeTab: tabId };
}

export function workflowTabForKey(state, currentTabId, key) {
  return tabForKey(getVisibleCockpitTaskIds(state), currentTabId, key);
}

function tabForKey(tabIds, currentTabId, key) {
  const currentIndex = tabIds.indexOf(currentTabId);
  if (currentIndex < 0 || tabIds.length === 0) {
    return null;
  }
  if (key === "Home") {
    return tabIds[0];
  }
  if (key === "End") {
    return tabIds.at(-1);
  }
  if (key === "ArrowRight") {
    return tabIds[(currentIndex + 1) % tabIds.length];
  }
  if (key === "ArrowLeft") {
    return tabIds[(currentIndex - 1 + tabIds.length) % tabIds.length];
  }
  return null;
}

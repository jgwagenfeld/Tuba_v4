export const WORKFLOW_TABS = Object.freeze([
  { id: "summary", label: "Review", requiresReview: true },
  { id: "model", label: "Model", requiresReview: true },
  { id: "load-cases", label: "Load Cases", requiresReview: true },
  { id: "results", label: "Results", requiresReview: true },
  { id: "diagnostics", label: "Issues", requiresReview: false },
  { id: "3d", label: "Display", requiresReview: false },
  { id: "compliance", label: "Compliance", requiresReview: true }
]);

const EVIDENCE_TAB_IDS = Object.freeze(["summary", "diagnostics", "compliance"]);

export function getVisibleWorkflowTabs({ review } = {}) {
  return review ? WORKFLOW_TABS.map((tab) => tab.id) : ["3d", "diagnostics"];
}

export function getVisibleCockpitTaskIds({ review } = {}) {
  return review
    ? ["summary", "model", "load-cases", "results", "diagnostics", "3d"]
    : ["3d", "diagnostics"];
}

export function defaultWorkflowTab({ review, embed } = {}) {
  return embed || !review ? "3d" : "summary";
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

export function evidenceTabForKey(currentTabId, key) {
  return tabForKey(EVIDENCE_TAB_IDS, currentTabId, key);
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

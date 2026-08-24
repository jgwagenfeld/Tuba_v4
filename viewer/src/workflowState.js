import { tableIdsForWorkflow } from "./reviewTables.js";

export const WORKFLOW_TABS = Object.freeze([
  { id: "summary", label: "Review", requiresReview: true },
  { id: "model", label: "Model", requiresReview: true },
  { id: "load-cases", label: "Load Cases", requiresReview: true },
  { id: "results", label: "Results", requiresReview: true },
  { id: "diagnostics", label: "Issues", requiresReview: false },
  { id: "3d", label: "Display", requiresReview: false },
  { id: "compliance", label: "Compliance", requiresReview: true }
]);

// Always offered: the first three are the review's own framing, and Compliance
// carries a caveat worth stating even when it has no table behind it.
const ALWAYS_EVIDENCE_TAB_IDS = Object.freeze(["summary", "compliance", "diagnostics", "reports"]);

// Offered only when the review actually carries their tables. WORKFLOW_TABLES
// routes line_list, load_cases, studies and fe_stress to these three ids, and
// the dock used to expose none of them - so four of the six tables in a real
// review were parsed, view-modelled and then had nowhere to go.
const TABLE_EVIDENCE_TAB_IDS = Object.freeze(["model", "load-cases", "results"]);

// The table-driven tabs slot in after Governing Results; the four that were
// always there keep their existing relative order, so a review carrying none of
// the new tables sees exactly the dock it saw before.
const EVIDENCE_TAB_ORDER = Object.freeze([
  "summary",
  "model",
  "load-cases",
  "results",
  "diagnostics",
  "compliance",
  "reports"
]);

export function getVisibleWorkflowTabs({ review } = {}) {
  return review ? WORKFLOW_TABS.map((tab) => tab.id) : ["model", "diagnostics"];
}

export function getVisibleCockpitTaskIds({ review } = {}) {
  return review ? ["summary", "model", "results", "diagnostics"] : ["model", "diagnostics"];
}

export function getVisibleEvidenceTabIds({ review } = {}) {
  if (!review) {
    return ["diagnostics"];
  }
  return EVIDENCE_TAB_ORDER.filter(
    (id) =>
      ALWAYS_EVIDENCE_TAB_IDS.includes(id) ||
      // Only when it carries something the always-present tabs do not already
      // show. result_summary routes to both summary and results, so testing for
      // "any table" alone sprouted a Results tab that duplicated Governing
      // Results and nothing else.
      tableIdsForWorkflow(id).some(
        (tableId) => Boolean(review.tables?.[tableId]) && !alwaysShownTableIds().has(tableId)
      )
  );
}

function alwaysShownTableIds() {
  return new Set(ALWAYS_EVIDENCE_TAB_IDS.flatMap((id) => tableIdsForWorkflow(id)));
}

export function defaultWorkflowTab({ review, embed } = {}) {
  if (embed) return "3d";
  return review ? "summary" : "model";
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

export function evidenceTabForKey(state, currentTabId, key) {
  return tabForKey(getVisibleEvidenceTabIds(state), currentTabId, key);
}

export function evidenceTabForReload(state, currentTabId) {
  const visibleIds = getVisibleEvidenceTabIds(state);
  return visibleIds.includes(currentTabId) ? currentTabId : visibleIds[0];
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

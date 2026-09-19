export const WORKFLOW_TABS = Object.freeze([
  { id: "model", label: "Model" },
  { id: "results", label: "Results" },
  { id: "diagnostics", label: "Issues" }
]);

//: The task an embedded scene sits in: no rail, no preset, the scene as loaded.
//
// This was a fourth entry in WORKFLOW_TABS, labelled "Display", and it was the
// only one getVisibleCockpitTaskIds could never return - so the rail could not
// offer it and setWorkflowTab would have thrown on it, while embed mode set it
// directly. A tab nobody can reach is not a tab. It is still a real state, so
// it keeps its id and loses the label that implied a control existed.
//
// tutorial.md used to send readers to find "the Display controls" for load-case
// selection, deformation, camera presets and the section box. Those four live
// in three different places, none of them a task.
export const EMBED_TASK_ID = "3d";

// The Results task owns the coloring channel now that the permanent bar above
// the viewport is gone, so a scene carrying fields or result states must offer
// it even without a review - otherwise there is no way left to pick what
// colours the model. setWorkflowTab checks the rail's own list, so the rail
// never offers a task it rejects.
function hasResultContent({ resultFields, resultStates } = {}) {
  return (resultFields ?? []).length > 0 || (resultStates ?? []).length > 0;
}

export function getVisibleCockpitTaskIds(state = {}) {
  // No Review task any more: it fronted the evidence dock, and the review's
  // tables live in the generated report the header links to. What is left in
  // the rail is what you do to the scene - model, results, issues. Load cases
  // are written in model.py, so Build mode is where they are edited.
  if (state.review) return ["model", "results", "diagnostics"];
  return hasResultContent(state) ? ["model", "results", "diagnostics"] : ["model", "diagnostics"];
}

export function defaultWorkflowTab({ review, embed } = {}) {
  if (embed) return EMBED_TASK_ID;
  return "model";
}

const TASK_VISIBILITY_PRESETS = Object.freeze({
  model: { design: true, analysis_mesh: false, results: false, annotations: false },
  results: { design: true, analysis_mesh: false, results: true, annotations: true },
  diagnostics: { design: true, analysis_mesh: false, results: false, annotations: true },
  // Build inspects what was built. A volume or mesh review carries no procedural
  // design geometry - its analysis mesh is the model - so the mesh stays in view
  // and only the result and annotation overlays drop. A layer declared hidden by
  // the bundle still stays hidden, so a review with real design geometry keeps
  // the mesh out of its Build view.
  build: { design: true, analysis_mesh: true, results: false, annotations: false }
});

export function visibilityPresetForTask(taskId) {
  return Object.hasOwn(TASK_VISIBILITY_PRESETS, taskId) ? TASK_VISIBILITY_PRESETS[taskId] : null;
}

// The stage tree.
//
// Build and the embedded canvas are not tasks. The rail's three tasks live
// *inside* the review stage; Build is a sibling of that whole stage, and the
// embedded canvas is a third sibling with no chrome at all. Storing that tree
// as two flat variables - a mode kept in module globals, and one activeTab -
// is what forced three separate workarounds: an enterBuild action that set a
// tab the reader was not on, a "build" entry in a table keyed by task id, and
// an EMBED_TASK_ID that no rail could ever offer.
//
// This is the one derived answer to "what is on screen". It is pure, so every
// rule below is a case in a function rather than a boolean recomputed from six
// globals in whichever render function happens to need it.
export function workspaceView(state = {}, session = {}) {
  const stage = stageOf(state, session);
  const inReview = stage === "review";
  const tabs = inReview ? getVisibleCockpitTaskIds(state) : [];
  // A task only means anything inside the review stage, and only if the rail is
  // still offering it: swapping bundles can strip the content a task was for,
  // and a rail marking a tab it did not draw is the kind of disagreement this
  // module exists to make impossible.
  const task = tabs.includes(state.activeTab) ? state.activeTab : tabs[0] ?? null;
  return {
    stage,
    task,
    tabs,
    railVisible: inReview && session.railExpanded !== false,
    // The toggle is the rail's own control: it stays while the rail is merely
    // collapsed, or there would be no way to bring it back, and goes when the
    // stage has no rail at all.
    railToggleVisible: inReview,
    scriptVisible: stage === "build",
    headerVisible: stage !== "embed",
    // Which studio bundle this stage reads. Results with nothing solved still
    // shows the live model rather than an empty review.
    bundle: inReview && session.studio?.hasReview ? "review" : "build",
    // The layer preset, chosen by the stage first and the task second. The
    // embedded scene takes none: it is shown as the bundle declared it.
    visibility: stage === "build" ? "build" : task
  };
}

function stageOf(state, session) {
  if (state.embed) return "embed";
  // A studio runs model.py; a published bundle shows the same pane frozen.
  // Either way the stage is whichever of the two is driving.
  const driver = session.studio?.available
    ? session.studio
    : session.sourceView?.available
      ? session.sourceView
      : null;
  return driver?.mode === "build" ? "build" : "review";
}

// Which stage a studio opens on. A review that is present and current is what
// the reader came back for; anything else - never solved, or stale because the
// model moved since the solve - opens on the script, where the work is.
export function openingStage(studio = {}) {
  return studio.hasReview && !studio.reviewStale ? "review" : "build";
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
  if (!getVisibleCockpitTaskIds(state).includes(tabId)) {
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

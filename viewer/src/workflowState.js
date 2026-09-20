// Which channel tints the scene: a solver field, or the model's own properties.
//
// Explicit state, never inferred from the rail's task - there is no task any
// more. The review's lenses are sections of one scrollable rail, so nothing a
// reader switches can change what the colours mean. A scene that carries
// results opens on them; a model with none colours by the model.
export const COLOR_CHANNELS = Object.freeze(["model", "results"]);

export function colorChannelOf(state = {}) {
  if (COLOR_CHANNELS.includes(state.colorChannel)) return state.colorChannel;
  return hasResultColouring(state) ? "results" : "model";
}

// A legacy bundle carries solver overlays without the newer result_state
// records, and it still has results to colour by.
function hasResultColouring(state = {}) {
  if ((state.resultFields ?? []).length > 0 || (state.resultStates ?? []).length > 0) return true;
  return (state.overlays ?? []).some(
    (overlay) => overlay.kind === "solver_result" || overlay.kind === "result_state"
  );
}

// A visibility preset is a *stage* default, not a per-lens one. Review takes the
// scene as the bundle declared it: its rail sections change what is shown
// alongside the viewport, never what is drawn on it. Applying a preset on a lens
// change fought the pinned display strip - which exists precisely so "what is
// drawn" is user-owned - and could switch off the very bodies a composited
// review opened to show.
//
// Build inspects what was built. A volume or mesh review carries no procedural
// design geometry - its analysis mesh is the model - so the mesh stays in view
// and only the result and annotation overlays drop. A layer declared hidden by
// the bundle still stays hidden, so a review with real design geometry keeps
// the mesh out of its Build view.
const STAGE_VISIBILITY_PRESETS = Object.freeze({
  build: { design: true, analysis_mesh: true, results: false, annotations: false }
});

export function visibilityPresetForStage(stageId) {
  return Object.hasOwn(STAGE_VISIBILITY_PRESETS, stageId) ? STAGE_VISIBILITY_PRESETS[stageId] : null;
}

export const STAGES = Object.freeze(["embed", "build", "review"]);

// The stage is carried by the scene state rather than by a mode global, because
// the scene itself depends on it: which layers are drawn is a stage question,
// asked by pure functions handed nothing but the state. Keeping it in a session
// global is what forced those functions to read `activeTab !== "model"` as a
// stand-in, which held only while Build was forcing a tab to "model".
export function sceneStage(state = {}) {
  if (state.embed) return "embed";
  return STAGES.includes(state.stage) ? state.stage : "review";
}

// The one derived answer to "what is on screen". It is pure, so every rule below
// is a case in a function rather than a boolean recomputed from six globals in
// whichever render function happens to need it.
//
// Build and the embedded canvas are not review sections: Build is a sibling of
// the whole review stage with the script in the rail's place, and the embedded
// canvas is a third sibling with no chrome at all.
export function workspaceView(state = {}, session = {}) {
  const stage = sceneStage(state);
  const inReview = stage === "review";
  return {
    stage,
    railVisible: inReview && session.railExpanded !== false,
    // The toggle is the rail's own control: it stays while the rail is merely
    // collapsed, or there would be no way to bring it back, and goes when the
    // stage has no rail at all.
    railToggleVisible: inReview,
    scriptVisible: stage === "build",
    headerVisible: stage !== "embed",
    // Which studio bundle this stage reads. Review with nothing solved still
    // shows the live model rather than an empty review.
    bundle: inReview && session.studio?.hasReview ? "review" : "build",
    // The layer preset, chosen by the stage alone. Review has none - it shows
    // the scene as the bundle declared it, and its sections do not rewrite it -
    // and the embedded scene likewise takes none.
    visibility: visibilityPresetForStage(stage) ? stage : null
  };
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
    embed: Boolean(embed)
  };
}

// Readiness is supplied by Studio; guidance never substitutes a solver result.
export function studioSolveGuidance({ project, embed = false, pendingEdits = false,
  running = false, solving = false, preparing = false, processRunning = false,
  meshBusy = false, sourceError = false } = {}) {
  if (!project || embed) return null;
  if (solving) return { state: 'solving', message: 'Code_Aster is running. Open Review when it finishes.' };
  if (preparing) return { state: 'importing', message: 'Importing the processed review…' };
  if (running) return { state: 'updating', message: 'Updating geometry. Wait for model.py to finish before solving.' };
  if (processRunning) return { state: 'hydraulics-running', message: 'Hydraulics is running. Code_Aster Solve requires passing hydraulic checks.' };
  if (meshBusy) return { state: 'mesh-running', message: 'A mesh job is running. Wait for it to finish, or cancel it in Mesh detail.' };
  if (pendingEdits) return { state: 'pending-edits', message: 'Update geometry (Ctrl+Enter) to apply model.py edits before solving.' };
  if (sourceError || project.can_mesh === false) return { state: 'source-error', message: 'Fix the model.py error, then Update geometry before solving.' };
  if (project.has_study === false || !project.solves) return {
    state: 'missing-study', message: 'Add LOAD_CASES in study.py to enable Code_Aster Solve.'
  };
  const process = project.process;
  if (process?.available && !project.can_solve) {
    const messages = {
      rejected: 'Review failed hydraulic checks in P&ID, revise model.py, then Run hydraulics again.',
      failed: 'Hydraulics failed. Fix the error shown beside Run hydraulics, then run it again.',
      stale: 'Hydraulics is outdated. Run hydraulics for the current model before Code_Aster Solve.',
      running: 'Hydraulics is running. Code_Aster Solve requires passing hydraulic checks.'
    };
    return { state: `hydraulics-${process.status ?? 'not_evaluated'}`,
      message: messages[process.status] ?? 'Run hydraulics and pass its checks before Code_Aster Solve.' };
  }
  if (!project.can_solve) return { state: 'not-ready', message: 'Check study.py and Update geometry successfully before solving.' };
  return null;
}

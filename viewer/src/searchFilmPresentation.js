// Film annotations are presentations of recorded checks and native scene data.
// Never fill a missing operation/state with another operation's results.
import { hydraulicSolverLabel } from './searchReplay.js';

const finite = value => typeof value === 'number' && Number.isFinite(value);
const point = value => Array.isArray(value) && value.length === 3 && value.every(finite);
const number = value => finite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : 'unavailable';
export const SECTION_COMPONENTS = ['N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'];

export function scopedOverlay(scene, type, operation, state, basis = null) {
  const fluid = type.startsWith('fluid_');
  if (!operation || (!fluid && !state)) return null;
  return scene?.overlays?.find(o => o.data?.result_type === type && o.data.load_case === operation &&
    (fluid ? hydraulicSolverLabel(o.data.basis) && (!basis || o.data.basis === basis) && !o.data.result_state_id : o.data.result_state_id === state)) ?? null;
}

function objectPoint(scene, id, end = null) {
  const object = scene?.objects?.find(o => o.id === id || o.id === `object:${id}` || o.entity_ref === id);
  const asset = scene?.geometry_assets?.find(a => a.id === object?.geometry_asset_id);
  const config = asset?.generation_config;
  if (point(config?.point)) return config.point;
  if (Array.isArray(config?.points) && config.points.length) {
    const points = config.points;
    const chosen = end === 'n1' ? points[0] : end === 'n2' ? points.at(-1) : points[Math.floor(points.length / 2)];
    if (point(chosen)) return chosen;
  }
  const b = asset?.bounds;
  return Array.isArray(b) && b.length === 6 && b.every(finite) ? [0, 1, 2].map(i => (b[i] + b[i + 3]) / 2) : null;
}

function hydraulicPresentation(frame, scene, operation) {
  const check = frame.check;
  const basis = frame.hydraulic_basis ?? check?.basis ?? frame.checks?.find(c => hydraulicSolverLabel(c.basis))?.basis ?? scene?.process?.basis;
  const solver = hydraulicSolverLabel(basis) ?? 'Hydraulic';
  const pressure = check?.unit === 'Pa';
  const fieldType = pressure ? 'fluid_pressure' : 'fluid_velocity';
  const overlay = hydraulicSolverLabel(basis) ? scopedOverlay(scene, fieldType, operation, null, basis) : null;
  const field = scene?.result_fields?.find(f => f.overlay_id === overlay?.id);
  const unit = pressure ? 'Pa' : 'm/s';
  const quantity = pressure ? 'mean absolute fluid pressure' : 'fluid velocity';
  const rows = [], annotations = [];
  const peak = Object.entries(overlay?.data.values ?? {}).filter(([, value]) => finite(value))
    .sort((a, b) => b[1] - a[1])[0];
  rows.push(peak ? `Largest recorded ${quantity}: ${number(peak[1])} ${unit} - ${peak[0].replace('object:element:', '')}`
    : `${solver} ${quantity} unavailable for this recorded scenario.`);
  if (check) {
    if (finite(check.measured_value) || finite(check.limit)) rows.push(`${check.constraint_id}: ${number(check.measured_value)} / limit ${number(check.limit)} ${check.unit ?? ''}`);
    if (check.message) rows.push(check.message);
    if (overlay) for (const ref of check.entity_refs ?? []) {
      const p = objectPoint(scene, ref);
      if (p) annotations.push({ point: p, label: `${ref.replace(/^(object:)?element:/, '')}: ${number(check.measured_value)} / limit ${number(check.limit)} ${check.unit ?? ''}`, severity: check.verdict });
    }
  } else if (peak) {
    const p = objectPoint(scene, peak[0]);
    if (p) annotations.push({ point: p, label: `${peak[0].replace('object:element:', '')}: ${number(peak[1])} ${unit}`, severity: 'result' });
  }
  rows.push(`${solver} steady hydraulics; fluid pressures are absolute.`);
  rows.push(frame.completed_operations?.length || scene?.search?.solved_operations?.length
    ? 'Code_Aster structural results are retained separately.' : 'Code_Aster structural results were not evaluated.');
  return { title: `${solver}: ${quantity} (${unit})`, rows, annotations, solver,
    fieldId: field?.id ?? null, fieldType, component: 'magnitude', unitSystem: 'si', mode: 'hydraulics' };
}

export function filmPresentation(frame, scene, operation, state) {
  const mode = frame.result_view ?? 'finding';
  if (mode === 'iteration') return iterationPresentation(frame, scene, operation, state);
  if (frame.fluid_results || hydraulicSolverLabel(frame.check?.basis)) return hydraulicPresentation(frame, scene, operation);
  const annotations = [], rows = [];
  let title = frame.check ? `${frame.check.verdict.toUpperCase()}: ${frame.check.constraint_id}` : 'Recorded candidate';
  // Reactions are a nodal quantity. Colour the pipe by its own measured stress
  // while the separate blue/orange support diagrams remain visible.
  let fieldType = 'stress', component = 'magnitude';
  const check = frame.check;
  if (!check && mode === 'finding') {
    if (frame.event_message) rows.push(frame.event_message);
    if (frame.reason_codes?.length) rows.push(`Decision: ${frame.reason_codes.join(', ')}`);
    if (frame.view?.availability !== 'available') rows.push(frame.view?.message ?? 'No recorded geometry or solver results available.');
  }
  if (check) {
    for (const [i, clash] of (check.details?.clashes ?? []).entries()) {
      if (!point(clash.location)) continue;
      annotations.push({ point: clash.location, label: `Collision ${i + 1}: penetration ${number(clash.penetration_m * 1000)} mm`, severity: 'fail' });
    }
    for (const [i, clash] of (check.details?.clashes ?? []).entries()) rows.push(`Collision ${i + 1}: ${clash.left?.id ?? 'unknown object'} / ${clash.right?.id ?? 'unknown object'}`);
    if (!annotations.length) for (const ref of check.entity_refs ?? []) {
      let p = objectPoint(scene, ref);
      if (ref.startsWith('node:')) p = scopedOverlay(scene, 'reaction_force', operation, state)?.data.vectors?.find(v => `node:${v.node_id}` === ref)?.start ?? p;
      if (point(p)) annotations.push({ point: p, label: `${ref.replace(/^(object:)?(element|node|support|obstacle):/, '')}: ${finite(check.measured_value) ? `${number(check.measured_value)} / limit ${number(check.limit)} ${check.unit ?? ''}` : check.verdict}`, severity: check.verdict });
    }
    if (check.measured_value != null || check.limit != null) rows.push(`${number(check.measured_value)} ${check.comparator ?? 'against'} ${number(check.limit)} ${check.unit ?? ''}`);
    rows.push(check.message ?? check.reason_text ?? check.reason_code ?? 'No reason recorded');
  }
  const reactions = scopedOverlay(scene, 'reaction_force', operation, state);
  const moments = scopedOverlay(scene, 'reaction_moment', operation, state);
  if (mode !== 'reactions') for (const vector of reactions?.data.vectors ?? []) {
    const values = reactions.data.values?.[vector.node_id];
    const m = moments?.data.values?.[vector.node_id];
    if (!point(values) || !point(vector.start)) continue;
    const force = number(Math.hypot(...values)), moment = point(m) ?
      (Math.hypot(...m) < 0.005 ? '<0.01' : number(Math.hypot(...m))) : 'unavailable';
    annotations.push({ point: vector.start, label: `${vector.node_id}: F ${force} N · M ${moment} N m`, severity: 'result' });
  }
  if (mode === 'reactions') {
    title = 'Support reactions — pipe coloured by FE stress';
    for (const vector of reactions?.data.vectors ?? []) {
      const values = reactions.data.values?.[vector.node_id];
      if (!point(values) || !point(vector.start)) continue;
      const m = moments?.data.values?.[vector.node_id];
      const momentLabel = point(m) ? (Math.hypot(...m) < 0.005 ? '<0.01' : number(Math.hypot(...m))) : 'unavailable';
      const label = `${vector.node_id}: F ${number(Math.hypot(...values))} N · M ${momentLabel} N m`;
      annotations.push({ point: vector.start, label, severity: 'result' });
      rows.push(`${vector.node_id}  F [${values.map(number).join(', ')}] N\n      M [${point(m) ? m.map(number).join(', ') : 'unavailable'}] N m`);
    }
    if (!rows.length) rows.push('Support reactions unavailable for this recorded operation/state.');
    rows.push('Code_Aster reactions on the model; loads on the foundation have opposite sign.');
  }
  if (mode === 'stress') {
    title = 'Pipe stress — FE von Mises (MPa)';
    const stress = scopedOverlay(scene, 'stress', operation, state);
    const entries = Object.entries(stress?.data.values ?? {}).filter(([, value]) => finite(value));
    const peak = entries.sort((a, b) => b[1] - a[1])[0];
    rows.push(peak ? `Largest recorded element maximum: ${number(peak[1] / 1e6)} MPa · ${peak[0].replace('object:element:', '')}` : 'Pipe stress unavailable for this recorded operation/state.');
    rows.push('Pipe colours show each element’s recorded maximum FE von Mises stress.');
    rows.push('FE stress — not a piping-code stress or compliance verdict.');
    if (peak) {
      const p = objectPoint(scene, peak[0]);
      if (p) annotations.push({ point: p, label: `${peak[0].replace('object:element:', '')}: element max ${number(peak[1] / 1e6)} MPa`, severity: 'result' });
    }
  }
  if (mode === 'internal_forces') {
    fieldType = 'internal_forces'; component = frame.component ?? 'MFZ';
    const names = { N: 'Axial force', VY: 'Shear Y', VZ: 'Shear Z', MT: 'Torsion', MFY: 'Bending Y', MFZ: 'Bending Z' };
    title = `${names[component]} — ${component} (${SECTION_COMPONENTS.indexOf(component) < 3 ? 'N' : 'N m'})`;
    const overlay = scopedOverlay(scene, 'internal_forces', operation, state);
    for (const [index, name] of SECTION_COMPONENTS.entries()) {
      let peak = null;
      for (const [id, result] of Object.entries(overlay?.data.element_results ?? {})) {
        for (const end of ['n1', 'n2']) {
          const value = result[`forces_${end}`]?.[index];
          if (finite(value) && (!peak || Math.abs(value) > Math.abs(peak.value))) peak = { id, end, value };
        }
      }
      const unit = index < 3 ? 'N' : 'N m';
      rows.push(peak ? `${name}: ${number(peak.value)} ${unit} · ${peak.id.replace('object:element:', '')} ${peak.end}` : `${name}: unavailable`);
      if (peak && name === component) {
        const p = objectPoint(scene, peak.id, peak.end);
        if (p) annotations.push({ point: p, label: `${name}: ${number(peak.value)} ${unit} (${peak.end})`, severity: 'result' });
      }
    }
    rows.push(`Pipe colours: signed ${component} at each element’s controlling endpoint.`);
    rows.push('Local element axes. Endpoint peaks only; no interior maximum or code compliance inferred.');
  }
  if (mode === 'displacement') {
    title = 'Displacement — physical deformation ×1'; fieldType = 'displacement'; component = 'magnitude';
    const overlay = scopedOverlay(scene, 'displacement', operation, state);
    const values = Object.entries(overlay?.data.values ?? {}).filter(([, v]) => point(v));
    const peak = values.sort((a, b) => Math.hypot(...b[1]) - Math.hypot(...a[1]))[0];
    rows.push(peak ? `Largest recorded nodal displacement: ${number(Math.hypot(...peak[1]) * 1000)} mm · ${peak[0]}` : 'Displacement unavailable for this recorded operation/state.');
    rows.push('Labels show measured displacement; the geometry remains at physical scale.');
  }
  const field = scene?.result_fields?.find(f => f.overlay_id === scopedOverlay(scene, fieldType, operation, state)?.id);
  return { title, rows, annotations, fieldId: field?.id ?? null, component, mode,
    fieldType, unitSystem: fieldType === 'stress' ? 'engineering' : 'si' };
}

function parameter(value, key) {
  const label = key.replace(/_m$/, '').replaceAll('_', ' ');
  return `${label}: ${String(value).replaceAll('_', ' ')}${key.endsWith('_m') ? ' m' : ''}`;
}


function findingRows(checks, fluid) {
  const groups = new Map();
  for (const check of checks) {
    const kind = check.constraint_id.replace(/\.\d+$/, '');
    // Combine identical recorded quantities only; rounding is for display.
    const key = fluid && kind !== check.constraint_id && finite(check.measured_value) && finite(check.limit)
      ? JSON.stringify([kind, check.measured_value, check.limit, check.unit, check.comparator, check.reason_code])
      : check;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(check);
  }
  return [...groups.values()].map(group => {
    const check = group[0];
    const measured = `${number(check.measured_value)} / limit ${number(check.limit)} ${check.unit ?? ''}`;
    if (group.length === 1) return `${check.constraint_id}: ${measured}`;
    const kind = check.constraint_id.replace(/\.\d+$/, '');
    let coverage = `${group.length} findings`;
    if (kind === 'flow.velocity') {
      const refs = group.flatMap(c => c.entity_refs ?? []);
      const pipes = new Set(refs.filter(ref => /^(object:)?element:/.test(ref))).size;
      const external = group.filter(c => !(c.entity_refs ?? []).length).length;
      if (refs.every(ref => /^(object:)?element:/.test(ref))) {
        coverage = [pipes && `${pipes} pipe element${pipes === 1 ? '' : 's'}`,
          external && `${external} external loss${external === 1 ? '' : 'es'}`].filter(Boolean).join(' + ');
      }
    }
    return `${kind}: ${measured} across ${coverage}.`;
  });
}

function iterationPresentation(frame, scene, operation, state) {
  const title = frame.phase === 'selection' ? 'Final choice after testing all layouts'
    : `Piping iteration ${frame.iteration_index} / ${frame.candidate_count}`;
  const rows = frame.phase === 'selection' ? [] : [Object.entries(frame.parameters ?? {}).map(([k, v]) => parameter(v, k)).join(' · ')];
  if (frame.reference_candidate_id && frame.phase !== 'selection') {
    const changes = frame.parameter_changes ?? [];
    rows.push(changes.length ? `Changed from ${frame.reference_candidate_id}: ${changes.map(c =>
      `${parameter(c.before, c.key)} → ${String(c.after).replaceAll('_', ' ')}${c.key.endsWith('_m') ? ' m' : ''}`).join('; ')}`
      : 'Same layout; evaluation retry.');
  }
  const sameState = !frame.native_results || (operation === frame.operation && (!frame.result_state_id || state === frame.result_state_id));
  const native = frame.native_results && sameState;
  const fluid = frame.fluid_results && operation === frame.operation;
  const base = native ? filmPresentation({ result_view: 'stress' }, scene, operation, state)
    : fluid ? hydraulicPresentation(frame, scene, operation)
    : { annotations: [], fieldId: null, fieldType: 'stress', component: 'magnitude', unitSystem: 'si' };
  const annotations = [];
  const clashes = new Map();
  const failures = (frame.checks ?? []).filter(c => c.verdict === 'fail' && (fluid ? hydraulicSolverLabel(c.basis) && (!frame.hydraulic_basis || c.basis === frame.hydraulic_basis)
    : !hydraulicSolverLabel(c.basis) && (c.operation ?? null) === (native ? operation : null) &&
      (c.result_state_id ?? null) === (native ? state : null)));
  for (const check of failures) {
    for (const clash of check.details?.clashes ?? []) {
      const key = JSON.stringify([clash.left?.id, clash.right?.id, clash.location, clash.penetration_m]);
      if (!clashes.has(key)) clashes.set(key, clash);
    }
    if (!(check.details?.clashes ?? []).length) {
      const finding = filmPresentation({ check }, scene, operation, state);
      annotations.push(...finding.annotations.filter(a => a.severity !== 'result'));
    }
  }
  rows.push(...findingRows(failures.filter(check => !(check.details?.clashes ?? []).length), fluid));
  for (const [index, clash] of [...clashes.values()].entries()) {
    if (!point(clash.location)) continue;
    const clearance = String(clash.severity).includes('clearance');
    annotations.push({ point: clash.location, severity: 'fail', label:
      `${index + 1}. ${clash.left?.id ?? 'pipe'} / ${clash.right?.id ?? 'obstacle'}: ${clearance ? 'clearance deficit' : 'overlap'} ${number(clash.penetration_m * 1000)} mm` });
  }
  if (clashes.size) rows.push(`${clashes.size} recorded collision / clearance findings. Red rings mark their locations.`);
  const operating = [...clashes.values()].find(c => finite(c.metadata?.cold_distance_m) && finite(c.metadata?.operating_distance_m));
  if (operating) rows.push(`Gap to ${operating.right?.id}: cold ${number(operating.metadata.cold_distance_m * 1000)} mm → ${operation} ${number(operating.metadata.operating_distance_m * 1000)} mm.`);
  if (operating) rows.push('Reference layout; red rings locate the physical operating-check findings.');
  if (native) {
    annotations.push(...base.annotations);
    const counts = frame.check_counts;
    rows.push(`${counts.pass} checks passed · ${counts.fail} failed · ${counts.unknown} unknown (${frame.completed_operations.join(' + ')}).`);
    if (!counts.fail && !counts.unknown && frame.phase !== 'selection') rows.push('All declared checks satisfied; retained for comparison.');
    rows.push(base.rows[0]);
    if (frame.phase !== 'selection') rows.push('Pipe colours: element maximum FE stress (MPa). Support labels: F (N), M (N m).');
  } else if (fluid) {
    const counts = frame.check_counts;
    if (counts) rows.push(`${counts.pass} checks passed; ${counts.fail} failed; ${counts.unknown} unknown.`);
    rows.push(base.rows[0], ...base.rows.slice(-2));
    if (!failures.length) annotations.push(...base.annotations);
  } else {
    rows.push(frame.outcome === 'interrupted' ? 'Attempt interrupted. No completed Code_Aster results; loads and stress unavailable.'
      : frame.check_counts?.fail && !frame.completed_operations?.length ? 'Rejected before solving. Support loads and stress were not evaluated.'
      : 'No completed Code_Aster results. Support loads and stress unavailable.');
    if (frame.check_counts?.unknown) rows.push(`${frame.check_counts.unknown} required checks remain unknown.`);
  }
  if (frame.native_results && !sameState) rows.push('Requested solver state unavailable; no substitute results displayed.');
  if (frame.fluid_results && !fluid) rows.push('Requested hydraulic scenario unavailable; no substitute results displayed.');
  if (frame.phase === 'selection') {
    const order = frame.finalists.find(c => c.candidate_id === frame.candidate_id)?.details?.objective_fields ?? [];
    rows.push(`Chosen ${frame.candidate_id}: ${number(frame.objectives.pipe_length_m)} m · ${number(frame.objectives.bend_count)} bends · ${number(frame.objectives.support_count)} supports.\nRank order: ${order.map(k => k.replaceAll('_', ' ')).join(', ')}, then proposal order.`);
    for (const c of frame.finalists.filter(c => c.candidate_id !== frame.candidate_id)) {
      const winner = frame.objectives;
      const tied = Object.keys(winner).length && Object.keys(winner).every(k => c.objectives[k] === winner[k]);
      rows.push(tied && c.reason_codes?.includes('lexicographic_objectives_and_proposal_order') ? `${c.candidate_id}: feasible, tied objectives; earlier proposal selected.`
        : `${c.candidate_id}: feasible, not selected (${number(c.objectives.pipe_length_m)} m, ${number(c.objectives.bend_count)} bends, ${number(c.objectives.support_count)} supports).`);
    }
  } else if (Object.keys(frame.objectives).length) rows.push(`Layout: ${number(frame.objectives.pipe_length_m)} m · ${number(frame.objectives.bend_count)} bends · ${number(frame.objectives.support_count)} supports.`);
  return { ...base, title, rows: rows.filter(Boolean), annotations, mode: 'iteration' };
}

export function conciseFilmCaption(frame, presentation, operation, state, error) {
  const outcome = frame.caption.match(/Recorded outcome: ([^\n]+)/)?.[1] ?? 'not recorded';
  if (frame.result_view === 'iteration') {
    const labels = { rejected_constraint: 'REJECTED — declared constraint', feasible_retained: 'FEASIBLE — kept for comparison',
      interrupted: 'INTERRUPTED — no completed result', evaluation_failed: 'EVALUATION FAILED', selected: 'SELECTED' };
    return [`${frame.candidate_id} · ${presentation.title}`, labels[frame.outcome] ?? outcome.replaceAll('_', ' '),
      frame.fluid_results ? `${presentation.solver ?? 'Hydraulic'} - ${operation ?? 'scenario unavailable'} - steady hydraulics`
        : `${operation ?? 'Cold layout'} · ${state ?? 'no solver state'}`,
      ...(error ? [`View unavailable: ${error}`] : presentation.rows), `Recorded event ${frame.event_sequence}`].join('\n\n');
  }
  return [`${frame.candidate_id ?? 'Run'} · ${outcome.replaceAll('_', ' ')}`,
    presentation.title, frame.fluid_results || hydraulicSolverLabel(frame.check?.basis)
      ? `${presentation.solver ?? 'Hydraulic'} - ${operation ?? 'scenario unavailable'} - steady hydraulics`
      : `${operation ?? 'Cold reference'} · ${state ?? 'no solver state'}`,
    ...(error ? [`View unavailable: ${error}`] : presentation.rows),
    `Recorded event ${frame.event_sequence} · ${frame.search_timestamp ?? 'time not recorded'}`].join('\n\n');
}

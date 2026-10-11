// Film annotations are presentations of recorded checks and native scene data.
// Never fill a missing operation/state with another operation's results.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const point = value => Array.isArray(value) && value.length === 3 && value.every(finite);
const number = value => finite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : 'unavailable';
export const SECTION_COMPONENTS = ['N', 'VY', 'VZ', 'MT', 'MFY', 'MFZ'];

export function scopedOverlay(scene, type, operation, state) {
  if (!operation || !state) return null;
  return scene?.overlays?.find(o => o.data?.result_type === type &&
    o.data.load_case === operation && o.data.result_state_id === state) ?? null;
}

function objectPoint(scene, id, end = null) {
  const object = scene?.objects?.find(o => o.id === id || o.entity_ref === id);
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

export function filmPresentation(frame, scene, operation, state) {
  const mode = frame.result_view ?? 'finding';
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

export function conciseFilmCaption(frame, presentation, operation, state, error) {
  const outcome = frame.caption.match(/Recorded outcome: ([^\n]+)/)?.[1] ?? 'not recorded';
  return [`${frame.candidate_id ?? 'Run'} · ${outcome.replaceAll('_', ' ')}`,
    presentation.title, `${operation ?? 'Cold reference'} · ${state ?? 'no solver state'}`,
    ...(error ? [`View unavailable: ${error}`] : presentation.rows),
    `Recorded event ${frame.event_sequence} · ${frame.search_timestamp ?? 'time not recorded'}`].join('\n\n');
}

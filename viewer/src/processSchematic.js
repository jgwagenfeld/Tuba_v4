import { hydraulicSolverLabel } from './searchReplay.js';

const KINDS = { mass_flow_source: 'Mass-flow boundary', pipe: 'Pipe route', fixed_loss: 'External fixed loss', pressure_sink: 'Pressure boundary' };
const xml = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[character]));
const number = value => Number.isFinite(value) ? value.toLocaleString('en', { maximumFractionDigits: 3 }) : 'unavailable';
export const processFailureReason = check => `${check.constraint_id}: ${check.message} (measured ${number(check.measured_value)}; limit ${number(check.limit)} ${check.unit ?? ''})`;

export function processSchematicModel(scene) {
  const process = scene?.process, graph = process?.schematic;
  if (!graph) return null;
  const refuse = () => { throw new Error('Process schematic does not match the retained hydraulic review.'); };
  if (graph.schema !== 'tuba.process.schematic.v1' || !graph.bound_fingerprint || graph.bound_fingerprint !== process.bound_fingerprint ||
      !hydraulicSolverLabel(process.basis) || !Array.isArray(graph.components) || graph.components.length < 3 ||
      !Array.isArray(graph.connections) || !Array.isArray(process.segments) || !process.segments.length ||
      graph.scenario?.id !== process.scenario_id) refuse();
  const components = graph.components, segments = process.segments;
  if (components[0].kind !== 'mass_flow_source' || components.at(-1).kind !== 'pressure_sink' ||
      components.slice(1, -1).some(component => !['pipe', 'fixed_loss'].includes(component.kind)) ||
      new Set(components.map(component => component.id)).size !== components.length ||
      graph.connections.length !== components.length - 1) refuse();
  for (let index = 1; index < components.length; index++) {
    if (!graph.connections.some(connection => connection.source_port === components[index - 1].outlet_port &&
        connection.target_port === components[index].inlet_port)) refuse();
  }
  if (segments.some(row => !components.some(component => component.id === row.component_id) ||
      !['pressure_in_pa', 'pressure_out_pa', 'mass_flow_kg_s', 'velocity_m_s'].every(key => Number.isFinite(row[key])))) refuse();
  const failures = (scene.search?.checks ?? []).filter(check => check.verdict === 'fail');
  const nodes = components.map((component, index) => {
    if (typeof component.id !== 'string' || !component.id || !Array.isArray(component.element_ids)) refuse();
    const rows = segments.filter(row => row.component_id === component.id);
    if (['pipe', 'fixed_loss'].includes(component.kind) && !rows.length) refuse();
    if (component.kind === 'pipe' && (rows.length !== component.element_ids.length ||
        rows.some((row, rowIndex) => row.element_id !== component.element_ids[rowIndex]))) refuse();
    if (component.kind !== 'pipe' && component.element_ids.length) refuse();
    const readings = rows.length ? rows : [index === 0 ? segments[0] : segments.at(-1)];
    const pressureIn = component.kind === 'pressure_sink' ? readings[0].pressure_out_pa : readings[0].pressure_in_pa;
    const pressureOut = component.kind === 'mass_flow_source' ? pressureIn : readings.at(-1).pressure_out_pa;
    const matched = failures.filter(check => (component.velocity_check_ids ?? []).includes(check.constraint_id) ||
      (check.entity_refs ?? []).some(ref => component.element_ids.includes(ref.replace(/^element:/, ''))) ||
      (!check.entity_refs?.length && ((component.kind === 'mass_flow_source' && check.constraint_id === 'flow.source_pressure') ||
        (component.kind === 'pressure_sink' && ['flow.sink_pressure', 'flow.delivery'].includes(check.constraint_id)))));
    const values = [`Flow ${number(readings[0].mass_flow_kg_s)} kg/s`,
      `p ${number(pressureIn / 1000)}${rows.length ? ` → ${number(pressureOut / 1000)}` : ''} kPa abs`];
    if (rows.length) values.push(`Max v ${number(Math.max(...rows.map(row => row.velocity_m_s)))} m/s`);
    return { ...component, label: KINDS[component.kind], values, failures: matched,
      pressureIn, pressureOut, massFlow: readings[0].mass_flow_kg_s };
  });
  return { graph, nodes, solver: hydraulicSolverLabel(process.basis), operation: process.operation, failures,
    scenario: graph.scenario, requirements: graph.requirements };
}

export function processComponentDetails(model, node) {
  const details = [node.label, ...node.values];
  if (node.kind === 'pipe') details.push(`Route ${node.route_id}`, `Length ${number(node.length_m)} m; bore ${number(node.bore_m * 1000)} mm`,
    `${node.element_ids.length} mechanical elements`, `Bend K ${number(node.bend_loss_coefficient)}: ${node.bend_loss_source}`);
  if (node.kind === 'fixed_loss') details.push(`K ${number(node.loss_coefficient)}: ${node.loss_source}`, 'Outside the mechanical model; no 3D element.');
  if (node.kind === 'mass_flow_source') details.push(`Prescribed source temperature ${number(model.scenario.source_temperature_k)} K`);
  if (node.kind === 'mass_flow_source' || node.kind === 'pressure_sink') details.push('Mathematical boundary; no equipment or 3D element implied.');
  if (['pipe', 'fixed_loss'].includes(node.kind) && Number.isFinite(model.requirements?.max_velocity_m_s)) {
    details.push(`Velocity limit ${number(model.requirements.max_velocity_m_s)} m/s`);
  }
  details.push(...node.failures.map(processFailureReason));
  return details;
}

// shortcut: serial circuits use a single column; add a graph layout when branches are supported.
export function processSchematicSvg(model, selectedId = null) {
  const width = 300, top = 84, step = 150, height = top + model.nodes.length * step + 46;
  const text = (x, y, value, extra = '') => `<text x="${x}" y="${y}" ${extra}>${xml(value)}</text>`;
  const chunks = value => String(value).match(/.{1,25}/gu) ?? [''];
  const body = model.nodes.map((node, index) => {
    const y = top + index * step, failed = node.failures.length > 0;
    const tag = chunks(node.id), title = [...tag.slice(0, 2)];
    if (tag.length > 2) title[1] = `${title[1].slice(0, 22)}…`;
    const symbol = node.kind === 'pipe' ? `<path d="M25 ${y + 20}v40m14 -40v40"/>` : node.kind === 'fixed_loss'
      ? `<path d="M32 ${y + 18}l14 20l-14 20l-14 -20Z"/>`
      : node.kind === 'pressure_sink' ? `<rect x="15" y="${y + 21}" width="34" height="34"/><path d="M32 ${y + 27}v22m-7 -7l7 7l7 -7"/>`
      : `<circle cx="32" cy="${y + 38}" r="17"/><path d="M32 ${y + 27}v22m-7 -7l7 7l7 -7"/>`;
    return `${index ? `<path class="connection" d="M150 ${y - 18}v14m-4 -5l4 5l4 -5"/>` : ''}
      <g role="button" tabindex="0" data-process-component="${index}" data-focus-key="process:component:${index}"
        data-component-id="${xml(node.id)}" aria-pressed="${node.id === selectedId}" aria-label="${xml([node.id, ...processComponentDetails(model, node)].join('. '))}"
        class="component${failed ? ' failed' : ''}${node.id === selectedId ? ' selected' : ''}">
        <title>${xml([node.id, ...processComponentDetails(model, node)].join('\n'))}</title>
        <rect x="4" y="${y}" width="292" height="132" rx="7"/>
        <g class="symbol">${symbol}</g>
        ${title.map((line, row) => text(59, y + 20 + row * 15, line, 'class="tag"')).join('')}
        ${text(59, y + 52, node.label, 'class="kind"')}
        ${node.values.map((value, row) => text(14, y + 73 + row * 17, value)).join('')}
        ${failed ? text(14, y + 123, Number.isFinite(node.failures[0].measured_value) && Number.isFinite(node.failures[0].limit)
          ? `FAIL · ${number(node.failures[0].measured_value)} ${node.failures[0].comparator === 'min' ? '<' : '>'} ${number(node.failures[0].limit)} ${node.failures[0].unit}`
          : `FAIL · ${node.failures[0].constraint_id}`, 'class="failure"') : ''}
      </g>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" class="process-diagram" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="group" aria-label="Process schematic for ${xml(model.graph.network_id)}">
    <title>${xml(model.graph.network_id)} — tagged process schematic</title>
    <desc>Serial flow connectivity, not physical scale. Fixed loss is a hydraulic restriction, not a control valve. No instruments or control signals are defined. ${xml(model.solver)} results; pressures absolute.</desc>
    <metadata>${xml(JSON.stringify({ schema: 'tuba.process.schematic.svg.v1', schematic: model.graph, basis: model.solver, operation: model.operation, pressure_reference: 'absolute', pressure_display_unit: 'kPa' }))}</metadata>
    <style>.process-diagram text{font:13px sans-serif;fill:#20313b}.process-diagram .tag{font-weight:700}.process-diagram .kind{font-size:12px;fill:#445864}.process-diagram .component{cursor:pointer}.process-diagram .component>rect{fill:#f5f8fa;stroke:#9aaab4}.process-diagram .symbol,.process-diagram .connection{fill:none;stroke:#355567;stroke-width:2}.process-diagram .component.failed>rect{stroke:#b3261e;stroke-width:2}.process-diagram .failure{fill:#9c211a;font-size:12px;font-weight:700}.process-diagram .component.selected>rect,.process-diagram .component:focus>rect{stroke:#00678a;stroke-width:3;fill:#e2f5fb}.process-diagram .note{font-size:12px;fill:#445864}</style>
    <rect width="100%" height="100%" fill="#fff"/>
    ${text(10, 21, 'Tagged process schematic', 'class="tag"')}
    ${text(10, 41, `${model.solver} · ${model.scenario.id}`, 'class="kind"')}
    ${text(10, 60, 'Serial flow ↓ · pressure absolute', 'class="note"')}
    ${body}
    ${text(10, height - 34, 'Schematic · not physical scale', 'class="note"')}
    ${text(10, height - 16, 'No instrumentation / control design', 'class="note"')}
  </svg>`;
}

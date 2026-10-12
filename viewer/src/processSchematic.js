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
  const ports = components.flatMap(component => component.kind === 'mass_flow_source' ? [component.outlet_port]
    : component.kind === 'pressure_sink' ? [component.inlet_port] : [component.inlet_port, component.outlet_port]);
  if (ports.some(port => typeof port !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(port)) ||
      new Set(ports).size !== ports.length || components[0].inlet_port !== undefined || components.at(-1).outlet_port !== undefined) refuse();
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
  const model = { graph, nodes, solver: hydraulicSolverLabel(process.basis), operation: process.operation, failures,
    scenario: graph.scenario, requirements: graph.requirements };
  model.items = Object.hasOwn(graph, 'pid') ? pidItems(model, refuse) : nodes;
  return model;
}

export function processComponentDetails(model, node) {
  const details = [node.label, ...node.values];
  if (node.kind === 'instrument') return [...details, node.description, ...node.signals, ...(node.associatedFailures ?? []).map(check => `Associated ${node.owner.id}: ${processFailureReason(check)}`)].filter(Boolean);
  if (node.equipment) details.push(node.equipment.description, `Hydraulic component ${node.id}; ${KINDS[node.kind]}.`);
  if (node.kind === 'pipe') details.push(`Route ${node.route_id}`, `Length ${number(node.length_m)} m; bore ${number(node.bore_m * 1000)} mm`,
    `${node.element_ids.length} mechanical elements`, `Bend K ${number(node.bend_loss_coefficient)}: ${node.bend_loss_source}`);
  if (node.kind === 'fixed_loss') details.push(`K ${number(node.loss_coefficient)}: ${node.loss_source}`, 'Outside the mechanical model; no 3D element.');
  if (node.kind === 'mass_flow_source') details.push(`Prescribed source temperature ${number(model.scenario.source_temperature_k)} K`);
  if (node.kind === 'mass_flow_source' || node.kind === 'pressure_sink') details.push(node.equipment
    ? 'Equipment uses a declared hydraulic boundary approximation; outside the mechanical model.'
    : 'Mathematical boundary; no equipment or 3D element implied.');
  if (['pipe', 'fixed_loss'].includes(node.kind) && Number.isFinite(model.requirements?.max_velocity_m_s)) {
    details.push(`Velocity limit ${number(model.requirements.max_velocity_m_s)} m/s`);
  }
  details.push(...node.failures.map(processFailureReason));
  return details;
}

// shortcut: serial circuits use a single column; add a graph layout when branches are supported.
export function processSchematicSvg(model, selectedId = null) {
  if (model.graph.pid) return pidSvg(model, selectedId);
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


const EQUIPMENT = { tank: 'Tank', pump: 'Pump', heat_exchanger: 'Heat exchanger', manual_valve: 'Manual valve', control_valve: 'Control valve' };
const INSTRUMENTS = { PT: 'Pressure transmitter', FT: 'Flow transmitter', PIC: 'Pressure controller', FIC: 'Flow controller' };

function pidItems(model, refuse) {
  const pid = model.graph.pid;
  if (!pid || pid.schema !== 'tuba.process-pid.v1' || !['equipment', 'instruments', 'signals'].every(key => Array.isArray(pid[key]))) refuse();
  const tags = new Set(), components = new Set(), byTag = new Map();
  for (const equipment of pid.equipment) {
    const node = model.nodes.find(item => item.id === equipment.component_id);
    if (!node || !Object.hasOwn(EQUIPMENT, equipment.kind) || components.has(node.id) || typeof equipment.tag !== 'string' ||
        !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(equipment.tag) || tags.has(equipment.tag) ||
        model.nodes.some(item => item.id === equipment.tag && item !== node) || typeof equipment.description !== 'string' || !equipment.description.trim() ||
        (equipment.kind.endsWith('_valve') ? node.kind !== 'fixed_loss' : !['mass_flow_source', 'pressure_sink'].includes(node.kind))) refuse();
    tags.add(equipment.tag); components.add(node.id); byTag.set(equipment.tag, equipment);
    node.equipment = equipment; node.displayTag = equipment.tag; node.label = EQUIPMENT[equipment.kind];
  }
  const instruments = pid.instruments.map(instrument => {
    if (!Object.hasOwn(INSTRUMENTS, instrument.kind) || typeof instrument.tag !== 'string' || !instrument.tag.startsWith(`${instrument.kind}-`) || instrument.tag.length <= instrument.kind.length + 1 ||
        !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(instrument.tag) || tags.has(instrument.tag) ||
        model.nodes.some(node => node.id === instrument.tag) || typeof instrument.description !== 'string' || !instrument.description.trim()) refuse();
    tags.add(instrument.tag); byTag.set(instrument.tag, instrument);
    const transmitter = ['PT', 'FT'].includes(instrument.kind);
    if (transmitter && (typeof instrument.port_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(instrument.port_id))) refuse();
    const owner = transmitter && model.nodes.find(node => node.inlet_port === instrument.port_id || node.outlet_port === instrument.port_id);
    if (transmitter ? !owner : instrument.port_id !== null) refuse();
    const pressure = owner && (owner.inlet_port === instrument.port_id ? owner.pressureIn : owner.pressureOut);
    return { ...instrument, id: instrument.tag, instrumentKind: instrument.kind, kind: 'instrument',
      label: INSTRUMENTS[instrument.kind], element_ids: owner ? owner.element_ids : [], owner,
      values: transmitter ? [`Port ${instrument.port_id}`, instrument.kind === 'PT' ? `Calculated p ${number(pressure / 1000)} kPa abs` : `Calculated flow ${number(owner.massFlow)} kg/s`]
        : ['Design intent only; no controller output calculated.'],
      failures: [], associatedFailures: owner ? owner.failures : [], signals: [] };
  });
  const links = new Set();
  for (const signal of pid.signals) {
    const source = byTag.get(signal.source_tag), target = byTag.get(signal.target_tag);
    const key = `${signal.source_tag}:${signal.target_tag}`;
    if (!source || !target || links.has(key) || !((source.kind === 'PT' && target.kind === 'PIC') ||
        (source.kind === 'FT' && target.kind === 'FIC') || (['PIC', 'FIC'].includes(source.kind) && target.kind === 'control_valve'))) refuse();
    links.add(key);
    for (const instrument of instruments.filter(item => [signal.source_tag, signal.target_tag].includes(item.id))) {
      instrument.signals.push(`Electrical signal: ${signal.source_tag} -> ${signal.target_tag} (declared, not simulated).`);
    }
  }
  for (const controller of instruments.filter(item => ['PIC', 'FIC'].includes(item.instrumentKind))) {
    if (pid.signals.filter(signal => signal.target_tag === controller.id).length !== 1 ||
        pid.signals.filter(signal => signal.source_tag === controller.id).length !== 1) refuse();
  }
  if (pid.equipment.some(item => item.kind === 'control_valve' && pid.signals.filter(signal => signal.target_tag === item.tag).length > 1)) refuse();
  return [...model.nodes, ...instruments];
}

// shortcut: one horizontal serial circuit; use graph layout when the hydraulic model supports branches.
function pidSvg(model, selectedId) {
  const y = 440, height = 790, instruments = model.items.filter(node => node.kind === 'instrument');
  let offset = 30;
  const positions = new Map(model.nodes.map(node => {
    const taps = instruments.filter(item => item.owner === node).sort((a, b) =>
      Number(a.port_id !== node.inlet_port) - Number(b.port_id !== node.inlet_port) || a.id.localeCompare(b.id));
    const width = Math.max(300, 150 * taps.length);
    const position = { x: offset + width / 2, width, taps };
    offset += width;
    return [node.id, position];
  }));
  const width = Math.max(offset + 30, 1140), pid = model.graph.pid, points = new Map();
  const text = (x, y, value, extra = '') => `<text x="${x}" y="${y}" ${extra}>${xml(value)}</text>`;
  const line = (x1, y1, x2, y2, cls = 'process-line') => `<path class="${cls}" d="M${x1} ${y1}H${x2}V${y2}"/>`;
  const group = (node, body) => `<g role="button" tabindex="0" data-process-component="${model.items.indexOf(node)}" data-focus-key="process:component:${model.items.indexOf(node)}" data-component-id="${xml(node.id)}"${node.equipment ? ` data-pid-tag="${xml(node.equipment.tag)}"` : ''} aria-pressed="${node.id === selectedId}" aria-label="${xml([node.displayTag ?? node.id, ...processComponentDetails(model, node)].join('. '))}" class="component${node.failures.length ? ' failed' : ''}${node.id === selectedId ? ' selected' : ''}"><title>${xml([node.displayTag ?? node.id, ...processComponentDetails(model, node)].join('\n'))}</title>${body}</g>`;
  const span = node => node.kind === 'pipe' ? positions.get(node.id).width / 2 - 32 : node.equipment?.kind === 'tank' ? 50 : 30;
  const body = model.nodes.map((node, index) => {
    const { x, width: slot } = positions.get(node.id), half = span(node), kind = node.equipment?.kind;
    points.set(node.equipment?.tag ?? node.id, { x, y: kind === 'control_valve' ? y - 56 : y });
    let symbol;
    if (kind === 'tank') symbol = `<path d="M${x - 50} ${y - 55}v100a50 12 0 0 0 100 0v-100m-100 0a50 12 0 0 0 100 0a50 12 0 0 0 -100 0"/>`;
    else if (kind === 'pump') symbol = `<circle cx="${x}" cy="${y}" r="30"/><path d="M${x - 16} ${y - 20}l36 20l-36 20Z"/>`;
    else if (kind === 'heat_exchanger') symbol = `<circle cx="${x}" cy="${y}" r="30"/><path d="M${x - 21} ${y - 21}l42 42m-42 0l42 -42"/>`;
    else if (kind?.endsWith('_valve')) symbol = `<path d="M${x - 30} ${y - 20}l60 40v-40l-60 40ZM${x} ${y}v-36"/>${kind === 'control_valve' ? `<path d="M${x - 21} ${y - 36}a21 20 0 0 1 42 0Z"/>` : `<path d="M${x - 18} ${y - 36}h36"/>`}`;
    else if (node.kind === 'pipe') symbol = `<path d="M${x - half} ${y}h${half * 2}"/>`;
    else if (node.kind === 'fixed_loss') symbol = `<path d="M${x - 30} ${y}l30 -22l30 22l-30 22Z"/>`;
    else symbol = `<circle cx="${x}" cy="${y}" r="30"/>${text(x, y + 6, node.kind === 'mass_flow_source' ? 'Q' : 'p', 'text-anchor="middle"')}`;
    const previous = model.nodes[index - 1], start = previous && positions.get(previous.id).x + span(previous), end = x - half;
    const connection = previous ? `${line(start, y, end, y)}<path class="process-line" d="M${(start + end) / 2 - 5} ${y - 5}l8 5l-8 5"/>` : '';
    const failed = node.failures[0];
    const failure = failed ? `FAIL: ${number(failed.measured_value)} ${failed.comparator === 'min' ? '<' : '>'} ${number(failed.limit)} ${failed.unit ?? ''}` : '';
    return connection + group(node, `<rect class="hit-box" x="${x - slot / 2 + 10}" y="${y - 72}" width="${slot - 20}" height="294" rx="7"/><g class="symbol">${symbol}</g>
      ${text(x, 526, node.displayTag ?? node.id, 'class="tag" text-anchor="middle"')}
      ${text(x, 549, node.label, 'class="note" text-anchor="middle"')}
      ${node.values.map((value, row) => text(x, 573 + row * 21, value, 'text-anchor="middle"')).join('')}
      ${failure ? text(x, 645, failure, 'class="failure" text-anchor="middle"') : ''}`);
  }).join('');
  const transmitters = instruments.filter(node => node.owner);
  const transmittersSvg = transmitters.map(node => {
    const position = positions.get(node.owner.id), index = position.taps.indexOf(node);
    const x = position.x - position.width / 2 + position.width * (index + .5) / position.taps.length;
    const side = node.owner.inlet_port === node.port_id ? -1 : 1;
    const tapX = position.x + side * span(node.owner);
    points.set(node.id, { x, y: 267 });
    return `<path class="tap-line" d="M${x + side * 28} 267H${x + side * 75}V365H${tapX}V${y}"/><circle class="tap-dot" cx="${tapX}" cy="${y}" r="4"/>` + group(node,
      `<rect class="hit-box" x="${x - 72}" y="231" width="144" height="120" rx="7"/><circle class="symbol" cx="${x}" cy="267" r="28"/>
      ${text(x, 273, node.instrumentKind, 'class="tag" text-anchor="middle"')}${text(x, 312, node.id, 'class="tag" text-anchor="middle"')}
      ${text(x, 336, node.values[1].replace('Calculated ', ''), 'class="reading" text-anchor="middle"')}`);
  }).join('');
  const controllers = instruments.filter(node => !node.owner);
  const controllersSvg = controllers.map(node => {
    const output = pid.signals.find(signal => signal.source_tag === node.id), x = points.get(output.target_tag).x;
    points.set(node.id, { x, y: 145 });
    return group(node, `<rect class="hit-box" x="${x - 80}" y="107" width="160" height="114" rx="7"/><circle class="symbol" cx="${x}" cy="145" r="29"/><path class="symbol" d="M${x - 29} 145h58"/>
      ${text(x, 140, node.instrumentKind, 'class="tag" text-anchor="middle"')}${text(x, 191, node.id, 'class="tag" text-anchor="middle"')}
      ${text(x, 212, 'Control intent only', 'class="note" text-anchor="middle"')}`);
  }).join('');
  const signals = pid.signals.map(signal => {
    const source = points.get(signal.source_tag), target = points.get(signal.target_tag), toController = controllers.some(node => node.id === signal.target_tag);
    const direction = source.x < target.x ? 1 : -1;
    return `<path class="signal-line" data-signal-source="${xml(signal.source_tag)}" data-signal-target="${xml(signal.target_tag)}" d="${toController
      ? Math.abs(source.x - target.x) < 40
        ? `M${source.x} ${source.y - 28}V${target.y + 29}m-5 8l5 -8l5 8`
        : `M${source.x} ${source.y - 28}V145H${target.x - 29 * direction}m${-8 * direction} -5l${8 * direction} 5l${-8 * direction} 5`
      : `M${source.x + 29} ${source.y}h65V${target.y - 23}H${target.x}v23m-5 -8l5 8l5 -8`}"/>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" class="process-pid" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="group" aria-label="P and ID for ${xml(model.graph.network_id)}">
    <title>${xml(model.graph.network_id)} - P&amp;ID</title>
    <desc>Declared equipment and instrumentation; serial process connectivity, not physical scale. Calculated hydraulic values, not sensor readings. Electrical control signals declare intent and are not simulated.</desc>
    <metadata>${xml(JSON.stringify({ schema: 'tuba.process.pid.svg.v1', schematic: model.graph, basis: model.solver, operation: model.operation, pressure_reference: 'absolute', pressure_display_unit: 'kPa', controls: 'design intent, not simulated' }))}</metadata>
    <style>.process-pid text{font:16px sans-serif;fill:#20313b}.process-pid .tag{font-weight:700}.process-pid .note{font-size:14px;fill:#445864}.process-pid .reading{font-size:14px}.process-pid .component{cursor:pointer}.process-pid .hit-box{fill:transparent;stroke:transparent}.process-pid .symbol,.process-pid .process-line,.process-pid .tap-line{fill:none;stroke:#263f4c;stroke-width:2.5}.process-pid .tap-line{stroke-width:1.5}.process-pid .tap-dot{fill:#263f4c}.process-pid .signal-line{fill:none;stroke:#566b7b;stroke-width:1.8;stroke-dasharray:7 5}.process-pid .component.failed .symbol{stroke:#b3261e;stroke-width:3}.process-pid .failure{fill:#a21c15;font-size:15px;font-weight:700}.process-pid .component.selected>.hit-box,.process-pid .component:focus>.hit-box{stroke:#00678a;stroke-width:2;fill:#e2f5fb;fill-opacity:.55}.process-pid .component:focus{outline:none}</style>
    <rect width="100%" height="100%" fill="white"/>
    ${text(30, 32, `${model.graph.network_id} - P&ID`, 'class="tag"')}
    ${text(30, 58, `${model.solver} | ${model.scenario.id} | Calculated results; pressure absolute`, 'class="note"')}
    ${text(30, 82, 'Select an equipment, line or instrument tag to review its hydraulic basis and linked 3D route.', 'class="note"')}
    ${body}${signals}${transmittersSvg}${controllersSvg}
    <path class="process-line" d="M30 701h50"/>${text(90, 707, 'Process / pressure or flow tap', 'class="note"')}
    <path class="signal-line" d="M400 701h50"/>${text(460, 707, 'Electrical signal (design intent)', 'class="note"')}
    <circle class="symbol" cx="835" cy="701" r="14"/><path class="symbol" d="M821 701h28"/>${text(859, 707, 'Panel controller', 'class="note"')}
    ${text(30, 742, 'Equipment uses boundary / fixed-K hydraulic approximations. Controllers do not simulate valve motion or flow control.', 'class="note"')}
    ${text(30, 769, 'Not physical scale. Symbols follow this legend; this drawing does not certify compliance with a P&ID standard.', 'class="note"')}
  </svg>`;
}

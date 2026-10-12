// Synthetic contract fixtures exercise presentation, not engineering acceptance.
import test from 'node:test';
import assert from 'node:assert/strict';
import { processSchematicModel, processSchematicSvg, processComponentDetails } from '../src/processSchematic.js';

function fixture() {
  const components = [
    { id: 'SOURCE-101', kind: 'mass_flow_source', outlet_port: 'source.out', element_ids: [] },
    { id: 'LINE-101', kind: 'pipe', inlet_port: 'line.in', outlet_port: 'line.out', route_id: 'water-route',
      element_ids: ['E1', 'E2'], length_m: 6.2, bore_m: .08, bend_loss_coefficient: .3, bend_loss_source: 'Declared fitting basis' },
    { id: 'LOSS-101', kind: 'fixed_loss', inlet_port: 'loss.in', outlet_port: 'loss.out', loss_coefficient: 2,
      loss_source: 'Manufacturer restriction', mechanical_domain: 'external', element_ids: [] },
    { id: 'SINK-101', kind: 'pressure_sink', inlet_port: 'sink.in', element_ids: [] }
  ];
  const scenario = { id: 'WaterOperating', source_temperature_k: 333.15 };
  const segment = (component_id, element_id, pin, pout) => ({ component_id, element_id, pressure_in_pa: pin,
    pressure_out_pa: pout, velocity_m_s: 4.25, mass_flow_kg_s: 10 });
  return { process: { basis: 'pandapipes', bound_fingerprint: 'abc', scenario_id: scenario.id, operation: 'Hot',
    segments: [segment('LINE-101', 'E1', 500000, 470000), segment('LINE-101', 'E2', 470000, 450000), segment('LOSS-101', null, 450000, 400000)],
    schematic: { schema: 'tuba.process.schematic.v1', network_id: 'water-circuit', bound_fingerprint: 'abc', components,
      connections: components.slice(1).map((component, index) => ({ source_port: components[index].outlet_port, target_port: component.inlet_port })),
      scenario, requirements: { max_velocity_m_s: 3 } } },
    search: { checks: [{ verdict: 'fail', constraint_id: 'flow.velocity.0', entity_refs: ['element:E1'], measured_value: 4.25,
      limit: 3, unit: 'm/s', message: 'Maximum velocity exceeded', basis: 'pandapipes' }] } };
}

test('serial schematic retains IDs and actual component pressure endpoints without inventing boundary elements', () => {
  const model = processSchematicModel(fixture());
  assert.equal(model.solver, 'pandapipes');
  assert.deepEqual(model.nodes.map(node => node.id), ['SOURCE-101', 'LINE-101', 'LOSS-101', 'SINK-101']);
  assert.deepEqual(model.nodes.map(node => node.element_ids), [[], ['E1', 'E2'], [], []]);
  assert.deepEqual(model.nodes.map(node => [node.pressureIn, node.pressureOut]), [[500000, 500000], [500000, 450000], [450000, 400000], [400000, 400000]]);
  assert.deepEqual(model.nodes[1].values, ['Flow 10 kg/s', 'p 500 → 450 kPa abs', 'Max v 4.25 m/s']);
  assert.equal(model.nodes[1].failures.length, 1);
  assert.equal(model.nodes[2].failures.length, 0);
  assert.match(processComponentDetails(model, model.nodes[0]).join('\n'), /Prescribed source temperature 333.15 K/);
  assert.match(processComponentDetails(model, model.nodes[2]).join('\n'), /Outside the mechanical model/);
  assert.match(processComponentDetails(model, model.nodes[1]).join('\n'), /measured 4.25; limit 3 m\/s/);
});

test('source pressure failure is attached to its boundary even without a physical element reference', () => {
  const scene = fixture();
  scene.search.checks = [{ verdict: 'fail', constraint_id: 'flow.source_pressure', entity_refs: [], message: 'Too high', measured_value: 500000, limit: 480000, unit: 'Pa' }];
  const model = processSchematicModel(scene);
  assert.equal(model.nodes[0].failures.length, 1);
  assert.equal(model.nodes[1].failures.length, 0);
});

test('older scenes are absent; unsupported or mismatched results are refused', () => {
  assert.equal(processSchematicModel({}), null);
  const oldScene = fixture();
  delete oldScene.process.schematic;
  assert.equal(processSchematicModel(oldScene), null);
  for (const mutate of [
    scene => { scene.process.schematic.bound_fingerprint = 'other candidate'; },
    scene => { scene.process.schematic.scenario.id = 'other scenario'; },
    scene => { scene.process.basis = 'invented solver'; },
    scene => { scene.process.segments[0].velocity_m_s = NaN; },
    scene => { scene.process.schematic.connections.pop(); },
    scene => { scene.process.schematic.connections[0].target_port = 'disconnected'; },
    scene => { scene.process.schematic.components[1].element_ids.reverse(); },
    scene => { scene.process.schematic.components[0].element_ids = ['fake-source']; },
    scene => { scene.process.segments[0].component_id = 'unknown'; }
  ]) {
    const scene = fixture(); mutate(scene);
    assert.throws(() => processSchematicModel(scene), /does not match/);
  }
});

test('SVG has keyboard buttons, stable metadata, explicit absolute units, selection and failure marks', () => {
  const model = processSchematicModel(fixture());
  const svg = processSchematicSvg(model, 'LINE-101');
  assert.equal(svg, processSchematicSvg(model, 'LINE-101'));
  assert.equal((svg.match(/role="button" tabindex="0"/g) ?? []).length, 4);
  assert.match(svg, /data-component-id="LINE-101" aria-pressed="true"/);
  assert.match(svg, /class="component failed selected"/);
  assert.match(svg, /FAIL · 4.25 &gt; 3 m\/s/);
  assert.match(svg, /kPa abs/);
  assert.match(svg, /&quot;bound_fingerprint&quot;:&quot;abc&quot;/);
  assert.match(svg, /&quot;route_id&quot;:&quot;water-route&quot;/);
  assert.match(svg, /&quot;element_ids&quot;:\[&quot;E1&quot;,&quot;E2&quot;\]/);
  assert.match(svg, /&quot;source_port&quot;:&quot;source.out&quot;/);
  assert.match(svg, /not physical scale/);
  assert.match(svg, /not a control valve/);
  assert.match(svg, /No instrumentation \/ control design/);
  assert.doesNotMatch(svg, /<script|href=|onclick=/);
});

test('free-form engineering notes remain escaped text in visible tooltips and embedded metadata', () => {
  const scene = fixture();
  scene.process.schematic.components[1].bend_loss_source = '<script>alert("x")</script> & \'note\'';
  const svg = processSchematicSvg(processSchematicModel(scene));
  assert.doesNotMatch(svg, /<script>/);
  assert.match(svg, /&lt;script&gt;alert\(&quot;x&quot;\)&lt;\/script&gt; &amp; &apos;note&apos;/);
});

test('external restriction uses explicit check IDs to show velocity failure without any fake physical reference', () => {
  const scene = fixture();
  scene.process.schematic.components[2].velocity_check_ids = ['flow.velocity.2'];
  scene.search.checks.push({ ...scene.search.checks[0], entity_refs: [], constraint_id: 'flow.velocity.2' });
  const model = processSchematicModel(scene);
  assert.equal(model.nodes[2].failures[0].constraint_id, 'flow.velocity.2');
  assert.deepEqual(model.nodes[2].element_ids, []);
  const svg = processSchematicSvg(model, 'LOSS-101');
  assert.match(svg, /data-component-id="LOSS-101" aria-pressed="true"[^>]*class="component failed selected"/s);
});

test('retained OpenModelica results keep their own label and new candidates have no inherited selection', () => {
  const scene = fixture(); scene.process.basis = 'openmodelica';
  const model = processSchematicModel(scene);
  assert.equal(model.solver, 'OpenModelica');
  assert.match(processSchematicSvg(model), /OpenModelica · WaterOperating/);
  assert.doesNotMatch(processSchematicSvg(model), /class="component[^"\n]* selected"/);
});


function pidFixture() {
  const scene = fixture();
  scene.process.schematic.pid = {
    schema: 'tuba.process-pid.v1',
    equipment: [
      { tag: 'TK-101', component_id: 'SOURCE-101', kind: 'tank', description: 'Supply tank' },
      { tag: 'FCV-101', component_id: 'LOSS-101', kind: 'control_valve', description: 'Valve approximated by fixed K' },
      { tag: 'TK-102', component_id: 'SINK-101', kind: 'tank', description: 'Receiving tank' }
    ],
    instruments: [
      { tag: 'PT-101', kind: 'PT', port_id: 'line.in', description: 'Upstream pressure tap' },
      { tag: 'PT-102', kind: 'PT', port_id: 'line.out', description: 'Downstream pressure tap' },
      { tag: 'FT-101', kind: 'FT', port_id: 'line.out', description: 'Outlet mass flow tap' },
      { tag: 'FIC-101', kind: 'FIC', port_id: null, description: 'Flow control intention' }
    ],
    signals: [{ source_tag: 'FT-101', target_tag: 'FIC-101' }, { source_tag: 'FIC-101', target_tag: 'FCV-101' }]
  };
  return scene;
}

function declarationFixture() {
  const scene = pidFixture(), { schematic, bound_fingerprint, scenario_id, operation } = scene.process;
  scene.process = { schema: 'tuba.process.declaration.v1', status: 'not_evaluated', geometry_fingerprint: 'geometry',
    schematic, bound_fingerprint, scenario_id, operation };
  return scene;
}

test('declared P&ID keeps topology, declarations and linked routes without hydraulic readings or failures', () => {
  const scene = declarationFixture(), before = structuredClone(scene), model = processSchematicModel(scene);
  assert.equal(model.evaluated, false);
  assert.equal(model.solver, null);
  assert.deepEqual(model.failures, []);
  assert.deepEqual(model.nodes.map(node => node.element_ids), [[], ['E1', 'E2'], [], []]);
  for (const node of model.nodes) {
    assert.deepEqual(node.values, ['Not evaluated']);
    assert.equal(node.pressureIn, undefined);
    assert.equal(node.massFlow, undefined);
  }
  assert.deepEqual(model.items.find(node => node.id === 'PT-101').values, ['Port line.in', 'Not evaluated']);
  assert.deepEqual(model.items.find(node => node.id === 'FT-101').values, ['Port line.out', 'Not evaluated']);
  assert.match(processComponentDetails(model, model.nodes[1]).join('\n'), /Length 6.2 m; bore 80 mm/);
  const svg = processSchematicSvg(model, 'LINE-101');
  assert.match(svg, /Not evaluated.*Declarations only/s);
  assert.match(svg, /aria-pressed="true"/);
  assert.doesNotMatch(svg, /Calculated (p|flow|results|hydraulic values)|Max v|Flow 0|p 0|FAIL/);
  assert.deepEqual(scene, before);
});

test('draft and evaluated schemas refuse malformed declarations and measured-data contamination', () => {
  for (const mutate of [
    process => { process.status = 'passed'; },
    process => { process.geometry_fingerprint = ''; },
    process => { process.operation = 123; },
    process => { process.segments = []; },
    process => { process.basis = 'pandapipes'; },
    process => { process.provenance = {}; },
    process => { process.checks = []; },
    process => { process.pressure_in_pa = 0; },
    process => { process.schematic.bound_fingerprint = 'other'; },
    process => { process.schematic.connections.pop(); },
    process => { process.schematic.pid.instruments[0].port_id = 'missing'; }
  ]) {
    const scene = declarationFixture(); mutate(scene.process);
    assert.throws(() => processSchematicModel(scene), /does not match/);
  }
  for (const schema of [null, false, 'unknown']) {
    const scene = pidFixture(); scene.process.schema = schema;
    assert.throws(() => processSchematicModel(scene), /does not match/);
  }
});

test('failed source keeps a stale declaration for the previous valid model without inheriting measurements', () => {
  const scene = declarationFixture();
  scene.process.evaluation_status = 'stale';
  scene.process.error = 'Previous valid model; current source failed: ValueError';
  const model = processSchematicModel(scene);
  assert.equal(model.evaluated, false);
  assert.deepEqual(model.failures, []);
  assert.equal(model.items.find(node => node.id === 'PT-101').values[1], 'Not evaluated');
});

test('current process checks own hydraulic failures and legacy scenes keep their fallback checks', () => {
  const scene = pidFixture();
  scene.process.schema = 'tuba.process.review.v1';
  scene.process.checks = [];
  assert.equal(processSchematicModel(scene).failures.length, 0);
  scene.process.checks = [scene.search.checks[0]];
  assert.equal(processSchematicModel(scene).nodes[1].failures.length, 1);
  scene.process.checks = null;
  assert.throws(() => processSchematicModel(scene), /does not match/);
  delete scene.process.checks;
  assert.equal(processSchematicModel(scene).failures.length, 1);
  scene.process.provenance = { solver: 'OpenModelica' };
  assert.throws(() => processSchematicModel(scene), /does not match/);
});

test('P&ID maps equipment and exact port readings to the real component without inventing controller results', () => {
  const model = processSchematicModel(pidFixture()), item = tag => model.items.find(node => node.id === tag);
  assert.equal(model.nodes[0].displayTag, 'TK-101');
  assert.deepEqual(model.nodes[0].element_ids, []);
  assert.match(processComponentDetails(model, model.nodes[0]).join('\n'), /boundary approximation; outside the mechanical model/);
  assert.deepEqual(item('PT-101').values, ['Port line.in', 'Calculated p 500 kPa abs']);
  assert.deepEqual(item('PT-102').values, ['Port line.out', 'Calculated p 450 kPa abs']);
  assert.deepEqual(item('FT-101').values, ['Port line.out', 'Calculated flow 10 kg/s']);
  assert.deepEqual(item('PT-101').element_ids, ['E1', 'E2']);
  assert.deepEqual(item('FT-101').element_ids, ['E1', 'E2']);
  assert.deepEqual(item('PT-101').failures, []);
  assert.match(processComponentDetails(model, item('PT-101')).join('\n'), /Associated LINE-101: flow.velocity.0/);
  assert.deepEqual(item('FIC-101').element_ids, []);
  assert.deepEqual(item('FIC-101').values, ['Design intent only; no controller output calculated.']);
  assert.equal(item('FIC-101').signals.length, 2);
  assert.doesNotMatch(processComponentDetails(model, item('FIC-101')).join('\n'), /kPa|kg\/s/);
});

test('P&ID SVG uses process symbols, instrument bubbles and typed signal links with explicit limitations', () => {
  const scene = pidFixture();
  scene.process.schematic.components[2].velocity_check_ids = ['flow.velocity.2'];
  scene.search.checks.push({ ...scene.search.checks[0], entity_refs: [], constraint_id: 'flow.velocity.2' });
  const model = processSchematicModel(scene), svg = processSchematicSvg(model, 'PT-102');
  assert.equal(svg, processSchematicSvg(model, 'PT-102'));
  assert.equal((svg.match(/role="button" tabindex="0"/g) ?? []).length, 8);
  assert.match(svg, /data-component-id="PT-102" aria-pressed="true"[^>]*class="component selected"/s);
  assert.match(svg, /data-component-id="LOSS-101" data-pid-tag="FCV-101"[^>]*class="component failed"/s);
  assert.doesNotMatch(svg, /data-component-id="PT-10[12]"[^>]*class="component failed/);
  assert.match(svg, /class="tap-line"/);
  assert.match(svg, /class="signal-line" data-signal-source="FT-101" data-signal-target="FIC-101"/);
  assert.match(svg, /class="signal-line" data-signal-source="FIC-101" data-signal-target="FCV-101"/);
  assert.match(svg, /stroke-dasharray:7 5/);
  assert.match(svg, /Panel controller/);
  assert.match(svg, /pressure absolute/);
  assert.match(svg, /Calculated hydraulic values, not sensor readings/);
  assert.match(svg, /Controllers do not simulate valve motion/);
  assert.match(svg, /&quot;port_id&quot;:&quot;line.out&quot;/);
  assert.match(svg, /&quot;bound_fingerprint&quot;:&quot;abc&quot;/);
  assert.match(svg, /&quot;basis&quot;:&quot;pandapipes&quot;/);
  assert.match(svg, /FAIL: 4.25 &gt; 3 m\/s/);
  assert.doesNotMatch(svg, /No instrumentation|not a control valve/);
  assert.doesNotMatch(svg, /<script|href=|onclick=/);
});

test('P&ID render refuses broken tap, equipment and electrical-signal associations', () => {
  for (const mutate of [
    pid => { pid.schema = 'unsupported'; },
    pid => { pid.equipment[0].tag = 101; },
    pid => { pid.equipment[0].description = ' '; },
    pid => { pid.equipment[0].kind = 'toString'; },
    pid => { pid.instruments[0].tag = 'PT-'; },
    pid => { pid.instruments[0].description = ''; },
    pid => { pid.instruments[0].port_id = 'missing.port'; },
    pid => { delete pid.instruments[0].port_id; },
    pid => { pid.instruments[0].port_id = null; },
    pid => { pid.instruments[0].port_id = 123; },
    pid => { pid.instruments[0].tag = 'FT-101'; },
    pid => { pid.instruments[3].port_id = 'line.in'; },
    pid => { pid.equipment[1].component_id = 'LINE-101'; },
    pid => { pid.equipment[0].tag = 'SINK-101'; },
    pid => { pid.equipment.push({ ...pid.equipment[0], tag: 'TK-103' }); },
    pid => { pid.signals[0].source_tag = 'PT-101'; },
    pid => { pid.signals[0].source_tag = 'FCV-101'; },
    pid => { pid.signals[0].source_tag = 'missing'; },
    pid => { pid.signals.pop(); },
    pid => { pid.signals.push({ ...pid.signals[0] }); }
  ]) {
    const scene = pidFixture(); mutate(scene.process.schematic.pid);
    assert.throws(() => processSchematicModel(scene), /does not match/);
  }
});

test('P&ID free-form descriptions are escaped and no symbols alter the existing solver graph', () => {
  const scene = pidFixture(), before = structuredClone(scene);
  scene.process.schematic.pid.equipment[0].description = '<script>alert("equipment")</script>';
  scene.process.schematic.pid.instruments[0].description = '<img onerror="bad"> & tap';
  const svg = processSchematicSvg(processSchematicModel(scene));
  assert.doesNotMatch(svg, /<script|<img/);
  assert.match(svg, /&lt;script&gt;alert\(&quot;equipment&quot;\)&lt;\/script&gt;/);
  assert.match(svg, /&lt;img onerror=&quot;bad&quot;&gt; &amp; tap/);
  assert.deepEqual(scene.process.segments, before.process.segments);
  assert.deepEqual(scene.process.schematic.components, before.process.schematic.components);
});

test('supported boundary symbols and manual valves keep their declared hydraulic approximations', () => {
  for (const kind of ['pump', 'heat_exchanger']) {
    const scene = pidFixture(); scene.process.schematic.pid.equipment[0].kind = kind;
    const model = processSchematicModel(scene);
    assert.match(processSchematicSvg(model), /data-pid-tag="TK-101"/);
    assert.deepEqual(model.nodes[0].element_ids, []);
  }
  const scene = pidFixture(), pid = scene.process.schematic.pid;
  pid.equipment[1].kind = 'manual_valve'; pid.instruments.pop(); pid.signals = [];
  assert.match(processSchematicSvg(processSchematicModel(scene)), /Manual valve/);
});


test('tap placement follows inlet/outlet topology even when instrument declarations are reversed', () => {
  const scene = pidFixture();
  const tapLines = svg => [...svg.matchAll(/<path class="tap-line" d="([^"]+)"/g)].map(match => match[1]).sort();
  const before = tapLines(processSchematicSvg(processSchematicModel(scene)));
  scene.process.schematic.pid.instruments.reverse();
  assert.deepEqual(tapLines(processSchematicSvg(processSchematicModel(scene))), before);
  const horizontalSpans = before.map(path => {
    const [, edge, corridor, tap] = path.match(/^M([\d.]+) 267H([\d.]+)V365H([\d.]+)V440$/);
    const side = Math.sign(Number(corridor) - Number(edge)), center = Number(edge) - side * 28;
    assert.equal(Math.abs(Number(corridor) - center), 75, 'Vertical tap leg stays outside the 144px instrument label area');
    return [Number(tap), Math.min(Number(tap), Number(corridor)), Math.max(Number(tap), Number(corridor))];
  });
  for (const a of horizontalSpans) for (const b of horizontalSpans) {
    if (a[0] !== b[0]) assert.ok(a[2] < b[1] || b[2] < a[1]);
  }
});


test('exact taps reject duplicate graph ports and malformed explicit P&ID declarations', () => {
  const scene = pidFixture();
  scene.process.schematic.components[0].outlet_port = 'line.out';
  scene.process.schematic.connections[0].source_port = 'line.out';
  assert.throws(() => processSchematicModel(scene), /does not match/);
  for (const invalid of [null, false, 0, '']) {
    const invalidScene = pidFixture(); invalidScene.process.schematic.pid = invalid;
    assert.throws(() => processSchematicModel(invalidScene), /does not match/);
  }
  for (const invalid of [undefined, null, '', 101, 'invalid port']) {
    const invalidScene = pidFixture(); invalidScene.process.schematic.components[1].inlet_port = invalid;
    assert.throws(() => processSchematicModel(invalidScene), /does not match/);
  }
  const extraPort = pidFixture(); extraPort.process.schematic.components[0].inlet_port = 'fake.in';
  extraPort.process.schematic.pid.instruments[0].port_id = 'fake.in';
  assert.throws(() => processSchematicModel(extraPort), /does not match/);
});

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

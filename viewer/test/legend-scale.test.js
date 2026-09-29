import assert from "node:assert/strict";
import test from "node:test";

import {
  BAND_COUNT_CHOICES,
  bandCountFor,
  bandEdges,
  effectiveRange,
  isRangeOverridden,
  niceBounds,
  niceStep,
  rampRatio,
  withScale
} from "../src/legendScale.js";

test("a step rounds up to a round number, never down past the data", () => {
  // 51 MPa over 9 bands is 5.67; 6 is the step that still covers 54.
  assert.equal(niceStep(51 / 9), 6);
  // The classic complaint about hard-coded bands is 0.15 against 0.25 - a step
  // set that rounded 0.2 up to 0.5 would make every band under a quarter
  // identical. 0.2 has to keep its own step.
  assert.equal(niceStep(0.2), 0.2);
  // Across a decade, so 5.7e7 over 9 bands is 6.3 MPa, not 60.
  assert.equal(niceStep(51e6 / 9), 6e6);
  assert.equal(niceStep(0), 0);
  assert.equal(niceStep(-4), 0);
  assert.equal(niceStep(NaN), 0);
});

test("a division that lands on a step boundary does not fall through to the next one", () => {
  // 0.3 comes back as 0.30000000000000004 from 1/10*3. Floating noise there used
  // to double every band edge.
  assert.equal(niceStep(0.30000000000000004), 0.3);
  assert.equal(niceStep(2.0000000000000004), 2);
});

test("round bounds give round band increments", () => {
  // The legend a reviewer wants: 0-60 in tens, not 0-57 in 6.3s.
  const bounds = niceBounds(0, 57, 6);
  assert.equal(bounds.min, 0);
  assert.equal(bounds.max, 60);
  assert.equal(bounds.step, 10);
  const edges = bandEdges({ bands: 6, rangeOverride: bounds, range: { min: 0, max: 57 } });
  assert.deepEqual(edges, [0, 10, 20, 30, 40, 50, 60]);
});

test("round bounds also work below one", () => {
  const bounds = niceBounds(0, 0.42, 4);
  assert.equal(bounds.step, 0.1);
  assert.equal(bounds.max, 0.5);
});

test("a flat field gets a usable range instead of dividing by zero", () => {
  const bounds = niceBounds(7, 7, 8);
  assert.equal(bounds.max, bounds.min + 1);
  const edges = bandEdges({ bands: 8, rangeOverride: bounds, range: { min: 7, max: 7 } });
  assert.ok(edges.length > 1);
  assert.ok(edges.every(Number.isFinite));
});

test("a legend with no scale reads exactly the range it always did", () => {
  const legend = { range: { min: 6e6, max: 57e6 } };
  assert.equal(bandCountFor(legend), 0);
  assert.deepEqual(effectiveRange(legend), { min: 6e6, max: 57e6 });
  assert.deepEqual(bandEdges(legend), [6e6, 57e6]);
  assert.equal(isRangeOverridden(legend), false);
  // Continuous behaviour is untouched: a value a quarter of the way up the
  // range lands a quarter of the way up the ramp.
  assert.equal(rampRatio(18.75e6, legend), 0.25);
});

test("banding widens the top edge to a whole band so nothing is clipped away", () => {
  const legend = { bands: 6, range: { min: 0, max: 57 } };
  const { min, max } = effectiveRange(legend);
  assert.equal(min, 0);
  assert.equal(max, 60);
  // The data maximum still lands inside the ramp, not past its end.
  assert.equal(rampRatio(57, legend), 1);
  assert.equal(rampRatio(0, legend), 0);
  // And past the data, the top band holds.
  assert.equal(rampRatio(58, legend), 1);
});

test("a band count of one or zero means continuous", () => {
  for (const bands of [0, 1, -3, 2.4, NaN, null, undefined, "continuous"]) {
    assert.equal(bandCountFor({ bands, range: { min: 0, max: 10 } }), Number.isFinite(bands) && bands >= 2 ? Math.round(bands) : 0);
  }
});

test("banded colours are ranked across the ramp, not sampled at band midpoints", () => {
  // Four bands sampled geometrically would all land inside the middle half of a
  // nine-stop ramp and come out near-identical. Ranking them spreads them over
  // the whole ramp, which is the entire reason to ask for a band count.
  const legend = { bands: 4, range: { min: 0, max: 60 } };
  const ratios = [0, 1, 2, 3].map((index) => rampRatio(index * 15 + 1, legend));
  assert.deepEqual(ratios, [0, 1 / 3, 2 / 3, 1]);
  // Every member of one band gets one identical ratio, so one identical colour.
  assert.equal(rampRatio(1, legend), rampRatio(14.9, legend));
  assert.equal(rampRatio(16, legend), rampRatio(29.9, legend));
});

test("a continuous ramp is untouched by the band ranking path", () => {
  const legend = { range: { min: 0, max: 100 } };
  assert.equal(rampRatio(50, legend), 0.5);
  assert.equal(rampRatio(-10, legend), 0);
  assert.equal(rampRatio(200, legend), 1);
  assert.equal(rampRatio(NaN, legend), 0);
});

test("withScale folds the user's scale in and reports the range the ramp is reading", () => {
  const base = { field: "max_von_mises", unit: "Pa", range: { min: 6e6, max: 57e6 } };
  const scaled = withScale(base, { bands: 6, rangeOverride: { min: 0, max: 60 } });
  assert.equal(scaled.bands, 6);
  assert.equal(scaled.range.min, 0);
  assert.equal(scaled.range.max, 60);
  assert.equal(scaled.field, "max_von_mises");
  // The base legend is not mutated: a field's own declared range is still there
  // to fall back to, and the hotspot swatch reading a stale object would be a
  // worse bug than a wrong colour.
  assert.deepEqual(base.range, { min: 6e6, max: 57e6 });
});

test("a nonsense override is dropped rather than half-applied", () => {
  const base = { range: { min: 0, max: 100 } };
  for (const rangeOverride of [null, { min: 10, max: 10 }, { min: 10, max: 5 }, { min: NaN, max: 10 }, { min: "x", max: 10 }]) {
    const scaled = withScale(base, { bands: 0, rangeOverride });
    assert.equal(scaled.rangeOverride, null);
    assert.deepEqual(scaled.range, { min: 0, max: 100 });
  }
});

test("a tiny range does not spin the band count up", () => {
  const edges = bandEdges({ bands: 16, range: { min: 1e-12, max: 1.0000000000001e-12 } });
  assert.ok(edges.length <= 4098, `band edge count ${edges.length} should be bounded`);
});

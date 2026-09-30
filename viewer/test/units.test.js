import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_UNIT_SYSTEM,
  UNIT_SYSTEMS,
  displayUnit,
  formatElapsed,
  formatNumber,
  formatNumberSeries,
  formatPropertyValue,
  formatQuantity,
  formatUtilization,
  formatValue,
  formatValueSeries,
  getUnitSystem,
  isConvertible,
  nextUnitSystem,
  setUnitSystem,
  toDisplay,
  toStored
} from "../src/units.js";
import { getBodies } from "../src/bodies.js";

test("engineering is the default, because a piping review reads mm and MPa", () => {
  assert.equal(DEFAULT_UNIT_SYSTEM, "engineering");
  assert.equal(getUnitSystem({}), "engineering");
  assert.equal(getUnitSystem({ unitSystem: "si" }), "si");
});

test("an unknown system is ignored rather than half-applied", () => {
  assert.equal(getUnitSystem({ unitSystem: "imperial" }), "engineering");
  const state = setUnitSystem({ unitSystem: "si" }, "furlongs");
  assert.equal(state.unitSystem, "si");
});

test("the chip cycles through every declared system and wraps", () => {
  let state = { unitSystem: UNIT_SYSTEMS[0].id };
  for (let step = 0; step < UNIT_SYSTEMS.length; step += 1) {
    state = setUnitSystem(state, nextUnitSystem(state));
  }
  assert.equal(state.unitSystem, UNIT_SYSTEMS[0].id);
});

test("stored SI restates as engineering units", () => {
  assert.equal(formatQuantity(0.1143, "m", "engineering"), "114.3 mm");
  assert.equal(formatQuantity(1.6075e8, "Pa", "engineering"), "160.8 MPa");
  assert.equal(formatQuantity(3605.55, "N", "engineering"), "3.606 kN");
  assert.equal(formatQuantity(2400, "N*m", "engineering"), "2.4 kN·m");
});

test("SI base leaves stored values exactly as the scene holds them", () => {
  assert.equal(formatQuantity(0.1143, "m", "si"), "0.1143 m");
  assert.equal(formatQuantity(1.6075e8, "Pa", "si"), "1.608e+8 Pa");
  assert.equal(toDisplay(1.6075e8, "Pa", "si"), 1.6075e8);
});

test("a unit the table does not know passes through untouched", () => {
  // Silently rescaling an unrecognised unit would be a lie, and a temperature
  // or a ratio has no second reading to offer.
  for (const unit of ["degC", "C", "ratio", "deg", "kg/m^3", ""]) {
    assert.equal(isConvertible(unit), false);
    assert.equal(toDisplay(120, unit, "engineering"), 120);
    assert.equal(displayUnit(unit, "engineering"), unit);
  }
  assert.equal(formatQuantity(120, "degC", "engineering"), "120 degC");
  assert.equal(formatQuantity(0.95, "", "engineering"), "0.95");
});

test("display and stored are exact inverses, in both systems", () => {
  // This is what keeps a threshold typed in MPa from being compared against
  // pascals and silently filtering out every hotspot.
  for (const system of UNIT_SYSTEMS.map((entry) => entry.id)) {
    for (const [value, unit] of [[5e7, "Pa"], [0.05, "m"], [1200, "N"], [2400, "N*m"], [120, "degC"]]) {
      const shown = toDisplay(value, unit, system);
      assert.equal(toStored(shown, unit, system), value, `${value} ${unit} in ${system}`);
    }
  }
});

test("a threshold typed in MPa reaches state in Pa", () => {
  assert.equal(toStored("50", "Pa", "engineering"), 5e7);
  assert.equal(toStored("50", "Pa", "si"), 50);
});

test("non-finite input yields an empty string, not NaN on screen", () => {
  for (const value of [undefined, null, "", NaN, "abc"]) {
    assert.equal(formatValue(value, "Pa", "engineering"), "");
    assert.equal(formatQuantity(value, "Pa", "engineering"), "");
  }
});

test("four significant figures keeps engineering quantities readable", () => {
  assert.equal(formatNumber(114.3), "114.3");
  assert.equal(formatNumber(0.00602), "0.00602");
  assert.equal(formatNumber(160.75), "160.8");
  assert.equal(formatNumber(57), "57");
  assert.equal(formatNumber(0), "0");
  // Beyond the readable band, exponential rather than a wall of digits.
  assert.equal(formatNumber(1.6075e8), "1.608e+8");
  assert.equal(formatNumber(1e-5), "1e-5");
});

test("display precision follows magnitude without erasing tiny results", () => {
  assert.equal(formatNumber(12.345678901), "12.35");
  assert.equal(formatNumber(0.0000123456789), "1.235e-5");
  assert.equal(formatNumber(-0), "0");
  for (const value of [Number.MIN_VALUE, -Number.MIN_VALUE, 1e-200, -1e200, Number.MAX_VALUE]) {
    assert.notEqual(formatNumber(value), "0");
    assert.doesNotMatch(formatNumber(value), /NaN|Infinity/);
  }
});

test("compared values gain precision only when rounded labels would coincide", () => {
  assert.deepEqual(formatNumberSeries([0, 25, 50, 75, 100]), ["0", "25", "50", "75", "100"]);
  assert.deepEqual(formatValueSeries([100000000, 100001000, 100002000], "Pa"), ["100", "100.001", "100.002"]);
  for (const values of [[999999, 1000000], [1e-12, 1.00001e-12], [-100.001, -100, -99.999]]) {
    assert.equal(new Set(formatNumberSeries(values).map(Number)).size, values.length);
  }
  assert.deepEqual(formatNumberSeries([1, 1, null, NaN]), ["1", "1", "", ""]);
});

test("inspector scalar, vector and nested result values are compact without changing the source", () => {
  const values = { displacement: [0.123456789, -0.0000123456789, 0], row_index: 123456, label: "node:123456789", valid: true };
  const original = JSON.stringify(values);
  assert.equal(formatPropertyValue(values), '{"displacement": [0.1235, -1.235e-5, 0], "row_index": 123456, "label": "node:123456789", "valid": true}');
  assert.equal(JSON.stringify(values), original);
  assert.equal(formatPropertyValue(12.3456789), "12.35");
  assert.equal(formatPropertyValue("12.3456789"), "12.3456789");
  assert.equal(formatPropertyValue(1234567890, "stress"), "1.235e+9");
  assert.equal(formatPropertyValue(1234567890, "element_count"), "1234567890");
  assert.equal(formatPropertyValue([1234567890], "node_ids"), "[1234567890]");
  assert.equal(formatPropertyValue(Infinity), "unavailable");
});

test("rounding never hides which side of the utilization limit a result occupies", () => {
  assert.equal(formatUtilization(0.99996), "<1");
  assert.equal(formatUtilization(1.00004), ">1");
  assert.equal(formatUtilization(1), "1");
  assert.equal(formatUtilization(1.234567), "1.235");
  assert.equal(formatPropertyValue(1.00004, "Utilisation"), ">1");
  assert.equal(formatPropertyValue({ utilization: 1.00004 }), '{"utilization": >1}');
  assert.equal(formatPropertyValue([1.00004], "utilization_values"), "[>1]");
  assert.equal(formatPropertyValue({ pipe1: 1.00004 }, "utilization_values"), '{"pipe1": >1}');
});

test("body metrics follow the unit chip", () => {
  const state = {
    layers: {
      pipe: { id: "pipe", category: "design", count: 1, visible: true, objectIds: ["o:pipe"], source: "object" }
    },
    objects: [
      {
        id: "o:pipe",
        kind: "pipe",
        geometry_asset_id: "geometry:pipe",
        metadata: {
          profile: { outer_diameter_m: 0.1143, wall_thickness_m: 0.00602 },
          bend_geometry: { radius: 0.3429 }
        }
      }
    ],
    objectLayerIds: { "o:pipe": ["pipe"] },
    overlays: [],
    geometryAssets: [],
    geometryPayloads: []
  };
  const engineering = getBodies({ ...state, unitSystem: "engineering" })[0];
  assert.equal(engineering.metrics[1], "OD 114.3 · WT 6.02 · R 342.9 mm");
  const si = getBodies({ ...state, unitSystem: "si" })[0];
  assert.equal(si.metrics[1], "OD 0.1143 · WT 0.00602 · R 0.3429 m");
});

// The header clock that runs while Code_Aster does. A solve emits solve_started
// and solve_finished and nothing between, so this is the only signal that
// separates a run still running from a run that has hung.
test("elapsed time reads as minutes and seconds under an hour", () => {
  assert.equal(formatElapsed(0), "0:00");
  assert.equal(formatElapsed(6_000), "0:06");
  assert.equal(formatElapsed(48_000), "0:48");
  assert.equal(formatElapsed(65_000), "1:05");
  assert.equal(formatElapsed(599_000), "9:59");
});

test("elapsed time grows an hours field rather than counting past 59 minutes", () => {
  assert.equal(formatElapsed(3_599_000), "59:59");
  assert.equal(formatElapsed(3_600_000), "1:00:00");
  assert.equal(formatElapsed(3_661_000), "1:01:01");
});

test("elapsed seconds stay two digits so the header does not jitter", () => {
  for (const ms of [1_000, 9_000, 10_000, 61_000, 3_601_000]) {
    assert.match(formatElapsed(ms), /:\d{2}$/);
  }
});

test("elapsed time is empty rather than wrong for values that are not a duration", () => {
  assert.equal(formatElapsed(-1_000), "");
  assert.equal(formatElapsed(Number.NaN), "");
  assert.equal(formatElapsed(undefined), "");
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_UNIT_SYSTEM,
  UNIT_SYSTEMS,
  displayUnit,
  formatNumber,
  formatQuantity,
  formatValue,
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
  assert.equal(formatQuantity(2400, "N*m", "engineering"), "2.4 kN*m");
});

test("SI base leaves stored values exactly as the scene holds them", () => {
  assert.equal(formatQuantity(0.1143, "m", "si"), "0.1143 m");
  assert.equal(formatQuantity(1.6075e8, "Pa", "si"), "1.61e+8 Pa");
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
  assert.equal(formatNumber(1.6075e8), "1.61e+8");
  assert.equal(formatNumber(1e-5), "1.00e-5");
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

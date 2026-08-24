// Display units.
//
// The scene stores SI base throughout - metres, pascals, newtons - and nothing
// here changes that. This is a presentation layer only: it converts on the way
// to the screen, and back on the way in from an input, so a threshold typed in
// MPa reaches the state in Pa. Values compared against overlay data are always
// in stored units.
//
// Only units the scene actually emits and that have a real engineering
// alternative are converted. Anything else passes through untouched: silently
// rescaling a unit this table does not recognise would be a lie, and a
// temperature or a ratio has no second reading to offer.

export const DEFAULT_UNIT_SYSTEM = "engineering";

export const UNIT_SYSTEMS = Object.freeze([
  { id: "engineering", label: "SI · mm · MPa", title: "Engineering: mm · MPa · kN" },
  { id: "si", label: "SI · m · Pa", title: "SI base: m · Pa · N" }
]);

// quantity -> per-system display unit and the factor from stored SI to it.
const QUANTITIES = Object.freeze({
  length: { si: { unit: "m", factor: 1 }, engineering: { unit: "mm", factor: 1e3 } },
  stress: { si: { unit: "Pa", factor: 1 }, engineering: { unit: "MPa", factor: 1e-6 } },
  force: { si: { unit: "N", factor: 1 }, engineering: { unit: "kN", factor: 1e-3 } },
  moment: { si: { unit: "N*m", factor: 1 }, engineering: { unit: "kN*m", factor: 1e-3 } }
});

// The stored unit strings Tuba emits, mapped onto a quantity.
const UNIT_QUANTITY = Object.freeze({
  m: "length",
  Pa: "stress",
  N: "force",
  "N*m": "moment",
  "N.m": "moment",
  "N-m": "moment"
});

export function getUnitSystem(state) {
  const requested = state?.unitSystem;
  return UNIT_SYSTEMS.some((system) => system.id === requested) ? requested : DEFAULT_UNIT_SYSTEM;
}

export function setUnitSystem(state, systemId) {
  return UNIT_SYSTEMS.some((system) => system.id === systemId) ? { ...state, unitSystem: systemId } : state;
}

export function nextUnitSystem(state) {
  const index = UNIT_SYSTEMS.findIndex((system) => system.id === getUnitSystem(state));
  return UNIT_SYSTEMS[(index + 1) % UNIT_SYSTEMS.length].id;
}

function conversionFor(unit, systemId) {
  const quantity = QUANTITIES[UNIT_QUANTITY[String(unit ?? "").trim()]];
  return quantity?.[systemId] ?? null;
}

// Is this unit one the display layer knows how to restate? Callers that offer a
// unit-bearing input need to know, because an unconvertible unit must keep its
// stored label rather than silently claiming a system it is not in.
export function isConvertible(unit) {
  return conversionFor(unit, DEFAULT_UNIT_SYSTEM) !== null;
}

export function displayUnit(unit, systemId = DEFAULT_UNIT_SYSTEM) {
  return conversionFor(unit, systemId)?.unit ?? String(unit ?? "");
}

// Number(null) and Number("") are both 0, which would print an absent value as
// a reading of zero. Nothing here may invent a measurement, so they are NaN.
function numeric(value) {
  if (value === null || value === undefined || value === "") return Number.NaN;
  const number = Number(value);
  return Number.isFinite(number) ? number : Number.NaN;
}

/** Stored SI value -> the value as displayed. Unknown units pass through. */
export function toDisplay(value, unit, systemId = DEFAULT_UNIT_SYSTEM) {
  const number = numeric(value);
  const conversion = conversionFor(unit, systemId);
  if (!Number.isFinite(number) || !conversion) return number;
  return number * conversion.factor;
}

/** A displayed value -> what to store. The inverse of toDisplay, for inputs. */
export function toStored(value, unit, systemId = DEFAULT_UNIT_SYSTEM) {
  const number = numeric(value);
  const conversion = conversionFor(unit, systemId);
  if (!Number.isFinite(number) || !conversion) return number;
  return number / conversion.factor;
}


/** "160.8 MPa" - the number and its unit, converted together so they agree. */
export function formatQuantity(value, unit, systemId = DEFAULT_UNIT_SYSTEM) {
  const number = formatNumber(toDisplay(value, unit, systemId));
  if (!number) return "";
  const label = displayUnit(unit, systemId);
  return label ? `${number} ${label}` : number;
}

/** Just the number, for readouts that print their unit once (legend ticks). */
export function formatValue(value, unit, systemId = DEFAULT_UNIT_SYSTEM) {
  return formatNumber(toDisplay(value, unit, systemId));
}

// Four significant figures. Enough to keep 114.3 mm and 0.006020 m from
// collapsing to the same precision, few enough that a legend tick stays short.
// Exponential only where a plain decimal would be unreadable.
export function formatNumber(value) {
  const number = numeric(value);
  if (!Number.isFinite(number)) return "";
  if (number === 0) return "0";
  const absolute = Math.abs(number);
  if (absolute >= 1e6 || absolute < 1e-4) return number.toExponential(2);
  return String(Number(number.toPrecision(4)));
}

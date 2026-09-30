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
  // Displayed with a middot: "N*m" is the string Tuba stores and the key this
  // table is looked up by, but a readout is for a reader, not for a parser.
  moment: { si: { unit: "N·m", factor: 1 }, engineering: { unit: "kN·m", factor: 1e-3 } }
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

/** Compared labels share precision, increased only when distinct values collide. */
export function formatValueSeries(values, unit, systemId = DEFAULT_UNIT_SYSTEM) {
  return formatNumberSeries(values.map((value) => toDisplay(value, unit, systemId)));
}

export function formatNumberSeries(values) {
  const numbers = values.map(numeric);
  const distinct = new Set(numbers.filter(Number.isFinite)).size;
  for (let precision = 4; precision <= 17; precision += 1) {
    const labels = numbers.map((value) => formatNumber(value, precision));
    if (new Set(labels.filter(Boolean).map(Number)).size === distinct) return labels;
  }
  return numbers.map((value) => Number.isFinite(value) ? String(value) : "");
}

/** A rounded ratio must still say which side of the limit it lies on. */
export function formatUtilization(value) {
  const number = numeric(value);
  const label = formatNumber(number);
  return number !== 1 && Number(label) === 1 ? `${number > 1 ? ">" : "<"}1` : label;
}

/** Inspector text only; numeric strings, identifiers and counts stay exact. */
export function formatPropertyValue(value, key = "") {
  if (typeof value === "number") {
    if (/utili[sz]ation/i.test(key)) return formatUtilization(value) || "unavailable";
    if (Number.isInteger(value) && /(?:^|_)(?:id|ids|index|indices|count|counts|line|rank)$/.test(key)) return String(value);
    return formatNumber(value) || "unavailable";
  }
  if (Array.isArray(value)) return `[${value.map((item) => propertyItem(item, key)).join(", ")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value).map(([childKey, item]) => `${JSON.stringify(childKey)}: ${propertyItem(item, `${key}_${childKey}`)}`).join(", ")}}`;
  }
  return String(value);
}

function propertyItem(value, key) {
  return typeof value === "string" ? JSON.stringify(value) : formatPropertyValue(value, key);
}

// Elapsed wall time, for the header clock that runs while Code_Aster does.
// m:ss below an hour and h:mm:ss above it, because a solve that has passed an
// hour is a different fact from one that has passed nine minutes and the
// reader should not have to divide to learn which they are looking at.
// Seconds stay two-digit so the width does not change as the count climbs.
export function formatElapsed(milliseconds) {
  const total = Math.floor(numeric(milliseconds) / 1000);
  if (!Number.isFinite(total) || total < 0) return "";
  const seconds = String(total % 60).padStart(2, "0");
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  if (!hours) return `${minutes}:${seconds}`;
  return `${hours}:${String(minutes).padStart(2, "0")}:${seconds}`;
}

// Four significant figures by default; compared labels can request more.
// Exponential only where a plain decimal would be unreadable. Tiny nonzero
// solver values stay nonzero: display formatting cannot infer solver accuracy.
export function formatNumber(value, precision = 4) {
  const number = numeric(value);
  if (!Number.isFinite(number)) return "";
  if (number === 0) return "0";
  const absolute = Math.abs(number);
  if (absolute >= 1e6 || absolute < 1e-4) {
    const [mantissa, exponent] = number.toExponential(precision - 1).split("e");
    return `${Number(mantissa)}e${exponent}`;
  }
  return String(Number(number.toPrecision(precision)));
}

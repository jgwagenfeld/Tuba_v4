// What numbers the colour ramp is actually reading.
//
// The ramp shipped continuous and auto-scaled: min to max of whatever the field
// happens to hold. That spends the whole gradient on the range and leaves the
// two places an engineer works indistinguishable - the bottom two thirds of the
// scale, where nothing is happening, and the top band, where a single sharp
// corner owns the entire top of the ramp. AutoPIPE is the known counterexample:
// six hard-coded bands, with the most-cited complaint in the category being that
// 0.15 and 0.25 get different colours while 0.85 and 0.95 are the same one.
//
// So: a band count, and a range the user can type. Round numbers are the point.
// CATI's post-processing advice is to type bounds like 0-500 MPa so the band
// increments come out at 50, rather than accepting 1.6-to-max and reading
// "6.7" on a legend. This module is where that arithmetic lives so the ramp on
// screen, the legend gradient and the tick labels cannot disagree about it.
//
// Nothing here changes the default. A bundle with no override and no band count
// reads exactly as it did before, because a review tool that reshapes its own
// legend on load invalidates the screenshots and muscle memory people arrived
// with.

const CONTINUOUS = 0;

// The nearest 1/1.5/2/2.5/3/4/5/6/8/10 x 10^k step to `raw`.
//
// Nearest, not up. Rounding up is the obvious choice - a band that clips the top
// of the model is the failure this feature exists to prevent - but it means a
// request for 6 bands never yields 6, only 5 or fewer, and 0.105 snaps to 0.15,
// which is not a round increment at all. Rounding to nearest and letting
// bandEdges extend the top edge to cover the data gets both: the increments
// stay round, the count lands on what was asked for, and nothing is clipped.
//
// 1.5 and 3 are in here alongside the 1/2/2.5/5 of the usual engineering step set
// because a set that only lands on decades rounds 57 MPa up to 100 and throws
// away most of the ramp. Keeping the finer steps means the snapped span stays
// within about half a step of the data, so "nice" never becomes "mostly empty".
const NICE_STEPS = Object.freeze([1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]);

export const BAND_COUNT_CHOICES = Object.freeze([CONTINUOUS, 4, 6, 8, 9, 12, 16]);

export function isContinuous(legend) {
  return bandCountFor(legend) === CONTINUOUS;
}

export function niceStep(raw) {
  if (!Number.isFinite(raw) || raw <= 0) {
    return 0;
  }
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const fraction = raw / magnitude;
  let best = NICE_STEPS[0];
  for (const step of NICE_STEPS) {
    // Strictly closer wins; an exact tie goes to the larger step, so a range of
    // exactly 9.5 steps reads as 0-60 in tens rather than 0-64 in eights.
    if (Math.abs(fraction - step) < Math.abs(fraction - best) - 1e-9) {
      best = step;
    }
  }
  // 3 * 0.1 is 0.30000000000000004 in IEEE754, and that noise walks into every
  // band edge and every tick label. The step is round by construction, so round
  // the product to the precision the decade implies.
  return Number((best * magnitude).toPrecision(12));
}

export function niceBounds(min, max, targetBands) {
  const low = Number.isFinite(Number(min)) ? Number(min) : 0;
  const high = Number.isFinite(Number(max)) ? Number(max) : low;
  if (high <= low) {
    return { min: low, max: low + 1, step: 1 };
  }
  const step = niceStep((high - low) / Math.max(1, bandCountOrZero(targetBands)));
  if (step <= 0) {
    return { min: low, max: high, step: 0 };
  }
  return {
    min: Math.floor(low / step + 1e-9) * step,
    max: Math.ceil(high / step - 1e-9) * step,
    step
  };
}

// The edges a banded ramp is divided at. With a band count the step is snapped
// to a round number and the top edge is allowed to sit above the data's own
// maximum, so the last band is a whole band rather than a sliver. Continuous
// mode reports the two ends and nothing between, which is what the existing
// three-tick legend draws.
export function bandEdges(legend) {
  const { min, max } = effectiveRange(legend);
  const bands = bandCountFor(legend);
  if (bands === CONTINUOUS) {
    return [min, max];
  }
  const step = niceStep((max - min) / bands);
  if (step <= 0) {
    return [min, max];
  }
  const edges = [min];
  // A hard cap guards a pathological field - a range of 0 handled above, but a
  // span so small the step rounds to zero relative to it would otherwise spin.
  const count = Math.min(Math.ceil((max - min) / step), 4096);
  for (let index = 1; index <= count; index += 1) {
    edges.push(min + index * step);
  }
  return edges;
}

// The range the ramp is reading, after any user override, and widened to the
// band grid when banded. Every caller - the 3D tint, the hotspot swatch, the
// legend gradient, the tick labels - goes through this one function, which is
// the only reason the picture and the legend cannot drift apart.
export function effectiveRange(legend) {
  const declared = {
    min: numberOr(legend?.range?.min, 0),
    max: numberOr(legend?.range?.max, 0)
  };
  const override = legend?.rangeOverride ?? null;
  const min = override && Number.isFinite(Number(override.min)) ? Number(override.min) : declared.min;
  const max = override && Number.isFinite(Number(override.max)) ? Number(override.max) : declared.max;
  if (max <= min) {
    return { min, max: min + 1 };
  }
  const bands = bandCountFor(legend);
  if (bands === CONTINUOUS) {
    return { min, max };
  }
  const step = niceStep((max - min) / bands);
  if (step <= 0) {
    return { min, max };
  }
  const count = Math.min(Math.max(Math.ceil((max - min) / step), 1), 4096);
  return { min, max: min + count * step };
}

export function bandCountFor(legend) {
  return bandCountOrZero(legend?.bands);
}

export function bandCountOrZero(value) {
  const count = Number(value);
  if (!Number.isFinite(count) || count < 2) {
    return CONTINUOUS;
  }
  return Math.round(count);
}

// Where a value lands in the ramp, 0 at the bottom and 1 at the top.
//
// Banded, this returns the band's own rank rather than its geometric midpoint,
// and that distinction matters: four bands sampled at their midpoints would all
// land inside the middle half of the ramp and come out near-identical. Ranking
// them 0, 1/3, 2/3, 1 instead spends the whole ramp on the bands the reviewer
// chose, which is the entire reason to choose a band count. Every member of a
// band gets one identical colour, so a band edge reads as an edge instead of as
// another gradient the eye slides past.
export function rampRatio(value, legend) {
  const { min, max } = effectiveRange(legend);
  if (!Number.isFinite(value)) {
    return 0;
  }
  const bands = bandCountFor(legend);
  if (bands === CONTINUOUS) {
    return clamp((value - min) / Math.max(max - min, 1e-12), 0, 1);
  }
  const bandCount = bandEdges(legend).length - 1;
  if (bandCount < 2) {
    return 0;
  }
  const position = clamp((value - min) / Math.max(max - min, 1e-12), 0, 1);
  const index = Math.min(Math.floor(position * bandCount), bandCount - 1);
  return index / (bandCount - 1);
}

export function isRangeOverridden(legend) {
  return Boolean(legend?.rangeOverride);
}

// A legend restated with the user's scale folded in, ready to hand back to the
// renderer. The override is dropped once it is cleared, so `Reset` returns the
// legend to describing the field rather than describing the field plus a ghost.
export function withScale(legend, scale) {
  if (!legend) {
    return legend;
  }
  const bands = bandCountOrZero(scale?.bands);
  const rangeOverride = normalizeOverride(scale?.rangeOverride);
  return {
    ...legend,
    bands,
    rangeOverride,
    range: effectiveRange({ ...legend, bands, rangeOverride })
  };
}

function normalizeOverride(override) {
  if (!override) {
    return null;
  }
  const min = Number(override?.min);
  const max = Number(override?.max);
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
    return null;
  }
  return { min, max };
}

function numberOr(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

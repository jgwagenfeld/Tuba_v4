// Cut view, Custom mode: one two-handle range per axis, and the arithmetic its
// handles and readouts share.
//
// Kept out of app.js so the handlers can be driven in a test: the keyboard step
// and the typed value are the two places a box used to move the wrong way.

import { displayUnit, getUnitSystem, toDisplay, toStored } from "./units.js";

// The keyboard step for one handle. A two-hundredth of the axis is right for a
// whole-model box and useless for the 10 cm box "Around selection" fits to a
// support on a 100 m model, so the step is also never more than a tenth of the
// box it is adjusting.
export function cutHandleStep(span, width) {
  const coarse = span / 200;
  return width > 0 ? Math.min(coarse, width / 10) : coarse;
}

// Where a handle may sit: inside [lo, hi] and never past the other handle.
// Touching is allowed; crossing is not.
export function clampCutHandle(box, axis, side, value, lo = -Infinity, hi = Infinity) {
  const inRange = Math.min(hi, Math.max(lo, value));
  return side === "min" ? Math.min(inRange, box.max[axis]) : Math.max(inRange, box.min[axis]);
}

// One keyboard step: toward the key's direction or nowhere. A step that would
// pass the other handle stops on it. It used to be snapped to a coarse step
// grid first, so ArrowRight on a small box's min handle moved it left.
export function stepCutHandle(box, axis, side, direction, { lo, hi, step }) {
  const current = box[side][axis];
  const next = clampCutHandle(box, axis, side, current + direction * step, lo, hi);
  return direction > 0 ? Math.max(current, next) : Math.min(current, next);
}

// A value typed into a readout, in display units. Null when it is not a number,
// so the readout can refuse it rather than move the cut somewhere unintended.
export function typedCutHandle(box, axis, side, text, systemId) {
  const typed = Number(String(text).trim().replace(",", "."));
  if (String(text).trim() === "" || !Number.isFinite(typed)) return null;
  return clampCutHandle(box, axis, side, toStored(typed, "m", systemId));
}

// Enough decimals that one keyboard step changes the readout, no more: a 2 m
// axis (1 cm steps) reads "-1.03 m" in metres and "-1030 mm" in millimetres.
export function cutReadoutDecimals(displayStep) {
  const magnitude = Math.abs(displayStep);
  if (!Number.isFinite(magnitude) || magnitude === 0) return 0;
  return Math.min(4, Math.max(0, Math.ceil(-Math.log10(magnitude))));
}

const KEY_STEPS = Object.freeze({ ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 });

// Two native range inputs laid over one track per axis: pointer, Home/End and
// screen-reader behaviour come with them. The slider has no step grid
// (step="any"); arrow and page keys are stepped here instead. Dragging only
// previews (re-clip, cheap); release, a key step or a typed value commits the
// box, which also culls whole objects.
export function cutViewRanges(state, { onPreview, onCommit }) {
  const system = getUnitSystem(state);
  const unit = displayUnit("m", system);
  const bounds = state.bounds;
  const box = { mode: "custom", min: [...state.sectionBox.min], max: [...state.sectionBox.max] };
  const commit = () => onCommit({ mode: "custom", min: [...box.min], max: [...box.max] });
  const grid = document.createElement("div");
  grid.className = "cut-view-ranges";
  ["X", "Y", "Z"].forEach((axis, index) => {
    const lo = Math.min(Number(bounds[index]), box.min[index]);
    const hi = Math.max(Number(bounds[index + 3]), box.max[index]);
    const span = hi - lo;
    const step = () => cutHandleStep(span, box.max[index] - box.min[index]);
    const decimals = cutReadoutDecimals(toDisplay(step(), "m", system));
    const format = (value) => {
      const text = toDisplay(value, "m", system).toFixed(decimals);
      return Number(text) === 0 ? (0).toFixed(decimals) : text;
    };

    const name = document.createElement("span");
    name.className = "cut-axis-name";
    name.textContent = axis;
    name.setAttribute("aria-hidden", "true");
    const track = document.createElement("div");
    track.className = "cut-range";
    const fill = document.createElement("div");
    fill.className = "cut-range-fill";

    const handles = ["min", "max"].map((side) => {
      const input = document.createElement("input");
      input.type = "range";
      input.min = String(lo);
      input.max = String(hi);
      input.step = "any";
      input.value = String(box[side][index]);
      input.dataset.focusKey = `cut-view:${axis}:${side}`;
      input.setAttribute("aria-label", `${axis} ${side}`);
      return input;
    });
    const [minInput, maxInput] = handles;
    const readout = document.createElement("span");
    readout.className = "cut-axis-readout";
    const values = ["min", "max"].map((side) => cutReadoutValue(`${axis} ${side}`, `cut-view:${axis}:${side}:value`, (text) => {
      const value = typedCutHandle(box, index, side, text, system);
      if (value === null) return null;
      return () => {
        box[side][index] = value;
        commit();
      };
    }));
    // An en dash, not "…": in the mono face the ellipsis sat on the baseline
    // and read as an underscore.
    readout.append(values[0].element, " – ", values[1].element, ` ${unit}`);

    const sync = () => {
      const fraction = (value) => (span > 0 ? (value - lo) / span : 0);
      const loFraction = fraction(box.min[index]);
      track.style.setProperty("--lo", String(loFraction));
      track.style.setProperty("--hi", String(fraction(box.max[index])));
      // Two handles parked on the same spot: the one that can still move
      // inward has to be on top, or the pair is stuck.
      minInput.style.zIndex = loFraction > 0.5 ? "2" : "";
      values[0].show(format(box.min[index]));
      values[1].show(format(box.max[index]));
      minInput.setAttribute("aria-valuetext", `${format(box.min[index])} ${unit}`);
      maxInput.setAttribute("aria-valuetext", `${format(box.max[index])} ${unit}`);
    };
    for (const [side, input] of [["min", minInput], ["max", maxInput]]) {
      // A drag or Home/End: wherever the pointer says, but never past the other
      // handle.
      input.addEventListener("input", () => {
        const value = clampCutHandle(box, index, side, Number(input.value), lo, hi);
        if (value !== Number(input.value)) input.value = String(value);
        box[side][index] = value;
        sync();
        onPreview(box);
      });
      input.addEventListener("change", commit);
      input.addEventListener("keydown", (event) => {
        const steps = KEY_STEPS[event.key];
        if (!steps) return;
        event.preventDefault();
        const value = stepCutHandle(box, index, side, Math.sign(steps), { lo, hi, step: step() * Math.abs(steps) });
        if (value === box[side][index]) return;
        box[side][index] = value;
        input.value = String(value);
        sync();
        commit();
      });
    }
    sync();
    track.append(fill, minInput, maxInput);
    grid.append(name, track, readout);
  });
  return grid;
}

// A readout that is also a field: click to type an exact value (engineers cut
// at a known elevation), Enter commits, Escape or leaving the field cancels.
// `onEnter` returns the commit to run, or null to refuse the text and keep the
// field open. The field closes first, so focus lands back on the readout.
function cutReadoutValue(label, focusKey, onEnter) {
  const element = document.createElement("span");
  element.className = "cut-readout-value";
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.focusKey = focusKey;
  const field = document.createElement("input");
  field.type = "text";
  field.inputMode = "decimal";
  field.dataset.focusKey = `${focusKey}:edit`;
  field.setAttribute("aria-label", `${label}, exact value`);
  let shown = "";
  let editing = false;
  // Re-entrant: swapping the focused field out fires its blur, which closes
  // again. The flag makes that second close a no-op.
  const close = () => {
    if (!editing) return;
    editing = false;
    element.replaceChildren(button);
  };
  button.addEventListener("click", () => {
    editing = true;
    field.removeAttribute?.("aria-invalid");
    field.value = shown;
    element.replaceChildren(field);
    field.focus();
    field.select?.();
  });
  field.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const apply = onEnter(field.value);
      if (!apply) {
        field.setAttribute("aria-invalid", "true");
        return;
      }
      close();
      button.focus();
      apply();
    } else if (event.key === "Escape") {
      // Escape in the palette would otherwise close it as well.
      event.preventDefault();
      event.stopPropagation();
      close();
      button.focus();
    }
  });
  field.addEventListener("blur", close);
  element.append(button);
  return {
    element,
    show(text) {
      shown = text;
      button.textContent = text;
      button.setAttribute("aria-label", `${label} ${text}, type an exact value`);
      button.title = "Click to type an exact value";
    }
  };
}

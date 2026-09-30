// A dimensioned drawing of one section, in the properties rail.
//
// The manual has a plate of these at docs/content/assets/figures/sections.svg,
// drawn by scripts/docs/generate_section_drawings.py, and this borrows its
// visual language: object outline heavy, bore light, centre lines dashed,
// dimensions in millimetres with a diameter sign where a circle has one. The
// plate cannot be reused here because it is one static figure per kind, and this
// has to draw whatever section the selection actually carries.
//
// **Axes.** Tuba's section loops use a (y, z) pair in which the first coordinate
// is the member depth for an I-beam (its catalog `RY` is H/2) and the first
// extent for a rectangle (`height_y`). `metadata.profile.properties` reports IY
// as the moment *about* the Y axis, so IZ is the depthwise one. The drawing is
// a rotation of that frame, not a different frame: the I-beam is drawn upright
// with H vertical, as the plate has it, and the rectangle with `height_y`
// horizontal, also as the plate has it. Dimensions are labelled by name, so the
// on-screen axes never have to be inferred - and the properties printed beside
// the drawing carry the Y/Z names that the loop frame uses.

import { formatNumber } from "./units.js";

export function formatProfileQuantity(value, unit) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "not computed";
  if (unit === "m2") return `${formatNumber(value * 1e4)} cm²`;
  if (unit === "m4") return `${formatNumber(value * 1e8)} cm⁴`;
  return formatNumber(value);
}

const SVG_NS = "http://www.w3.org/2000/svg";
const SIZE = 168;
const PAD = 28;
const DIA = "Ø";
let diagramId = 0;

//: Root-radius arcs are drawn this finely. A rolled section's fillet is a detail,
//: not the section, and 12 segments keeps its chord error near a hundredth of the
//: drawn width.
const ARC_STEPS = 12;

function el(name, attributes) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function line(x1, y1, x2, y2, className) {
  return el("line", { x1, y1, x2, y2, class: className });
}

function text(x, y, content, { anchor = "middle", rotate = 0, className = "profile-dimension-label" } = {}) {
  const node = el("text", { x, y, "text-anchor": anchor, class: className });
  if (rotate) node.setAttribute("transform", `rotate(${rotate} ${x} ${y})`);
  node.textContent = content;
  return node;
}

function pathFrom(points, close = true) {
  const d = points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
  return el("path", { d: `${d}${close ? " Z" : ""}`, class: "profile-object" });
}

function circle(cx, cy, radius, className) {
  return el("circle", { cx, cy, r: Math.max(radius, 0), class: className });
}

function centreLines(points) {
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const left = Math.min(...xs);
  const right = Math.max(...xs);
  const top = Math.min(...ys);
  const bottom = Math.max(...ys);
  return [
    line(left - 7, (top + bottom) / 2, right + 7, (top + bottom) / 2, "profile-centreline"),
    line((left + right) / 2, top - 7, (left + right) / 2, bottom + 7, "profile-centreline")
  ];
}

function dimensionHorizontal(svg, y, x1, x2, label, offset) {
  svg.append(line(x1, y, x1, y + offset, "profile-extension"));
  svg.append(line(x2, y, x2, y + offset, "profile-extension"));
  svg.append(line(x1, y + offset, x2, y + offset, "profile-dimension"));
  svg.append(text((x1 + x2) / 2, y + offset + 12, label));
}

function dimensionVertical(svg, x, y1, y2, label, offset) {
  svg.append(line(x, y1, x + offset, y1, "profile-extension"));
  svg.append(line(x, y2, x + offset, y2, "profile-extension"));
  svg.append(line(x + offset, y1, x + offset, y2, "profile-dimension"));
  svg.append(text(x + offset - 5, (y1 + y2) / 2, label, { anchor: "end", rotate: -90 }));
}

// --- the five section kinds -------------------------------------------------
// Each drawer returns the drawn outline in screen coordinates so the centre
// lines are struck from the real extent, or null when the profile carries no
// usable dimensions.

function drawPipe(svg, profile, frame) {
  const outer = profile.outer_diameter_m ?? 0;
  if (!(outer > 0)) return null;
  const { cx, cy, scale } = frame;
  const radius = (outer / 2) * scale;
  const bore = profile.inner_diameter_m ?? Math.max(outer - 2 * (profile.wall_thickness_m ?? 0), 0);
  svg.append(circle(cx, cy, radius, "profile-object"));
  if (bore > 0) svg.append(circle(cx, cy, (bore / 2) * scale, "profile-bore"));
  return [[cx - radius, cy - radius], [cx + radius, cy + radius]];
}

function drawBar(svg, profile, frame) {
  const outer = profile.outer_diameter_m ?? 0;
  if (!(outer > 0)) return null;
  const { cx, cy, scale } = frame;
  const radius = (outer / 2) * scale;
  const wall = profile.wall_thickness_m ?? 0;
  svg.append(circle(cx, cy, radius, "profile-object"));
  // WT = 0 is a solid bar, and a hollow one is a circle with a bore. Code_Aster
  // refuses a *solid* BARRE in a POUTRE, so this states Tuba's shape, not a
  // Code_Aster section.
  if (wall > 0) svg.append(circle(cx, cy, Math.max(radius - wall * scale, 0), "profile-bore"));
  return [[cx - radius, cy - radius], [cx + radius, cy + radius]];
}

function drawCable(svg, profile, frame) {
  const radius = profile.radius_m ?? 0;
  if (!(radius > 0)) return null;
  const { cx, cy, scale } = frame;
  const drawn = radius * scale;
  svg.append(circle(cx, cy, drawn, "profile-object"));
  return [[cx - drawn, cy - drawn], [cx + drawn, cy + drawn]];
}

function drawRect(svg, profile, frame) {
  const along = profile.height_y_m ?? 0;
  const up = profile.height_z_m ?? 0;
  if (!(along > 0 && up > 0)) return null;
  const { cx, cy, scale } = frame;
  const wallAlong = profile.thickness_y_m ?? 0;
  const wallUp = profile.thickness_z_m ?? 0;
  const w = along * scale;
  const h = up * scale;
  svg.append(el("rect", { x: cx - w / 2, y: cy - h / 2, width: w, height: h, class: "profile-object" }));
  if (wallAlong > 0 && wallUp > 0) {
    svg.append(el("rect", {
      x: cx - w / 2 + wallAlong * scale,
      y: cy - h / 2 + wallUp * scale,
      width: Math.max(w - 2 * wallAlong * scale, 0),
      height: Math.max(h - 2 * wallUp * scale, 0),
      class: "profile-bore"
    }));
  }
  return [[cx - w / 2, cy - h / 2], [cx + w / 2, cy + h / 2]];
}

// --- the filleted I-section -------------------------------------------------

function modelArc(cu, cv, radius, startDeg, endDeg) {
  const points = [];
  for (let step = 0; step <= ARC_STEPS; step += 1) {
    const angle = ((startDeg + ((endDeg - startDeg) * step) / ARC_STEPS) * Math.PI) / 180;
    points.push([cu + radius * Math.cos(angle), cv + radius * Math.sin(angle)]);
  }
  return points;
}

// The outline of a rolled I-section in model (u, v): u is the depth, v the
// width. The root radii round *re-entrant* corners, so each arc is centred at
// (u0 - R sign(u0), v0 + R sign(v0)) - toward mid-height, away from the web -
// and bulges into the void between the flanges. This is the same construction
// as tuba/sections/properties.py, and drawing the fillet on the other side of
// its own chord would understate the section being labelled.
function ibeamOutline(height, width, web, flange, radius) {
  const halfDepth = height / 2;
  const halfWidth = width / 2;
  const halfWeb = web / 2;
  const underside = halfDepth - flange;
  const r = radius;
  const points = [
    [halfDepth, halfWidth],
    [halfDepth, -halfWidth],
    [underside, -halfWidth],
    [underside, -(halfWeb + r)]
  ];
  if (r > 0) points.push(...modelArc(underside - r, -(halfWeb + r), r, 0, 90));
  points.push([underside - r, -halfWeb], [-underside + r, -halfWeb]);
  if (r > 0) points.push(...modelArc(-underside + r, -(halfWeb + r), r, 90, 180));
  points.push([-underside, -halfWidth], [-halfDepth, -halfWidth], [-halfDepth, halfWidth]);
  points.push([-underside, halfWidth], [-underside, halfWeb + r]);
  if (r > 0) points.push(...modelArc(-underside + r, halfWeb + r, r, 180, 270));
  points.push([-underside + r, halfWeb], [underside - r, halfWeb]);
  if (r > 0) points.push(...modelArc(underside - r, halfWeb + r, r, 270, 360));
  points.push([underside, halfWeb + r], [underside, halfWidth]);
  return points;
}

function drawIbeam(svg, profile, frame) {
  const height = profile.height_m ?? 0;
  const width = profile.width_m ?? 0;
  const web = profile.web_thickness_m ?? 0;
  const flange = profile.flange_thickness_m ?? 0;
  if (!(height > 0 && width > 0 && web > 0 && flange > 0)) return null;
  const { cx, cy, scale } = frame;
  const radius = Math.max(profile.root_radius_m ?? 0, 0);
  // Drawn upright: model u (depth) becomes screen up, so the second coordinate
  // is negated. The fillet arcs stay in model space, where their angles were
  // derived, and are mapped afterwards.
  const points = ibeamOutline(height, width, web, flange, radius).map(([u, v]) => [
    cx + v * scale,
    cy - u * scale
  ]);
  return points;
}

const DRAWERS = Object.freeze({
  pipe: drawPipe,
  bar: drawBar,
  cable: drawCable,
  rectangular: drawRect,
  ibeam: drawIbeam
});

const LABELS = Object.freeze({
  pipe: "Pipe",
  bar: "Bar",
  cable: "Cable",
  rectangular: "Rectangular",
  ibeam: "I-beam"
});

// What the section measures itself by, in the order an engineer asks for it.
// Not every kind has every dimension, and a row reading 0 is a lie, so a
// dimension the profile does not carry is simply not drawn.
function dimensionLines(profile) {
  const kind = String(profile.kind ?? "");
  if (kind === "pipe" || kind === "bar") {
    return [
      [`${DIA}${mm(profile.outer_diameter_m)}`, "width"],
      ...((profile.wall_thickness_m ?? 0) > 0 ? [[`t ${mm(profile.wall_thickness_m)}`, "wall"]] : [])
    ];
  }
  if (kind === "cable") return [[`R${mm(profile.radius_m)}`, "width"]];
  if (kind === "rectangular") {
    return [[mm(profile.height_y_m), "width"], [mm(profile.height_z_m), "height"]];
  }
  return [
    [mm(profile.width_m), "width"],
    [mm(profile.height_m), "height"],
    ...((profile.web_thickness_m ?? 0) > 0 ? [[`tw ${mm(profile.web_thickness_m)}`, "wall"]] : []),
    ...((profile.flange_thickness_m ?? 0) > 0 ? [[`tf ${mm(profile.flange_thickness_m)}`, "wall"]] : [])
  ];
}

function mm(value) {
  return String(Math.round((value ?? 0) * 1000 * 100) / 100);
}

// The screen extents of a section, so a DN20 bar and a 1 m column are both
// legible in the same rail. `along` is horizontal, `up` is vertical.
function frameFor(profile) {
  const kind = String(profile.kind ?? "");
  let along = 0;
  let up = 0;
  if (kind === "pipe" || kind === "bar") along = up = profile.outer_diameter_m ?? 0;
  else if (kind === "cable") along = up = 2 * (profile.radius_m ?? 0);
  else if (kind === "rectangular") {
    along = profile.height_y_m ?? 0;
    up = profile.height_z_m ?? 0;
  } else if (kind === "ibeam") {
    along = profile.width_m ?? 0;
    up = profile.height_m ?? 0;
  }
  const extent = Math.max(along, up);
  if (!(extent > 0)) return null;
  const box = SIZE - 2 * PAD;
  return { cx: SIZE / 2, cy: SIZE / 2, scale: box / extent, along, up };
}

/**
 * The dimensioned drawing of `profile`, or null when the profile is not one of
 * the five kinds Tuba models or carries no usable dimensions.
 */
export function profileDiagram(profile) {
  if (!profile || typeof profile !== "object") return null;
  const kind = String(profile.kind ?? "");
  if (!(kind in DRAWERS)) return null;
  const frame = frameFor(profile);
  if (!frame) return null;

  const svg = el("svg", {
    viewBox: `0 0 ${SIZE} ${SIZE}`,
    width: String(SIZE),
    height: String(SIZE),
    class: "profile-diagram",
    role: "img"
  });
  const entries = dimensionLines(profile);
  svg.setAttribute(
    "aria-label",
    `${LABELS[kind] ?? kind} cross-section, ${entries.map(([value, role]) => `${role} ${value} millimetres`).join(", ")}`
  );

  const group = el("g", {});
  const outline = DRAWERS[kind](group, profile, frame);
  if (!outline) return null;
  const materialId = `profile-material-${++diagramId}`;
  const defs = el("defs", {});
  const pattern = el("pattern", {
    id: `${materialId}-hatch`, width: 6, height: 6,
    patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)"
  });
  pattern.append(line(0, 0, 0, 6, "profile-hatch"));
  const mask = el("mask", { id: materialId, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: SIZE, height: SIZE });
  const materialOutline = DRAWERS[kind](mask, profile, frame);
  if (kind === "ibeam") mask.append(pathFrom(materialOutline));
  // Reuse the section geometry to hatch material while leaving bores transparent.
  for (const shape of mask.children) {
    shape.setAttribute("style", `fill: ${shape.getAttribute("class") === "profile-bore" ? "black" : "white"}; stroke: none`);
  }
  defs.append(pattern, mask);
  svg.append(defs, el("rect", { width: SIZE, height: SIZE, fill: `url(#${materialId}-hatch)`, mask: `url(#${materialId})` }));
  for (const rule of centreLines(outline)) group.append(rule);
  if (kind === "ibeam") group.append(pathFrom(outline));
  svg.append(group);

  const { cx, cy, scale } = frame;
  const halfAlong = (frame.along * scale) / 2;
  const halfUp = (frame.up * scale) / 2;
  const widthLabel = entries.find(([, role]) => role === "width")?.[0];
  const heightLabel = entries.find(([, role]) => role === "height")?.[0];
  if (widthLabel) dimensionHorizontal(svg, cy + halfUp, cx - halfAlong, cx + halfAlong, widthLabel, 13);
  if (heightLabel) dimensionVertical(svg, cx - halfAlong, cy - halfUp, cy + halfUp, heightLabel, -13);
  const wall = entries.filter(([, role]) => role === "wall").map(([value]) => value);
  if (wall.length) svg.append(text(cx, cy - halfUp - 7, wall.join(" · "), { className: "profile-dimension-note" }));
  return svg;
}

/**
 * The derived properties of `profile` as display rows, or a single line saying
 * why they are absent. Section properties are computed from the section's own
 * geometry, so they are labelled as derived and never as a solver result.
 */
export function profilePropertyRows(profile, format) {
  const properties = profile?.properties;
  if (!properties || typeof properties !== "object") return [];
  if (properties.error) {
    return [{ label: "Section properties", value: `not computed — ${properties.error}` }];
  }
  return [
    { label: "Area A", value: format(properties.area_m2, "m2") },
    { label: "IY · about Y", value: format(properties.iy_m4, "m4") },
    { label: "IZ · about Z", value: format(properties.iz_m4, "m4") },
    {
      label: "Torsion J",
      // A thin-wall estimate is a different claim from an exact one, and the
      // difference is up to 40% on a light rolled section.
      value: properties.j_is_exact
        ? format(properties.j_m4, "m4")
        : `${format(properties.j_m4, "m4")} · ${profile.kind === "rectangular" && !profile.thickness_y_m && !profile.thickness_z_m ? "estimate" : "thin-wall estimate"}`
    },
    { label: "Polar moment", value: format(properties.polar_moment_m4, "m4") }
  ];
}

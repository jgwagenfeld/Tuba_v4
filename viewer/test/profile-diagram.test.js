// The section drawing in the properties rail.
//
// The manual has a section plate (docs/content/assets/figures/sections.svg) that
// this borrows its language from, so the two things that could go wrong are worth
// pinning: a profile the drawer does not recognise must draw nothing rather than
// guess, and the I-beam's root radii have to bulge into the void between the
// flanges. Drawing a fillet on the other side of its own chord is the mistake
// this geometry invites, and it understates the section it is labelling - the
// same error cost a tenth of the section area in tuba/sections/properties.py.

import assert from "node:assert/strict";
import test from "node:test";

import { profileDiagram, profilePropertyRows } from "../src/profileDiagram.js";

// A minimal DOM: the drawing is built with createElementNS, setAttribute and
// append, and these tests read the attributes and text back out.
function withDom(run) {
  const original = globalThis.document;
  const make = (tag) => ({
    tagName: String(tag).toUpperCase(),
    children: [],
    attributes: {},
    textContent: "",
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name] ?? null; }
  });
  globalThis.document = { createElementNS: (_ns, tag) => make(tag) };
  const walk = (node, visit) => {
    if (!node) return;
    visit(node);
    for (const child of node.children ?? []) walk(child, visit);
  };
  const textOf = (node) => {
    if (!node) return "";
    return [node.textContent ?? "", ...(node.children ?? []).map(textOf)].join("");
  };
  try {
    return run({
      nodes: (node, tag) => {
        const found = [];
        walk(node, (candidate) => { if (candidate.tagName === tag.toUpperCase()) found.push(candidate); });
        return found;
      },
      text: textOf
    });
  } finally {
    globalThis.document = original;
  }
}

const PIPE = { kind: "pipe", outer_diameter_m: 0.1143, inner_diameter_m: 0.10226, wall_thickness_m: 0.00602 };
const BAR = { kind: "bar", outer_diameter_m: 0.18, wall_thickness_m: 0 };
const CABLE = { kind: "cable", radius_m: 0.04 };
const BOX = { kind: "rectangular", height_y_m: 0.24, height_z_m: 0.14, thickness_y_m: 0.012, thickness_z_m: 0.012 };
const IBEAM = {
  kind: "ibeam", height_m: 0.2, width_m: 0.1,
  web_thickness_m: 0.0056, flange_thickness_m: 0.0085, root_radius_m: 0.012
};

test("every section kind Tuba models draws", () => {
  for (const profile of [PIPE, BAR, CABLE, BOX, IBEAM]) {
    withDom(({ nodes }) => {
      const svg = profileDiagram(profile);
      assert.ok(svg, `${profile.kind} should draw`);
      // The object outline is what makes it a section rather than a box, and it
      // has to be classed: an unclassed SVG path takes the UA default fill and
      // paints the section solid black.
      const outlines = [
        ...nodes(svg, "circle"),
        ...nodes(svg, "path"),
        ...nodes(svg, "rect")
      ];
      assert.ok(outlines.length > 0, `${profile.kind} should draw an outline`);
      assert.ok(
        outlines.some((node) => node.getAttribute("class") === "profile-object"),
        `${profile.kind} outline must carry the profile-object class`
      );
    });
  }
});

test("a kind the drawer does not know draws nothing rather than guessing", () => {
  assert.equal(profileDiagram({ kind: "welded-plate", height_m: 0.2 }), null);
  assert.equal(profileDiagram({}), null);
  assert.equal(profileDiagram(null), null);
});

test("a section with no usable dimension draws nothing", () => {
  // A profile carrying a kind and no numbers is a record, not a shape, and an
  // empty frame with a caption would read as a section of no size.
  assert.equal(profileDiagram({ kind: "ibeam", height_m: 0, width_m: 0 }), null);
  assert.equal(profileDiagram({ kind: "pipe" }), null);
});

test("a solid bar has no bore and a hollow one does", () => {
  withDom(({ nodes }) => {
    assert.equal(nodes(nodes(profileDiagram(BAR), "g")[0], "circle").length, 1, "a solid bar is one circle");
    assert.equal(
      nodes(nodes(profileDiagram({ ...BAR, wall_thickness_m: 0.006 }), "g")[0], "circle").length,
      2,
      "a hollow bar is a circle and a bore"
    );
  });
});

test("a pipe with no bore left is drawn as a solid circle, not a zero-radius one", () => {
  withDom(({ nodes }) => {
    const svg = profileDiagram({ kind: "pipe", outer_diameter_m: 0.05, wall_thickness_m: 0.05 });
    const drawn = nodes(nodes(svg, "g")[0], "circle");
    assert.equal(drawn.length, 1, "a pipe whose wall equals its diameter has no bore to draw");
  });
});

test("section hatching covers material, excludes bores, and uses distinct SVG references", () => {
  withDom(({ nodes }) => {
    const ids = new Set();
    for (const profile of [PIPE, BAR, CABLE, BOX, IBEAM]) {
      const svg = profileDiagram(profile);
      const mask = nodes(svg, "mask")[0];
      const pattern = nodes(svg, "pattern")[0];
      const fill = svg.children.find(node => node.getAttribute("mask"));
      assert.equal(fill.getAttribute("mask"), `url(#${mask.getAttribute("id")})`);
      assert.equal(fill.getAttribute("fill"), `url(#${pattern.getAttribute("id")})`);
      assert.equal(pattern.getAttribute("patternTransform"), "rotate(45)");
      assert.ok(!ids.has(mask.getAttribute("id")), "each diagram needs its own material mask");
      ids.add(mask.getAttribute("id"));
      assert.match(mask.children[0].getAttribute("style"), /fill: white/);
      const bores = mask.children.filter(node => node.getAttribute("class") === "profile-bore");
      assert.equal(bores.length, ["pipe", "rectangular"].includes(profile.kind) ? 1 : 0);
      for (const bore of bores) assert.match(bore.getAttribute("style"), /fill: black/);
      assert.ok(svg.children.indexOf(fill) < svg.children.indexOf(nodes(svg, "g")[0]), "outlines and centre lines stay above the hatching");
    }
  });
});

test("the drawing is labelled with the section's own dimensions in millimetres", () => {
  withDom(({ text: read }) => {
    const label = read(profileDiagram(IBEAM));
    assert.match(label, /100/, "the I-beam's 100 mm flange width is dimensioned");
    assert.match(label, /200/, "the I-beam's 200 mm depth is dimensioned");
    assert.match(label, /tw 5\.6/, "the web thickness is named tw");
    assert.match(label, /tf 8\.5/, "the flange thickness is named tf");
  });
});

test("a circle is dimensioned with a diameter sign and a cable with a radius", () => {
  withDom(({ text: read }) => {
    assert.match(read(profileDiagram(PIPE)), /Ø114\.3/);
    assert.match(read(profileDiagram(CABLE)), /R40/);
  });
});

test("an I-beam is drawn upright, with its depth vertical", () => {
  // The loop frame puts depth on the first coordinate; the drawing rotates it so
  // the section reads the way the manual's plate does. If the rotation were
  // dropped the flanges would be on edge and the section would look like a bar.
  withDom(({ nodes }) => {
    const path = nodes(profileDiagram(IBEAM), "path")[0];
    const ys = path.getAttribute("d").split(/[ML]/).filter(Boolean)
      .map((pair) => Number(pair.split(" ")[1]));
    const xs = path.getAttribute("d").split(/[ML]/).filter(Boolean)
      .map((pair) => Number(pair.split(" ")[0]));
    const height = Math.max(...ys) - Math.min(...ys);
    const width = Math.max(...xs) - Math.min(...xs);
    // 200 deep against 100 wide: the vertical extent must be the larger.
    assert.ok(height > width * 1.5, `expected a tall section, got ${height} by ${width}`);
  });
});

test("the root radius bulges into the void between the flanges", () => {
  // The fillet is a reflex-corner fillet: its centre lies across the corner in
  // the void, and the arc bulges away from the chord towards the void. A drawing
  // that put it on the chord's other side would round the corner off instead,
  // losing the material a rolled section actually has.
  withDom(({ nodes }) => {
    const sharp = profileDiagram({ ...IBEAM, root_radius_m: 0 });
    const filleted = profileDiagram(IBEAM);
    const area = (profile) => {
      const d = nodes(profile, "path")[0].getAttribute("d");
      const pairs = d.split(/[ML]/).filter(Boolean).map((pair) => pair.split(" ").map(Number));
      let total = 0;
      for (let i = 0; i < pairs.length; i += 1) {
        const [x0, y0] = pairs[i];
        const [x1, y1] = pairs[(i + 1) % pairs.length];
        total += x0 * y1 - x1 * y0;
      }
      return Math.abs(total / 2);
    };
    // Each of the four root radii adds R^2 (1 - pi/4) of section. A sign error
    // here would make the filleted section the smaller of the two.
    assert.ok(
      area(filleted) > area(sharp),
      `a filleted I-beam must enclose more than a sharp-cornered one: ${area(filleted)} vs ${area(sharp)}`
    );
  });
});

test("the drawing names itself for a screen reader", () => {
  withDom(() => {
    const svg = profileDiagram(BOX);
    const label = svg.getAttribute("aria-label");
    assert.match(label, /Rectangular cross-section/);
    assert.match(label, /width 240 millimetres/);
    assert.match(label, /height 140 millimetres/);
  });
});

test("section properties are published as derived, and say when they are absent", () => {
  const format = (value, unit) => `${value.toExponential(3)} ${unit}`;
  const rows = profilePropertyRows(
    { kind: "ibeam", properties: { area_m2: 2.848e-3, iy_m4: 1.424e-6, iz_m4: 1.944e-5, j_m4: 5.165e-8, j_is_exact: false, polar_moment_m4: 2.086e-5 } },
    format
  );
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row.value]));
  assert.match(byLabel["Area A"], /2\.848e-3/);
  assert.match(byLabel["IY · about Y"], /1\.424e-6/);
  assert.match(byLabel["IZ · about Z"], /1\.944e-5/);
  // A thin-wall estimate is a different claim from an exact constant, and on a
  // light rolled section it is up to 40% out, so the row has to say which.
  assert.match(byLabel["Torsion J"], /thin-wall estimate/);
});

test("an exact torsion constant is not labelled an estimate", () => {
  const rows = profilePropertyRows(
    { kind: "rectangular", properties: { area_m2: 1, iy_m4: 1, iz_m4: 1, j_m4: 1, j_is_exact: true, polar_moment_m4: 2 } },
    (value) => String(value)
  );
  assert.doesNotMatch(rows.find((row) => row.label === "Torsion J").value, /estimate/);
});

test("solid rectangle torsion is not described as a thin-wall calculation", () => {
  const rows = profilePropertyRows(
    { kind: "rectangular", thickness_y_m: 0, thickness_z_m: 0, properties: { j_m4: 1e-6, j_is_exact: false } },
    String
  );
  const torsion = rows.find(row => row.label === "Torsion J").value;
  assert.match(torsion, /estimate/);
  assert.doesNotMatch(torsion, /thin-wall/);
});

test("a section whose properties could not be computed says so instead of vanishing", () => {
  const rows = profilePropertyRows(
    { kind: "rectangular", properties: { error: "hollow on one axis and solid on the other" } },
    String
  );
  assert.equal(rows.length, 1);
  assert.match(rows[0].value, /not computed/);
  assert.match(rows[0].value, /hollow on one axis/);
});

test("a profile with no property block publishes no property rows", () => {
  // An older bundle carries no `properties` key. The drawing still works, and the
  // table simply has nothing to add rather than a row of zeros.
  assert.deepEqual(profilePropertyRows({ kind: "pipe" }, String), []);
  assert.deepEqual(profilePropertyRows({}, String), []);
});

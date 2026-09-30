import assert from "node:assert/strict";
import test from "node:test";
import { filterProfiles, profileDefinition, profileInsertion } from "../src/profileLibrary.js";

test("profile search, Python quoting, and cursor insertion preserve authored code", () => {
  const rows = [
    { name: "IPE160", family: "IPE", profile: { kind: "ibeam", height_m: .16 } },
    { name: "HE160B", family: "HEB", profile: { kind: "ibeam", height_m: .162 } }
  ];
  assert.deepEqual(filterProfiles(rows, { search: "ipe 160", family: "IPE", minHeight: 150, maxHeight: 170 }), [rows[0]]);
  assert.deepEqual(filterProfiles(rows, { minHeight: 170 }), []);
  assert.equal(profileDefinition(rows[0], 'Beam"one'), 'model.add_ibeam_section("Beam\\"one", profile_name="IPE160")');
  assert.throws(() => profileDefinition(rows[0], " "), /section name/);
  const pipe = { name: "DN100_SCH40", family: "Pipe", nps: "4", schedule: "40",
    profile: { kind: "pipe", outer_diameter_m: .1143, wall_thickness_m: .00602 } };
  assert.deepEqual(filterProfiles([...rows, pipe], { search: "DN100", family: "Pipe", minHeight: 100, maxHeight: 120 }), [pipe]);
  assert.deepEqual(filterProfiles([pipe], { search: "NPS 4" }), [pipe]);
  assert.deepEqual(filterProfiles([pipe], { search: "Sch 40" }), [pipe]);
  assert.equal(profileDefinition(pipe, 'Pipe"one'), 'model.add_pipe_section("Pipe\\"one", OD=0.1143, WT=0.00602)');
  for (const wall of [NaN, Infinity, 0, -.1, .1]) assert.throws(() => profileDefinition({ ...pipe, profile: { ...pipe.profile, wall_thickness_m: wall } }, "bad"), /Invalid pipe dimensions/);
  assert.throws(() => profileDefinition({ profile: { kind: "unsupported" } }, "bad"), /cannot be inserted/);
  const code = "model = Model()\n# keep this\n";
  const at = code.indexOf("# keep");
  const inserted = profileInsertion(code, at, "model.add_ibeam_section()" );
  assert.equal(code.slice(0, inserted.offset) + inserted.text + code.slice(inserted.offset),
    "model = Model()\nmodel.add_ibeam_section()\n# keep this\n");
  assert.equal(profileInsertion(code, at + 3, "section()").offset, at);
});

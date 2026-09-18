import assert from "node:assert/strict";
import test from "node:test";

import { deriveBundleSource } from "../src/bundleSource.js";

function study(loadCase, comm) {
  return {
    kind: "study",
    files: { comm },
    metadata: { solver_input_identity: { load_case: loadCase } }
  };
}

test("a scene without a source script has no source view", () => {
  assert.equal(deriveBundleSource({}, { provenance: [study("Operating", "artifacts/study.comm")] }), null);
  assert.equal(deriveBundleSource(null, null), null);
  assert.equal(deriveBundleSource({ source_uri: "" }, null), null);
});

test("a source script with no review offers model.py and no .comm tabs", () => {
  assert.deepEqual(deriveBundleSource({ source_uri: "source.py" }, null), {
    scriptUri: "source.py",
    loadCases: []
  });
});

test("each study record names its load case and its comm", () => {
  const source = deriveBundleSource(
    { source_uri: "source.py", solver_input_identities: [{ load_case: "Operating" }] },
    { provenance: [study("Operating", "artifacts/study.comm")] }
  );

  assert.deepEqual(source, {
    scriptUri: "source.py",
    loadCases: [{ name: "Operating", uri: "artifacts/study.comm" }]
  });
});

test("load cases follow the scene's order, not provenance order", () => {
  const source = deriveBundleSource(
    { source_uri: "source.py", solver_input_identities: [{ load_case: "local" }, { load_case: "global" }] },
    { provenance: [study("global", "artifacts/global/study.comm"), study("local", "artifacts/local/study.comm")] }
  );

  assert.deepEqual(source.loadCases, [
    { name: "local", uri: "artifacts/local/study.comm" },
    { name: "global", uri: "artifacts/global/study.comm" }
  ]);
});

test("a scene that predates the load-case list falls back to provenance order", () => {
  const source = deriveBundleSource(
    { source_uri: "source.py" },
    { provenance: [study("Wind", "artifacts/study.comm")] }
  );

  assert.deepEqual(source.loadCases, [{ name: "Wind", uri: "artifacts/study.comm" }]);
});

test("repeated study records for one load case collapse to one tab", () => {
  const source = deriveBundleSource(
    { source_uri: "source.py", solver_input_identities: [{ load_case: "Operating" }] },
    { provenance: [study("Operating", "artifacts/study.comm"), study("Operating", "artifacts/study.comm")] }
  );

  assert.deepEqual(source.loadCases, [{ name: "Operating", uri: "artifacts/study.comm" }]);
});

test("a study record without an identity contributes no tab", () => {
  const source = deriveBundleSource(
    { source_uri: "source.py", solver_input_identities: [{ load_case: "Operating" }] },
    { provenance: [{ kind: "study", files: { comm: "artifacts/study.comm" } }] }
  );

  assert.deepEqual(source.loadCases, []);
});

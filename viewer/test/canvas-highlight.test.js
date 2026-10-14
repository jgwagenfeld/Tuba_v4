import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";

const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const source = app.slice(app.indexOf("function renderCanvas()"), app.indexOf("function renderViewportUnavailable()"));

function setup(selectedObjectId = null, connectionHighlightObjectId = null) {
  const calls = { redraws: 0, relations: 0, highlights: [] };
  const runtime = {
    viewportUnavailable: false, selectedObjectId, connectionHighlightObjectId, hoveredObjectId: null,
    currentState: { selectedObjectIds: selectedObjectId ? [selectedObjectId] : [] }, bootId: "test",
    dom: { canvas: {} }, lastRenderGraph: null, renderCameraControls() {}, setStatus() {},
    viewportRenderer: { render: () => ({ renderableObjects: [], diagnostics: [] }),
      redraw: () => calls.redraws++ },
    applySelectionHighlight: (graph, ids) => calls.highlights.push([...ids]), applyHoverHighlight() {},
    getGeometryRelations: () => { calls.relations++; return [{ id: "connected" }]; },
    getHotspots: () => [], getScalarLegend: () => null
  };
  runInNewContext(source, runtime);
  return { calls, render: runtime.renderCanvas };
}

test("an unselected canvas does not request a connection highlight or another draw", () => {
  const { calls, render } = setup();
  render();
  assert.equal(calls.redraws, 0);
  assert.equal(calls.relations, 0);
  assert.deepEqual(calls.highlights, []);
});

test("requested connection highlights still include the selection and its relations", () => {
  const { calls, render } = setup("support", "support");
  render();
  assert.equal(calls.redraws, 1);
  assert.equal(calls.relations, 1);
  assert.deepEqual(calls.highlights, [["support", "connected"]]);
  const different = setup("other", "support");
  different.render();
  assert.equal(different.calls.redraws, 0);
});

import { SCENE_LIMITS, validateJsonBudget } from "./sceneBudget.js";
import { packGeometryArrays } from "./geometryTransfer.js";

self.onmessage = ({ data: { id, bytes, remaining } }) => {
  try {
    const budget = { values: SCENE_LIMITS.values - remaining };
    const value = validateJsonBudget(JSON.parse(new TextDecoder().decode(bytes)), budget);
    // Validate the complete expanded document before sharing any arrays, so
    // repeated geometry still consumes the original receiving quota.
    const packet = packGeometryArrays(value);
    self.postMessage({ id, ...packet, values: budget.values - (SCENE_LIMITS.values - remaining) },
      packet.geometryArrays ? [packet.geometryArrays.buffer] : []);
  }
  catch (error) { self.postMessage({ id, error: error.message }); }
};

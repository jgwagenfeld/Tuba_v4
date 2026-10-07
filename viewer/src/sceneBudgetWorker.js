import { SCENE_LIMITS, validateJsonBudget } from "./sceneBudget.js";

self.onmessage = ({ data: { id, bytes, remaining } }) => {
  try {
    const budget = { values: SCENE_LIMITS.values - remaining };
    const value = validateJsonBudget(JSON.parse(new TextDecoder().decode(bytes)), budget);
    self.postMessage({ id, value, values: budget.values - (SCENE_LIMITS.values - remaining) });
  }
  catch (error) { self.postMessage({ id, error: error.message }); }
};

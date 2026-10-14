// Internal worker transport only. Published scene JSON and renderer inputs keep
// ordinary arrays; equal numeric geometry is delivered once in a Float64 slab.
const NUMERIC_FIELDS = ["vertices", "base_vertices", "faces", "triangles", "indices",
  "surface_edge_indices", "volume_vertices", "volume_edge_indices", "vertex_values",
  "points", "base_points", "cold_points", "starts", "ends", "start_points", "end_points",
  "arrow_starts", "arrow_ends", "crest_points", "values"];

function configsIn(value) {
  const assets = Array.isArray(value) ? value : value?.geometry_assets;
  const configs = Array.isArray(assets) ? assets.map(asset => asset?.generation_config) : [];
  if (value?.generation_config) configs.push(value.generation_config);
  return configs.filter(config => config && typeof config === "object" && !Array.isArray(config));
}

function dimensions(array) {
  if (!Array.isArray(array) || array.length < 8) return null;
  const columns = Array.isArray(array[0]) ? array[0].length : 0;
  if (Array.isArray(array[0]) && !columns) return null;
  const negativeZeros = [];
  let length = 0;
  for (const row of array) {
    if (columns) {
      if (!Array.isArray(row) || row.length !== columns) return null;
      for (const number of row) {
        if (!Number.isFinite(number)) return null;
        if (number === 0 && Object.is(number, -0)) negativeZeros.push(length);
        length++;
      }
    } else {
      if (!Number.isFinite(row)) return null;
      if (row === 0 && Object.is(row, -0)) negativeZeros.push(length);
      length++;
    }
  }
  return { columns, length, signs: negativeZeros.join(",") };
}

function equalNumbers(left, right, columns) {
  if (!columns) return left.every((number, index) => Object.is(number, right[index]));
  return left.every((row, index) => row.every((number, column) => Object.is(number, right[index][column])));
}

export function packGeometryArrays(value) {
  const unique = [], layouts = [], slots = [], byContent = new Map();
  let length = 0;
  configsIn(value).forEach((config, configIndex) => {
    for (const key of NUMERIC_FIELDS) {
      const array = config[key];
      const shape = dimensions(array);
      if (!shape) continue;
      // A sign-aware key prevents many signed-zero patterns from entering one
      // collision bucket and causing quadratic comparisons below the quota.
      const fingerprint = `${JSON.stringify(array)}|${shape.signs}`;
      const candidates = byContent.get(fingerprint) ?? [];
      // JSON stringification conflates -0 with +0. Compare the original numbers
      // as well, preserving every parsed double, including the sign of zero.
      let index = candidates.find(candidate => equalNumbers(array, unique[candidate], shape.columns));
      if (index === undefined) {
        index = unique.length;
        unique.push(array);
        layouts.push([length, shape.length, shape.columns]);
        length += shape.length;
        candidates.push(index);
        byContent.set(fingerprint, candidates);
      }
      slots.push([configIndex, key, index]);
      config[key] = null;
    }
  });
  if (!slots.length) return { value };
  const numbers = new Float64Array(length);
  unique.forEach((array, index) => {
    const [offset, , columns] = layouts[index];
    if (!columns) numbers.set(array, offset);
    else {
      let cursor = offset;
      for (const row of array) for (const number of row) numbers[cursor++] = number;
    }
  });
  return { value, geometryArrays: { buffer: numbers.buffer, layouts, slots } };
}

export function unpackGeometryArrays(packet) {
  const { value, geometryArrays } = packet;
  if (!geometryArrays) return value;
  const numbers = new Float64Array(geometryArrays.buffer);
  const arrays = geometryArrays.layouts.map(([offset, length, columns]) => {
    if (!columns) {
      const array = new Array(length);
      for (let index = 0; index < length; index++) array[index] = numbers[offset + index];
      return array;
    }
    const rows = [];
    for (let row = 0; row < length / columns; row++) {
      const start = offset + row * columns;
      // Exact-size tuple literals avoid both spare capacity in every small
      // coordinate array and a TypedArray view/iterator allocation per row.
      if (columns === 3) rows.push([numbers[start], numbers[start + 1], numbers[start + 2]]);
      else if (columns === 4) rows.push([numbers[start], numbers[start + 1], numbers[start + 2], numbers[start + 3]]);
      else if (columns === 2) rows.push([numbers[start], numbers[start + 1]]);
      else {
        const point = new Array(columns);
        for (let column = 0; column < columns; column++) point[column] = numbers[start + column];
        rows.push(point);
      }
    }
    return rows;
  });
  const configs = configsIn(value);
  // Source geometry is read-only: renderer positions and deformation buffers
  // are separate allocations. Share only source arrays, never rendered objects.
  for (const [configIndex, key, index] of geometryArrays.slots) configs[configIndex][key] = arrays[index];
  return value;
}

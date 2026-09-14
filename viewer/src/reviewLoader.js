const REVIEW_SCHEMA_VERSION = "engineering_review.v1";
const PORTABLE_TABLE_ID = /^[a-z0-9][a-z0-9_-]*$/;

class ReviewContractError extends Error {}

export function normalizeReview(value) {
  if (!isPlainMapping(value)) {
    throw new ReviewContractError("Engineering review must be a JSON object.");
  }
  if (value.schema_version !== REVIEW_SCHEMA_VERSION) {
    throw new ReviewContractError(
      `Engineering review schema_version must be ${REVIEW_SCHEMA_VERSION}.`
    );
  }
  if (typeof value.analysis_status !== "string" || value.analysis_status.length === 0) {
    throw new ReviewContractError("Engineering review analysis_status must be a non-empty string.");
  }
  if (!isPlainMapping(value.tables)) {
    throw new ReviewContractError("Engineering review tables must be a JSON object mapping.");
  }

  const tableEntries = Object.entries(value.tables);
  for (const [tableId, table] of tableEntries) {
    if (!PORTABLE_TABLE_ID.test(tableId)) {
      throw new ReviewContractError(
        `Engineering review table id ${tableId} must be a stable portable identifier.`
      );
    }
    if (!isPlainMapping(table)) {
      throw new ReviewContractError(`Engineering review table ${tableId} must be a JSON object.`);
    }
    validateTable(tableId, table);
  }

  return {
    ...value,
    tables: Object.fromEntries(tableEntries),
    tableOrder: tableEntries.map(([tableId]) => tableId)
  };
}

export async function loadOptionalReview(baseUrl = ".", fetcher = globalThis.fetch) {
  const normalizedBaseUrl = String(baseUrl).replace(/\/+$/, "");
  const uri = `${normalizedBaseUrl}/review.json`;

  try {
    const response = await fetcher(uri);
    if (response.status === 404) {
      return { review: null, diagnostics: [], legacy: true };
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ""}`);
    }
    const review = normalizeReview(await response.json());
    return { review, diagnostics: [], legacy: false };
  } catch (error) {
    return {
      review: null,
      diagnostics: [reviewLoadDiagnostic(error)],
      legacy: false
    };
  }
}

function validateTable(tableId, table) {
  if (table.id !== tableId) {
    throw new ReviewContractError(
      `Engineering review table ${tableId} must declare the same stable id.`
    );
  }
  for (const field of ["title", "source"]) {
    if (typeof table[field] !== "string" || table[field].length === 0) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} ${field} must be a non-empty string.`
      );
    }
  }
  if (!Array.isArray(table.columns)) {
    throw new ReviewContractError(`Engineering review table ${tableId} columns must be an array.`);
  }
  const columnIds = new Set();
  for (const [index, column] of table.columns.entries()) {
    if (!isPlainMapping(column)) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} column ${index} must be a JSON object.`
      );
    }
    if (typeof column.id !== "string" || column.id.length === 0) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} column ${index} id must be a non-empty string.`
      );
    }
    if (columnIds.has(column.id)) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} has duplicate column id ${column.id}.`
      );
    }
    columnIds.add(column.id);
    if (typeof column.label !== "string" || column.label.length === 0) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} column ${column.id} label must be a non-empty string.`
      );
    }
    for (const field of ["unit", "description"]) {
      if (field in column && typeof column[field] !== "string") {
        throw new ReviewContractError(
          `Engineering review table ${tableId} column ${column.id} ${field} must be a string.`
        );
      }
    }
  }
  if (!Array.isArray(table.rows)) {
    throw new ReviewContractError(`Engineering review table ${tableId} rows must be an array.`);
  }
  for (const [index, row] of table.rows.entries()) {
    if (!isPlainMapping(row)) {
      throw new ReviewContractError(
        `Engineering review table ${tableId} row ${index} must be a JSON object.`
      );
    }
    validateJsonValue(row, `Engineering review table ${tableId} row ${index}`);
  }
}

function validateJsonValue(value, path) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new ReviewContractError(`${path} contains a non-finite number.`);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateJsonValue(item, `${path}[${index}]`));
    return;
  }
  if (isPlainMapping(value)) {
    for (const [key, item] of Object.entries(value)) {
      validateJsonValue(item, `${path}.${key}`);
    }
    return;
  }
  throw new ReviewContractError(`${path} contains a non-JSON value.`);
}

function isPlainMapping(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function reviewLoadDiagnostic(error) {
  return {
    severity: "error",
    code:
      error instanceof ReviewContractError
        ? "viewer.review.invalid_contract"
        : "viewer.review.load_failed",
    source: "review.json",
    message: String(error)
  };
}

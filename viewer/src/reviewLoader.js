const REVIEW_SCHEMA_VERSION = "engineering_review.v1";

class ReviewContractError extends Error {}

export function normalizeReview(value) {
  if (!isMapping(value)) {
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
  if (!isMapping(value.tables)) {
    throw new ReviewContractError("Engineering review tables must be a JSON object mapping.");
  }

  const tableEntries = Object.entries(value.tables);
  for (const [tableId, table] of tableEntries) {
    if (!isMapping(table)) {
      throw new ReviewContractError(`Engineering review table ${tableId} must be a JSON object.`);
    }
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

function isMapping(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
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

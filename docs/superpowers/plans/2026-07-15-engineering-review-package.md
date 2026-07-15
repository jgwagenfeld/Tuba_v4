# Engineering Review Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authoritative, deterministic `tuba.reporting` API that builds engineering review tables from `TubaModel`, `AnalysisStudy`, `ResultState`, and `ComplianceReport`, then exports JSON, CSV, and printable HTML alongside an optional existing scene bundle.

**Architecture:** Keep reporting independent of rendering. `tuba.reporting` owns immutable table/provenance records, validation, pure table builders, and export. A thin `tuba.visualization.reporting_adapter` preserves scene-only compatibility and supplies the optional Three.js scene bundle without creating a reporting-to-visualization dependency.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `json`, `csv`, `html`, `pathlib`, existing Tuba domain/analysis/compliance models, pytest/unittest-compatible tests.

## Global Constraints

- Preserve the production chain `TubaModel -> Code_Aster -> ResultState -> review/display`; never create or label proxy values as solver results.
- A model-only review is valid and must be `not_solved`; it must not emit solver-derived or compliance tables.
- Use the exact FE basis label `FE Von Mises (not piping-code stress)`.
- Only `ComplianceReport` data may be called sustained stress, expansion stress, code allowable, code utilization, or compliance.
- Do not import `tuba.visualization` from `tuba.reporting`; scene support belongs in the visualization adapter.
- Keep `tuba.visualization.reports` and `write_static_report(scene, ...)` source-compatible.
- Serialize tables and rows in stable order, sort mapping keys, and keep public links relative.
- Use deterministic Code_Aster fixtures in portable tests. The example may import committed/sample artifact tables, but it must not imply that exporting `.comm`, `.mail`, or `.export` files is a completed solve.

---

### Task 1: Define the immutable review contract and public API

**Files:**

- Create: `tuba/reporting/__init__.py`
- Create: `tuba/reporting/model.py`
- Create: `tests/test_reporting_model.py`

- [ ] **Step 1: Write failing contract tests**

Add tests that construct columns, tables, diagnostics, provenance, and a package; verify stable table lookup, duplicate-table rejection, recursive JSON-safe serialization, and an explicit missing-table error.

```python
from tuba.reporting import (
    EngineeringReviewError,
    EngineeringReviewPackage,
    ReportColumn,
    ReportTable,
)


def test_package_serializes_tables_in_declared_order():
    summary = ReportTable(
        id="project_summary",
        title="Project summary",
        columns=(ReportColumn("project_name", "Project"),),
        rows=({"project_name": "HOT-100"},),
        source="model",
    )
    package = EngineeringReviewPackage(
        package_id="review:hot-100:r0",
        created_at="2026-07-15T00:00:00Z",
        project_name="HOT-100",
        model_standard="ASME_B31.3",
        model_revision=0,
        analysis_status="not_solved",
        tables=(summary,),
    )

    assert package.table("project_summary") is summary
    assert list(package.to_dict()["tables"]) == ["project_summary"]


def test_package_rejects_duplicate_table_ids():
    table = ReportTable(id="nodes", title="Nodes", columns=(), rows=(), source="model")
    with pytest.raises(EngineeringReviewError, match="Duplicate report table"):
        EngineeringReviewPackage(
            package_id="review:test",
            created_at="2026-07-15T00:00:00Z",
            project_name="Test",
            model_standard="ASME_B31.3",
            model_revision=0,
            analysis_status="not_solved",
            tables=(table, table),
        )
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m pytest tests/test_reporting_model.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'tuba.reporting'`.

- [ ] **Step 3: Implement the records and deterministic serialization**

Use frozen dataclasses and tuple-backed collections. Keep the public schema compact and JSON-native.

```python
@dataclass(frozen=True)
class ReportColumn:
    id: str
    label: str
    unit: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            **({"unit": self.unit} if self.unit else {}),
            **({"description": self.description} if self.description else {}),
        }


@dataclass(frozen=True)
class ReviewDiagnostic:
    severity: str
    code: str
    source: str
    message: str
    target: str | None = None


@dataclass(frozen=True)
class ReviewProvenance:
    kind: str
    id: str
    solver_name: str | None = None
    load_case: str | None = None
    files: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportTable:
    id: str
    title: str
    columns: tuple[ReportColumn, ...]
    rows: tuple[Mapping[str, Any], ...]
    source: str
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "columns": [column.to_dict() for column in self.columns],
            "rows": [_json_value(dict(row)) for row in self.rows],
            **({"unavailable_reason": self.unavailable_reason} if self.unavailable_reason else {}),
        }


@dataclass(frozen=True)
class EngineeringReviewPackage:
    package_id: str
    created_at: str
    project_name: str
    model_standard: str
    model_revision: int
    analysis_status: str
    tables: tuple[ReportTable, ...]
    schema_version: str = "engineering_review.v1"
    units: Mapping[str, str] = field(default_factory=lambda: {"length": "m", "force": "N", "stress": "Pa"})
    coordinate_system: Mapping[str, Any] = field(default_factory=lambda: {"up_axis": "Z"})
    provenance: tuple[ReviewProvenance, ...] = ()
    diagnostics: tuple[ReviewDiagnostic, ...] = ()
    scene_uri: str | None = None

    def table(self, table_id: str) -> ReportTable:
        try:
            return self.tables_by_id[table_id]
        except KeyError as error:
            raise EngineeringReviewError(f"Unknown report table {table_id!r}.") from error

    @property
    def tables_by_id(self) -> dict[str, ReportTable]:
        return {table.id: table for table in self.tables}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "created_at": self.created_at,
            "project_name": self.project_name,
            "model_standard": self.model_standard,
            "model_revision": self.model_revision,
            "analysis_status": self.analysis_status,
            "units": _json_value(dict(self.units)),
            "coordinate_system": _json_value(dict(self.coordinate_system)),
            "provenance": [record.to_dict() for record in self.provenance],
            "tables": {table.id: table.to_dict() for table in self.tables},
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            **({"scene_uri": self.scene_uri} if self.scene_uri else {}),
        }
```

Export only these names from `tuba/reporting/__init__.py`: the five records, `EngineeringReviewError`, `build_engineering_review`, and `write_engineering_review`. The builder/export imports may temporarily point to modules added in later tasks only after those modules exist; until then export the records and error.

- [ ] **Step 4: Run the contract tests and confirm GREEN**

Run: `python -m pytest tests/test_reporting_model.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract**

```powershell
git add tuba/reporting/__init__.py tuba/reporting/model.py tests/test_reporting_model.py
git commit -m "feat: define engineering review contract"
```

### Task 2: Build authoritative model/input tables

**Files:**

- Create: `tuba/reporting/tables.py`
- Create: `tests/reporting_fixtures.py`
- Create: `tests/test_reporting_tables.py`
- Modify: `tuba/reporting/model.py`

- [ ] **Step 1: Add a reusable model fixture and failing model-table tests**

Build one model containing pipe and rectangular sections, temperature-dependent material allowables, route/station data, a bend, an anchor, a guide/spring-style support, a named load case, a nodal force, and an operation field. Assert these exact table IDs and important fields:

```python
MODEL_TABLE_IDS = (
    "project_summary",
    "nodes",
    "line_list",
    "section_schedule",
    "materials",
    "supports",
    "load_cases",
)


def test_model_tables_retain_engineering_inputs(review_model):
    tables = build_model_tables(review_model)

    assert tuple(table.id for table in tables) == MODEL_TABLE_IDS
    pipe = next(row for row in _rows(tables, "section_schedule") if row["section"] == "PipeSec")
    assert pipe["outer_diameter_m"] == 0.1143
    assert pipe["wall_thickness_m"] == 0.00602
    assert pipe["corrosion_allowance_m"] == 0.001
    support = next(row for row in _rows(tables, "supports") if row["support_id"] == "SUP-1")
    assert support["blocked_dof"] == [True, True, True, True, True, True]
    hot = next(row for row in _rows(tables, "load_cases") if row["load_case"] == "Hot")
    assert hot["nodal_load_count"] == 1
    assert hot["field_count"] == 1
```

Also assert rows are sorted by stable IDs, section totals include count/length/mass, line-list lengths come from authoritative node coordinates, and every section type serializes all defining dimensions/properties.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `python -m pytest tests/test_reporting_tables.py -q`

Expected: FAIL because `build_model_tables` does not exist.

- [ ] **Step 3: Implement pure model table builders**

Define one builder per table and a stable registry:

```python
MODEL_TABLE_BUILDERS = (
    build_project_summary_table,
    build_nodes_table,
    build_line_list_table,
    build_section_schedule_table,
    build_materials_table,
    build_supports_table,
    build_load_cases_table,
)


def build_model_tables(model: TubaModel, *, analysis_status: str = "not_solved") -> tuple[ReportTable, ...]:
    return tuple(
        builder(model, analysis_status=analysis_status) if builder is build_project_summary_table else builder(model)
        for builder in MODEL_TABLE_BUILDERS
    )
```

Use `math.dist(model.nodes[element.n1].coords, model.nodes[element.n2].coords)` for straight lengths and arc length for bends when radius/angle are present. Flatten load cases only at the summary level; include nested `nodal_forces` and `fields` JSON values so no load definition is lost. Put units on `ReportColumn`, not in values.

- [ ] **Step 4: Run model table tests and confirm GREEN**

Run: `python -m pytest tests/test_reporting_tables.py -q`

Expected: PASS.

- [ ] **Step 5: Commit model tables**

```powershell
git add tuba/reporting/model.py tuba/reporting/tables.py tests/reporting_fixtures.py tests/test_reporting_tables.py
git commit -m "feat: add authoritative model review tables"
```

### Task 3: Validate study/result lineage and build solver-derived tables

**Files:**

- Create: `tuba/reporting/builder.py`
- Create: `tests/test_reporting_builder.py`
- Modify: `tuba/reporting/tables.py`
- Modify: `tuba/reporting/__init__.py`

- [ ] **Step 1: Write failing model-only and lineage-validation tests**

Cover: model-only status; no solver/compliance tables; supplied study table; revision mismatch; missing study link; solver mismatch; load-case mismatch; mesh mismatch; unknown node; unknown element; and non-Code_Aster production result.

```python
def test_model_only_review_is_not_solved_and_has_no_result_tables(review_model):
    review = build_engineering_review(
        review_model,
        package_id="review:model-only",
        created_at="2026-07-15T00:00:00Z",
    )

    assert review.analysis_status == "not_solved"
    assert "displacements" not in review.tables_by_id
    assert "code_compliance" not in review.tables_by_id


@pytest.mark.parametrize("field,value,message", [
    ("model_revision", 9, "model revision"),
    ("study_id", "study:missing", "supplied study"),
    ("mesh_id", "mesh:other", "mesh"),
    ("load_case", "Cold", "load case"),
])
def test_result_lineage_mismatches_raise(review_model, code_aster_study, code_aster_result_state, field, value, message):
    bad = replace(code_aster_result_state, **{field: value})
    with pytest.raises(EngineeringReviewError, match=message):
        build_engineering_review(review_model, studies=[code_aster_study], result_states=[bad])
```

- [ ] **Step 2: Run the builder tests and confirm RED**

Run: `python -m pytest tests/test_reporting_builder.py -q`

Expected: FAIL because `build_engineering_review` does not exist.

- [ ] **Step 3: Implement validation and package status**

Make caller-supplied `package_id` and `created_at` available for reproducible builds; default them only at the public boundary.

```python
def build_engineering_review(
    model: TubaModel,
    *,
    studies: Iterable[AnalysisStudy] = (),
    result_states: Iterable[ResultState] = (),
    compliance_reports: Iterable[ComplianceReport] = (),
    package_id: str | None = None,
    created_at: str | None = None,
) -> EngineeringReviewPackage:
    studies = tuple(studies)
    result_states = tuple(result_states)
    compliance_reports = tuple(compliance_reports)
    _validate_lineage(model, studies, result_states, compliance_reports)
    status = _analysis_status(studies, result_states, compliance_reports)
    diagnostics = build_diagnostics(result_states)
    tables = list(build_model_tables(model, analysis_status=status))
    if studies:
        tables.append(build_studies_table(studies))
    if result_states:
        tables.extend(build_result_tables(model, studies, result_states, compliance_reports=compliance_reports))
    if compliance_reports:
        tables.append(build_compliance_table(studies, result_states, compliance_reports))
    tables.append(build_diagnostics_table(diagnostics))
    return EngineeringReviewPackage(
        package_id=package_id or _default_package_id(model),
        created_at=created_at or _utc_now(),
        project_name=model.project_name,
        model_standard=model.standard,
        model_revision=int(getattr(model, "revision", 0)),
        analysis_status=status,
        tables=tuple(tables),
        provenance=build_provenance(studies, result_states, compliance_reports),
        diagnostics=diagnostics,
    )
```

Treat `int(getattr(model, "revision", 0))` as the current model revision. Require `study.solver_name == result.solver_name == "Code_Aster"` case-insensitively for solver-derived production tables. Compute status as `not_solved`, `partial`, `solved`, or `compliance_complete` from the supplied authoritative records; do not run a solver.

- [ ] **Step 4: Write failing result-table tests**

Assert `studies`, `result_summary`, `displacements`, `reactions`, `element_forces`, `fe_stress`, and `diagnostics`. Every solver row must contain `solver_name`, `study_id`, `result_state_id`, and `load_case`.

```python
def test_fe_stress_is_explicitly_not_code_stress(solved_review):
    row = solved_review.table("fe_stress").rows[0]
    assert row["result_basis"] == "FE Von Mises (not piping-code stress)"
    assert "code_utilization" not in row


def test_result_summary_has_governing_locations(solved_review):
    rows = solved_review.table("result_summary").rows
    assert all(row["governing_entity_ref"] for row in rows)
```

- [ ] **Step 5: Implement studies/result/diagnostic table builders**

Build rows directly from `AnalysisStudy` and `ResultState`. Use six explicit DOF fields (`dx`, `dy`, `dz`, `drx`, `dry`, `drz` or force/moment equivalents), vector magnitudes, both element ends, and entity references such as `node:N1` / `element:pipe_0`. Parser diagnostics from `ResultState.metadata["parser_diagnostics"]` become `ReviewDiagnostic` rows and package diagnostics.

```python
SOLVER_COLUMNS = (
    ReportColumn("solver_name", "Solver"),
    ReportColumn("study_id", "Study ID"),
    ReportColumn("result_state_id", "Result state ID"),
    ReportColumn("load_case", "Load case"),
)


def _solver_identity(study: AnalysisStudy, state: ResultState) -> dict[str, str]:
    return {
        "solver_name": state.solver_name,
        "study_id": study.id,
        "result_state_id": state.id,
        "load_case": state.load_case,
    }
```

Reject a summary maximum if its governing entity cannot be determined.

- [ ] **Step 6: Run builder/table tests and confirm GREEN**

Run: `python -m pytest tests/test_reporting_builder.py tests/test_reporting_tables.py -q`

Expected: PASS.

- [ ] **Step 7: Commit lineage and result tables**

```powershell
git add tuba/reporting/__init__.py tuba/reporting/builder.py tuba/reporting/tables.py tests/test_reporting_builder.py tests/test_reporting_tables.py
git commit -m "feat: build traceable solver review tables"
```

### Task 4: Make compliance code/edition explicit and report only authoritative checks

**Files:**

- Modify: `tuba/compliance/asme_b313.py`
- Modify: `tuba/reporting/builder.py`
- Modify: `tuba/reporting/tables.py`
- Create: `tests/test_reporting_compliance.py`
- Modify: `tests/test_compliance_b31j.py`

- [ ] **Step 1: Write failing compliance metadata and table tests**

```python
def test_compliance_report_states_code_and_edition():
    report = ComplianceReport(load_case="Hot")
    assert report.code_name == "ASME B31.3"
    assert report.code_edition == "2020"


def test_compliance_table_comes_from_compliance_report(full_review):
    row = full_review.table("code_compliance").rows[0]
    assert row["code_name"] == "ASME B31.3"
    assert row["code_edition"] == "2020"
    assert row["sustained_stress_pa"] == full_review_compliance.results[0].sustained_stress
    assert row["entity_ref"] == f"element:{full_review_compliance.results[0].element_id}"
```

Also test that a compliance report with no matching solved load case raises `EngineeringReviewError`, and a solved review without compliance contains no `code_compliance` table and remains `solved`.

- [ ] **Step 2: Run the tests and confirm RED**

Run: `python -m pytest tests/test_reporting_compliance.py tests/test_compliance_b31j.py -q`

Expected: FAIL because `ComplianceReport` has no explicit code metadata and the table is absent.

- [ ] **Step 3: Extend `ComplianceReport` without breaking callers**

Add defaulted fields after existing fields:

```python
@dataclass
class ComplianceReport:
    results: list[ElementComplianceResult] = field(default_factory=list)
    load_case: str | None = None
    code_name: str = "ASME B31.3"
    code_edition: str = "2020"
```

Store the normalized edition on `ASMEB313Evaluator` and construct reports with `code_edition=self.edition`; the current evaluator default is `2020`, while callers selecting `2022` must see `2022` in the report. Update `summary()` to use `code_name` and `code_edition`. Keep existing positional construction of `results` and `load_case` valid.

- [ ] **Step 4: Add compliance validation, rows, and governing summaries**

Emit one row per `ElementComplianceResult`, retaining trace fields (`pressure`, `Do`, `t`, `Z`, `i_i`, `i_o`, `k`, `h`, `M_i`, `M_o`, `M_t`, `moment_basis`, `S_h`, `S_c`, `f`). Link each row to a matching Code_Aster state by load case and add its solver identity. Add governing sustained/expansion rows to `result_summary` with element/node locations.

- [ ] **Step 5: Run compliance and reporting tests and confirm GREEN**

Run: `python -m pytest tests/test_reporting_compliance.py tests/test_compliance_b31j.py tests/test_reporting_builder.py -q`

Expected: PASS.

- [ ] **Step 6: Commit compliance semantics**

```powershell
git add tuba/compliance/asme_b313.py tuba/reporting/builder.py tuba/reporting/tables.py tests/test_reporting_compliance.py tests/test_compliance_b31j.py
git commit -m "feat: report explicit piping code compliance"
```

### Task 5: Export deterministic JSON, CSV, and printable HTML with an optional scene

**Files:**

- Create: `tuba/reporting/export.py`
- Create: `tests/test_reporting_export.py`
- Modify: `tuba/reporting/__init__.py`
- Create: `tuba/visualization/reporting_adapter.py`
- Modify: `tuba/visualization/__init__.py`

- [ ] **Step 1: Write failing artifact-layout and content tests**

```python
def test_write_engineering_review_exports_one_contract_to_all_formats(tmp_path, solved_review):
    output = write_engineering_review(solved_review, tmp_path, title="HOT-100 engineering review")

    payload = json.loads(output.review_path.read_text(encoding="utf-8"))
    manifest = json.loads(output.manifest_path.read_text(encoding="utf-8"))
    html = output.index_path.read_text(encoding="utf-8")
    assert payload == solved_review.to_dict()
    assert manifest["review_uri"] == "review.json"
    assert manifest["reports"]["line_list"] == "reports/line_list.csv"
    assert "@media print" in html
    assert "FE Von Mises (not piping-code stress)" in html
    assert "not solved" not in html.lower()
```

Add tests for model-only unavailable messaging, CSV column order, HTML escaping, relative links, deterministic repeated writes, and `scene=None`. In adapter tests, pass a real `VisualizationScene` and assert the existing `scene.json`, `metadata/`, and `geometry/` layout plus `scene_uri="scene.json"`.

- [ ] **Step 2: Run export tests and confirm RED**

Run: `python -m pytest tests/test_reporting_export.py -q`

Expected: FAIL because the exporter does not exist.

- [ ] **Step 3: Implement renderer-independent export**

The core exporter writes review files and accepts only a scene-writer callback, avoiding visualization imports:

```python
@dataclass(frozen=True)
class EngineeringReviewOutput:
    root: Path
    index_path: Path
    review_path: Path
    manifest_path: Path
    csv_paths: Mapping[str, Path]
    scene_uri: str | None = None


def write_engineering_review(
    review: EngineeringReviewPackage,
    path: str | Path,
    *,
    title: str | None = None,
    scene_writer: Callable[[Path], str | None] | None = None,
) -> EngineeringReviewOutput:
    root = Path(path)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    scene_uri = scene_writer(root) if scene_writer is not None else None
    payload = review.to_dict()
    if scene_uri is not None:
        payload["scene_uri"] = scene_uri
    review_path = root / "review.json"
    _write_json(review_path, payload)
    csv_paths = {table.id: _write_table_csv(table, reports_dir) for table in review.tables if table.rows}
    manifest = _build_manifest(review, csv_paths, scene_uri=scene_uri, title=title)
    manifest_path = root / "report_manifest.json"
    _write_json(manifest_path, manifest)
    index_path = root / "index.html"
    index_path.write_text(_render_html(review, manifest, title=title), encoding="utf-8")
    return EngineeringReviewOutput(
        root=root,
        index_path=index_path,
        review_path=review_path,
        manifest_path=manifest_path,
        csv_paths=csv_paths,
        scene_uri=scene_uri,
    )
```

Write JSON with `indent=2`, `sort_keys=True`, UTF-8, and a trailing newline. CSV headers follow `ReportTable.columns`; nested values are compact sorted JSON. Printable HTML follows Summary -> Model -> Load Cases -> Results -> Compliance -> Diagnostics and uses the same `ReportTable.rows` values.

- [ ] **Step 4: Add the visualization convenience adapter**

Keep the public example signature requested by the design while preserving dependency direction:

```python
def write_engineering_review_with_scene(
    review: EngineeringReviewPackage,
    path: str | Path,
    *,
    scene: VisualizationScene | None = None,
    title: str | None = None,
) -> EngineeringReviewOutput:
    def write_scene(root: Path) -> str:
        write_scene_bundle(scene, root)
        return "scene.json"

    return write_engineering_review(
        review,
        path,
        title=title,
        scene_writer=write_scene if scene is not None else None,
    )
```

Export this adapter from `tuba.visualization`. Document that callers use `tuba.reporting.write_engineering_review` without a scene and `tuba.visualization.write_engineering_review_with_scene` with a scene. Do not make `tuba.reporting` accept or import `VisualizationScene`.

- [ ] **Step 5: Run export and scene-bundle tests and confirm GREEN**

Run: `python -m pytest tests/test_reporting_export.py tests/test_visualization_web_export.py -q`

Expected: PASS.

- [ ] **Step 6: Commit exporters**

```powershell
git add tuba/reporting/__init__.py tuba/reporting/export.py tuba/visualization/__init__.py tuba/visualization/reporting_adapter.py tests/test_reporting_export.py
git commit -m "feat: export engineering review packages"
```

### Task 6: Preserve legacy scene reports and migrate the Code_Aster artifact example

**Files:**

- Modify: `tuba/visualization/reports.py`
- Modify: `tuba/visualization/static_report.py`
- Modify: `tests/test_visualization_reports.py`
- Modify: `tests/test_visualization_static_report.py`
- Modify: `examples/code_aster_artifact_review.py`
- Modify: `tests/test_code_aster_artifact_import.py`
- Modify: `docs/tuba-workflow.md`
- Modify: `docs/architecture/library-architecture-review.md`

- [ ] **Step 1: Add failing compatibility and example tests**

Retain the exact current report function imports/return types. Assert scene-only static HTML clearly says it is a legacy scene-derived report and contains no code-compliance claim. Update the artifact example test to require `review.json`, `report_manifest.json`, representative CSVs, and the scene bundle.

```python
def test_scene_only_static_report_labels_missing_authoritative_inputs(tmp_path):
    report = write_static_report(scene_fixture(), tmp_path)
    html = report.index_path.read_text(encoding="utf-8")
    assert "Legacy scene-derived report" in html
    assert "Code compliance unavailable" in html


def test_artifact_review_example_writes_engineering_review(tmp_path):
    summary = run_example(tmp_path)
    root = Path(summary["bundle_root"])
    assert (root / "review.json").exists()
    assert (root / "reports" / "fe_stress.csv").exists()
    assert (root / "scene.json").exists()
```

- [ ] **Step 2: Run compatibility/example tests and confirm RED**

Run: `python -m pytest tests/test_visualization_reports.py tests/test_visualization_static_report.py tests/test_code_aster_artifact_import.py -q`

Expected: reporting/static legacy tests still pass, while new legacy labeling and `review.json` assertions fail.

- [ ] **Step 3: Implement scene-only compatibility adaptation**

Keep `line_list`, `section_schedule`, `load_case_summary`, `stress_report`, `reaction_report`, `displacement_report`, `build_reports`, and `write_report_csvs` callable with `VisualizationScene`. Update only labels/metadata so FE stress is not called code stress. `write_static_report` may continue its existing layout but must add the legacy warning and unavailable compliance language.

- [ ] **Step 4: Migrate the artifact example to the authoritative review path**

Build the review from the same exported/imported `artifact.study` and `artifact.result_state`; do not synthesize an additional result state.

```python
review = build_engineering_review(
    model,
    studies=[artifact.study],
    result_states=[artifact.result_state],
    package_id="review:code_aster_artifact",
    created_at="2026-06-21T00:00:00Z",
)
output = write_engineering_review_with_scene(
    review,
    output_path / "review_scene",
    scene=scene,
    title="Code_Aster artifact engineering review",
)
```

Continue labeling `_write_sample_result_tables` as a deterministic portable fixture. State in the example docstring/docs that production review values must come from a real Code_Aster run/import.

- [ ] **Step 5: Update workflow and architecture docs**

Show the new function-first review API, distinguish FE stress from piping-code compliance, and preserve both established visualization paths. Avoid describing the report writer as a solver.

- [ ] **Step 6: Run focused compatibility and artifact tests and confirm GREEN**

Run: `python -m pytest tests/test_visualization_reports.py tests/test_visualization_static_report.py tests/test_code_aster_artifact_import.py -q`

Expected: PASS.

- [ ] **Step 7: Commit compatibility and migration**

```powershell
git add tuba/visualization/reports.py tuba/visualization/static_report.py tests/test_visualization_reports.py tests/test_visualization_static_report.py examples/code_aster_artifact_review.py tests/test_code_aster_artifact_import.py docs/tuba-workflow.md docs/architecture/library-architecture-review.md
git commit -m "feat: migrate scene reports to review packages"
```

### Task 7: Regenerate the public review artifact and run package gates

**Files:**

- Modify: `viewer/public/code-aster-review/review.json`
- Modify: `viewer/public/code-aster-review/report_manifest.json`
- Modify: `viewer/public/code-aster-review/index.html`
- Create/Modify: `viewer/public/code-aster-review/reports/*.csv`
- Modify as generated: `viewer/public/code-aster-review/scene.json`
- Modify as generated: `viewer/public/code-aster-review/metadata/*`
- Modify as generated: `viewer/public/code-aster-review/geometry/*`

- [ ] **Step 1: Generate a fresh deterministic artifact**

Run: `python examples/code_aster_artifact_review.py`

Expected: exits 0 and writes `.benchmarks/code_aster_artifact_review/review_scene/review.json`, CSV files, printable HTML, manifest, and the existing scene layout.

- [ ] **Step 2: Inspect semantics before publishing**

Run:

```powershell
rg -n "FE Von Mises \(not piping-code stress\)|Code_Aster|result_state:Hot|not_solved" .benchmarks/code_aster_artifact_review/review_scene/review.json .benchmarks/code_aster_artifact_review/review_scene/index.html
rg -n "code utilization|ASME utilization|certified|approved|signed" .benchmarks/code_aster_artifact_review/review_scene
```

Expected: the first command finds FE basis and provenance; `not_solved` is absent. The second command finds no forbidden claims unless a real `ComplianceReport` was explicitly supplied (this example does not supply one).

- [ ] **Step 3: Publish the generated directory without deleting unrelated files**

Use PowerShell `Copy-Item -Recurse -Force` from `.benchmarks/code_aster_artifact_review/review_scene/*` into `viewer/public/code-aster-review/`, then inspect `git status --short` and the generated diff. Do not overwrite user changes outside this directory.

- [ ] **Step 4: Run all Python review and visualization gates**

Run:

```powershell
python -m pytest tests/test_reporting_model.py tests/test_reporting_tables.py tests/test_reporting_builder.py tests/test_reporting_compliance.py tests/test_reporting_export.py -q
python -m pytest tests/test_visualization_reports.py tests/test_visualization_static_report.py tests/test_visualization_web_export.py tests/test_code_aster_artifact_import.py -q
python -m pytest -q
```

Expected: all PASS. If the full suite is blocked by an optional dependency/runtime, record the exact boundary and keep focused proof.

- [ ] **Step 5: Run the real Code_Aster smoke gate when configured**

First locate the repository-supported gate:

Run: `rg -n "real.*Code_Aster|Code_Aster.*smoke|ASTER_ROOT|as_run" tests scripts docs pyproject.toml`

Run the discovered documented command only when its runtime is configured. Expected: PASS with real Code_Aster artifacts. If unavailable, report the runtime/setup blocker explicitly; do not substitute export-only success.

- [ ] **Step 6: Commit the generated review artifact**

```powershell
git add viewer/public/code-aster-review
git commit -m "docs: publish engineering review package artifact"
```

- [ ] **Step 7: Confirm a clean handoff**

Run: `git status --short`

Expected: no output, apart from pre-existing user-owned changes that were deliberately left untouched and documented.

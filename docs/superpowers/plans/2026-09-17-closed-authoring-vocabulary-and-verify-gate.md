# One Verify Gate and a Model-Script Lint — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Tuba one verification gate that every solving surface calls, and a lint that keeps an authored `model.py` to the builder/unit vocabulary, so a model cannot be solved after silently skipping validation, clash detection or rules.

**Architecture:** Two new surfaces built on the existing checks. `tuba/verify.py` composes `validate_model` (`tuba/validation.py`), `ClashEngine.check_all` (`tuba/clash/engine.py`) and the `RuleEngine` (`tuba/rules.py`) into one `VerifyReport`, exposed as `TubaModel.verify(...)` and as the MCP `verify_model` tool. `check_model_script` joins `check_unit_style` as a lint over the model script itself; it skips generated scripts, returns findings as advisories, and is surfaced through the same gate. Wiring lands at the chokepoints that already load a project — `tuba/project/__init__.py`, `tuba/mcp/server.py` — and the teaching surfaces (`tuba/skills/tuba-modeling/SKILL.md`) call the gate instead of hand-wiring checks.

**Tech Stack:** Python 3, pytest. No Code_Aster run is needed for either task.

**Spec:** `docs/adr/0004-closed-authoring-vocabulary-and-one-verify-gate.md`.

## Global Constraints

- **Compose, do not replace.** `validate_model`, `ClashEngine.check_all` and `RuleEngine` keep their signatures and tests. `verify_model` composes them; it never re-implements a check.
- **Keep the facade small (ADR 0001).** `verify_model` lives in `tuba/verify.py`. Do not add it to `tuba/__init__.py`; the discoverable path is the `TubaModel.verify()` method.
- **No import cycle.** `tuba/rules.py` imports `tuba.model`, so `tuba/verify.py` must not be imported at module scope anywhere in `tuba/model.py`. `TubaModel.verify` imports `tuba.verify` lazily inside the method.
- **No optional-stack import at package import.** `import tuba` must still leave `scipy`, `trimesh` and `meshio` unloaded (`tests/test_public_api.py::test_import_does_not_load_optional_geometry_stack`). `tuba/verify.py` is not imported by `tuba/__init__.py`.
- **Blocking vs advisory.** Blocking (`VerifyReport.passed is False`): every `validate_model` error, every hard-severity clash, every failed rule whose `severity == "error"`. Advisory: clearance clashes, failed `severity == "warning"` rules, and model-script findings.
- **Generated scripts are exempt from the lint.** `tuba/project/script.py::is_generated` decides; a generated script must keep unrolling singles for the studio's code link.
- **The lint never rewrites.** It returns findings. `examples/support-rack-review/model.py` is an authored script edited by hand, never by a tool.
- **Nothing here fabricates a result or touches evidence.** No `evidence/` directory changes; committed artifacts stay byte-identical.
- **Environment:** from the repository root, run tests with `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <paths> -q`.
- **Tests:** add `tests/test_verify.py` and `tests/test_model_script_lint.py`. Reconcile existing tests a task breaks; do not weaken an existing assertion to pass.
- **Commits:** the repository's conventional style (for example `feat(verify): compose validation, clash and rules into one gate`), no trailers.

---

### Task 1: The verify gate

**Files:**
- Add: `tuba/verify.py`, `tests/test_verify.py`
- Modify: `tuba/model.py` (add `TubaModel.verify` next to `validate`), `tuba/mcp/server.py` (add the `verify_model` tool; gate `solve_model`), `tuba/project/__init__.py` (`main` verifies before solving), `tuba/skills/tuba-modeling/SKILL.md` (teach the gate), `docs/content/workflow.md` (name the gate)
- Test: `tests/test_verify.py`, `tests/test_rules.py`, `tests/test_validation.py`, `tests/test_mcp_units.py`, `tests/test_examples.py`

**Interfaces:**
- Consumes: `validate_model` (`tuba/validation.py:23`), `ModelValidationError` (`tuba/validation.py:19`), `ClashEngine.check_all` (`tuba/clash/engine.py:232`), `ClashResult` (`tuba/clash/types.py:25`), `RuleEngine` / `RuleReport` (`tuba/rules.py:56`).
- Produces: `VerifyReport`, `verify_model(...)` and `TubaModel.verify(...)`; the MCP `verify_model` tool returning `VerifyReport.to_dict()`.

- [ ] **Step 1: Write the failing tests**

Add `tests/test_verify.py` in the repository's `unittest.TestCase` style. Cover:

```python
import unittest

from tuba import Model
from tuba.rules import RuleResult, SupportSpacingRule
from tuba.verify import verify_model


class TestVerify(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Verify")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([4.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return model

    def test_clean_model_passes_and_serializes(self):
        report = verify_model(self._model())

        self.assertTrue(report.passed)
        self.assertEqual(report.validation_errors, [])
        self.assertEqual(report.clashes, [])
        self.assertEqual(report.to_dict()["passed"], True)

    def test_validation_error_blocks_and_skips_geometry(self):
        model = self._model()
        model.add_element(id="bad", type="pipe_straight", n1="missing", n2="missing", section="PipeSec", material="Steel")

        report = verify_model(model)

        self.assertFalse(report.passed)
        self.assertTrue(any("missing" in error for error in report.validation_errors))
        self.assertEqual(report.clashes, [])  # geometry checks need valid topology, so they are skipped

    def test_hard_clash_blocks(self):
        model = self._model()
        model.add_obstacle("box", "cuboid", min_point=[1.0, -0.1, -0.1], max_point=[2.0, 0.1, 0.1])

        report = verify_model(model)

        self.assertFalse(report.passed)
        self.assertEqual(len(report.clashes), 1)
        self.assertEqual(report.clashes[0].severity, "hard")

    def test_error_severity_rule_blocks_and_warning_does_not(self):
        class BlockingRule:
            rule_id = "blocking"

            def evaluate(self, model):
                return [RuleResult(rule_id="blocking", passed=False, severity="error", message="nope")]

        blocking = verify_model(self._model(), rules=[BlockingRule()])
        warning = verify_model(self._model(), rules=[SupportSpacingRule(max_span_m=2.5)])

        self.assertFalse(blocking.passed)
        self.assertTrue(warning.passed)  # SupportSpacingRule reports a warning; it never blocks a solve
        self.assertTrue(any("4" in text for text in warning.warnings))

    def test_model_method_delegates(self):
        report = self._model().verify()

        self.assertTrue(report.passed)
```

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_verify.py -q
```
Expected: fails to import `tuba.verify`.

- [ ] **Step 2: Implement `tuba/verify.py`**

```python
"""One cold-model verification gate: structural validation, the join-aware clash
check, and the rule engine, composed into a single report a solver surface must pass.

Advisory findings never block; blocking errors do, so a surface that solves cannot
quietly run only the checks that were convenient to call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from tuba.clash import ClashEngine
from tuba.clash.types import ClashResult
from tuba.model import TubaModel
from tuba.rules import ModelRule, RuleEngine, RuleReport
from tuba.validation import ModelValidationError, validate_model

#: Severities that make a clash blocking. ``check_all`` is a cold check, so today this
#: is ``"hard"``; the operating variants are listed so operating results can reuse the gate.
_BLOCKING_CLASH_SEVERITIES: frozenset[str] = frozenset(
    {"hard", "cold_hard", "operating_hard", "operating_only_hard"}
)


@dataclass(frozen=True)
class VerifyReport:
    """The three checks' native records."""

    validation_errors: list[str] = field(default_factory=list)
    clashes: list[ClashResult] = field(default_factory=list)
    rules: RuleReport = field(default_factory=RuleReport)

    @property
    def errors(self) -> list[str]:
        """Blocking findings: validation errors, hard clashes, error-severity rules."""
        found = list(self.validation_errors)
        found += [
            f"{clash.left} clashes with {clash.right}: penetration {clash.penetration_m:.6g} m."
            for clash in self.blocking_clashes
        ]
        found += [result.message for result in self.rules.results if not result.passed and result.severity == "error"]
        return found

    @property
    def blocking_clashes(self) -> list[ClashResult]:
        return [clash for clash in self.clashes if clash.severity in _BLOCKING_CLASH_SEVERITIES]

    @property
    def warnings(self) -> list[str]:
        """Advisory findings: clearance clashes, warning rules, model-script findings."""
        found = [
            f"{clash.left} is within clearance of {clash.right}: {clash.distance_m:.6g} m."
            for clash in self.clashes
            if clash.severity not in _BLOCKING_CLASH_SEVERITIES
        ]
        found += [result.message for result in self.rules.results if not result.passed and result.severity != "error"]
        return found

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "validation_errors": list(self.validation_errors),
            "clashes": [clash.to_dict() for clash in self.clashes],
            "rules": self.rules.to_dict(),
        }


def verify_model(
    model: TubaModel,
    *,
    clearance_m: float = 0.0,
    duplicate_tol_m: float | None = None,
    rules: Iterable[ModelRule] = (),
) -> VerifyReport:
    """Run every cold-model check in one pass and report what blocks a solve.

    Structural validation runs first. When it fails, the geometry stages are skipped
    (the clash engine and the geometric rules need a model whose nodes and references
    exist), so the report carries the validation errors alone.

    *rules* is supplementary engineering rules (for example
    ``SupportSpacingRule(max_span_m=...)``); the clash check is always run here and
    must not be repeated in *rules*.
    """
    validation_errors: list[str] = []
    try:
        validate_model(model)
    except ModelValidationError as exc:
        validation_errors = [line for line in str(exc).splitlines() if line]

    if validation_errors:
        return VerifyReport(validation_errors=validation_errors)

    clashes = ClashEngine().check_all(
        model, clearance_m=clearance_m, duplicate_tol_m=duplicate_tol_m
    )
    report = RuleEngine(list(rules)).evaluate(model)

    return VerifyReport(
        validation_errors=validation_errors,
        clashes=clashes,
        rules=report,
    )
```

Task 2 extends this with the model-script lint (the `script` argument and `script_findings`), so this task is complete and shippable on its own.

- [ ] **Step 3: Add `TubaModel.verify`**

In `tuba/model.py`, next to `validate` (around line 1231), add a method that imports lazily and delegates, with the same keyword arguments:

```python
    def verify(self, **options: Any):
        """Run the one cold-model verification gate; see :func:`tuba.verify.verify_model`."""
        from tuba.verify import verify_model

        return verify_model(self, **options)
```

Add a test to `tests/test_verify.py` for the delegation (Step 1 already has `test_model_method_delegates`).

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_verify.py tests/test_validation.py tests/test_rules.py -q
```
Expected: all pass.

- [ ] **Step 4: Add the MCP `verify_model` tool and gate `solve_model`**

In `tuba/mcp/server.py`, add a tool beside `check_clashes` (around line 924):

```python
@mcp.tool()
def verify_model(clearance_m: float = 0.0) -> Dict[str, Any]:
    """Run the one cold-model verification gate before solving.

    Returns every blocking error (structural validation, hard clashes, error rules)
    and every advisory (clearance clashes, warning rules) in one report.
    ``solve_model`` refuses while a blocking error stands.
    """
    from tuba.verify import verify_model as _verify

    model = get_active_model()
    return _verify(model, clearance_m=clearance_m).to_dict()
```

Task 2 extends this to pass the session's model-script text once the lint exists.

In `solve_model` (around line 969), after the empty-model and empty-support guards, add:

```python
    from tuba.verify import verify_model as _verify

    report = _verify(model).to_dict()
    if not report["passed"] and not force:
        return {
            "status": "error",
            "message": "Model verification failed; no solver run. "
                       "Fix the errors or pass force=True.",
            "verification": report,
        }
```

Call `tuba.verify.verify_model` directly, not the `verify_model` tool wrapper, so the gate does not depend on how the MCP decorator registers tools. Add a `force: bool = False` parameter to `solve_model` with a docstring line saying it bypasses the gate for diagnostics only and never fabricates results.

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_mcp_units.py tests/test_verify.py -q
```
Expected: pass. If a fixture intentionally violates validation or clashes, pass `force=True` in that test and note it in the report rather than weakening the gate.

- [ ] **Step 5: Verify before solving in the project build**

In `tuba/project/__init__.py::main`, after `namespace = project.run_model()` (around line 113) and before the solve branch, run the gate and stop on failure:

```python
    from tuba.verify import verify_model

    report = verify_model(namespace["model"])
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not report.passed:
        for error in report.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
```

This keeps one gate for the CLI, studio-adjacent builds and the gallery. Task 2 adds `script=project.model_path.read_text(encoding="utf-8")` once the model-script lint exists (read with `encoding="utf-8"` as the repo does elsewhere).

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_examples.py tests/test_project*.py -q
```
Expected: all pass. If an example now fails verification, treat it as a real finding: fix the example or record the decision; do not remove the gate.

- [ ] **Step 6: Teach the gate**

- `tuba/skills/tuba-modeling/SKILL.md`: replace the "Verify before you solve" snippet's hand-wired `ClashEngine().check_all(model)` with `report = model.verify(); assert report.passed, report.errors` and keep the paragraph explaining that `check_all` is the full cold-model triple. Say that `model.verify()` is the one gate and that `check_all` alone is the obstacle-only subset.
- `docs/content/workflow.md`: add one sentence naming `model.verify()` as the pre-solve gate.

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_static_site_docs.py tests/test_public_api.py -q
```
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add tuba/verify.py tuba/model.py tuba/mcp/server.py tuba/project/__init__.py tests/test_verify.py
git commit -m "feat(verify): compose validation, clash and rules into one pre-solve gate"
git add tuba/skills/tuba-modeling/SKILL.md docs/content/workflow.md docs/adr/0004-closed-authoring-vocabulary-and-one-verify-gate.md
git commit -m "docs: name the verify gate and its decision record"
```

---

### Task 2: The model-script lint

**Files:**
- Modify: `tuba/project/script.py` (add `RAW_STRUCTURE_BUDGET`, `check_model_script`, `require_model_script_style`)
- Add: `tests/test_model_script_lint.py`
- Test: `tests/test_model_script_lint.py`, `tests/test_model_script.py`

**Interfaces:**
- Consumes: `is_generated` (`tuba/project/script.py:40`), `GENERATED_HEADER` (`tuba/project/script.py:29`).
- Produces: `check_model_script(text) -> list[str]` (advisory findings) and `require_model_script_style(text) -> None` (raises `ValueError`); it extends `VerifyReport` with `script_findings` and `verify_model` with `script=`, and the MCP `verify_model` tool with the session script text.

**Why the support-rack example is not edited here:** routing its raw pipe records (`examples/support-rack-review/model.py:47-55`) through `model.pipe(...)` changes the generated element ids and the model fingerprint, which stales its committed evidence and breaks `tests/test_project_freshness.py::test_committed_support_rack_evidence_is_fresh` and `tests/test_project_evidence.py` until the evidence is re-solved on a Code_Aster runtime. That conversion belongs with the re-solve, in the follow-on task below; this task adds the lint and proves it on the clean reference layout.

- [ ] **Step 1: Write the failing tests**

Add `tests/test_model_script_lint.py`:

```python
import unittest

from tuba.project.script import GENERATED_HEADER, check_model_script, require_model_script_style


class TestModelScriptLint(unittest.TestCase):
    def test_builder_script_is_clean(self):
        text = (
            "from tuba import Model\n"
            'model = Model("P")\n'
            'with model.pipe(section="DN100", material="Steel") as p:\n'
            "    p.start([0.0, 0.0, 0.0])\n"
            "    p.run(2.0)\n"
            "    p.end([2.0, 0.0, 0.0])\n"
        )
        self.assertEqual(check_model_script(text), [])

    def test_loop_counts_once(self):
        text = (
            "from tuba import Model\n"
            'model = Model("P")\n'
            "for i in range(40):\n"
            "    model.add_node([float(i), 0.0, 0.0])\n"
        )
        self.assertEqual(check_model_script(text), [])

    def test_raw_dump_is_reported(self):
        calls = "".join(f"model.add_node([{i}.0, 0.0, 0.0])\n" for i in range(12))
        findings = check_model_script(calls)

        self.assertEqual(len(findings), 1)
        self.assertIn("12", findings[0])
        self.assertIn("assemble", findings[0])

    def test_generated_script_is_exempt(self):
        text = GENERATED_HEADER + "\n" + "".join(
            f"model.add_node([{i}.0, 0.0, 0.0])\n" for i in range(50)
        )
        self.assertEqual(check_model_script(text), [])

    def test_require_refuses_a_dump(self):
        calls = "".join(f"model.add_element(id='e{i}', type='beam', n1='a', n2='b', section='S', material='M')\n" for i in range(9))

        with self.assertRaises(ValueError):
            require_model_script_style(calls)
```

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_model_script_lint.py -q
```
Expected: fails to import `check_model_script`.

- [ ] **Step 2: Implement the lint in `tuba/project/script.py`**

Add, near `is_generated`:

```python
#: How many syntactic ``model.add_node`` / ``model.add_element`` call sites an authored
#: model script may hold before the lint asks for a construction unit. A loop or a unit
#: is one call site however many records it builds, so a dump is what crosses this line.
RAW_STRUCTURE_BUDGET = 8


def _counts_as_raw(attr: ast.Attribute) -> bool:
    if attr.attr not in {"add_node", "add_element"}:
        return False
    value = attr.value
    return (isinstance(value, ast.Name) and value.id == "model") or (
        isinstance(value, ast.Attribute) and value.attr == "model"
    )


def check_model_script(text: str) -> list[str]:
    """Advisory findings against an authored model script; a generated script is exempt.

    Only the raw-record dump is flagged: ``add_node``/``add_element`` call sites above
    ``RAW_STRUCTURE_BUDGET``. Supports are exempt, the builder and ``assemble`` calls are
    the remedy, and this never rewrites anything.
    """
    if is_generated(text):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"model script does not parse: {exc}"]
    raw = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and _counts_as_raw(node.func)
    )
    if raw > RAW_STRUCTURE_BUDGET:
        return [
            f"model script makes {raw} raw add_node/add_element calls "
            f"(budget {RAW_STRUCTURE_BUDGET}): express the repeated cluster as a construction "
            "unit in def form and apply it with assemble(model, ...), or route it with "
            "model.pipe(...). Raw records are generated-script output, not an authoring medium."
        ]
    return []


def require_model_script_style(text: str) -> None:
    """Refuse an authored model script that dumps raw records; the strict entry point."""
    findings = check_model_script(text)
    if findings:
        raise ValueError("\n".join(findings))
```

`ast` is already imported in this module (line 14).

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_model_script_lint.py tests/test_model_script.py -q
```
Expected: pass; generated-script tests unaffected.

- [ ] **Step 3: Fold the lint into the gate**

Extend `VerifyReport` with `script_findings: list[str] = field(default_factory=list)`, include it in `warnings` and in `to_dict()`, and give `verify_model` a `script: str | None = None` argument that lints when given:

```python
    script_findings: list[str] = []
    if script is not None:
        from tuba.project.script import check_model_script

        script_findings = check_model_script(script)
```

`tuba/verify.py` importing `tuba.project.script` lazily inside the function avoids a cycle (`tuba.project` imports `tuba.model`). Add the advisory test to `tests/test_verify.py`:

```python
    def test_script_findings_are_advisory(self):
        calls = "".join(f"model.add_node([{i}.0, 0.0, 0.0])\n" for i in range(12))
        report = verify_model(self._model(), script=calls)

        self.assertTrue(report.passed)                  # the finding never blocks
        self.assertEqual(len(report.script_findings), 1)
        self.assertIn(report.script_findings[0], report.warnings)
```

Then pass the script text where the gate is called: the MCP `verify_model` tool (the session's last-written/read `model.py` text held around `tuba/mcp/server.py:60`) reads it into a small helper, and `tuba/project/__init__.py::main` already passes `script=project.model_path.read_text(encoding="utf-8")` from Task 1, Step 5.

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_model_script_lint.py tests/test_verify.py tests/test_mcp_units.py -q
```
Expected: pass.

- [ ] **Step 4: Prove it on the clean reference layout**

Add to `tests/test_model_script_lint.py` a test that reads the reference layout from disk and asserts no findings, so a future dump in it is caught:

```python
    def test_reference_layout_is_within_budget(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        text = (root / "examples" / "hydrogen-plant-layout" / "model.py").read_text(encoding="utf-8")
        self.assertEqual(check_model_script(text), [])
```

Then confirm the lint does flag the one authored script the ADR names, without asserting a golden result that a later fix would break:

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -c "from pathlib import Path; from tuba.project.script import check_model_script; print(check_model_script(Path('examples/support-rack-review/model.py').read_text(encoding='utf-8')))"
```
Expected: one finding naming the raw-record count and the `assemble`/`model.pipe` remedy. Record the output in the report; the fix is the follow-on task below, not this one.

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_model_script_lint.py tests/test_model_script.py -q
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add tuba/project/script.py tests/test_model_script_lint.py
git commit -m "feat(model-script): lint authored model.py against a raw-record budget"
```

---

## Follow-on tasks (scoped; plan separately when reached)

These are the rest of the ADR's decision. They are named here so the direction is recorded, but they need their own measured design before steps are written.

1. **Assemblies as retained recipes.** Today `RackBay`/`RackRow` are frozen dataclasses applied with `ModelTransaction(model).apply(rack.to_patch())`, which bypasses `assembly_calls`, so their parameters are not reliably replayable. Give every assembly one `recipe`/`with_params(...)` path and apply assemblies through `assemble(model, ref, **params)` so the generated script replays the call, not the patch. Files: `tuba/assemblies.py`, `tuba/patches.py`, `tuba/project/script.py`, `examples/hydrogen-plant-layout/model.py`, `examples/support-rack-review/model.py`.
2. **Resolve bend intent at authoring time.** `PipingBuilder._bend_with_axis` computes its axis from the *current* heading and `BuildStep` stores the ambiguous `plane`; store the resolved axis (or the explicit `bend_to` target) in the step so step edits cannot flip a sign. Files: `tuba/builder.py`, `tuba/model.py` (`BendGeometry`), tests for recipe replay.
3. **Inspection speaks the authoring vocabulary.** `inspect_model` should return routes, station ranges, support ids, attachment points and groups by the names the builder and units use, so an agent selects rather than scrapes coordinates. Files: `tuba/mcp/server.py`, `tuba/visualization/builders/_core.py` (group metadata), tests.
4. **Bring `support-rack-review` inside the budget and re-solve its evidence.** Convert its raw pipe nodes/elements (`examples/support-rack-review/model.py:47-55`) to one `model.pipe(...)` run with the two attached rest shoes, then re-solve `evidence/Operating` on a configured Code_Aster runtime (`TUBA_RUN_CODE_ASTER_INTEGRATION=1`) so `tests/test_project_freshness.py::test_committed_support_rack_evidence_is_fresh` and `tests/test_project_evidence.py` pass on the new fingerprint. Then promote the lint to blocking (`require_model_script_style`) in `tuba/project/__init__.py` and move this item's outcome into the ADR.

## Verification

- `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_verify.py tests/test_model_script_lint.py tests/test_validation.py tests/test_rules.py tests/test_clash_engine.py tests/test_self_clash.py tests/test_examples.py tests/test_mcp_units.py tests/test_public_api.py tests/test_static_site_docs.py -q`
- `import tuba` still loads no optional stack (covered by `tests/test_public_api.py`).
- Build one example end to end and confirm the gate runs and passes before the solver: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m tuba.project examples/code-aster-review --output .build/verify-gate` (needs the configured Code_Aster runtime for a fresh solve; if unavailable, the run must stop with the runtime blocker, not fake a result).
- Confirm committed evidence is unchanged: `git status --short examples/*/evidence`.

## Not in this plan

- Making the model-script lint blocking by default. It stays advisory until every authored script in `examples/` is clean; `require_model_script_style` is the strict entry point for that promotion.
- Folding mixed/STEP and imported-component studies into the gate.
- A third display path or any change to `tuba/plotting` or `tuba/visualization`.

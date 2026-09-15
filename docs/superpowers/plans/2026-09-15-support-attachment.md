# Supports Attached to Other Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a support act between two model nodes, and make every rest a working contact shoe, with Code_Aster doing the connecting.

**Architecture:** Extend the existing shared decisions instead of adding modules: `aster_contact.shoes` returns a shoe for every rest on any formulation, `modelisation` learns attached springs, and the boundary-condition branch of `aster_comm` writes `LIAISON_DDL` ties for attached supports. Shoes keep Tuba's helper-node `DIS_CHOC` geometry; an attached shoe or spring ties its helper node to the attached node.

**Tech Stack:** Python 3.12, unittest and pytest, Code_Aster 18.0.12 on WSL.

**Spec:** `docs/superpowers/specs/2026-09-15-support-attachment-design.md`

## Global Constraints

- Work in the worktree `D:/tmp/tuba-support-attach` on branch `support-attachment`. Run Python with the main checkout's interpreter from the worktree root: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest ...`.
- A model without rests, springs, support masses or attachments exports byte-identical `study.comm` and `study.mail`.
- No new modules under `tuba/`. Tests may add files.
- Real Code_Aster tests are opt-in with `pytestmark = pytest.mark.skipif(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1", ...)` and run with `TUBA_RUN_CODE_ASTER_INTEGRATION=1`.
- On Windows every `uv run` is `UV_NO_SYNC=1 uv run --no-sync ...`.
- Do not edit `viewer/`; another session works there.
- Conventional commit subjects (`feat(solver): ...`, `test: ...`, `docs: ...`), no trailers.
- From Task 3 until Task 9 the committed evidence of rest and spring examples is stale on purpose, so gallery freshness and attestation tests fail. Each task runs the tests it names; Task 9 onward runs the full suite.

## File Map

| File | Responsibility | Tasks |
|---|---|---|
| `tuba/model.py` | `SUPPORT_TYPES`, `Support.attached_to`, `add_support`, `to_dict` | 1, 5 |
| `tuba/validation.py` | attachment checks | 5 |
| `tuba/schema.py` | `attached_to` in both support schemas | 5 |
| `tuba/builder.py`, `tuba/patches.py`, `tuba/fragments.py`, `tuba/reporting/tables.py` | carry `attached_to` | 5 |
| `tuba/external/ifc.py`, `tuba/mcp/server.py` | normalise imported types, document `rest` | 1 |
| `tuba/solver/aster_contact.py` | shoes for every rest, `write_shoe_anchor` | 3, 6 |
| `tuba/solver/aster_comm.py` | node-group `POI1`, shoes in the standard writer, ties, attached springs, temperature groups | 2, 3, 4, 6, 7 |
| `tuba/solver/aster_loads.py` | `write_thermal_load(varc_groups=...)` | 4 |
| `tuba/solver/aster_mesh.py` | node groups for attached nodes, spring helpers | 6, 7 |
| `tuba/solver/modelisation.py` | `spring_links` | 7 |
| `tuba/solver/aster.py` | compiler inputs for single-operation shoes | 3 |
| `tuba/solver/contact_results.py` | formulation label | 3 |
| `tuba/load_path.py` | rack loads from attached nodes | 8 |
| `examples/future_ready_semantic_workflow.py`, `tests/test_future_ready_integration.py` | attach the demo support | 8 |
| `scripts/official_gallery.py`, `examples/*/evidence/` | declarations and re-solved evidence | 9, 10 |
| `examples/support-rack-review/model.py`, `docs/content/examples.md` | rebuilt rack example | 10 |
| `CONTEXT.md`, `docs/content/modeling.md` | terms and docs | 11 |
| `tests/test_support_attachment.py` (new), `tests/test_code_aster_supports.py` (new, opt-in) | feature tests | 1–8 |

---

### Task 1: Refuse unknown support types

**Files:**
- Modify: `tuba/model.py:333-365` (`Support`)
- Modify: `tuba/external/ifc.py:870-875`
- Modify: `tuba/mcp/server.py:315`
- Create: `tests/test_support_attachment.py`

**Interfaces:**
- Produces: `tuba.model.SUPPORT_TYPES: tuple[str, ...]`; `Support.__post_init__` raises `ValueError("Unknown support type ...")`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_support_attachment.py`:

```python
"""Supports: the closed type list and attachment to another node."""
import unittest

from tuba import Model
from tuba.model import SUPPORT_TYPES


def cantilever():
    """A 6 m DN100 pipe along X with its two end nodes."""
    model = Model("Attach")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    root = model.add_node([0.0, 0.0, 0.0])
    tip = model.add_node([6.0, 0.0, 0.0])
    model.add_element(id="pipe", type="pipe_straight", n1=root, n2=tip, section="DN100", material="Steel")
    return model, root, tip


class SupportTypes(unittest.TestCase):
    def test_documented_types_are_accepted(self):
        self.assertEqual(SUPPORT_TYPES, ("anchor", "guide", "rest", "spring", "hanger", "custom"))
        model, _root, tip = cantilever()
        for kind in SUPPORT_TYPES:
            model.add_support(tip, kind)

    def test_unknown_type_is_refused_with_the_valid_types(self):
        model, _root, tip = cantilever()
        with self.assertRaisesRegex(
            ValueError, "Unknown support type 'sliding'; use one of anchor, guide, rest, spring, hanger, custom"
        ):
            model.add_support(tip, "sliding")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py -q`
Expected: FAIL with `ImportError: cannot import name 'SUPPORT_TYPES'`.

- [ ] **Step 3: Implement**

In `tuba/model.py`, directly above `@dataclass` of `class Support`, add:

```python
SUPPORT_TYPES = ("anchor", "guide", "rest", "spring", "hanger", "custom")
```

Change the field comment to `type: str  # one of SUPPORT_TYPES`, and make these the first lines of `Support.__post_init__`:

```python
        if self.type not in SUPPORT_TYPES:
            raise ValueError(f"Unknown support type {self.type!r}; use one of {', '.join(SUPPORT_TYPES)}.")
```

In `tuba/external/ifc.py`, import `SUPPORT_TYPES` from `tuba.model` (extend the existing `tuba.model` import), and directly before `model.add_support(node=closest_node, type=sup_type, friction_coefficient=friction_coeff)` add:

```python
                    sup_type = next((known for known in SUPPORT_TYPES if known in sup_type), "rest")
```

In `tuba/mcp/server.py:315`, change `'anchor'|'guide'|'sliding'|'spring'` to `'anchor'|'guide'|'rest'|'spring'`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py tests/test_ifc.py tests/test_mcp_server.py tests/test_code_aster_friction.py tests/test_visualization_layer_structure.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuba/model.py tuba/external/ifc.py tuba/mcp/server.py tests/test_support_attachment.py
git commit -m "feat(model): refuse unknown support types"
```

### Task 2: Create discrete supports from node groups

Code_Aster 18 reads `NOEUD='N1'` as node number 1, so every ground spring and support mass landed on the first mesh node (spec fact 8).

**Files:**
- Modify: `tuba/solver/aster_comm.py:193`
- Modify: `tests/test_code_aster_study.py:407` (`test_export_analysis_study_creates_poi1_with_code_aster_node_selector`)
- Create: `tests/test_code_aster_supports.py`

**Interfaces:**
- Produces: `tests/test_code_aster_supports.py` with helpers `cantilever(name) -> (model, root, tip)` and `solve(model, case, name, **options)`, reused by Tasks 3, 6 and 7.

- [ ] **Step 1: Write the failing tests**

In `test_export_analysis_study_creates_poi1_with_code_aster_node_selector`, replace the assertion `self.assertIn(f"_F(NOM_GROUP_MA='DIS_{n1}', NOEUD='{n1}'),", comm)` with:

```python
        self.assertIn(f"_F(NOM_GROUP_MA='DIS_{n1}', GROUP_NO='GN_{n1}'),", comm)
        self.assertNotIn("NOEUD=", comm)
```

Create `tests/test_code_aster_supports.py`:

```python
"""Real Code_Aster references for supports: what each support carries, and where."""
import math
import os
from pathlib import Path

import pytest

from tuba import Model

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster support references",
)

ROOT = Path(".build/support-references")
SPAN_WEIGHT_N = 7850.0 * math.pi * (0.1143 - 0.006) * 0.006 * 9.81 * 6.0


def cantilever(name):
    """A 6 m DN100 pipe along X, anchored at x = 0."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    root = model.add_node([0.0, 0.0, 0.0])
    tip = model.add_node([6.0, 0.0, 0.0])
    model.add_element(id="pipe", type="pipe_straight", n1=root, n2=tip, section="DN100", material="Steel")
    model.add_support(root, "anchor", id="anchor")
    return model, root, tip


def solve(model, case, name, **options):
    return model.solve(case, work_dir=str((ROOT / name).resolve()), force=True, **options)


def test_ground_spring_acts_on_its_own_node():
    model, _root, tip = cantilever("GroundSpring")
    model.add_support(tip, "spring", stiffness_matrix=[0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0], id="spring")
    model.define_load_case("Hot", gravity=True, pressure=0.0, temperature=120.0, ref_temperature=20.0)
    run = solve(model, "Hot", "ground-spring")
    # Hand theory: the tip spring carries 325 N and the tip sags 3.25 mm. Unsupported it would sag 40.5 mm.
    assert run.results.node_results[tip].displacement[2] == pytest.approx(-3.25e-3, rel=0.01)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py -q -k poi1`
Expected: FAIL, the command still contains `NOEUD='N1'`.

Run: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_supports.py -q`
Expected: FAIL, the tip sags about 40.5 mm.

- [ ] **Step 3: Implement**

In `tuba/solver/aster_comm.py:193`, write the `CREA_POI1` entry from the node group the mesh already defines for every supported node:

```python
                    w(f"        _F(NOM_GROUP_MA='{map_name(discrete_support_group(s.node))}', GROUP_NO='{map_name(f'GN_{s.node}')}'),")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run both commands from Step 2. Expected: PASS (the real solve takes under a minute).

- [ ] **Step 5: Commit**

```bash
git add tuba/solver/aster_comm.py tests/test_code_aster_study.py tests/test_code_aster_supports.py
git commit -m "fix(solver): create spring and mass elements on their own node"
```

### Task 3: Every rest is a shoe, on every formulation

Rests on `TUYAU_3M` currently write `LIAISON_UNIL` with the wrong sign (spec fact 1), and shoes only exist on `POU_D_T` without pressure. After this task every rest compiles to the existing `DIS_CHOC` shoe, and a single-operation solve with shoes goes through the standard nonlinear writer, which already writes every load. `load_path` histories keep `write_contact_solve`.

**Files:**
- Modify: `tuba/solver/aster_contact.py` (`shoes`, `validate_path`, new `write_shoe_anchor`, `write_contact_solve`)
- Modify: `tuba/solver/aster.py:274-285` (`analysis_study_inputs`)
- Modify: `tuba/solver/aster_comm.py` (imports, `native_path`, `is_nonlinear`, rest comment, shoe anchors, delete the `LIAISON_UNIL` block, `COMPORTEMENT`, time list, table `INST` filters)
- Modify: `tuba/solver/contact_results.py` (formulation label)
- Test: `tests/test_code_aster_study.py`, `tests/test_code_aster_friction.py`, `tests/test_code_aster_supports.py`

**Interfaces:**
- Consumes: `cantilever`, `solve`, `SPAN_WEIGHT_N` from `tests/test_code_aster_supports.py` (Task 2).
- Produces: `shoes(model, formulation)` returns a `Shoe` for every rest on any formulation; `write_shoe_anchor(w, index: int, spec: Shoe, map_name) -> str` writes `GROUND{index} = AFFE_CHAR_MECA(...)` and returns `"GROUND{index}"`. Task 6 extends it.

- [ ] **Step 1: Write the failing tests**

In `tests/test_code_aster_study.py`, replace `test_export_analysis_study_writes_required_unilateral_contact_coefficients` with:

```python
    def test_export_analysis_study_writes_a_contact_shoe_for_every_rest(self):
        model = Model(project_name="RestShoe")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.add_support(n1, type="rest")
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertNotIn("LIAISON_UNIL", comm)
        self.assertNotIn("DEFI_CONTACT", comm)
        self.assertIn("DIS_CONTACT=_F(", comm)
        self.assertIn("RELATION='DIS_CHOC'", comm)
        self.assertIn("FORCE_TUYAU=_F(", comm)
        self.assertIn("GROUND0 = AFFE_CHAR_MECA(MODELE=MODELE, DDL_IMPO=_F(GROUP_NO=", comm)
        self.assertIn("_F(CHARGE=GROUND0)", comm)
        self.assertIn("INTERVALLE=_F(JUSQU_A=1.0, NOMBRE=10)", comm)
        inputs = study.metadata["compiler_inputs"]
        self.assertEqual(inputs["contact_law"], "DIS_CHOC")
        self.assertEqual(inputs["pipe_modelization"], "TUYAU_3M")
        self.assertEqual(inputs["load_path"], ["Hot"])
```

In `test_export_analysis_study_restrains_pipe_warping_at_nonlinear_rest`, replace `self.assertIn("CONTACT=contact", comm)` with `self.assertIn("RELATION='DIS_CHOC'", comm)`, and in its comment replace "the tail of a plain split also carries the LIAISON_UNIL zone, which names the same node" with "the tail of a plain split also carries the commands after it".

In `tests/test_code_aster_friction.py`:

```python
    def test_friction_requires_a_rest(self):
        model = friction_model()
        model.supports[-1].type = 'anchor'
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'Friction requires a rest support'):
                CodeAsterSolver().export_study(model, 'Hot', root)
```

replaces `test_unqualified_formulation_cannot_silently_omit_friction`. In `test_contact_parameters_cannot_be_ignored`, loop over `(('TUYAU_3M','anchor'),('POU_D_T','anchor'),('POU_D_T','guide'))`, expect the regex `'gap/stiffness parameters require a rest'`, and end with `self.assertEqual(len(shoes(model,'TUYAU_3M')),1)`. In `test_volume_and_mixed_entrypoints_reject_friction_before_meshing`, expect `'Friction requires a rest support'`.

Append to `tests/test_code_aster_supports.py`:

```python
@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_rest_carries_three_eighths_of_the_span_weight(modelization):
    model, _root, tip = cantilever(f"Rest {modelization}")
    model.add_support(tip, "rest", id="rest")
    model.define_load_case("Gravity", gravity=True, pressure=0.0, temperature=20.0, ref_temperature=20.0)
    run = solve(model, "Gravity", f"rest-{modelization}", pipe_modelization=modelization)
    tip_result = run.results.node_results[tip]
    assert tip_result.reaction_force[2] == pytest.approx(3.0 / 8.0 * SPAN_WEIGHT_N, rel=0.01)
    assert abs(tip_result.displacement[2]) < 1.0e-5


def test_rest_lifts_off_under_uplift():
    model, _root, tip = cantilever("RestUplift")
    model.add_support(tip, "rest", id="rest")
    case = model.define_load_case("Uplift", gravity=True, pressure=0.0, temperature=20.0, ref_temperature=20.0)
    case.add_nodal_force(tip, force=[0.0, 0.0, 2000.0])
    run = solve(model, "Uplift", "rest-uplift")
    contact = run.results.contact_results["rest"]
    assert contact.status == "open"
    assert abs(contact.normal_force) < 1.0
    assert run.results.node_results[tip].displacement[2] > 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py tests/test_code_aster_friction.py -q`
Expected: FAIL: `LIAISON_UNIL` is still written and TUYAU_3M friction is still refused.

- [ ] **Step 3: Implement the shoe decisions in `tuba/solver/aster_contact.py`**

In `shoes`, replace the two formulation checks with:

```python
        if support.friction_coefficient and support.type != 'rest':
            raise ValueError('Friction requires a rest support.')
        if support.type != 'rest':
            if support.gap != 0 or support.normal_stiffness is not None or support.tangential_stiffness is not None:
                raise ValueError('Contact gap/stiffness parameters require a rest support.')
            continue
```

Move the check `if result and any(s.type == "spring" or s.mass > 0 for s in model.supports): raise ValueError("Native shoes with discrete springs or support masses are not yet qualified.")` out of `shoes` and into the top of `validate_path` as `if any(s.type == "spring" or s.mass > 0 for s in model.supports): raise ValueError(...)` with the same message: only load-path histories keep that limit.

Add after `validate_path`:

```python
def write_shoe_anchor(w, index, spec, map_name):
    """Hold a shoe's helper node in space and return the load name for EXCIT."""
    name = f'GROUND{index}'
    w(f"{name} = AFFE_CHAR_MECA(MODELE=MODELE, DDL_IMPO=_F(GROUP_NO='{map_name(spec.ground)}',DX=0.,DY=0.,DZ=0.))")
    return name
```

In `write_contact_solve`, replace the `GROUND{i}` loop with:

```python
    for i, spec in enumerate(specs):
        entries.append(f'_F(CHARGE={write_shoe_anchor(w, i, spec, map_name)})')
```

- [ ] **Step 4: Record single-operation shoes in `tuba/solver/aster.py`**

In `analysis_study_inputs`, replace the block from `if self.load_path is not None and not contact_specs:` through the `compiler_inputs = dict(...)` with:

```python
        if self.load_path is not None and not contact_specs:
            raise ValueError('load_path currently requires a resting shoe.')
        if contact_specs:
            if self.load_path is not None:
                names, _cases = validate_path(model, load_case, self.load_path)
            else:
                names = (load_case_name,)
            compiler_inputs = dict(compiler_inputs or {}, pipe_modelization=self.pipe_modelization.value,
                                  load_path=list(names), load_step=self.load_step,
                                  contact_law='DIS_CHOC', contact_stiffness_defaults=[1e10, 1e8])
            if self.load_path is not None:
                compiler_inputs['load_path_inputs'] = {name: model.to_dict()['load_cases'][name] for name in names}
```

In `tuba/solver/contact_results.py`, change `formulation='POU_D_T / DIS_CHOC'` to `formulation=f"{inputs['pipe_modelization']} / DIS_CHOC"`.

- [ ] **Step 5: Route shoes through the standard writer in `tuba/solver/aster_comm.py`**

1. Add `import math` to the imports, and import `write_shoe_anchor` alongside `shoes`.
2. Change `native_path = bool(contacts) or self.load_path is not None` to `native_path = self.load_path is not None`.
3. Delete `unilateral_supports = [...]` and its comment, and set `is_nonlinear = bool(contacts) or bool(cable_elems)`. Reword the comment above it: shoes and cables are nonlinear by construction.
4. In the `elif sup.type == "rest":` branch, replace the comment with: `# A rest is a contact shoe (aster_contact.shoes), never a bilateral DDL_IMPO. It still owes the warping restraint every support gets: a TUYAU node needs WO fixed; a beam node has none.`
5. Directly after the support boundary-condition loop, before `if native_path:`, add:

```python
        if not native_path:
            for index, contact in enumerate(contacts):
                active_bcs.append(write_shoe_anchor(w, index, contact, map_name))
```

6. Delete the whole `has_unilateral = ...` block that writes `UNIL_ZERO`, `UNIL_ONE` and `DEFI_CONTACT`, and delete `if has_unilateral: w("    CONTACT=contact,")`.
7. Replace the nonlinear time list with:

```python
            if is_nonlinear:
                if contacts:
                    if not math.isfinite(self.load_step) or not 0 < self.load_step <= 1:
                        raise ValueError("load_step must be finite and in (0, 1].")
                    w(f"lst_inst = DEFI_LIST_REEL(DEBUT=0.0, INTERVALLE=_F(JUSQU_A=1.0, NOMBRE={math.ceil(1 / self.load_step)}));")
                else:
                    w("lst_inst = DEFI_LIST_REEL(VALE=(0.0, 1.0));")
```

8. Replace the `if cable_elems:` / `else:` `COMPORTEMENT` branches with:

```python
                if cable_elems or contacts:
                    elastic_groups: List[str] = []
                    if pipe_straights or pipe_bends:
                        elastic_groups.append("AllPipes")
                    if beam_elems:
                        elastic_groups.append("G_TUBE")
                    if bar_elems:
                        elastic_groups.append("G_BAR")
                    for support in model.supports:
                        if needs_discrete_element(support):
                            elastic_groups.append(discrete_support_group(support.node))
                    w("    COMPORTEMENT=(")
                    if elastic_groups:
                        w("        _F(")
                        w(f"            GROUP_MA={group_ma_value(elastic_groups, map_name)},")
                        w("            RELATION='ELAS',")
                        w("        ),")
                    if cable_elems:
                        w("        _F(")
                        w(f"            GROUP_MA='{map_name('G_CABLE')}',")
                        w("            RELATION='CABLE',")
                        w("            DEFORMATION='GROT_GDEP',")
                        w("        ),")
                    for contact in contacts:
                        w(f"        _F(GROUP_MA='{map_name(contact.group)}', RELATION='DIS_CHOC', RESI_INTE=1e-9),")
                    w("    ),")
                else:
                    w("    COMPORTEMENT=_F(")
                    w("        TOUT='OUI',")
                    w("        RELATION='ELAS',")
                    w("    ),")
```

9. Contact histories are imported increment by increment, so their tables keep every instant. Change the three `if is_nonlinear and not native_path:` guards (EFGE, DEPL, REAC tables) and the SIEQ table's `if is_nonlinear:` guard to `if is_nonlinear and not contacts:`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_contact_authoring.py tests/test_native_contact_import.py tests/test_tuba_core.py tests/test_support_attachment.py -q`
Expected: PASS. If a test pins the old `LIAISON_UNIL` text or the old refusal messages, update it to the shoe behaviour and name it in the report.

Run: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_supports.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tuba/solver/aster_contact.py tuba/solver/aster.py tuba/solver/aster_comm.py tuba/solver/contact_results.py tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_code_aster_supports.py
git commit -m "feat(solver): solve every rest as a contact shoe"
```

### Task 4: Temperature stays on the 1D elements

Code_Aster refuses thermal expansion on two-node discrete elements in a linear solve (`<DISCRETS_67>`, spec fact 7), and discrete elements have nothing to expand. When a model has discrete support elements, `AFFE_VARC` names the structural element groups; every other model keeps `TOUT='OUI'`. This task also adds the byte-identical guard that protects every later task.

**Files:**
- Modify: `tuba/solver/aster_loads.py` (`write_thermal_load`)
- Modify: `tuba/solver/aster_comm.py` (thermal call)
- Modify: `tuba/solver/aster_contact.py` (`write_contact_solve` material assignment)
- Test: `tests/test_code_aster_study.py`, `tests/test_code_aster_friction.py`

**Interfaces:**
- Produces: `write_thermal_load(..., is_nonlinear: bool, varc_groups: Sequence[str] | None = None)`. In `aster_comm`, `has_discrete_supports = bool(contacts) or any(needs_discrete_element(s) for s in model.supports)`; Task 7 adds spring links to it.

- [ ] **Step 1: Write the byte-identical guard and run it on the current code**

Add to the test class in `tests/test_code_aster_study.py`:

```python
    def test_studies_without_discrete_supports_keep_their_committed_command_text(self):
        from importlib import import_module

        galleries = import_module("scripts.official_gallery").OFFICIAL_GALLERIES
        checked = 0
        for gallery in galleries:
            if gallery.refresh_producer is None or gallery.volume_export or gallery.refresh_load_cases:
                continue
            with TemporaryDirectory() as scratch:
                model, case = gallery.refresh_producer(Path(scratch))
                if any(
                    s.type in ("rest", "spring") or s.mass > 0 or getattr(s, "attached_to", None)
                    for s in model.supports
                ):
                    continue
                solver = CodeAsterSolver(work_dir=scratch, **gallery.solver_options)
                study = solver.export_analysis_study(model, case, scratch)
                fresh = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")
            committed = (gallery.artifact_dir / "study.comm").read_text(encoding="utf-8")
            self.assertEqual(fresh, committed, gallery.id)
            checked += 1
        self.assertGreater(checked, 0)
```

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py -q -k committed_command_text`
Expected: PASS. It must pass before any change in this task. If a gallery already differs, stop and report which one: that drift predates this plan.

- [ ] **Step 2: Write the failing tests**

Add to the same class:

```python
    def test_temperature_stays_off_discrete_support_elements(self):
        def export(with_spring):
            model = Model(project_name="SpringTemperature")
            model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
            model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
            n0 = model.add_node([0.0, 0.0, 0.0])
            n1 = model.add_node([1.0, 0.0, 0.0])
            model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
            model.add_support(n0, type="anchor")
            if with_spring:
                model.add_support(n1, type="spring", stiffness_matrix=[0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0])
            model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
            with TemporaryDirectory() as tmpdir:
                study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
                return (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("    AFFE_VARC=_F(\n        GROUP_MA=('AllPipes',),\n", export(with_spring=True))
        self.assertIn("    AFFE_VARC=_F(\n        TOUT='OUI',\n", export(with_spring=False))
```

In `tests/test_code_aster_friction.py::test_native_law_and_stateful_path_are_emitted`, add `self.assertIn("AFFE_VARC=_F(GROUP_MA=('AllPipes',),", comm)`.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py tests/test_code_aster_friction.py -q -k "temperature_stays_off or stateful_path"`
Expected: FAIL, both writers still write `TOUT='OUI'`.

- [ ] **Step 3: Implement**

In `tuba/solver/aster_loads.py`, add the keyword parameter `varc_groups: Sequence[str] | None = None` to `write_thermal_load` and replace its `w("        TOUT='OUI',")` inside `AFFE_VARC` with:

```python
    if varc_groups is None:
        w("        TOUT='OUI',")
    else:
        w(f"        GROUP_MA={tuple(map_name(group) for group in varc_groups)!r},")
```

In `tuba/solver/aster_comm.py`, directly before the `if has_temperature:` thermal call, add:

```python
            has_discrete_supports = bool(contacts) or any(needs_discrete_element(s) for s in model.supports)
            structural_groups = [
                group
                for group, present in (
                    ("AllPipes", bool(pipe_straights or pipe_bends)),
                    ("G_TUBE", bool(beam_elems)),
                    ("G_BAR", bool(bar_elems)),
                    ("G_CABLE", bool(cable_elems)),
                )
                if present
            ]
```

and pass `varc_groups=structural_groups if has_discrete_supports else None` to `write_thermal_load`.

In `tuba/solver/aster_contact.py::write_contact_solve`, move the line that builds `elastic_groups = [name for name in ('AllPipes','G_TUBE','G_BAR') if ...]` above the `CHMAT = AFFE_MATERIAU` lines, and write the material assignment's last line as:

```python
    w(f"), AFFE_VARC=_F(GROUP_MA={tuple(map_name(x) for x in elastic_groups)!r},NOM_VARC='TEMP',EVOL=THERM,VALE_REF={cases[0].ref_temperature!r}))")
```

Leave the `elastic_groups.extend(...)` and the final mapping after it unchanged.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_code_aster_line_loads.py -q`
Expected: PASS, including the guard from Step 1.

Run: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_supports.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuba/solver/aster_loads.py tuba/solver/aster_comm.py tuba/solver/aster_contact.py tests/test_code_aster_study.py tests/test_code_aster_friction.py
git commit -m "fix(solver): keep temperature off discrete support elements"
```

### Task 5: `Support.attached_to` end to end

**Files:**
- Modify: `tuba/model.py` (`Support`, `add_support`, `to_dict`)
- Modify: `tuba/validation.py:50-52`
- Modify: `tuba/schema.py` (model support schema near line 143, patch `add_support` schema near line 598)
- Modify: `tuba/builder.py:328-375`, `tuba/patches.py:44-56` and `:261-275`, `tuba/fragments.py:137-160`, `tuba/reporting/tables.py:246-290`
- Test: `tests/test_support_attachment.py`

**Interfaces:**
- Consumes: `SUPPORT_TYPES`, `cantilever()` from Task 1.
- Produces: `Support.attached_to: Optional[str]`; `TubaModel.add_support(..., attached_to: Optional[str] = None)`; `PipingBuilder.add_support(..., attached_to=None)`; `AddSupport.attached_to: str | None`. Validation raises `ModelValidationError` with the messages below.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_support_attachment.py`, and add the imports at the top:

```python
from tuba.patches import ModelPatch, ModelTransaction
from tuba.project.script import generate_model_script
from tuba.validation import ModelValidationError


class SupportAttachment(unittest.TestCase):
    def test_attachment_round_trips_through_dict_script_and_patch(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "rest", attached_to=rack, id="shoe")
        self.assertEqual(Model.from_dict(model.to_dict()).supports[-1].attached_to, rack)
        self.assertIn(f"attached_to={rack!r}", generate_model_script(model))

        patched, _root, tip = cantilever()
        result = ModelTransaction(patched).apply(ModelPatch.from_dict({"operations": [
            {"op": "add_node", "local_id": "rack", "coords": [6.0, 0.0, -0.25]},
            {"op": "add_support", "node": tip, "type": "rest", "attached_to": "rack"},
        ]}))
        self.assertEqual(patched.supports[-1].attached_to, result.node_ids["rack"])

    def test_builder_carries_the_attachment(self):
        model, _root, _tip = cantilever()
        rack = model.add_node([0.0, 3.0, -0.25])
        with model.pipe(section="DN100", material="Steel") as builder:
            builder.start([0.0, 3.0, 0.0])
            builder.add_support("rest", attached_to=rack)
        self.assertEqual(model.supports[-1].attached_to, rack)

    def test_attachment_must_name_another_existing_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to="N99", id="lost")
        with self.assertRaisesRegex(ModelValidationError, "Support 'lost' is attached to missing node 'N99'"):
            model.validate()

    def test_a_support_cannot_attach_to_its_own_node(self):
        model, _root, tip = cantilever()
        model.add_support(tip, "rest", attached_to=tip, id="self")
        with self.assertRaisesRegex(ModelValidationError, "Support 'self' is attached to its own node"):
            model.validate()

    def test_attached_support_cannot_impose_a_displacement(self):
        model, _root, tip = cantilever()
        rack = model.add_node([6.0, 0.0, -0.25])
        model.add_support(tip, "anchor", attached_to=rack, imposed_displacement=[0.0, 0.0, 0.01], id="moved")
        with self.assertRaisesRegex(ModelValidationError, "Support 'moved' is attached to a node, so it cannot impose a displacement"):
            model.validate()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py -q`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'attached_to'`.

- [ ] **Step 3: Implement the model, schema and validation**

In `tuba/model.py`:
- add the `Support` field `attached_to: Optional[str] = None  # the node the restraint acts against; None means ground` after `tangential_stiffness`;
- add the `add_support` parameter `attached_to: Optional[str] = None` after `tangential_stiffness` and pass `attached_to=attached_to` to `Support(...)`;
- in `to_dict`, after the `tangential_stiffness` entry, add `**({"attached_to": s.attached_to} if s.attached_to is not None else {}),`.

In `tuba/schema.py`, add `"attached_to": {"type": "string"},` to the model `supports` item properties and to the patch `add_support` properties.

In `tuba/validation.py`, replace the support loop with:

```python
    for support in model.supports:
        if support.node not in model.nodes:
            errors.append(f"Support references missing node {support.node!r}.")
        if support.attached_to is not None:
            if support.attached_to not in model.nodes:
                errors.append(f"Support {support.id!r} is attached to missing node {support.attached_to!r}.")
            elif support.attached_to == support.node:
                errors.append(
                    f"Support {support.id!r} is attached to its own node {support.node!r}; give the pipe its own node."
                )
            if support.imposed_displacement is not None:
                errors.append(f"Support {support.id!r} is attached to a node, so it cannot impose a displacement.")
```

- [ ] **Step 4: Carry the field through builder, patches, fragments and the report**

- `tuba/builder.py::add_support`: add the parameter `attached_to: Optional[str] = None`, record it with `attached_to=attached_to` in `self._record("add_support", ...)`, and pass `attached_to=attached_to` to `self.model.add_support(...)`.
- `tuba/patches.py`: add `attached_to: str | None = None` as the last field of `AddSupport`, and in `_apply_add_support` pass `attached_to=node_ids.get(operation.attached_to, operation.attached_to) if operation.attached_to is not None else None`.
- `tuba/fragments.py`: pass `attached_to=support.attached_to` to `AddSupport(...)`.
- `tuba/reporting/tables.py::build_supports_table`: add the row value `"attached_to": support.attached_to,` after `"node"`, and the column `ReportColumn("attached_to", "Attached to"),` after the `node` column.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py tests/test_model_script.py tests/test_contact_authoring.py tests/test_tuba_core.py -q`
Expected: PASS.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests -q -k "report or patch or fragment or schema or mcp"`
Expected: PASS. A test that pins the supports report columns gets the new `attached_to` column.

- [ ] **Step 6: Commit**

```bash
git add tuba/model.py tuba/validation.py tuba/schema.py tuba/builder.py tuba/patches.py tuba/fragments.py tuba/reporting/tables.py tests/test_support_attachment.py
git commit -m "feat(model): let a support name the node it is attached to"
```

### Task 6: Attached two-way supports and attached shoes

An attached anchor, guide, custom or hanger ties the DOFs its grounded form would block to the attached node with `LIAISON_DDL` (spec fact 3). An attached rest keeps its shoe and ties the shoe's helper node to the attached node instead of fixing it (spec fact 6).

**Files:**
- Modify: `tuba/solver/aster_comm.py` (new `_held_dofs`, attached branch at the top of the support loop)
- Modify: `tuba/solver/aster_contact.py` (`write_shoe_anchor`)
- Modify: `tuba/solver/aster_mesh.py:314` (mail node groups) and `:482` (analysis-mesh node groups)
- Test: `tests/test_support_attachment.py`, `tests/test_code_aster_supports.py`

**Interfaces:**
- Consumes: `write_shoe_anchor` (Task 3), `Support.attached_to` (Task 5), `cantilever`, `solve` (Task 2).
- Produces: `aster_comm._held_dofs(support) -> list[str]`; a `GN_<node>` group for every attached node; `rack_with_pipe_on_top(name)` and `post_and_pipe(name, attached)` helpers in `tests/test_code_aster_supports.py`, reused by Task 7.

- [ ] **Step 1: Write the failing export tests**

Add to `tests/test_support_attachment.py` (with `from pathlib import Path`, `from tempfile import TemporaryDirectory` and `from tuba.solver.aster import CodeAsterSolver` at the top):

```python
def export(model, case="Hot", **options):
    with TemporaryDirectory() as tmpdir:
        study = CodeAsterSolver(work_dir=tmpdir, **options).export_analysis_study(model, case, tmpdir)
        root = Path(study.work_dir)
        return (root / "study.comm").read_text(encoding="utf-8"), (root / "study.mail").read_text(encoding="utf-8")


def attached_model(kind, **support):
    """The cantilever, a post under its tip, and a support at the tip attached to the post top."""
    model, root, tip = cantilever()
    model.add_rectangular_section("Post", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    other = model.add_node([6.0, 0.0, -0.25])
    base = model.add_node([6.0, 0.0, -1.25])
    model.add_element(id="post", type="beam", n1=base, n2=other, section="Post", material="Steel")
    model.add_support(root, "anchor")
    model.add_support(base, "anchor")
    model.add_support(tip, kind, attached_to=other, id="attached", **support)
    model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
    return model, tip, other


class AttachedExport(unittest.TestCase):
    def test_attached_anchor_ties_all_six_dofs(self):
        model, tip, other = attached_model("anchor")
        comm, mail = export(model)
        for dof in ("DX", "DY", "DZ", "DRX", "DRY", "DRZ"):
            self.assertIn(
                f"_F(GROUP_NO=('GN_{tip}', 'GN_{other}'), DDL=('{dof}', '{dof}'), COEF_MULT=(1.0, -1.0), COEF_IMPO=0.0),",
                comm,
            )
        self.assertIn(f"GROUP_NO NOM=GN_{other}", mail)

    def test_attached_guide_ties_only_its_direction(self):
        model, _tip, _other = attached_model("guide", direction=[0.0, 1.0, 0.0])
        comm, _mail = export(model)
        self.assertIn("DDL=('DY', 'DY')", comm)
        self.assertNotIn("DDL=('DX', 'DX')", comm)

    def test_attached_rest_ties_its_shoe_helper_instead_of_fixing_it(self):
        model, _tip, other = attached_model("rest", friction_coefficient=0.3)
        comm, _mail = export(model)
        self.assertIn("GROUND0 = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=(", comm)
        self.assertIn(f"'GN_{other}'),DDL=('DZ','DZ')", comm)
        self.assertNotIn("DDL_IMPO=_F(GROUP_NO='GROUND_", comm)
```

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py -q -k AttachedExport`
Expected: FAIL: attached supports still write `DDL_IMPO`, and no `GN_` group exists for the attached node.

- [ ] **Step 2: Write the failing solver references**

At the top of `tests/test_code_aster_supports.py` add `import numpy as np`, `from tuba.assemblies import RackBay` and `from tuba.patches import ModelTransaction`. Append:

```python
def rack_with_pipe_on_top(name):
    """The support-rack bay, whole model at 180 C, pipe on its own nodes 0.25 m above the attachment nodes."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_ibeam_section("RackColumnIPE", "IPE160")
    model.add_ibeam_section("RackLongIPE", "IPE140")
    model.add_ibeam_section("RackCrossIPE", "IPE100")
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    ModelTransaction(model).apply(RackBay(
        name="rack_A", origin=(0.0, -1.0, 0.0), length=4.0, width=2.0, height=3.0, levels=(3.0,),
        section="RackLongIPE", material="Steel", column_section="RackColumnIPE",
        longitudinal_section="RackLongIPE", transverse_section="RackCrossIPE",
    ).to_patch())
    rack = model.groups["rack_A"]
    for node_id in rack["nodes"]:
        if abs(float(model.nodes[node_id].coords[2])) < 1e-9:
            model.add_support(node_id, "anchor")
    points = rack["metadata"]["attachment_points"]
    rack_left = points["level_1_left"].split(":", 1)[1]
    rack_right = points["level_1_right"].split(":", 1)[1]
    start = model.add_node((-2.0, -1.0, 3.25))
    on_left = model.add_node((0.0, -1.0, 3.25))
    on_right = model.add_node((4.0, -1.0, 3.25))
    end = model.add_node((6.0, -1.0, 3.25))
    for element_id, n1, n2 in (("pipe_inlet", start, on_left), ("pipe_rack_span", on_left, on_right), ("pipe_outlet", on_right, end)):
        model.add_element(id=element_id, type="pipe_straight", n1=n1, n2=n2, section="DN100", material="Steel")
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    model.define_load_case("Operating", gravity=True, pressure=1.5e6, temperature=180.0, ref_temperature=20.0)
    return model, (on_left, rack_left), (on_right, rack_right)


def post_and_pipe(name, attached):
    """A 2 m post anchored at its base carries a 3 m pipe anchored at its far end."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    model.add_rectangular_section("Post", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    base = model.add_node([0.0, 0.0, 0.0])
    top = model.add_node([0.0, 0.0, 2.0])
    far = model.add_node([3.0, 0.0, 2.0])
    model.add_element(id="post", type="beam", n1=base, n2=top, section="Post", material="Steel")
    pipe_start = model.add_node([0.0, 0.0, 2.0]) if attached else top
    model.add_element(id="pipe", type="pipe_straight", n1=pipe_start, n2=far, section="DN100", material="Steel")
    model.add_support(base, "anchor")
    model.add_support(far, "anchor")
    if attached:
        model.add_support(pipe_start, "anchor", attached_to=top)
    model.define_load_case("Hot", gravity=True, pressure=0.0, temperature=120.0, ref_temperature=20.0)
    return model, top


def test_rack_shoe_slides_with_coulomb_friction_under_pressure():
    model, left, right = rack_with_pipe_on_top("RackShoes")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        model.add_support(pipe_node, "rest", attached_to=rack_node, friction_coefficient=0.3, id=f"shoe_{index}")
    run = solve(model, "Operating", "rack-shoes")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        contact = run.results.contact_results[f"shoe_{index}"]
        assert contact.status == "sliding"
        assert contact.normal_force == pytest.approx(2728.0, rel=0.02)
        assert float(np.linalg.norm(contact.tangential_force)) == pytest.approx(0.3 * contact.normal_force, rel=0.001)
        slide = run.results.node_results[rack_node].displacement[0] - run.results.node_results[pipe_node].displacement[0]
        assert abs(slide) == pytest.approx(3.83e-3, rel=0.02)


def test_attached_anchor_between_coincident_nodes_matches_a_shared_node():
    # POU_D_T on both sides: a TUYAU_3M anchor also restrains warping, which a shared node does not.
    shared, shared_top = post_and_pipe("SharedNode", attached=False)
    tied, tied_top = post_and_pipe("TiedNode", attached=True)
    shared_run = solve(shared, "Hot", "shared-node", pipe_modelization="POU_D_T")
    tied_run = solve(tied, "Hot", "tied-node", pipe_modelization="POU_D_T")
    np.testing.assert_allclose(
        tied_run.results.node_results[tied_top].displacement[:3],
        shared_run.results.node_results[shared_top].displacement[:3],
        atol=1e-6,
    )
```

- [ ] **Step 3: Implement ties in `tuba/solver/aster_comm.py`**

Add after the imports:

```python
def _held_dofs(support) -> list[str]:
    """The DOFs a two-way support holds, exactly as the grounded branch blocks them."""
    names = ["DX", "DY", "DZ", "DRX", "DRY", "DRZ"]
    if support.blocked_dof is not None:
        return [names[i] for i, value in enumerate(support.blocked_dof) if value not in (False, 0, "0", "x", "X", None)]
    if support.type == "anchor":
        return names
    if support.type == "guide" and support.direction:
        return [names[i] for i, value in enumerate(support.direction) if abs(value) > 1e-12]
    return names[:3]
```

In the support loop, directly after `char_name = f"BC_{i}"`, add:

```python
            if sup.attached_to is not None and sup.type not in ("rest", "spring"):
                dofs = _held_dofs(sup)
                if not dofs:
                    continue
                other = map_name(f"GN_{sup.attached_to}")
                w(f"{char_name} = AFFE_CHAR_MECA(")
                w("    MODELE=MODELE,")
                w("    LIAISON_DDL=(")
                for dof in dofs:
                    w(f"        _F(GROUP_NO=('{grp_name}', '{other}'), DDL=('{dof}', '{dof}'), COEF_MULT=(1.0, -1.0), COEF_IMPO=0.0),")
                w("    ),")
                if sup.node in pipe_nodes_with_warping:
                    w("    DDL_IMPO=_F(")
                    w(f"        GROUP_NO='{grp_name}',")
                    w("        WO=0.0,")
                    w("    ),")
                w(");")
                w()
                active_bcs.append(char_name)
                continue
```

- [ ] **Step 4: Tie attached shoes and group attached nodes**

In `tuba/solver/aster_contact.py`, replace `write_shoe_anchor` with:

```python
def write_shoe_anchor(w, index, spec, map_name):
    """Hold a shoe's helper node: fixed in space, or tied to the node its rest is attached to."""
    name = f'GROUND{index}'
    ground = map_name(spec.ground)
    if spec.support.attached_to is None:
        w(f"{name} = AFFE_CHAR_MECA(MODELE=MODELE, DDL_IMPO=_F(GROUP_NO='{ground}',DX=0.,DY=0.,DZ=0.))")
    else:
        other = map_name(f'GN_{spec.support.attached_to}')
        ties = ','.join(f"_F(GROUP_NO=('{ground}','{other}'),DDL=('{dof}','{dof}'),COEF_MULT=(1.,-1.),COEF_IMPO=0.)"
                        for dof in ('DX', 'DY', 'DZ'))
        w(f"{name} = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=({ties}))")
    return name
```

In `tuba/solver/aster_mesh.py`, add `| {sup.attached_to for sup in model.supports if sup.attached_to is not None}` to both node-group sets: `grouped_node_ids` in `_write_mail` and the `GN_` loop of the analysis mesh.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py tests/test_code_aster_study.py tests/test_code_aster_friction.py -q`
Expected: PASS, including the byte-identical guard.

Run: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_supports.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuba/solver/aster_comm.py tuba/solver/aster_contact.py tuba/solver/aster_mesh.py tests/test_support_attachment.py tests/test_code_aster_supports.py
git commit -m "feat(solver): tie attached supports and shoes to their node"
```

### Task 7: Attached springs

An attached spring is a `SEG2` `DIS_TR` from a generated helper node 1 m below the support node, with global `K_TR_D_L`, and the helper tied to the attached node in all six DOFs (spec fact 7). The spring force then shows up as `REAC_NODA` on the attached node.

**Files:**
- Modify: `tuba/solver/modelisation.py` (`SpringLink`, `spring_links`, `needs_discrete_element`, `modelisation_assignments`)
- Modify: `tuba/solver/aster_mesh.py` (helper nodes, cells and groups in the mail and the analysis mesh)
- Modify: `tuba/solver/aster_comm.py` (`_spring_stiffness`, `K_TR_D_L`, spring ties, `COMPORTEMENT` groups, `has_discrete_supports`)
- Test: `tests/test_support_attachment.py`, `tests/test_code_aster_supports.py`

**Interfaces:**
- Consumes: `attached_model`, `export` (Task 6 tests), `rack_with_pipe_on_top`, `solve`.
- Produces: `modelisation.SpringLink(support, group, helper)` and `spring_links(model) -> list[SpringLink]`, with `group = f"SPRING_{index}"` and `helper = f"SPRHLP_{index}"`, where `index` is the support's position in `model.supports`.

- [ ] **Step 1: Write the failing tests**

Add to `AttachedExport` in `tests/test_support_attachment.py`:

```python
    def test_attached_spring_is_a_helper_seg2_tied_to_the_attached_node(self):
        model, tip, other = attached_model("spring", stiffness_matrix=[0.0, 0.0, 1.0e7, 0.0, 0.0, 0.0])
        comm, mail = export(model)
        self.assertIn("CARA='K_TR_D_L'", comm)
        self.assertNotIn("CREA_POI1", comm)
        self.assertIn("MODELISATION='DIS_TR'", comm)
        self.assertIn("SPRING0 = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=(", comm)
        self.assertIn(f"'GN_{other}'),DDL=('DRZ','DRZ')", comm)
        self.assertIn("    AFFE_VARC=_F(\n        GROUP_MA=('AllPipes', 'G_TUBE'),\n", comm)
        self.assertIn(f" SPRING_2 SPRHLP_2 {tip}", mail)
```

Append to `tests/test_code_aster_supports.py`:

```python
def test_attached_spring_moves_by_force_over_stiffness():
    model, left, right = rack_with_pipe_on_top("RackSprings")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        model.add_support(pipe_node, "spring", attached_to=rack_node,
                          stiffness_matrix=[0.0, 0.0, 1.0e7, 0.0, 0.0, 0.0], id=f"spring_{index}")
    run = solve(model, "Operating", "rack-springs")
    for pipe_node, rack_node in (left, right):
        force = run.results.node_results[rack_node].reaction_force[2]
        relative = run.results.node_results[rack_node].displacement[2] - run.results.node_results[pipe_node].displacement[2]
        assert abs(force) == pytest.approx(2629.4, rel=0.02)
        assert relative == pytest.approx(abs(force) / 1.0e7, rel=0.01)
```

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py -q -k attached_spring`
Expected: FAIL: the attached spring is still written as a `POI1` on its own node.

- [ ] **Step 2: Implement `spring_links` in `tuba/solver/modelisation.py`**

Add `from dataclasses import dataclass` and:

```python
@dataclass(frozen=True)
class SpringLink:
    """An attached spring: a SEG2 from a helper node to the support node, the helper tied to the attached node."""

    support: "Support"
    group: str
    helper: str


def spring_links(model: "TubaModel") -> list[SpringLink]:
    links = [
        SpringLink(support, f"SPRING_{index}", f"SPRHLP_{index}")
        for index, support in enumerate(model.supports)
        if support.type == "spring"
        and support.attached_to is not None
        and (support.stiffness_matrix is not None or support.stiffness is not None)
    ]
    authored = set(model.nodes) | {element.id for element in model.elements} | set(model.groups)
    collisions = authored.intersection(name for link in links for name in (link.group, link.helper))
    if collisions:
        raise ValueError(f"Attached spring helper names collide with authored names: {sorted(collisions)}.")
    return links
```

In `needs_discrete_element`, require `support.attached_to is None` for `is_discrete_spring`. In `modelisation_assignments`, after the `POI1` loop, add `for link in spring_links(model): assignments[link.group] = "DIS_TR"`.

- [ ] **Step 3: Write the helper geometry in `tuba/solver/aster_mesh.py`**

Import `spring_links`. In `_write_mail`, set `links = spring_links(model)` next to `contacts`, then:
- in `COOR_3D`, after the contact helper nodes: `for link in links:` write `f"  {map_name(link.helper)} "` plus the coordinates `model.nodes[link.support.node].coords - np.array([0.0, 0.0, 1.0])`, formatted like the contact nodes;
- change `if contacts:` before the `SEG2` block to `if contacts or links:`. After the contact cells, write `f' {map_name(link.group)} {map_name(link.helper)} {map_name(link.support.node)}'` for each link. After the contact groups, write `GROUP_MA NOM={map_name(link.group)}` and `GROUP_NO NOM={map_name(link.helper)}` blocks shaped like the contact ones.

In the analysis mesh, after the contact loop, register each link the way contacts are registered: the helper node with `MeshNodeSource(..., role='spring_helper')`, the element `(link.helper, link.support.node)` with `MeshElementSource(..., role='spring_connector')`, and the groups `link.helper` and `link.group`. If `MeshNodeSource` or `MeshElementSource` validates `role` against a fixed list, add the two roles there.

- [ ] **Step 4: Write stiffness, ties and groups in `tuba/solver/aster_comm.py`**

Import `spring_links`. Move the stiffness computation of the `K_TR_D_N` loop into:

```python
def _spring_stiffness(support) -> list[float]:
    """The six global stiffnesses [Kx, Ky, Kz, Krx, Kry, Krz] of a spring support."""
    if support.stiffness_matrix:
        return support.stiffness_matrix
    if not support.direction:
        raise ValueError(
            f"Spring support at node {support.node} uses scalar stiffness without direction. "
            "Use stiffness_matrix=[Kx, Ky, Kz, Krx, Kry, Krz] or provide direction."
        )
    value = support.stiffness if support.stiffness is not None else 1.0e6
    stiffness = [0.0] * 6
    for index, component in enumerate(support.direction):
        if abs(component) > 1e-12:
            stiffness[index] = value
    return stiffness
```

- Guard the `K_TR_D_N` loop with `if s.type == "spring" and s.attached_to is None and (...)` and set `k = _spring_stiffness(s)`. The written text stays byte-identical.
- After that loop, add a `K_TR_D_L` entry for each link: `GROUP_MA=map_name(link.group)`, `REPERE='GLOBAL'`, `CARA='K_TR_D_L'`, and `VALE` formatted like the `K_TR_D_N` entry from `_spring_stiffness(link.support)`.
- Right after the shoe anchors loop from Task 3, add:

```python
        for index, link in enumerate(spring_links(model)):
            helper = map_name(link.helper)
            other = map_name(f"GN_{link.support.attached_to}")
            ties = ",".join(
                f"_F(GROUP_NO=('{helper}','{other}'),DDL=('{dof}','{dof}'),COEF_MULT=(1.,-1.),COEF_IMPO=0.)"
                for dof in ("DX", "DY", "DZ", "DRX", "DRY", "DRZ")
            )
            w(f"SPRING{index} = AFFE_CHAR_MECA(MODELE=MODELE, LIAISON_DDL=({ties}))")
            active_bcs.append(f"SPRING{index}")
```

- In the nonlinear `COMPORTEMENT` groups, append `link.group` for every link to `elastic_groups`.
- Set `has_discrete_supports = bool(contacts) or bool(spring_links(model)) or any(needs_discrete_element(s) for s in model.supports)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_support_attachment.py tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_tuba_core.py -q`
Expected: PASS.

Run: `TUBA_RUN_CODE_ASTER_INTEGRATION=1 D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_supports.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuba/solver/modelisation.py tuba/solver/aster_mesh.py tuba/solver/aster_comm.py tests/test_support_attachment.py tests/test_code_aster_supports.py
git commit -m "feat(solver): attach springs to another node"
```

### Task 8: Rack loads come from the attached nodes

A support belongs to every `rack_bay` group containing its `attached_to` node. A rack's load is the sum of the reactions at its distinct attached nodes, because that is where Code_Aster reports the ties' forces on the structure (spec facts 3 and 7). A grounded support standing on a rack node is no longer a rack load.

**Files:**
- Modify: `tuba/load_path.py`
- Modify: `examples/future_ready_semantic_workflow.py:64-100`, `tests/test_future_ready_integration.py:40-80`
- Test: `tests/test_load_path.py`, `tests/test_visualization_racks.py`

**Interfaces:**
- Consumes: `Support.attached_to` (Task 5).
- Produces: `analyze_load_paths(model, *, node_reactions: dict[str, tuple[float, float, float]] | None = None, result_state: ResultState | None = None) -> LoadPathReport`. The `support_reactions` keyword is removed. `SupportRackAssociation.node` is the attached rack node, and `attachment_point` is its attachment-point name or `""`.

- [ ] **Step 1: Write the failing tests**

Replace the test methods of `tests/test_load_path.py` (keep `_rack_model`) with:

```python
    def _attached_support(self, model, kind="rest"):
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        x, y, z = model.nodes[rack_node].coords
        pipe_node = model.add_node([x, y + 0.1 * len(model.supports), z + 0.25])
        return model.add_support(node=pipe_node, type=kind, attached_to=rack_node), rack_node

    def test_attached_support_associates_to_its_rack(self):
        model = self._rack_model()
        support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model)
        self.assertEqual(len(report.associations), 1)
        association = report.associations[0]
        self.assertEqual(str(association.support), f"support:{support.id}")
        self.assertEqual(str(association.rack), "group:rack_A")
        self.assertEqual(str(association.node), f"node:{rack_node}")
        self.assertEqual(association.attachment_point, "level_1_left")

    def test_rack_load_is_the_reaction_at_the_attached_node(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model, node_reactions={rack_node: (100.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 1)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_two_supports_on_one_attached_node_count_its_reaction_once(self):
        model = self._rack_model()
        _first, rack_node = self._attached_support(model)
        self._attached_support(model, kind="guide")
        report = analyze_load_paths(model, node_reactions={rack_node: (0.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 2)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_result_state_reactions_roll_up_to_rack_loads(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={},
            node_reactions={rack_node: (100.0, 0.0, -1000.0, 0.0, 0.0, 0.0)},
            element_results={},
        )
        report = analyze_load_paths(model, result_state=result_state)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_grounded_support_on_a_rack_node_is_not_a_rack_load(self):
        model = self._rack_model()
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        support = model.add_support(node=rack_node, type="rest")
        report = analyze_load_paths(model)
        self.assertEqual(report.associations, [])
        self.assertIn(f"Support {support.id!r} is not associated", " ".join(report.diagnostics))
```

In `tests/test_visualization_racks.py::_rack_model`, attach the support instead of placing it on the rack node:

```python
        if attach_support:
            rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
            x, y, z = model.nodes[rack_node].coords
            pipe_node = model.add_node([x, y, z + 0.25])
            support = model.add_support(node=pipe_node, type="rest", attached_to=rack_node)
```

and in `test_build_scene_adds_rack_assembly_and_load_path_overlays` call `analyze_load_paths(model, node_reactions={support.attached_to: (100.0, 0.0, -1000.0)})`.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_load_path.py tests/test_visualization_racks.py -q`
Expected: FAIL: `analyze_load_paths` has no `node_reactions` keyword.

- [ ] **Step 2: Implement `tuba/load_path.py`**

Keep `SupportRackAssociation` and `LoadPathReport` as they are, add the two field comments below, and replace everything from `def analyze_load_paths` to the end of the file:

```python
    #: The rack node the support is attached to.
    node: EntityRef
    #: That node's attachment-point name on the rack, or "" for another rack node.
    attachment_point: str
```

```python
def analyze_load_paths(
    model: TubaModel,
    *,
    node_reactions: dict[str, tuple[float, float, float]] | None = None,
    result_state: ResultState | None = None,
) -> LoadPathReport:
    """Associate attached supports with racks and sum the reactions at their attached nodes.

    Code_Aster reports a tie's force on the structure as REAC_NODA on the attached node,
    so a rack's load is the sum over its distinct attached nodes.
    """
    reactions = _node_reactions_from_result_state(model, result_state) if result_state is not None else {}
    reactions.update(node_reactions or {})
    racks = _rack_nodes(model)
    associations: list[SupportRackAssociation] = []
    diagnostics: list[str] = []
    for support in model.supports:
        matches = racks.get(support.attached_to, []) if support.attached_to is not None else []
        if not matches:
            diagnostics.append(f"Support {support.id!r} is not associated with a rack.")
            continue
        for rack_name, point_name in matches:
            associations.append(
                SupportRackAssociation(
                    support=EntityRef("support", support.id),
                    rack=EntityRef("group", rack_name),
                    node=EntityRef("node", support.attached_to),
                    attachment_point=point_name,
                )
            )
    return LoadPathReport(associations=associations, rack_loads=_rack_loads(associations, reactions), diagnostics=diagnostics)


def _rack_nodes(model: TubaModel) -> dict[str, list[tuple[str, str]]]:
    racks: dict[str, list[tuple[str, str]]] = {}
    for group_name, group in model.groups.items():
        metadata = group.get("metadata", {})
        if metadata.get("assembly_type") != "rack_bay":
            continue
        names = {
            node_ref.split(":", 1)[1]: point_name
            for point_name, node_ref in metadata.get("attachment_points", {}).items()
            if isinstance(node_ref, str) and node_ref.startswith("node:")
        }
        for node_id in group.get("nodes", []):
            racks.setdefault(node_id, []).append((group_name, names.get(node_id, "")))
    return racks


def _rack_loads(
    associations: list[SupportRackAssociation],
    node_reactions: dict[str, tuple[float, float, float]],
) -> dict[str, dict[str, float]]:
    loads: dict[str, dict[str, float]] = {}
    counted: set[tuple[str, str]] = set()
    for association in associations:
        entry = loads.setdefault(
            association.rack.id,
            {"support_count": 0, "force_x_n": 0.0, "force_y_n": 0.0, "force_z_n": 0.0},
        )
        entry["support_count"] += 1
        key = (association.rack.id, association.node.id)
        reaction = node_reactions.get(association.node.id)
        if reaction is None or key in counted:
            continue
        counted.add(key)
        entry["force_x_n"] += float(reaction[0])
        entry["force_y_n"] += float(reaction[1])
        entry["force_z_n"] += float(reaction[2])
    return loads


def _node_reactions_from_result_state(
    model: TubaModel,
    result_state: ResultState,
) -> dict[str, tuple[float, float, float]]:
    model_revision = int(getattr(model, "revision", 0))
    if result_state.model_revision != model_revision:
        raise ValueError(
            f"Cannot analyze load paths for model revision {model_revision}; result state uses {result_state.model_revision}."
        )
    return {
        node_id: (float(reaction[0]), float(reaction[1]), float(reaction[2]))
        for node_id, reaction in result_state.node_reactions.items()
        if all(component is not None for component in reaction[:3])
    }
```

- [ ] **Step 3: Rest the demo pipe on the rack**

In `examples/future_ready_semantic_workflow.py` and the mirrored code in `tests/test_future_ready_integration.py`:
- route the line 0.25 m above the level and mid-bay: `RouteEndpoint(id="A", point=(0.0, 0.5, 1.75))`, `RouteEndpoint(id="B", point=(4.0, 0.5, 1.75))`, with the candidate `points` and `RouteSegment` using the same two points;
- attach the support: `rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]`, then `support = model.add_support(node=model.find_node_by_point((0.0, 0.5, 1.75)), type="rest", attached_to=rack_node)`;
- call `analyze_load_paths(model, node_reactions={rack_node: (0.0, 0.0, -500.0)})`.

The asserted line length (4.0 m), rack force (−500 N) and rule results stay the same.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_load_path.py tests/test_visualization_racks.py tests/test_future_ready_integration.py tests/test_operating_state_fixtures.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuba/load_path.py examples/future_ready_semantic_workflow.py tests/test_future_ready_integration.py tests/test_load_path.py tests/test_visualization_racks.py
git commit -m "feat(load-path): take rack loads from the attached nodes"
```

### Task 9: Re-solve the evidence of rest and spring examples

Tasks 2–4 change the solver input of every example with a rest, spring or support mass. Their evidence is re-solved here, and their card declarations gain the shoe elements.

**Files:**
- Modify: `scripts/official_gallery.py` (`elements=` of `code-aster-review`, `elements-supports-review`, `autorouted-expansion-loop`)
- Replace: `examples/code-aster-review/evidence/Operating/`, `examples/elements-supports-review/evidence/LoadCase1/`, `examples/autorouted-expansion-loop/evidence/Hot/`, `examples/native-friction-review/evidence/Cold/`
- Modify: tests that pin values from those artifacts (found in Step 4)

**Interfaces:**
- Consumes: Tasks 2–8.
- Produces: attested evidence that matches the current solver inputs.

- [ ] **Step 1: Update the element declarations**

In `scripts/official_gallery.py`, add `"DIS_T"` to the `elements=` tuples of `code-aster-review`, `elements-supports-review` and `autorouted-expansion-loop`.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_code_aster_gallery_refresh.py -q -k declared_gallery_elements`
Expected: PASS. If it fails, set each tuple to the elements and order the failure message reports.

- [ ] **Step 2: Re-solve the four studies**

Run from the worktree root, one at a time:

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe scripts/refresh_code_aster_gallery.py --gallery code-aster-review --output examples/code-aster-review/evidence/Operating
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe scripts/refresh_code_aster_gallery.py --gallery elements-supports-review --output examples/elements-supports-review/evidence/LoadCase1
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe scripts/refresh_code_aster_gallery.py --gallery autorouted-expansion-loop --output examples/autorouted-expansion-loop/evidence/Hot
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe scripts/refresh_code_aster_gallery.py --gallery native-friction-review --output examples/native-friction-review/evidence/Cold
```

Expected: each finishes with an attested import. `elements-supports-review` already needed time-step cuts before this change (spec fact 10). If any study does not converge, stop and report BLOCKED with the `<EXCEPTION>` text from its `study.mess`. Do not change model physics or solver settings to force convergence.

- [ ] **Step 3: Check that the rests now carry load**

Run:

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe - <<'EOF'
from pathlib import Path
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import load_project

for project, case in (("code-aster-review", "Operating"), ("elements-supports-review", "LoadCase1"), ("autorouted-expansion-loop", "Hot")):
    model = load_project(Path("examples") / project).run_model()["model"]
    run = import_code_aster_artifacts(model=model, work_dir=Path("examples") / project / "evidence" / case)
    print(project, {sid: (c.status, round(c.normal_force, 1)) for sid, c in run.results.contact_results.items()})
EOF
```

Expected: every rest prints a status and a normal force. A closed shoe shows a positive force, an open one shows 0.0. Put the printed table in the task report.

- [ ] **Step 4: Update values pinned to the old artifacts**

Find the consumers with `git grep -n "code-aster-review\|elements-supports-review\|autorouted-expansion-loop\|native-friction-review" -- tests notebooks docs`. The attestation tests read the git index, so first `git add examples/code-aster-review/evidence examples/elements-supports-review/evidence examples/autorouted-expansion-loop/evidence examples/native-friction-review/evidence`.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_plotting_rmed.py tests/test_code_aster_friction_example.py tests/test_native_contact_import.py tests/test_notebook_code_aster_results.py tests/test_official_viewer_publication.py tests/test_project_freshness.py tests/test_code_aster_gallery_refresh.py tests/test_official_gallery_models.py -q`

Expected: PASS after updates. Update a pinned number only by reading it from the re-solved artifacts, and list every changed pin with its old and new value in the report.

- [ ] **Step 5: Run the full suite**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests -q`
Expected: PASS apart from the two known worktree failures in `tests/test_package_release.py` (`'vite' is not recognized`, no `viewer/node_modules`).

- [ ] **Step 6: Commit**

```bash
git add scripts/official_gallery.py examples/code-aster-review/evidence examples/elements-supports-review/evidence examples/autorouted-expansion-loop/evidence examples/native-friction-review/evidence tests
git commit -m "chore(evidence): re-solve examples whose rests are now shoes"
```

### Task 10: Rebuild the support-rack example on attached friction shoes

The shipped example welds the pipe into the rack and holds the rack down with global rests (spec fact 1). It becomes the pipe resting on two friction shoes above the beam.

**Files:**
- Modify: `examples/support-rack-review/model.py`
- Modify: `scripts/official_gallery.py` (`support-rack-review` record)
- Modify: `docs/content/examples.md:74` (Load transfer paragraph)
- Replace: `examples/support-rack-review/evidence/Operating/`

**Interfaces:**
- Consumes: Tasks 3, 5, 6 and 8.

- [ ] **Step 1: Rest the pipe on shoes**

In `examples/support-rack-review/model.py`, change the docstring to `"""A DN100 line resting on friction shoes on a steel I-beam rack bay, analysed together with the rack."""` and replace everything from `start = model.add_node((-2.0, -1.0, 3.0))` through `model.add_support(right, "rest")` with:

```python
# The pipe centreline sits 0.25 m above the beam nodes: half the IPE140, the shoe and the pipe radius.
start = model.add_node((-2.0, -1.0, 3.25))
on_left = model.add_node((0.0, -1.0, 3.25))
on_right = model.add_node((4.0, -1.0, 3.25))
end = model.add_node((6.0, -1.0, 3.25))
model.add_element(id="pipe_inlet", type="pipe_straight", n1=start, n2=on_left, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_rack_span", type="pipe_straight", n1=on_left, n2=on_right, section="DN100", material="Steel", route_id="P-100")
model.add_element(id="pipe_outlet", type="pipe_straight", n1=on_right, n2=end, section="DN100", material="Steel", route_id="P-100")
model.add_support(start, "anchor")
model.add_support(end, "anchor")
model.add_support(on_left, "rest", attached_to=left, friction_coefficient=0.3)
model.add_support(on_right, "rest", attached_to=right, friction_coefficient=0.3)
```

- [ ] **Step 2: Update the card and its docs**

In `scripts/official_gallery.py`, set the `support-rack-review` record to `elements=("TUYAU_3M", "POU_D_T", "DIS_T")` and its `summary` to:

```python
        summary=(
            "A DN100 line resting on friction shoes on an I-beam rack, analysed together with the rack under gravity, "
            "1.5 MPa internal pressure and a temperature increase from 20 C to 180 C, with no imposed nodal forces. "
            "The review shows the shoe forces, the load the shoes put on the rack, and a support-spacing check."
        ),
```

In `docs/content/examples.md`, replace the paragraph under the Load transfer image with the same two sentences.

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_official_gallery_models.py tests/test_code_aster_gallery_refresh.py -q -k "support_rack or declared_gallery_elements"`
Expected: PASS.

- [ ] **Step 3: Re-solve and check the shoes and the rack load**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe scripts/refresh_code_aster_gallery.py --gallery support-rack-review --output examples/support-rack-review/evidence/Operating`

Then run:

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe - <<'EOF'
from pathlib import Path
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.load_path import analyze_load_paths
from tuba.project import load_project

model = load_project(Path("examples/support-rack-review")).run_model()["model"]
run = import_code_aster_artifacts(model=model, work_dir=Path("examples/support-rack-review/evidence/Operating"))
print({sid: (c.status, round(c.normal_force, 1)) for sid, c in run.results.contact_results.items()})
print(analyze_load_paths(model, result_state=run.result_state).rack_loads)
EOF
```

Expected: both shoes `sliding` with a normal force near 2.7 kN, and `rack_A` with `support_count` 2 and a negative `force_z_n` near twice one shoe's normal force. Put the output in the report.

- [ ] **Step 4: Run the affected tests**

Run `git add examples/support-rack-review/evidence`, then:
`D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_official_gallery_models.py tests/test_code_aster_gallery_refresh.py tests/test_project_freshness.py tests/test_official_viewer_publication.py tests/test_studio_project.py tests/test_static_site_docs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/support-rack-review scripts/official_gallery.py docs/content/examples.md
git commit -m "feat(examples): rest the rack example's pipe on friction shoes"
```

### Task 11: Glossary and modeling docs

**Files:**
- Modify: `CONTEXT.md` (end of the Language section)
- Modify: `docs/content/modeling.md:100-104` (Supports)

- [ ] **Step 1: Add the two terms to `CONTEXT.md`**

Append after the **Stale review** entry:

```markdown

**Attached support**:
A support whose restraint acts between its node and another model node instead of a point fixed in space.
_Avoid_: Linked support, connector

**Shoe**:
The one-way contact every rest compiles to: it carries compression, slides with its friction coefficient and lifts off.
_Avoid_: Unilateral zone
```

- [ ] **Step 2: Document attachments in `docs/content/modeling.md`**

After the paragraph that starts "Supports are boundary-condition records", add:

````markdown
A support is fixed in space unless it names the node it is attached to, such as the rack beam node under a pipe shoe:

```python
model.add_support(pipe_node, "rest", attached_to=rack_node, friction_coefficient=0.3)
```

The restraint then acts between matching directions of the two nodes; the offset between their positions carries no lever arm. Every rest is a one-way contact shoe: it carries compression, slides with its friction coefficient and lifts off. Give the pipe its own node, because a pipe built through the structure node is welded to it.
````

- [ ] **Step 3: Run the docs tests**

Run: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_static_site_docs.py tests/test_current_api_docs.py tests/test_code_aster_docs.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md docs/content/modeling.md
git commit -m "docs: attached supports and shoes"
```

### Task 12: Pages screenshots and final verification (main checkout, after merge)

The orchestrator runs this in `D:/Gitprojects/Tuba_v4` after `support-attachment` fast-forwards into `main`, because the worktree has no `viewer/node_modules`. The Pages screenshots show `code-aster-review` and `autorouted-expansion-loop`, whose results changed.

- [ ] **Step 1: Full suite**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: PASS. In the main checkout `test_clean_git_index_snapshot_rebuilds_identical_viewer_and_installed_launcher` may fail with WinError 206, a known path-length limit.

- [ ] **Step 2: Windows Pages build and screenshots**

```bash
UV_NO_SYNC=1 uv run --no-sync python scripts/build_pages.py pages --output .build/pages-check
cd viewer && TUBA_PAGES_SITE_ROOT=../.build/pages-check node node_modules/@playwright/test/cli.js test --config playwright.config.js e2e/pages-artifact.spec.js e2e/friction-gallery.spec.js
```

Expected: PASS. If only `pages-*.png` pixel comparisons fail, rerun the second command with `--update-snapshots` and look at the new `viewer/e2e/snapshots/pages-artifact.spec.js/win32/*.png` before keeping them.

- [ ] **Step 3: Linux screenshots, only if Step 2 changed win32 baselines**

```bash
mkdir -p .build/linux-snapshots
git archive HEAD | docker run --rm -i -v "$PWD/.build/linux-snapshots:/out" tuba-pages-repro bash -lc '
  mkdir -p /work && cd /work && tar -x &&
  uv sync --locked --group docs --extra dev --extra code-aster-rmed &&
  (cd viewer && npm ci) &&
  uv run --no-sync python scripts/build_pages.py pages --output _site &&
  cd viewer && TUBA_PAGES_SITE_ROOT=../_site npx playwright test --config playwright.config.js e2e/pages-artifact.spec.js --update-snapshots;
  cp e2e/snapshots/pages-artifact.spec.js/linux/*.png /out/'
cp .build/linux-snapshots/*.png viewer/e2e/snapshots/pages-artifact.spec.js/linux/
```

- [ ] **Step 4: Commit the baselines**

```bash
git add viewer/e2e/snapshots/pages-artifact.spec.js
git commit -m "test(pages): re-baseline screenshots for shoe results"
```


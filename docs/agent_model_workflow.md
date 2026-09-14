# Agent Model Workflow

Agents should not mutate `TubaModel` by directly calling low-level model methods.

Preferred workflow:

1. Generate or select a `ModelFragment` in local coordinates.
2. Generate a `CoordinateSystem` describing placement in the parent model.
3. Build a `ModelPatch`.
4. Validate the patch payload against schema.
5. Apply the patch through `ModelTransaction`.
6. Validate the resulting `TubaModel`.
7. Render or export from the validated model.

Example:

```python
from tuba import Model
from tuba.coordinates import CoordinateSystem
from tuba.fragments import ModelFragment

fragment = ModelFragment("rack_template")
fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

with fragment.pipe(section="PipeSec", material="Steel") as b:
    b.start([0.0, 0.0, 0.0]).run(2.0)

model = Model("Plant")
model.add_material("Steel", E=2.0e11, nu=0.3)
model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

model.place_fragment(
    fragment,
    CoordinateSystem(origin=(10.0, 20.0, 0.0)),
    name="rack_A",
)

model.validate()
```

The fragment remains editable as a local object. The parent model stores a named group for GUI selection and solver export remains based on ordinary nodes and elements.

## IFC-Style Placement Frames

Placed fragments may also create a named `PlacementFrame`. The parent model still stores node coordinates in model-global Cartesian coordinates, but the frame is retained for GUI selection, IFC export, import provenance, and repeatable local editing.

Use explicit frames when authoring local coordinates:

```python
frame = model.placement_frames["rack_A"]
global_point = model.to_global_point((1.0, 0.0, 0.0), frame="placement_frame:rack_A")
```

Do not assume node coordinates are local just because a placement assignment exists.

## Contracts

- Placement names are unique. Reusing a group name raises `ValueError` and rolls the parent model back.
- Fragment material and section names must either be absent from the parent model or match exactly. Name collisions with different properties raise `ValueError`.
- Group metadata stores placed node IDs, element IDs, support indexes, the fragment name, the placement coordinate system, and a copy of fragment metadata for GUI selection/provenance.
- Patch payloads should be validated with `validate_patch_dict()` before applying them. Full model payloads should be validated with `validate_model_dict()` before loading.
- `AddNode` reuses existing coincident nodes by default. Set `reuse_existing=False` when a GUI or agent intends to create a distinct node at the same coordinate.
- `ModelTransaction` is the mutation boundary. Direct low-level mutation is still possible for hand-authored scripts, but generated changes should go through patches so rollback and validation run consistently.

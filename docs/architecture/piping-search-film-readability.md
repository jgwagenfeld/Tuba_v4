# Piping search film: readable findings and native results

The original film put long technical captions below a small drawing and held
each frame for two seconds. Selecting involved objects did not explain the
failure visibly. Hidden review controls also consumed viewport space.

The film now uses a full drawing area on the left and a readable result card
on the right. Recorded collision locations have red rings and leader labels
with penetration in millimetres. The card identifies each colliding pair.
Nozzle findings label the measured value and its limit at the recorded node.
The interactive replay's **Show finding** uses the same annotations, and they
follow camera changes through the existing Three.js renderer.

Solved attempts have dedicated views for every completed operation:

- Support reactions: global force and moment components, labelled magnitudes at
  every recorded support node, solid blue force arrows, and orange curved moment
  arrows. Both layers remain visible when a result field is selected. These are
  reactions on the model; foundation loads have the opposite sign.
- Internal forces: six signed extrema from the recorded element ends,
  separately labelled in N and N m, with the controlling endpoint marked.
  The drawing colours MFZ by default and states the load case and solver state.
- Displacement: largest recorded nodal magnitude and displacement colouring,
  with physical deformation held at scale one.

Every solved replay view, including a failed-check view, keeps the support force
and moment glyphs and labels visible. Directions come from the measured global
vectors; curved arrows follow the right-hand rule. Force and moment diagrams
have independent display scales and a minimum visible size. The numbers retain
their physical units; arrow lengths do not define a shared N-to-N m scale.
Magnitudes below 0.005 in the respective SI unit have no finite-size glyph and
are labelled below 0.01 at two-decimal display precision. Missing data is labelled
unavailable. Code_Aster reactions belong to nodes: if restraints share a node,
this is their combined nodal reaction, not an invented split between restraints.

Result views hide opaque insulation envelopes and fade reference equipment to
12 percent opacity so the pipe and its underlying result contours can be seen.
Collision views retain physical envelopes. The scene
and its Code_Aster evidence are unchanged. Each value is scoped to the exact
operation and result state; missing fields remain unavailable. Endpoint extrema
do not establish interior maxima, support capacity, or piping-code compliance.

Use `--events review --hold-seconds 5` for a compact review capture. This retains
candidate geometry, decisions, their failed/unknown findings, failed or interrupted
evaluations, and completed-operation result views. `milestones` and `all` remain
available for detailed event histories. Film manifests retain the full original
caption alongside the concise displayed caption, checks, source replay hash,
frame hashes, and viewer identity.

The corrected exports and validation are outside tracked source at
`D:/tuba-runs/Tuba_v4/search-support-reactions-20261011`. A 24-second preview
starts with recorded results and holds rejected reactions, selected reactions,
and a measured nozzle overload for eight seconds each. The full replay retains
the search history. The earlier player's `index.html` opens the result preview
first and provides the full replay separately.

Browser verification compares every rendered nonzero Hot support force and
moment glyph with the exact native node, component vector, and unit, then checks
blue and orange pixels in the actual WebGL canvas. Labels and tables alone do
not satisfy this check. Renderer tests cover simultaneous layers, visible mesh
geometry, operation scoping, and unchanged construction-view behavior.

This is a presentation of retained native Code_Aster evidence, not a fresh
solver or standards qualification. It adds no visualization surface.

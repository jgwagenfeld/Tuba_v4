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

- Support reactions: global force and moment components, force magnitudes at
  their nodes, and native reaction arrows. These are reactions on the model;
  foundation loads have the opposite sign.
- Internal forces: six signed extrema from the recorded element ends,
  separately labelled in N and N m, with the controlling endpoint marked.
  The drawing colours MFZ by default and states the load case and solver state.
- Displacement: largest recorded nodal magnitude and displacement colouring,
  with physical deformation held at scale one.

Result views hide opaque insulation envelopes so their underlying result
contours can be seen. Collision views retain physical envelopes. The scene
and its Code_Aster evidence are unchanged. Each value is scoped to the exact
operation and result state; missing fields remain unavailable. Endpoint extrema
do not establish interior maxima, support capacity, or piping-code compliance.

Use `--events review --hold-seconds 5` for a compact review capture. This retains
candidate geometry, decisions, their failed/unknown findings, failed or interrupted
evaluations, and completed-operation result views. `milestones` and `all` remain
available for detailed event histories. Film manifests retain the full original
caption alongside the concise displayed caption, checks, source replay hash,
frame hashes, and viewer identity.

The replacement export and validation are outside tracked source at
`D:/tuba-runs/Tuba_v4/search-film-readable-20261011`.
This is a presentation of retained native Code_Aster evidence, not a fresh
solver or standards qualification. It adds no visualization surface.

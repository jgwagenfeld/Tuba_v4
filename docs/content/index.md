# Tuba v4

Tuba is an open-source Python library for modeling piping systems and their supporting structures, running Code_Aster analyses, and reviewing the results.

Tuba also provides CLI and MCP (Model Context Protocol) interfaces. Ongoing development aims to automate parts of model building.

```text
Tuba model -> Code_Aster solve -> imported artifacts -> processed result review
```

## Examples

Open these reviews in your browser without installing Tuba. Each featured example includes Code_Aster results and Python source you can inspect and adapt.

[![Plant layout with two process lines, a shared steel pipe rack, and surrounding equipment.](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/hydrogen-plant-layout.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout)

**[Plant layout](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=hydrogen-plant-layout)** — Two process lines, an elevated rack, shoe supports and equipment obstacles in one model. Inspect displacement, pipe-wall stress and friction shoe reactions. This is an illustrative hydrogen-plant layout, not a hydrogen-service qualification. [Model source](https://github.com/jgwagenfeld/Tuba_v4/blob/main/examples/hydrogen-plant-layout/model.py) · [Study](https://github.com/jgwagenfeld/Tuba_v4/blob/main/examples/hydrogen-plant-layout/study.py).

<div class="grid cards" markdown>

-   [![Three pipe lines on a shared steel rack](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/multipipe-rack.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=multipipe-rack)

    **Multipipe rack** — How do three lines at different temperatures load one shared rack?

-   [![An automatically routed hot line with an expansion loop](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/autorouted-expansion-loop.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop)

    **Thermal expansion** — Where does a hot line move, and what does it reach?

-   [![Solid tee mesh coupled to pipe elements](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/pipe-tee-volume-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review)

    **3D solid** — How does 1D beam pipework transition into a 3D solid tee junction?

-   [![A steel industrial hall with repeated portal frames and bracing](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/steel-portal-frame-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=steel-portal-frame-review)

    **Portal frame stability** — A seven-frame hall under gravity and wind, with linear buckling modes for the ideal frame. These are reference results, not member-adequacy checks.

-   [![Comparison of frictionless and frictional pipe supports](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/native-friction-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=native-friction-review)

    **Nonlinear friction** — How does friction change the same pipe and load path?

-   [![Pipe loads transferred through shoes to a steel rack](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/support-rack-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review)

    **Load transfer** — What do the supports and the steel underneath actually carry?

-   [![The same pipework evaluated in four load cases](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/load-case-preparation.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=load-case-preparation)

    **Load-case preparation** — How do sustained, thermal, occasional and pressure loads change the same pipe?

-   [![Three I-section orientations under the same load](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/profile-orientation-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=profile-orientation-review)

    **Beam orientation** — How does a rolled I-section change the response to the same tip force?

-   [![A restrained pipe with two bends](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

    **Pipe bends** — What happens to a pressurised line held at both ends?

</div>

The thermal-expansion example selects its route geometrically, then checks the solved operating clearance; it does not rank competing routes by solver results. [Browse all examples and their limits](examples.md), including braced racks, guy cables and imported components. The imported-component review contains geometry only.

## Start here

- **[Setup](setup.md)** — create the shared Tuba and Code_Aster conda environment on Linux x86_64, or Ubuntu WSL2 on Windows, check the runtime, and launch Studio.
- **[Try browser editing](setup.md#try-a-model-in-the-browser)** — choose **Build**, edit `model.py`, and **Update geometry**. The preview is unsolved; **Review** retains published Code_Aster results and marks them outdated after edits.
- **[Tutorial](tutorial.md)** — build a pipe, run Code_Aster, and display the imported results.
- **[Modeling](modeling.md)** — procedural authoring, sections, supports, construction units, fluid contents and verification.
- **[Workflow](workflow.md#projects-in-studio-the-cli-and-agents)** — use the same `model.py` and `study.py` through Studio, CLI and MCP.
- **[Share a project](project-sharing.md)** — exchange source, CAD and optional saved evidence, or package a completed review.

## Process networks and retained search

[Process networks](process-networks.md) connects a typed water circuit and authored route to pandapipes, then maps verified pressure, temperature and contents loads into Code_Aster. Studio offers a linked P&ID, **Run hydraulics**, **Solve** and **Review**. Install the optional `process` extra; controls are drawn, not simulated. OpenModelica is an optional comparison backend.

[Retained piping search](piping-search.md) evaluates a bounded parameter grid, retains rejected layouts and their checks, and exports review, replay and film artifacts. [Autorouting](autorouting.md) covers geometric route proposals. These workflows have different scopes; an automatically proposed route still needs verification and a Code_Aster evaluation.

## Where results come from

New stress, displacement, reaction and operating-state clearance results require a completed Code_Aster run and imported result files. The [recommended setup](setup.md#recommended-one-environment) installs Tuba and Code_Aster together. Modeling, geometric routing and viewing preserved results do not require a local solver installation.

Exporting `.comm`, `.mail` and `.export` input files does not run an analysis. A blocked runtime stops evaluation. FE stress and user reference ratios do not establish piping-code compliance; acceptance criteria and independent engineering verification remain the user's responsibility.

## Result visualization

- `tuba/plotting/` provides PyVista quick-look and export views.
- `tuba/visualization/` and `viewer/` produce shareable web review bundles with geometry, analysis meshes, results and run metadata.

Use one path per notebook or example. See the [web-scene workflow](workflow.md#reviewable-web-scene) and an [example result view](assets/figures/code_aster_review.png).

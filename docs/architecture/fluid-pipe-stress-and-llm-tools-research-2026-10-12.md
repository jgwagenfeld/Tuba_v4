# Existing fluid, pipe-stress, and LLM tools

Research date: 2026-10-12. Repository baseline: `c54eab5`.
This complements the [process-network and Modelica roadmap](process-network-modelica-and-code-aster-roadmap.md)
and [LLM piping research](llm-piping-reasoning-and-guidance-research-2026-10-12.md).
The work reviewed primary documentation and research sources. No commercial
software was installed, no license terms were evaluated, and no hydraulic or
structural study was run for this comparison.

## Assessment

Commercial links between hydraulic calculations and pipe-stress analysis already
exist. COMSOL is the closest documented combination found in this review: it
provides a coupled pipe-flow/mechanics example and facilities for LLM assistance
and API-driven agents. These are complementary documented capabilities, not a
demonstration of an autonomous, qualified plant designer. The inspected sources
do not establish the complete workflow of P&ID ingestion, hydraulic sizing,
obstacle-aware routing, support design, piping-code acceptance, and explanation
of every rejected candidate.

The opportunity for Tuba is to coordinate that design loop using explicit
engineering contracts and reviewable solver evidence. Simply linking fluid
calculations to pipe stress would repeat an existing commercial capability.

## Commercial comparison

| Tool or combination | Documented fluid-to-stress connection | Documented LLM scope |
| --- | --- | --- |
| **COMSOL Multiphysics** | Pipe Flow and Pipe Mechanics are coupled in the [fixed-geometry interface](https://doc.comsol.com/6.3/doc/com.comsol.help.sme/sme_ug_multiphysics.18.14.html). Flow affects mechanics; deformation does not affect flow in this interface. | A built-in chatbot helps with API code; external agents can inspect, edit, solve, and evaluate models through the [COMSOL API workflow](https://www.comsol.com/technologies/generative-and-agentic-ai-workflows). |
| **PASS/HYDROSYSTEM + PASS/START-PROF** | [HYDROSYSTEM](https://passuite.com/hydrosystem) provides hydraulic/thermal network calculations and an interface to the [START-PROF](https://passuite.com/start) pipe-stress program. Its surge module also transfers water-hammer forces. | The reviewed product pages do not establish an LLM-controlled design workflow. |
| **SIGMA ROHR2 + SINETZ** | [ROHR2's interfaces](https://rohr2.com/en/fluid-dynamics-interfaces.html) export model data to SINETZ. [SINETZ](https://www.rohr2.com/en/sinetz.html) calculates network flow, pressure loss, and heat loss. ROHR2 also imports transient force histories from hydraulic tools. | The reviewed pages do not establish LLM generation or repair of the coupled design. |
| **Datacor/AFT Impulse + a stress program** | [Impulse](https://www.datacor.com/products/impulse) imports piping models and exports transient forces to CAESAR II, AutoPIPE, ROHR2, and TRIFLEX. This is particularly relevant to water hammer. | No LLM-controlled combined design workflow was established by the reviewed source. |
| **Bentley AutoPIPE** | Can participate in the hydraulic force-transfer workflow above. Its [datasheet](https://www.bentley.com/wp-content/uploads/pds-autopipe-ltr-en-lr.pdf) separately describes genetic-algorithm support optimization. | [AutoPIPE 2026](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0051117) introduces a documentation-query Copilot as a technology preview. This is separate from support optimization. |

Absence of a documented LLM workflow in these pages is not proof that a vendor
has no such capability. It means that this review did not substantiate it.
File exchange also does not establish a continuously synchronized or two-way
physical coupling.

### COMSOL: the closest combined reference

The official [flow-and-stress tutorial](https://doc.comsol.com/6.3/doc/com.comsol.help.models.sme.pipe_flow_stress/pipe_flow_stress.html)
uses a supported pipe with a bend. The coupling applies pressure, wall-friction,
and bend-flow forces, while including pipe and contents weight. It displays
pressure, stress, displacement, bending moments, and shear forces. This is a
useful concrete reference for the requested result display. It is explicitly a
one-way coupling, not a demonstration of a complete piping-code design process.

COMSOL's [AI documentation](https://www.comsol.com/technologies/generative-and-agentic-ai-workflows)
describes model-context attachment, API-code assistance, and agents that modify
features, run studies, and inspect results. This supports building an LLM-driven
engineering iteration workflow on the platform. It does not establish that a
ready-made piping agent already implements all the constraints in Tuba's vision.

### Specialized pipe tools: relevant existing workflows

PASS is a direct example of a hydraulic network product linked to a specialized
pipe-stress product. Its advertised interface is more relevant to everyday
network sizing than a full CFD calculation. Specific transferred fields,
supported versions, synchronization rules, and licensing would need verification
in a practical evaluation of [HYDROSYSTEM and START-PROF](https://passuite.com/hydrosystem).

ROHR2's documented [fluid interfaces](https://rohr2.com/en/fluid-dynamics-interfaces.html)
cover geometry and component exchange, plus load-time imports from several
hydraulic programs. The documentation supports these exchange paths; this review
does not assume automatic return of every SINETZ pressure or temperature result.

For water hammer, Impulse has an explicit
[valve-closure force example](https://docs.aft.com/Impulse/Examples/Valve-Closure-with-Pipe-Forces.html).
Transient force histories should be treated as time-dependent mechanical loads,
rather than replaced by one static pressure value.

AutoPIPE also shows why the word "AI" needs qualification. Bentley describes
the support optimizer as a
[genetic algorithm](https://www.bentley.com/wp-content/uploads/pds-autopipe-ltr-en-lr.pdf).
The [2026 release notes](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0051117)
describe Copilot as natural-language access to product documentation and mark it
as a technology preview, which the notes define as not yet QA-certified or ready
for production. The reviewed evidence does not identify that Copilot as the
support-design algorithm.

## Open-source coupling and research prototypes

**preCICE + OpenFOAM + CalculiX** provides a real open-source fluid-structure
coupling route. Its [elastic-tube tutorial](https://precice.org/tutorials-elastic-tube-3d.html)
couples fluid and solid solvers for a pressure-driven tube expansion. This is a
CFD/structural coupling example, rather than an application for P&ID-derived
1D network sizing and piping-code checks. Based on that difference, it is a
heavier starting point for Tuba's ordinary routing and hydraulic design loop.

The existing [preCICE Code_Aster adapter](https://precice.org/adapter-code_aster)
currently documents conjugate heat transfer. It should not be presented as a
ready-made hydraulic-network-to-Code_Aster pipe-force bridge. Adapter scope and
compatibility must be checked before reusing it.

**HydraulicGPT** is a relevant LLM/hydraulics research demonstration. The
[published study](https://www.cambridge.org/core/journals/cambridge-prisms-water/article/accelerating-water-distribution-systems-planning-and-design-with-generative-artificial-intelligence-models/0B0C3E7B3E9D628BB3750E2F2AFD8D1F)
uses domain-authored Python functions and hydraulic simulation through WNTR.
The authors provide [public code](https://github.com/NhuDoADL/HydraulicGPT).
It does not establish a pipe-stress or 3D support-design integration. The reviewed
repository listing does not establish a reuse license, so this note calls it
public research code rather than assuming an open-source license.

**OpenModelica + Code_Aster through Tuba** remains a proposed open-source
architecture in the [existing roadmap](process-network-modelica-and-code-aster-roadmap.md).
The reviewed Tuba baseline does not already provide that fluid/structural bridge.
This note does not turn the proposal into a completed integration claim.

## Distinguish five kinds of integration

1. **Model exchange:** reuse geometry, component dimensions, connectivity, and
   operating data. Imported models still need validation in the receiving tool.
2. **One-way load transfer:** use hydraulic outputs as structural inputs without
   structural deformation changing the hydraulic solution.
3. **Two-way physical coupling:** fluid and structure exchange fields during the
   physical simulation. This may matter for selected transient or deformation
   problems, but is different from a design iteration loop.
4. **LLM assistance and automation:** documentation questions, code generation,
   and API-driven model edits have substantially different engineering scope.
5. **Design generation with acceptance:** routing and support changes must pass
   declared hydraulic, mechanical, geometric, and project-specific checks.

An LLM calling hydraulic and structural solvers in sequence can implement a
design loop without a two-way physical co-simulation. Conversely, a sophisticated
fluid-structure solver does not itself create a routing/design agent.

## Implications for Tuba

The following are development recommendations inferred from the comparison:

- Keep the shared process/component identities and procedural Python model
  proposed in the existing roadmap. An LLM should revise authored construction
  units and parameters while stable identifiers connect the hydraulic and
  structural projections.
- Begin with supported steady 1D flow and explicit one-way structural-load
  mapping. Document pressure/temperature references, contents density, fitting
  effects, coordinate frames, and which mechanical terms the receiving solver
  already includes. Prevent duplicated pressure, momentum, or friction loads.
- Recompute hydraulics when a route changes length, elevation, bends, bore, or
  component selection. Accept the design only after the affected checks have
  been evaluated. An example project limit such as 3 m/s belongs in the declared
  requirements; it is not a universal piping rule.
- Preserve the production contract: Tuba model -> real external-process
  Code_Aster solve -> processed structural results. An LLM's explanation is not
  an alternative source of support forces, internal forces, or stress results.
- Extend the existing review scene with hydraulic fields, located failures,
  and candidate history. Show the matching Code_Aster forces/moments and mark
  structural results as unevaluated when a hydraulic rejection skips the solve.
- Evaluate LLM proposals against deterministic and evolutionary baselines using
  the same requirements and solver budgets. Commercial support optimization is
  evidence that established search approaches remain relevant.

Use COMSOL's worked coupled-pipe case as a published modeling reference for a
small bridge demonstration. It is not an independent validation result until
the compared inputs, assumptions, discretization, and actual solver runs are
recorded. Use PASS and ROHR2/SINETZ as interface/workflow references for network
data exchange. No purchase recommendation or performance comparison follows
from this documentation-only review.

The first implementation task remains the shared process-network contract and
its connection to an authored Tuba route, as defined in the existing roadmap.
This market review adds references and clarifies positioning; it does not
implement the hydraulic backend or change the Code_Aster production contract.

# LLM reasoning about piping and guidance for generation

Research date: 2026-10-12. This extends the
[direct-LLM research](direct-llm-piping-generation-research-2026-10-11.md)
and [development roadmap](llm-piping-design-roadmap.md). Primary sources were
checked live. This is a research and design recommendation; no new model,
benchmark campaign, or Code_Aster evaluation was run.

## What the evidence supports

An LLM can interpret engineering intent, reason over explicit connectivity and
component attributes, choose changes to a design, and use measured feedback to
revise it. Evidence is strongest when the agent works through an engineering
representation and executable tools. It is much weaker for inferring exact 3D
clearances or structural acceptability directly from an image or generated
coordinates. The studies below measure different tasks; their percentages are
not interchangeable measures of industrial piping competence.

| Primary source and access | Actual LLM role | Measured evidence and boundary |
| --- | --- | --- |
| Kong et al., *A method for pipe auto-routing using an LLM-based expert system*, IJNAOE 18, 100796 (2026). [Publisher](https://www.sciencedirect.com/science/article/pii/S2092678226000609), [author laboratory](https://sydlab.snu.ac.kr/journal/2026-08-12-00/). Publisher abstract and laboratory record inspected; full paper not inspected. | Structured object/relation rules guide a route-analysis agent; a second agent adjusts A* cost weights using diagnostics and iteration history. A* constructs the routes. | Abstract reports three iterations: approximately 14% fewer bends and a 73% reduction in the grouping metric, with 8% more length and roughly one minute per iteration. This establishes rule-guided routing refinement, not direct LLM routing or FE/code qualification. |
| Wang et al., *From Semantic Intent to Adaptive Geometric Priors*, [SSRN preprint 7299984](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7299984), posted August 17, 2026. Indexed primary abstract inspected; 41-page full text unavailable during this review. | One agent standardizes instructions; another proposes sparse routing corridors as probabilistic search priors. A separate DRIVE model predicts search-domain radius. Downstream optimization finds routes. | Abstract reports 90.8% exact accuracy on held-out reasoning cases, radius-prediction R² = 0.976, and up to 48.8% fewer exploration nodes and 32.3% fewer effective iterations. These are intent/search metrics, not stress-accepted design rates. |
| Zakarin et al., *LLMs in Process Diagram Engineering: From Optimal PFDs to Validated P&IDs*, [arXiv preprint](https://arxiv.org/html/2608.11220v1). Full HTML inspected, especially sections 4.1–4.2. | Generates Python action programs against a restricted graph SDK. Context includes the graph, interface contract, domain hints, and examples. Programs are checked and executed in isolation; an independent reference checks outputs. | On 23 manually prepared rule scenarios, all tested models executed successfully; semantic correctness was 23/23 for one model and 22/23 for two others. The separate synthesis stage combines GA and LLM repair. Diagram topology and instrumentation are evaluated, not 3D routing, thermal expansion, or stress. |
| Alimin and Schweidtmann, *GraphRAG for engineering diagrams: ChatP&ID*, AIChE Journal 72(10), e70540 (2026). [University publication record](https://research.tudelft.nl/en/publications/graphrag-for-engineering-diagrams-chatpampid-enables-llm-interact/). Primary abstract inspected; linked final PDF inaccessible. | Queries DEXPI-derived P&ID knowledge graphs using retrieval rather than relying only on diagram pixels or the full serialized file. | Abstract reports 91% query accuracy for ContextRAG with GPT-5-mini; graph representations improved accuracy by 18% over image inputs and reduced token costs by 85% versus ingesting smart-P&ID files directly. Useful evidence for representation and retrieval, not autonomous 3D design. |
| Lee, Kim and Jung, *Multi-agent LLM framework integrating CAD, FEA, and optimization*, Structural Engineering and Mechanics 96(6), 523–533 (2025). [Published paper](https://www.techno-press.org/download.php?journal=sem&num=6&ordernum=6&volume=96). Full PDF accessible; methodology and scope inspected. | GPT-5 generates FreeCAD Python, coordinates meshing and ANSYS analysis, and updates JSON design parameters from targets and history. Section 2.5 explicitly uses LLM updates instead of a numerical optimization algorithm. | Four examples include a flanged pipe. This is relevant direct design/FE-feedback precedent, but the reported scope is linear analysis and simple geometries; the authors acknowledge reduced robustness in complex scenarios. It does not qualify industrial pipe networks. |
| Do et al., *Accelerating water distribution systems planning and design with generative artificial intelligence models*. [Published article](https://www.cambridge.org/core/journals/cambridge-prisms-water/article/accelerating-water-distribution-systems-planning-and-design-with-generative-artificial-intelligence-models/0B0C3E7B3E9D628BB3750E2F2AFD8D1F), [author code](https://github.com/NhuDoADL/HydraulicGPT). Article inspected; code not executed. | A function-calling agent coordinates domain-authored tools and WNTR hydraulic simulations, compares scenarios, and proposes augmentation. | Demonstration uses a network of 28,985 nodes and 33,200 pipes; a suggested diameter augmentation matches an independent engineer assessment. Network scale belongs to the hydraulic tools, not a demonstrated ability to reason unaided over every pipe. This is hydraulics, not support/stress analysis. |

### CAD representations and an actual agent-skill experiment

These adjacent studies help answer how to guide the designer. Their geometry
metrics do not establish piping stress, support, or fabrication acceptance.

| Primary source and access | Finding relevant to Tuba | Boundary |
| --- | --- | --- |
| Mallis et al., *CAD-Assistant*, ICCV 2025. [Author project and results](https://cadassistant.github.io/), [published paper](https://openaccess.thecvf.com/content/ICCV2025/papers/Mallis_CAD-Assistant_Tool-Augmented_VLLMs_as_Generic_CAD_Task_Solvers_ICCV_2025_paper.pdf). Project methodology and tables inspected. | The planner generates FreeCAD Python, executes it, and uses renderings, sections, and constraint tools. GPT-4o 3D question-answering accuracy rises from 0.782 to 0.857 in this benchmark. This supports giving the agent tools and inspectable model state. | Question answering and sketch constraints are different tasks from designing an accepted industrial pipe network; these results also concern an older model cohort. |
| *A Solver-Aided Hierarchical Language for LLM-Driven CAD Design* (AIDL). [Full author preprint](https://arxiv.org/html/2502.09819), [published paper](https://diglib.eg.org/bitstream/handle/10.1111/cgf70250/cgf70250.pdf). Methods, ablation, and limitations inspected. | Hierarchical components, semantic references, and geometric constraints make designs easier to edit coherently. Removing constraints increased executable-program success from 64% to 94%, but produced detached components and weaker editability. Reported repairs sometimes removed constraints until errors disappeared, losing design intent. | More constraints are not automatically better generation instructions. Execution success and image similarity alone miss connectivity and preserved requirements. Keep the intended requirements outside the editable candidate and verify them independently. |
| K-Dense, *lab-hardware-cad*, updated August 15, 2026. [Author benchmark](https://www.k-dense.ai/blog/lab-hardware-cad-skill), [actual SKILL.md](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/lab-hardware-cad/SKILL.md). Both inspected; not installed or executed. | In 98 runs, the stronger model tied on dimensional success (13/14 per arm). Named-parameter regeneration worked in 49/49 skill runs versus 0/49 baselines. The skill supplies sourced dimensions, parametric Python, references, and checks. | First-party lab-hardware study; no parts fabricated. The baseline prompt did not explicitly require parametric editing: this does not isolate the value of the skill format over ordinary explicit instructions. Its declaration-only interface gate can pass wrong built geometry. |
| Liu et al., *CAD-Factory*, SIGGRAPH 2026. [Author project](https://cad-factory.github.io/). Project overview inspected; detailed paper metrics not reviewed. | Separates structural topology from parameter instantiation, with planning, coding, execution validation, and part-level visual feedback. | Relevant architectural precedent for hierarchical authoring, not evidence that Tuba needs its own DSL, multiple agents, or a newly trained model. |
| JoyIndustrial-VisCAD Team, *RealCADBench*, September 2026. [Full preprint](https://arxiv.org/html/2609.03773v1). Protocol, aggregate results, and reported failure modes inspected. | Evaluates a 1,770-task slice, including 25 assemblies, using FreeCAD Python exports. Runnable output, geometric similarity, and visual/semantic identity favor different models; recurring failures include omitted fine features and incorrect component placement. | This is a geometry benchmark, not a piping-physics assessment. Its export-based metrics do not independently establish preserved parametric intent, tolerances, manufacturing readiness, or structural acceptance. |

### Public skills already covering adjacent engineering tasks

- [MP-AI-20 expansion-joints SKILL.md](https://github.com/MP-AI-20/mechanical-engineering-skills/blob/main/skills/expansion-joints/SKILL.md)
  packages bellows, movement, thermal expansion, and anchor-force guidance.
  Its public text was inspected; its formulae were not independently audited and
  no measured LLM piping-design benchmark was established by this review.
- [Soljourner engineering-skills inventory](https://github.com/Soljourner/claude-engineering-skills/blob/master/SKILLS_INVENTORY.md)
  lists hydraulic-component references, fluid-property tools, NetworkX piping
  graphs, and simulation integrations. The inventory was inspected, not its
  claimed integrations executed.
- [hanhuark mechanical-engineering-research skill suite](https://github.com/hanhuark/mechanical-engineering-research-skill)
  includes focused thermal-fluid analysis and assumption/validation review.
  Its README explicitly labels showcase artifacts as synthetic examples.

These are public examples of packaging domain knowledge, not verified drop-in
Tuba piping-design engines. They were researched without installation. Borrow
the organization of focused references and executable checks; validate any
adopted engineering content against the applicable source and Tuba behavior.

Two additional leads should not be mistaken for measured industrial validation:

- Fan et al., *Green Industrial Engineering on the Web: Agent-Driven Ant Colony
  Optimization Tuning for Energy-Efficient 3D Pipe Routing*, is confirmed in the
  [official WWW 2026 accepted-paper list](https://www2026.thewebconf.org/accepted/web4good.html).
  Its [ACM DOI](https://doi.org/10.1145/3774904.3793013) is a retrieval lead;
  the abstract/full paper was inaccessible. The title alone is insufficient to
  claim a particular LLM architecture or performance improvement.
- The published [marine-CAD cognitive-AI framework](https://www.mdpi.com/2077-1312/14/15/1352)
  explicitly describes its pipe-routing example as conceptual. Its corpus,
  hybrid reasoning, and traceability architecture is a design proposal, not a
  timed shipyard trial or evidence of regulatory acceptance.

## How far can the agent reason?

For Tuba, distinguish four abilities rather than asking whether a model
"understands piping" in the abstract:

1. **Intent and engineering language.** Translate requirements, recognize
   related components, and suggest design concepts. These are suitable agent
   tasks, provided assumptions remain explicit.
2. **Topology and model semantics.** Trace connected routes, locate supports and
   nozzles, inspect restraint directions, and select editable construction
   units. Structured connectivity and attributes are preferable to asking the
   agent to reconstruct every relationship from screenshots.
3. **Spatial and physical hypotheses.** Propose a corridor, flexibility loop,
   or restraint change and predict which failure it might address. Treat that
   prediction as a testable hypothesis; coupled effects can reverse it.
4. **Engineering acceptance.** Determine exact clearance, reactions, moments,
   stress, travel, or applicable code acceptance from the evaluated model and
   checks. In Tuba, production result claims require the real Code_Aster
   workflow and matching candidate evidence. Fluent explanations and convincing
   pictures cannot substitute for those results.

The first three are a useful design agent. The fourth must remain an explicit
engineering evaluation boundary. This separation is our synthesis of the
studies, not a claim that they tested Tuba.

## Should we give it rules, skills, or another representation?

**Yes: give the agent guidance and enforce the important requirements.** The
direct pipe-routing evidence explicitly uses structured rules; the P&ID work
uses graph representations and checked SDK actions. Neither establishes that a
large prose prompt alone makes geometry or physics reliable.

Keep three kinds of guidance separate:

| Guidance | Proposed Tuba form | Meaning |
| --- | --- | --- |
| Fixed task requirements | Versioned project inputs for interfaces, operations, material/section assumptions, required checks, and limits; executable checks where available | A candidate passes only if the evaluation satisfies them. The designer cannot silently relax them. |
| Engineering preferences and heuristics | Short explanations of objectives and tradeoffs; source-linked project practices | Help choose a promising design. A heuristic is conditional, not a universal law; reducing bends or adding restraints can worsen another requirement. |
| Procedural skills | Small task-loaded instructions with API examples, an inspection/edit/evaluation procedure, and known failure modes | Make tool use and authoring repeatable. A skill improves behavior; it is not a solver, a standards implementation, or proof of expertise. |

Use existing authored `model.py` and parameterized construction units. Give the
agent stable IDs, connectivity, route/unit parameters, obstacle envelopes,
support degrees of freedom, and exact failing measurements alongside useful
views. Keep the compiled node/element state available for inspection without
making flat coordinate dumps the authoring language. This fits Tuba's existing
procedural Python contract; a new DSL or a mandatory multi-agent architecture is
not a prerequisite.

Use three complementary representations:

- **Engineering graph:** equipment/nozzles, lines, branches, component types,
  stable IDs, and relationships. Process-flow connectivity and structural load
  paths are different relationships; neither should be inferred solely from a
  render.
- **Hierarchical construction program:** a line composed of runs, offsets,
  loops, supports, and rack units with named dimensions, explicit units, and
  local coordinate frames. Keep topology choices distinct from dimension edits,
  while retaining the existing Python authoring API.
- **Measured findings:** candidate-linked numerical results and failure records,
  paired with targeted views of the relevant clash, restraint, or force/moment
  distribution. Give the agent the data that produced the drawing as well as
  the drawing itself.

For example, an excessive hot-case guide reaction should prompt inspection of
the restraint directions, permitted motion, and the expansion path. The agent
can propose an offset or a permitted restraint change, predict its effect, and
re-evaluate weight support, reactions, travel, stress, and operating clashes.
Deleting the guide or changing the temperature merely to clear the finding is
not a repair when those are fixed requirements. This is a proposed diagnostic
procedure, not a numerical engineering result from this research.

Keep a short always-loaded authoring and evidence contract. Load only the
relevant task skill: procedural Tuba authoring, route/clash repair, thermal
flexibility, support/rack design, or solver-result review. Each proposed skill
should provide tested API examples, inspection steps, conditional engineering
advice, and explicit checks. Store catalogue data and applicable project/code
requirements as versioned references with provenance. A `SKILL.md` should tell
the agent how to use those references and validators; it should not become an
unverified substitute for them. These are proposed skill boundaries, not claims
that these skills have already been implemented.

A minimal experiment should load one relevant skill, such as collision repair
or thermal-flexibility review, rather than every rule and every example at once.
Each revision should record the intended change, affected IDs, predicted effect,
preserved requirements, and the checks needed to test it. Require a concise
engineering rationale and verify its consequences; elaborate reasoning prose
does not itself establish correctness.

Return feedback as candidate-linked findings with operation/state, object IDs,
quantity/component, units, measured value, limit/margin, collision pair/location,
and artifact references. Preserve failed, unavailable, and interrupted attempts
as different outcomes. The replay video is a review surface; the same underlying
structured evidence should drive the next design decision.

## Recommended next comparison and limits

Compare the same pinned coding model on the same problems and budgets with:
(a) minimal API instructions, (b) those instructions plus a small task skill and
source-linked examples, and (c) that guidance plus semantic model context,
structured findings, and targeted views. All configurations retain the same
Code_Aster backend, tool access, immutable acceptance checks, and minimum task
inputs. This first comparison measures guidance and representation; a later
comparison can test adding A* or numerical optimization tools. Repeat runs and
count invalid designs, failed/interrupted calls, solver evaluations, verified
feasibility, first-feasible time, objectives, and total cost. Separate fixed
parameter tuning from permission to change route topology.

The practical recommendation is to develop the direct agent and feedback loop
first, with rules and reusable units making its decisions easier to inspect.
Add A*, bounded searches, or other optimizers where measured failures justify
them. Existing hybrid research demonstrates their usefulness, not their
necessity for every future coding model.

Access limits: Kong and Wang were reviewed at abstract level; ChatP&ID through
its university-hosted abstract; the ACM routing paper only through its official
publication listing. Those studies cannot support uninspected implementation
details. No inspected source establishes generally autonomous, fully qualified
industrial thermal piping with complete supports, operating cases, fabrication
requirements, and all applicable standards. No current Tuba LLM success rate is
claimed here.

Verification for this note: source access and evidence boundaries reviewed;
repository links and Markdown whitespace checked. No executable product change,
new LLM trial, or fresh Code_Aster solve is represented by this document.

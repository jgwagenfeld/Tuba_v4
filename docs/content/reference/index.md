# Reference

The reference separates generated signatures from the maintained workflow guidance.

## Generated public API

[Public API](public-api.md) renders signatures and docstrings from the installed Tuba source with mkdocstrings. It does not copy Python signatures into Markdown.

The package-level `tuba.Model` name is the public alias for `TubaModel`. The generated class reference therefore uses the defining symbol, `tuba.model.TubaModel`, while normal user code can continue to import `Model` from `tuba`.

For the order in which these APIs are used, see the [workflow](../workflow.md). Exported study files are not a completed engineering evaluation until Code_Aster has run and Tuba has imported the result artifacts.

## Workflow interfaces

Studio, CLI and MCP use the same authored project files and verification gate.
The [CLI and MCP guide](../workflow.md#projects-in-studio-the-cli-and-agents)
covers their entry points and explicit project binding.

- [Autorouting](../autorouting.md) — geometric route requests and candidate review.
- [Retained piping search](../piping-search.md) — bounded solver-backed evaluations, decisions, replay and film.
- [Process networks](../process-networks.md) — typed graphs, hydraulic evidence, P&ID and Code_Aster load mapping.

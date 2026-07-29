# Reference

The reference separates generated signatures from the maintained workflow guidance.

## Generated public API

[Public API](public-api.md) renders signatures and docstrings from the installed Tuba source with mkdocstrings. It does not copy Python signatures into Markdown.

The package-level `tuba.Model` name is the public alias for `TubaModel`. The generated class reference therefore uses the defining symbol, `tuba.model.TubaModel`, while normal user code can continue to import `Model` from `tuba`.

For the order in which these APIs are used, see the [workflow](../workflow.md). Exported study files are not a completed engineering evaluation until Code_Aster has run and Tuba has imported the result artifacts.

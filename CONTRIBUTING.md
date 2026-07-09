# Contributing to Tuba v4

Tuba v4 is a Code_Aster-backed piping workflow. A useful contribution should
fit this sequence:

1. Define or modify the Tuba piping model.
2. Export and run the Code_Aster study, or import artifacts from a real
   Code_Aster run.
3. Display, review, or report those imported artifacts.

## What Counts As A Result

Generated `study.comm`, `study.mail`, and `study.export` files are solver input
and handoff files. They are useful for review and debugging, but they are not
completed engineering results.

Stress, displacement, reaction, compliance, and operating-state clash output
must come from Code_Aster artifacts such as parsed result tables or `.rmed`
files. If a runtime or artifact is missing, the workflow should stop with a
clear setup message instead of showing placeholder values.

## Code_Aster Work

- Prefer the native Tuba execution path in `tuba.solver.aster` and
  `tuba.solver.code_aster_runtime`.
- Shell commands, Docker wrappers, and legacy `as_run` paths are compatibility
  fallbacks, not the main product path.
- Keep export-only examples explicit: exporting a study is not a completed
  engineering evaluation until Code_Aster has run and Tuba has imported the
  result artifacts.

Run the local runtime check before working on solver execution:

```powershell
python -m tuba.solver.code_aster_doctor --check
```

## Result Display

Use the existing display paths:

- `tuba.plotting` for PyVista quick-look notebook views and export helpers.
- `tuba.visualization` plus `viewer/` for reviewable browser scene bundles.

Do not add a separate viewer path for solver results unless the project first
decides to replace one of the existing paths.

## ada-py Boundary

`ada-py` is useful reference material for interoperability ideas, but it is
GPL-3.0-or-later. Do not copy or vendor `ada-py` code into Tuba core. Any future
adapter must keep the license boundary explicit.

## Useful Checks

```powershell
python -m unittest tests.test_current_api_docs tests.test_static_site_docs -v
python -m unittest tests.test_code_aster_real_smoke -v
```

The real solver smoke test requires a configured Code_Aster runtime and the
integration opt-in documented in `README.md`.

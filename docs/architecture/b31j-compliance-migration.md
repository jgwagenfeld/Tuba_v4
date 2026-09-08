# Piping standards checks: retired

The built-in ASME B31.3 evaluator and B31J / Appendix D factor helpers have
been removed. This supersedes the former migration plan; no further standards
implementation is planned in Tuba.

Tuba remains a model -> Code_Aster solve -> processed-result review workflow.
Users select applicable standards and perform the necessary engineering checks.
Existing user-supplied report and evaluator interfaces are documented in
[the public API](../content/reference/public-api.md#user-owned-standards-checks).

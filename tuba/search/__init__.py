"""Durable, explainable search over authored Tuba piping models."""

from .contracts import Candidate, CheckResult, CheckSpec, Decision, Evaluation, SearchDefinition

__all__ = ["Candidate", "CheckResult", "CheckSpec", "Decision", "Evaluation", "SearchDefinition"]


def __getattr__(name):
    if name in {"load_search", "grid_parameters", "run_search"}:
        from . import run
        return getattr(run, name)
    if name == "evaluate_candidate":
        from .evaluate import evaluate_candidate
        return evaluate_candidate
    if name in {"export_history", "write_candidate_review"}:
        from . import export
        return getattr(export, name)
    raise AttributeError(name)


__all__ += ["load_search", "grid_parameters", "run_search", "evaluate_candidate", "export_history", "write_candidate_review"]

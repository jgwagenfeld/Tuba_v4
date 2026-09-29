"""What a load path did to its shoes, derived from a native contact history.

A friction review is a sequence question. A shoe that is sticking at the end of
a load path says nothing about how it got there, and the result state a bundle
opens on is the *last* stage. So the viewer offered one instant at a time plus a
flat list of every instant to pick from, and the native friction example read as
inert: its first stage genuinely is inert, because gravity acts along the shoe
normal and nothing drives the pipe tangentially until the temperature rises.

This module turns the same attested history the solver wrote into the facts a
reviewer has to sign off on: which shoe reached its Coulomb cone and for how
long, which lifted clear, which came back down, and which never carried load at
all. It is the published form of the assertions ``check()`` already makes in
Python for the example - computed once, here, from the result states, so the
Studio, the review package and any other reader describe the same run instead of
each re-deriving it.

Two properties shape the output. Findings are aggregated into **spans**, not
events: a shoe that slides through three consecutive stages is one finding
("slid from Hot through Lift"), not three. And every value is published
structured and in SI - prose is deliberately not generated here, because only
the viewer knows the reader's unit system, and a bundle that said "3221 N" would
contradict a reader working in kN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from tuba.solver.base import ContactResult

#: Tolerances, matching the ones the native reader applies in
#: ``tuba.solver.contact_results``, so a finding and a status can never disagree
#: about whether a force or a gap is real.
FORCE_TOLERANCE_N = 1.0
RELATIVE_FORCE_TOLERANCE = 1.0e-3
GAP_TOLERANCE_M = 1.0e-9

#: DIS_CHOC reports |Ft| = mu*N exactly on a sliding branch, so a shoe at 100% of
#: its cone has slid - that is the physics, not a defect. Only above this does
#: the solver report more friction than its own law allows, which is a
#: convergence artifact worth a reviewer's attention.
OVER_LIMIT_UTILIZATION = 1.001

#: Severities are deliberately confined to these two words. The Pages build
#: refuses a published scene containing any mapping with ``severity: "error"``,
#: and a shoe that has slid is a solved result, not a build failure.
SEVERITY_INFO = "info"
SEVERITY_ATTENTION = "attention"

CONTACT_FINDINGS_SCHEMA = "tuba.contact_findings.v1"

#: Finding kinds, in the order a reviewer meets them.
FINDING_KINDS = (
    "slip",
    "lift_off",
    "reseat",
    "force_reversal",
    "over_limit",
    "unloaded",
)


def _magnitude(vector: Sequence[float]) -> float:
    return float(math.sqrt(sum(float(value) ** 2 for value in vector)))


def _is_real(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclass(frozen=True)
class ContactSample:
    """One shoe at one converged increment."""

    state: Any
    contact: ContactResult
    stage: int
    label: str
    pseudo_time: float

    @property
    def state_id(self) -> str:
        return str(getattr(self.state, "id", ""))

    @property
    def tangential(self) -> float:
        return _magnitude(self.contact.tangential_force)


def _force_tolerance(contact: ContactResult) -> float:
    return max(FORCE_TOLERANCE_N, RELATIVE_FORCE_TOLERANCE * max(abs(contact.normal_force), contact.friction_limit))


def _carries_normal_force(contact: ContactResult) -> bool:
    return contact.normal_force > _force_tolerance(contact)


def _has_tangential_force(contact: ContactResult) -> bool:
    return _magnitude(contact.tangential_force) > _force_tolerance(contact)


def _is_open(contact: ContactResult) -> bool:
    return contact.status == "open"


def _is_sliding(contact: ContactResult) -> bool:
    return contact.status == "sliding"


def _frictionless(contact: ContactResult) -> bool:
    """A closed shoe with no cone has no stick/slip classification at all.

    The native reader reports this as ``indeterminate``, which reads like a
    solver failure but is the correct description of a mu = 0 support.
    """
    return contact.friction_limit <= 0.0 and contact.status in {"indeterminate", "open"}


def _run_id(state: Any) -> str:
    metadata = getattr(state, "metadata", {}) or {}
    return str(metadata.get("run_id") or metadata.get("analysis_id") or getattr(state, "load_case", "") or "")


def _pseudo_time(state: Any) -> float:
    metadata = getattr(state, "metadata", {}) or {}
    value = metadata.get("pseudo_time")
    return float(value) if _is_real(value) else 0.0


def _stage_index(state: Any) -> int:
    metadata = getattr(state, "metadata", {}) or {}
    value = metadata.get("stage_index")
    return int(value) if _is_real(value) else 0


def _stage_label(state: Any) -> str:
    metadata = getattr(state, "metadata", {}) or {}
    label = metadata.get("stage_label")
    return str(label) if label else f"Stage {_stage_index(state)}"


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _contiguous_runs(indices: Sequence[int]) -> list[list[int]]:
    """Group sorted stage indices into runs of consecutive stages.

    A shoe that slides at stages 2, 3 and 4 is one span of behaviour, not three
    findings; only a break in the sequence starts a new one.
    """
    runs: list[list[int]] = []
    for index in sorted(set(indices)):
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


def contact_samples(result_states: Iterable[Any]) -> dict[str, list[ContactSample]]:
    """Every shoe's solved history, keyed by support id and ordered by time.

    States are ordered by run, then pseudo-time, then id, so one run is always
    walked in the order the solver produced and two runs staged into a single
    bundle stay separable.
    """
    states = sorted(
        (state for state in result_states if getattr(state, "contact_results", None)),
        key=lambda state: (str(_run_id(state)), _pseudo_time(state), str(getattr(state, "id", ""))),
    )
    samples: dict[str, list[ContactSample]] = {}
    for state in states:
        for support_id, contact in sorted((getattr(state, "contact_results", {}) or {}).items()):
            samples.setdefault(str(support_id), []).append(
                ContactSample(
                    state=state,
                    contact=contact,
                    stage=_stage_index(state),
                    label=_stage_label(state),
                    pseudo_time=_pseudo_time(state),
                )
            )
    return samples


def build_contact_findings(result_states: Iterable[Any]) -> dict[str, Any] | None:
    """Derive the load-path story for every contact-bearing run, or ``None``.

    ``None`` when the scene carries no contact history at all, so a review of a
    model that merely rests on a shoe is not handed an empty contact story.
    """
    samples = contact_samples(result_states)
    if not samples:
        return None
    runs: list[dict[str, Any]] = []
    for run_id in _ordered_unique(
        _run_id(sample.state) for shoe in samples.values() for sample in shoe
    ):
        scoped = {
            support_id: [sample for sample in history if _run_id(sample.state) == run_id]
            for support_id, history in samples.items()
        }
        scoped = {support_id: history for support_id, history in scoped.items() if history}
        if scoped:
            runs.append(_run_findings(run_id, scoped))
    if not runs:
        return None
    primary = max(runs, key=lambda run: (run["stage_count"], sum(len(shoe["stages"]) for shoe in run["shoes"])))
    return {
        "schema": CONTACT_FINDINGS_SCHEMA,
        "primary_run_id": primary["run_id"],
        "runs": runs,
    }


def _run_findings(run_id: str, scoped: dict[str, list[ContactSample]]) -> dict[str, Any]:
    stages = _stage_records(scoped)
    stage_by_index = {stage["index"]: stage for stage in stages}
    shoes = [_shoe_record(support_id, history, stage_by_index) for support_id, history in scoped.items()]
    findings: list[dict[str, Any]] = [finding for shoe in shoes for finding in shoe["findings"]]
    findings.sort(key=lambda finding: (finding["stage_index"], tuple(finding["support_ids"]), finding["kind"]))
    for position, finding in enumerate(findings):
        finding["id"] = f"contact_finding:{position:03d}"
    return {
        "run_id": run_id,
        "load_case": stages[0]["load_case"] if stages else "",
        "stage_count": len(stages),
        "shoe_count": len(shoes),
        "stages": stages,
        "shoes": shoes,
        "findings": findings,
        "attention_count": sum(1 for finding in findings if finding["severity"] == SEVERITY_ATTENTION),
    }


def _stage_records(scoped: dict[str, list[ContactSample]]) -> list[dict[str, Any]]:
    """One record per authored stage, carrying its end state and every state id.

    A stage is the unit a reviewer thinks in - "Hot", "Lift" - so the stage list
    is what a navigator should step through, not the fifty converged increments
    inside them.
    """
    grouped: dict[int, list[ContactSample]] = {}
    for history in scoped.values():
        for sample in history:
            grouped.setdefault(sample.stage, []).append(sample)
    records: list[dict[str, Any]] = []
    for index in sorted(grouped):
        ids: list[str] = []
        for sample in grouped[index]:
            if sample.state_id not in ids:
                ids.append(sample.state_id)
        last = grouped[index][-1]
        records.append(
            {
                "index": index,
                "label": last.label,
                "pseudo_time": last.pseudo_time,
                "load_case": str(getattr(last.state, "load_case", "") or ""),
                "result_state_id": last.state_id,
                "result_state_ids": ids,
                "increment_count": len(ids),
            }
        )
    return records


def _shoe_record(support_id: str, history: list[ContactSample], stage_by_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    frictionless = _frictionless(history[0].contact)
    summaries = [_stage_summary(index, stage_by_index[index], history) for index in sorted(stage_by_index) if
                 any(sample.stage == index for sample in history)]
    findings: list[dict[str, Any]] = []

    if not frictionless:
        findings.extend(_slip_findings(history))
        findings.extend(_reversal_findings(history))
        findings.extend(_over_limit_findings(history))
    # Lift-off and reseat describe the pipe leaving and regaining a shoe, so they
    # hold for a frictionless support too: a mu = 0 shoe can still be the one
    # that drops away, and that is the more consequential outcome.
    findings.extend(_separation_findings(history))
    if not frictionless:
        findings.extend(_unloaded_findings(history))

    utilizations = [
        sample.contact.utilization
        for sample in history
        if sample.contact.utilization is not None
    ]
    return {
        "support_id": support_id,
        "frictionless": frictionless,
        "note": (
            "Friction coefficient is zero, so this shoe has no Coulomb cone: it carries "
            "compression only and has no stick/slip classification."
            if frictionless
            else ""
        ),
        "ever_slid": any(_is_sliding(sample.contact) for sample in history),
        "ever_open": any(_is_open(sample.contact) for sample in history),
        "peak_normal_force_n": max((sample.contact.normal_force for sample in history), default=0.0),
        "peak_tangential_force_n": max((sample.tangential for sample in history), default=0.0),
        "peak_utilization": max(utilizations) if utilizations else None,
        "peak_slip_m": max((_magnitude(sample.contact.slip) for sample in history), default=0.0),
        "max_gap_m": max((sample.contact.gap for sample in history), default=0.0),
        "final_status": history[-1].contact.status,
        "stages": summaries,
        "findings": findings,
    }


def _stage_summary(index: int, stage: dict[str, Any], history: list[ContactSample]) -> dict[str, Any]:
    members = [sample for sample in history if sample.stage == index]
    last = members[-1]
    utilizations = [sample.contact.utilization for sample in members if sample.contact.utilization is not None]
    return {
        "index": index,
        "label": stage["label"],
        "pseudo_time": stage["pseudo_time"],
        "result_state_id": stage["result_state_id"],
        "status": last.contact.status,
        "statuses": sorted({sample.contact.status for sample in members}),
        "transitioned": len({sample.contact.status for sample in members}) > 1,
        "normal_force_n": last.contact.normal_force,
        "tangential_force_n": last.tangential,
        "friction_limit_n": last.contact.friction_limit,
        "utilization": last.contact.utilization,
        "gap_m": last.contact.gap,
        "slip_m": _magnitude(last.contact.slip),
        "peak_normal_force_n": max(sample.contact.normal_force for sample in members),
        "peak_tangential_force_n": max(sample.tangential for sample in members),
        "peak_slip_m": max((_magnitude(sample.contact.slip) for sample in members), default=0.0),
        "peak_gap_m": max(sample.contact.gap for sample in members),
        "peak_utilization": max(utilizations) if utilizations else None,
    }


def _finding(
    kind: str,
    severity: str,
    support_id: str,
    stage_indices: Sequence[int],
    history: Sequence[ContactSample],
    values: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    """One finding, anchored at the first stage of the span it covers."""
    first = next(sample for sample in history if sample.stage == stage_indices[0])
    last = next(sample for sample in reversed(history) if sample.stage == stage_indices[-1])
    return {
        "id": "",
        "kind": kind,
        "severity": severity,
        "support_ids": [support_id],
        "stage_index": stage_indices[0],
        "stage_indices": list(stage_indices),
        "stage_label": first.label,
        "final_stage_label": last.label,
        "spans_stages": len(stage_indices) > 1,
        "pseudo_time": first.pseudo_time,
        "result_state_id": first.state_id,
        "values": values,
        "note": note,
    }


def _slip_findings(history: list[ContactSample]) -> list[dict[str, Any]]:
    """Each unbroken run of stages in which the shoe was on the Coulomb cone.

    Sliding is the state the cone is *in*: a shoe at 100% of mu*N has slid, so
    the finding reports how long it stayed there rather than raising a defect.
    """
    by_stage: dict[int, list[ContactSample]] = {}
    for sample in history:
        if _is_sliding(sample.contact):
            by_stage.setdefault(sample.stage, []).append(sample)
    findings = []
    for run in _contiguous_runs(list(by_stage)):
        peak = max((sample for stage in run for sample in by_stage[stage]), key=lambda sample: sample.tangential)
        findings.append(
            _finding(
                "slip",
                SEVERITY_ATTENTION,
                peak.contact.support_id,
                run,
                history,
                {
                    "tangential_force_n": peak.tangential,
                    "friction_limit_n": peak.contact.friction_limit,
                    "utilization": peak.contact.utilization,
                    "slip_m": max((_magnitude(sample.contact.slip) for stage in run for sample in by_stage[stage]), default=0.0),
                    "normal_force_n": peak.contact.normal_force,
                },
                "The tangential force reached the Coulomb cone, so the shoe slid instead of sticking.",
            )
        )
    return findings


def _reversal_findings(history: list[ContactSample]) -> list[dict[str, Any]]:
    """Stages where the tangential force reversed direction.

    Compared across the whole increment history, not within a stage: the
    reversal caused by removing a load usually happens in the first increment
    after the stage boundary, and a per-stage walk would compare that increment
    against nothing and miss it entirely.
    """
    stages: dict[int, ContactSample] = {}
    reversed_from: dict[int, float] = {}
    for previous, current in zip(history, history[1:]):
        if not (_has_tangential_force(current.contact) and _has_tangential_force(previous.contact)):
            continue
        dot = sum(a * b for a, b in zip(current.contact.tangential_force, previous.contact.tangential_force))
        if dot < 0.0:
            stages.setdefault(current.stage, current)
            reversed_from.setdefault(current.stage, previous.tangential)
    findings = []
    for run in _contiguous_runs(list(stages)):
        peak = max((stages[stage] for stage in run), key=lambda sample: sample.tangential)
        findings.append(
            _finding(
                "force_reversal",
                SEVERITY_INFO,
                peak.contact.support_id,
                run,
                history,
                {
                    "tangential_force_n": peak.tangential,
                    "previous_tangential_force_n": reversed_from[peak.stage],
                },
                "The tangential force reversed direction, so the shoe is now being dragged the other way.",
            )
        )
    return findings


def _over_limit_findings(history: list[ContactSample]) -> list[dict[str, Any]]:
    samples = [sample for sample in history if (sample.contact.utilization or 0.0) > OVER_LIMIT_UTILIZATION]
    if not samples:
        return []
    worst = max(samples, key=lambda sample: sample.contact.utilization or 0.0)
    return [
        _finding(
            "over_limit",
            SEVERITY_ATTENTION,
            worst.contact.support_id,
            _contiguous_runs([sample.stage for sample in samples])[0],
            history,
            {
                "tangential_force_n": worst.tangential,
                "friction_limit_n": worst.contact.friction_limit,
                "utilization": worst.contact.utilization,
            },
            "The reported tangential force exceeds the Coulomb cone, which the sliding branch "
            "should never produce; treat it as a convergence artifact.",
        )
    ]


def _separation_findings(history: list[ContactSample]) -> list[dict[str, Any]]:
    """Each departure from the surface and each return to it.

    An open shoe has no friction capacity at all, so both transitions are
    reported even for a mu = 0 support: the pipe leaving its shoe is the
    structural event, whatever the cone says.
    """
    findings: list[dict[str, Any]] = []
    for index, sample in enumerate(history):
        previous = history[index - 1] if index else None
        opened = _is_open(sample.contact) and sample.contact.gap > GAP_TOLERANCE_M
        was_open = previous is not None and _is_open(previous.contact)
        if opened and not was_open:
            run = [candidate.stage for candidate in history[index:] if _is_open(candidate.contact)]
            findings.append(
                _finding(
                    "lift_off",
                    SEVERITY_ATTENTION,
                    sample.contact.support_id,
                    _contiguous_runs(run)[0],
                    history,
                    {
                        "gap_m": sample.contact.gap,
                        "normal_force_n": sample.contact.normal_force,
                        "friction_limit_n": sample.contact.friction_limit,
                    },
                    "The shoe left the surface, so its friction capacity fell to zero while it is clear.",
                )
            )
        elif not _is_open(sample.contact) and was_open:
            findings.append(
                _finding(
                    "reseat",
                    SEVERITY_INFO,
                    sample.contact.support_id,
                    [sample.stage],
                    history,
                    {
                        "normal_force_n": sample.contact.normal_force,
                        "friction_limit_n": sample.contact.friction_limit,
                        "gap_m": sample.contact.gap,
                    },
                    "The shoe came back down onto the surface and carries load again.",
                )
            )
    return findings


def _unloaded_findings(history: list[ContactSample]) -> list[dict[str, Any]]:
    """Stages in which the shoe carried no normal force and so no friction.

    The reference stage is excluded: an unloaded reference state is the
    definition of a reference, not an observation about the shoe.
    """
    peak_by_stage: dict[int, float] = {}
    labels: dict[int, str] = {}
    for sample in history:
        if sample.stage == 0:
            continue
        labels.setdefault(sample.stage, sample.label)
        peak_by_stage[sample.stage] = max(
            peak_by_stage.get(sample.stage, 0.0), sample.contact.normal_force
        )
    if not peak_by_stage:
        return []
    unloaded = [stage for stage, peak in sorted(peak_by_stage.items()) if peak <= FORCE_TOLERANCE_N]
    if not unloaded:
        return []
    runs = _contiguous_runs(unloaded)
    return [
        _finding(
            "unloaded",
            SEVERITY_INFO,
            history[0].contact.support_id,
            run,
            history,
            {
                "stages_without_normal_force": run,
                "stage_labels": [labels[stage] for stage in run],
            },
            "The shoe carries no normal force, so it has no friction capacity in these stages.",
        )
        for run in runs
    ]

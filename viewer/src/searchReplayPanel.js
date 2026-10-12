import { branchIds, hydraulicSolverLabel, latestViewRequest, parameterDiff, replayAt, reviewForCheck, safeReplayUrl } from "./searchReplay.js";

const text = value => value === undefined || value === null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
const label = value => String(value ?? "").replaceAll("_", " ");
function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = text(content);
  if (className) node.className = className;
  return node;
}
function button(content, action, attrs = {}) {
  const node = element("button", content);
  node.type = "button";
  Object.assign(node.dataset, attrs);
  node.addEventListener("click", action);
  return node;
}

export function initSearchReplay(container, { manifest, baseUrl, showView, highlight }) {
  let sequence = manifest.events.at(-1)?.sequence ?? 0;
  let candidateId = manifest.candidates.find(c => c.outcome === "selected")?.id ?? manifest.candidates[0]?.id;
  let evaluationId = null, referenceId = null, branchOnly = false;
  const requests = latestViewRequest();
  let snapshot, selected, evaluation;
  let shownView = null;

  async function display(view, check = null) {
    const request = requests.next();
    const message = container.querySelector("[data-search-view-status]");
    if (message) message.textContent = view?.availability === "available" ? "Loading recorded view…" : view?.message ?? "No view recorded at this event";
    try {
      const url = view?.availability === "available" ? safeReplayUrl(baseUrl, view.bundle) : null;
      if (url !== shownView || !url) {
        shownView = null;
        await showView(url, request);
      }
      if (!request.current()) return;
      shownView = url;
      if (check) highlight(check);
      if (message?.isConnected) message.textContent = view?.availability === "available"
        ? (check ? "Showing the recorded finding" : evaluation ? "Showing this sealed attempt" : "Reference geometry — no solver result")
        : view?.message ?? "No geometry or verified results available";
      return { availability: view?.availability ?? 'unavailable', url, check };
    } catch (error) {
      if (!request.current()) return;
      shownView = null;
      await showView(null, request);
      if (message?.isConnected) message.textContent = `View unavailable: ${error.message}`;
      return { availability: 'unavailable', url: null, error: error.message, check };
    }
  }

  function select(id) { candidateId = id; evaluationId = null; render(); }
  function move(next) { sequence = next; evaluationId = null; render(); }

  function render({ displayView = true } = {}) {
    const focused = container.contains(document.activeElement) ? document.activeElement : null;
    const focusLabel = focused?.getAttribute("aria-label");
    const focusCandidate = focused?.dataset.searchCandidate;
    const focusText = focused?.tagName === "BUTTON" ? focused.textContent : null;
    snapshot = replayAt(manifest, sequence);
    selected = snapshot.candidates.find(c => c.id === candidateId) ?? snapshot.candidates[0];
    candidateId = selected?.id;
    evaluation = selected?.evaluations.find(e => e.id === evaluationId) ?? selected?.evaluations.at(-1);
    evaluationId = evaluation?.id ?? null;
    const panel = element("div", undefined, "search-replay-panel");
    const nav = element("div", undefined, "search-event-nav");
    const previous = button("Previous event", () => move(Math.max(0, sequence - 1)), { searchPrevious: "" });
    const next = button("Next event", () => move(Math.min(manifest.events.at(-1)?.sequence ?? 0, sequence + 1)), { searchNext: "" });
    previous.disabled = sequence <= 0;
    next.disabled = sequence >= (manifest.events.at(-1)?.sequence ?? 0);
    nav.append(previous, next);
    const slider = element("input");
    Object.assign(slider, { type: "range", min: "0", max: String(manifest.events.at(-1)?.sequence ?? 0), step: "1", value: String(sequence) });
    slider.setAttribute("aria-label", "Search event");
    slider.dataset.searchEvent = "";
    slider.addEventListener("change", () => move(Number(slider.value)));
    const event = snapshot.event;
    const eventText = element("p", event ? `Event ${event.sequence}: ${label(event.kind)} · ${event.candidate_id ?? "run"}` : "Before the first recorded event");
    eventText.dataset.searchEventLabel = "";
    panel.append(nav, slider, eventText, element("p", `Search time (UTC): ${event?.timestamp ?? event?.at_utc ?? "—"}`, "search-note"),
      element("p", `Feasible so far: ${snapshot.bestFeasibleIds.join(", ") || "none"}`, "search-note"));

    const branch = element("label", "Show selected branch");
    const branchToggle = element("input"); branchToggle.type = "checkbox"; branchToggle.checked = branchOnly;
    branchToggle.addEventListener("change", () => { branchOnly = branchToggle.checked; render(); });
    branch.prepend(branchToggle); panel.append(branch);
    const branchMembers = branchOnly ? branchIds(snapshot.candidates, candidateId) : null;
    const rows = branchMembers ? snapshot.candidates.filter(c => branchMembers.has(c.id)) : snapshot.candidates;
    const list = element("div", undefined, "search-candidates");
    list.setAttribute("role", "group"); list.setAttribute("aria-label", "Recorded candidates");
    for (const row of rows) {
      const item = button(`${row.id} · ${label(row.outcome)}`, () => select(row.id), { searchCandidate: row.id });
      item.setAttribute("aria-pressed", String(row.id === candidateId)); list.append(item);
    }
    panel.append(list);
    if (selected) {
      const heading = element("h2", selected.id); heading.dataset.searchSelected = candidateId;
      const outcome = element("p", `Recorded outcome: ${label(evaluation?.outcome ?? selected.outcome)}`, "search-outcome");
      outcome.dataset.searchOutcome = "";
      panel.append(heading, outcome, element("p", selected.rationale, "search-note"));
      const missingOperations = (manifest.run.settings?.operations ?? []).filter(op => !evaluation?.completed_operations?.includes(op));
      if (missingOperations.length) panel.append(element("p", `Required operations not completed in this attempt: ${missingOperations.join(", ")}`, "search-note"));
      const missingChecks = (manifest.run.check_specs ?? []).filter(spec => spec.required && !evaluation?.checks?.some(check => check.constraint_id === spec.id));
      if (missingChecks.length) panel.append(element("p", `Required checks not recorded: ${missingChecks.map(spec => spec.id).join(", ")}`, "search-note"));
      panel.append(element("p", "Result state / increment belongs to the solver; it is separate from search event time.", "search-note"));
      const parentLinks = element("div", undefined, "search-parents");
      parentLinks.append(element("span", "Parents: "));
      if (!selected.parent_ids.length) parentLinks.append(element("span", "No declared parent (independent proposal)"));
      for (const id of selected.parent_ids) parentLinks.append(snapshot.candidates.some(c => c.id === id)
        ? button(id, () => select(id)) : element("span", `${id} (not available at this event)`));
      panel.append(parentLinks);
      if (selected.evaluations.length) {
        const attempts = element("select"); attempts.setAttribute("aria-label", "Evaluation attempt"); attempts.dataset.searchAttempt = "";
        for (const [index, entry] of selected.evaluations.entries()) {
          const option = element("option", `Attempt ${index + 1} · ${label(entry.status)} · ${label(entry.outcome)}`);
          option.title = `${entry.attempt_id} / ${entry.id}`;
          option.value = entry.id; option.selected = entry.id === evaluationId; attempts.append(option);
        }
        attempts.addEventListener("change", () => { evaluationId = attempts.value; render(); }); panel.append(attempts);
      }
      const stateMessage = element("p", "", "search-note"); stateMessage.dataset.searchViewStatus = ""; stateMessage.setAttribute("role", "status");
      panel.append(stateMessage);
      if (evaluation?.source_event_kind === "attempt.recovered") {
        panel.append(element("p", `Crash-recovered attempt ${evaluation.attempt_id}: sealed execution without a published evaluation. No checks or candidate decision inferred.`, "search-note"));
        for (const artifact of evaluation.review.artifact_diagnostics ?? []) {
          panel.append(element("p", `Archived recovery evidence: ${artifact.path} (${artifact.availability})`, "search-note"));
        }
      }
      const controls = element("div", undefined, "search-event-nav");
      controls.append(button("Reference geometry", () => void display(selected.preview), { searchReference: "" })); panel.append(controls);
      const params = element("details"); params.open = true; params.append(element("summary", "Parameters and comparison"));
      const compare = element("select"); compare.setAttribute("aria-label", "Compare candidate parameters"); compare.dataset.searchCompare = "";
      const none = element("option", "No comparison"); none.value = ""; compare.append(none);
      for (const row of snapshot.candidates.filter(c => c.id !== candidateId)) {
        const option = element("option", row.id); option.value = row.id; option.selected = row.id === referenceId; compare.append(option);
      }
      compare.addEventListener("change", () => { referenceId = compare.value || null; render(); }); params.append(compare);
      const reference = snapshot.candidates.find(c => c.id === referenceId);
      const table = element("table"); table.dataset.searchParameters = "";
      const header = element("tr"); for (const title of ["Parameter", reference ? reference.id : "Value", ...(reference ? [candidateId] : [])]) header.append(element("th", title));
      table.append(header);
      for (const key of [...new Set([...Object.keys(selected.parameters), ...Object.keys(reference?.parameters ?? {})])].sort()) {
        const row = element("tr"); row.append(element("td", key));
        if (reference) row.append(element("td", reference.parameters[key])); row.append(element("td", selected.parameters[key]));
        if (reference && parameterDiff(selected, reference).some(d => d.key === key)) row.className = "search-changed";
        table.append(row);
      }
      params.append(table);
      if (reference) params.append(button(`Inspect ${reference.id} in this view`, () => select(reference.id)));
      panel.append(params);
      const decisions = evaluation?.decisions ?? selected.decisions;
      for (const decision of decisions) {
        panel.append(element("p", `Decision at event ${decision.sequence}: ${label(decision.outcome)} · ${(decision.reason_codes ?? []).map(label).join(", ")}`, "search-decision"));
        if (decision.details && Object.keys(decision.details).length) panel.append(element("pre", decision.details, "search-details"));
      }
      if (selected.build?.objectives) panel.append(element("p", `Declared objective values: ${text(selected.build.objectives)}`, "search-note"));
      for (const check of evaluation?.checks ?? []) {
        const callout = element("details", undefined, `search-check search-${check.verdict}`);
        callout.dataset.searchConstraint = check.constraint_id;
        callout.open = check.verdict === "fail" || check.verdict === "unknown";
        callout.append(element("summary", `${label(check.verdict)} · ${check.constraint_id} · ${check.operation ?? (hydraulicSolverLabel(check.basis) ? check.details?.scenario_id ?? "hydraulic scenario" : "cold")}`),
          element("p", `${check.required ? "Required" : "Advisory"} · ${check.basis} · ${check.result_state_id ?? (hydraulicSolverLabel(check.basis) ? "steady hydraulic result" : "reference geometry")}`),
          element("p", `${check.message ?? check.reason_text ?? ""} (${label(check.reason_code)})`), element("p", `Targets: ${(check.entity_refs ?? []).join(", ") || "whole model"}`));
        if (check.measured_value != null || check.limit != null) callout.append(element("p", `${text(check.measured_value)} ${check.comparator ?? "against"} ${text(check.limit)} ${check.unit ?? ""}`));
        for (const clash of check.details?.clashes ?? []) callout.append(element("p", `Collision at ${text(clash.location)} m; native distance ${text(clash.distance_m)} m; penetration ${text(clash.penetration_m)} m`));
        if (check.details?.coverage) {
          const coverage = element("details"); coverage.append(element("summary", "Geometry coverage"), element("p", text(check.details.coverage)));
          callout.append(coverage);
        }
        callout.append(button("Show finding", () => void display(reviewForCheck(selected, evaluation, check), check), { searchFinding: check.constraint_id }));
        for (const ref of check.evidence_refs ?? []) {
          if (evaluation.review?.availability === "available" && evaluation.completed_operations?.includes(check.operation)) {
            const filename = String(ref).split(/[\\/]/).at(-1);
            try {
              const link = element("a", filename);
              link.href = safeReplayUrl(baseUrl, `${evaluation.review.bundle}/artifacts/${check.operation}/${filename}`);
              link.target = "_blank"; link.rel = "noopener noreferrer"; link.dataset.searchEvidence = "";
              callout.append(link);
            } catch { callout.append(element("span", "Evidence path unavailable")); }
          } else callout.append(element("span", `Archived evidence (unavailable in this view): ${ref}`));
        }
        panel.append(callout);
      }
      const diagnostics = snapshot.events.filter(e => e.kind === "evaluation.diagnostic" && e.candidate_id === candidateId && e.payload.attempt_id === evaluation?.attempt_id);
      for (const diagnostic of diagnostics) panel.append(element("p", diagnostic.payload.message, "search-note"));
    } else panel.append(element("p", "No candidate has been proposed yet."));
    if (manifest.availability_diagnostics?.length) {
      const diagnostics = element("details"); diagnostics.append(element("summary", "Artifact availability"));
      for (const item of manifest.availability_diagnostics) diagnostics.append(element("p", `${item.availability}: ${item.path}`)); panel.append(diagnostics);
    }
    container.replaceChildren(panel);
    if (focused) [...container.querySelectorAll("input, select, button")].find(node =>
      focusLabel ? node.getAttribute("aria-label") === focusLabel : focusCandidate ? node.dataset.searchCandidate === focusCandidate :
      focusText && node.tagName === "BUTTON" && node.textContent === focusText)?.focus({ preventScroll: true });
    if (displayView) void display(evaluation?.review ?? selected?.preview);
  }
  render();
  return { select, move, snapshot: () => snapshot,
    async seek(next, id, attempt, checkIndex = null, reference = false) {
      sequence = next; candidateId = id; evaluationId = attempt;
      render({ displayView: false });
      if (id && selected?.id !== id || attempt && evaluation?.id !== attempt) throw new Error('Film scope not available at this event');
      const check = checkIndex == null ? null : evaluation?.checks?.[checkIndex];
      if (checkIndex != null && !check) throw new Error('Film finding not available at this event');
      return display(reference ? selected?.preview : check ? (reviewForCheck(selected, evaluation, check)) : evaluation?.review ?? selected?.preview, reference ? null : check);
    }
  };
}

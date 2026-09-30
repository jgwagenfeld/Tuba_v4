import { profileDiagram, profilePropertyRows } from "./profileDiagram.js";

function familyOf(row) { return row.family ?? row.profile.kind; }
function heightOf(profile) {
  return profile.height_m ?? profile.height_z_m ?? profile.outer_diameter_m ?? 2 * (profile.radius_m ?? 0);
}

export function filterProfiles(rows, { search = "", family = "", minHeight = "", maxHeight = "" } = {}) {
  const term = search.replace(/\s/g, "").toLowerCase();
  const min = minHeight === "" ? -Infinity : Number(minHeight);
  const max = maxHeight === "" ? Infinity : Number(maxHeight);
  return rows.filter(row => {
    const text = `${row.name} ${row.profile_name ?? ""} ${familyOf(row)} ${row.nps ? `NPS${row.nps}` : ""} ${row.schedule ? `Sch${row.schedule}` : ""}`.replace(/\s/g, "").toLowerCase();
    const height = heightOf(row.profile) * 1000;
    return text.includes(term) && (!family || familyOf(row) === family) && height >= min && height <= max;
  });
}

export function profileDefinition(row, name) {
  name = name.trim();
  if (!name) throw new Error("Enter a section name.");
  if (row.profile.kind === "pipe") {
    const od = row.profile.outer_diameter_m, wt = row.profile.wall_thickness_m;
    if (!Number.isFinite(od) || !Number.isFinite(wt) || wt <= 0 || 2 * wt >= od) throw new Error("Invalid pipe dimensions: expected OD > 2 × WT > 0.");
    return `model.add_pipe_section(${JSON.stringify(name)}, OD=${od}, WT=${wt})`;
  }
  if (row.profile.kind !== "ibeam") throw new Error("This profile cannot be inserted from the catalog.");
  return `model.add_ibeam_section(${JSON.stringify(name)}, profile_name=${JSON.stringify(row.name)})`;
}

export function profileInsertion(code, position, definition) {
  const offset = code.slice(0, position).lastIndexOf("\n") + 1;
  const indent = /^[\t ]*/.exec(code.slice(offset))[0];
  return { offset, text: `${indent}${definition}\n` };
}

export function initProfileLibrary(dialog, { format, sourceCurrent, reveal, insert }) {
  const find = name => dialog.querySelector(`[data-profiles-${name}]`);
  const search = find("search"), family = find("family");
  const min = find("min"), max = find("max"), list = find("list");
  const preview = find("preview"), sectionName = find("section-name");
  const form = find("insert-form"), revealButton = find("reveal");
  const status = find("status");
  let data = null, tab = "catalog", selected = null;

  function updateCode() {
    sectionName.setCustomValidity("");
    const duplicate = data.used.some(row => row.name === sectionName.value.trim());
    if (duplicate) sectionName.setCustomValidity("This section already exists. Choose another name.");
    find("code").textContent = sectionName.value.trim() ? profileDefinition(selected, sectionName.value) : "";
  }

  function showProfile(row) {
    selected = row;
    preview.hidden = !row;
    if (!row) return;
    find("name").textContent = row.profile_name ? `${row.name} · ${row.profile_name}` : row.name;
    const diagram = profileDiagram(row.profile);
    find("figure").replaceChildren(...(diagram ? [diagram] : []));
    const table = find("properties");
    table.replaceChildren();
    const dimensions = Object.entries(row.profile).filter(([key, value]) => key.endsWith("_m") && typeof value === "number" && key !== "collision_radius_m");
    const rows = dimensions.map(([key, value]) => ({
      label: key.replace(/_m$/, "").replace(/_/g, " "), value: `${Number((value * 1000).toFixed(3))} mm`
    }));
    rows.push(...profilePropertyRows(row.profile, format));
    for (const { label, value } of rows) {
      const tr = document.createElement("tr"), th = document.createElement("th"), td = document.createElement("td");
      th.scope = "row"; th.textContent = label; td.textContent = value;
      tr.append(th, td); table.append(tr);
    }
    const source = find("source");
    source.textContent = tab === "catalog" || row.profile_name
      ? row.source ?? `${data.source}. ${data.source_note}` : "Project section defined in model.py.";
    if (tab === "catalog" && row.source_url?.startsWith("https://")) {
      const link = document.createElement("a");
      link.href = row.source_url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = "Dimension table"; source.append(" ", link);
    }
    form.hidden = tab !== "catalog";
    revealButton.hidden = tab !== "used";
    revealButton.disabled = !Number.isInteger(row.source_line) || !sourceCurrent();
    find("definition-note").textContent = tab === "used"
      ? !sourceCurrent() ? "Sections reflect the last successful run. Run model.py to refresh definitions and line links."
        : !Number.isInteger(row.source_line) ? "This section has no recorded model.py line." : `Defined at model.py:${row.source_line}`
      : "Inserts at the start of the current line. Assign the section to members in Python.";
    if (tab === "catalog") {
      let name = row.name;
      let suffix = 2;
      while (data.used.some(used => used.name === name)) name = `${row.name}_${suffix++}`;
      sectionName.value = name;
      updateCode();
    }
    for (const button of list.children) button.setAttribute("aria-pressed", String(button.dataset.profileName === row.name));
  }

  function showRows(preferred) {
    if (!data) return;
    const rows = filterProfiles(tab === "catalog" ? data.catalog : data.used, {
      search: search.value, family: family.value, minHeight: min.value, maxHeight: max.value
    });
    list.replaceChildren();
    for (const row of rows) {
      const button = document.createElement("button"), detail = document.createElement("small");
      button.type = "button"; button.dataset.profileName = row.name;
      button.setAttribute("aria-pressed", "false");
      detail.textContent = row.profile.kind === "pipe"
        ? `${row.nps ? `NPS ${row.nps} · ${/^\d+$/.test(row.schedule) ? "Sch " : ""}${row.schedule} · ` : ""}OD ${Number((row.profile.outer_diameter_m * 1000).toFixed(2))} × WT ${Number((row.profile.wall_thickness_m * 1000).toFixed(2))} mm`
        : `${familyOf(row)} · ${Number((heightOf(row.profile) * 1000).toFixed(2))} mm high`;
      button.append(row.name, detail);
      button.addEventListener("click", () => showProfile(row));
      list.append(button);
    }
    status.textContent = `${rows.length} ${tab === "used" ? "sections in this model" : "profiles"}${rows.length ? "" : " — no matches"}`;
    showProfile(rows.find(row => row.name === (preferred ?? selected?.name)) ?? rows[0] ?? null);
  }

  function selectTab(next, preferred) {
    tab = next;
    for (const button of dialog.querySelectorAll("[data-profiles-tab]")) button.setAttribute("aria-pressed", String(button.dataset.profilesTab === tab));
    family.replaceChildren(new Option("All families", ""), ...[...new Set((tab === "catalog" ? data.catalog : data.used).map(familyOf))].sort().map(value => new Option(value, value)));
    showRows(preferred);
  }

  for (const control of [search, family, min, max]) control.addEventListener("input", () => showRows());
  for (const button of dialog.querySelectorAll("[data-profiles-tab]")) button.addEventListener("click", () => {
    if (data) selectTab(button.dataset.profilesTab);
  });
  find("close").addEventListener("click", () => dialog.close());
  sectionName.addEventListener("input", updateCode);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!selected || !form.reportValidity()) return;
    const definition = profileDefinition(selected, sectionName.value);
    dialog.close();
    insert(definition);
  });
  revealButton.addEventListener("click", () => {
    if (revealButton.disabled || !sourceCurrent()) return;
    dialog.close();
    reveal(selected.source_line);
  });

  return async function open(section) {
    data = null;
    list.replaceChildren(); preview.hidden = true;
    search.value = family.value = min.value = max.value = "";
    status.textContent = "Loading profiles…";
    if (!dialog.open) dialog.showModal();
    search.focus();
    try {
      const response = await fetch("/api/profiles", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || !payload.ok || !Array.isArray(payload.catalog) || !Array.isArray(payload.used)) throw new Error(payload.error || "Studio did not return a profile catalog.");
      data = payload;
      selectTab(section ? "used" : "catalog", section);
    } catch (error) {
      status.textContent = `Profiles unavailable: ${error.message}`;
    }
  };
}

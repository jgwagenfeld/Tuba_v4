const MAX_UPLOAD = 16 * 1024 * 1024;

export function publishedDownloads(entry) {
  return Object.entries(entry?.downloads ?? {}).filter(([kind, uri]) =>
    ["project", "ifc"].includes(kind) &&
    uri === `downloads/${entry.id}.${kind === "project" ? "zip" : "ifc"}`);
}

export function renderPublishedDownloads(dialog, entry) {
  const downloads = dialog.querySelector("[data-exchange-downloads]");
  downloads.replaceChildren();
  for (const [kind, uri] of publishedDownloads(entry)) {
    const link = document.createElement("a");
    link.href = uri;
    link.download = "";
    link.textContent = kind === "project" ? "Project ZIP" : "IFC geometry only";
    downloads.append(link, document.createTextNode(" "));
  }
}

export async function fetchIfcCapability(fetcher = fetch) {
  const response = await fetcher("/api/project", { cache: "no-store" });
  if (!response.ok) throw new Error(`Studio answered ${response.status}`);
  const current = await response.json();
  if (!current.ok || !current.ifc) throw new Error("Studio did not return IFC capability.");
  return current.ifc;
}

export async function fetchIfcExport(fetcher = fetch) {
  const response = await fetcher("/api/ifc/export", { cache: "no-store" });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.error || `IFC export refused (${response.status})`);
  }
  return {
    blob: await response.blob(),
    filename: response.headers.get("content-disposition")?.match(/filename="([A-Za-z0-9_.-]+)"/)?.[1] ?? "model.ifc"
  };
}

export function initExchange(dialog, { project, catalogEntry, reload }) {
  const file = dialog.querySelector("[data-ifc-file]");
  const previewButton = dialog.querySelector("[data-ifc-preview]");
  const attachButton = dialog.querySelector("[data-ifc-attach]");
  const convertButton = dialog.querySelector("[data-ifc-convert]");
  const references = dialog.querySelector("[data-ifc-references]");
  const products = dialog.querySelector("[data-ifc-products]");
  const status = dialog.querySelector("[data-ifc-status]");
  const exportLink = dialog.querySelector("[data-ifc-export]");
  const exportScope = dialog.querySelector("[data-ifc-export-scope]");
  const studioOnly = dialog.querySelector("[data-ifc-studio-only]");
  const form = dialog.querySelector("[data-ifc-assignments]");
  let capability = project?.ifc ?? null;
  let preview = null;
  let attachedId = null;
  let busy = false;

  renderPublishedDownloads(dialog, catalogEntry);

  function say(message) { status.textContent = message; }
  function controls() {
    const available = Boolean(capability?.available);
    studioOnly.hidden = Boolean(project);
    file.hidden = previewButton.hidden = attachButton.hidden = convertButton.hidden = form.hidden = !project;
    exportLink.hidden = !project || !capability?.export_available;
    file.disabled = previewButton.disabled = attachButton.disabled = convertButton.disabled = !available || busy;
    attachButton.disabled ||= !preview || !file.files?.length;
    convertButton.disabled ||= !attachedId || !products.querySelector("input:checked");
    exportLink.disabled = !capability?.export_available || busy;
    exportScope.textContent = project ? (capability?.export_reason || capability?.export_scope || "Geometry only") : "Published downloads are listed on each Gallery card when available.";
    if (project && !available) say(capability?.reason || "Install IFC support: pip install 'tuba[ifc]'");
  }
  function renderReferences() {
    references.replaceChildren();
    for (const reference of capability?.references ?? []) {
      const row = document.createElement("p");
      row.textContent = `${reference.name} · ${reference.product_count} products · ${reference.warning_count} warnings `;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${reference.name}`);
      remove.addEventListener("click", () => run(async () => {
        await request("/api/ifc/remove", { id: reference.id });
        capability.references = capability.references.filter(item => item.id !== reference.id);
        if (attachedId === reference.id) attachedId = null;
        renderReferences();
        controls();
        await reload();
      }));
      row.append(remove);
      references.append(row);
    }
  }
  function renderPreview() {
    products.replaceChildren();
    if (!preview) return;
    const info = document.createElement("p");
    info.textContent = `${preview.products.length} products · ${preview.length_unit} (${preview.metres_per_unit} m/unit) · bounds ${preview.bounds_m?.join(", ")} m`;
    products.append(info);
    for (const product of preview.products) {
      const row = document.createElement("label");
      const check = document.createElement("input");
      check.type = "checkbox";
      check.value = product.guid;
      check.disabled = !product.convertible;
      check.addEventListener("change", controls);
      row.append(check, document.createTextNode(` ${product.ifc_class} · ${product.name || product.guid} · ${product.guid}${product.reason ? ` — ${product.reason}` : ""}`));
      products.append(row);
    }
    for (const warning of preview.warnings ?? []) {
      const row = document.createElement("p");
      row.textContent = `Warning${warning.guid ? ` ${warning.guid}` : ""}: ${warning.reason}`;
      products.append(row);
    }
  }
  async function request(path, body) {
    const raw = body instanceof File;
    const response = await fetch(path, {
      method: "POST",
      headers: raw ? { "Content-Type": "application/octet-stream", "X-IFC-Name": body.name } : { "Content-Type": "application/json" },
      body: raw ? body : JSON.stringify(body)
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || `${response.status} ${response.statusText}`);
    }
    return response;
  }
  async function run(action) {
    if (busy) return;
    busy = true;
    controls();
    try { await action(); }
    catch (error) { say(error.message); }
    finally { busy = false; controls(); }
  }
  async function refresh() {
    if (!project) return;
    exportLink.hidden = true;
    try {
      capability = await fetchIfcCapability();
      project.ifc = capability;
      renderReferences();
      controls();
    } catch (error) {
      say(`IFC capability unavailable: ${error.message}`);
    }
  }
  exportLink.addEventListener("click", () => run(async () => {
    const { blob, filename } = await fetchIfcExport();
    download(blob, filename);
    say("Downloaded native model geometry only; IFC references and solver results are excluded.");
  }));
  previewButton.addEventListener("click", () => run(async () => {
    const selected = file.files?.[0];
    if (!selected) throw new Error("Choose an IFC file.");
    if (selected.size < 1 || selected.size > MAX_UPLOAD) throw new Error("IFC file must be 1 byte to 16 MiB.");
    preview = (await (await request("/api/ifc/preview", selected)).json()).preview;
    attachedId = null;
    renderPreview();
    say("Preview only. Attach to keep this reference in the project.");
  }));
  attachButton.addEventListener("click", () => run(async () => {
    if (!preview || !file.files?.[0]) throw new Error("Preview an IFC file first.");
    const result = await (await request("/api/ifc/attach", file.files[0])).json();
    attachedId = result.reference.id;
    capability.references = [...capability.references.filter(ref => ref.id !== attachedId), result.reference];
    renderReferences();
    await reload();
    say("Reference attached. The authored model and solver results are unchanged.");
  }));
  convertButton.addEventListener("click", () => run(async () => {
    const guids = [...products.querySelectorAll("input:checked")].map(input => input.value);
    if (!attachedId || !guids.length) throw new Error("Attach a reference and select straight pipes.");
    const payload = {
      reference_id: attachedId, guids,
      material: { name: form.elements.material_name.value, E_pa: Number(form.elements.E_pa.value),
        nu: Number(form.elements.nu.value), rho_kg_m3: Number(form.elements.rho_kg_m3.value) },
      section: { name: form.elements.section_name.value,
        outer_diameter_m: Number(form.elements.outer_diameter_m.value),
        wall_thickness_m: Number(form.elements.wall_thickness_m.value) }
    };
    if (!form.reportValidity()) return;
    const blob = await (await request("/api/ifc/convert", payload)).blob();
    download(blob, "ifc-pipes.zip");
    say("Downloaded a new unsolved project. Author loads and supports before Code_Aster solve.");
  }));
  file.addEventListener("change", () => { preview = null; attachedId = null; renderPreview(); controls(); });
  renderReferences();
  controls();
  return refresh;
}

export function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

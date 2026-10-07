const HTML_LIMIT = 8 * 1024 * 1024;
const CSV_LIMIT = 4 * 1024 * 1024;
const TOTAL_LIMIT = 32 * 1024 * 1024;
const REPORT_POLICY = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'";

export async function boundedBytes(response, limit) {
  if (!response.ok) throw new Error(`Report download refused (${response.status}).`);
  if (Number(response.headers.get("content-length")) > limit) throw new Error("Report download exceeds the size limit.");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > limit) throw new Error("Report download exceeds the size limit.");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}

export async function passiveReport(html, baseUrl, fetcher = fetch) {
  const document = new DOMParser().parseFromString(
    `<meta http-equiv="Content-Security-Policy" content="${REPORT_POLICY}">` + html, "text/html");
  document.querySelectorAll("script,iframe,frame,object,embed,form,meta,base,link").forEach(node => node.remove());
  for (const node of document.querySelectorAll("*")) {
    for (const attribute of [...node.attributes]) {
      if (/^on/i.test(attribute.name)) node.removeAttribute(attribute.name);
    }
  }
  const links = [...document.querySelectorAll("a[href]")];
  const csvLinks = links.filter(link => /^reports\/[A-Za-z0-9_-]+\.csv$/.test(link.getAttribute("href")));
  if (csvLinks.length > 32) throw new Error("Report contains too many CSV downloads.");
  let total = 0;
  for (const link of links) {
    const href = link.getAttribute("href");
    link.removeAttribute("target");
    if (/^#[A-Za-z0-9_-]+$/.test(href)) continue;
    if (!csvLinks.includes(link)) { link.removeAttribute("href"); continue; }
    const bytes = await boundedBytes(await fetcher(new URL(href, baseUrl)), Math.min(CSV_LIMIT, TOTAL_LIMIT - total));
    total += bytes.length;
    // Data downloads remain readable in the opaque sandbox; parent-origin blob
    // URLs do not. FileReader avoids a handwritten base64 encoder.
    const url = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(new Blob([bytes], { type: "text/csv;charset=utf-8" }));
    });
    link.href = url;
    link.download = href.split("/").at(-1);
  }
  const policy = document.createElement("meta");
  policy.httpEquiv = "Content-Security-Policy";
  policy.content = REPORT_POLICY;
  document.head.prepend(policy);
  const referrer = document.createElement("meta");
  referrer.name = "referrer";
  referrer.content = "no-referrer";
  document.head.prepend(referrer);
  return { html: "<!doctype html>" + document.documentElement.outerHTML, document };
}

export async function openReport(url, browser = window) {
  const popup = browser.open("", "_blank", "popup");
  if (!popup) throw new Error("Allow a popup to open the engineering report.");
  popup.opener = null;
  const document = popup.document;
  document.title = "Engineering report";
  document.body.textContent = "Loading report…";
  try {
    const bytes = await boundedBytes(await fetch(url), HTML_LIMIT);
    const report = await passiveReport(new TextDecoder().decode(bytes), new URL(url, browser.location.href));
    if (popup.closed) return;
    const controls = document.createElement("nav");
    const print = document.createElement("button");
    print.textContent = "Print report";
    print.addEventListener("click", () => popup.print());
    const close = document.createElement("button");
    close.textContent = "Close report";
    close.addEventListener("click", () => popup.close());
    controls.append(print, close);
    const frame = document.createElement("iframe");
    frame.title = "Engineering review tables";
    frame.setAttribute("sandbox", "allow-downloads");
    frame.srcdoc = report.html;
    frame.style.cssText = "display:block;width:100%;height:calc(100vh - 3rem);border:0";
    document.body.style.margin = "0";
    const printable = printableReport(report.document, document);
    const style = document.createElement("style");
    style.textContent = `.print-report{display:none}@media print{nav,iframe{display:none}.print-report{display:block}
      table{border-collapse:collapse;width:100%;font:9pt sans-serif;overflow-wrap:anywhere}
      td,th{border:1px solid #aaa;padding:3px;text-align:left}thead{display:table-header-group}
      h1,h2,h3{break-after:avoid}body{font:10pt sans-serif}p{margin:.5em 0}}`;
    document.head.append(style);
    document.body.replaceChildren(controls, frame, printable);
  } catch (error) {
    document.body.textContent = error.message;
    throw error;
  }
}

// Printing an iframe clips it to the viewport. Rebuild the full print content
// from text cells only; received markup and attributes never enter the popup.
function printableReport(source, target) {
  const result = target.createElement("main");
  result.className = "print-report";
  for (const node of source.body.querySelectorAll("h1,h2,h3,p,table")) {
    if (node.closest("td,th")) continue;
    const tag = node.tagName.toLowerCase();
    const copy = target.createElement(tag);
    if (tag !== "table") copy.textContent = node.textContent;
    else {
      for (const row of node.rows) {
        const tr = target.createElement("tr");
        for (const cell of row.cells) {
          const td = target.createElement(cell.tagName.toLowerCase());
          td.textContent = cell.textContent;
          tr.append(td);
        }
        copy.append(tr);
      }
    }
    result.append(copy);
  }
  return result;
}

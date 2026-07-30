// Repair accessibility defects in the Zensical 0.0.51 theme's own markup.
// Nothing here patches Tuba content; every target is theme-generated, and the
// theme mounts most of it from its own bundle after this script runs.
// viewer/e2e/pages-artifact.spec.js gates the result: a theme upgrade that
// changes this markup fails the axe audit instead of silently regressing.

const patchDocument = () => {
  // Per-line anchors are scroll targets with no text; keeping the id preserves
  // line links, dropping href takes them out of the tab order.
  for (const anchor of document.querySelectorAll('a[id^="__codelineno-"][href]')) {
    anchor.removeAttribute("href");
  }
  // The clipboard button's wrapper is not navigation, so it must not be a landmark.
  for (const nav of document.querySelectorAll("nav.md-code__nav:not([role])")) {
    nav.setAttribute("role", "none");
  }
  // The drawer scrim is a decorative click target; its header toggle stays exposed.
  document.querySelector("label.md-overlay")?.setAttribute("aria-hidden", "true");
};

const patchSearchDialog = (root) => {
  const [search, filters] = root.querySelectorAll("button");
  search?.setAttribute("aria-label", "Search");
  filters?.setAttribute("aria-label", "Filters");

  const input = root.querySelector("input");
  // Results are links in a list, not listbox options, so combobox is the wrong role.
  input?.removeAttribute("role");
  input?.setAttribute("aria-label", "Search");

  // Dialog headings must continue the page outline instead of restarting at 3.
  for (const heading of root.querySelectorAll("h3:not([aria-level])")) {
    heading.setAttribute("aria-level", "2");
  }
  for (const heading of root.querySelectorAll("h4:not([aria-level])")) {
    heading.setAttribute("aria-level", "3");
  }

  // The tag-filter panel always scrolls but holds nothing focusable until a site
  // defines tags, so it needs its own tab stop to stay keyboard-reachable. One
  // panel exists for the dialog's lifetime, so stop scanning once it is tagged.
  if (root.querySelector('div[tabindex="0"]')) return;
  for (const panel of root.querySelectorAll("div")) {
    if (
      getComputedStyle(panel).overflowY === "scroll" &&
      !panel.querySelector("a, button, input, [tabindex]")
    ) {
      panel.tabIndex = 0;
    }
  }
};

const patchSearchHost = () => {
  const host = [...document.body.children].find((element) => element.shadowRoot);
  if (!host || host.hasAttribute("role")) return;
  // The dialog is injected outside every landmark, and it is the site search.
  host.setAttribute("role", "search");
  host.setAttribute("aria-label", "Search");

  // Result breadcrumbs ship at an alpha that misses the 4.5:1 contrast floor.
  const root = host.shadowRoot;
  const contrast = document.createElement("style");
  contrast.textContent = "menu{color:rgb(var(--color-foreground)/.6)!important}";
  root.append(contrast);

  // The dialog's contents mount after its host, and re-render on every query.
  new MutationObserver(() => patchSearchDialog(root)).observe(root, {
    childList: true,
    subtree: true
  });
  patchSearchDialog(root);
};

const patchTheme = () => {
  patchDocument();
  patchSearchHost();
};

patchTheme();
// The theme's bundle mounts the search dialog and the per-code-block clipboard
// buttons after this script runs; both patches above are idempotent.
new MutationObserver(patchTheme).observe(document.body, { childList: true, subtree: true });

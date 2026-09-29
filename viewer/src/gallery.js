// The gallery is the front door for someone who has never heard of Tuba: a set
// of reviews described by the engineering question each one answers, rather
// than by the id of the study that produced it.
//
// Cards are plain links, so a selection is an ordinary navigation and the
// existing boot path runs unchanged on arrival - there is no second state
// machine to keep in step. The geometry is shown, not rendered: each card is a
// photograph the Pages build shot from the very bundle shipping beside it, so
// the picture cannot drift from the model and the landing page costs no WebGL
// context. Twelve live viewports would spend twelve browser contexts to draw
// twelve frozen frames.

import { publishedDownloads } from "./exchange.js";

// The catalog did not load, so there is no grid to draw. This used to have no
// state at all: loadBundleCatalog returned [], shouldShowGallery said no, and the
// visitor landed in an empty studio shell titled "Scene" with a status line
// reading "Ready" and no way to tell that the front door had failed. A named
// review is still reachable by URL, so the page says what is wrong and keeps
// that door open.
export function renderGalleryUnavailable(container, reason) {
  if (!container) return;
  container.replaceChildren();

  const masthead = document.createElement("div");
  masthead.className = "gallery-masthead";
  const wordmark = document.createElement("span");
  wordmark.className = "wordmark";
  wordmark.textContent = "Tuba";
  const tagline = document.createElement("span");
  tagline.className = "gallery-tagline";
  tagline.textContent = "Code_Aster-backed piping engineering and result review";
  masthead.append(wordmark, tagline);
  container.append(masthead);

  const heading = document.createElement("h1");
  heading.className = "gallery-heading";
  heading.textContent = "Reviews are unavailable";
  container.append(heading);

  const notice = document.createElement("p");
  notice.className = "gallery-unavailable";
  notice.setAttribute("role", "status");
  notice.textContent = reason;
  container.append(notice);

  const help = document.createElement("p");
  help.className = "gallery-intro";
  help.textContent =
    "A review you have a link to still opens - add ?bundle=<id> to this address. "
    + "To run one locally, open its project folder with the studio command below.";
  container.append(help);
  container.append(galleryFooter());
}

/** Turn a bundle id into a readable title, for catalogs that carry only ids. */
export function titleFromId(bundleId) {
  return String(bundleId)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

/**
 * Accept every catalog shape the viewer meets: the rich list published by the
 * pages build, the bare id list its dev server discovers from public/, and the
 * empty list emitted into the packaged shell.
 */
// A bundle reaches the viewer as a catalog id ("code-aster-review"), as a path
// ("/code-aster-review"), or with a trailing slash. The header switcher used to
// compare those forms directly, so a bundle requested by path matched no option
// and the browser fell back to showing the first one - the control named a
// model you were not looking at.
export function bundleKey(value) {
  return String(value ?? "")
    .replace(/^\.?\/+/, "")
    .replace(/\/+$/, "");
}

export function normalizeCatalog(catalog) {
  if (!Array.isArray(catalog)) {
    return [];
  }
  return catalog
    .map((entry) => {
      if (typeof entry === "string") {
        return { id: entry, title: titleFromId(entry) };
      }
      if (entry && typeof entry.id === "string") {
        return { ...entry, title: entry.title || titleFromId(entry.id) };
      }
      return null;
    })
    .filter(Boolean);
}

export function bundleIdsOf(catalog) {
  return normalizeCatalog(catalog).map((entry) => entry.id);
}

/**
 * The gallery replaces the scene only when there is a real choice to offer and
 * nobody asked for a specific review. A shared single-bundle folder and an
 * embedded viewer both open straight into their review, as before.
 */
export function shouldShowGallery({ requestedBundle, embed, catalog }) {
  return !requestedBundle && !embed && normalizeCatalog(catalog).length > 1;
}

// Solver present or not, size, and cases. A review with no solver behind it says
// so, and says it in a way that cannot be mistaken for a solved one: the whole
// point of the change is that a grid of 13 cards must not imply 13 analyses.
export function reviewFacts(entry) {
  const facts = [];
  const solved = entry.solved ?? entry.has_results ?? null;
  if (solved === false) {
    facts.push({
      kind: "unsolved",
      text: "Model only — not solved",
      title: "This bundle ships geometry without Code_Aster results. Opening it shows the model, not a review."
    });
  } else {
    const cases = Number(entry.case_count ?? entry.load_case_count ?? 0);
    if (cases > 0) {
      facts.push({
        kind: "cases",
        text: cases === 1 ? "1 load case" : `${cases} load cases`,
        title: "Load cases Code_Aster solved for this review"
      });
    }
    const elements = Array.isArray(entry.elements) ? entry.elements.length : 0;
    if (elements > 0) {
      facts.push({
        kind: "elements",
        text: `${elements} element type${elements === 1 ? "" : "s"}`,
        title: entry.elements.join(", ")
      });
    }
    const solver = entry.solver ?? entry.solver_name ?? null;
    if (solver) {
      const version = entry.solver_version ?? entry.runtime_version ?? null;
      facts.push({
        kind: "solver",
        text: version ? `${solver} ${version}` : String(solver),
        title: "Solver that produced these results"
      });
    }
  }
  if (entry.evidence) {
    facts.push({ kind: "evidence", text: entry.evidence });
  }
  return facts;
}

function card(entry) {
  const link = document.createElement("a");
  link.className = "gallery-card";
  link.href = `?bundle=${encodeURIComponent(entry.id)}`;
  link.dataset.galleryCard = entry.id;

  if (entry.thumbnail) {
    const image = document.createElement("img");
    image.className = "gallery-card-image";
    image.src = entry.thumbnail;
    image.alt = "";
    image.loading = "lazy";
    // Thumbnails are build artifacts - the Pages build photographs the bundles
    // it just produced - so a working tree that has not built one yet has no
    // picture to show. A card without its image still reads; a broken-image
    // icon in place of one reads as a bug in the review it is advertising.
    image.addEventListener("error", () => image.remove(), { once: true });
    link.append(image);
  }

  const body = document.createElement("div");
  body.className = "gallery-card-body";

  // The question leads and the title is the eyebrow beneath it. 13709fc swapped
  // the two, which put a whole sentence into the uppercase eyebrow style and
  // failed the pages-gallery check that every card asks a question.
  const heading = document.createElement("h2");
  heading.className = "gallery-card-question";
  heading.textContent = entry.question || entry.title;
  body.append(heading);

  if (entry.question) {
    const title = document.createElement("p");
    title.className = "gallery-card-title";
    title.textContent = entry.title;
    body.append(title);
  }

  if (entry.summary) {
    const summary = document.createElement("p");
    summary.className = "gallery-card-summary";
    summary.textContent = entry.summary;
    body.append(summary);
  }

  if (Array.isArray(entry.elements) && entry.elements.length > 0) {
    // Which elements a review actually solved is the first thing an engineer
    // asks of an example, and it is not guessable from the picture: the
    // friction review idealises its pipes as POU_D_T beams, not as TUYAU_3M.
    // Solver names rather than friendly labels, because "Beam" on a pipe
    // review would be the lie the raw name avoids.
    const elements = document.createElement("ul");
    elements.className = "gallery-card-elements";
    elements.dataset.galleryElements = "";
    for (const element of entry.elements) {
      const chip = document.createElement("li");
      chip.className = "gallery-card-element";
      chip.textContent = element;
      elements.append(chip);
    }
    body.append(elements);
  }

  // The facts a reviewer chooses on. PROFILE_EVIDENCE collapsed six profiles
  // onto three strings, four of which were the literal word "Results" - so 12 of
  // 13 cards wore the same uppercase badge saying nothing, and the one slot
  // where the product could have earned trust repeated itself instead. What an
  // engineer actually uses to pick a review is size: how many elements the
  // solver idealised, how many load cases were solved, and whether there is a
  // solver behind it at all. All three come from the catalog; none are inferred.
  const facts = reviewFacts(entry);
  if (facts.length) {
    const list = document.createElement("ul");
    list.className = "gallery-card-facts";
    list.dataset.galleryFacts = "";
    for (const fact of facts) {
      const item = document.createElement("li");
      item.className = `gallery-card-fact gallery-card-fact-${fact.kind}`;
      item.textContent = fact.text;
      if (fact.title) item.title = fact.title;
      list.append(item);
    }
    body.append(list);
  }

  // Kept, but demoted and never the thing twelve cards all say. The catalog's own
  // prose still belongs on the card when there is only prose to say.
  if (entry.evidence && !facts.some((fact) => fact.kind === "evidence")) {
    const evidence = document.createElement("p");
    evidence.className = "gallery-card-evidence";
    evidence.dataset.galleryEvidence = "";
    evidence.textContent = entry.evidence;
    body.append(evidence);
  }

  if (entry.project) {
  // Provenance, not an instruction: the folder that produced this review,
  // the way a figure is credited. The studio command itself is stated once in
  // the footer - thirteen copies of it were thirteen chances to drift, and
  // this line sits inside the card's one link, so anything that looked
  // clickable here would have been a link to the review instead of the thing
  // it appeared to promise. It is not <code>, because <code> reads as "copy
  // me".
    const origin = document.createElement("p");
    origin.className = "gallery-card-origin";
    origin.dataset.galleryOrigin = "";
    origin.textContent = entry.project;
    body.append(origin);
  }

  link.append(body);
  const wrapper = document.createElement("div");
  wrapper.className = "gallery-card-frame";
  wrapper.append(link);
  const downloads = publishedDownloads(entry);
  if (downloads.length) {
    const nav = document.createElement("nav");
    nav.className = "gallery-card-downloads";
    nav.setAttribute("aria-label", `${entry.title} downloads`);
    for (const [kind, uri] of downloads) {
      const download = document.createElement("a");
      download.href = uri;
      download.download = "";
      download.textContent = kind === "project" ? "Project ZIP" : "IFC geometry";
      nav.append(download);
    }
    wrapper.append(nav);
  }
  if (entry.build_identity) {
    const identity = document.createElement("small");
    identity.className = "gallery-card-identity";
    identity.textContent = `Source ${entry.build_identity.replace(/^sha256:/, "").slice(0, 12)}`;
    identity.title = `Source ${entry.build_identity}`;
    identity.setAttribute("aria-label", identity.title);
    wrapper.append(identity);
  }
  return wrapper;
}

export function renderGallery(container, catalog) {
  const entries = normalizeCatalog(catalog);
  container.replaceChildren();

  // This page is the URL people share, and it used to name the product
  // nowhere: the word "Tuba" appeared only in <title>. A visitor arriving cold
  // could read twelve cards and still have nothing saying what Tuba is or
  // where to get it.
  const masthead = document.createElement("div");
  masthead.className = "gallery-masthead";
  const wordmark = document.createElement("span");
  // One class for the product mark on both surfaces: the review header draws
  // the same one, so the two cannot drift apart in weight or tracking again.
  wordmark.className = "wordmark";
  wordmark.textContent = "Tuba";
  const tagline = document.createElement("span");
  tagline.className = "gallery-tagline";
  tagline.textContent = "Code_Aster-backed piping engineering and result review";
  // The viewer build hash used to sit here, in the prime top-left position beside
  // the wordmark. A truncated content hash is not provenance to a reader, and
  // this is the one place on the page where a reader looks first. It is still
  // published - in the footer, with the per-card source hashes, where provenance
  // belongs - and the solver facts it displaced now have somewhere to go.
  const fact = document.createElement("span");
  fact.className = "gallery-masthead-fact";
  const solved = entries.filter((entry) => entry.solved !== false).length;
  fact.textContent = `${solved} solved review${solved === 1 ? "" : "s"} of ${entries.length}`;
  masthead.append(wordmark, tagline, fact);
  container.append(masthead);

  const heading = document.createElement("h1");
  heading.className = "gallery-heading";
  heading.textContent = "Structural and piping reviews";
  container.append(heading);

  const intro = document.createElement("p");
  intro.className = "gallery-intro";
  intro.textContent =
    "Each review below is a model that was analysed and kept together with its evidence - beams, " +
    "pipes, bars, cables and solids, in whatever mix the study needed. " +
    "Open one to inspect the geometry, the deformed shape, the stresses and the support loads.";
  container.append(intro);

  // Grouped, because thirteen undifferentiated cards is the page's one decision
  // point offering thirteen equal options with no way to narrow it. The grouping
  // is derived from what each review actually solved, which the catalog already
  // declares - so a reader looking for a pipe review sees the pipe reviews, and
  // the one decision inside a group is which engineering question to open.
  //
  // The first group is open and the rest are behind a disclosure with their
  // counts, which also gives a 3400px monotonic scroll a mid-point.
  for (const group of groupEntries(entries)) {
    container.append(galleryGroup(group));
  }
  container.append(galleryFooter());
  return entries.length;
}

// What a review is made of, in the reviewer's terms. Derived from the declared
// Code_Aster MODELISATION names rather than from a hand-written label, so a
// review cannot be filed under something it is not.
const GROUPS = [
  {
    id: "pipe",
    label: "Piping and plant",
    note: "Pipe runs, expansion loops, racks and process layouts.",
    test: (entry) => entry.elements?.some((element) => ["TUYAU_3M", "DIS_T", "DIS_TR"].includes(element))
  },
  {
    id: "beams",
    label: "Beams, bars and cables",
    note: "Line and beam studies, including tension-only members.",
    test: (entry) => entry.elements?.some((element) => ["POU_D_T", "BARRE", "CABLE"].includes(element))
  },
  {
    id: "solids",
    label: "3D solids and meshes",
    note: "Volume studies, and the mesh a 1D model discretises into.",
    test: (entry) => entry.elements?.includes("3D")
  },
  {
    id: "geometry",
    label: "Geometry only",
    note: "Models published without a solve. No stresses, no reactions, no verdict.",
    // Checked first, because a geometry-only card may still declare the elements
    // its geometry is made of - and it must not be filed as an analysis.
    test: (entry) => entry.solved === false
  }
];

// Claim order, distinct from the display order above. See groupEntries.
const CLAIM_ORDER = Object.freeze(["geometry", "solids", "pipe", "beams"]);

export function groupEntries(entries) {
  const claimed = new Set();
  const groups = [];
  // The order cards are CLAIMED in is not the order they are DISPLAYED in, and
  // conflating the two is what put a hydrogen plant layout on a shelf labelled
  // "Beams, bars and cables": the walk used to run over the table reversed, so
  // `beams` tested before `pipe` and any card declaring POU_D_T was claimed by
  // beams even when it also declared TUYAU_3M. Four of the eight leading cards
  // were piping reviews under the wrong name.
  //
  // Claim order, most decisive first:
  //   geometry - decided by the solver flag, not by an element name, so a card
  //              it claims can never also sit in a subject group;
  //   solids   - "3D" is the most specific thing a card can declare;
  //   pipe     - a pipe review is a piping product's core case and wins a tie
  //              against a beam, which is almost always also on the model as
  //              rack steel;
  //   beams    - last, so it takes what the others did not.
  for (const id of CLAIM_ORDER) {
    const group = GROUPS.find((candidate) => candidate.id === id);
    if (!group) continue;
    const members = entries.filter((entry) => !claimed.has(entry.id) && group.test(entry));
    if (members.length === 0) continue;
    for (const member of members) claimed.add(member.id);
    groups.unshift({ ...group, members });
  }
  const rest = entries.filter((entry) => !claimed.has(entry.id));
  if (rest.length) groups.unshift({ id: "other", label: "Other", note: "", members: rest });
  // The largest group leads: it is above the fold, so the page opens on whatever
  // most of the set actually is rather than on whichever group sorted first.
  groups.sort((a, b) => b.members.length - a.members.length);
  return groups;
}

function galleryGroup(group) {
  const section = document.createElement("section");
  section.className = "gallery-group";
  section.dataset.galleryGroup = group.id;
  // A group of six or more is open; a smaller one is behind its count. The
  // consequence is that at most one group is ever open, because only one can
  // reach six in a set of thirteen - and the disclosure in front of every card
  // is exactly the friction the grouping was meant to remove.
  const open = group.members.length >= 6;
  const heading = document.createElement("h2");
  heading.className = "gallery-group-heading";
  heading.textContent = group.label;
  const count = document.createElement("span");
  count.className = "gallery-group-count";
  count.textContent = `${group.members.length}`;
  heading.append(count);
  if (group.note) {
    const note = document.createElement("p");
    note.className = "gallery-group-note";
    note.textContent = group.note;
    section.append(heading, note);
  } else {
    section.append(heading);
  }
  const grid = document.createElement("div");
  grid.className = "gallery-grid";
  grid.dataset.galleryGrid = "";
  for (const entry of group.members) {
    grid.append(card(entry));
  }
  if (open) {
    section.append(grid);
  } else {
    const details = document.createElement("details");
    details.className = "gallery-group-details";
    const summary = document.createElement("summary");
    summary.textContent = group.label;
    details.append(summary, grid);
    section.append(details);
  }
  return section;
}

//: Where the gallery sends a reader who has finished the grid.
//
// Peak-end: the last thing on this page was the bottom of the twelfth card,
// so the journey ended by running out. Links are relative because the docs
// site is this page's parent on Pages, which keeps them right on a fork or
// any other host rather than pinning one deployment's domain.
const FOOTER_LINKS = Object.freeze([
  ["Setup", "../setup.html"],
  ["Tutorial", "../tutorial.html"],
  ["Modeling", "../modeling.html"],
  ["Source", "https://github.com/jgwagenfeld/Tuba_v4"]
]);

function galleryFooter() {
  const footer = document.createElement("footer");
  footer.className = "gallery-footer";

  const note = document.createElement("p");
  note.className = "gallery-footer-note";
  note.textContent =
    "Tuba builds a piping model in Python, solves it with Code_Aster, and keeps the "
    + "result together with the run that produced it. Every review above is published "
    + "with its own evidence.";
  footer.append(note);

  // Provenance, where it belongs. The viewer build hash used to sit in the
  // masthead beside the wordmark - the prime position on a shared page, spent on a
  // string no reader can act on. Each card already carries the source hash of the
  // model.py it was built from, so this line states the one fact the cards cannot:
  // which build of the viewer drew them.
  const build = document.createElement("p");
  build.className = "gallery-footer-build";
  const shortBuild = String(__TUBA_VIEWER_BUILD__).replace(/^sha256:/, "").slice(0, 12);
  build.textContent = `Drawn by viewer ${shortBuild}; each card names the model.py it was built from.`;
  build.title = `Viewer ${__TUBA_VIEWER_BUILD__}`;
  footer.append(build);

  // The command is stated here, once. It used to be on all thirteen cards,
  // which put a terminal command at reader prominence on a page whose subject
  // is the engineering question - and the card is one link, so clicking it
  // opened the review rather than doing what the <code> styling promised.
  const edit = document.createElement("p");
  edit.className = "gallery-footer-edit";
  const editLead = document.createElement("span");
  editLead.textContent = "Each review is a project folder. Open any of them with ";
  const command = document.createElement("code");
  command.textContent = "python -m tuba.cli_studio examples/<id>";
  edit.append(editLead, command, ".");
  footer.append(edit);

  const nav = document.createElement("nav");
  nav.className = "gallery-footer-links";
  nav.setAttribute("aria-label", "Tuba documentation");
  for (const [label, href] of FOOTER_LINKS) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    nav.append(link);
  }
  footer.append(nav);
  return footer;
}

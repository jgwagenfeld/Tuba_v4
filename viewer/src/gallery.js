// The gallery is the front door for someone who has never heard of Tuba: a set
// of reviews described by the engineering question each one answers, rather
// than by the id of the study that produced it.
//
// It renders no geometry and reads no scene. Cards are plain links, so a
// selection is an ordinary navigation and the existing boot path runs
// unchanged on arrival - there is no second state machine to keep in step.

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

  const heading = document.createElement("h2");
  heading.className = "gallery-card-question";
  heading.textContent = entry.title;
  body.append(heading);

  if (entry.question) {
    const title = document.createElement("p");
    title.className = "gallery-card-title";
    title.textContent = entry.question;
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

  if (entry.evidence) {
    // Never dropped: what a review is backed by stays visible on the card even
    // though it is no longer the headline.
    const evidence = document.createElement("p");
    evidence.className = "gallery-card-evidence";
    evidence.dataset.galleryEvidence = "";
    evidence.textContent = entry.evidence;
    body.append(evidence);
  }

  link.append(body);
  return link;
}

export function renderGallery(container, catalog) {
  const entries = normalizeCatalog(catalog);
  container.replaceChildren();

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

  const grid = document.createElement("div");
  grid.className = "gallery-grid";
  grid.dataset.galleryGrid = "";
  for (const entry of entries) {
    grid.append(card(entry));
  }
  container.append(grid);
  return entries.length;
}

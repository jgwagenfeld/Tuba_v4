import "@fontsource/roboto-condensed/latin-400.css";
import "@fontsource/roboto-condensed/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-700.css";
import "./styles.css";
import { renderGallery, renderGalleryUnavailable, shouldShowGallery } from "./gallery.js";

// The gallery and the review are two different front doors, and they were
// bundled as one. main.js statically imported app.js, which statically imports
// renderer.js, which statically imports three - so three.core.js (2.08 MB) was a
// hard boot dependency of the landing page, which never creates a WebGL context.
// Measured on the published gallery: 74.4% of its transfer, 2.87 MB across 64
// requests, to draw thirteen photographs.
//
// The gallery's own comment had the right argument - "the geometry is shown, not
// rendered ... twelve live viewports would spend twelve browser contexts to draw
// twelve frozen frames" - and it never reached the bundle graph. It does now:
// the catalog is read here, and the studio is only imported when a review is
// actually wanted. The scene, the renderer and the three.js core load on the
// review path alone.
//
// The catalog read has to happen twice now, once here to make the decision and
// once inside the studio. It is one small JSON file and it is the same file,
// and the alternative is shipping the renderer to a page that will not use it.
// The same decision app.js makes for itself. It is duplicated rather than shared
// because importing app.js is the thing being avoided, and because a shared
// module would have to be imported by both - which is fine, except the only
// reason to share it is to avoid reading a URLSearchParams twice.
function readStartupConfig() {
  const params = new URLSearchParams(window.location.search);
  return {
    requestedBundle: params.get("bundle"),
    embed: params.get("embed") === "1"
  };
}

async function bootGalleryOrStudio() {
  let catalog = [];
  let catalogError = null;
  try {
    const response = await fetch("./bundles.json");
    if (!response.ok) {
      catalogError = `The gallery catalog is unavailable (HTTP ${response.status}).`;
    } else {
      const bundles = await response.json();
      if (!Array.isArray(bundles)) {
        catalogError = "The gallery catalog is not a list of reviews.";
      } else {
        catalog = bundles;
      }
    }
  } catch (error) {
    catalogError = `The gallery catalog could not be loaded (${error.message}).`;
  }

  const gallery = document.querySelector("[data-gallery]");
  const config = readStartupConfig();
  const showGallery = gallery && shouldShowGallery({ ...config, catalog });
  // A named review is still openable with a broken catalog, so the failure page
  // only speaks when nothing was asked for and the catalog is what is missing.
  const showFailure = gallery && !showGallery && !config.requestedBundle && catalogError;

  if (showGallery || showFailure) {
    document.body.dataset.view = "gallery";
    gallery.hidden = false;
    if (showGallery) renderGallery(gallery, catalog);
    else renderGalleryUnavailable(gallery, catalogError);
    const profiles = document.createElement("button");
    profiles.type = "button";
    profiles.textContent = "Profiles";
    profiles.className = "gallery-profiles";
    profiles.dataset.profilesOpen = "";
    profiles.setAttribute("aria-haspopup", "dialog");
    profiles.setAttribute("aria-controls", "profile-library");
    gallery.querySelector(".gallery-masthead").append(profiles);
    let openProfiles;
    profiles.addEventListener("click", async () => {
      const { initProfileLibrary } = await import("./profileLibrary.js");
      openProfiles ??= initProfileLibrary(document.querySelector("[data-profile-library]"));
      await openProfiles();
    });
    return;
  }

  // The studio reads the catalog itself: it needs the entries for the bundle
  // switcher and the exchange dialog, and one small JSON file twice is cheaper
  // than a module boundary that exists only to hand it over.
  await import("./app.js");
}

void bootGalleryOrStudio();

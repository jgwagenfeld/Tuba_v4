// Pane handles live in the workspace, outside the panes' scrolling content.
// Preferences stay separate from the widths that fit the current window.
export function initPaneResizing({ workspace, codePane, taskRail, inspector }) {
  const panes = [
    { id: "script", element: codePane, handle: workspace.querySelector("[data-code-resize]"),
      property: "--script-pane-width", key: "tuba.codePaneWidthPx", min: 300, side: "left" },
    { id: "controls", element: taskRail, handle: workspace.querySelector("[data-controls-resize]"),
      property: "--review-pane-width", key: "tuba.controlsPaneWidthPx", min: 240, side: "left" },
    { id: "inspector", element: inspector, handle: workspace.querySelector("[data-inspector-resize]"),
      property: "--inspector-width", key: "tuba.inspectorPaneWidthPx", min: 256, side: "right" }
  ];
  for (const pane of panes) {
    try {
      const stored = Number.parseInt(window.localStorage.getItem(pane.key) ?? "", 10);
      pane.preferred = Number.isFinite(stored) && stored > 0 ? stored : null;
    } catch {
      pane.preferred = null;
    }
  }

  const clamp = (value, min, max) => Math.min(max, Math.max(min, Math.round(value)));
  let drag = null;

  function sync() {
    const width = workspace.clientWidth;
    if (!width) return;
    const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
    const defaults = {
      script: Math.min(34 * rem, Math.max(width * 0.42, 20 * rem)),
      controls: Math.min(18.5 * rem, Math.max(width * 0.45, 15 * rem)),
      inspector: 20 * rem
    };
    const phone = window.matchMedia("(max-width: 520px)").matches;
    for (const pane of panes) {
      pane.visible = !pane.element.hidden && pane.element.getClientRects().length > 0;
      // Review controls become a full-width bottom sheet on phones.
      pane.handle.hidden = !pane.visible || (phone && pane.id === "controls");
      pane.minWidth = Math.min(pane.min, Math.floor(width * 0.75));
      pane.maxWidth = Math.floor(width * (phone && pane.side === "right" ? 0.9 : 0.75));
      pane.width = clamp(pane.preferred ?? defaults[pane.id], pane.minWidth, pane.maxWidth);
    }

    const left = panes.find(pane => pane.side === "left" && !pane.handle.hidden);
    const right = panes.find(pane => pane.side === "right" && !pane.handle.hidden);
    if (!phone) {
      // A selection must not push the scene off screen. At smaller widths the
      // reserve yields to the minimum readable widths of the two panes.
      const reserve = Math.min(320, Math.max(0, width - (left?.minWidth ?? 0) - (right?.minWidth ?? 0)));
      if (left) {
        left.width = clamp(left.width, left.minWidth, Math.min(left.maxWidth, width - reserve - (right?.minWidth ?? 0)));
      }
      if (right) {
        right.maxWidth = Math.min(right.maxWidth, width - reserve - (left?.width ?? 0));
        right.width = clamp(right.width, right.minWidth, right.maxWidth);
      }
      if (left) left.maxWidth = Math.min(left.maxWidth, width - reserve - (right?.width ?? 0));
    }
    for (const pane of panes) {
      workspace.style.setProperty(pane.property, `${pane.width}px`);
    }

    const workspaceBox = workspace.getBoundingClientRect();
    for (const pane of panes) {
      if (pane.handle.hidden) continue;
      const box = pane.element.getBoundingClientRect();
      const edge = pane.side === "left" ? box.right : box.left;
      Object.assign(pane.handle.style, {
        left: `${edge - workspaceBox.left - 5}px`,
        top: `${box.top - workspaceBox.top}px`,
        height: `${box.height}px`
      });
      pane.handle.setAttribute("aria-valuemin", String(pane.minWidth));
      pane.handle.setAttribute("aria-valuemax", String(pane.maxWidth));
      pane.handle.setAttribute("aria-valuenow", String(Math.round(box.width)));
      pane.handle.setAttribute("aria-valuetext", `${Math.round(box.width)} pixels wide`);
    }
    if (drag?.pane.handle.hidden) stopDrag();
  }

  function save(pane, value) {
    pane.preferred = value == null ? null : clamp(value, pane.minWidth, pane.maxWidth);
    try {
      if (pane.preferred == null) window.localStorage.removeItem(pane.key);
      else window.localStorage.setItem(pane.key, String(pane.preferred));
    } catch {
      // Resizing still works when browser storage is unavailable.
    }
    sync();
  }

  function stopDrag() {
    if (!drag) return;
    const { pane, pointerId } = drag;
    drag = null;
    delete pane.handle.dataset.dragging;
    delete workspace.dataset.paneResizing;
    if (pane.handle.hasPointerCapture(pointerId)) pane.handle.releasePointerCapture(pointerId);
  }

  for (const pane of panes) {
    const { handle } = pane;
    handle.addEventListener("pointerdown", event => {
      if (event.button !== 0 || drag) return;
      event.preventDefault();
      sync();
      handle.focus({ preventScroll: true });
      handle.setPointerCapture(event.pointerId);
      handle.dataset.dragging = "";
      workspace.dataset.paneResizing = "";
      drag = { pane, pointerId: event.pointerId, x: event.clientX, width: pane.element.getBoundingClientRect().width };
    });
    handle.addEventListener("pointermove", event => {
      if (drag?.pane !== pane || event.pointerId !== drag.pointerId) return;
      const direction = pane.side === "left" ? 1 : -1;
      save(pane, drag.width + direction * (event.clientX - drag.x));
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
      handle.addEventListener(type, event => {
        if (drag?.pane === pane && drag.pointerId === event.pointerId) stopDrag();
      });
    }
    handle.addEventListener("dblclick", () => save(pane, null));
    handle.addEventListener("keydown", event => {
      const step = event.shiftKey ? 40 : 10;
      const direction = pane.side === "left" ? 1 : -1;
      const current = pane.element.getBoundingClientRect().width;
      const values = {
        ArrowLeft: current - direction * step,
        ArrowRight: current + direction * step,
        Home: pane.minWidth,
        End: pane.maxWidth,
        Enter: null
      };
      if (!(event.key in values)) return;
      event.preventDefault();
      save(pane, values[event.key]);
    });
  }

  // Also catches inspector show/hide, drawer height and changes to the host panel.
  const observer = new ResizeObserver(sync);
  observer.observe(workspace);
  for (const pane of panes) observer.observe(pane.element);
  window.addEventListener("resize", sync);
  sync();
  return { sync };
}

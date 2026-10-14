// Only the live project's two stages are retained. Reloads stay fresh by
// default; navigation opts in while the change-notification socket is connected.
export function createStudioBundleCache() {
  const entries = new Map();
  const owned = key => key === "build" || key === "review";
  return {
    async load(key, loader, { reuse = false } = {}) {
      if (!owned(key)) return loader();
      const previous = entries.get(key);
      if (reuse && previous?.value) return previous.value;
      const entry = {};
      entries.set(key, entry);
      try {
        const value = await loader();
        // A live update or newer request may have superseded this load.
        if (entries.get(key) === entry) entry.value = value;
        return value;
      } catch (error) {
        if (entries.get(key) === entry) entries.delete(key);
        throw error;
      }
    },
    remember(key, bundle, state) {
      const entry = entries.get(key);
      if (entry?.value?.bundle === bundle) entry.value = { bundle, state };
    },
    invalidate(key) { entries.delete(key); },
    clear() { entries.clear(); }
  };
}

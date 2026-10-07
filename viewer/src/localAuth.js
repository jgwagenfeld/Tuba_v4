// Browser authority is scoped to the exact origin, including its TCP port.
const STORAGE_KEY = "tuba:access";
let accessToken = null;
let studioOrigin = null;

export function authenticatedFetch(fetcher, origin, token) {
  return (input, options = {}) => {
    const url = new URL(input instanceof Request ? input.url : input, origin);
    if (!token || url.origin !== origin) return fetcher(input, options);
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(options.headers).forEach((value, key) => headers.set(key, value));
    headers.set("Authorization", `Bearer ${token}`);
    // A redirect to another local port must never carry the capability.
    return fetcher(input, { ...options, headers, redirect: "error" });
  };
}

export function initializeLocalAuth(browser = window) {
  const fragment = new URLSearchParams(browser.location.hash.slice(1));
  const supplied = fragment.get("tuba_token");
  if (supplied !== null) {
    fragment.delete("tuba_token");
    browser.history.replaceState(null, "", browser.location.pathname + browser.location.search +
      (fragment.size ? `#${fragment}` : ""));
    if (/^[A-Za-z0-9_-]{43}$/.test(supplied)) browser.sessionStorage.setItem(STORAGE_KEY, supplied);
  }
  accessToken = browser.sessionStorage.getItem(STORAGE_KEY);
  studioOrigin = browser.location.origin;
  if (accessToken) browser.fetch = authenticatedFetch(browser.fetch.bind(browser), studioOrigin, accessToken);
}

export function previewProtocols(url) {
  const target = new URL(url);
  const origin = `${target.protocol === "wss:" ? "https:" : "http:"}//${target.host}`;
  return accessToken && origin === studioOrigin ? ["tuba-preview", `tuba-auth.${accessToken}`] : [];
}

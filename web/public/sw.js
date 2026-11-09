/* Baaki service worker (registered by components/pwa/ServiceWorkerRegister.tsx, production only).
 *
 *   App shell + static assets   precached on install; /_next/static (hashed) and fonts: cache-first
 *   Brand images                /sky.webp, /icons/*, /og/*, /assets/* (AssetSlot photos the user
 *                               supplies later under the same name): stale-while-revalidate, so a
 *                               replaced image shows up on the next visit instead of sticking forever
 *   Pages (navigations)         network-first; cached copy, then /offline when there is no network
 *   /api/media/* (voice notes)  network-first; offline copy kept at most MEDIA_MAX_AGE and
 *                               MEDIA_MAX entries (never forever); Range requests bypass the cache
 *   /api/* (everything else)    network-first; GET responses cached for offline viewing only
 *   The quick exit (lib/safety.ts) deletes the API and media caches.
 *
 * Bump VERSION to drop every old cache on the next visit.
 */
const VERSION = "v2-pale"; // v2: Vyra-style redesign (pale palette, new mark); drops every v1 cache
const SHELL = `baaki-shell-${VERSION}`;
const STATIC = `baaki-static-${VERSION}`;
const PAGES = `baaki-pages-${VERSION}`;
const API = `baaki-api-${VERSION}`;
const MEDIA = `baaki-media-${VERSION}`;
const KEEP = [SHELL, STATIC, PAGES, API, MEDIA];

const SHELL_URLS = [
  "/",
  "/app",
  "/offline",
  "/manifest.webmanifest",
  "/sky.webp",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/maskable-192.png",
  "/icons/apple-touch-icon.png",
  "/icons/favicon.svg",
];
const MEDIA_MAX = 30;
const MEDIA_MAX_AGE = 24 * 60 * 60 * 1000; // 1 day
const NETWORK_TIMEOUT = 8000;
// The neutral quick-exit page is never cached under its own name in a way that reveals Baaki,
// and the employer page is always fresh.
const NO_CACHE_PAGES = [/^\/r\/?$/, /^\/e\//];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((c) => Promise.allSettled(SHELL_URLS.map((u) => c.add(new Request(u, { cache: "reload" })))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("baaki-") && !KEEP.includes(k)).map((k) => caches.delete(k))))
      .then(() => pruneMedia())
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "wipe") {
    event.waitUntil(Promise.all([caches.delete(API), caches.delete(MEDIA), caches.delete(PAGES)]));
  }
});

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("timeout")), ms);
    promise.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}

async function pruneMedia() {
  const cache = await caches.open(MEDIA);
  const reqs = await cache.keys();
  const now = Date.now();
  const entries = [];
  for (const req of reqs) {
    const res = await cache.match(req);
    const at = Number(res && res.headers.get("x-baaki-cached-at")) || 0;
    if (now - at > MEDIA_MAX_AGE) await cache.delete(req);
    else entries.push({ req, at });
  }
  entries.sort((a, b) => b.at - a.at);
  for (const { req } of entries.slice(MEDIA_MAX)) await cache.delete(req);
}

async function stamp(res) {
  const body = await res.clone().blob();
  const headers = new Headers(res.headers);
  headers.set("x-baaki-cached-at", String(Date.now()));
  return new Response(body, { status: res.status, statusText: res.statusText, headers });
}

async function networkFirst(request, cacheName, { timeout = NETWORK_TIMEOUT, stampIt = false } = {}) {
  const cache = await caches.open(cacheName);
  try {
    const res = await withTimeout(fetch(request), timeout);
    if (res && res.ok && res.status === 200 && res.type !== "opaque") {
      const copy = stampIt ? await stamp(res) : res.clone();
      cache.put(request, copy).then(() => (stampIt ? pruneMedia() : null)).catch(() => {});
    }
    return res;
  } catch (err) {
    const hit = await cache.match(request);
    if (hit) {
      if (stampIt) {
        const at = Number(hit.headers.get("x-baaki-cached-at")) || 0;
        if (Date.now() - at > MEDIA_MAX_AGE) {
          await cache.delete(request);
          throw err;
        }
      }
      return hit;
    }
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res && res.ok) cache.put(request, res.clone()).catch(() => {});
  return res;
}

// Brand images can be replaced in place (same file name), so serve the cached copy at once and
// refresh it in the background.
async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  const fresh = fetch(request)
    .then((res) => {
      if (res && res.ok && res.status === 200) cache.put(request, res.clone()).catch(() => {});
      return res;
    })
    .catch(() => null);
  if (hit) {
    fresh.catch(() => {});
    return hit;
  }
  return (await fresh) || Response.error();
}

async function page(request) {
  const url = new URL(request.url);
  if (NO_CACHE_PAGES.some((re) => re.test(url.pathname))) {
    try {
      return await fetch(request);
    } catch {
      return (await caches.match("/offline")) || Response.error();
    }
  }
  try {
    return await networkFirst(request, PAGES, { timeout: 6000 });
  } catch {
    return (await caches.match(request, { ignoreSearch: true })) || (await caches.match(url.pathname)) || (await caches.match("/offline")) || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // uploads, POSTs: straight to the network
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/media/")) {
    if (request.headers.has("range")) return; // audio seeking: 206 responses cannot be cached
    event.respondWith(networkFirst(request, MEDIA, { stampIt: true }));
    return;
  }
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, API, { timeout: 30000 }).catch(() => new Response(JSON.stringify({ error: "offline" }), { status: 503, headers: { "Content-Type": "application/json" } })));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(page(request));
    return;
  }
  if (url.pathname.startsWith("/_next/static/") || /\.(?:woff2?|ttf|otf)$/.test(url.pathname)) {
    event.respondWith(cacheFirst(request)); // content-hashed: safe to keep forever
    return;
  }
  if (
    url.pathname === "/sky.webp" ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.startsWith("/og/") ||
    url.pathname.startsWith("/assets/") ||
    /\.(?:png|svg|jpe?g|webp|avif|gif|ico)$/.test(url.pathname)
  ) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }
  if (url.pathname.startsWith("/_next/")) return; // RSC payloads, HMR: network only
});

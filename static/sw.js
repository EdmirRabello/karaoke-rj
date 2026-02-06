/* static/sw.js */
const SW_VERSION = "2026-02-05-4"; // mude para forçar update

const CACHE_STATIC = `krj-static-${SW_VERSION}`;
const CACHE_PAGES  = `krj-pages-${SW_VERSION}`;

const STATIC_ASSETS = [
  "/static/css/base.css",
  "/static/css/home.css",
  "/static/css/catalog.css",
  "/static/js/theme.js",
  "/static/js/catalog.js",
  "/static/js/image-viewer.js",
  "/static/manifest.json",
];

// recebe comandos do site (ex: SKIP_WAITING)
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("install", (event) => {
  // opcional, ajuda em dev
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE_STATIC)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .catch(() => {})
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((k) => k.startsWith("krj-") && k !== CACHE_STATIC && k !== CACHE_PAGES)
        .map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // só seu domínio
  if (url.origin !== location.origin) return;

  // NÃO intercepta Range (vídeo/stream)
  if (req.headers.has("range")) return;

  const isNav =
    req.mode === "navigate" ||
    (req.headers.get("accept") || "").includes("text/html");

  const isStatic = url.pathname.startsWith("/static/");

  // NÃO cachear vídeo (evita 206 / stream)
  const isMedia = /\.(mp4|webm|mp3|wav)$/i.test(url.pathname);

  if (isNav) {
    event.respondWith(networkFirst(req));
    return;
  }

  if (isStatic && !isMedia) {
    event.respondWith(staleWhileRevalidate(req, CACHE_STATIC));
    return;
  }
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE_PAGES);
  try {
    const fresh = await fetch(req, { cache: "no-store" });
    // só cacheia resposta normal
    if (fresh && fresh.ok && fresh.status === 200 && fresh.type === "basic") {
      cache.put(req, fresh.clone());
    }
    return fresh;
  } catch {
    const cached = await cache.match(req);
    return cached || Response.error();
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);

  const fetchPromise = fetch(req)
    .then((res) => {
      // não cacheia resposta parcial/estranha
      if (res && res.ok && res.status === 200 && res.type === "basic") {
        cache.put(req, res.clone());
      }
      return res;
    })
    .catch(() => null);

  return cached || (await fetchPromise) || Response.error();
}

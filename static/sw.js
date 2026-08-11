/* static/sw.js */
const SW_VERSION = "2026-08-11-offline-1"; // mude para forçar update (opcional; base.html já usa ?v=ASSET_V)

const CACHE_STATIC = `krj-static-${SW_VERSION}`;
const CACHE_PAGES  = `krj-pages-${SW_VERSION}`;
const CACHE_OFFLINE = "krj-offline-shell";

/**
 * ✅ Regra de ouro:
 * - NÃO pré-cachear arquivos que mudam muito (catalog.js / catalog.css),
 *   porque isso prende clientes na versão antiga.
 * - Cachear só o que é bem estável.
 */
const STATIC_ASSETS = [
  `/static/css/base.css?v=${SW_VERSION}`,
  `/static/css/home.css?v=${SW_VERSION}`,
  `/static/js/theme.js?v=${SW_VERSION}`,
  `/static/js/image-viewer.js?v=${SW_VERSION}`,
  `/static/manifest.json?v=${SW_VERSION}`,
];

// recebe comandos do site (ex: SKIP_WAITING)
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "SKIP_WAITING") self.skipWaiting();

  // Prepara explicitamente a tela de consulta para uso sem internet.
  // Funciona inclusive na primeira visita, antes de o SW controlar a página.
  if (data.type === "CACHE_OFFLINE_BUNDLE") {
    const urls = Array.isArray(data.urls) ? data.urls : [];
    const port = event.ports && event.ports[0];
    event.waitUntil((async () => {
      try {
        const cache = await caches.open(CACHE_OFFLINE);
        for (const raw of urls) {
          try {
            const u = new URL(raw, self.location.origin);
            if (u.origin !== self.location.origin) continue;
            const req = new Request(u.href, { credentials: "same-origin" });
            const res = await fetch(req, { cache: "no-store" });
            if (res && res.ok) await cache.put(req, res.clone());
          } catch (_) {}
        }
        port && port.postMessage({ok: true});
      } catch (e) {
        port && port.postMessage({ok: false, error: String(e)});
      }
    })());
  }
});

self.addEventListener("install", (event) => {
  // ajuda a instalar mais rápido
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
        .filter((k) => k.startsWith("krj-") && k !== CACHE_STATIC && k !== CACHE_PAGES && k !== CACHE_OFFLINE)
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
  const isMedia = /\.(mp4|webm|mp3|wav)$/i.test(url.pathname);

  // ✅ arquivos "críticos" que mudam sempre — não podem ficar presos
  const isCriticalAsset =
    url.pathname === "/static/js/catalog.js" ||
    url.pathname === "/static/css/catalog.css";

  // Páginas (HTML) => network-first (já era o seu)
  if (isNav) {
    event.respondWith(networkFirst(req));
    return;
  }

  // Static crítico => network-first (com fallback no cache)
  if (isStatic && isCriticalAsset) {
    event.respondWith(networkFirstStatic(req, CACHE_STATIC));
    return;
  }

  // Static normal (sem mídia) => stale-while-revalidate
  if (isStatic && !isMedia) {
    event.respondWith(staleWhileRevalidate(req, CACHE_STATIC));
    return;
  }

  // demais requests: deixa passar
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE_PAGES);
  try {
    const fresh = await fetch(req, { cache: "no-store" });
    if (fresh && fresh.ok && fresh.status === 200 && fresh.type === "basic") {
      cache.put(req, fresh.clone());
    }
    return fresh;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    const offline = await caches.open(CACHE_OFFLINE);
    return (await offline.match(req)) || Response.error();
  }
}

/**
 * ✅ Network-first para assets críticos:
 * - tenta rede sempre
 * - se falhar, usa cache
 * - se a rede responder ok, atualiza cache
 */
async function networkFirstStatic(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const fresh = await fetch(req, { cache: "no-store" });
    if (fresh && fresh.ok && fresh.status === 200 && fresh.type === "basic") {
      cache.put(req, fresh.clone());
    }
    return fresh;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    const offline = await caches.open(CACHE_OFFLINE);
    return (await offline.match(req)) || Response.error();
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);

  const fetchPromise = fetch(req)
    .then((res) => {
      if (res && res.ok && res.status === 200 && res.type === "basic") {
        cache.put(req, res.clone());
      }
      return res;
    })
    .catch(() => null);

  return cached || (await fetchPromise) || Response.error();
}

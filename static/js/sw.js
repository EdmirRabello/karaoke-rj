const CACHE = "karaoke-rj-v2";
const ASSETS = ["/", "/catalogo", "/static/css/catalog.css", "/static/js/catalog.js", "/static/manifest.json"];
self.addEventListener("install", (e)=>{ e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))); });
self.addEventListener("fetch", (e)=>{
  e.respondWith(
    caches.match(e.request).then((cached)=>{
      return cached || fetch(e.request).then((resp)=>{
        const copy = resp.clone();
        if (e.request.method === "GET" && resp.status === 200 && resp.type === "basic"){
          caches.open(CACHE).then(c=>c.put(e.request, copy));
        }
        return resp;
      }).catch(()=>cached);
    })
  );
});

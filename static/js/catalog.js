/* catalog.js — Catálogo de Músicas (Karaokê RJ)
   ==========================================================
   Regras (simples e estáveis):
   1) AUTO (sem busca e sem clique manual no A–Z):
      - sempre começa em "#"
      - carrega # -> A -> B -> C ... (apenas para frente, via append)
   2) MANUAL (clicou numa letra do A–Z):
      - trava naquela letra
      - scroll infinito carrega só MAIS daquela letra (não avança sozinho)
   3) Busca por texto:
      - desliga o modo letra (letter=null) e faz busca normal
   4) Favoritos:
      - localStorage por USER_ID + sync best-effort no servidor
   5) Top Favoritos (geral)
   6) Overlay filtros (mobile) abre pela lupa e fecha no X
   7) Modal PDFs (Básico/Plus) abre links do Drive

   Endpoints:
   - Busca: /api/search?q=...&limit=...&offset=...&letter=...&tipo=...&plano=...
   - Favoritos:
       POST /api/fav/register  {user_id, code}
       POST /api/fav/remove    {user_id, code}
       GET  /api/fav/user?user_id=...&limit=...
       POST /api/fav/sync      {user_id, codes, mode:"merge"}
   - Detalhes por códigos:
       POST /api/songs/by-codes {codes:[...]}
   - Top Favoritos (geral):
       GET /api/top-favoritos?limit=30
*/

"use strict";

// ==========================================================
// Util
// ==========================================================
const el = (id) => document.getElementById(id);
const mqDesktop = window.matchMedia("(min-width: 981px)");
const isDesktop = () => mqDesktop.matches;

// ==========================================================
// Elementos (inputs / filtros)
// ==========================================================
const qInput = el("q");
const filterTipo = el("filterTipo");
const filterPlano = el("filterPlano");
const btnSearch = el("btnSearch");

// ==========================================================
// UI (painel / lista)
// ==========================================================
const statusDiv = el("status");
const resultsDiv = el("results");
const panelTitle = el("panelTitle");
const countCard = el("countCard");

// ==========================================================
// Botões appbar (mobile)
// ==========================================================
const btnFavUser = el("btnFavUser");
const btnTopFav = el("btnTopFav");
const btnCatalog = el("btnCatalog");

// ==========================================================
// Botões DESKTOP (deskbar)
// ==========================================================
const btnFavUserDesk = el("btnFavUserDesk");
const btnTopFavDesk = el("btnTopFavDesk");
const btnCatalogDesk = el("btnCatalogDesk");

// ==========================================================
// Filtros overlay (mobile)
// ==========================================================
const sidebarEl = el("sidebar");
const btnFiltersToggle = el("btnFiltersToggle"); // X
const filtersChevron = el("filtersChevron");     // ícone X

// ==========================================================
// A–Z
// ==========================================================
const azRail = el("azRail");

// ==========================================================
// Outros
// ==========================================================
const btnInstall = el("btnInstall");

// ==========================================================
// Estado
// ==========================================================
let view = "catalog"; // "catalog" | "favorites" | "top"

// Paginação por letra (sempre)
let paging = {
    offset: 0,
    limit: 60,
    total: null,
    loading: false,
    done: false,
    letter: "#", // ✅ começa no # (não no A)
};

// Controle de modo
let forceLetterMode = false; // true = usuário clicou no A–Z (manual)

// Contador “auto”
let catalogShown = 0;
let catalogTotalAll = null;
let catalogTotalBusy = false;
let advancing = false;

// ==========================================================
// Helpers texto / UI
// ==========================================================
function esc(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatCode(code) {
    const s = String(code ?? "");
    if (!/^\d+$/.test(s)) return s;
    return s.length >= 5 ? s : s.padStart(5, "0");
}

function setStatus(kind, message) {
    if (!statusDiv) return;

    const msg = String(message || "").trim();
    if (!msg) {
        statusDiv.style.display = "none";
        statusDiv.textContent = "";
        statusDiv.className = "status";
        return;
    }

    statusDiv.style.display = "block";
    statusDiv.className = "status status-" + (kind || "info");
    statusDiv.textContent = msg;
}

function setCount(shown, total = null) {
    if (!countCard) return;

    const s = Number(shown || 0);
    const t = (total === null || total === undefined) ? null : Number(total || 0);

    if (t !== null && t >= s) countCard.innerHTML = `🎵 <b>${s}</b> de <b>${t}</b>`;
    else countCard.innerHTML = `🎵 <b>${s}</b> músicas`;
}

function normalizePlan(value) {
    const v = String(value || "")
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    if (v.includes("PLUS")) return "PLUS";
    if (v.includes("BASICO")) return "BÁSICO";
    return "";
}

// Letra do cantor (sem acento). Se não for A-Z => "#"
function getLetterKey(name) {
    const s = String(name || "").trim();
    if (!s) return "#";

    const ch = s[0]
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    if (ch < "A" || ch > "Z") return "#";
    return ch;
}

// ==========================================================
// A–Z (sequência)
// ==========================================================
function normLetter(x) {
    const s = String(x || "").trim();
    if (!s) return "";
    // aceita "#", "%23", "＃" etc
    if (s === "%23") return "#";
    if (s === "＃") return "#";
    return s.toUpperCase();
}

function getAZButtons() {
    if (!azRail) return [];
    return Array.from(azRail.querySelectorAll("[data-letter]"));
}

function getAZLetters() {
    const btns = getAZButtons();
    const letters = btns
        .map(b => normLetter(b.dataset.letter))
        .filter(Boolean);

    // Se no HTML já existe "#", usamos a ordem do HTML.
    // Se não existir, garantimos "#" como primeira.
    if (letters.length) {
        if (!letters.includes("#")) letters.unshift("#");
        return letters;
    }

    // fallback
    return ["#", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"];
}

function setAZActive(letter) {
    const L = normLetter(letter);
    const btns = getAZButtons();
    btns.forEach(b => b.classList.toggle("active", normLetter(b.dataset.letter) === L));
}

function nextLetter(letter) {
    const seq = getAZLetters();
    const L = normLetter(letter);
    const idx = seq.indexOf(L);
    if (idx < 0) return null;
    return seq[idx + 1] || null;
}

// ==========================================================
// USER_ID + Favoritos (localStorage)
// ==========================================================
function getUserId() {
    const KEY = "krj_user_id_v1";
    let id = localStorage.getItem(KEY);
    if (!id || !/^\d+$/.test(id)) {
        id = String(Math.floor(Math.random() * 1_000_000_000));
        localStorage.setItem(KEY, id);
    }
    return Number(id);
}

const USER_ID = getUserId();
const FAV_KEY = `cantus_favs_codes_v1_u${USER_ID}`;

function getFavs() {
    try {
        const cur = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
        return Array.isArray(cur) ? cur.map(String) : [];
    } catch {
        return [];
    }
}

function setFavs(arr) {
    const safe = Array.isArray(arr) ? arr.map(String) : [];
    localStorage.setItem(FAV_KEY, JSON.stringify(safe));
}

function isFav(code) {
    return getFavs().includes(String(code));
}

function updateFavCount() {
    const badge = document.querySelector("#favBadge") || document.querySelector(".fav-badge");
    if (!badge) return;

    const count = getFavs().length;
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.style.display = count ? "inline-flex" : "none";
    badge.classList.toggle("is-big", count > 99);

    if (count) {
        badge.classList.remove("bump");
        void badge.offsetWidth;
        badge.classList.add("bump");
    }
}

// Migração antiga -> nova chave
(function migrateOldFavs() {
    try {
        const old = JSON.parse(localStorage.getItem("krj_favs") || "[]");
        const cur = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
        if (Array.isArray(old) && old.length && (!Array.isArray(cur) || !cur.length)) {
            localStorage.setItem(FAV_KEY, JSON.stringify(old.map(String)));
        }
        localStorage.removeItem("krj_favs");
    } catch {
    }
})();

async function syncFavToServer(code, nowFav) {
    try {
        const url = nowFav ? "/api/fav/register" : "/api/fav/remove";
        await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({user_id: USER_ID, code: Number(code)}),
        });
    } catch (e) {
        console.warn("Falha ao sincronizar favorito", e);
    }
}

function toggleFav(code) {
    const c = String(code);
    let favs = getFavs();

    if (favs.includes(c)) favs = favs.filter(x => x !== c);
    else favs.push(c);

    setFavs(favs);

    const nowFav = favs.includes(c);
    syncFavToServer(c, nowFav);
    updateFavCount();
    return nowFav;
}

// ==========================================================
// Overlay filtros (mobile)
// ==========================================================
function openFilters() {
    const html = document.documentElement;
    html.classList.remove("no-filters");
    html.classList.add("filters-open");

    if (btnFiltersToggle) btnFiltersToggle.style.display = "grid";
    sidebarEl?.classList.remove("filters-collapsed");
    btnFiltersToggle?.setAttribute("aria-expanded", "true");
    if (filtersChevron) filtersChevron.className = "bi bi-x-lg";

    setTimeout(() => qInput?.focus(), 60);
}

function closeFilters() {
    const html = document.documentElement;
    html.classList.add("no-filters");
    html.classList.remove("filters-open");

    sidebarEl?.classList.add("filters-collapsed");
    btnFiltersToggle?.setAttribute("aria-expanded", "false");

    if (btnFiltersToggle) btnFiltersToggle.style.display = "none";
    if (filtersChevron) filtersChevron.className = "bi bi-x-lg";
}

// ==========================================================
// Modo (catalog | favorites | top)
// ==========================================================
function setAZEnabled(enabled) {
    if (!azRail) return;
    azRail.classList.toggle("is-disabled", !enabled);
    if (!enabled) azRail.querySelectorAll("[data-letter]").forEach(b => b.classList.remove("active"));
}

function setAppbarActive(key) {
    document.querySelectorAll(".appbar .appbar__item").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".deskbar .deskbar__item").forEach(x => x.classList.remove("active"));

    if (key === "catalog") btnCatalog?.classList.add("active");
    if (key === "favorites") btnFavUser?.classList.add("active");
    if (key === "top") btnTopFav?.classList.add("active");

    if (key === "catalog") btnCatalogDesk?.classList.add("active");
    if (key === "favorites") btnFavUserDesk?.classList.add("active");
    if (key === "top") btnTopFavDesk?.classList.add("active");
}

function setMode(mode) {
    view = mode;

    const root = document.documentElement;
    root.classList.toggle("view-top", mode === "top");
    root.classList.toggle("view-favorites", mode === "favorites");
    root.classList.toggle("view-catalog", mode === "catalog");

    setAppbarActive(mode);

    const isCatalog = (mode === "catalog");
    if (qInput) {
        qInput.disabled = !isCatalog;
        if (!isCatalog) qInput.value = "";
    }
    if (btnSearch) btnSearch.disabled = !isCatalog;
    if (filterTipo) filterTipo.disabled = !isCatalog;
    if (filterPlano) filterPlano.disabled = !isCatalog;

    setAZEnabled(isCatalog);
    closeFilters();
}

// ==========================================================
// Render
// ==========================================================
function renderRows(items, opts = {}) {
    if (!resultsDiv) return;

    const showStar = (view !== "top");
    const incoming = items || [];
    const append = !!opts.append;
    const desktop = isDesktop();

    let html = "";

    for (const it of incoming) {
        const codeStr = formatCode(it.code);
        const favOn = isFav(it.code);

        const singer = (it.singer || "").trim();
        const title = (it.title || "").trim();
        const planText = normalizePlan(it.package || it.availability);
        const n = Number(it.total ?? 0);
        const letterKey = getLetterKey(singer);

        const rankHtml = (view === "top")
            ? `<div class="top-rank">
           <span class="pos">#${esc(it.rank ?? "")}</span>
           <span class="likes">❤️ ${esc(n)} </span>
         </div>`
            : "";

        if (desktop) {
            const actionsHtml = (view === "top")
                ? `<div class="fav-cell">${rankHtml}</div>`
                : (showStar
                    ? `<div class="fav-cell">
               <button class="fav-btn ${favOn ? "on" : ""}"
                       data-code="${esc(it.code)}"
                       type="button"
                       aria-label="Favoritar">
                 <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}"></i>
               </button>
             </div>`
                    : ``);

            html += `
        <div class="row ${view === "top" ? "row-top" : ""}"
             data-code="${esc(it.code)}"
             data-letter="${esc(letterKey)}">
          <div class="cell-code">${esc(codeStr)}</div>
          <div class="cell-title">${esc(title)}</div>
          <div class="cell-singer">${esc(singer)}</div>
          <div class="cell-pack">
            ${planText ? `<span class="plan-badge">${esc(planText)}</span>` : ``}
          </div>
          <div class="cell-actions">${actionsHtml}</div>
        </div>`;
        } else {
            html += `
        <div class="row ${view === "top" ? "row-top" : ""}"
             data-code="${esc(it.code)}"
             data-letter="${esc(letterKey)}">

          ${view === "top" ? `<div class="cell-rank-mobile">${rankHtml}</div>` : ``}

          <div class="cell-topline">
            <div class="code-pack">
              <span class="code">${esc(codeStr)}</span>
              ${planText ? `<span class="plan-mini">${esc(planText)}</span>` : ``}
            </div>

            ${showStar && view !== "top" ? `
              <div class="cell-actions">
                <button class="fav-btn ${favOn ? "on" : ""}"
                        data-code="${esc(it.code)}"
                        type="button"
                        aria-label="Favoritar">
                  <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}"></i>
                </button>
              </div>` : ``}
          </div>

          <div class="cell-title">
            <span class="lbl">Título:</span>
            <span class="val">${esc(title)}</span>
          </div>

          <div class="cell-singer">
            <span class="lbl">Cantor:</span>
            <span class="val">${esc(singer)}</span>
          </div>
        </div>`;
        }
    }

    if (!append) resultsDiv.innerHTML = html;
    else resultsDiv.insertAdjacentHTML("beforeend", html);
}

// ==========================================================
// Filtros selecionados
// ==========================================================
function getTipoSelecionado() {
    const t = (filterTipo?.value || "").trim();
    return t ? t : null;
}

function getPlanoSelecionado() {
    const p = (filterPlano?.value || "").trim().toLowerCase();
    if (!p) return null;
    if (p === "basico" || p === "básico") return "basico";
    if (p === "plus") return "plus"; // se seu backend aceitar
    return null;
}

// ==========================================================
// Modo AUTO ou MANUAL?
// ==========================================================
function isCatalogAutoMode() {
    const q = (qInput?.value || "").trim();
    return (view === "catalog" && !q && !!paging.letter && !forceLetterMode);
}

// total geral (para contador bonito)
async function ensureCatalogTotalAll() {
    if (catalogTotalAll !== null) return catalogTotalAll;
    if (catalogTotalBusy) return null;

    catalogTotalBusy = true;
    try {
        const tipo = getTipoSelecionado();
        const plano = getPlanoSelecionado();

        let url = `/api/search?q=&limit=1&offset=0`;
        // ⚠️ de propósito: SEM letter aqui (total geral)
        if (tipo) url += `&tipo=${encodeURIComponent(tipo)}`;
        if (plano) url += `&plano=${encodeURIComponent(plano)}`;

        const res = await fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"});
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const total = (typeof data.total === "number") ? data.total : null;
        catalogTotalAll = total;
        return total;
    } catch (e) {
        console.warn("Falha ao obter total geral do catálogo:", e);
        catalogTotalAll = null;
        return null;
    } finally {
        catalogTotalBusy = false;
    }
}

// ==========================================================
// Busca principal
// ==========================================================
async function doSearch(reset = true, opts = {}) {
    setMode("catalog");
    setStatus("", "");

    const allowAdvance = (opts.allowAdvance !== false);

    const q = (qInput?.value || "").trim();

    // Busca por texto DESLIGA letter e também sai do modo manual
    if (q) {
        forceLetterMode = false;
        paging.letter = null;
        setAZActive(null);
    }

    if (reset) {
        paging.offset = 0;
        paging.total = null;
        paging.done = false;

        if (resultsDiv) {
            resultsDiv.innerHTML = "";
            resultsDiv.scrollTop = 0;
        }

        // contador global (só no auto)
        if (isCatalogAutoMode()) {
            catalogShown = 0;
            catalogTotalAll = null;
            ensureCatalogTotalAll();
        }
    }

    const tipo = getTipoSelecionado();
    const plano = getPlanoSelecionado();

    let url = `/api/search?q=${encodeURIComponent(q)}&limit=${paging.limit}&offset=${paging.offset}`;
    if (paging.letter) url += `&letter=${encodeURIComponent(paging.letter)}`;
    if (tipo) url += `&tipo=${encodeURIComponent(tipo)}`;
    if (plano) url += `&plano=${encodeURIComponent(plano)}`;

    if (paging.loading || paging.done) return;
    paging.loading = true;

    try {
        const res = await fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"});
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const items = data.items || [];
        const total = typeof data.total === "number" ? data.total : null;

        renderRows(items, {append: !reset});

        paging.offset += items.length;
        paging.total = total;

        // contador
        if (isCatalogAutoMode()) {
            catalogShown += items.length;
            if (catalogTotalAll === null) await ensureCatalogTotalAll();
            if (catalogTotalAll !== null) setCount(catalogShown, catalogTotalAll);
            else setCount(catalogShown, null);
        } else {
            const shown = paging.offset;
            const t = total ?? shown;
            setCount(shown, t);
        }

        if (!items.length && reset) setStatus("info", "Nenhum resultado.");

        const endedThisChunk = (!items.length || (total !== null && paging.offset >= total));
        if (endedThisChunk) {
            paging.done = true;

            // AUTO: ao chegar no fim da letra atual, pode avançar pra próxima (apenas para frente)
            if (!reset && allowAdvance && isCatalogAutoMode()) {
                await advanceAndLoadNextLetter();
            }
        }
    } catch (e) {
        console.error(e);
        if (reset) {
            setCount(0, 0);
            renderRows([], {append: false});
        }
        setStatus("error", "Erro ao buscar.");
        paging.done = true;
    } finally {
        paging.loading = false;
    }
}

// ==========================================================
// Avança letra (AUTO)
// ==========================================================
async function advanceAndLoadNextLetter() {
    if (!isCatalogAutoMode()) return false;
    if (advancing) return false;

    advancing = true;
    try {
        let guard = 0;
        while (guard++ < 80) {
            const nxt = nextLetter(paging.letter);
            if (!nxt) return false;

            paging.letter = nxt;
            setAZActive(nxt);

            paging.offset = 0;
            paging.total = null;
            paging.done = false;

            // carrega a nova letra (append)
            const before = paging.offset;
            await doSearch(false, {allowAdvance: false});
            if (paging.offset > before) return true;
            // se veio vazio, tenta próxima letra
        }
        return false;
    } finally {
        advancing = false;
    }
}

// ==========================================================
// Favoritos
// ==========================================================
async function loadFavorites() {
    setMode("favorites");
    panelTitle && (panelTitle.textContent = "Meus Favoritos");
    setStatus("", "");

    const localCodes = getFavs();
    const localCodesNum = localCodes.map(c => Number(c)).filter(n => Number.isFinite(n) && n > 0);

    // Render local (se tiver)
    if (localCodesNum.length) {
        try {
            const resLocal = await fetch("/api/songs/by-codes", {
                method: "POST",
                headers: {"Content-Type": "application/json", "Accept": "application/json"},
                cache: "no-store",
                body: JSON.stringify({codes: localCodesNum}),
            });

            if (resLocal.ok) {
                const dataLocal = await resLocal.json();
                const itemsLocal = dataLocal.items || [];
                setCount(itemsLocal.length);
                renderRows(itemsLocal, {append: false});
            } else {
                setCount(localCodesNum.length);
                renderRows([], {append: false});
            }
        } catch (e) {
            console.warn("Falha ao carregar detalhes locais:", e);
            setCount(localCodesNum.length);
            renderRows([], {append: false});
        }
        updateFavCount();
    } else {
        setCount(0, 0);
        renderRows([], {append: false});
    }

    // Tenta servidor
    try {
        const res = await fetch(`/api/fav/user?user_id=${encodeURIComponent(USER_ID)}&limit=500`, {
            headers: {Accept: "application/json"},
            cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const serverItems = data.items || [];
        const serverCodes = serverItems.map(it => String(it.code)).filter(Boolean);

        if (serverCodes.length) {
            setFavs(serverCodes);
            updateFavCount();
            setCount(serverItems.length);
            renderRows(serverItems, {append: false});
            return;
        }

        if (localCodesNum.length) {
            try {
                await fetch("/api/fav/sync", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({user_id: USER_ID, codes: localCodesNum, mode: "merge"}),
                });
            } catch (e) {
                console.warn("Falha ao restaurar favoritos no servidor:", e);
            }
            setStatus("info", "Favoritos locais carregados (servidor sem dados no momento).");
        } else {
            setStatus("info", "Você ainda não favoritou nenhuma música.");
        }
    } catch (e) {
        console.warn("Servidor indisponível para favoritos:", e);
        if (localCodesNum.length) setStatus("info", "Favoritos locais carregados (sem conexão com o servidor).");
        else setStatus("error", "Erro ao carregar favoritos.");
    }
}

// ==========================================================
// Top Favoritos (Geral)
// ==========================================================
async function loadTopFavoritesGlobal() {
    setMode("top");
    panelTitle && (panelTitle.textContent = "Top Favoritos (Geral)");
    setStatus("", "");

    try {
        const res = await fetch(`/api/top-favoritos?limit=30`, {
            headers: {Accept: "application/json"},
            cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.items || []);

        const items = list.slice(0, 30).map((it, idx) => ({snippet: "", ...it, rank: idx + 1}));

        setCount(items.length, items.length);
        renderRows(items, {append: false});

        if (!items.length) setStatus("info", "Ainda não há dados de Top Favoritos.");
    } catch (e) {
        console.error(e);
        setCount(0, 0);
        renderRows([], {append: false});
        setStatus("error", "Erro ao carregar Top Favoritos.");
    }
}

// ==========================================================
// Eventos — Favoritar (lista)
// ==========================================================
resultsDiv?.addEventListener("click", async (e) => {
    const btn = e.target?.closest?.("button.fav-btn[data-code]");
    if (!btn) return;

    const code = btn.getAttribute("data-code");
    const nowFav = toggleFav(code);

    btn.classList.toggle("on", nowFav);
    const icon = btn.querySelector("i");
    if (icon) icon.className = nowFav ? "bi bi-star-fill" : "bi bi-star";

    if (view === "favorites" && !nowFav) {
        await loadFavorites();
    }
});

// ==========================================================
// Reset para AUTO previsível
// ==========================================================
function resetToAutoCatalogMode() {
    forceLetterMode = false;
    catalogTotalAll = null;
    paging.letter = "#";     // ✅ sempre volta pro começo real
    paging.offset = 0;
    paging.total = null;
    paging.done = false;
    setAZActive("#");
}

// ==========================================================
// Eventos — Busca / filtros
// ==========================================================
btnSearch?.addEventListener("click", () => {
    resetToAutoCatalogMode();
    doSearch(true);
});

qInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        resetToAutoCatalogMode();
        doSearch(true);
    }
});

filterTipo?.addEventListener("change", () => {
    if (view === "catalog") {
        resetToAutoCatalogMode();
        doSearch(true);
    }
});

filterPlano?.addEventListener("change", () => {
    if (view === "catalog") {
        resetToAutoCatalogMode();
        doSearch(true);
    }
});

// ==========================================================
// Eventos — Appbar / Deskbar
// ==========================================================
function goCatalogHome() {
    resetToAutoCatalogMode();
    setMode("catalog");
    if (qInput) qInput.value = "";
    if (resultsDiv) {
        resultsDiv.innerHTML = "";
        resultsDiv.scrollTop = 0;
    }
    catalogShown = 0;
    catalogTotalAll = null;
    ensureCatalogTotalAll();
    doSearch(true);
}

btnCatalog?.addEventListener("click", goCatalogHome);
btnCatalogDesk?.addEventListener("click", goCatalogHome);

btnFavUser?.addEventListener("click", loadFavorites);
btnFavUserDesk?.addEventListener("click", loadFavorites);
btnTopFav?.addEventListener("click", loadTopFavoritesGlobal);
btnTopFavDesk?.addEventListener("click", loadTopFavoritesGlobal);

// ==========================================================
// A–Z — clique (entra no modo MANUAL)
// ==========================================================
(function initAZClick() {
    if (!azRail) return;

    azRail.addEventListener("click", (e) => {
        if (view !== "catalog") return;

        const b = e.target?.closest?.("[data-letter]");
        if (!b) return;

        const letter = normLetter(b.dataset.letter);
        if (!letter) return;

        // ✅ modo manual: trava na letra escolhida
        forceLetterMode = true;

        paging.letter = letter;
        paging.offset = 0;
        paging.total = null;
        paging.done = false;

        if (qInput) qInput.value = ""; // sem busca
        setAZActive(letter);

        if (resultsDiv) {
            resultsDiv.innerHTML = "";
            resultsDiv.scrollTop = 0;
        }

        doSearch(true, {allowAdvance: false});
    });

    // se começar a digitar busca: sai do modo manual
    qInput?.addEventListener("input", () => {
        if (view !== "catalog") return;
        const q = (qInput.value || "").trim();
        if (q) {
            forceLetterMode = false;
            paging.letter = null;
            setAZActive(null);
        }
    });
})();

function getScrollContainer() {
    // No desktop quem rola é o wrap; no mobile quem rola é o #results
    return isDesktop() ? (resultsDiv?.closest(".results-wrap") || resultsDiv) : resultsDiv;
}


// ==========================================================
// A–Z — sincroniza letra ativa com scroll (só no AUTO)
// ==========================================================
(function initAZScrollSync() {
    const list = getScrollContainer();
    const rail = azRail;
    if (!list || !rail) return;

    let raf = null;

    list.addEventListener("scroll", () => {
        if (raf) return;
        raf = requestAnimationFrame(() => {
            raf = null;

            if (view !== "catalog") return;
            if (!paging.letter) return;

            // ✅ manual não mexe no highlight
            if (forceLetterMode) return;

            const listRect = list.getBoundingClientRect();
            const rows = list.querySelectorAll(".row[data-letter]");

            for (const r of rows) {
                const rect = r.getBoundingClientRect();
                const topInside = rect.top - listRect.top;
                if (topInside >= -8) {
                    const L = r.getAttribute("data-letter");
                    if (L) setAZActive(L);
                    break;
                }
            }
        });
    }, {passive: true});
})();

// ==========================================================
// Infinite scroll (catálogo)
// ==========================================================
(function initInfiniteScrollSafe() {
    if (!resultsDiv) return;

    const scroller = getScrollContainer();
    if (!scroller) return;

    scroller.addEventListener("scroll", () => {
        if (view !== "catalog") return;
        if (paging.loading) return;

        const nearEnd =
            scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 40;

        if (!nearEnd) return;

        // MANUAL: só carrega mais da MESMA letra
        if (forceLetterMode) {
            if (!paging.done) doSearch(false, {allowAdvance: false});
            return;
        }

        // AUTO: carrega mais; se acabou a letra, avança pra próxima
        if (paging.done && isCatalogAutoMode()) {
            advanceAndLoadNextLetter();
            return;
        }

        if (paging.done) return;
        doSearch(false);
    }, {passive: true});
})();


// ==========================================================
// Filtros — overlay (mobile)
// ==========================================================
(function initFiltersOverlay() {
    if (!sidebarEl || !btnFiltersToggle || !filtersChevron) return;

    btnFiltersToggle.style.display = "none";
    filtersChevron.className = "bi bi-x-lg";

    btnFiltersToggle.addEventListener("click", closeFilters);

    const btnTop = el("btnSearchIcon");
    btnTop?.addEventListener("click", () => {
        if (view !== "catalog") return;
        openFilters();
    });
})();

// ==========================================================
// Init
// ==========================================================
setCount(0, 0);
setStatus("", "");
renderRows([], {append: false});
updateFavCount();

// ✅ Inicial previsível: catálogo AUTO no "#"
setMode("catalog");
resetToAutoCatalogMode();
if (qInput) qInput.value = "";
ensureCatalogTotalAll();
doSearch(true);

// ==========================================================
// PWA Install (Android/Chrome)
// ==========================================================
let deferredInstallPrompt = null;

window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    if (btnInstall) btnInstall.hidden = false;
});

if (btnInstall) {
    btnInstall.addEventListener("click", async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        try {
            await deferredInstallPrompt.userChoice;
        } catch {
        }
        deferredInstallPrompt = null;
        btnInstall.hidden = true;
    });
}

// ==========================================================
// PDFs (Modal)
// ==========================================================
const PDFS = {
    basico: [
        {
            key: "internacional",
            label: "Internacional",
            id: "https://drive.google.com/file/d/10gcVKr_VykhHP1c-xRsuQtaWV3ZfYwfZ/view?usp=drive_link"
        },
        {
            key: "nacional",
            label: "Nacional",
            id: "https://drive.google.com/file/d/10gyQgbFt5mu7DtD7kcOdQa7LzoQZtJ-g/view?usp=drive_link"
        },
        {
            key: "gospel",
            label: "Gospel",
            id: "https://drive.google.com/file/d/18l_Jxbey33Njd86Wm5CBDzwynm1OPIoh/view?usp=drive_link"
        },
        {
            key: "completo",
            label: "Completo",
            id: "https://drive.google.com/file/d/1IxSyjx8E30MGaUbmdQ5V1fOm2ZaEaADR/view?usp=drive_link"
        },
    ],
    plus: [
        {
            key: "internacional",
            label: "Internacional",
            id: "https://drive.google.com/file/d/10ewWaoFJVg69hjGHhIf3K-sXdCJTmQcA/view?usp=drive_link"
        },
        {
            key: "nacional",
            label: "Nacional",
            id: "https://drive.google.com/file/d/10dYFGQ4xbI9b749SfhMJp9qLmFqGGYnv/view?usp=drive_link"
        },
        {
            key: "gospel",
            label: "Gospel",
            id: "https://drive.google.com/file/d/1Qa-uNnijPEsGYD2wCvUtZmSp6V7zSZdq/view?usp=drive_link"
        },
        {
            key: "completo",
            label: "Completo",
            id: "https://drive.google.com/file/d/1dzf3fD6GkC_XWP8LXkPMVvmySPWJZjM1/view?usp=drive_link"
        },
    ],
};

function driveViewUrl(url) {
    return url;
}

const pdfModal = el("pdfModal");
const pdfGrid = el("pdfGrid");
let pdfTab = "basico";

function renderPdfGrid() {
    if (!pdfGrid) return;
    const items = PDFS[pdfTab] || [];
    pdfGrid.innerHTML = items.map(it => `
    <div class="pdf-card">
      <div class="pdf-card__left">
        <div class="pdf-card__name">${esc(it.label)}</div>
        <div class="pdf-card__meta">${esc(pdfTab.toUpperCase())}</div>
      </div>
      <button class="pdf-card__btn" type="button" data-pdf-open="${esc(it.id)}">Abrir</button>
    </div>
  `).join("");
}

function openPdfModal() {
    if (!pdfModal) return;
    pdfModal.classList.add("is-open");
    pdfModal.setAttribute("aria-hidden", "false");
    renderPdfGrid();
}

function closePdfModal() {
    if (!pdfModal) return;
    pdfModal.classList.remove("is-open");
    pdfModal.setAttribute("aria-hidden", "true");
}

el("btnPdf")?.addEventListener("click", openPdfModal);
el("btnPdfDesk")?.addEventListener("click", openPdfModal);

pdfModal?.addEventListener("click", (e) => {
    const target = e.target;

    if (target?.closest?.("[data-pdf-close]")) {
        closePdfModal();
        return;
    }

    const btn = target?.closest?.("[data-pdf-open]");
    const url = btn?.dataset?.pdfOpen;
    if (url) window.open(driveViewUrl(url), "_blank", "noopener");
});

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pdfModal?.classList.contains("is-open")) closePdfModal();
});

document.querySelectorAll(".pdf-tab").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".pdf-tab").forEach(b => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        pdfTab = btn.dataset.pdfTab || "basico";
        renderPdfGrid();
    });
});

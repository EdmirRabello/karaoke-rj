/* catalog.js — Catálogo de Músicas (Karaokê RJ)
   ==========================================================
   - Busca: /api/search
   - Favoritos: localStorage + sync best-effort (/api/fav/register, /api/fav/remove)
   - Listagens:
     * Meus Favoritos: /api/fav/user?user_id=...&limit=...
     * Top Favoritos (Geral): /api/top-favoritos
*/

const el = (id) => document.getElementById(id);

const qInput = el("q");
const filterTipo = el("filterTipo");
const filterPlano = el("filterPlano");
const btnSearch = el("btnSearch");

const statusDiv = el("status");
const resultsDiv = el("results");
const panelTitle = el("panelTitle");
const countCard = el("countCard");

const btnFavUser = el("btnFavUser"); // topo: Meus Favoritos
const btnTopFav = el("btnTopFav");   // topo: Top Favoritos (Geral)

const btnFiltersToggle = el("btnFiltersToggle");
const filtersChevron = el("filtersChevron");
const sidebarEl = el("sidebar");

let view = "search";

// ✅ USER_ID único por dispositivo/navegador (resolve "favoritos iguais pra todo mundo")
function getUserId() {
  const KEY = "krj_user_id_v1";
  let id = localStorage.getItem(KEY);

  if (!id || !/^\d+$/.test(id)) {
    // número grande, simples, persistente
    id = String(Math.floor(Math.random() * 1_000_000_000));
    localStorage.setItem(KEY, id);
  }
  return Number(id);
}
const USER_ID = getUserId();

// ✅ chave dos favoritos separada por usuário (evita “misturar” no mesmo celular)
const FAV_KEY = `cantus_favs_codes_v1_u${USER_ID}`;

let lastItems = [];
let lastCount = 0;

const mqDesktop = window.matchMedia("(min-width: 981px)");
function isDesktop() {
  return mqDesktop.matches;
}

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

function setCount(n) {
  if (!countCard) return;
  const num = Number(n || 0);
  lastCount = num;
  countCard.innerHTML = `🎵 <b>${num}</b> músicas encontradas`;
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

// ===== NORMALIZAÇÃO DO PLANO (PLUS x BÁSICO) =====
function normalizePlan(value) {
  const v = String(value || "")
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  if (v.includes("PLUS")) return "PLUS";
  if (v.includes("BASICO")) return "BÁSICO";
  return "";
}

// ===== FAVORITOS (localStorage) =====
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
  const badge = document.querySelector(".fav-badge");
  if (!badge) return;

  const favs = getFavs();
  const count = favs.length;

  badge.textContent = count > 99 ? "99+" : String(count);
  badge.style.display = count ? "flex" : "none";
  badge.classList.toggle("is-big", count > 99);

  if (count) {
    badge.classList.remove("bump");
    void badge.offsetWidth;
    badge.classList.add("bump");
  }
}

// Migração: "krj_favs" -> novo FAV_KEY (apenas se existir e o atual estiver vazio)
(function migrateOldFavs() {
  try {
    const old = JSON.parse(localStorage.getItem("krj_favs") || "[]");
    const cur = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
    if (Array.isArray(old) && old.length && (!Array.isArray(cur) || !cur.length)) {
      localStorage.setItem(FAV_KEY, JSON.stringify(old.map(String)));
    }
    localStorage.removeItem("krj_favs");
  } catch {}
})();

// ===== Sync server (best-effort) =====
async function syncFavToServer(code, nowFav) {
  try {
    const url = nowFav ? "/api/fav/register" : "/api/fav/remove";
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, code: Number(code) }),
    });
  } catch (e) {
    console.warn("Falha ao sincronizar favorito", e);
  }
}

function toggleFav(code) {
  const c = String(code);
  let favs = getFavs();

  if (favs.includes(c)) favs = favs.filter((x) => x !== c);
  else favs.push(c);

  setFavs(favs);

  const nowFav = favs.includes(c);
  syncFavToServer(c, nowFav);

  updateFavCount();
  return nowFav;
}

// ===== Filtros =====
function getTipoSelecionado() {
  const t = (filterTipo?.value || "").trim();
  return t ? t : null;
}

function getPlanoSelecionado() {
  const p = (filterPlano?.value || "").trim().toLowerCase();
  if (!p) return null;
  if (p === "basico" || p === "básico") return "basico";
  return null;
}

// ===== Mobile: recolhe filtros =====
function collapseFiltersMobile() {
  const isMobile = window.matchMedia("(max-width: 980px)").matches;
  if (!isMobile || !sidebarEl) return;

  sidebarEl.classList.add("filters-collapsed");
  btnFiltersToggle?.setAttribute("aria-expanded", "false");

  if (filtersChevron) {
    filtersChevron.classList.remove("bi-chevron-up", "bi-chevron-down");
    filtersChevron.classList.add("bi-chevron-down");
  }
}

// ===== Render =====
function renderRows(items) {
  if (!resultsDiv) return;

  const list = items || [];
  lastItems = list;

  const desktop = isDesktop();
  let html = "";

  for (const it of list) {
    const codeStr = formatCode(it.code);
    const favOn = isFav(it.code);

    const singer = (it.singer || "").trim();
    const title = (it.title || "").trim();

    const planText = normalizePlan(it.package || it.availability);
    const planCls = planText ? "plan-badge" : "";

    const rankHtml =
      view === "top"
        ? `<div class="top-rank">
             <span class="pos">#${esc(it.rank ?? "")}</span>
             <span class="likes">❤️ ${esc(it.total ?? "")}</span>
           </div>`
        : "";

    if (desktop) {
      html += `
        <div class="row ${view === "top" ? "row-top" : ""}">
          ${view === "top" ? `<div class="cell-rank">${rankHtml}</div>` : ``}
          <div class="cell-code">${esc(codeStr)}</div>
          <div class="cell-title">${esc(title)}</div>
          <div class="cell-singer">${esc(singer)}</div>
          <div class="cell-pack">
            ${planText ? `<span class="${esc(planCls)}">${esc(planText)}</span>` : ``}
          </div>
          <div class="cell-actions">
            <button class="fav-btn ${favOn ? "on" : ""}" data-code="${esc(it.code)}" type="button" aria-label="Favoritar">
              <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}"></i>
            </button>
          </div>
        </div>
      `;
    } else {
      html += `
        <div class="row ${view === "top" ? "row-top" : ""}" data-code="${esc(it.code)}">
          ${view === "top" ? `<div class="cell-rank-mobile">${rankHtml}</div>` : ``}

          <div class="cell-topline">
            <div class="code-pack">
              <span class="code">${esc(codeStr)}</span>
              ${planText ? `<span class="plan-mini">${esc(planText)}</span>` : ``}
            </div>

            <div class="cell-actions">
              <button class="fav-btn ${favOn ? "on" : ""}" data-code="${esc(it.code)}" type="button" aria-label="Favoritar">
                <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}"></i>
              </button>
            </div>
          </div>

          <div class="cell-title">
            <span class="lbl">Título:</span>
            <span class="val">${esc(title)}</span>
          </div>

          <div class="cell-singer">
            <span class="lbl">Cantor:</span>
            <span class="val">${esc(singer)}</span>
          </div>
        </div>
      `;
    }
  }

  resultsDiv.innerHTML = html;
}

// ===== API =====
async function doSearch() {
  collapseFiltersMobile();

  view = "search";
  panelTitle && (panelTitle.textContent = "Resultados");
  setStatus("", "");

  const q = (qInput?.value || "").trim();
  const tipo = getTipoSelecionado();
  const plano = getPlanoSelecionado();

  let url = `/api/search?q=${encodeURIComponent(q)}&limit=200`;
  if (tipo) url += `&tipo=${encodeURIComponent(tipo)}`;
  if (plano) url += `&plano=${encodeURIComponent(plano)}`;

  try {
    const res = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = data.items || [];
    setCount(items.length);
    renderRows(items);

    if (!items.length) setStatus("info", "Nenhum resultado.");
  } catch (e) {
    console.error(e);
    setCount(0);
    renderRows([]);
    setStatus("error", "Erro ao buscar.");
  }
}

async function loadFavorites() {
  collapseFiltersMobile();

  view = "favorites";
  panelTitle && (panelTitle.textContent = "Meus Favoritos");
  setStatus("", "");

  try {
    const res = await fetch(
      `/api/fav/user?user_id=${encodeURIComponent(USER_ID)}&limit=500`,
      { headers: { Accept: "application/json" }, cache: "no-store" }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = data.items || [];

    // sincroniza localStorage com o servidor desse usuário
    try {
      const serverCodes = items.map((it) => String(it.code)).filter(Boolean);
      setFavs(serverCodes);
    } catch {}
    updateFavCount();

    setCount(items.length);
    renderRows(items);

    if (!items.length) setStatus("info", "Você ainda não favoritou nenhuma música.");
  } catch (e) {
    console.error(e);
    setCount(0);
    renderRows([]);
    setStatus("error", "Erro ao carregar favoritos.");
  }
}

// ✅ TOP 30 FAVORITOS GERAL (todos os usuários) — usa /api/top-favoritos
async function loadTopFavoritesGlobal() {
  collapseFiltersMobile();

  view = "top";
  panelTitle && (panelTitle.textContent = "Top Favoritos (Geral)");
  setStatus("", "");

  try {
    const res = await fetch(`/api/top-favoritos`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    // backend pode retornar array direto OU {items:[...]}
    const list = Array.isArray(data) ? data : (data.items || []);

    const items = list.slice(0, 30).map((it, idx) => ({
      ...it,
      rank: idx + 1,
    }));

    setCount(items.length);
    renderRows(items);

    if (!items.length) setStatus("info", "Ainda não há dados de Top Favoritos.");
  } catch (e) {
    console.error(e);
    setCount(0);
    renderRows([]);
    setStatus("error", "Erro ao carregar Top Favoritos.");
  }
}

// ===== Eventos =====
resultsDiv?.addEventListener("click", async (e) => {
  const btn = e.target?.closest?.("button[data-code]");
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

btnSearch?.addEventListener("click", doSearch);
qInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});

btnFavUser?.addEventListener("click", loadFavorites);
btnTopFav?.addEventListener("click", loadTopFavoritesGlobal);

filterTipo?.addEventListener("change", () => {
  if (view === "favorites") loadFavorites();
  else if (view === "top") loadTopFavoritesGlobal();
  else doSearch();
});

filterPlano?.addEventListener("change", () => {
  if (view === "favorites") loadFavorites();
  else if (view === "top") loadTopFavoritesGlobal();
  else doSearch();
});

// ===== Toggle filtros (mobile) =====
(function () {
  if (!btnFiltersToggle || !sidebarEl) return;

  function apply(collapsed) {
    sidebarEl.classList.toggle("filters-collapsed", collapsed);
    btnFiltersToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");

    if (filtersChevron) {
      filtersChevron.classList.remove("bi-chevron-up", "bi-chevron-down");
      filtersChevron.classList.add(collapsed ? "bi-chevron-down" : "bi-chevron-up");
    }
  }

  btnFiltersToggle.addEventListener("click", () => {
    const collapsed = sidebarEl.classList.contains("filters-collapsed");
    apply(!collapsed);
  });

  apply(false);
})();

// ===== Init =====
setCount(0);
setStatus("", "");
renderRows([]);
updateFavCount();

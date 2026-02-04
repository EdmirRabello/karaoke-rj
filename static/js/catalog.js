// Tema agora é global (static/js/theme.js) e funciona em todas as páginas.

const el = (id) => document.getElementById(id);

const qInput = el("q");
const filterTipo = el("filterTipo");
const filterPlano = el("filterPlano");
const btnSearch = el("btnSearch");
const btnVoice = el("btnVoice");
const statusDiv = el("status");
const resultsDiv = el("results");
const panelTitle = el("panelTitle");
const countCard = el("countCard");
const btnFavTop = el("btnFavTop");
// Contador de favoritos aparece em mais de um lugar (header e sidebar)
const favCountEls = Array.from(document.querySelectorAll(".favCount"));

// Alguns layouts não têm botão dedicado "navSearch" (usam o btnSearch)
const navSearch = el("navSearch") || btnSearch;
const navFav = el("navFav");

const sidebar = el("sidebar");
const overlay = el("overlay");
const btnHamburger = el("btnHamburger");
const btnCollapse = el("btnCollapse");

let view = "search";
const FAV_KEY = "cantus_favs_codes_v1";

// ✅ guarda último resultado para re-render ao trocar breakpoint
let lastItems = [];
let lastCount = 0;

// breakpoints
const mqDesktop = window.matchMedia("(min-width: 981px)");

function isDesktop(){
  return mqDesktop.matches;
}

function esc(s){
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function formatCode(code){
  const s = String(code ?? "");
  if (!/^\d+$/.test(s)) return s;
  return s.length >= 5 ? s : s.padStart(5, "0");
}

function setCount(n){
  if (!countCard) return;
  const num = Number(n || 0);
  lastCount = num;
  countCard.innerHTML = `🎵 <b>${num}</b> músicas encontradas`;
  countCard.classList.add("bump");
  setTimeout(()=>countCard.classList.remove("bump"), 180);
}

function setStatus(kind, message, opts){
  if (!statusDiv) return;
  const msg = String(message || "");
  const k = String(kind || "info");
  const action = opts && opts.action ? opts.action : null;
  const actionLabel = opts && opts.actionLabel ? String(opts.actionLabel) : "Tentar novamente";

  statusDiv.className = "status " + (k ? ("status-" + k) : "");
  statusDiv.setAttribute("role", k === "error" ? "alert" : "status");
  statusDiv.innerHTML = `
    <div class="status-inner">
      <span class="status-text">${esc(msg)}</span>
      ${action ? `<button type="button" class="k-btn k-btn-ghost k-btn--compact status-action" data-status-action="1">${esc(actionLabel)}</button>` : ``}
    </div>
  `;

  if (action){
    const btn = statusDiv.querySelector('[data-status-action="1"]');
    if (btn) btn.onclick = action;
  }
}

function getFavs(){
  try { return JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); }
  catch { return []; }
}

function setFavs(arr){
  localStorage.setItem(FAV_KEY, JSON.stringify(arr));
}

function updateFavCount(){
  const n = getFavs().length;
  const text = n > 99 ? "99+" : String(n);

  // Atualiza todos os contadores existentes na página
  if (!favCountEls.length) return;

  for (const elx of favCountEls){
    if (!elx) continue;
    if (n > 0){
      elx.textContent = text;
      elx.style.display = "inline-flex";
      elx.classList.toggle("is-max", n > 99);
    } else {
      elx.textContent = "";
      elx.style.display = "none";
      elx.classList.remove("is-max");
    }
  }
}



function isFav(code){
  return getFavs().includes(String(code));
}

function toggleFav(code){
  const c = String(code);
  let favs = getFavs();
  if (favs.includes(c)) favs = favs.filter(x => x !== c);
  else favs.push(c);
  setFavs(favs);
  return favs.includes(c);
}

function getTipoSelecionado(){
  const t = (filterTipo?.value || "").trim();
  return t ? t : null;
}

function getPlanoSelecionado(){
  const p = (filterPlano?.value || "").trim();
  return p ? p : null;
}

function setNavActive(activeBtn){
  [navSearch, navFav].forEach(b => b?.classList.remove("active"));
  activeBtn?.classList.add("active");
}

function openSidebar(){
  if (!sidebar || !overlay) return;
  sidebar.classList.add("open");
  overlay.hidden = false;
  overlay.classList.add("show");
}

function closeSidebar(){
  if (!sidebar || !overlay) return;
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
  setTimeout(()=>{ overlay.hidden = true; }, 160);
}

function toggleCollapse(){
  // No desktop: recolhe sidebar
  // No mobile: fecha drawer
  if (!sidebar || !btnCollapse) return;

  const mobile = window.matchMedia("(max-width: 980px)").matches;
  if (mobile) { closeSidebar(); return; }

  const collapsed = sidebar.classList.toggle("collapsed");
  btnCollapse.innerHTML = collapsed ? '<i class="bi bi-chevron-double-right"></i>' : '<i class="bi bi-chevron-double-left"></i>';
  btnCollapse.title = collapsed ? "Expandir filtros" : "Recolher filtros";
}

overlay?.addEventListener("click", closeSidebar);
btnHamburger?.addEventListener("click", () => {
  // ✅ evita erro no desktop: sidebar já está fixa
  if (isDesktop()) return;
  openSidebar();
});
btnCollapse?.addEventListener("click", toggleCollapse);

function closeSidebarIfMobile(){
  if (window.matchMedia("(max-width: 900px)").matches) closeSidebar();
}

function clearRows(){
  if (!resultsDiv) return;
  resultsDiv.innerHTML = "";
}

function normalizePlan(v){
  const s = String(v ?? "").trim();
  if (!s) return "";
  const up = s.toUpperCase();

  const hasPlus = up.includes("PLUS");
  const hasBasic = up.includes("BASICO") || up.includes("BÁSICO") || up.includes("BASIC");

  if (hasPlus && hasBasic) return "PLUS + BÁSICO";
  if (hasPlus && !hasBasic) return "SÓ PLUS";
  if (!hasPlus && hasBasic) return "SÓ BÁSICO";
  return s;
}

function planBadgeClass(planText){
  const up = String(planText).toUpperCase();
  if (up.includes("SÓ PLUS") || up.includes("SO PLUS")) return "plan-plus-only";
  if (up.includes("PLUS") && (up.includes("BÁSICO") || up.includes("BASICO"))) return "plan-mixed";
  if (up.includes("PLUS")) return "plan-plus";
  if (up.includes("BÁSICO") || up.includes("BASICO")) return "plan-basic";
  return "plan-default";
}

/* ============================
   RENDER: 2 layouts
   - Desktop: tabela horizontal (sem labels)
   - Mobile: cards (com labels)
============================ */
function renderRows(items){
  if (!resultsDiv) return;
  const list = items || [];
  lastItems = list;

  const desktop = isDesktop();
  let html = "";

  for (const it of list){
    const codeStr = formatCode(it.code);
    const favOn = isFav(it.code);

    const singer = (it.singer || "").trim();
    const title  = (it.title || "").trim();

    const planText = normalizePlan(it.availability || "");
    const planCls  = planBadgeClass(planText);

    if (desktop){
      // ✅ DESKTOP: sem "Código:", "Cantor:", etc (o cabeçalho já mostra)
      html += `
        <div class="row">
          <div class="cell-code">${esc(codeStr)}</div>
          <div class="cell-title">${esc(title)}</div>
          <div class="cell-singer">${esc(singer)}</div>
          <div class="cell-pack">${planText ? `<span class="plan-badge ${esc(planCls)}">${esc(planText)}</span>` : ``}</div>
          <div class="cell-actions">
            <button class="fav-btn ${favOn ? "on" : ""}" data-code="${esc(it.code)}"
                    type="button"
                    aria-label="${favOn ? "Remover dos favoritos" : "Adicionar aos favoritos"}"
                    title="${favOn ? "Favorito" : "Favoritar"}">
              <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}" aria-hidden="true"></i>
            </button>
          </div>
        </div>
      `;
    } else {
      // ✅ MOBILE: cards com labels + plano em linha própria (badge)
      html += `
        <div class="row" data-code="${esc(it.code)}">

          <div class="cell-top">
            <div class="cell-code">
              <span class="lbl">Código:</span>
              <span class="val">${esc(codeStr)}</span>
            </div>
          </div>

          <div class="cell-singer">
            <span class="lbl">Cantor:</span>
            <span class="val">${esc(singer)}</span>
          </div>

          <div class="cell-title">
            <span class="lbl">Título:</span>
            <span class="val">${esc(title)}</span>
          </div>

          ${planText ? `
            <div class="cell-pack">
              <span class="plan-badge ${esc(planCls)}">${esc(planText)}</span>
            </div>
          ` : ``}

          <div class="cell-actions">
            <button class="fav-btn ${favOn ? "on" : ""}" data-code="${esc(it.code)}"
                    type="button"
                    aria-label="${favOn ? "Remover dos favoritos" : "Adicionar aos favoritos"}"
                    title="${favOn ? "Favorito" : "Favoritar"}">
              <i class="bi ${favOn ? "bi-star-fill" : "bi-star"}" aria-hidden="true"></i>
            </button>
          </div>

        </div>
      `;
    }
  }

  resultsDiv.innerHTML = html;
}

// ✅ re-render quando trocar breakpoint desktop/mobile
let lastDesktopState = isDesktop();
mqDesktop.addEventListener?.("change", () => {
  const nowDesktop = isDesktop();
  if (nowDesktop === lastDesktopState) return;
  lastDesktopState = nowDesktop;

  // mantém status/contagem e só muda o layout
  setCount(lastCount);
  renderRows(lastItems);

  // fecha sidebar se entrou em desktop
  if (nowDesktop) closeSidebar();
});

async function doSearch(){
  view = "search";
  setNavActive(navSearch);
  closeSidebarIfMobile();

  panelTitle && (panelTitle.textContent = "Resultados");
  setStatus("loading", "Buscando...");

  const q = (qInput.value || "").trim();
  const tipo = getTipoSelecionado();
  const plano = getPlanoSelecionado();

  let url = `/api/search?q=${encodeURIComponent(q)}&limit=200`;
  if (tipo) url += `&tipo=${encodeURIComponent(tipo)}`;
  if (plano) url += `&plano=${encodeURIComponent(plano)}`;

  try{
    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = data.items || [];
    setCount(items.length);
    setStatus("success", items.length ? "Resultados carregados." : "Nenhum resultado.");
    renderRows(items);
  }catch(e){
    console.error(e);
    setCount(0);
    setStatus("error", "Não consegui buscar agora. Verifique sua internet e tente novamente.", { action: doSearch, actionLabel: "Recarregar" });
    lastItems = [];
    clearRows();
  }
}

async function loadFavorites(){
  view = "favorites";
  setNavActive(navFav);
  closeSidebarIfMobile();

  panelTitle && (panelTitle.textContent = "Meus Favoritos");

  const favs = getFavs();
  const tipo = getTipoSelecionado();
  const plano = getPlanoSelecionado();

  if (!favs.length){
    setCount(0);
    setStatus("info", "0 favorito(s)");
    lastItems = [];
    clearRows();
    return;
  }

  setStatus("loading", "Carregando favoritos...");

  try{
    let url = `/api/favorites?codes=${encodeURIComponent(favs.join(","))}&limit=500`;
    if (tipo) url += `&tipo=${encodeURIComponent(tipo)}`;
    if (plano) url += `&plano=${encodeURIComponent(plano)}`;

    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = data.items || [];
    setCount(items.length);
    setStatus("success", items.length ? "Favoritos carregados." : "Nenhum favorito nesse filtro.");
    renderRows(items);
  }catch(e){
    console.error(e);
    setCount(0);
    setStatus("error", "Não consegui carregar seus favoritos agora. Tente novamente.", { action: loadFavorites, actionLabel: "Recarregar" });
    lastItems = [];
    clearRows();
  }
}

function startVoice(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){
    alert("Busca por voz não suportada neste navegador. Use Chrome.");
    return;
  }
  const r = new SR();
  r.lang = "pt-BR";
  r.onresult = (e) => {
    qInput.value = e.results[0][0].transcript;
    doSearch();
  };
  r.start();
}

resultsDiv?.addEventListener("click", async (e) => {
  const btn = e.target?.closest?.("button[data-code]");
  if (!btn) return;

  const code = btn.getAttribute("data-code");
  const nowFav = toggleFav(code);
  updateFavCount();

  btn.classList.toggle("on", nowFav);

  btn.title = nowFav ? "Favorito" : "Favoritar";
  btn.setAttribute("aria-label", nowFav ? "Remover dos favoritos" : "Adicionar aos favoritos");

  const icon = btn.querySelector("i");
  if (icon){
    icon.classList.toggle("bi-star-fill", nowFav);
    icon.classList.toggle("bi-star", !nowFav);
  }

  if (view === "favorites" && !nowFav){
    await loadFavorites();
  }
});

btnSearch?.addEventListener("click", doSearch);
qInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});

navSearch?.addEventListener("click", doSearch);
navFav?.addEventListener("click", loadFavorites);

btnFavTop?.addEventListener("click", () => {
  loadFavorites();
  closeSidebar(); // se o drawer estiver aberto
});


btnVoice?.addEventListener("click", startVoice);

filterTipo?.addEventListener("change", () => view === "favorites" ? loadFavorites() : doSearch());
filterPlano?.addEventListener("change", () => view === "favorites" ? loadFavorites() : doSearch());

// estado inicial
setCount(0);
setStatus("info", "Digite para buscar músicas");
clearRows();
updateFavCount();

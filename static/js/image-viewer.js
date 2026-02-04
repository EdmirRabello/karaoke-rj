/* image-viewer.js
   Abre imagens em tamanho grande ao clicar (PC e mobile).
   - Clique em qualquer coisa dentro de .aluguel-media (imagem + overlay)
   - Usa data-full se existir; senão usa src
*/
(function(){
  const viewer = document.getElementById("imgViewer");
  const imgEl = document.getElementById("imgViewerImg");
  const closeBtn = document.getElementById("imgViewerClose");

  if (!viewer || !imgEl || !closeBtn) return;

  let lastFocus = null;

  function openViewer(src, alt){
    lastFocus = document.activeElement;
    imgEl.src = src;
    imgEl.alt = alt || "Imagem ampliada";
    viewer.classList.add("is-open");
    viewer.setAttribute("aria-hidden","false");
    document.documentElement.classList.add("no-scroll");
    document.body.classList.add("no-scroll");
    closeBtn.focus({ preventScroll: true });
  }

  function closeViewer(){
    viewer.classList.remove("is-open");
    viewer.setAttribute("aria-hidden","true");
    document.documentElement.classList.remove("no-scroll");
    document.body.classList.remove("no-scroll");
    imgEl.removeAttribute("src");
    imgEl.removeAttribute("alt");
    if (lastFocus && typeof lastFocus.focus === "function"){
      try{ lastFocus.focus({ preventScroll: true }); }catch(e){ lastFocus.focus(); }
    }
  }

  function getFullSrc(img){
    if (!img) return null;
    return img.getAttribute("data-full") || img.currentSrc || img.src;
  }

  // Delegação: pega clique em qualquer .aluguel-media (serve para aluguel e vendas)
  document.addEventListener("click", (ev) => {
    const media = ev.target.closest?.(".aluguel-media");
    if (!media || !media.querySelector) return;

    const img = media.querySelector("img");
    if (!img) return;

    const src = getFullSrc(img);
    if (!src) return;

    ev.preventDefault();
    openViewer(src, img.alt || "Imagem");
  }, { passive: false });

  // Fechar: botão, clique no fundo, ESC
  closeBtn.addEventListener("click", (e) => { e.preventDefault(); closeViewer(); });

  viewer.addEventListener("click", (e) => {
    if (e.target === viewer) closeViewer();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && viewer.classList.contains("is-open")) closeViewer();
  });

  // Prevenir arrastar imagem no desktop (melhora UX)
  imgEl.addEventListener("dragstart", (e) => e.preventDefault());
})();

// theme.js — tema único (preto). Mantido apenas por compatibilidade.
(() => {
  document.documentElement.setAttribute("data-theme", "dark");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", "#05060a");
})();

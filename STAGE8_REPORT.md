# Stage 8 — Ultra polish (final)

## Mudanças aplicadas
- **Performance (LCP/Render):**
  - `preconnect` + `dns-prefetch` para `cdn.jsdelivr.net` (Bootstrap/Icons) em **home** e **catálogo**.
  - `preload` de **base.css** e do CSS da página (home/catalog).
  - `fetchpriority="high"` no preload do poster do hero (home).
  - `catalog.js` com **defer** (não bloqueia o HTML).

- **Design System aplicado 100% no catálogo:**
  - Input de busca: `class="k-input"`
  - Selects: `class="k-input k-input--compact"`

- **Limpeza conservadora (sem risco):**
  - Removidas regras `nav-cta` do `home.css` (não existiam no HTML).
  - Removidos resquícios `.chip` do `catalog.css` (não existiam no HTML).

## Varredura conservadora de CSS (sem remoção agressiva)
Mantive classes do Design System que não estão em uso direto, pois são “peças” prontas para futuras seções.

### base.css (ainda disponíveis para uso futuro)
- `k-btn--compact`, `k-btn-danger`, `k-card`, `k-chip`, `k-ellipsis`, `k-muted`, `k-nowrap`, `k-pill`

### Classes dinâmicas (JS injeta)
- `status-success`, `status-error`, `status-loading`, `status-inner`, `status-text`

> Observação: remoção agressiva de seletores só é segura com auditoria runtime (Bootstrap + classes aplicadas por JS).

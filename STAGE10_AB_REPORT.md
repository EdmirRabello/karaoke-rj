# STAGE 10 — A/B Automático (Hero + WhatsApp)

## O que foi implementado
- Teste A/B automático **50/50** na Home.
- Persistência por visitante via `localStorage` (`ab_variant`), evitando alternância a cada refresh.
- Permite forçar versão por URL:
  - `/?ab=A`
  - `/?ab=B`

## Elementos afetados
- Hero: título, subtítulo e kicker.
- Links do WhatsApp:
  - Botão do Hero
  - Barra fixa no mobile
  - Botão flutuante

## Mensagens do WhatsApp
- **A (comercial):** orçamento direto
- **B (experiência):** foco em experiência

## Arquivo alterado
- `templates/home.html` (adição de `data-*` e script A/B)

> Observação: o número de WhatsApp utilizado foi o já existente no projeto: `5521996504516`.

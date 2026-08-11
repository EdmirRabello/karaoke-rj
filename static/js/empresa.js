// ======================================================
// KRJ Empresa
// White Label
// ======================================================

(function () {

    const empresa = window.KRJ_EMPRESA;

    if (!empresa) {
        console.warn("Empresa não encontrada.");
        return;
    }

    console.log("Empresa carregada:", empresa);

    document.title = (empresa.nome || "Catálogo") + " - Catálogo";

    const logoEmpresa = empresa.logo || "/static/img/logo.png";
    const faviconEmpresa = empresa.favicon || logoEmpresa;

    let icon = document.querySelector("link[rel='icon']");
    if (!icon) {
        icon = document.createElement("link");
        icon.rel = "icon";
        document.head.appendChild(icon);
    }
    icon.href = faviconEmpresa;

    const logo = document.querySelector(".k-brand img");
    if (logo && logoEmpresa) {
        logo.src = logoEmpresa;
        logo.alt = empresa.nome || "Catálogo";
    }

    const titulo = document.querySelector(".k-brand__name b");
    if (titulo) {
        titulo.textContent = empresa.nome || "Catálogo";
    }

    function criarLinkWhatsApp(numero, texto) {
        const n = String(numero || "").replace(/\D/g, "");
        if (!n) return "";

        let url = "https://wa.me/" + n;

        if (texto) {
            url += "?text=" + encodeURIComponent(texto);
        }

        return url;
    }

    function criarBotaoRede(nome, link) {
        if (!link) return "";

        let url = link;

        if (nome === "whatsapp") {
            url = criarLinkWhatsApp(
                link,
                "Olá! Vim pelo catálogo online."
            );
        }

        if (!url) return "";

        const icones = {
            instagram: "bi-instagram",
            facebook: "bi-facebook",
            youtube: "bi-youtube",
            site: "bi-globe2",
            whatsapp: "bi-whatsapp",
            tiktok: "bi-tiktok"
        };

        const labels = {
            instagram: "Instagram",
            facebook: "Facebook",
            youtube: "YouTube",
            site: "Site",
            whatsapp: "WhatsApp",
            tiktok: "TikTok"
        };

        return `
            <a class="empresa-social empresa-social--${nome}"
               href="${url}"
               target="_blank"
               rel="noopener noreferrer"
               aria-label="${labels[nome] || nome}">
                <i class="bi ${icones[nome] || "bi-link-45deg"}"></i>
            </a>
        `;
    }

    function montarBotoesRedes(redes) {
        const ordem = [
            "instagram",
            "facebook",
            "youtube",
            "whatsapp",
            "site",

        ];

        let html = "";

        ordem.forEach(nome => {
            if (redes && redes[nome]) {
                html += criarBotaoRede(nome, redes[nome]);
            }
        });

        return html;
    }

    function abrirLandingEmpresa() {

        if (!empresa.landing) {
            alert("Landing da empresa ainda não cadastrada.");
            return;
        }

        let old = document.getElementById("krjConnectModal");
        if (old) old.remove();

        const modal = document.createElement("div");
        modal.id = "krjConnectModal";
        modal.className = "krj-connect-modal";

        const whatsapp = empresa.redes && empresa.redes.whatsapp
            ? empresa.redes.whatsapp
            : "5521996504516";

        const linkWhatsApp = criarLinkWhatsApp(
            whatsapp,
            "Olá! Tenho interesse em conhecer o catálogo exclusivo para minha empresa."
        );

        modal.innerHTML = `
            <div class="krj-connect-modal__overlay" data-krj-connect-close></div>

            <div class="krj-connect-modal__card" role="dialog" aria-modal="true">

                <button class="krj-connect-modal__close"
                        type="button"
                        data-krj-connect-close>
                    ✕
                </button>

                <div class="krj-connect-modal__body">
                    <img class="krj-connect-modal__banner"
                         src="${empresa.landing}"
                         alt="${empresa.nome || "Empresa"}">
                </div>

                <div class="krj-connect-modal__footer">
                    <a class="krj-connect-modal__cta"
                       href="${linkWhatsApp}"
                       target="_blank"
                       rel="noopener noreferrer">
                        💬 Quero conhecer
                    </a>
                </div>

            </div>
        `;

        document.body.appendChild(modal);

        setTimeout(() => modal.classList.add("is-open"), 30);

        modal.querySelectorAll("[data-krj-connect-close]").forEach(btn => {
            btn.addEventListener("click", () => {
                modal.classList.remove("is-open");
                setTimeout(() => modal.remove(), 250);
            });
        });
    }

    function fecharPopup(box) {
        sessionStorage.setItem("krj_empresa_popup_visto", empresa.slug || "empresa");
        box.classList.remove("is-open");
        setTimeout(() => box.remove(), 250);
    }

    function abrirPopupEmpresa() {

        if (!empresa.config || empresa.config.popup === false) return;

        if (sessionStorage.getItem("krj_empresa_popup_visto") === empresa.slug) {
            return;
        }

        const redes = empresa.redes || {};
        const botoes = montarBotoesRedes(redes);

        if (!botoes && !empresa.mensagem_popup) return;

        const textoBotao = empresa.dominio_oficial
            ? "Quer um catálogo exclusivo para sua empresa?"
            : "Conheça nossa empresa";

        const recursosHtml = empresa.dominio_oficial
            ? `
                <div class="empresa-popup__features">
                    Catálogo • QR Code • Compartilhamento • Vídeos • Redes Sociais • Muito mais...
                </div>
            `
            : "";

        const box = document.createElement("div");
        box.id = "empresaPopup";
        box.className = "empresa-popup";

box.innerHTML = `
    <div class="empresa-popup__overlay" data-empresa-fechar></div>

    <div class="empresa-popup__card" role="dialog" aria-modal="true">

        <button class="empresa-popup__close" type="button" data-empresa-fechar>✕</button>

        <div class="empresa-popup__decor decor-1">♪</div>
        <div class="empresa-popup__decor decor-2">♫</div>
        <div class="empresa-popup__decor decor-3">♬</div>

        <div class="empresa-popup__microfone">
            <i class="bi bi-mic-fill"></i>
        </div>

        <h2 class="empresa-popup__title">${empresa.titulo_popup || empresa.nome || "Catálogo"}</h2>

        <div class="empresa-popup__subtitle">
            ⭐ O <strong>maior catálogo</strong> de karaokê do Brasil ⭐
        </div>

        ${
            logoEmpresa
            ? `
                <div class="empresa-popup__logo-wrap">
                    <img class="empresa-popup__logo" src="${logoEmpresa}" alt="${empresa.nome || "Empresa"}">
                </div>
            `
            : ""
        }

        <div class="empresa-popup__social-title">
            <span></span>
            <b><i class="bi bi-people-fill"></i> Siga-nos e conecte-se</b>
            <span></span>
        </div>

        <div class="empresa-popup__social-box">
            <div class="empresa-popup__socials">
                ${botoes}
            </div>
        </div>

        <div class="empresa-popup__acoes">

            <button class="empresa-popup__about" type="button">
                <span class="empresa-popup__about-icon">⭐</span>
                <span>${textoBotao}</span>
            </button>

            ${recursosHtml}

            <button class="empresa-popup__continue" type="button" data-empresa-fechar>
                🎤 Entrar no catálogo
            </button>

        </div>
    </div>
`;

        document.body.appendChild(box);

        setTimeout(() => box.classList.add("is-open"), 50);

        box.querySelectorAll("[data-empresa-fechar]").forEach(btn => {
            btn.addEventListener("click", () => fecharPopup(box));
        });

        const btnSobre = box.querySelector(".empresa-popup__about");

        if (btnSobre) {
            btnSobre.addEventListener("click", abrirLandingEmpresa);
        }

     }

    setTimeout(abrirPopupEmpresa, 600);

})();
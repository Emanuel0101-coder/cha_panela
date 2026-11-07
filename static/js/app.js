
const API = "/api";
const TOKEN_KEY = "cha_panela_token";

// ELEMENTOS
const telaConfirmacao = document.getElementById("tela-confirmacao");
const telaSucesso = document.getElementById("tela-sucesso");
const telaPresentes = document.getElementById("tela-presentes");

const formConfirmacao = document.getElementById("form-confirmacao");
const inputNome = document.getElementById("nome");
const btnConfirmar = document.getElementById("btn-confirmar");
const btnLista = document.getElementById("btn-lista");
const btnNovoConvidado = document.getElementById("btn-novo-convidado");

const listaPresentes = document.getElementById("lista-presentes");
const contadorEscolhas = document.getElementById("contador-escolhas");
const btnConfirmarEscolhas = document.getElementById("btn-confirmar-escolhas");
const mensagemFeedback = document.getElementById("mensagem-feedback");

const modal = document.getElementById("modal-confirmacao");
const nomePresente = document.getElementById("nome-presente");
const btnCancelar = document.getElementById("btn-cancelar");
const btnReservar = document.getElementById("btn-reservar");

let presentesDisponiveis = [];
let presentesSelecionados = [];
let reservasExistentes = 0;
let presenteEmEscolha = null;


// ==========================================
// MODAL DE QUANTIDADE
// ==========================================

function criarModalQuantidade() {
    if (document.getElementById("modal-quantidade")) return;

    const estilos = document.createElement("style");

    estilos.textContent = `
        .quantidade-overlay {
            position: fixed;
            inset: 0;
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: rgba(10, 25, 48, 0.65);
            backdrop-filter: blur(4px);
        }

        .quantidade-overlay.hidden {
            display: none;
        }

        .quantidade-card {
            width: 100%;
            max-width: 390px;
            padding: 30px 24px;
            border-radius: 20px;
            background: #fff;
            text-align: center;
            box-shadow: 0 15px 50px rgba(0,0,0,0.2);
            animation: aparecerQuantidade 0.2s ease;
        }

        @keyframes aparecerQuantidade {
            from {
                opacity: 0;
                transform: translateY(12px) scale(0.97);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        .quantidade-icone {
            width: 58px;
            height: 58px;
            margin: 0 auto 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: #fff5d8;
            font-size: 28px;
        }

        .quantidade-card h2 {
            margin: 0 0 10px;
            color: #142b4c;
            font-size: 22px;
        }

        .quantidade-nome {
            margin: 0 0 8px;
            color: #142b4c;
            font-weight: 700;
            font-size: 16px;
        }

        .quantidade-descricao {
            margin: 0 0 22px;
            color: #687386;
            font-size: 14px;
            line-height: 1.5;
        }

        .quantidade-opcoes {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-bottom: 22px;
        }

        .quantidade-opcao {
            flex: 1;
            min-height: 76px;
            border: 2px solid #e2e7ee;
            border-radius: 14px;
            background: #fff;
            color: #142b4c;
            cursor: pointer;
            transition: 0.2s;
        }

        .quantidade-opcao:hover {
            border-color: #e9bd45;
            background: #fffaf0;
        }

        .quantidade-opcao.ativa {
            border-color: #e2b438;
            background: #fff5d8;
        }

        .quantidade-opcao strong {
            display: block;
            font-size: 23px;
        }

        .quantidade-opcao small {
            display: block;
            margin-top: 4px;
            font-size: 12px;
        }

        .quantidade-acoes {
            display: flex;
            gap: 10px;
        }

        .quantidade-acoes button {
            flex: 1;
            min-height: 45px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
        }

        .quantidade-cancelar {
            border: 1px solid #dce1e8;
            background: #fff;
            color: #536176;
        }

        .quantidade-confirmar {
            border: none;
            background: #142b4c;
            color: #fff;
        }

        .quantidade-confirmar:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }
    `;

    document.head.appendChild(estilos);

    const overlay = document.createElement("div");

    overlay.id = "modal-quantidade";
    overlay.className = "quantidade-overlay hidden";

    overlay.innerHTML = `
        <div class="quantidade-card">
            <div class="quantidade-icone">🎁</div>

            <h2>Quantas unidades?</h2>

            <p class="quantidade-nome" id="quantidade-nome"></p>

            <p class="quantidade-descricao" id="quantidade-descricao">
                Escolha quantas unidades desse presente deseja reservar.
            </p>

            <div class="quantidade-opcoes" id="quantidade-opcoes"></div>

            <div class="quantidade-acoes">
                <button type="button"
                    class="quantidade-cancelar"
                    id="quantidade-cancelar">
                    Cancelar
                </button>

                <button type="button"
                    class="quantidade-confirmar"
                    id="quantidade-confirmar"
                    disabled>
                    Confirmar
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    overlay.addEventListener("click", event => {
        if (event.target === overlay) {
            fecharModalQuantidade();
        }
    });

    document
        .getElementById("quantidade-cancelar")
        .addEventListener("click", fecharModalQuantidade);

    document
        .getElementById("quantidade-confirmar")
        .addEventListener("click", confirmarQuantidade);
}


function abrirModalQuantidade(presente) {
    presenteEmEscolha = presente;

    const overlay = document.getElementById("modal-quantidade");
    const nome = document.getElementById("quantidade-nome");
    const descricao = document.getElementById("quantidade-descricao");
    const opcoes = document.getElementById("quantidade-opcoes");
    const btnConfirmarQuantidade =
        document.getElementById("quantidade-confirmar");

    const escolhasJaFeitas = presentesSelecionados.reduce(
        (total, item) => total + item.quantidade,
        0
    );

    const escolhasRestantes =
        2 - reservasExistentes - escolhasJaFeitas;

    const limite = Math.min(
        2,
        Number(presente.disponiveis),
        escolhasRestantes
    );

    if (limite <= 0) return;

    nome.textContent = presente.nome;

    descricao.textContent =
        `Há ${presente.disponiveis} unidades disponíveis. Escolha quantas deseja reservar.`;

    opcoes.innerHTML = "";
    btnConfirmarQuantidade.disabled = true;

    presente.quantidadeEscolhida = null;

    for (let quantidade = 1; quantidade <= limite; quantidade++) {
        const botao = document.createElement("button");

        botao.type = "button";
        botao.className = "quantidade-opcao";

        botao.innerHTML = `
            <strong>${quantidade}</strong>
            <small>${quantidade === 1 ? "Unidade" : "Unidades"}</small>
        `;

        botao.addEventListener("click", () => {
            opcoes.querySelectorAll(".quantidade-opcao").forEach(opcao => {
                opcao.classList.remove("ativa");
            });

            botao.classList.add("ativa");
            presente.quantidadeEscolhida = quantidade;
            btnConfirmarQuantidade.disabled = false;
        });

        opcoes.appendChild(botao);
    }

    overlay.classList.remove("hidden");
}


function fecharModalQuantidade() {
    const overlay = document.getElementById("modal-quantidade");

    if (overlay) {
        overlay.classList.add("hidden");
    }

    presenteEmEscolha = null;
}


function confirmarQuantidade() {
    if (
        !presenteEmEscolha ||
        !presenteEmEscolha.quantidadeEscolhida
    ) {
        return;
    }

    presentesSelecionados.push({
        id: presenteEmEscolha.id,
        quantidade: presenteEmEscolha.quantidadeEscolhida
    });

    fecharModalQuantidade();
    esconderFeedback();
    renderizarPresentes();
}


// ==========================================
// NAVEGAÇÃO
// ==========================================

function mostrarTela(tela) {
    telaConfirmacao.classList.add("hidden");
    telaSucesso.classList.add("hidden");
    telaPresentes.classList.add("hidden");

    tela.classList.remove("hidden");
}


async function abrirLista() {
    mostrarTela(telaPresentes);
    await carregarPresentes();
}


// ==========================================
// TOKEN
// ==========================================

function obterToken() {
    return localStorage.getItem(TOKEN_KEY);
}


// ==========================================
// REQUISIÇÕES
// ==========================================

async function requisicao(url, options = {}) {
    const resposta = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    const dados = await resposta.json();

    if (!resposta.ok) {
        throw new Error(dados.erro || "Ocorreu um erro.");
    }

    return dados;
}


// ==========================================
// MENSAGENS
// ==========================================

function mostrarFeedback(mensagem, tipo = "sucesso") {
    mensagemFeedback.textContent = mensagem;
    mensagemFeedback.className = `feedback-message ${tipo}`;
    mensagemFeedback.classList.remove("hidden");
}


function esconderFeedback() {
    mensagemFeedback.textContent = "";
    mensagemFeedback.className = "feedback-message hidden";
}


// ==========================================
// VERIFICAR ACESSO SALVO
// ==========================================

async function verificarPresenca() {
    const token = obterToken();

    if (!token) {
        mostrarTela(telaConfirmacao);
        return;
    }

    try {
        const dados = await requisicao(
            `${API}/verificar-presenca`,
            {
                method: "POST",
                body: JSON.stringify({ token })
            }
        );

        if (dados.confirmado) {
            await abrirLista();
        } else {
            localStorage.removeItem(TOKEN_KEY);
            mostrarTela(telaConfirmacao);
        }

    } catch (erro) {
        localStorage.removeItem(TOKEN_KEY);
        mostrarTela(telaConfirmacao);
    }
}


// ==========================================
// CADASTRAR / CONFIRMAR PRESENÇA
// ==========================================

formConfirmacao.addEventListener("submit", async event => {
    event.preventDefault();

    const nome = inputNome.value.trim();

    if (nome.length < 2) {
        alert("Informe seu nome.");
        return;
    }

    btnConfirmar.disabled = true;
    btnConfirmar.textContent = "Confirmando...";

    try {
        const dados = await requisicao(
            `${API}/confirmar-presenca`,
            {
                method: "POST",
                body: JSON.stringify({ nome })
            }
        );

        if (dados.admin) {
            localStorage.removeItem(TOKEN_KEY);
            window.location.href = dados.redirect;
            return;
        }

        localStorage.setItem(TOKEN_KEY, dados.token);

        if (dados.ja_cadastrado) {
            await abrirLista();
        } else {
            mostrarTela(telaSucesso);
        }

    } catch (erro) {
        alert(erro.message);

    } finally {
        btnConfirmar.disabled = false;
        btnConfirmar.textContent = "Confirmar presença";
    }
});


// ==========================================
// BOTÃO DA TELA DE SUCESSO
// ==========================================

btnLista.addEventListener("click", abrirLista);


// ==========================================
// CADASTRAR OUTRA PESSOA
// ==========================================

btnNovoConvidado.addEventListener("click", () => {
    localStorage.removeItem(TOKEN_KEY);

    inputNome.value = "";
    presentesSelecionados = [];
    reservasExistentes = 0;

    esconderFeedback();
    mostrarTela(telaConfirmacao);

    inputNome.focus();
});


// ==========================================
// CARREGAR PRESENTES
// ==========================================

async function carregarPresentes() {
    listaPresentes.innerHTML =
        '<p class="loading">Carregando presentes...</p>';

    esconderFeedback();

    try {
        const token = obterToken();

        presentesDisponiveis = await requisicao(
            `${API}/presentes?token=${encodeURIComponent(token)}`
        );

        // Soma as unidades já reservadas pelo convidado.
        reservasExistentes = presentesDisponiveis.reduce(
            (total, presente) =>
                total + Number(presente.quantidade_selecionada || 0),
            0
        );

        presentesSelecionados = [];

        renderizarPresentes();

    } catch (erro) {
        listaPresentes.innerHTML = `
            <div class="empty-list">
                <p>Não foi possível carregar os presentes.</p>
                <button type="button" id="btn-tentar-novamente">
                    Tentar novamente
                </button>
            </div>
        `;

        document
            .getElementById("btn-tentar-novamente")
            .addEventListener("click", carregarPresentes);

        if (erro.message.includes("Confirme sua presença")) {
            localStorage.removeItem(TOKEN_KEY);
            mostrarTela(telaConfirmacao);
        }
    }
}


// ==========================================
// DESENHAR LISTA DE PRESENTES
// ==========================================

function renderizarPresentes() {
    listaPresentes.innerHTML = "";

    if (presentesDisponiveis.length === 0) {
        listaPresentes.innerHTML = `
            <div class="empty-list">
                <h3>Não há presentes cadastrados ainda.</h3>
                <p>Em breve teremos novidades por aqui!</p>
            </div>
        `;

        atualizarContador();
        return;
    }

    const unidadesSelecionadas = presentesSelecionados.reduce(
        (total, item) => total + item.quantidade,
        0
    );

    const totalEscolhas = reservasExistentes + unidadesSelecionadas;

    presentesDisponiveis.forEach(presente => {
        const item = document.createElement("button");

        item.type = "button";
        item.className = "gift-item";

        const informacoes = document.createElement("span");
        informacoes.className = "gift-information";

        const nome = document.createElement("strong");
        nome.textContent = presente.nome;

        const estoque = document.createElement("small");

        const jaEscolhido = presente.selecionado_por_mim;
        const esgotado = Number(presente.disponiveis) <= 0;

        const selecaoAtual = presentesSelecionados.find(
            selecionado => selecionado.id === presente.id
        );

        const selecionado = Boolean(selecaoAtual);

        if (jaEscolhido) {
            estoque.textContent =
                `Você já reservou ${presente.quantidade_selecionada} unidade(s)`;

            item.classList.add("already-selected");

        } else if (esgotado) {
            estoque.textContent = "Todas as unidades já foram escolhidas";
            item.classList.add("unavailable");

        } else if (selecionado) {
            estoque.textContent =
                `${selecaoAtual.quantidade} unidade(s) selecionada(s)`;

        } else if (presente.quantidade_total > 1) {
            estoque.textContent =
                `${presente.disponiveis} de ${presente.quantidade_total} disponíveis`;

        } else {
            estoque.textContent = "Disponível";
        }

        informacoes.append(nome, estoque);

        const indicador = document.createElement("span");
        indicador.className = "gift-indicator";
        indicador.textContent = jaEscolhido || selecionado ? "✓" : "+";

        item.append(informacoes, indicador);

        const limiteAtingido = totalEscolhas >= 2;

        if (jaEscolhido || esgotado) {
            item.disabled = true;

        } else if (limiteAtingido && !selecionado) {
            item.disabled = true;
            item.classList.add("limit-reached");
        }

        if (selecionado) {
            item.classList.add("selected");
        }

        item.addEventListener("click", () => {
            alternarPresente(presente);
        });

        listaPresentes.appendChild(item);
    });

    atualizarContador();
}


// ==========================================
// SELECIONAR / DESELECIONAR PRESENTE
// ==========================================

function alternarPresente(presente) {
    const indice = presentesSelecionados.findIndex(
        selecionado => selecionado.id === presente.id
    );

    if (indice !== -1) {
        presentesSelecionados.splice(indice, 1);

        esconderFeedback();
        renderizarPresentes();
        return;
    }

    const unidadesSelecionadas = presentesSelecionados.reduce(
        (total, item) => total + item.quantidade,
        0
    );

    const total = reservasExistentes + unidadesSelecionadas;

    if (total >= 2) {
        mostrarFeedback(
            "Você já escolheu suas duas unidades de presentes.",
            "aviso"
        );
        return;
    }

    if (Number(presente.disponiveis) <= 0) {
        mostrarFeedback(
            "Esse presente não está mais disponível.",
            "erro"
        );
        return;
    }

    if (Number(presente.disponiveis) > 1) {
        abrirModalQuantidade(presente);
        return;
    }

    presentesSelecionados.push({
        id: presente.id,
        quantidade: 1
    });

    esconderFeedback();
    renderizarPresentes();
}


// ==========================================
// CONTADOR E BOTÃO DE CONFIRMAÇÃO
// ==========================================

function atualizarContador() {
    const unidadesSelecionadas = presentesSelecionados.reduce(
        (total, item) => total + item.quantidade,
        0
    );

    const total = reservasExistentes + unidadesSelecionadas;

    contadorEscolhas.textContent =
        `${total} de 2 unidades escolhidas`;

    btnConfirmarEscolhas.disabled =
        presentesSelecionados.length === 0;

    if (total >= 2) {
        contadorEscolhas.classList.add("limit-reached-text");
    } else {
        contadorEscolhas.classList.remove("limit-reached-text");
    }
}


// ==========================================
// ABRIR MODAL DE CONFIRMAÇÃO FINAL
// ==========================================

btnConfirmarEscolhas.addEventListener("click", () => {
    if (presentesSelecionados.length === 0) return;

    const nomes = presentesSelecionados.map(selecao => {
        const presente = presentesDisponiveis.find(
            p => p.id === selecao.id
        );

        if (!presente) return "";

        return selecao.quantidade > 1
            ? `${presente.nome} (${selecao.quantidade} unidades)`
            : presente.nome;

    }).filter(Boolean);

    nomePresente.textContent = nomes.join(" e ");

    modal.classList.remove("hidden");
});


// ==========================================
// CANCELAR CONFIRMAÇÃO FINAL
// ==========================================

btnCancelar.addEventListener("click", () => {
    modal.classList.add("hidden");
});


// ==========================================
// CONFIRMAR RESERVAS
// ==========================================

btnReservar.addEventListener("click", async () => {
    if (presentesSelecionados.length === 0) return;

    const token = obterToken();

    btnReservar.disabled = true;
    btnReservar.textContent = "Confirmando...";

    try {
        await requisicao(
            `${API}/reservar`,
            {
                method: "POST",
                body: JSON.stringify({
                    token,
                    presentes: presentesSelecionados
                })
            }
        );

        modal.classList.add("hidden");
        presentesSelecionados = [];

        await carregarPresentes();

        mostrarFeedback(
            "Sua escolha foi confirmada! Muito obrigado pelo carinho. Ficamos muito felizes por ter você fazendo parte desse momento tão especial! 💛",
            "sucesso"
        );

    } catch (erro) {
        modal.classList.add("hidden");

        if (erro.message.includes("Confirme sua presença")) {
            localStorage.removeItem(TOKEN_KEY);
            mostrarTela(telaConfirmacao);
        } else {
            await carregarPresentes();
            mostrarFeedback(erro.message, "erro");
        }

    } finally {
        btnReservar.disabled = false;
        btnReservar.textContent = "Sim, confirmar";
    }
});


// ==========================================
// INICIALIZAÇÃO
// ==========================================

criarModalQuantidade();
verificarPresenca();

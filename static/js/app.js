
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


// NAVEGAÇÃO
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


// TOKEN
function obterToken() {
    return localStorage.getItem(TOKEN_KEY);
}


// REQUISIÇÕES
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


// MENSAGENS
function mostrarFeedback(mensagem, tipo = "sucesso") {
    mensagemFeedback.textContent = mensagem;
    mensagemFeedback.className = `feedback-message ${tipo}`;
    mensagemFeedback.classList.remove("hidden");
}

function esconderFeedback() {
    mensagemFeedback.textContent = "";
    mensagemFeedback.className = "feedback-message hidden";
}


// VERIFICAR ACESSO SALVO
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


// CADASTRAR / CONFIRMAR PRESENÇA
formConfirmacao.addEventListener("submit", async (event) => {
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


// BOTÃO DA TELA DE SUCESSO
btnLista.addEventListener("click", abrirLista);


// CADASTRAR OUTRA PESSOA NO MESMO NAVEGADOR
btnNovoConvidado.addEventListener("click", () => {
    localStorage.removeItem(TOKEN_KEY);
    inputNome.value = "";
    presentesSelecionados = [];
    reservasExistentes = 0;
    esconderFeedback();

    mostrarTela(telaConfirmacao);
    inputNome.focus();
});


// CARREGAR PRESENTES
async function carregarPresentes() {
    listaPresentes.innerHTML =
        '<p class="loading">Carregando presentes...</p>';

    esconderFeedback();

    try {
        const token = obterToken();

        const presentes = await requisicao(
            `${API}/presentes?token=${encodeURIComponent(token)}`
        );

        presentesDisponiveis = presentes;

        reservasExistentes = presentes.filter(
            presente => presente.selecionado_por_mim
        ).length;

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


// DESENHAR LISTA
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

    presentesDisponiveis.forEach((presente) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "gift-item";

        const informacoes = document.createElement("span");
        informacoes.className = "gift-information";

        const nome = document.createElement("strong");
        nome.textContent = presente.nome;

        const estoque = document.createElement("small");

        const jaEscolhido = presente.selecionado_por_mim;
        const esgotado = presente.disponiveis <= 0;
        const selecionado = presentesSelecionados.includes(presente.id);

        if (jaEscolhido) {
            estoque.textContent = "Você já escolheu este presente";
            item.classList.add("already-selected");
        } else if (esgotado) {
            estoque.textContent = "Todas as unidades já foram escolhidas";
            item.classList.add("unavailable");
        } else if (presente.quantidade_total > 1) {
            estoque.textContent =
                `${presente.disponiveis} de ${presente.quantidade_total} disponíveis`;
        } else {
            estoque.textContent = "Disponível";
        }

        informacoes.append(nome, estoque);

        const indicador = document.createElement("span");
        indicador.className = "gift-indicator";

        if (jaEscolhido) {
            indicador.textContent = "✓";
        } else if (selecionado) {
            indicador.textContent = "✓";
        } else {
            indicador.textContent = "+";
        }

        item.append(informacoes, indicador);

        const limiteAtingido =
            reservasExistentes + presentesSelecionados.length >= 2;

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


// SELECIONAR / DESELECIONAR
function alternarPresente(presente) {
    const indice = presentesSelecionados.indexOf(presente.id);

    if (indice !== -1) {
        presentesSelecionados.splice(indice, 1);
    } else {
        const total = reservasExistentes + presentesSelecionados.length;

        if (total >= 2) {
            mostrarFeedback(
                "Você já selecionou dois presentes. Desmarque um para escolher outro.",
                "aviso"
            );
            return;
        }

        if (presente.disponiveis <= 0) {
            mostrarFeedback(
                "Esse presente não está mais disponível.",
                "erro"
            );
            return;
        }

        presentesSelecionados.push(presente.id);
    }

    esconderFeedback();
    renderizarPresentes();
}


// CONTADOR E BOTÃO DE CONFIRMAÇÃO
function atualizarContador() {
    const total = reservasExistentes + presentesSelecionados.length;

    contadorEscolhas.textContent = `${total} de 2 presentes escolhidos`;

    btnConfirmarEscolhas.disabled =
        presentesSelecionados.length === 0;

    if (total >= 2) {
        contadorEscolhas.classList.add("limit-reached-text");
    } else {
        contadorEscolhas.classList.remove("limit-reached-text");
    }
}


// ABRIR MODAL DE CONFIRMAÇÃO
btnConfirmarEscolhas.addEventListener("click", () => {
    if (presentesSelecionados.length === 0) {
        return;
    }

    const nomes = presentesSelecionados.map(id => {
        const presente = presentesDisponiveis.find(p => p.id === id);
        return presente ? presente.nome : "";
    }).filter(Boolean);

    nomePresente.textContent = nomes.join(" e ");

    modal.classList.remove("hidden");
});


// CANCELAR CONFIRMAÇÃO
btnCancelar.addEventListener("click", () => {
    modal.classList.add("hidden");
});


// CONFIRMAR RESERVAS
btnReservar.addEventListener("click", async () => {
    if (presentesSelecionados.length === 0) {
        return;
    }

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


// INICIALIZAÇÃO
verificarPresenca();

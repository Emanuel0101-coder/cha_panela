
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

const modal = document.getElementById("modal-confirmacao");
const nomePresente = document.getElementById("nome-presente");
const btnCancelar = document.getElementById("btn-cancelar");
const btnReservar = document.getElementById("btn-reservar");

let presenteSelecionado = null;


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


// VERIFICAR SE JÁ EXISTE ACESSO SALVO
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

        // Acesso administrativo
        if (dados.admin) {
            localStorage.removeItem(TOKEN_KEY);
            window.location.href = dados.redirect;
            return;
        }

        // Salva o acesso individual deste convidado
        localStorage.setItem(TOKEN_KEY, dados.token);

        // Nome que já estava cadastrado: abre a lista diretamente
        if (dados.ja_cadastrado) {
            await abrirLista();
        } else {
            // Primeiro cadastro: mostra a tela de sucesso
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
    mostrarTela(telaConfirmacao);
    inputNome.focus();
});


// CARREGAR PRESENTES
async function carregarPresentes() {
    listaPresentes.innerHTML =
        '<p class="loading">Carregando presentes...</p>';

    try {
        const presentes = await requisicao(`${API}/presentes`);

        listaPresentes.innerHTML = "";

        if (presentes.length === 0) {
            listaPresentes.innerHTML = `
                <div class="empty-list">
                    <h3>Todos os presentes já foram escolhidos! 💛</h3>
                    <p>Obrigado pelo carinho e participação.</p>
                </div>
            `;
            return;
        }

        presentes.forEach((presente) => {
            const item = document.createElement("button");

            item.type = "button";
            item.className = "gift-item";

            const nome = document.createElement("span");
            nome.textContent = presente.nome;

            const seta = document.createElement("span");
            seta.className = "gift-arrow";
            seta.textContent = "›";

            item.append(nome, seta);

            item.addEventListener("click", () => {
                selecionarPresente(presente, item);
            });

            listaPresentes.appendChild(item);
        });

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
    }
}


// SELECIONAR PRESENTE
function selecionarPresente(presente, elemento) {
    document.querySelectorAll(".gift-item").forEach((item) => {
        item.classList.remove("selected");
    });

    elemento.classList.add("selected");
    presenteSelecionado = presente;
    nomePresente.textContent = presente.nome;

    modal.classList.remove("hidden");
}


// CANCELAR SELEÇÃO
btnCancelar.addEventListener("click", () => {
    modal.classList.add("hidden");

    document.querySelectorAll(".gift-item").forEach((item) => {
        item.classList.remove("selected");
    });

    presenteSelecionado = null;
});


// CONFIRMAR RESERVA
btnReservar.addEventListener("click", async () => {
    if (!presenteSelecionado) {
        return;
    }

    const token = obterToken();

    btnReservar.disabled = true;
    btnReservar.textContent = "Confirmando...";

    try {
        await requisicao(
            `${API}/reservar/${presenteSelecionado.id}`,
            {
                method: "POST",
                body: JSON.stringify({ token })
            }
        );

        modal.classList.add("hidden");
        presenteSelecionado = null;

        alert("Presente escolhido com sucesso! Muito obrigado! 💛");

        await carregarPresentes();

    } catch (erro) {
        alert(erro.message);

        if (erro.message.includes("Confirme sua presença")) {
            localStorage.removeItem(TOKEN_KEY);
            modal.classList.add("hidden");
            mostrarTela(telaConfirmacao);
        } else {
            await carregarPresentes();
            modal.classList.add("hidden");
        }

    } finally {
        btnReservar.disabled = false;
        btnReservar.textContent = "Sim, escolher";
    }
});


// INICIALIZAÇÃO
verificarPresenca();

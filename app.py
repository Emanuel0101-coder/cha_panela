import os
import secrets

import psycopg
from flask import Flask, render_template, request, jsonify, session, redirect

from database import (
    init_app,
    criar_ou_obter_convidado,
    buscar_convidado,
    listar_convidados,
    listar_presentes,
    reservar_presentes,
)


app = Flask(__name__)

app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "").strip()

app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "chave-temporaria-apenas-para-desenvolvimento",
)

app.config["ADMIN_PASSWORD"] = os.environ.get(
    "ADMIN_PASSWORD",
    "adminTubasNyra",
)

if not app.config["DATABASE_URL"]:
    raise RuntimeError(
        "A variável DATABASE_URL não foi configurada. "
        "Adicione a connection string do Neon nas variáveis de ambiente."
    )

if app.config["SECRET_KEY"] == "chave-temporaria-apenas-para-desenvolvimento":
    app.logger.warning(
        "Configure uma FLASK_SECRET_KEY forte nas variáveis do Render."
    )

init_app(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def pagina_admin():
    if not session.get("admin_autenticado"):
        return redirect("/")

    return render_template("admin.html")


def obter_dados_json():
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


def obter_token():
    token = obter_dados_json().get("token", "")

    if not isinstance(token, str) or len(token) > 256:
        return None

    return token


def validar_convidado(token):
    if not isinstance(token, str) or not token:
        return None

    return buscar_convidado(token)


@app.route("/api/confirmar-presenca", methods=["POST"])
def confirmar_presenca():
    dados = obter_dados_json()
    nome = dados.get("nome", "")

    if not isinstance(nome, str):
        return jsonify({"erro": "Nome inválido."}), 400

    nome = " ".join(nome.split())

    # Acesso administrativo
    if secrets.compare_digest(nome, app.config["ADMIN_PASSWORD"]):
        session["admin_autenticado"] = True

        return jsonify({
            "sucesso": True,
            "admin": True,
            "redirect": "/admin",
        })

    if len(nome) < 2 or len(nome) > 100:
        return jsonify({
            "erro": "Informe um nome entre 2 e 100 caracteres."
        }), 400

    token = secrets.token_urlsafe(32)

    try:
        convidado, ja_cadastrado = criar_ou_obter_convidado(
            nome,
            token,
        )

    except psycopg.Error:
        app.logger.exception("Erro ao cadastrar convidado.")

        return jsonify({
            "erro": "Não foi possível confirmar sua presença. Tente novamente."
        }), 500

    return jsonify({
        "sucesso": True,
        "admin": False,
        "token": token,
        "nome": convidado["nome"],
        "ja_cadastrado": ja_cadastrado,
    }), 201


@app.route("/api/verificar-presenca", methods=["POST"])
def verificar_presenca():
    convidado = validar_convidado(obter_token())

    if not convidado:
        return jsonify({"confirmado": False}), 401

    return jsonify({
        "confirmado": True,
        "nome": convidado["nome"],
    })


@app.route("/api/presentes", methods=["GET"])
def api_presentes():
    token = request.args.get("token", "")
    convidado = validar_convidado(token)

    if not convidado:
        return jsonify({
            "erro": "Confirme sua presença para continuar."
        }), 401

    try:
        presentes = listar_presentes(convidado["id"])

    except psycopg.Error:
        app.logger.exception("Erro ao listar presentes.")

        return jsonify({
            "erro": "Não foi possível carregar os presentes."
        }), 500

    return jsonify([
        {
            "id": presente["id"],
            "nome": presente["nome"],
            "quantidade_total": presente["quantidade_total"],
            "disponiveis": max(0, presente["disponiveis"]),
            "selecionado_por_mim": bool(
                presente["selecionado_por_mim"]
            ),
            "quantidade_selecionada": presente["quantidade_selecionada"],
        }
        for presente in presentes
    ])


@app.route("/api/reservar", methods=["POST"])
def api_reservar():
    dados = obter_dados_json()

    convidado = validar_convidado(
        dados.get("token", "")
    )

    if not convidado:
        return jsonify({
            "erro": "Confirme sua presença para continuar."
        }), 401

    presentes = dados.get("presentes", [])

    # Agora cada presente deve ser enviado como:
    # {"id": 1, "quantidade": 2}

    if (
        not isinstance(presentes, list)
        or len(presentes) == 0
        or len(presentes) > 2
    ):
        return jsonify({
            "erro": "Selecione entre um e dois presentes."
        }), 400

    ids = []

    for item in presentes:
        if not isinstance(item, dict):
            return jsonify({
                "erro": "Formato de presente inválido."
            }), 400

        presente_id = item.get("id")
        quantidade = item.get("quantidade")

        if (
            type(presente_id) is not int
            or presente_id <= 0
            or type(quantidade) is not int
            or quantidade <= 0
        ):
            return jsonify({
                "erro": "A quantidade ou o presente selecionado é inválido."
            }), 400

        ids.append(presente_id)

    if len(ids) != len(set(ids)):
        return jsonify({
            "erro": "O mesmo presente não pode ser selecionado duas vezes."
        }), 400

    try:
        sucesso, mensagem = reservar_presentes(
            convidado["id"],
            presentes,
        )

    except psycopg.Error:
        app.logger.exception("Erro ao reservar presentes.")

        return jsonify({
            "erro": "Não foi possível realizar a reserva. Tente novamente."
        }), 500

    if not sucesso:
        return jsonify({"erro": mensagem}), 409

    return jsonify({
        "sucesso": True,
        "mensagem": mensagem,
    })


@app.route("/api/admin/convidados", methods=["GET"])
def api_admin_convidados():
    if not session.get("admin_autenticado"):
        return jsonify({"erro": "Acesso não autorizado."}), 401

    try:
        convidados = listar_convidados()

    except psycopg.Error:
        app.logger.exception("Erro ao listar convidados.")

        return jsonify({
            "erro": "Não foi possível carregar os convidados."
        }), 500

    return jsonify([
        {
            "id": convidado["id"],
            "nome": convidado["nome"],
        }
        for convidado in convidados
    ])


@app.route("/api/admin/sair", methods=["POST"])
def api_admin_sair():
    session.pop("admin_autenticado", None)

    return jsonify({"sucesso": True})


if __name__ == "__main__":
    app.run(debug=True)
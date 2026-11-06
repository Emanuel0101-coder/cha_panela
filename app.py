
import os
import secrets
import sqlite3

from flask import Flask, render_template, request, jsonify, session, redirect

from database import (
    init_app,
    criar_ou_obter_convidado,
    buscar_convidado,
    listar_convidados,
    listar_presentes,
    reservar_presentes
)


app = Flask(__name__)

app.config["DATABASE"] = os.environ.get(
    "DATABASE_PATH",
    os.path.join(app.instance_path, "presentes.db")
)

app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "chave-temporaria-apenas-para-desenvolvimento"
)

app.config["ADMIN_PASSWORD"] = os.environ.get(
    "ADMIN_PASSWORD",
    "adminTubasNyra"
)

os.makedirs(app.instance_path, exist_ok=True)

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

    if not isinstance(token, str) or len(token) > 128:
        return None

    return token


def validar_convidado(token):
    if not token:
        return None

    return buscar_convidado(token)


@app.route("/api/confirmar-presenca", methods=["POST"])
def confirmar_presenca():
    dados = obter_dados_json()
    nome = dados.get("nome", "")

    if not isinstance(nome, str):
        return jsonify({"erro": "Nome inválido."}), 400

    nome = " ".join(nome.split())

    if secrets.compare_digest(nome, app.config["ADMIN_PASSWORD"]):
        session["admin_autenticado"] = True
        return jsonify({
            "sucesso": True,
            "admin": True,
            "redirect": "/admin"
        })

    if len(nome) < 2 or len(nome) > 100:
        return jsonify({
            "erro": "Informe um nome entre 2 e 100 caracteres."
        }), 400

    token = secrets.token_urlsafe(32)

    try:
        convidado, ja_cadastrado = criar_ou_obter_convidado(
            nome, token
        )

    except sqlite3.Error:
        return jsonify({
            "erro": "Não foi possível confirmar sua presença."
        }), 500

    return jsonify({
        "sucesso": True,
        "admin": False,
        "token": token,
        "nome": convidado["nome"],
        "ja_cadastrado": ja_cadastrado
    }), 201


@app.route("/api/verificar-presenca", methods=["POST"])
def verificar_presenca():
    convidado = validar_convidado(obter_token())

    if not convidado:
        return jsonify({"confirmado": False}), 401

    return jsonify({
        "confirmado": True,
        "nome": convidado["nome"]
    })


@app.route("/api/presentes", methods=["GET"])
def api_presentes():
    token = request.args.get("token", "")
    convidado = validar_convidado(token)

    if not convidado:
        return jsonify({
            "erro": "Confirme sua presença para continuar."
        }), 401

    presentes = listar_presentes(convidado["id"])

    return jsonify([
        {
            "id": presente["id"],
            "nome": presente["nome"],
            "quantidade_total": presente["quantidade_total"],
            "disponiveis": max(0, presente["disponiveis"]),
            "selecionado_por_mim": bool(
                presente["selecionado_por_mim"]
            )
        }
        for presente in presentes
    ])


@app.route("/api/reservar", methods=["POST"])
def api_reservar():
    dados = obter_dados_json()
    convidado = validar_convidado(dados.get("token", ""))

    if not convidado:
        return jsonify({
            "erro": "Confirme sua presença para continuar."
        }), 401

    presentes_ids = dados.get("presentes", [])

    if (
        not isinstance(presentes_ids, list)
        or len(presentes_ids) == 0
        or len(presentes_ids) > 2
        or any(type(item) is not int or item <= 0 for item in presentes_ids)
    ):
        return jsonify({
            "erro": "Selecione entre um e dois presentes."
        }), 400

    try:
        sucesso, mensagem = reservar_presentes(
            convidado["id"],
            presentes_ids
        )

    except sqlite3.Error:
        return jsonify({
            "erro": "Não foi possível realizar a reserva."
        }), 500

    if not sucesso:
        return jsonify({"erro": mensagem}), 409

    return jsonify({
        "sucesso": True,
        "mensagem": mensagem
    })


@app.route("/api/admin/convidados", methods=["GET"])
def api_admin_convidados():
    if not session.get("admin_autenticado"):
        return jsonify({"erro": "Acesso não autorizado."}), 401

    convidados = listar_convidados()

    return jsonify([
        {"id": convidado["id"], "nome": convidado["nome"]}
        for convidado in convidados
    ])


@app.route("/api/admin/sair", methods=["POST"])
def api_admin_sair():
    session.pop("admin_autenticado", None)
    return jsonify({"sucesso": True})


if __name__ == "__main__":
    app.run(debug=True)

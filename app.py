
import os
import secrets
import sqlite3

from flask import Flask, render_template, request, jsonify, session, redirect

from database import (
    init_app,
    criar_convidado,
    buscar_convidado,
    listar_convidados,
    listar_presentes,
    reservar_presente,
    nome_ja_cadastrado
)


app = Flask(__name__)

app.config["DATABASE"] = os.path.join(
    app.instance_path,
    "presentes.db"
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

    # Acesso administrativo
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

    
    ja_cadastrado = nome_ja_cadastrado(nome)

    token = secrets.token_urlsafe(32)

    try:
        criar_convidado(nome, token)

    except sqlite3.Error:
        return jsonify({
            "erro": "Não foi possível confirmar sua presença."
        }), 500

    return jsonify({
        "sucesso": True,
        "admin": False,
        "token": token,
        "nome": nome,
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
    presentes = listar_presentes()

    return jsonify([
        {"id": presente["id"], "nome": presente["nome"]}
        for presente in presentes
    ])


@app.route("/api/reservar/<int:presente_id>", methods=["POST"])
def api_reservar(presente_id):
    convidado = validar_convidado(obter_token())

    if not convidado:
        return jsonify({
            "erro": "Confirme sua presença para continuar."
        }), 401

    try:
        reservado = reservar_presente(presente_id)

    except sqlite3.Error:
        return jsonify({
            "erro": "Não foi possível realizar a reserva."
        }), 500

    if not reservado:
        return jsonify({
            "erro": "Este presente já foi escolhido por outra pessoa."
        }), 409

    return jsonify({
        "sucesso": True,
        "mensagem": "Presente escolhido com sucesso!"
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

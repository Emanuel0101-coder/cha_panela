
import sqlite3
import hashlib
from pathlib import Path
from flask import current_app, g


PRESENTES_TESTE = [
    "Jogo de panelas",
    "Frigideira antiaderente",
    "Panela de pressão",
    "Jogo de pratos",
    "Jogo de copos",
    "Talheres (jogo completo)",
    "Conjunto de xícaras",
    "Potes organizadores",
    "Escorredor de louças",
    "Tábua de corte"
]


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        g.db = sqlite3.connect(db_path, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db_path = current_app.config["DATABASE"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = get_db()
    schema_path = Path(current_app.root_path) / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as arquivo:
        db.executescript(arquivo.read())

    # Remove a regra antiga que impedia nomes repetidos.
    db.execute("DROP INDEX IF EXISTS idx_convidados_nome_unico")

    # Insere os presentes de teste somente se a lista estiver vazia.
    quantidade = db.execute(
        "SELECT COUNT(*) FROM presentes"
    ).fetchone()[0]

    if quantidade == 0:
        db.executemany(
            "INSERT INTO presentes (nome) VALUES (?)",
            [(nome,) for nome in PRESENTES_TESTE]
        )

    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()


def gerar_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_convidado(nome, token):
    db = get_db()
    token_hash = gerar_hash(token)

    cursor = db.execute(
        """
        INSERT INTO convidados (nome, token_hash)
        VALUES (?, ?)
        """,
        (nome, token_hash)
    )

    db.commit()
    return cursor.lastrowid


def buscar_convidado(token):
    db = get_db()
    token_hash = gerar_hash(token)

    return db.execute(
        """
        SELECT id, nome
        FROM convidados
        WHERE token_hash = ?
        """,
        (token_hash,)
    ).fetchone()


def listar_convidados():
    db = get_db()

    return db.execute(
        """
        SELECT id, nome
        FROM convidados
        ORDER BY nome COLLATE NOCASE
        """
    ).fetchall()


def listar_presentes():
    db = get_db()

    return db.execute(
        """
        SELECT id, nome
        FROM presentes
        WHERE reservado = 0
        ORDER BY nome COLLATE NOCASE
        """
    ).fetchall()


def reservar_presente(presente_id):
    db = get_db()

    try:
        cursor = db.execute(
            """
            UPDATE presentes
            SET reservado = 1
            WHERE id = ? AND reservado = 0
            """,
            (presente_id,)
        )

        db.commit()
        return cursor.rowcount == 1

    except sqlite3.Error:
        db.rollback()
        raise


def adicionar_presente(nome):
    db = get_db()

    cursor = db.execute(
        "INSERT INTO presentes (nome) VALUES (?)",
        (nome,)
    )

    db.commit()
    return cursor.lastrowid


def nome_ja_cadastrado(nome):
    db = get_db()

    resultado = db.execute(
        """
        SELECT id
        FROM convidados
        WHERE nome = ? COLLATE NOCASE
        LIMIT 1
        """,
        (nome,)
    ).fetchone()

    return resultado is not None


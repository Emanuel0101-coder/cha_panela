
import sqlite3
import hashlib
from pathlib import Path
from flask import current_app, g


PRESENTES_TESTE = [
    ("Jogo de panelas", 1),
    ("Frigideira antiaderente", 1),
    ("Panela de pressão", 1),
    ("Jogo de pratos", 1),
    ("Jogo de copos", 1),
    ("Talheres (jogo completo)", 1),
    ("Conjunto de xícaras", 1),
    ("Potes organizadores", 1),
    ("Escorredor de louças", 1),
    ("Tábua de corte", 1),
    ("Jogo de lençol", 2)
]


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        g.db = sqlite3.connect(db_path, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA busy_timeout = 10000")
        g.db.execute("PRAGMA foreign_keys = ON")
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

    # Compatibilidade com o banco antigo.
    colunas = {
        coluna["name"]
        for coluna in db.execute("PRAGMA table_info(presentes)").fetchall()
    }

    if "quantidade_total" not in colunas:
        db.execute("""
            ALTER TABLE presentes
            ADD COLUMN quantidade_total INTEGER NOT NULL DEFAULT 1
        """)

    # Copia os tokens antigos para a tabela de múltiplos acessos.
    db.execute("""
        INSERT OR IGNORE INTO tokens_convidados (token_hash, convidado_id)
        SELECT token_hash, id FROM convidados
    """)

    # Reúne convidados duplicados, sem perder seus tokens.
    duplicados = db.execute("""
        SELECT id, MIN(id) OVER (
            PARTITION BY lower(trim(nome))
        ) AS id_principal
        FROM convidados
    """).fetchall()

    for pessoa in duplicados:
        if pessoa["id"] != pessoa["id_principal"]:
            db.execute("""
                UPDATE tokens_convidados
                SET convidado_id = ?
                WHERE convidado_id = ?
            """, (pessoa["id_principal"], pessoa["id"]))

            db.execute("""
                DELETE FROM convidados WHERE id = ?
            """, (pessoa["id"],))

    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_nome_unico
        ON convidados(lower(trim(nome)))
    """)

    # Insere a lista inicial se estiver vazia.
    quantidade = db.execute(
        "SELECT COUNT(*) FROM presentes"
    ).fetchone()[0]

    if quantidade == 0:
        db.executemany("""
            INSERT INTO presentes (nome, quantidade_total)
            VALUES (?, ?)
        """, PRESENTES_TESTE)

    else:
        # Acrescenta o lençol de teste sem duplicá-lo.
        db.execute("""
            INSERT INTO presentes (nome, quantidade_total)
            SELECT ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM presentes
                WHERE nome = ? COLLATE NOCASE
            )
        """, ("Jogo de lençol", 2, "Jogo de lençol"))

    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()


def gerar_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_ou_obter_convidado(nome, token):
    db = get_db()
    token_hash = gerar_hash(token)

    try:
        db.execute("BEGIN IMMEDIATE")

        convidado = db.execute("""
            SELECT id, nome
            FROM convidados
            WHERE lower(trim(nome)) = lower(trim(?))
            LIMIT 1
        """, (nome,)).fetchone()

        ja_cadastrado = convidado is not None

        if convidado is None:
            cursor = db.execute("""
                INSERT INTO convidados (nome, token_hash)
                VALUES (?, ?)
            """, (nome, token_hash))

            convidado_id = cursor.lastrowid
            nome_final = nome

        else:
            convidado_id = convidado["id"]
            nome_final = convidado["nome"]

        db.execute("""
            INSERT INTO tokens_convidados (token_hash, convidado_id)
            VALUES (?, ?)
        """, (token_hash, convidado_id))

        db.commit()

        return {
            "id": convidado_id,
            "nome": nome_final
        }, ja_cadastrado

    except sqlite3.Error:
        db.rollback()
        raise


def buscar_convidado(token):
    db = get_db()
    token_hash = gerar_hash(token)

    return db.execute("""
        SELECT c.id, c.nome
        FROM tokens_convidados t
        JOIN convidados c ON c.id = t.convidado_id
        WHERE t.token_hash = ?
    """, (token_hash,)).fetchone()


def listar_convidados():
    db = get_db()

    return db.execute("""
        SELECT id, nome
        FROM convidados
        ORDER BY nome COLLATE NOCASE
    """).fetchall()


def listar_presentes(convidado_id):
    db = get_db()

    return db.execute("""
        SELECT
            p.id,
            p.nome,
            p.quantidade_total,
            (
                p.quantidade_total
                - p.reservado
                - (
                    SELECT COUNT(*)
                    FROM reservas r
                    WHERE r.presente_id = p.id
                )
            ) AS disponiveis,
            EXISTS (
                SELECT 1
                FROM reservas r
                WHERE r.presente_id = p.id
                AND r.convidado_id = ?
            ) AS selecionado_por_mim
        FROM presentes p
        ORDER BY p.nome COLLATE NOCASE
    """, (convidado_id,)).fetchall()


def contar_reservas(convidado_id):
    db = get_db()

    return db.execute("""
        SELECT COUNT(*)
        FROM reservas
        WHERE convidado_id = ?
    """, (convidado_id,)).fetchone()[0]


def reservar_presentes(convidado_id, presentes_ids):
    db = get_db()

    # Remove IDs repetidos sem alterar a ordem.
    presentes_ids = list(dict.fromkeys(presentes_ids))

    if not presentes_ids:
        return False, "Selecione pelo menos um presente."

    try:
        db.execute("BEGIN IMMEDIATE")

        quantidade_atual = db.execute("""
            SELECT COUNT(*)
            FROM reservas
            WHERE convidado_id = ?
        """, (convidado_id,)).fetchone()[0]

        if quantidade_atual + len(presentes_ids) > 2:
            db.rollback()
            return False, "Você pode escolher no máximo dois presentes."

        for presente_id in presentes_ids:
            presente = db.execute("""
                SELECT
                    p.id,
                    p.quantidade_total - p.reservado - (
                        SELECT COUNT(*)
                        FROM reservas r
                        WHERE r.presente_id = p.id
                    ) AS disponiveis
                FROM presentes p
                WHERE p.id = ?
            """, (presente_id,)).fetchone()

            if presente is None:
                db.rollback()
                return False, "Um dos presentes selecionados não existe."

            if presente["disponiveis"] <= 0:
                db.rollback()
                return False, "Um dos presentes acabou de ser escolhido."

            db.execute("""
                INSERT INTO reservas (convidado_id, presente_id)
                VALUES (?, ?)
            """, (convidado_id, presente_id))

        db.commit()
        return True, "Presentes escolhidos com sucesso!"

    except sqlite3.IntegrityError:
        db.rollback()
        return False, "Você já escolheu um desses presentes."

    except sqlite3.Error:
        db.rollback()
        raise


def adicionar_presente(nome, quantidade=1):
    db = get_db()

    cursor = db.execute("""
        INSERT INTO presentes (nome, quantidade_total)
        VALUES (?, ?)
    """, (nome, quantidade))

    db.commit()
    return cursor.lastrowid
